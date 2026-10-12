# v0.7.15: provenance, review correction and controlled Stage 3 testing

## Install and inspect

1. Stop the old server. Extract this release into its own folder and run
   `start_windows.bat`. Refresh Edge with Ctrl+F5 and confirm **v0.7.15**.
2. Load the same office IFC. A new whole-model geometry run is not necessary
   to repair the saved review ledger or test the synthetic Stage 3 matrix.
3. Under **STAGE 3 · CONTROLLED HARD-CLASH TESTING**, click **Validate Stage 3
   reference cases**. Expected current result: **FAIL · 14/18**.
4. Click **Export Stage 3 reference JSON**. This report tests the engine on
   small reference models; it does not evaluate the uploaded office IFC.
5. **Download hard-clash sample IFC** lets you inspect the metre fixture in
   this or another viewer. The millimetre variant is included under
   `samples/golden/hard_clash_matrix_millimetre.ifc`.

## What the factual matrix establishes

Expectations are specified independently using constructed box coordinates,
dimensions and an explicit opening relationship. The same nine cases are
encoded with metre and millimetre IFC length units. Geometry is tessellated in
world coordinates with opening subtractions enabled. All 18 eligible bodies
extract as finite manifold meshes in each fixture.

The following results occur identically in both unit variants with IfcOpenShell
**0.8.5**, a **2 mm** strict-greater-than screening policy and **0.000001 mm**
boundary slack. The dependency is pinned for reproducibility.

| Known case | Analytic intersection volume (m³) | Expected candidate | Measured candidate | Result |
|---|---:|---|---|---|
| Aligned boxes overlapping 250 mm | 0.25 | Yes | No | False negative |
| Boxes separated by 100 mm | 0 | No | No | Pass |
| Face touching | 0 | No | No | Pass |
| 1 mm overlap | 0.001 | No, below threshold | No | Pass |
| 2 mm overlap | 0.002 | No, boundary excluded | No | Pass |
| Aligned boxes overlapping 3 mm | 0.003 | Yes | No | False negative |
| Contained 0.5 m cube | 0.125 | Yes | Yes, 250 mm kernel distance | Pass |
| Duct through an explicitly subtracted opening | 0 | No | No | Pass |
| Duct between two disjoint solids with overlapping combined bounds | 0 | No | No | Pass |

The volume column is an **analytic reference fact**, not an engine volume
measurement. The kernel's protrusion/pierce distance is neither intersection
volume nor a universal minimum translation distance. A passing negative control
means agreement with that expected answer; it does not establish that the
algorithm correctly handles all similar configurations.

Independent regression checks inspect actual tessellated bounds for the
250 mm and 3 mm controls. Because these controls are single axis-aligned
rectangular extrusions, their intersections are analytically established.
No bounding-box-overlap heuristic is substituted for shape intersection on
general IFC geometry. The disjoint-solid and opening controls specifically
guard against such a shortcut.

The reference evidence is `docs/evidence/hard-clash-reference-v0.7.15.json`.
Each unit variant records its exact file SHA-256, extraction counts, engine
version, settings, timings and detected-pair identities/witness points.

## Why Stage 3 remains blocked

Four positive controls are missed despite complete geometry extraction. The
app exposes these **FALSE_NEGATIVE** results and does not turn zero findings
into a clash-free verdict. This release adds a diagnostic reference probe,
not production model clash validation. The UI model-check control is disabled.
The public geometry-check endpoint supports Stage 2 only: omitted later-stage
settings are disabled, and explicit attempts to enable clashes, connectivity,
alignment or dimensions are rejected before reading/extracting the model.
Internal legacy prototypes remain for development.

The 2 mm setting is an application screening choice, **not an industry-wide
acceptance limit**. These fixtures do not establish project compliance, design
intent, drawing completeness or performance on the office model. Existing
Stage 1 position/shape discrepancies remain unresolved. No new local Edge/GPU
or exhaustive office-model tessellation run was performed in this release.

Next: reproduce the aligned-face misses with an independent solid intersection
method, implement and verify a reliable correction, and rerun positive and
negative controls before releasing bounded MEP-versus-structure model scans.
Clearance, connectivity, alignment and dimension milestones remain deferred.

## Review correction and audit history

Only the previously identified test record is migrated automatically:

- IFC SHA-256: `f99b62ccadd9d625c64c4b68f89eda544ea8cac5986970d0a21473d9fcb3fd76`.
- Pair key: `duplicate_opening_candidate|66076|108748`.
- Current decision must be `confirmed_duplicate` with the exact known
  persistence-test note. A changed author review note or another model is
  left untouched.

The new decision is **Unresolved**. The note records the different hosts and
the previously measured lower-bound separation of 58.71 m between opening
#66076 and its explicitly related host #65997. That relationship needs review;
it does not establish duplicate intent.

The old status, note and review time remain in `review_history`, with an
archive time and reason. The issue has an expandable **Archived review history**
control after Stage 2 results load. QC JSON includes the entire model-specific
`duplicate_review_ledger`, even before rerunning duplicates. Editing a future
review retains its archived history. The migration is idempotent. If browser
storage refuses the write, the session still retains the repaired history and
offers JSON export; it does not discard the original disk record.

Reviewer confirmation rate describes saved judgements, not measured detection
accuracy. Unresolved candidates and unknown recall remain explicit.

## Release identity and verification

Backend measurements and viewer probes use v0.7.15 consistently. QC, Stage 1,
GPU and Stage 3 exports record the current exporter version. Old measured
versions and timestamps remain in their original provenance; exporting cached
evidence does not relabel it as a fresh measurement.

Verification in this environment: **107 Python regression tests passed**;
review-ledger, viewer selection, render batching and frontend interaction
suites passed. Tests assert that known kernel misses keep the Stage 3 gate
failed, preserve real IFC identities in detected pairs, verify reference
units/coordinates, prevent API gate bypass, exercise review migration and
storage failure, and verify version consistency. This regression success is
separate from the **failed 14/18 Stage 3 acceptance matrix**.

Repeat the probe:

```bash
python scripts/verify_hard_clash_reference.py stage3-reference.json
```

It deliberately exits **1** when reference acceptance fails, while saving the
full JSON. Regression commands are `python -m unittest discover -s tests -v`
and `npm test --prefix web` after dependencies are installed.

## Primary references

- [IfcOpenShell geometry tree documentation](https://docs.ifcopenshell.org/ifcopenshell-python/geometry_tree.html):
  API and protrusion/pierce semantics. The current page is 0.9 documentation;
  the evidence here records tests run on 0.8.5.
- [Upstream issue #4594](https://github.com/IfcOpenShell/IfcOpenShell/issues/4594):
  reports missed intersections when wall/slab faces align exactly. The observed
  fixture failure is consistent with this report; an exact root cause has not
  been established by this project.
- [Upstream issue #6109](https://github.com/IfcOpenShell/IfcOpenShell/issues/6109):
  reports another clash-testing example affected by slight geometric shifts.

The fixture source is `scripts/generate_hard_clash_fixture.py`; the independent
expected matrix is `ifcqc/hard_clash_acceptance.py`.
