#!/usr/bin/env node
// Independent targeted WASM evidence. This does not run a browser/GPU test or
// certify intersections, opening validity, entire-model coverage or author intent.
import {createHash} from 'node:crypto';
import fs from 'node:fs/promises';
import * as WebIFC from '../web/node_modules/web-ifc/web-ifc-api-node.js';
import {accumulateGeometryEvidence, finalizeGeometryEvidence} from '../web/geometry-evidence.js';

const [, , modelPath, comparisonPath, outputPath] = process.argv;
if (!outputPath) throw new Error('Usage: node scripts/verify_opening_host_world_bounds.mjs MODEL.ifc COMPARISON.json OUTPUT.json');
const bytes = new Uint8Array(await fs.readFile(modelPath));
const expected = JSON.parse(await fs.readFile(comparisonPath, 'utf8'));
const hash = createHash('sha256').update(bytes).digest('hex');
if (hash !== expected.source_sha256) throw new Error('Comparison belongs to a different IFC source.');
const checks = expected.opening_host_checks?.results;
if (!checks?.length) throw new Error('Comparison contains no opening-host evidence.');
const requested = new Map();
for (const check of checks) {
  if (check.opening_bounds_metres) requested.set(check.opening_id, check.opening_bounds_metres);
  if (check.host_id != null && check.host_bounds_metres) requested.set(check.host_id, check.host_bounds_metres);
}
const api = new WebIFC.IfcAPI();
api.SetWasmPath(new URL('../web/node_modules/web-ifc/', import.meta.url).href, true);
await api.Init();
const started = performance.now();
const modelID = api.OpenModel(bytes, {COORDINATE_TO_ORIGIN: true, CIRCLE_SEGMENTS: 128});
const records = new Map();
try {
  for (const [id] of requested) {
    const mesh = api.GetFlatMesh(modelID, id);
    for (let part = 0; part < mesh.geometries.size(); part++) {
      const placed = mesh.geometries.get(part);
      const geometry = api.GetGeometry(modelID, placed.geometryExpressID);
      try {
        const vertices = api.GetVertexArray(geometry.GetVertexData(), geometry.GetVertexDataSize());
        const indices = api.GetIndexArray(geometry.GetIndexData(), geometry.GetIndexDataSize());
        if (vertices.length && indices.length) accumulateGeometryEvidence(records, id, vertices, indices, placed.flatTransformation);
      } finally { geometry.delete(); }
    }
  }
  const measured = finalizeGeometryEvidence(records, api.GetCoordinationMatrix(modelID));
  const comparisons = [...requested].map(([id, reference]) => {
    const box = measured.element_bounds_metres[String(id)];
    const differences = box ? ['minimum','maximum'].flatMap(key => reference[key].map((value, axis) => Math.abs(value - box[key][axis]))) : null;
    return {element_id: id, measured_bounds_metres: box || null, expected_ifcopenshell_bounds_metres: reference,
      maximum_coordinate_difference_mm: differences ? Math.max(...differences) * 1000 : null,
      passed_bounds_comparison: differences != null && differences.every(value => value <= .001)};
  });
  const evidence = {source_sha256: hash, source_size_bytes: bytes.length, engine: 'web-ifc', engine_version: api.GetVersion(),
    runtime: 'Node.js WASM; no browser/GPU certification', settings: {coordinate_to_origin:true,circle_segments:128},
    ...measured, tolerance_mm: 1, duration_ms: performance.now() - started,
    comparisons, passed_all_requested_bounds: comparisons.length > 0 && comparisons.every(item => item.passed_bounds_comparison),
    claim_boundary: 'Only requested opening/host world bounds compared. Default web-ifc opening handling may differ from uncut IfcOpenShell Body extraction. Matching bounds do not prove shape equality, actual contact, valid cuts or author intent. No whole-model or GPU verdict.'};
  await fs.writeFile(outputPath, JSON.stringify(evidence, null, 2) + '\n');
  console.log(JSON.stringify({requested_elements: requested.size, passed: evidence.passed_all_requested_bounds, comparisons, duration_ms: evidence.duration_ms}));
} finally { api.CloseModel(modelID); }
