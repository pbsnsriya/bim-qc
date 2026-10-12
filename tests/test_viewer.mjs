import assert from "node:assert/strict";
import * as THREE from "../web/vendor/three/three.module.js";
import {
  applySelectionAppearance,
  fitCameraToBox,
  restoreMaterialStates,
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

const { states, selectedBox } = applySelectionAppearance([mesh]);
assert.equal(material.color.getHex(), 0xffc83d, "selected geometry becomes amber");
assert.equal(material.emissive.getHex(), 0x6b3f00, "selected geometry receives warm emissive highlight");
assert.equal(material.opacity, 1, "selected geometry becomes fully visible");
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
assert.equal(material.color.getHex(), originalColor, "clear selection restores the original colour");
assert.equal(material.opacity, 0.65, "clear selection restores the original opacity");

console.log("viewer selection tests passed");
