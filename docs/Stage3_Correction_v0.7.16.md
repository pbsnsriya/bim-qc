# Stage 3 aligned-overlap correction — v0.7.16

## Result and scope

The four reproduced aligned-overlap misses are corrected for the constructed
reference cases. All **30/30** expected volume, threshold and supported-depth
controls pass with IfcOpenShell **0.8.5** and Manifold **3.5.1**. The original
kernel still passes only **14/18** original controls and remains visible in
the factual matrix. This is a correction in this application's intersection
pipeline, not a claim that the upstream IfcOpenShell kernel was patched.

A bounded MEP-versus-structure pilot is available after the reference gate and
browser extraction readiness pass. It supports at most **100 eligible elements**,
**200,000 extracted triangles** and **2,500 retained pair tests**. Whole large
models are rejected before body tessellation; an explicit list of valid STEP
IDs narrows the evaluation. These are pilot resource limits, not an increased
capacity claim for full-model clash scans. IFC upload capacity remains 100 MiB.

## How to verify locally

1. Stop the old server, extract this version into a new folder, and run
   `start_windows.bat`. Its installation step adds the pinned `manifold3d`
   dependency. Refresh Edge using Ctrl+F5 and confirm v0.7.16.
2. Load any model to show the dashboard, then use **Load hard-clash sample**.
   This replaces the current model with `hard_clash_pilot.ifc`.
3. Click **Verify extraction evidence**, then **Validate Stage 3 reference
   cases**. Expected reference result: **30/30**, with original kernel baseline
   **14/18**. The reference probe evaluates its own small IFCs, not this model.
4. Leave the pilot threshold at **2 mm** and the STEP-ID field blank. Click
   **Validate hard clashes (pilot)**. Expected: **five candidates**, **one
   unresolved complex intersection**, **zero missing/rejected bodies**. Its
   overall scope remains **needs attention**, because complex depth is unknown.
5. Click the 250 mm and 3 mm findings. Each should select both the duct and
   wall. Check isolate/fade and clear selection, then export the QC JSON.
6. Enter **20, 32** in STEP IDs and rerun. This original 250 mm overlap pair
   should report **one candidate**, no unresolved intersections, and an
   evaluated **explicit subset only**. Other model elements are not checked.
7. For the office model, select valid MEP and structural IDs and use that field.
   The existing column duplicate pairs contain no MEP member and cannot by
   themselves test the MEP-versus-structure pilot.

Passing the reference gate does not resolve the office model's existing Stage 1
position/shape discrepancies. No new exhaustive office-model tessellation or
real local Edge/GPU test was performed here. Frontend tests use a simulated
viewer mapping; this local visual check remains necessary.

## Measured algorithm and factual limits

IfcOpenShell extracts world-coordinate **Body** meshes with opening subtraction
enabled. Arrays are copied while their owning shape is alive. Manifold accepts
only finite, validly indexed, positive-volume solid inputs. Rejected inputs stay
visible; they are not repaired, reoriented or replaced with convex hulls.

For each MEP/structural pair, bounds are used only to exclude separated pairs.
Retained pairs undergo a **solid Boolean intersection**, including coincident
faces. Volume is measured from that result. Face, edge and vertex touching have
no positive-volume intersection. Actual IFC openings and disconnected wall
components are evaluated as solids; their combined bounds never prove a clash.

Coordinates are represented with float64. Each body is centred locally and
the second body is translated into the first body's coordinate frame for the
calculation; relative positions are preserved. This numerical re-expression
does not perturb geometry to make a clash detectable. Full world-coordinate
intersection bounds are restored for evidence.

Threshold depth is evaluated only for sufficiently small convex polyhedra.
Convexity requires every vertex to lie behind every outward face plane; holes,
concavities and disconnected components do not silently become convex hulls.
The separating-axis set comprises face normals from both meshes and nonparallel
edge cross products. For each unit axis the two translations to contact are
`max(A)-min(B)` and `max(B)-min(A)`. The least positive distance across the
complete tested axis set is the relative minimum translation to boundary
contact. Containment therefore uses the exit distance, not merely the length
of the overlapping projected intervals.

This metric differs from IfcOpenShell's old protrusion/pierce distance:

