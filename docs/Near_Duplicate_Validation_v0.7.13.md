# Near-duplicate validation — v0.7.13

## Status

Implementation and automated verification completed. All 88 Python tests passed,
including the stored-model HTTP tests and new near-duplicate cases. JavaScript
syntax checks and all frontend/viewer/batching tests passed. Frontend integration
uses a viewer stub with real backend geometry and API calls: actual local GPU
rendering still needs the user acceptance checks below.

## Start with the supplied small model

1. Stop the old server, extract the update and start it. Refresh with Ctrl+F5;
   confirm **v0.7.13**. Use the same browser/address to retain local review history.
2. Upload `samples/golden/duplicate_near_matrix.ifc` from the extracted project.
3. Run Stage 1 geometry validation and wait for Stage 2 readiness.
4. Leave **Include near-duplicates** checked, set **Placement tolerance (mm)**
   to **5**, and click **Validate duplicates**.
5. Expect **1 exact physical pair, 4 near physical pairs and 0 exact opening
   pairs**. The independent near reference matrix should show **12/12**.
6. Click a Near duplicate candidate: both elements should highlight and frame.
   Its evidence shows measured ΔX/ΔY/ΔZ, centre distance, applied tolerance and
   surface residual. Compare shows matching dimensions and different position.
7. Record a test decision and note. Set the tolerance to **1 mm**, rerun and
   expect **0 near pairs**, retaining the exact pair. Restore **5 mm** and rerun:
   the saved decision/note should return.
8. Uncheck near-duplicates and rerun: only exact/opening checks remain active.
9. Export JSON and truth-matrix CSV, retaining measured offsets and tolerance.
   Clear selection should restore the viewer.

The 5 mm result has two 2 mm pairs around an original and its exact copy, one
independent 5 mm boundary pair, and one 2 mm pair with different properties.
The 5.001 mm pair is outside that setting. At 6 mm it becomes an additional
candidate. Configured tolerances alter expected reference outcomes explicitly.

## What establishes the result

Known offsets of 0, 2, 5, 5.001 and 1000 mm are specified in the fixture generator
independently of the detector. Exclusions cover different IFC class, different
dimensions, rotated asymmetric geometry, opening voids, spaced repeats, and
different triangular surfaces with identical bounds. A complete expected pair
set is checked to expose extra findings.

The algorithm uses:

- Same exact IFC class, with subtraction features excluded.
- World geometry normalised to metres by IfcOpenShell.
- Adjacent spatial cells, covering negative coordinates and cell boundaries.
- Euclidean distance between world bounds centres; per-axis tolerance alone
  cannot admit a pair beyond the radial limit.
- Triangle-coordinate fingerprint after removing each centre's translation.
  Fingerprints are followed by actual corresponding vertex residual measurement.
- Surface residual at most **0.001 mm**, distinct from the placement threshold.
- A **0.000001 mm** floating-point slack in the placement boundary comparison.
- Exact pairs and offsets at or below the numerical shape threshold are
  excluded from near results; exact duplicate review remains separate.

Triangle numeric arrays are copied while the IfcOpenShell iterator is alive;
iterator-owned geometry handles are not retained for later surface comparison.
Normalised mesh arrays are created only for fingerprinting/comparison and are
not cached for every element. There is no second tessellation pass for near
checks within a geometry request.

## Limits and incomplete results

This increment matches translation-equivalent tessellated surfaces. It does not
perform rotation alignment, mirror matching, or full analytic/B-rep equality.
Different triangulations or coordinates across a quantisation boundary can
produce false negatives, so absence of a candidate does not establish model
correctness. Same-class matching surfaces can still be intentionally repeated.

The placement range is **0.01–100 mm**. The initial 5 mm is a review setting,
not an industry or project acceptance standard. Review decisions remain manual.

At most 250,000 nearby pair comparisons and 5,000 candidates are processed.
Reaching a limit marks the scan **INCOMPLETE** in the UI and exported JSON.
Geometry unavailable for represented elements is also disclosed. A reference
matrix pass establishes those synthetic cases, independently of scan coverage
or project compliance.

The supplied 77.59 MiB office model has not yet completed a dedicated full-model
near-duplicate performance/coverage test for this release. Start with the small
fixture above before that larger test.
