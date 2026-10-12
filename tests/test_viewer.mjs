import assert from "node:assert/strict";
import * as THREE from "../web/vendor/three/three.module.js";
import {
  applySelectionAppearance,
  fitCameraToBox,
  restoreMaterialStates,
  summarizeGeometryEvidence,
  ifcBoundsToViewerBox,
} from "../web/viewer.js";

const material = new THREE.MeshStandardMaterial({
  color: 0x739286,
  emissive: 0x000000,
  opacity: 0.65,
  transparent: true,
});
const originalColor = material.color.getHex();
const mesh = new THREE.Mesh(new THREE.BoxGeometry(2, 3, 4), material);
mesh.position.set(8, 2, -3);
mesh.updateMatrixWorld(true);

const { states, meshStates, selectedBox } = applySelectionAppearance([mesh]);
assert.equal(material.color.getHex(), 0xffc83d, "selected geometry becomes amber");
assert.equal(material.emissive.getHex(), 0x6b3f00, "selected geometry receives warm emissive highlight");
assert.equal(material.opacity, 1, "selected geometry becomes fully visible");
assert.equal(material.depthTest, false, "selected geometry remains visible through occluding model surfaces");
assert.equal(material.depthWrite, false, "x-ray selection does not hide later geometry");
assert.equal(mesh.renderOrder, 10_000, "selected geometry renders after ordinary model geometry");
assert.equal(selectedBox.isEmpty(), false, "selection produces a non-empty bounding box");

const camera = new THREE.PerspectiveCamera(42, 1, 0.01, 1000);
camera.position.set(20, 14, 20);
const before = camera.position.clone();
const controls = { target: new THREE.Vector3(), update() {} };
fitCameraToBox(camera, controls, selectedBox);
assert.equal(camera.position.equals(before), false, "camera moves to frame the selected element");
assert.equal(controls.target.distanceTo(selectedBox.getCenter(new THREE.Vector3())) < 1e-9, true, "camera targets the selected element");

const pickCamera = new THREE.PerspectiveCamera(45, 1, 0.1, 100);
pickCamera.position.set(8, 2, 10);
pickCamera.lookAt(mesh.position);
pickCamera.updateProjectionMatrix();
pickCamera.updateMatrixWorld(true);
const raycaster = new THREE.Raycaster();
raycaster.setFromCamera(new THREE.Vector2(0, 0), pickCamera);
assert.equal(raycaster.intersectObject(mesh, false).length > 0, true, "direct canvas picking can hit IFC geometry");

restoreMaterialStates(states);
for (const original of meshStates) original.mesh.renderOrder = original.renderOrder;
assert.equal(material.color.getHex(), originalColor, "clear selection restores the original colour");
assert.equal(material.opacity, 0.65, "clear selection restores the original opacity");
assert.equal(material.depthTest, true, "clear selection restores depth testing");
assert.equal(mesh.renderOrder, 0, "clear selection restores render order");

const firstBounds = new THREE.Box3(new THREE.Vector3(0, 0, 0), new THREE.Vector3(1, 2, 3));
const secondBounds = new THREE.Box3(new THREE.Vector3(5, 5, 5), new THREE.Vector3(7, 6, 6));
const evidence = summarizeGeometryEvidence(new Map([[10, firstBounds], [20, secondBounds]]), 16, 24, 2);
assert.deepEqual(evidence.element_ids, [10, 20], "browser evidence records stable IFC element ids");
assert.deepEqual(evidence.element_extents_metres["10"], [1, 3, 2], "browser evidence normalizes Y-up viewer extents to IFC Z-up axes");
assert.deepEqual(evidence.overall_extents_metres, [7, 6, 6], "browser evidence records normalized overall extents");
assert.equal(evidence.origin_mode, "model-centred", "browser evidence discloses coordinate recentering");
assert.match(evidence.axis_mapping, /Y-up normalized to IFC Z-up/, "browser evidence discloses its axis mapping");

console.log("viewer selection tests passed");

const { accumulateGeometryEvidence, finalizeGeometryEvidence } = await import('../web/geometry-evidence.js');
// Triangle vertices, rotated 45 degrees. Transforming its local AABB would give a wrong max Y.
const records = new Map();
const angle = Math.PI / 4;
const transformation = new THREE.Matrix4().makeRotationZ(angle).toArray();
accumulateGeometryEvidence(records, 90, [0,0,0,0,0,1, 2,0,0,0,0,1, 0,1,0,0,0,1], [0,1,2], transformation);
const measured = finalizeGeometryEvidence(records, new THREE.Matrix4().toArray());
assert.ok(Math.abs(measured.element_bounds_metres['90'].maximum[2] - Math.SQRT2) < 1e-10, 'actual rotated vertices determine bounds');
assert.ok(Math.abs(measured.element_shape_metrics['90'].surface_area_m2 - 1) < 1e-10, 'triangle area is invariant under rotation');
const shifted = new Map([[91, {minimum:[0,0,0], maximum:[1,1,1],volume_m3:1,surface_area_m2:6}]]);
const restored = finalizeGeometryEvidence(shifted, new THREE.Matrix4().makeTranslation(-12,-4,20).toArray());
assert.deepEqual(restored.element_bounds_metres['91'], {minimum:[12,19,4], maximum:[13,20,5]}, 'inverse recentering and signed axis conversion restore IFC world bounds');

// The diagnostic marker must use the exact inverse axis/origin convention.
const viewerBox = ifcBoundsToViewerBox(restored.element_bounds_metres['91'], new THREE.Matrix4().makeTranslation(-12,-4,20).toArray());
assert.deepEqual(viewerBox.min.toArray(), [0,0,0]);
assert.deepEqual(viewerBox.max.toArray(), [1,1,1]);
const officeBox = ifcBoundsToViewerBox({minimum:[14,42,52],maximum:[15,43,53]}, new THREE.Matrix4().makeTranslation(-61.44746630414893,-53.3,82.27184895393557).toArray());
assert.ok(Math.abs(officeBox.min.x - (14-61.44746630414893)) < 1e-10);
assert.ok(Math.abs(officeBox.min.y - (52-53.3)) < 1e-10);
assert.ok(Math.abs(officeBox.min.z - (-43+82.27184895393557)) < 1e-10);
assert.equal(ifcBoundsToViewerBox({minimum:[0,0,0],maximum:[1,1,1]}, null), null);
assert.equal(ifcBoundsToViewerBox({minimum:[0,0,0],maximum:[NaN,1,1]}, new THREE.Matrix4().toArray()), null);
assert.equal(ifcBoundsToViewerBox({minimum:[2,0,0],maximum:[1,1,1]}, new THREE.Matrix4().toArray()), null);
console.log('opening bounds marker coordinate tests passed');
