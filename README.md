# OpenBIM QC Assistant

An open-source, local-first MVP for inspecting IFC files, finding common
information-quality issues, and exporting a review report.

## What works now

- Streaming multipart IFC upload up to 100 MiB; each model is sent once
- Interactive local 3D geometry with orbit and zoom controls
- Issue-to-model highlighting with side-aware camera framing, direct 3D
  selection, and X-ray, fade-context, or isolate visibility modes
- IFC2x3 / IFC4 schema detection
- IfcOpenShell-backed semantic traversal and schema-aware type counts
- Deterministic checks for missing names, duplicate GlobalIds, missing spatial
  containment, missing type assignment, and missing classification
- Coordination, handover, and model-health QC profiles
- Severity and rule filtering
- Element-level issue details
- JSON, CSV, and BCF 2.1 issue export
- IDS validation with issue-to-model highlighting
- IfcOpenShell geometry processing and semantic inspection
- Stage 1 geometry-extraction evidence with six analytically known IFC fixtures,
  IfcOpenShell/web-ifc element comparison, explicit 1 mm tolerance, units,
  world coordinates, STEP-id mapping, failures, and timing
- Stage 2 exact-duplicate candidate detection with a four-assertion known-answer
  IFC matrix, 0.001 mm numerical tolerance, explicit exclusions, and paired
  3D highlighting
- MEP-to-structure hard and configurable clearance clash checks
- IFC-port connectivity checks with explicit unverifiable-data reporting
- Orthogonal-alignment and minimum-dimension review rules
- Synthetic good/bad IFC fixtures and automated unit tests
- No cloud upload: files are analysed by the local Python process
- Precise selection outcomes for direct geometry, aggregate children, void
  features, metadata records, and genuine missing representations
- Large-result protection: at most 250 issue rows are rendered at once while
  JSON and CSV exports retain the full result set
- Isolated Stage 1 geometry jobs with live product progress, cancellation,
  a 15-minute limit, a 4 GiB worker-memory ceiling, and one concurrent job
- Browser/GPU evidence probe reporting WebGL version, renderer, drawing-buffer
  size, loaded meshes, draw calls, rendered triangles, frames, and average FPS;
  rendering capability and interactive performance are graded separately

The 3D path uses the open-source `web-ifc` WASM parser and Three.js, both
vendored so the app runs without a CDN or internet connection. If WebGL or
geometry parsing is unavailable, the UI falls back to a data-oriented model map.

## Run

Requires Python 3.10+. Install the geometry dependency once:

```bash
python3 -m pip install -e .
python3 server.py
```

Open <http://127.0.0.1:8000>. Choose `Load demo model` or upload an IFC file.

The upload limit is 100 MiB. The browser uses multipart upload and the local
server keeps a bounded temporary model session, so IDS, profile changes, and
geometry operations do not resend the IFC. Large-model semantic analysis
remains interactive, while full IfcOpenShell tessellation runs in an isolated,
single-worker background job. The UI reports product progress and provides a
real cancel button; a 15-minute timeout and 4 GiB address-space ceiling protect
the main application process.

After loading a model, choose **Validate IDS** for your own `.ids` file or
**Try sample IDS**. The dependency-free validator supports entity applicability
and required/prohibited `GlobalId`, `Name`, and `Description` attributes. It
marks results as partial whenever a file uses a facet outside that subset.
IDS failures join the issue list, so selecting one highlights its IFC element.

Choose **Export BCF** to create a BCF 2.1 `.bcfzip` with one topic per QC/IDS
finding and an IFC component selection when a GlobalId is available.

For the optional full IDS toolkit, install:

```bash
python3 -m pip install -e ".[full]"
```

IfcOpenShell is the geometry engine for coordination checks. The capability API
also detects IfcTester, while the built-in IDS subset remains the current
interactive issue adapter.

On Windows, extract the ZIP and double-click `start_windows.bat`; it installs
IfcOpenShell if missing, then starts the application. Do not open
`web/index.html` directly: the API and WASM viewer require the local server.

## Geometry coordination checks

Load a model and first choose **Verify extraction evidence**. Stage 1 must pass
before the experimental coordination checks unlock. The evidence report shows:

- a six-case known-answer matrix covering metre/millimetre units, IFC4/IFC2X3,
  nested rotated placement, large coordinates, and expected rejection when a
  product has no representation;
- independently measured IfcOpenShell and browser web-ifc element IDs and
  extents, compared at a 1 mm tolerance;
- schema, units, extraction coverage, world bounds, STEP-id mapping,
  vertices/triangles, failures, warnings, and processing time.

After validation, choose **Export evidence JSON** to retain the complete matrix,
engine versions, measurements, deltas, tolerances, browser/GPU probe, and
conclusion. Choose **Run browser/GPU check** after the 3D model loads and keep
the tab visible during its two-second frame probe.

This is deliberately an **extraction-consistency** claim. It proves that known
fixtures behave as expected and that two geometry engines agree on the uploaded
model. It does not prove that the IFC agrees with approved drawings, design
intent, schedules, survey data, or the built asset; those require a selected
external reference in a later comparison milestone.

After Stage 1 passes, choose **Validate exact duplicates**. The application first
checks its original synthetic truth fixture, then reports same-class elements
with identical world-space tessellated geometry. Selecting a finding highlights
both members of the candidate pair. A match still requires human review before
anything is deleted.

The clash matrix currently evaluates `IfcDistributionElement` objects against
walls, slabs, beams, columns, footings, piles, roofs, ramps, and stairs. Exact
coincident same-class geometry is labelled **exact duplicate candidate** for
human confirmation.
Connectivity uses exported `IfcDistributionPort` relationships; models without
ports are reported as unverifiable instead of being incorrectly failed.

## Test

```bash
python3 -m unittest discover -s tests -v
```

The optional frontend interaction suites require Node.js 20+:

```bash
cd web
npm install
npm test
```

They verify selection materials, camera framing, raycasting, issue/data-map
synchronization, clearing, and accessible issue controls.

## Architecture

```text
Browser UI -> one multipart IFC upload -> bounded local model session
     |                                      |
     +-> web-ifc/Three.js viewer            +-> semantic QC / IDS / exports
                                            +-> isolated geometry job
```

IfcOpenShell is the semantic and engineering source of truth. web-ifc handles
browser rendering and independent geometry evidence. The original lightweight
STEP parser remains only as a small educational/test utility and is not used by
the production QC endpoint.

## Current boundary and next milestone

This release does not claim full IDS conformance: property, material,
classification, part-of, and advanced restriction facets need a full IfcTester
adapter. BCF export contains topics and component viewpoints, but no camera or
snapshot yet.

Stage 1 is signed off. Stage 2 currently covers exact duplicate candidates only.
Hard/clearance clashes, connectivity, alignment, and dimensions remain
experimental rule prototypes and have **not** completed their individual stages.
Alignment results are advisory because diagonal elements may be intentional,
and the current dimension prototype only enforces a minimum geometric extent.

Next Stage 2 increment: near-duplicate tolerance, confidence scoring, and
project-configurable intentional-repeat exclusions.

## Licence

MIT. The included IFC fixtures are original synthetic test data created for
this project. See `THIRD_PARTY_NOTICES.md` for vendored viewer dependencies.
