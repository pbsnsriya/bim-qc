# Opening–host consistency — v0.7.14

This increment screens explicit IFC void relationships for geometric separation.
It does not decide accidental duplication, repair relationships, or certify a
valid cut. Existing duplicate decisions and reviewer notes remain unchanged.

## Start and find the result

1. Stop the old server, extract this release into a new folder, and run
   `start_windows.bat`. Refresh the browser with Ctrl+F5 and confirm **v0.7.14**.
   Use the same browser/address to retain locally saved review decisions.
2. Upload the IFC, complete Stage 1 readiness prerequisites, and run
   **Validate duplicates**. Server-side geometry evidence from the previous
   process is not retained across a server restart.
3. Open the opening issue's **Compare #A ↔ #B** disclosure. Below **Highlight
   hosts**, find **Opening–host consistency**. Comparison measures only the
   requested openings and hosts; it does not start whole-model tessellation.
4. Read each finding, its bounds distance lower bound, axis gaps and threshold.
   Expand **Measured bounds and source relationship** for coordinates and IFC
   relationship IDs. Expand **Rule, measurement and limits** for provenance.
5. Click **Highlight opening + host** on one relationship, then choose
   **Isolate selected** in the viewer to remove context. Amber is selectable
   geometry; the orange box encloses selected geometry. If the opening has no
   selectable mesh, a **cyan diagnostic bounds marker** shows its measured
   location. The status explicitly distinguishes this marker from geometry and
   reports partial/missing selections or unresolved Stage 1 placements.
6. **Clear selection** removes the bounds marker and restores model appearance.
   Review decisions and notes remain manual. **Export JSON** includes successful
   comparisons opened for the current model, their fingerprints, and all check
   measurements. Unopened or failed comparisons are not evaluated by this export.

## Rule and status meanings

