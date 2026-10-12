import * as THREE from "./vendor/three/three.module.js";
import { OrbitControls } from "./vendor/three/examples/jsm/controls/OrbitControls.js";
import * as WebIFC from "./vendor/web-ifc/web-ifc-api.js";

import { accumulateGeometryEvidence, finalizeGeometryEvidence } from "./geometry-evidence.js";
import { buildRenderBatches, createSelectionGroup, expressIDForHit } from "./render-batches.js";

let sceneState = null;

export function summarizeGeometryEvidence(elementBounds, vertexCount, triangleCount, meshCount) {
  const elementExtents = {};
  const overall = new THREE.Box3();
  for (const [expressID, box] of elementBounds) {
    const size = box.getSize(new THREE.Vector3());
    // web-ifc's viewer coordinates are Y-up. Normalize measurements back to
    // IFC/IfcOpenShell Z-up axes before cross-engine comparison.
    elementExtents[String(expressID)] = [size.x, size.z, size.y];
    overall.union(box);
  }
  const overallVector = overall.isEmpty() ? null : overall.getSize(new THREE.Vector3());
  const overallSize = overallVector ? [overallVector.x, overallVector.z, overallVector.y] : null;
  return {
    engine: "web-ifc",
    origin_mode: "model-centred",
    axis_mapping: "web-ifc Y-up normalized to IFC Z-up [x,z,y]",
    element_ids: [...elementBounds.keys()].sort((a, b) => a - b),
    element_extents_metres: elementExtents,
    overall_extents_metres: overallSize,
    vertices: vertexCount,
    triangles: triangleCount,
    mesh_groups: meshCount,
  };
}

function disposePrevious() {
  if (!sceneState) return;
  clearSelection();
  cancelAnimationFrame(sceneState.frame);
  if (sceneState.batches) {
    sceneState.scene.remove(sceneState.modelGroup);
    sceneState.batches.dispose();
  }
  sceneState.scene.traverse((object) => {
    if (object.geometry) object.geometry.dispose();
    if (object.material) {
      const materials = Array.isArray(object.material) ? object.material : [object.material];
      materials.forEach((material) => material.dispose());
    }
  });
  sceneState.controls.dispose();
  sceneState.renderer.dispose();
  sceneState.resize.disconnect();
  sceneState.canvas.remove();
  sceneState = null;
}

function createScene(container) {
  disposePrevious();
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0xe7ece5);
  const camera = new THREE.PerspectiveCamera(42, 1, 0.01, 100000);
  camera.position.set(12, 10, 12);
  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  container.prepend(renderer.domElement);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  const ambient = new THREE.HemisphereLight(0xffffff, 0x617269, 2.1);
  scene.add(ambient);
  const sun = new THREE.DirectionalLight(0xffffff, 2.5);
  sun.position.set(10, 18, 8);
  scene.add(sun);
  const grid = new THREE.GridHelper(30, 30, 0x7b8d83, 0xcbd3cc);
  scene.add(grid);

  const resize = new ResizeObserver(() => {
    const width = Math.max(container.clientWidth, 1);
    const height = 380;
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    current.dirty = true;
  });
  resize.observe(container);

  const current = {
    scene,
    camera,
    renderer,
    controls,
    resize,
    canvas: renderer.domElement,
    frame: 0,
    expressMeshes: new Map(),
    selectedMaterials: [],
    selectedMeshes: [],
    contextStates: [],
    selectedMeshObjects: [],
    selectionMode: "xray",
    selectionHelper: null,
    modelGroup: null,
    diagnostics: null,
    frameCount: 0,
    startedAt: performance.now(),
    lastFrameAt: null,
    contextLost: false,
    dirty: true,
    probing: false,
    batches: null,
    selectionGroup: null,
    selectedIDs: [],
  };
  controls.addEventListener("change", () => { current.dirty = true; });
  renderer.domElement.addEventListener("webglcontextlost", (event) => {
    event.preventDefault();
    current.contextLost = true;
  });
  renderer.domElement.addEventListener("webglcontextrestored", () => {
    current.contextLost = false;
    current.dirty = true;
  });
  const animate = () => {
    controls.update();
    if (current.dirty || current.probing) {
      current.dirty = false;
      renderer.render(scene, camera);
      current.frameCount += 1;
      current.lastFrameAt = performance.now();
    }
    current.frame = requestAnimationFrame(animate);
  };
  animate();
  sceneState = current;
  return current;
}

function fitCamera(camera, controls, object) {
  const box = new THREE.Box3().setFromObject(object);
  fitCameraToBox(camera, controls, box);
}

