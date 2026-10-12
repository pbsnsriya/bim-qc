# BIM QC

**OpenBIM Quality & Mapping Assistant** — a local-first IFC inspection and quality-review project maintained by [pbsnsriya](https://github.com/pbsnsriya).

Upload an IFC, inspect its geometry, investigate information-quality issues, compare possible duplicates, and export traceable review evidence. Application version: **v0.7.16**.

The current application uses deterministic rules and geometry measurements. AI-assisted instructions and correction suggestions are planned; there is no connected AI service in this release.

## Current capabilities

| Area | Implemented behavior |
| --- | --- |
| IFC ingestion | Streaming multipart upload up to 100 MiB; bounded temporary model sessions; IFC2x3/IFC4 schema detection |
| 3D review | web-ifc/Three.js viewer, direct picking, issue highlighting, pair selection, camera framing, X-ray/fade/isolate and clear selection |
| Information checks | Missing names, duplicate GlobalIds, missing containment, missing assigned types and missing classification; QC profiles and issue filters |
| Stage 1 | IfcOpenShell extraction evidence, independently measured web-ifc comparisons, known-answer fixtures, explicit tolerances, progress, cancellation and timeout controls |
| Stage 2 | Exact physical/opening candidates, translation-only near-duplicate candidates, pair/property comparisons, explicit opening hosts and saved reviewer decisions |
| Stage 3 | Bounded MEP-versus-structure hard-clash pilot with 30 known-answer controls, solid intersection volume and convex minimum-translation measurements |
| IDS | Limited entity/IfcRoot-attribute validation; unsupported facets are disclosed rather than treated as passed |
| Exports | JSON, CSV, BCF 2.1 issue topics and component viewpoints, extraction/reference/GPU evidence |

Findings are candidates for review. Matching bounds or properties do not prove duplicate intent. Geometry extraction evidence is separate from project compliance. This application does not automatically edit or delete model elements.

## Run locally

Requires **Python 3.10+**. Node.js is needed only for development tests and independent WASM comparison scripts.

```bash
git clone https://github.com/pbsnsriya/bim-qc.git
cd bim-qc
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -e .
python server.py
```

Open <http://127.0.0.1:8000>. On Windows, `start_windows.bat` installs the Python dependencies and starts the application. The vendored viewer files allow browser rendering without a CDN after dependencies are installed.

Try `samples/geometry_demo.ifc` for general review. For Stage 3, use **Load hard-clash sample**, wait for the viewer, run **Verify extraction evidence**, then **Validate Stage 3 reference cases** and **Validate hard clashes (pilot)**. At the default 2 mm threshold the compact sample produces five candidates and one positive complex intersection whose depth is **Not evaluated**.

Extraction completion alone does not unlock Stage 3. Its gate requires passed extraction/browser-mapping prerequisites for the currently loaded model and passed Stage 3 reference controls. Loading another IFC resets model readiness.

## Actual stack

| Layer | Used in v0.7.16 |
| --- | --- |
| Frontend | HTML, CSS, vanilla JavaScript ES modules |
| Viewer | Three.js 0.180.0 and That Open's web-ifc 0.0.78 WASM parser; spatial rendering batches and selection overlays |
| Local HTTP API | Python standard-library `ThreadingHTTPServer`; JSON and multipart endpoints |
| IFC semantics and tessellation | IfcOpenShell 0.8.5 |
| Solid intersection | Manifold3D 3.5.1; convex SAT minimum-translation calculations |
| Session/review storage | Temporary local IFC files, bounded in-memory session/job state, browser localStorage keyed to model SHA-256 |
| Tests | Python unittest, Node.js assertions, jsdom and independent web-ifc WASM probes |

React/TypeScript, FastAPI, full IfcTester validation, PostgreSQL, Excel writeout, structured AI tool calls and Docker are **future options**, not dependencies of this release. The viewer uses web-ifc directly rather than That Open Components/Fragments.

## Architecture and engineering evidence

See [Architecture](docs/ARCHITECTURE.md) for data flow, APIs and resource boundaries; [Local usage](docs/LOCAL_USAGE.md) for detailed controls and evidence interpretation; [Roadmap](docs/ROADMAP.md) for staged milestones; and [Portfolio brief](docs/PORTFOLIO_BRIEF.md) for the project story.

Stage 3 evaluates at most **100 eligible elements**, **200,000 triangles** and **2,500 retained pair tests**. Larger IFCs require a selected STEP-ID subset. Positive non-convex intersections remain visible with unknown depth; they do not receive a false pass. Clearance, connection, alignment and dimension prototypes are not enabled in the released API.

The supplied office-model evidence remains subject to unresolved engine discrepancies and opening-host questions. Passing the reference fixture does not clear a real project or certify compliance with a BIM firm's standards.

## Test

```bash
python -m unittest discover -s tests -v
npm ci --prefix web
npm test --prefix web
python scripts/verify_hard_clash_reference.py local-reports/hard-clash-reference.json
```

The v0.7.16 release recorded **118 passing Python tests and 30/30 Stage 3 reference controls**, with frontend/viewer suites also passing. Automated viewer tests and headless WASM comparison are separate from a physical browser/GPU acceptance test.

## Repository history

The Git history imports eight CRC-verified source snapshots from **v0.7.9 through v0.7.16**, each tagged by version, followed by repository documentation. These are release-import commits created now, not the original development commits or dates. Original MVP–v0.7.8 snapshots could not be recovered and have not been fabricated. See [Release history](docs/RELEASE_HISTORY.md) and the [snapshot manifest](docs/release-snapshots.json).

Source, synthetic IFC/IDS samples, test suites, scripts, vendored viewer runtime, licence notices and existing release evidence are included. Dependency installations, temporary uploads, credentials and generated build caches are excluded.

## Contributing and licence

Read [Contributing](CONTRIBUTING.md) and [Security](SECURITY.md). Project code is MIT licensed; retain the separate licences for vendored dependencies in [Third-party notices](THIRD_PARTY_NOTICES.md).