| Control | Intersection volume | Minimum translation | Original kernel distance |
|---|---:|---:|---:|
| Aligned 250 mm overlap | 0.25 m³ | 250 mm | No candidate |
| Aligned 3 mm overlap | 0.003 m³ | 3 mm | No candidate |
| Contained 0.5 m cube in unit cube | 0.125 m³ | 750 mm | 250 mm |
| Identical unit boxes | 1 m³ | 1000 mm | Not in original baseline |
| Duct intersecting disconnected wall components | 0.004 m³ | Not evaluated | Not in original baseline |

Non-convex inputs, inputs with more than **512 triangular faces**, or feature
combinations exceeding the **10,000-axis budget** do not receive an invented
depth. Positive intersections remain visible as `hard_clash_depth_unresolved`
and prevent an evaluated complete-scope status. No candidates with unsupported
depth are presented as clear. Manifold acceptance checks do not certify all
possible geometric self-intersections or original curved-CAD equivalence.

The threshold comparison is strictly greater than the selected value plus
**0.000001 mm** numerical slack. The solid-volume evaluation floor is
**1e-15 m³**; nonzero intersections below that floor remain Not evaluated.
The factual matrix compares volume at **1e-8 m³ absolute tolerance** and
minimum translation at **0.0001 mm absolute tolerance**, including million-metre
world coordinates. Expected values are analytic facts from specified geometry,
not previous engine output. The defaults are application choices, not mandated
industry tolerances or project acceptance criteria.

The 30 controls include the original nine and six additions in both IFC unit
variants: rotated overlap, large-coordinate overlap, identical solids, unknown
non-convex depth, edge touching and vertex touching. A passing unknown-depth
control means the correct limitation was reported; it does not mean its depth
has been validated. The compact viewer pilot excludes the million-metre case
to avoid testing unrelated GPU precision at the same time.

## Evidence and checks

- `docs/evidence/hard-clash-reference-v0.7.16.json`: 30 controls, expected and
  measured volumes/depths, original kernel baseline, engine versions, source
  hashes, settings, timings and per-pair measurements.
- `docs/evidence/hard-clash-pilot-v0.7.16.json`: compact pilot results at 2 mm.
- `samples/golden/hard_clash_matrix.ifc` and `_millimetre.ifc`: current controls.
- `samples/golden/hard_clash_pilot.ifc`: compact viewer sample.
- `samples/golden/archive-v0715/`: exact old fixtures, preserving the hashes
  in historical v0.7.15 evidence after expanding the current matrix.

**118 Python regression tests passed**, and the review-ledger, viewer,
render-batching and frontend suites passed. New checks include actual solid
volumes, containment depth, arbitrary rotations, input-order reversal, reported
separation-vector verification, touching/gaps, large coordinates, non-convex
limitations, rejected geometry, pre-tessellation capacity rejection, server
gate enforcement, model fingerprint agreement, pilot pair highlighting, scope
changes and JSON export. Regression tests and reference acceptance are distinct.

Repeat reference export using:

```bash
python scripts/verify_hard_clash_reference.py stage3-reference.json
```

No clearance, connectivity, alignment, dimension or drawing-comparison stages
are activated. Pilot findings do not establish coordination intent, compliance
or a clash-free whole project. Next validation is the local sample interaction
check, followed by reviewed MEP/structure subsets and complex-depth handling.

## Primary references

- [Manifold technical description](https://github.com/elalish/manifold/wiki/Manifold-Library):
  solid booleans, manifold topology and coincident-face treatment.
- [Manifold Python bindings](https://github.com/elalish/manifold/blob/master/bindings/python/manifold3d.cpp):
  mesh input and intersection/volume API. This project runs pinned 3.5.1; the
  linked branch can change.
- [Bullet convex contact API](https://pybullet.org/Bullet/BulletFull/structbtPolyhedralContactClipping.html):
  separating-axis use for convex polyhedra. This project's SAT code is original;
  verification includes independent Boolean separation checks.
- [IfcOpenShell issue #4594](https://github.com/IfcOpenShell/IfcOpenShell/issues/4594)
  and [issue #6109](https://github.com/IfcOpenShell/IfcOpenShell/issues/6109):
  related upstream reports; the original engine is retained for comparison.
