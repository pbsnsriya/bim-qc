# Portfolio brief

## OpenBIM Quality & Mapping Assistant

**Problem:** IFC handover and coordination workflows need traceable evidence for missing information, uncertain geometry, duplicate candidates and intersections. Visual inspection alone is difficult to repeat or audit.

**Implementation:** A local browser and Python application ingests IFC files, indexes model information, runs deterministic checks, synchronizes findings with a 3D viewer and exports review evidence. This is an evolving portfolio project, not a firm-specific approved QC specification.

## Demonstrated work

- Schema-aware IFC semantics using IfcOpenShell; independent browser WASM geometry extraction using web-ifc.
- 100 MiB multipart uploads, bounded local sessions and cancellable resource-limited geometry jobs.
- Accessible issue selection, paired highlighting, camera framing and spatial render batching.
- Exact and translation-only near duplicate candidates, targeted physical/property comparisons and model-specific review history.
- Explicit opening-host relationships and world-bounds separation evidence.
- A hard-clash reference matrix that preserves the earlier 14/18 kernel baseline and evaluates the corrected pilot against 30 known volume/depth controls.
- Synthetic IFC/IDS generators, Python and Node.js tests, licence-aware vendoring and JSON/CSV/BCF exports.

## Current evidence boundary

Application v0.7.16 recorded 118 passing Python tests and 30/30 Stage 3 controls, with frontend/viewer suites also passing. The bounded Stage 3 pilot is MEP versus structure only. Positive complex intersections can retain unknown depth and prevent a complete threshold-evaluation verdict.

Supplied office-model diagnostics still contain unresolved cross-engine differences and opening-host questions. Reference passes do not certify that model, BIM-firm compliance, drawings, construction tolerances or site reality. Viewer stubs/WASM probes are distinct from local GPU acceptance.

## Next work

Validate Stage 3 in the local browser and reviewed real-model subsets. Extend complex-body depth evidence before scaling. Clearance, connection, alignment and dimension checks remain later staged work. Full IDS integration, IFC correction preview/writeback, before/after version storage, Excel exports and AI-assisted commands are planned.

The current frontend is vanilla JavaScript with Three.js/web-ifc, and the API is Python's standard-library HTTP server. React/TypeScript, FastAPI and PostgreSQL are future architecture options. See [Architecture](ARCHITECTURE.md) and [Roadmap](ROADMAP.md).
