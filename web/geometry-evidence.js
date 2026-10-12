import * as THREE from "./vendor/three/three.module.js";

// Evidence is measured from actual transformed vertices, not transformed local
// bounding boxes (which overestimate a rotated non-box object's world bounds).
export function accumulateGeometryEvidence(records, id, vertexData, indexData, transformation) {
  const record = records.get(id) || { minimum: [Infinity, Infinity, Infinity], maximum: [-Infinity, -Infinity, -Infinity], surface_area_m2: 0, volume_m3: 0 };
  const matrix = new THREE.Matrix4().fromArray(transformation);
  const points = [];
  const point = new THREE.Vector3();
  for (let i = 0; i < vertexData.length; i += 6) {
    point.set(vertexData[i], vertexData[i + 1], vertexData[i + 2]).applyMatrix4(matrix);
    points.push(point.clone());
    for (let axis = 0; axis < 3; axis++) {
      record.minimum[axis] = Math.min(record.minimum[axis], point.getComponent(axis));
      record.maximum[axis] = Math.max(record.maximum[axis], point.getComponent(axis));
    }
  }
  let signedVolume = 0;
  const anchor = points[0] || new THREE.Vector3();
  const a = new THREE.Vector3(), b = new THREE.Vector3(), c = new THREE.Vector3();
  const ab = new THREE.Vector3(), ac = new THREE.Vector3(), cross = new THREE.Vector3();
  for (let i = 0; i < indexData.length; i += 3) {
    a.copy(points[indexData[i]]).sub(anchor);
    b.copy(points[indexData[i + 1]]).sub(anchor);
    c.copy(points[indexData[i + 2]]).sub(anchor);
    cross.crossVectors(ab.subVectors(b, a), ac.subVectors(c, a));
    record.surface_area_m2 += cross.length() / 2;
    signedVolume += a.dot(cross.crossVectors(b, c)) / 6;
  }
  record.volume_m3 += Math.abs(signedVolume);
  records.set(id, record);
}

export function finalizeGeometryEvidence(records, coordinationMatrix) {
  const inverse = new THREE.Matrix4().fromArray(coordinationMatrix).invert();
  const bounds = {}, metrics = {};
  for (const [id, record] of records) {
    // GetCoordinationMatrix describes recentering in web-ifc Y-up space.
    // Invert it before converting Y-up [x,y,z] back to IFC [x,-z,y].
    const box = new THREE.Box3();
    for (let mask = 0; mask < 8; mask++) {
      const p = new THREE.Vector3(...record.minimum.map((value, axis) => (mask & (1 << axis)) ? record.maximum[axis] : value)).applyMatrix4(inverse);
      box.expandByPoint(new THREE.Vector3(p.x, -p.z, p.y));
    }
    bounds[String(id)] = { minimum: box.min.toArray(), maximum: box.max.toArray() };
    metrics[String(id)] = { surface_area_m2: record.surface_area_m2, volume_m3: record.volume_m3 };
  }
  return {
    evidence_version: 2,
    bounds_frame: "IFC world Z-up metres",
    element_bounds_metres: bounds,
    element_shape_metrics: metrics,
    coordination_matrix: Array.from(coordinationMatrix),
    measurement_scope: "World bounds and triangulated surface/volume diagnostics; not complete shape equivalence or manifold certification.",
  };
}
