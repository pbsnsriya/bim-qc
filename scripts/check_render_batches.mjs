#!/usr/bin/env node
// CPU/WASM geometry and batching verification. This is not a GPU/FPS benchmark.
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import { createHash } from "node:crypto";
import * as THREE from "../web/vendor/three/three.module.js";
import * as WebIFC from "../web/node_modules/web-ifc/web-ifc-api-node.js";
import { buildRenderBatches } from "../web/render-batches.js";

const [, , filename, output] = process.argv;
if (!filename) throw new Error("Usage: node scripts/check_render_batches.mjs model.ifc [report.json]");
const bytes = new Uint8Array(await fs.readFile(filename));
const api = new WebIFC.IfcAPI();
api.SetWasmPath(new URL("../web/node_modules/web-ifc/", import.meta.url).href, true);
await api.Init();
const model = api.OpenModel(bytes, { COORDINATE_TO_ORIGIN: true, CIRCLE_SEGMENTS: 128 });
const sources = [];
const materials = new Map();
const geometries = new Map();
api.StreamAllMeshes(model, flat => {
  for (let i = 0; i < flat.geometries.size(); i++) {
    const placed = flat.geometries.get(i);
    let geometry = geometries.get(placed.geometryExpressID);
    if (!geometry) {
      const source = api.GetGeometry(model, placed.geometryExpressID);
      const data = api.GetVertexArray(source.GetVertexData(), source.GetVertexDataSize());
      const positions = new Float32Array(data.length / 2);
      const normals = new Float32Array(data.length / 2);
      for (let j = 0, k = 0; j < data.length; j += 6, k += 3) {
        positions.set(data.subarray(j, j + 3), k);
        normals.set(data.subarray(j + 3, j + 6), k);
      }
      geometry = new THREE.BufferGeometry();
      geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
      geometry.setAttribute("normal", new THREE.BufferAttribute(normals, 3));
      geometry.setIndex(new THREE.BufferAttribute(new Uint32Array(api.GetIndexArray(source.GetIndexData(), source.GetIndexDataSize())), 1));
      geometries.set(placed.geometryExpressID, geometry);
      source.delete();
    }
    const color = placed.color;
    const key = [color.x, color.y, color.z, color.w].join(",");
    if (!materials.has(key)) materials.set(key, new THREE.MeshStandardMaterial({ color: new THREE.Color(color.x, color.y, color.z), opacity: color.w, transparent: color.w < 1, side: THREE.DoubleSide }));
    const mesh = new THREE.Mesh(geometry, materials.get(key));
    mesh.userData.expressID = flat.expressID;
    mesh.applyMatrix4(new THREE.Matrix4().fromArray(placed.flatTransformation));
    sources.push(mesh);
  }
});
api.CloseModel(model);
const started = performance.now();
const batches = buildRenderBatches(sources);
const originals = new Map(sources.map(mesh => [mesh.uuid, mesh]));
let maximumVertexDelta = 0;
let verifiedVertices = 0;
let verifiedIndices = 0;
const point = new THREE.Vector3();
const actual = new THREE.Vector3();
for (const mesh of batches.group.children) {
  for (const range of mesh.userData.pickRanges) {
    const source = originals.get(range.sourceUUID);
    assert.equal(range.expressID, source.userData.expressID);
    assert.equal(range.count, source.geometry.index.count);
    const flipped = source.matrixWorld.determinant() < 0;
    for (let i = 0; i < range.count; i++) {
      const offset = i % 3;
      const sourceIndex = i - offset + (flipped && offset ? 3 - offset : offset);
      assert.equal(mesh.geometry.index.getX(range.start + i) - range.vertexStart, source.geometry.index.getX(sourceIndex), "all triangle indices and IFC owners are preserved");
      verifiedIndices++;
    }
    for (let i = 0; i < range.vertexCount; i++) {
      point.fromBufferAttribute(source.geometry.attributes.position, i).applyMatrix4(source.matrixWorld);
      actual.fromBufferAttribute(mesh.geometry.attributes.position, range.vertexStart + i);
      maximumVertexDelta = Math.max(maximumVertexDelta, point.distanceTo(actual));
      verifiedVertices++;
    }
  }
}
assert.equal(verifiedVertices, sources.reduce((total, mesh) => total + mesh.geometry.attributes.position.count, 0));
assert.equal(verifiedIndices / 3, batches.stats.triangles);
assert.ok(maximumVertexDelta < 0.0001, "render positions remain within 0.1 mm of the original Float32 display geometry");
const sourceDrawCalls = sources.reduce((total, mesh) => total + (mesh.material.transparent ? 2 : 1), 0);
const batchDrawCalls = batches.group.children.reduce((total, mesh) => total + (mesh.material.transparent ? 2 : 1), 0);
const report = {
  model: filename.split(/[\\/]/).pop(),
  sha256: createHash("sha256").update(bytes).digest("hex"),
  size_bytes: bytes.length,
  passed: true,
  ...batches.stats,
  source_draw_calls_all_visible: sourceDrawCalls,
  batched_draw_calls_all_visible: batchDrawCalls,
  draw_call_reduction_percent: Math.round((1 - batchDrawCalls / sourceDrawCalls) * 1000) / 10,
  verified_vertices: verifiedVertices,
  verified_triangle_indices: verifiedIndices,
  maximum_render_vertex_delta_metres: maximumVertexDelta,
  batching_and_verification_ms: Math.round(performance.now() - started),
  scope: "CPU/WASM: complete triangle/IFC-owner preservation and Float32 display-position comparison. No GPU FPS or project compliance claim.",
};
if (output) await fs.writeFile(output, JSON.stringify(report, null, 2));
console.log(JSON.stringify(report, null, 2));
batches.dispose();