export function fitCameraToBox(camera, controls, box, options = {}) {
  if (box.isEmpty()) return;
  const center = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3());
  const radius = Math.max(size.x, size.y, size.z, 1);
  let direction;
  if (options.preferSide) {
    // IFC Z is viewer Y. For broad, low elements such as exported perimeter
    // walls, use a lower side-oblique view so roofs do not hide the selection.
    direction = size.x >= size.z
      ? new THREE.Vector3(0.15, 0.3, 1).normalize()
      : new THREE.Vector3(1, 0.3, 0.15).normalize();
  } else {
    direction = camera.position.clone().sub(controls.target).normalize();
  }
  if (!Number.isFinite(direction.x)) direction.set(1, 0.8, 1).normalize();
  camera.position.copy(center).addScaledVector(direction, radius * 2.2);
  camera.near = Math.max(radius / 1000, 0.01);
  camera.far = Math.max(radius * 100, 1000);
  camera.updateProjectionMatrix();
  controls.target.copy(center);
  controls.update();
}

export function restoreMaterialStates(states) {
  for (const original of states) {
    original.material.color.copy(original.color);
    original.material.emissive.copy(original.emissive);
    original.material.emissiveIntensity = original.emissiveIntensity;
    original.material.opacity = original.opacity;
    original.material.transparent = original.transparent;
    original.material.depthTest = original.depthTest;
    original.material.depthWrite = original.depthWrite;
    original.material.needsUpdate = true;
  }
}

export function applySelectionAppearance(meshes) {
  const states = [];
  const meshStates = [];
  const selectedBox = new THREE.Box3();
  const seenMaterials = new Set();
  for (const mesh of meshes) {
    meshStates.push({ mesh, renderOrder: mesh.renderOrder });
    mesh.renderOrder = 10_000;
    selectedBox.expandByObject(mesh);
    const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
    for (const material of materials) {
      if (seenMaterials.has(material)) continue;
      seenMaterials.add(material);
      states.push({
        material,
        color: material.color.clone(),
        emissive: material.emissive.clone(),
        emissiveIntensity: material.emissiveIntensity,
        opacity: material.opacity,
        transparent: material.transparent,
        depthTest: material.depthTest,
        depthWrite: material.depthWrite,
      });
      material.color.set(0xffc83d);
      material.emissive.set(0x6b3f00);
      material.emissiveIntensity = 1.25;
      material.opacity = 1;
      material.transparent = false;
      // Draw selected geometry over occluding roofs, façades, and finishes.
      material.depthTest = false;
      material.depthWrite = false;
      material.needsUpdate = true;
    }
  }
  return { states, meshStates, selectedBox };
}

function restoreContextStates(current) {
  for (const state of current.contextStates) {
    state.mesh.visible = state.visible;
    if (state.materials) restoreMaterialStates(state.materials);
  }
  current.contextStates = [];
}

function applyContextMode(current) {
  if (current.batches) {
    current.batches.setSelection(current.selectedIDs, current.selectionMode);
    current.dirty = true;
    return;
  }
  restoreContextStates(current);
  if (!current.modelGroup || current.selectionMode === "xray") return;
  const selected = new Set(current.selectedMeshObjects);
  for (const mesh of current.modelGroup.children) {
    if (selected.has(mesh)) continue;
    if (current.selectionMode === "isolate") {
      current.contextStates.push({ mesh, visible: mesh.visible });
      mesh.visible = false;
      continue;
    }
    if (current.selectionMode === "fade") {
      const materials = (Array.isArray(mesh.material) ? mesh.material : [mesh.material]).map((material) => ({
        material,
        color: material.color.clone(),
        emissive: material.emissive.clone(),
        emissiveIntensity: material.emissiveIntensity,
        opacity: material.opacity,
        transparent: material.transparent,
        depthTest: material.depthTest,
        depthWrite: material.depthWrite,
      }));
      current.contextStates.push({ mesh, visible: mesh.visible, materials });
      for (const { material } of materials) {
        material.opacity = Math.min(material.opacity, 0.08);
        material.transparent = true;
        material.depthWrite = false;
        material.needsUpdate = true;
      }
    }
  }
}

export function setSelectionMode(mode) {
  if (!sceneState || !["xray", "fade", "isolate"].includes(mode)) return false;
  sceneState.selectionMode = mode;
  if (sceneState.selectedMeshObjects.length) applyContextMode(sceneState);
  return true;
}

