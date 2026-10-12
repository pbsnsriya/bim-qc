#!/usr/bin/env node

import { createHash } from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import * as WebIFC from "../web/node_modules/web-ifc/web-ifc-api-node.js";

import { accumulateGeometryEvidence, finalizeGeometryEvidence } from "../web/geometry-evidence.js";
const measuredGeometry = new Map();

const [, , ifcPath, outputPath] = process.argv;
if (!ifcPath || !outputPath) {
  throw new Error("Usage: node scripts/web_ifc_evidence.mjs MODEL.ifc evidence.json");
}

const startedAt = performance.now();
const bytes = new Uint8Array(await fs.readFile(ifcPath));
const api = new WebIFC.IfcAPI();
const scriptDirectory = path.dirname(fileURLToPath(import.meta.url));
const wasmDirectory = path.resolve(scriptDirectory, "../web/node_modules/web-ifc") + path.sep;
api.SetWasmPath(pathToFileURL(wasmDirectory).href, true);
await api.Init();
const modelID = api.OpenModel(bytes, { COORDINATE_TO_ORIGIN: true, CIRCLE_SEGMENTS: 128 });
const bounds = new Map();
let meshGroups = 0;
let vertices = 0;
let triangles = 0;

function includePoint(box, x, y, z) {
  box.minimum[0] = Math.min(box.minimum[0], x);
  box.minimum[1] = Math.min(box.minimum[1], y);
  box.minimum[2] = Math.min(box.minimum[2], z);
  box.maximum[0] = Math.max(box.maximum[0], x);
  box.maximum[1] = Math.max(box.maximum[1], y);
  box.maximum[2] = Math.max(box.maximum[2], z);
}

api.StreamAllMeshes(modelID, (flatMesh) => {
  const box = bounds.get(flatMesh.expressID) || {
    minimum: [Infinity, Infinity, Infinity],
    maximum: [-Infinity, -Infinity, -Infinity],
  };
  for (let index = 0; index < flatMesh.geometries.size(); index += 1) {
    const placed = flatMesh.geometries.get(index);
    const source = api.GetGeometry(modelID, placed.geometryExpressID);
    const vertexData = api.GetVertexArray(source.GetVertexData(), source.GetVertexDataSize());
    const indexData = api.GetIndexArray(source.GetIndexData(), source.GetIndexDataSize());
    accumulateGeometryEvidence(measuredGeometry, flatMesh.expressID, vertexData, indexData, placed.flatTransformation);
    const matrix = placed.flatTransformation;
    for (let vertex = 0; vertex < vertexData.length; vertex += 6) {
      const x = vertexData[vertex];
      const y = vertexData[vertex + 1];
      const z = vertexData[vertex + 2];
      includePoint(
        box,
        matrix[0] * x + matrix[4] * y + matrix[8] * z + matrix[12],
        matrix[1] * x + matrix[5] * y + matrix[9] * z + matrix[13],
        matrix[2] * x + matrix[6] * y + matrix[10] * z + matrix[14],
      );
    }
    meshGroups += 1;
    vertices += vertexData.length / 6;
    triangles += indexData.length / 3;
    source.delete();
  }
  bounds.set(flatMesh.expressID, box);
});
const measuredEvidence = finalizeGeometryEvidence(measuredGeometry, api.GetCoordinationMatrix(modelID));
api.CloseModel(modelID);

const extents = {};
for (const [expressID, box] of bounds) {
  const viewerSize = box.maximum.map((value, index) => value - box.minimum[index]);
  extents[String(expressID)] = [viewerSize[0], viewerSize[2], viewerSize[1]];
}
const evidence = {
  ...measuredEvidence,
  engine: "web-ifc",
  engine_version: api.GetVersion(),
  settings: { coordinate_to_origin: true, circle_segments: 128 },
  runtime: "Node.js WASM (non-GPU independent comparison)",
  origin_mode: "model-centred",
  axis_mapping: "web-ifc Y-up normalized to IFC Z-up [x,-z,y], recentering reversed",
  element_ids: [...bounds.keys()].sort((a, b) => a - b),
  element_extents_metres: extents,
  mesh_groups: meshGroups,
  vertices,
  triangles,
  duration_ms: Math.round((performance.now() - startedAt) * 10) / 10,
  source_file: path.basename(ifcPath),
  source_sha256: createHash("sha256").update(bytes).digest("hex"),
  source_size_bytes: bytes.length,
};
await fs.writeFile(outputPath, JSON.stringify(evidence));
console.log(JSON.stringify({
  output: outputPath,
  elements: evidence.element_ids.length,
  mesh_groups: meshGroups,
  vertices,
  triangles,
  duration_ms: evidence.duration_ms,
}));
