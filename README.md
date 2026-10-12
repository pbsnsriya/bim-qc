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
- Opening–host consistency evidence: measured bounds separation, explicit
  unresolved/missing states, and a cyan opening bounds marker when the void has
  no selectable viewer mesh
- JSON, CSV, and BCF 2.1 issue export
- IDS validation with issue-to-model highlighting
- IfcOpenShell geometry processing and semantic inspection
- Stage 1 geometry-extraction evidence with ten analytically known IFC fixtures,
  IfcOpenShell/web-ifc element comparison, explicit 1 mm tolerance, units,
  world coordinates, STEP-id mapping, failures, and timing
- Stage 2 exact-duplicate candidate detection with a four-assertion known-answer
  IFC matrix, 0.001 mm numerical tolerance, explicit exclusions, and paired
  3D highlighting
- Stage 3 controlled hard-clash reference probe: known kernel misses are visible;
  model clash checking remains blocked pending their resolution
- Legacy experimental clearance, connectivity, alignment and dimension code is
  retained for development; these later milestones have not passed staged acceptance
- Synthetic good/bad IFC fixtures and automated unit tests
- No cloud upload: files are analysed by the local Python process
- Precise selection outcomes for direct geometry, aggregate children, void
  features, metadata records, and genuine missing representations
- Large-result protection: at most 250 issue rows are rendered at once while
  JSON and CSV exports retain the full result set
- Isolated Stage 1 geometry jobs with live product progress, cancellation,
  a size-aware 15/30/45-minute limit, a 4 GiB worker-memory ceiling, and one concurrent job
- A size-aware 5/10/15-minute no-progress watchdog distinguishes stalled jobs
  from slow but advancing tessellation; timeouts are explicitly inconclusive
- Completed Stage 1 evidence is cached for the exact IFC SHA-256 plus browser
  geometry evidence during the current server session, avoiding repeated work
- Large-model tessellation runs in bounded 250-element batches. A malformed or
  omitted shape can therefore trigger targeted recovery only for its batch,
  instead of forcing every remaining model element through a slow individual retry.
- Stage 1 reports IFC-open, bulk-tessellation, targeted-retry and engine-comparison
  timings together with retry counts and the slowest fallback elements.
- Windows-safe geometry progress updates: temporary antivirus/indexer file
  locks are retried and cannot abort the underlying tessellation job
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
real cancel button; size-aware wall/CPU limits and a 4 GiB address-space ceiling protect
the main application process. On Windows, temporary locks on the progress JSON
are retried; progress-reporting failures no longer terminate geometry extraction.
The UI reports elapsed time and the active limit. A timeout or no-progress stop
produces no Stage 1 verdict and must not be interpreted as invalid model geometry.
Completed evidence is reused when the exact IFC and browser geometry signature
are validated again before the local server is restarted.

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

Load a model and first choose **Verify extraction evidence**. Stage 2 readiness
must pass before duplicate review unlocks; strict extraction consistency can
still need attention. The evidence report shows:

- a ten-case known-answer matrix covering metre/millimetre units, IFC4/IFC2X3,
  nested rotated placement, large coordinates, openings, curved solids, mapped
  instances, complex placements, and expected missing-representation rejection;
- independently measured IfcOpenShell and browser web-ifc element IDs and
  world bounds, compared at 1 mm, plus triangulated area/volume diagnostics with
  a demo allowance of 0.001 m²/m³ + 0.5% of the backend value;
- schema, units, extraction coverage, world bounds, STEP-id mapping,
  vertices/triangles, failures, warnings, and processing time.

After validation, choose **Export evidence JSON** to retain the complete matrix,
engine versions, measurements, deltas, tolerances, browser/GPU probe, and
conclusion. Choose **Run browser/GPU check** after the 3D model loads and keep
the tab visible during its two-second frame probe.

This is an **extraction-consistency** claim under an explicit demo profile.
Bounds, area and volume support consistency checks; they do not establish full
surface correspondence, manifold validity or complete shape equivalence.
Every unresolved critical solid/physical leaf remains a readiness blocker even
when coverage exceeds 95%. Optional representations are not universally IFC errors.
The rule table publishes source, expected value, measured value, tolerance and verdict.
Project compliance, drawing completeness and normative schema conformance remain
**Not evaluated** unless their required references/validators have been supplied. It does not prove that the IFC agrees with approved drawings, design
intent, schedules, survey data, or the built asset; those require a selected
external reference in a later comparison milestone.

