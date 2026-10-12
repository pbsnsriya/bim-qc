# OpenBIM QC Assistant

An open-source, local-first MVP for inspecting IFC files, finding common
information-quality issues, and exporting a review report.

## What works now

- Drag-and-drop IFC upload in the browser
- Interactive local 3D geometry with orbit and zoom controls
- Issue-to-model highlighting with camera framing and direct 3D selection
- IFC2x3 / IFC4 schema detection
- STEP entity parsing and type counts
- Deterministic checks for missing names, duplicate GlobalIds, missing spatial
  containment, missing type assignment, and missing classification
- Coordination, handover, and model-health QC profiles
- Severity and rule filtering
- Element-level issue details
- JSON, CSV, and BCF 2.1 issue export
- IDS validation with issue-to-model highlighting
- IfcOpenShell geometry processing and semantic inspection
- Stage 1 geometry-foundation diagnostics for units, world coordinates, shape
  coverage, STEP-id mapping, finite bounds, extraction failures, and timing
- Duplicate-element and duplicate-tag detection
- MEP-to-structure hard and configurable clearance clash checks
- IFC-port connectivity checks with explicit unverifiable-data reporting
- Orthogonal-alignment and minimum-dimension review rules
- Synthetic good/bad IFC fixtures and automated unit tests
- No cloud upload: files are analysed by the local Python process

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

Load a model and first choose **Validate geometry foundation**. Stage 1 must
pass before the experimental coordination checks unlock. The diagnostic report
shows the IFC schema and length unit, represented/generated shape counts,
coverage percentage, world-coordinate bounds, vertex/triangle counts, failed
elements, warnings, processing time, and the individual pass/fail gates.

After Stage 1 passes, configure the clearance/alignment/dimension tolerances and
choose **Run experimental checks**. Results join the normal issue list and remain
selectable in the 3D viewer and exportable to BCF, JSON, or CSV.

The clash matrix currently evaluates `IfcDistributionElement` objects against
walls, slabs, beams, columns, footings, piles, roofs, ramps, and stairs. Exact
coincident geometry is labelled **probable duplicate** for human confirmation.
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
Browser UI -> web-ifc/Three.js geometry + issue highlighting
     |
     +------> JSON API -> IFC STEP rules ------> JSON / CSV
                         + IfcOpenShell geometry ----> clashes / duplicates
                         + IDS subset ----------> BCF 2.1
```

The code intentionally separates parsing, rules, exchange formats, and optional
backends so the UI issue contract remains stable.

## Current boundary and next milestone

This release does not claim full IDS conformance: property, material,
classification, part-of, and advanced restriction facets need a full IfcTester
adapter. BCF export contains topics and component viewpoints, but no camera or
snapshot yet.

Stage 1 is the currently refined milestone. Duplicate geometry, hard/clearance
clashes, connectivity, alignment, and dimensions remain experimental rule
prototypes and have **not** yet completed their individual refinement stages.
Alignment results are advisory because diagonal elements may be intentional,
and the current dimension prototype only enforces a minimum geometric extent.

Next milestone: refine Stage 2 duplicate-element detection, including tolerance,
confidence, intentional-duplicate exclusions, and a focused validation fixture.

## Licence

MIT. The included IFC fixtures are original synthetic test data created for
this project. See `THIRD_PARTY_NOTICES.md` for vendored viewer dependencies.