export function clearSelection() {
  if (!sceneState) return;
  restoreContextStates(sceneState);
  restoreMaterialStates(sceneState.selectedMaterials);
  sceneState.selectedMaterials = [];
  for (const original of sceneState.selectedMeshes) original.mesh.renderOrder = original.renderOrder;
  sceneState.selectedMeshes = [];
  sceneState.selectedMeshObjects = [];
  sceneState.selectedIDs = [];
  if (sceneState.selectionGroup) {
    sceneState.scene.remove(sceneState.selectionGroup);
    const materials = new Set(sceneState.selectionGroup.children.map(mesh => mesh.material));
    for (const material of materials) material.dispose();
    sceneState.selectionGroup = null;
  }
  sceneState.batches?.setSelection();
  sceneState.dirty = true;
  if (sceneState.selectionHelper) {
    sceneState.scene.remove(sceneState.selectionHelper);
    sceneState.selectionHelper.geometry.dispose();
    sceneState.selectionHelper.material.dispose();
    sceneState.selectionHelper = null;
  }
}

export function selectExpressID(expressID, focus = true) {
  return selectExpressIDs([expressID], focus);
}

export function selectExpressIDs(expressIDs, focus = true) {
  if (!sceneState) return false;
  const sources = [...new Set(expressIDs.map(Number))]
    .flatMap((expressID) => sceneState.expressMeshes.get(expressID) || []);
  if (!sources.length) return false;
  clearSelection();
  // Only selected originals become separate draw objects. Clone their materials
  // so the shared batch materials (and unrelated elements) never turn amber.
  const selectionGroup = createSelectionGroup(sources);
  const meshes = selectionGroup.children;
  sceneState.selectionGroup = selectionGroup;
  sceneState.selectedIDs = [...new Set(sources.map(source => source.userData.expressID))];
  sceneState.scene.add(selectionGroup);
  const { states, meshStates, selectedBox } = applySelectionAppearance(meshes);
  sceneState.selectedMaterials = states;
  sceneState.selectedMeshes = meshStates;
  sceneState.selectedMeshObjects = meshes;
  applyContextMode(sceneState);
  sceneState.selectionHelper = new THREE.Box3Helper(selectedBox, 0xff6b1a);
  sceneState.scene.add(sceneState.selectionHelper);
  if (focus) fitCameraToBox(sceneState.camera, sceneState.controls, selectedBox, { preferSide: true });
  return true;
}

function enableCanvasPicking(current) {
  const raycaster = new THREE.Raycaster();
  const pointer = new THREE.Vector2();
  let start = null;
  current.canvas.addEventListener("pointerdown", (event) => { start = [event.clientX, event.clientY]; });
  current.canvas.addEventListener("pointerup", (event) => {
    if (!start || Math.hypot(event.clientX - start[0], event.clientY - start[1]) > 4) return;
    const bounds = current.canvas.getBoundingClientRect();
    pointer.x = ((event.clientX - bounds.left) / bounds.width) * 2 - 1;
    pointer.y = -((event.clientY - bounds.top) / bounds.height) * 2 + 1;
    raycaster.setFromCamera(pointer, current.camera);
    // Raycaster does not skip invisible objects. Filter hidden context explicitly.
    const pickable = [...(current.modelGroup?.children || []), ...(current.selectionGroup?.children || [])].filter(mesh => mesh.visible);
    const hit = raycaster.intersectObjects(pickable, false)[0];
    const expressID = expressIDForHit(hit);
    if (expressID == null) return;
    selectExpressID(expressID, false);
    globalThis.dispatchEvent(new CustomEvent("ifc-element-selected", { detail: { expressID } }));
  });
}