After Stage 2 readiness passes, choose **Validate duplicates**. The application first
checks its original synthetic truth fixture, then reports same-class physical
elements with identical world-space tessellated geometry. Selecting a physical
finding highlights both members of the candidate pair. Subtraction features such
as `IfcOpeningElement` are excluded from the physical rule and reported under
**duplicate opening candidate** instead; selecting one highlights the related
host wall, slab, or other building element. A match still requires human review
before anything is changed or deleted.

The strict Stage 1 evidence result and Stage 2 capability gate are intentionally
separate. Stage 1 may retain an extent-variance warning when IfcOpenShell and
web-ifc tessellate a small number of elements differently. Exact duplicate
analysis can still unlock when core extraction passes and every backend element
has a browser STEP-id/extent mapping, because duplicate decisions are made only
by IfcOpenShell and the viewer uses those stable IDs solely for highlighting.
After the check, Quality Review automatically filters to both physical and
opening-void duplicate candidates. Clicking a candidate returns the page to the
3D viewer. Exactly coincident physical elements may visually appear as one amber
object because they occupy the same space; opening findings highlight their
selectable hosts because subtraction voids are not standalone rendered meshes.

Each duplicate candidate includes a project review decision: **Unresolved**,
**Confirmed duplicate**, or **Intentional / not duplicate**, plus a reviewer
evidence note. Uploaded IFCs receive a streaming SHA-256 fingerprint, and review
decisions are stored locally against that exact model fingerprint, so rerunning
Stage 2 retains the ledger while a different IFC revision cannot silently inherit
old decisions. The live truth-matrix summary reports confirmed, intentional,
and unresolved counts and reviewer confirmation rate. This rate is not measured
detection accuracy. Recall remains explicitly
unavailable until reviewers also record duplicates the detector missed.

The general JSON and CSV reports include review status, note, and timestamp.
**Export truth matrix CSV** produces a focused candidate ledger containing the
canonical pair key, physical/opening classification, opening and host IDs,
selection IDs, decision, evidence, confidence, tolerance, and detection basis.

The controlled Stage 3 probe compares `IfcDistributionElement` bodies against
structural classes. Its failed reference gate is shown separately from model
duplicate results. Legacy connectivity prototypes use exported
`IfcDistributionPort` relationships; they are not enabled in the released API.

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

IfcOpenShell measures semantics and backend geometry; those measurements still
require independent checks and disclosed limitations. web-ifc handles
browser rendering and independent geometry evidence. The original lightweight
STEP parser remains only as a small educational/test utility and is not used by
the production QC endpoint.

## Current boundary and next milestone

This release does not claim full IDS conformance: property, material,
classification, part-of, and advanced restriction facets need a full IfcTester
adapter. BCF export contains topics and component viewpoints, but no camera or
snapshot yet.

Stage 1 must be verified per exact model SHA-256. The supplied office model remains
**needs attention**; the current evidence must not be called a project sign-off. Stage 2 currently covers exact physical duplicate
candidates, separately reviewed exact opening-void candidates, and a persistent
accept/reject truth-matrix workflow, plus translation-only near-duplicate
candidates with a configurable 0.01–100 mm placement limit.
Project-configurable intentional-repeat rules remain a later increment.
Hard/clearance clashes, connectivity, alignment, and dimensions remain
experimental rule prototypes and have **not** completed their individual stages.
Alignment results are advisory because diagonal elements may be intentional,
and the current dimension prototype only enforces a minimum geometric extent.

The next milestone is controlled Stage 3 hard-clash validation. Its current
18-case reference gate fails because aligned overlaps are missed. Resolve those
misses before enabling model scans; clearance and subsequent stages remain deferred.

## v0.7.15 review provenance and Stage 3 reference gate

Fresh backend measurements, the viewer and exports now use the same release
identity. Exporter version/time are separate from original measurement
provenance, including cached evidence.

The identified persistence-test confirmation for office openings #66076/#108748
is returned to **Unresolved** when the same IFC SHA-256 and exact test note are
loaded. Its old decision, note and time remain in archived review history and
the JSON ledger. Other judgements are untouched. Reviewer confirmation rate is
explicitly distinct from measured detection accuracy.

