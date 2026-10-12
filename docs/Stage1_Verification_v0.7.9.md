# Stage 1 verification — v0.7.9

Date: 2026-10-03. Scope: independent prototype; no firm checklist, project sign-off or standards certification.

## Exact model tested

`01-ARK_NordicLCA_Office_Timber_As-Built_Revit.ifc`

- Size: 61,308,928 bytes (58.47 MiB).
- SHA-256: `80f2a8fa581e490120e7719b136ccbf057e222f97c6389ec043ab32ef85fca2a`.
- IfcOpenShell 0.8.5; web-ifc 0.0.78; Linux/Python 3.12.14.
- This currently supplied file is smaller than historical files mentioned in conversation. We cannot establish equivalence to the earlier timed-out file without its exact hash. Current evidence must not be used to claim that the historical Windows timeout has been reproduced or resolved.

## Extraction and performance

| Run | End-to-end IFC open + extraction/comparison | Represented products | Generated shapes | Failures |
| --- | --- | --- | --- | --- |
| Archived v0.7.8 source | 372.12 seconds | 8,783 | 8,780 | 3 |
| v0.7.9 measured geometry run | 354.47 seconds | 8,783 | 8,780 | 3 |

These are single runs on this Linux machine, with other small checks active. They establish completion here, not a statistically controlled speed comparison or a Windows/GPU result. v0.7.9 process peak RSS was 888.5 MiB; it excludes browser and whole-application memory. Both runs retained 250-element batches, one thread, and 238 targeted retries. The slow retry group included sanitary terminals. v0.7.9 geometry measurements were retained for later comparison against the final 128-segment web-ifc settings; the exported `post_processing` field makes that explicit.

## Three extraction failures: confirmed defects in these file bytes

| Element | Placement | Missing required reference | Investigation result |
| --- | --- | --- | --- |
| #582910, IfcSlab (roof) | #582909 | #825120 | Product extraction fails; all three extrusion items individually tessellate. Missing RelativePlacement target confirmed in raw text. |
| #73006, IfcOpeningElement | #73005 | #825115 | Product extraction fails; extrusion item individually tessellates. Missing RelativePlacement target confirmed in raw text. |
| #116644, IfcOpeningElement | #116643 | #825119 | Product extraction fails; extrusion item individually tessellates. Missing RelativePlacement target confirmed in raw text. |

The IFC4 [IfcLocalPlacement definition](https://standards.buildingsmart.org/IFC/RELEASE/IFC4/ADD2_TC1/HTML/schema/ifcgeometricconstraintresource/lexical/ifclocalplacement.htm) requires RelativePlacement. These references have no definitions in the supplied file. This is a confirmed exchange-file defect; it does not establish whether the original authoring model/export or a later file change caused it.

web-ifc independently generated meshes for all three and logged invalid-placement references. Rendering therefore does not prove correct placement; accepting its fallback at an assumed placement would hide the defect. This is supported SweptSolid geometry, not evidence of an unsupported primitive. Do not repair these placements by guessing coordinates. Recover the referenced records from an intact source/export.

Independent desktop-viewer visual inspection is **Not evaluated**. The workspace lacks a local browser binary, and the cloud browser refused `127.0.0.1` with `ERR_BLOCKED_BY_CLIENT`. The independent Node WASM inspection is engine evidence, not a desktop-viewer review or a GPU check.

## Model verdict

**Needs attention. Stage 2 extraction prerequisites are blocked for this model.**

- Three confirmed missing-placement defects remain critical.
- Six leaf physical elements (one ramp and five stairs) lack their own representations and have no declared aggregate/nested geometry children. They require review under this demo profile. Representation is not universally mandatory in IFC; these are not declared normative schema defects.
- Aggregate shape coverage is 99.97% before rounding (UI rounds to 100.0%). It cannot override these nine critical IDs.
- 8,633 successfully extracted visible-product IDs are compared; opening voids are intentionally omitted from standalone rendering.
- No missing successful visible-product IDs; one extra browser product (#582910), whose backend extraction failed.
- With 128 circle segments, all compared world bounds are within 1 mm, but 21 elements exceed area/volume demo allowances. These are unresolved engine/mesh discrepancies, not automatically confirmed design/model defects. Their IDs and measured deltas are in the JSON and clickable in the UI.
- Bounds, area and signed-volume diagnostics do not prove complete shape correspondence or manifold validity. Full shape equivalence, drawing completeness, design dimensions/alignment and project/industry acceptance are **Not evaluated**.

## Factual controls and tolerances

- Ten analytic controls pass: IFC4 metres, IFC4 millimetres, IFC2X3, nested rotation, large coordinates, missing-representation rejection, host opening cutout, radius-1 cylinder, two mapped instances and three-level placements.
- All nine renderable fixtures pass independent web-ifc comparison. Expected no-geometry rejection is verified separately.
- Positions/extents: 0.001 m. Area/volume: absolute 0.001 m²/m³ plus 0.5% of backend value. These are chosen **demo-profile tolerances**, not universal BIM standards.
- Default web-ifc circle resolution caused a ~40.5 mm cylinder bound difference and ~5.3% volume difference. Setting 128 circle segments fixes this known case at unchanged tolerances. It increases mesh detail; arbitrary-radius curves and physical GPU performance still need checking.
- Negative tests reject an element translated without changing its extents, a missing cutout without changing host extents, non-finite metrics/bounds, a missing evidence channel, a foreign file hash, and critical missing geometry despite 100% represented-product coverage.
- Original older geometry fixtures use demonstration identifiers; this geometric matrix does not certify their complete IFC schema conformance.

## What remains on your computer

1. Extract this v0.7.9 archive and start `start_windows.bat`; refresh the app page.
2. Load the exact IFC you want to certify. Choose **Run browser/GPU check**, then **Verify extraction evidence**, then **Export evidence JSON**.
3. Confirm the file SHA-256 and size, critical element list, rule table and engine discrepancy IDs. A timeout is inconclusive, not a model defect.
4. Inspect the flagged elements in an independent desktop viewer; retain a screenshot/version and verify that it reports the missing placements rather than silently assigning a default location.

## Evidence files

- `office-v078-stage1.json`: archived v0.7.8 result, including source version/file identity.
- `office-stage1.json`: v0.7.9 measured geometry, final engine comparison, raw defect evidence, analytic matrix and explicit unperformed browser/GPU check.
- `office-webifc.json`: default-resolution comparison run.
- `office-webifc-128.json`: final detailed comparison run (128 segments).
- `extraction-failure-investigation.json` / `failed-elements-webifc.json`: raw placements, independent engine observations and per-item extraction attempts.
- `fixture-verification.json`: analytic and independent WASM control results.

Automated validation: 60 Python tests, viewer geometry/selection tests, frontend interaction tests and independent fixture CLI verification pass. No new clash, connectivity, alignment or dimension milestone is signed off by this work.