export async function loadIfcGeometry(bytes, container) {
  const current = createScene(container);
  const api = new WebIFC.IfcAPI();
  // web-ifc otherwise treats this as relative to its generated script prefix,
  // which can duplicate the vendor path when loaded as an ES module.
  const wasmBase = new URL("./vendor/web-ifc/", import.meta.url).href;
  api.SetWasmPath(wasmBase, true);
  await api.Init();
  const modelID = api.OpenModel(bytes, { COORDINATE_TO_ORIGIN: true, CIRCLE_SEGMENTS: 128 });
  const group = new THREE.Group();
  const materials = new Map();
  const geometriesByID = new Map();
  let meshCount = 0;
  let vertexCount = 0;
  let triangleCount = 0;
  const elementBounds = new Map();
  const measuredGeometry = new Map();

  api.StreamAllMeshes(modelID, (flatMesh) => {
    const geometries = flatMesh.geometries;
    for (let index = 0; index < geometries.size(); index += 1) {
      const placed = geometries.get(index);
      const source = api.GetGeometry(modelID, placed.geometryExpressID);
      const vertexData = api.GetVertexArray(source.GetVertexData(), source.GetVertexDataSize());
      const indexData = api.GetIndexArray(source.GetIndexData(), source.GetIndexDataSize());
      accumulateGeometryEvidence(measuredGeometry, flatMesh.expressID, vertexData, indexData, placed.flatTransformation);
      let geometry = geometriesByID.get(placed.geometryExpressID);
      if (!geometry) {
        const positions = new Float32Array((vertexData.length / 6) * 3);
        const normals = new Float32Array((vertexData.length / 6) * 3);
        for (let sourceIndex = 0, targetIndex = 0; sourceIndex < vertexData.length; sourceIndex += 6, targetIndex += 3) {
          positions.set(vertexData.subarray(sourceIndex, sourceIndex + 3), targetIndex);
          normals.set(vertexData.subarray(sourceIndex + 3, sourceIndex + 6), targetIndex);
        }
        geometry = new THREE.BufferGeometry();
        geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
        geometry.setAttribute("normal", new THREE.BufferAttribute(normals, 3));
        geometry.setIndex(new THREE.BufferAttribute(new Uint32Array(indexData), 1));
        geometry.computeBoundingBox();
        geometriesByID.set(placed.geometryExpressID, geometry);
      }
      const color = placed.color;
      const materialKey = [color.x, color.y, color.z, color.w].join(",");
      let material = materials.get(materialKey);
      if (!material) {
        material = new THREE.MeshStandardMaterial({
          color: new THREE.Color(color.x, color.y, color.z),
          opacity: color.w,
          transparent: color.w < 1,
          roughness: 0.78,
          metalness: 0.02,
          side: THREE.DoubleSide,
        });
        materials.set(materialKey, material);
      }
      const mesh = new THREE.Mesh(geometry, material);
      mesh.userData.expressID = flatMesh.expressID;
      mesh.applyMatrix4(new THREE.Matrix4().fromArray(placed.flatTransformation));
      mesh.updateMatrixWorld(true);
      geometry.computeBoundingBox();
      const placedBounds = geometry.boundingBox.clone().applyMatrix4(mesh.matrixWorld);
      const accumulatedBounds = elementBounds.get(flatMesh.expressID) || new THREE.Box3();
      accumulatedBounds.union(placedBounds);
      elementBounds.set(flatMesh.expressID, accumulatedBounds);
      group.add(mesh);
      const elementMeshes = current.expressMeshes.get(flatMesh.expressID) || [];
      elementMeshes.push(mesh);
      current.expressMeshes.set(flatMesh.expressID, elementMeshes);
      meshCount += 1;
      vertexCount += geometry.attributes.position.count;
      triangleCount += indexData.length / 3;
      source.delete();
    }
  });

  const measuredEvidence = finalizeGeometryEvidence(measuredGeometry, api.GetCoordinationMatrix(modelID));
  api.CloseModel(modelID);
  current.diagnostics = summarizeGeometryEvidence(
    elementBounds, vertexCount, triangleCount, meshCount,
  );
  Object.assign(current.diagnostics, measuredEvidence);
  current.diagnostics.engine_version = api.GetVersion();
  current.diagnostics.settings = { coordinate_to_origin: true, circle_segments: 128 };
  current.diagnostics.source_sha256 = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)), value => value.toString(16).padStart(2, "0")).join("");
  current.diagnostics.source_size_bytes = bytes.length;
  current.diagnostics.axis_mapping = "web-ifc Y-up normalized to IFC Z-up [x,-z,y], recentering reversed";
  current.diagnostics.element_extents_metres = Object.fromEntries(Object.entries(measuredEvidence.element_bounds_metres).map(([id, box]) => [id, box.maximum.map((v, i) => v - box.minimum[i])]));
  if (meshCount) {
    current.batches = buildRenderBatches(group.children);
    current.modelGroup = current.batches.group;
    current.scene.add(current.modelGroup);
    current.diagnostics.rendering = current.batches.stats;
    current.dirty = true;
    fitCamera(current.camera, current.controls, current.modelGroup);
    enableCanvasPicking(current);
  }
  return meshCount;
}

export function getGeometryDiagnostics() {
  return sceneState?.diagnostics ? structuredClone(sceneState.diagnostics) : null;
}

export function frameModel() {
  if (!sceneState?.modelGroup) return false;
  fitCamera(sceneState.camera, sceneState.controls, sceneState.modelGroup);
  sceneState.dirty = true;
  return true;
}