Click **Validate Stage 3 reference cases** under the Stage 3 panel. The small
metre/millimetre models run independently of the uploaded model and reveal
expected versus measured answers. IfcOpenShell 0.8.5 passes **14/18** controls,
missing aligned 250 mm and 3 mm overlaps in both units. This is a **failed
engine/probe reference gate**, not an IFC model failure. Model clash checking
remains blocked, including direct attempts to enable later checks through the
legacy geometry API. Duplicate review remains available.

Use **Export Stage 3 reference JSON** and **Download hard-clash sample IFC** to
inspect the evidence. The package includes both unit variants and the fixture
generator. See `docs/Stage3_Reference_Gate_v0.7.15.md` for measurements, limits,
review repair and repeatable checks.

## v0.7.14 opening–host geometry screening

Open an opening candidate's **Compare #A ↔ #B** panel and find
**Opening–host consistency** below the host controls. Each explicit relationship
shows the bounds distance lower bound, X/Y/Z gaps, the 1 mm screening threshold,
world bounds, and source relationship IDs. Measured separation is flagged;
overlapping bounds remain **Unresolved**, and unavailable evidence is
**Not evaluated**. This is not a solid-intersection or valid-cut certification.

**Highlight opening + host** requests the actual opening and its assigned host.
If the viewer has no opening mesh, it displays a cyan measured bounds marker
and labels it as diagnostic bounds, not opening geometry. Use **Isolate selected**
to remove surrounding geometry, and **Clear selection** to remove the marker
and restore the model. Existing review decisions and notes are retained.

**Export JSON** now preserves the successful comparisons opened for this model,
including their source fingerprints and numerical evidence. Unopened or failed
comparisons are explicitly outside that export's evaluated scope.

The supplied office opening #66076 has a measured bounds gap of at least
58.712795 m to its assigned host #65997. Opening #108748/host #108613 have
overlapping bounds and remain unresolved. These results concern the exact IFC
revision identified in the evidence, not every revision of the same filename.

See `docs/Opening_Host_Geometry_v0.7.14.md` for the test IFC, acceptance steps,
numerical rule and measurement limits. The existing stage milestones remain
separate; this targeted comparison does not rerun whole-model tessellation.

## v0.7.13 near-duplicate candidates

Under Stage 2, enable **Include near-duplicates** and choose **Placement tolerance
(mm)**, initially 5 mm. Click **Validate duplicates** after Stage 1 readiness
passes. Exact, near physical and opening candidates share pair selection,
comparison, decisions and reviewer notes. Changing settings shows a rerun hint;
old results retain their recorded tolerance. Reviews survive reruns and tolerance
changes for the same exact IFC fingerprint.

Near detection measures Euclidean world bounds centre distance and verifies
translation-normalised triangular surfaces, including triangle connectivity.
Matching bounds alone cannot qualify. Each candidate records ΔX/ΔY/ΔZ, distance,
placement limit, surface residual and a separate 0.001 mm numerical shape limit.
The placement setting is a review threshold, not a construction standard.

The search uses adjacent spatial cells and is bounded at 250,000 nearby pair
comparisons and 5,000 results; reaching either limit is explicitly INCOMPLETE.
Represented geometry that cannot be evaluated is disclosed separately. Different
triangulations can be missed, and rotational alignment is not attempted.
Opening voids are excluded from near physical matches; exact opening review stays
unchanged. Candidates never automatically delete elements or decide intent.

Test with `samples/golden/duplicate_near_matrix.ifc`: at 5 mm, expect **4 near
pairs and 1 exact pair**. At 1 mm, expect **0 near pairs and 1 exact pair**.
The near reference matrix reports **12/12** assertions when it passes.
JSON includes scan completeness and reference evidence; QC/truth-matrix CSV
exports include the measured near-pair fields.

See `docs/Near_Duplicate_Validation_v0.7.13.md` for acceptance steps and boundaries.

## v0.7.12 opening hosts

Opening pair comparisons now show each **Host element (IfcRelVoidsElement)**
with its STEP ID, IFC class, name and assigned type name, when exported.
Click **Highlight hosts** under the comparison table to select and frame the
hosts using the existing X-ray, fade or isolate mode. **Clear selection** resets
the viewer. The control reuses the cached comparison and does not change review
decisions or notes.

