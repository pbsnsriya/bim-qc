import * as THREE from "./vendor/three/three.module.js";
import { OrbitControls } from "./vendor/three/examples/jsm/controls/OrbitControls.js";
import * as WebIFC from "./vendor/web-ifc/web-ifc-api.js";

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
    selectionHelper: null,
    modelGroup: null,
    diagnostics: null,
  };
  const animate = () => {
    controls.update();
    renderer.render(scene, camera);
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

export function fitCameraToBox(camera, controls, box) {
  if (box.isEmpty()) return;
  const center = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3());
  const radius = Math.max(size.x, size.y, size.z, 1);
  const direction = camera.position.clone().sub(controls.target).normalize();
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
    original.material.needsUpdate = true;
  }
}

export function applySelectionAppearance(meshes) {
  const states = [];
  const selectedBox = new THREE.Box3();
  const seenMaterials = new Set();
  for (const mesh of meshes) {
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
      });
      material.color.set(0xffc83d);
      material.emissive.set(0x6b3f00);
      material.emissiveIntensity = 1.25;
      material.opacity = 1;
      material.transparent = false;
      material.needsUpdate = true;
    }
  }
  return { states, selectedBox };
}

export function clearSelection() {
  if (!sceneState) return;
  restoreMaterialStates(sceneState.selectedMaterials);
  sceneState.selectedMaterials = [];
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
  const meshes = [...new Set(expressIDs.map(Number))]
    .flatMap((expressID) => sceneState.expressMeshes.get(expressID) || []);
  if (!meshes?.length) return false;
  clearSelection();
  const { states, selectedBox } = applySelectionAppearance(meshes);
  sceneState.selectedMaterials = states;
  sceneState.selectionHelper = new THREE.Box3Helper(selectedBox, 0xff6b1a);
  sceneState.scene.add(sceneState.selectionHelper);
  if (focus) fitCameraToBox(sceneState.camera, sceneState.controls, selectedBox);
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
    const hit = raycaster.intersectObjects(current.modelGroup?.children || [], false)[0];
    const expressID = hit?.object?.userData?.expressID;
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
  const modelID = api.OpenModel(bytes, { COORDINATE_TO_ORIGIN: true });
  const group = new THREE.Group();
  let meshCount = 0;
  let vertexCount = 0;
  let triangleCount = 0;
  const elementBounds = new Map();

  api.StreamAllMeshes(modelID, (flatMesh) => {
    const geometries = flatMesh.geometries;
    for (let index = 0; index < geometries.size(); index += 1) {
      const placed = geometries.get(index);
      const source = api.GetGeometry(modelID, placed.geometryExpressID);
      const vertexData = api.GetVertexArray(source.GetVertexData(), source.GetVertexDataSize());
      const indexData = api.GetIndexArray(source.GetIndexData(), source.GetIndexDataSize());
      const positions = new Float32Array((vertexData.length / 6) * 3);
      const normals = new Float32Array((vertexData.length / 6) * 3);
      for (let sourceIndex = 0, targetIndex = 0; sourceIndex < vertexData.length; sourceIndex += 6, targetIndex += 3) {
        positions.set(vertexData.subarray(sourceIndex, sourceIndex + 3), targetIndex);
        normals.set(vertexData.subarray(sourceIndex + 3, sourceIndex + 6), targetIndex);
      }
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
      geometry.setAttribute("normal", new THREE.BufferAttribute(normals, 3));
      geometry.setIndex(new THREE.BufferAttribute(new Uint32Array(indexData), 1));
      const color = placed.color;
      const material = new THREE.MeshStandardMaterial({
        color: new THREE.Color(color.x, color.y, color.z),
        opacity: color.w,
        transparent: color.w < 1,
        roughness: 0.78,
        metalness: 0.02,
        side: THREE.DoubleSide,
      });
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
      vertexCount += positions.length / 3;
      triangleCount += indexData.length / 3;
      source.delete();
    }
  });

  api.CloseModel(modelID);
  current.diagnostics = summarizeGeometryEvidence(
    elementBounds, vertexCount, triangleCount, meshCount,
  );
  if (meshCount) {
    current.modelGroup = group;
    current.scene.add(group);
    fitCamera(current.camera, current.controls, group);
    enableCanvasPicking(current);
  }
  return meshCount;
}

export function getGeometryDiagnostics() {
  return sceneState?.diagnostics ? structuredClone(sceneState.diagnostics) : null;
}

// A stable global bridge avoids browsers failing on a late dynamic import.
globalThis.OpenBIMViewer = {
  loadIfcGeometry,
  selectExpressID,
  selectExpressIDs,
  clearSelection,
  getGeometryDiagnostics,
  applySelectionAppearance,
  restoreMaterialStates,
  fitCameraToBox,
};
