import assert from "node:assert/strict";
import * as THREE from "../web/vendor/three/three.module.js";
import { buildRenderBatches, createSelectionGroup, expressIDForHit } from "../web/render-batches.js";
import { applySelectionAppearance } from "../web/viewer.js";

const material = new THREE.MeshStandardMaterial({ color: 0x739286, side: THREE.DoubleSide });
const glass = new THREE.MeshStandardMaterial({ opacity: 0.5, transparent: true, side: THREE.DoubleSide });
function box(id, x, mat = material) {
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(1, 2, 3), mat);
  mesh.position.set(x, 0, 0);
  mesh.userData.expressID = id;
  mesh.updateMatrixWorld(true);
  return mesh;
}
const sources = [box(10, 1), box(20, 4), box(30, 7), box(40, 10, glass), box(50, 13, glass)];
// A shared-material batch contains three independently selectable IFC objects.
const result = buildRenderBatches(sources, { cellSize: 1000 });
assert.equal(result.stats.render_batches, 3);
assert.equal(result.stats.opaque_batches, 1);
assert.equal(result.stats.transparent_parts, 2, "transparent objects retain independent sorting");
assert.equal(result.stats.triangles, 60, "no triangles are removed by batching");
const ray = new THREE.Raycaster();
function pick(id, x, meshes = result.group.children) {
  ray.set(new THREE.Vector3(x, 0, 10), new THREE.Vector3(0, 0, -1));
  result.group.updateMatrixWorld(true);
  const hit = ray.intersectObjects(meshes.filter(mesh => mesh.visible), false)[0];
  assert.equal(expressIDForHit(hit), id);
}
for (const [id, x] of [[10, 1], [20, 4], [30, 7], [40, 10], [50, 13]]) pick(id, x);
const batch = result.group.children[0];
const stableIndex = batch.geometry.index;
const originalIndex = stableIndex.array.slice();
result.setSelection([10, 20], "xray");
assert.equal(batch.geometry.drawRange.count, 36, "selected pair is removed from context, leaving the third box");
pick(30, 7);
pick(null, 1);
assert.equal(batch.geometry.index, stableIndex, "selection reuses one GPU index buffer");
const selection = createSelectionGroup(sources.slice(0, 2));
assert.deepEqual(selection.children.map(mesh => mesh.userData.expressID), [10, 20]);
applySelectionAppearance(selection.children);
assert.equal(selection.children[0].material.color.getHex(), 0xffc83d);
assert.equal(material.color.getHex(), 0x739286, "pair highlighting cannot recolour unrelated batched objects");
pick(10, 1, selection.children);
result.setSelection([10, 20], "isolate");
assert.equal(result.group.children.every(mesh => !mesh.visible), true);
pick(20, 4, selection.children);
result.setSelection([10, 20], "fade");
assert.equal(batch.material.opacity, 0.08);
assert.equal(batch.material.depthWrite, false);
assert.equal(material.opacity, 1, "fade does not mutate shared source materials");
result.setSelection();
assert.deepEqual(batch.geometry.index.array, originalIndex, "clear restores every original triangle");
assert.equal(batch.geometry.index, stableIndex);
assert.equal(batch.material, material);
assert.equal(result.group.children.every(mesh => mesh.visible), true);
for (const [id, x] of [[10, 1], [20, 4], [30, 7]]) pick(id, x);
for (let i = 0; i < 20; i++) {
  result.setSelection([20], "fade");
  result.setSelection([10, 30], "isolate");
  result.setSelection();
}
assert.deepEqual(batch.geometry.index.array, originalIndex, "repeated review transitions restore the same indices");
assert.equal(buildRenderBatches(sources.slice(0, 3), { cellSize: 1000, maxVertices: 24 }).stats.render_batches, 3, "large batches split at the vertex cap");
assert.equal(buildRenderBatches([box(1, 1), box(2, 100)], { cellSize: 5 }).stats.render_batches, 2, "spatial chunks retain frustum-culling granularity");

// Compare each merged vertex to its original transformed vertex; include
// mirrored and nonuniform scaling, and verify geometric normals stay aligned.
const transformed = box(60, -4);
transformed.scale.set(-2, 3, 0.5);
transformed.rotation.set(0.3, 0.5, 0.8);
transformed.updateMatrixWorld(true);
const mirrored = buildRenderBatches([transformed]);
const merged = mirrored.group.children[0].geometry;
const point = new THREE.Vector3();
for (let i = 0; i < transformed.geometry.attributes.position.count; i++) {
  point.fromBufferAttribute(transformed.geometry.attributes.position, i).applyMatrix4(transformed.matrixWorld);
  assert.ok(point.distanceTo(new THREE.Vector3().fromBufferAttribute(merged.attributes.position, i)) < 1e-6);
}
const a = new THREE.Vector3(), b = new THREE.Vector3(), c = new THREE.Vector3();
a.fromBufferAttribute(merged.attributes.position, merged.index.getX(0));
b.fromBufferAttribute(merged.attributes.position, merged.index.getX(1));
c.fromBufferAttribute(merged.attributes.position, merged.index.getX(2));
const faceNormal = b.sub(a).cross(c.sub(a)).normalize();
assert.ok(faceNormal.dot(new THREE.Vector3().fromBufferAttribute(merged.attributes.normal, merged.index.getX(0))) > 0.999, "mirrored placement preserves face orientation and lighting");
let disposed = 0;
batch.geometry.addEventListener("dispose", () => disposed++);
result.dispose();
assert.equal(disposed, 1);
console.log("render batching, transformed geometry, picking, pair selection and context restoration tests passed");