Missing relationships produce an explicit **Not evaluated** warning. The host
button is disabled if neither opening has a known host. A shared host is selected
once; distinct hosts are shown as contextual differences, excluded from the
physical-difference count. Partial or unavailable viewer selection is reported.

For opening voids, absent type, material and load-bearing fields are **Not
applicable**; exported values remain visible. Phase/status and assembly information
are still **Not evaluated** when absent. Physical elements retain the existing
missing-information handling. No host is inferred from an element name or position.

See `docs/Opening_Host_Comparison_v0.7.12.md` for the verified supplied-model
relationships, automated checks and local acceptance steps.

## v0.7.11 pair comparison

Click a duplicate issue to highlight its pair and open the **Compare #A ↔ #B**
panel immediately underneath. You can also open Compare independently using
its keyboard-accessible disclosure. The panel shows type, material names,
storey, load-bearing status, dimensions, world position and identities side by
side. Amber rows identify physical/property differences; blue rows identify
different records. Missing values are explicit, not matching verdicts.

Expand **Source properties and quantities** to compare occurrence and type
values. Property-set record IDs are excluded. Length and coordinate measurements
are normalized to mm and m; source quantities retain their declared IFC units.

Comparison reads the existing uploaded IFC session and tessellates only the
two requested elements. Results are cached in the page for the current model;
review edits and filter changes reuse them. Failed requests offer Retry.
Loading a new model clears the cache and aborts pending browser requests.
Server comparisons are serialized to avoid parsing multiple large models at
once. This adds no new whole-model tessellation gate.

**Decision** and **Reviewer note** remain manual and retain the existing
model-specific saved ledger. Matching properties or bounds do not certify
full shape equality or prove that the author intended a duplicate. Near
duplicates and hard clashes remain later increments.

See `docs/Pair_Comparison_v0.7.11.md` for the two supplied column acceptance
cases, automated verification and measurement limits.

## v0.7.10 viewer optimization

Opaque geometry with matching materials is now merged into spatial render
batches. Transparent parts remain individually sortable. Materials and repeated
source geometry are shared; IFC STEP IDs remain attached to triangle ranges for
picking, while selected elements use separate amber overlays. X-ray, fade,
isolate, pair highlighting and clear selection remain available. Geometry
evidence is measured from the original web-ifc output before render batching.

The viewer redraws on camera, resize, selection and context-restoration changes.
The browser/GPU probe forces continuous rendering, so idle redraw suppression
does not inflate measured FPS. Probe exports now record batching counts,
selected IDs, selection mode and camera position/target.

To compare performance: start this build, refresh the browser, load the same
IFC, click **Frame model**, run **Run browser/GPU check**, and click **Export
GPU evidence**. The standalone GPU export does not require backend geometry
validation. Test issue selection, direct geometry picking, pair highlighting,
isolate/fade and clear selection separately before approving the viewer change.

See `docs/Viewer_Optimization_v0.7.10.md` for verification results and limits.
This release does not resolve cross-engine geometry discrepancies or claim a
verified FPS improvement on your hardware.

## v0.7.9 evidence and verification

See `docs/Stage1_Verification_v0.7.9.md` and `docs/evidence/office-stage1.json`.
The archive includes original v0.7.8 extraction evidence on the currently supplied
61,308,928-byte office IFC. This is not proof for the earlier differently sized
model or for the user's Windows machine. Browser/GPU results are explicitly
Not evaluated here because no usable local browser was available.

web-ifc uses 128 circle segments in both the browser and independent Node script.
This fixes the known 1 m cylinder's coarse default tessellation discrepancy
without changing acceptance tolerance. It does not guarantee 1 mm approximation
for arbitrary radii/curves. More detailed meshes may cost browser memory and FPS;
the physical GPU check remains required for your local model.

For independent geometry verification (Node required), run `npm ci --prefix web`,
then `python3 scripts/verify_stage1_crossengine.py`. For large-model extraction,
run `python3 scripts/export_stage1_evidence.py MODEL.ifc evidence.json`; optionally
supply `--comparison webifc-evidence.json` generated by
`node scripts/web_ifc_evidence.mjs MODEL.ifc webifc-evidence.json`.
These CLI runs provide WASM comparison, not browser/GPU certification.

## Licence

MIT. The included IFC fixtures are original synthetic test data created for
this project. See `THIRD_PARTY_NOTICES.md` for vendored viewer dependencies.