Source relationships are read from `IfcOpeningElement.VoidsElements` and
`IfcRelVoidsElement.RelatingBuildingElement`, not inferred from element names,
type names, or nearby geometry. The [buildingSMART IFC4 opening definition](https://standards.buildingsmart.org/IFC/RELEASE/IFC4/FINAL/HTML/schema/ifcproductextension/lexical/ifcopeningelement.htm)
describes the opening as a void associated with its host. It does not supply the
application's 1 mm tolerance.

Fresh targeted IfcOpenShell tessellation measures every supplied **Body**
representation in IFC world coordinates, Z-up, metres. Axes and annotations are
excluded. IFC opening subtractions are disabled when measuring the bodies;
holes already embedded in exported tessellation or boolean Body geometry remain.
See the official [IfcOpenShell geometry settings](https://docs.ifcopenshell.org/ifcopenshell/geometry_settings.html).
The implementation was tested using IfcOpenShell **0.8.5**.

For each X/Y/Z axis, the gap is the maximum of zero, host minimum minus opening
maximum, and opening minimum minus host maximum. The Euclidean length of those
three gaps is the distance between the axis-aligned bounding boxes. It is a
**lower bound** on the geometry distance, not the exact surface distance.

| Finding | Measurable condition | Meaning |
| --- | --- | --- |
| Measured separation | Bounds gap exceeds 1 mm plus numeric slack | Extracted bodies cannot contact within this screening threshold. Investigate the export and relationship. |
| Unresolved — gap within threshold | Positive bounds gap is at most 1 mm plus slack | Small measured separation; actual contact/cut validity remains unknown. |
| Unresolved — bounds overlap or touch | Zero bounds gap within numeric slack | Necessary bound condition only. No body-intersection or valid-cut PASS. |
| Not evaluated | Missing explicit host, no Body, or incomplete/failed extraction | Required evidence is unavailable. No model-defect verdict. |

The 1 mm gap threshold is a disclosed **application screening default**, not an
industry, firm, or project acceptance standard. It is independent of the
near-duplicate placement tolerance. Numeric comparison slack is 0.000001 mm
(one nanometre) to accommodate floating-point threshold boundaries.

## Independent factual controls

Use `samples/golden/opening_host_matrix.ifc`. Its generator is
`scripts/generate_opening_host_fixture.py`; the positions below are specified
analytically, independently of extracted output. The first two openings coincide
but reference different hosts, producing one opening duplicate candidate for
review. Each sample label is preserved in the IFC.

| Opening name | Expected bounds gap | Expected finding |
| --- | ---: | --- |
| Coincident A — host overlaps | 0 mm | Unresolved — overlap |
| Coincident B — wrong distant host | 8000 mm | Measured separation |
| Within threshold 0.5 mm | 0.5 mm | Unresolved — within threshold |
| Threshold boundary 1 mm | 1 mm | Unresolved — within threshold |
| Beyond threshold 1.001 mm | 1.001 mm | Measured separation |
| Touching bounds | 0 mm | Unresolved — touching |
| Bounds overlap without body contact | 0 mm | Unresolved — overlap, never PASS |

The last control places the opening in empty space between two disjoint host
solids enclosed by one bounding box. It deliberately tests the limit of this
method: bounds can overlap while the bodies do not contact. This fixture is a
constructed factual control, not a publicly reviewed industry project.

Additional automated cases cover a 3/4/12 m axis separation with an independently
known 13 m bounds distance, IFC millimetre units, nested rotated placements,
missing relationships, missing/Axis-only bodies, extraction failure, uncut host
bounds, shared-host measurement reuse, and multiple relationships. Existing
IFC2x3 opening-host comparison tests remain passing.

## Supplied office IFC

Source: `01-ARK_NordicLCA_Office_Timber_As-Built_Revit.ifc`, **81,357,305 bytes**.
SHA-256: `f99b62ccadd9d625c64c4b68f89eda544ea8cac5986970d0a21473d9fcb3fd76`.

| Opening | Explicit relationship | Host | Axis gaps X/Y/Z | Bounds distance lower bound | Finding |
| --- | --- | --- | --- | ---: | --- |
| #66076 | #66082 | #65997 · KS-2 | 44691.198496 / 38077.409108 / 0 mm | 58712.795091 mm | Measured separation |
| #108748 | #108754 | #108613 · KS-1 | 0 / 0 / 0 mm | 0 mm | Unresolved — overlap |

The comparison completed locally in approximately **13.14 seconds**, including
loading the 77.59 MiB source and measuring this pair. This is targeted comparison
timing, not a whole-model tessellation or browser-performance result.

Full targeted comparison output, source identity, settings and coordinates:
`docs/evidence/office-opening-host-v0.7.14.json`.

Independent Node.js web-ifc WASM bounds evidence:
`docs/evidence/office-opening-host-webifc-v0.7.14.json`. It compares only the four
requested opening/host IDs with the IfcOpenShell bounds at a 1 mm coordinate
tolerance. It does not certify full shape equality, actual contact, all elements
in the model, or the user's GPU/browser. To reproduce after installing frontend
dependencies (`cd web` then `npm ci`), run from the project root:

```bash
node scripts/verify_opening_host_world_bounds.mjs MODEL.ifc docs/evidence/office-opening-host-v0.7.14.json OUTPUT.json
```

The script rejects a source fingerprint mismatch. A different revision of the
same filename must be measured independently.

## Verification and remaining local check

**99 Python tests passed**, including the new factual controls, API evidence,
and prior Stage 1/Stage 2 regressions. `npm test` passed the viewer, render-batch
and frontend integration suites. Frontend checks cover relationship-specific
selection, partial selection with a bounds marker, missing hosts, unchanged
decisions, and fingerprinted JSON evidence. Marker tests verify the signed
Z-up/Y-up conversion and model recentering against independently known coordinates.

Integration uses a viewer stub, and coordinate tests run without a GPU. The
remaining local acceptance check is to locate #66076 with host #65997, isolate
them, verify the labelled cyan marker is spatially separated from the amber
host, and verify clear/reset. No new Edge or local GPU test was performed here.
Keep the duplicate pair **Unresolved** until its relationship/author intent is
reviewed. No automatic correction is applied.
