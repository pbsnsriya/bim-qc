import * as THREE from "./vendor/three/three.module.js";

export function createSelectionGroup(sources) {
  const group = new THREE.Group();
  const materials = new Map();
  for (const source of sources) {
    if (!materials.has(source.material)) materials.set(source.material, source.material.clone());
    const mesh = new THREE.Mesh(source.geometry, materials.get(source.material));
    mesh.userData.expressID = source.userData.expressID;
    mesh.applyMatrix4(source.matrixWorld);
    group.add(mesh);
    mesh.updateMatrixWorld(true);
  }
  return group;
}

// Batch opaque geometry by material and location. Keep transparent parts
// separate so Three.js can still sort them individually from the camera.
// Source meshes remain available for element-level selection overlays.
export function buildRenderBatches(sourceMeshes, { maxVertices = 100_000, cellSize } = {}) {
  const overall = new THREE.Box3();
  for (const mesh of sourceMeshes) {
    mesh.updateMatrixWorld(true);
    if (!mesh.geometry.boundingBox) mesh.geometry.computeBoundingBox();
    overall.union(mesh.geometry.boundingBox.clone().applyMatrix4(mesh.matrixWorld));
  }
  const size = overall.getSize(new THREE.Vector3());
  const width = cellSize || Math.max(size.x, size.y, size.z, 1) / 6;
  const buckets = new Map();
  const batches = [];
  const group = new THREE.Group();
  const fadedMaterials = new Map();
  const centre = new THREE.Vector3();
  for (const source of sourceMeshes) {
    source.geometry.boundingBox.getCenter(centre).applyMatrix4(source.matrixWorld);
    const key = source.material.transparent
      ? `transparent:${source.uuid}`
      : `${source.material.uuid}:${Math.floor(centre.x / width)},${Math.floor(centre.y / width)},${Math.floor(centre.z / width)}`;
    let bucket = buckets.get(key);
    const vertices = source.geometry.attributes.position.count;
    if (!bucket || bucket.vertices + vertices > maxVertices) {
      bucket = { sources: [], vertices: 0, indices: 0 };
      buckets.set(key, bucket);
      batches.push(bucket);
    }
    bucket.sources.push(source);
    bucket.vertices += vertices;
    bucket.indices += source.geometry.index.count;
  }
  for (const batch of batches) {
    const positions = new Float32Array(batch.vertices * 3);
    const normals = new Float32Array(batch.vertices * 3);
    const indices = new Uint32Array(batch.indices);
    const ranges = [];
    let vertexOffset = 0;
    let indexOffset = 0;
    const point = new THREE.Vector3();
    const normal = new THREE.Vector3();
    const normalMatrix = new THREE.Matrix3();
    for (const source of batch.sources) {
      const geometry = source.geometry;
      const p = geometry.attributes.position;
      const n = geometry.attributes.normal;
      normalMatrix.getNormalMatrix(source.matrixWorld);
      for (let i = 0; i < p.count; i += 1) {
        point.fromBufferAttribute(p, i).applyMatrix4(source.matrixWorld);
        normal.fromBufferAttribute(n, i).applyMatrix3(normalMatrix).normalize();
        point.toArray(positions, (vertexOffset + i) * 3);
        normal.toArray(normals, (vertexOffset + i) * 3);
      }
      const flipped = source.matrixWorld.determinant() < 0;
      for (let i = 0; i < geometry.index.count; i += 3) {
        indices[indexOffset + i] = geometry.index.getX(i) + vertexOffset;
        indices[indexOffset + i + 1] = geometry.index.getX(i + (flipped ? 2 : 1)) + vertexOffset;
        indices[indexOffset + i + 2] = geometry.index.getX(i + (flipped ? 1 : 2)) + vertexOffset;
      }
      ranges.push({ expressID: source.userData.expressID, start: indexOffset, count: geometry.index.count, vertexStart: vertexOffset, vertexCount: p.count, sourceUUID: source.uuid });
      vertexOffset += p.count;
      indexOffset += geometry.index.count;
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute("normal", new THREE.BufferAttribute(normals, 3));
    geometry.setIndex(new THREE.BufferAttribute(indices, 1));
    geometry.computeBoundingBox();
    geometry.computeBoundingSphere();
    const mesh = new THREE.Mesh(geometry, batch.sources[0].material);
    mesh.matrixAutoUpdate = false;
    mesh.userData.pickRanges = ranges;
    Object.assign(batch, { mesh, ranges, originalIndices: indices.slice(), baseMaterial: mesh.material, indexFiltered: false });
    group.add(mesh);
  }

  function setSelection(selectedIDs = [], mode = "xray") {
    const selected = new Set(selectedIDs.map(Number));
    for (const batch of batches) {
      const { mesh, ranges, originalIndices, baseMaterial } = batch;
      const remaining = ranges.filter(range => !selected.has(range.expressID));
      // Isolation does not need to upload replacement indices for hidden context.
      const isolated = selected.size > 0 && mode === "isolate";
      const count = remaining.reduce((total, range) => total + range.count, 0);
      mesh.visible = !isolated && count > 0;
      if (!isolated && remaining.length !== ranges.length) {
        const indices = mesh.geometry.index.array;
        let offset = 0;
        mesh.userData.pickRanges = remaining.map(range => {
          indices.set(originalIndices.subarray(range.start, range.start + range.count), offset);
          const updated = { ...range, start: offset };
          offset += range.count;
          return updated;
        });
        mesh.geometry.index.needsUpdate = true;
        mesh.geometry.setDrawRange(0, count);
        batch.indexFiltered = true;
      } else {
        if (batch.indexFiltered) {
          mesh.geometry.index.array.set(originalIndices);
          mesh.geometry.index.needsUpdate = true;
          mesh.geometry.setDrawRange(0, originalIndices.length);
          batch.indexFiltered = false;
        }
        mesh.userData.pickRanges = ranges;
      }
      if (selected.size && mode === "fade") {
        if (!fadedMaterials.has(baseMaterial)) {
          const faded = baseMaterial.clone();
          faded.opacity = Math.min(baseMaterial.opacity, 0.08);
          faded.transparent = true;
          faded.depthWrite = false;
          // Context is deliberately faint; avoid two-pass double-sided rendering.
          faded.forceSinglePass = true;
          fadedMaterials.set(baseMaterial, faded);
        }
        mesh.material = fadedMaterials.get(baseMaterial);
      } else mesh.material = baseMaterial;
    }
  }

  return {
    group,
    setSelection,
    stats: {
      strategy: "opaque-material-spatial-batches",
      source_mesh_groups: sourceMeshes.length,
      render_batches: batches.length,
      opaque_batches: batches.filter(batch => !batch.baseMaterial.transparent).length,
      transparent_parts: batches.filter(batch => batch.baseMaterial.transparent).length,
      material_count: new Set(sourceMeshes.map(mesh => mesh.material)).size,
      triangles: batches.reduce((total, batch) => total + batch.indices / 3, 0),
      max_vertices_per_batch: maxVertices,
      oversized_source_parts: sourceMeshes.filter(mesh => mesh.geometry.attributes.position.count > maxVertices).length,
      cell_size_metres: width,
    },
    dispose() {
      for (const batch of batches) batch.mesh.geometry.dispose();
      for (const geometry of new Set(sourceMeshes.map(mesh => mesh.geometry))) geometry.dispose();
      for (const material of new Set(sourceMeshes.map(mesh => mesh.material))) material.dispose();
      for (const material of fadedMaterials.values()) material.dispose();
    },
  };
}

export function expressIDForHit(hit) {
  if (!hit) return null;
  if (hit.object.userData.expressID != null) return hit.object.userData.expressID;
  const ranges = hit.object.userData.pickRanges || [];
  const index = hit.faceIndex * 3;
  let low = 0;
  let high = ranges.length - 1;
  while (low <= high) {
    const middle = (low + high) >> 1;
    const range = ranges[middle];
    if (index < range.start) high = middle - 1;
    else if (index >= range.start + range.count) low = middle + 1;
    else return range.expressID;
  }
  return null;
}