function getRendererEvidence(current) {
  const context = current.renderer.getContext();
  const debugInfo = context.getExtension("WEBGL_debug_renderer_info");
  const rendererInfo = current.renderer.info;
  const canvasBounds = current.canvas.getBoundingClientRect();
  return {
    webgl_version: current.renderer.capabilities.isWebGL2 ? "WebGL 2" : "WebGL 1",
    renderer: debugInfo
      ? context.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL)
      : context.getParameter(context.RENDERER),
    vendor: debugInfo
      ? context.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL)
      : context.getParameter(context.VENDOR),
    precision: current.renderer.capabilities.precision,
    max_texture_size: current.renderer.capabilities.maxTextureSize,
    max_samples: current.renderer.capabilities.maxSamples,
    context_lost: current.contextLost || context.isContextLost(),
    canvas_css_pixels: [Math.round(canvasBounds.width), Math.round(canvasBounds.height)],
    drawing_buffer_pixels: [context.drawingBufferWidth, context.drawingBufferHeight],
    render_calls: rendererInfo.render.calls,
    rendered_triangles: rendererInfo.render.triangles,
    gpu_geometries: rendererInfo.memory.geometries,
    gpu_textures: rendererInfo.memory.textures,
    frame_count: current.frameCount,
    rendering: current.batches?.stats || null,
    render_mode: "on-demand; continuous during GPU probe",
    selection_mode: current.selectionMode,
    selected_element_ids: [...current.selectedIDs],
    camera_position: current.camera.position.toArray(),
    camera_target: current.controls.target.toArray(),
  };
}

export function getRenderingDiagnostics() {
  return sceneState ? getRendererEvidence(sceneState) : null;
}

export async function runGpuValidation(durationMs = 2000) {
  if (!sceneState) throw new Error("Load IFC geometry before running the browser/GPU check.");
  const current = sceneState;
  const startedAt = performance.now();
  const startingFrame = current.frameCount;
  current.probing = true;
  try {
    await new Promise((resolve) => setTimeout(resolve, Math.max(500, durationMs)));
  } finally {
    current.probing = false;
  }
  if (sceneState !== current) throw new Error("The active model changed during the GPU check.");
  const elapsedMs = performance.now() - startedAt;
  const renderedFrames = current.frameCount - startingFrame;
  const evidence = getRendererEvidence(current);
  const geometry = current.diagnostics || {};
  const averageFps = Math.round((renderedFrames * 1000 / Math.max(elapsedMs, 1)) * 10) / 10;
  const capabilityChecks = [
    { id: "webgl_context", passed: Boolean(evidence.webgl_version) && !evidence.context_lost, message: `${evidence.webgl_version} context is active.` },
    { id: "canvas_size", passed: evidence.drawing_buffer_pixels.every((value) => value > 0), message: `Drawing buffer is ${evidence.drawing_buffer_pixels.join(" × ")} pixels.` },
    { id: "visible_meshes", passed: Number(geometry.mesh_groups || 0) > 0, message: `${Number(geometry.mesh_groups || 0).toLocaleString()} mesh group(s) are loaded.` },
    { id: "rendered_frames", passed: renderedFrames >= 10, message: `${renderedFrames} frames rendered during the probe.` },
    { id: "draw_calls", passed: evidence.render_calls > 0 && evidence.rendered_triangles > 0, message: `${evidence.render_calls} draw call(s), ${evidence.rendered_triangles.toLocaleString()} triangle(s) in the latest frame.` },
  ];
  const performanceCheck = {
    id: "interactive_frame_rate",
    passed: averageFps >= 20,
    message: `${averageFps} average FPS (interactive target: at least 20 FPS).`,
  };
  const renderingPassed = capabilityChecks.every((check) => check.passed);
  return {
    viewer_version: "0.7.10",
    passed: renderingPassed && performanceCheck.passed,
    rendering_capability_passed: renderingPassed,
    interactive_performance_passed: performanceCheck.passed,
    measured_at: new Date().toISOString(),
    probe_duration_ms: Math.round(elapsedMs),
    probe_frames: renderedFrames,
    average_fps: averageFps,
    geometry: structuredClone(geometry),
    renderer: evidence,
    checks: [...capabilityChecks, performanceCheck],
    claim_boundary: "This proves that this browser created an active WebGL context and rendered the loaded IFC during the probe. It does not benchmark every interaction or prove drawing/design correctness.",
  };
}

// A stable global bridge avoids browsers failing on a late dynamic import.
globalThis.OpenBIMViewer = {
  loadIfcGeometry,
  selectExpressID,
  selectExpressIDs,
  clearSelection,
  setSelectionMode,
  getGeometryDiagnostics,
  runGpuValidation,
  frameModel,
  getRenderingDiagnostics,
  applySelectionAppearance,
  restoreMaterialStates,
  fitCameraToBox,
};
