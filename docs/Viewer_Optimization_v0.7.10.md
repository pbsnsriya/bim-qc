# Viewer optimization v0.7.10

## Change

Batch opaque source meshes by exact RGBA material and spatial cell (largest
model extent divided by six). Split at 100,000 vertices, allowing an oversized
individual source part to remain whole. Keep transparent source parts separate
for camera sorting and preserve their original two-pass rendering. Reuse
materials and repeated geometry IDs. Preserve every triangle and map hit
triangles back to their original IFC STEP IDs.

Selection overlays use original geometry with cloned highlight materials, so
selecting one element cannot recolour its batch neighbours. Remove selected
triangles from context using a reusable index buffer. Isolation hides context;
fade uses faint shared context materials. Clear selection restores the original
indices, appearance and visibility. Picking explicitly excludes hidden context.

Render on camera/control changes, resize, selection and WebGL restoration.
During the GPU probe, continuously render and count actual rendered frames.
The probe does not count idle animation callbacks as rendered frames.

Add Frame model and standalone Export GPU evidence. Include viewer version,
render batches, draw calls, selection mode, selected IDs and camera position in
the exported GPU evidence. Backend geometry measurements and tolerances remain
independent of render batching.

## Automated verification

- 60 Python backend tests pass, including the known-answer geometry matrix.
- Viewer selection, batching and frontend interaction suites pass.
- Picking preserves IDs for several objects inside one batch.
- Pair highlights do not alter unselected materials.
- X-ray exclusion, isolate, fade and repeated clear/restore transitions pass.
- A stable index buffer is reused across selection transitions.
- Mirrored, rotated and nonuniformly scaled positions and face normals pass.
- Transparent parts remain separate; material/spatial/vertex limits are checked.
- Standalone GPU export is verified before backend Stage 1 validation.
- CPU/WASM checks on the supplied golden IFC fixtures verify every triangle
  index, IFC owner and transformed display vertex.

## Larger-model CPU/WASM check

File: 01-ARK_NordicLCA_Office_Timber_As-Built_Revit.ifc, **61,308,928 bytes
(58.47 MiB)**, SHA-256
`80f2a8fa581e490120e7719b136ccbf057e222f97c6389ec043ab32ef85fca2a`.
This is a different model export from the user's current 77.59 MiB timber IFC.

| Measurement | Result |
| --- | --- |
| Source mesh parts | 13,962 |
| Render batches | 1,443 (401 opaque; 1,042 transparent) |
| Shared materials | 38 |
| Calculated all-visible source draw calls | 15,004 |
| Calculated all-visible batched draw calls | 2,485 |
| Calculated draw-call reduction | 83.4% |
| Preserved triangles | 1,706,697 |
| Verified display vertices | 4,194,666 |
| Verified triangle indices | 5,120,091 |
| Largest additional Float32 display-position difference | 0.000004659 m (0.00466 mm) |

Raw results: `evidence/render-batching-office-v0.7.10.json` and
`evidence/render-batching-fixtures-v0.7.10.json`. The vertex comparison threshold
is 0.1 mm for this render-only regression check, not a project acceptance rule.
web-ifc reports pre-existing placement errors on this older export; passing this
check means preservation of its extracted geometry, not approval of the model.

Draw-call totals above are calculated with all model batches visible and the
original transparent double-sided material behavior. They exclude grid/selection
helpers and do not account for camera culling. They are not measured GPU FPS.

## Remaining local verification

A real WebGL browser run was not completed in the execution environment because
the browser executable was unavailable and its download failed. Automated
frontend tests use JSDOM and a viewer bridge stub; batching/picking tests use
actual Three.js geometry and Raycaster without a GPU. No RTX FPS pass is claimed.

1. Close the old server, extract this build into a fresh folder and run
   `start_windows.bat`. Confirm the header says v0.7.10; refresh the browser.
2. Load the **81,357,305-byte (77.59 MiB)** timber IFC with SHA-256
   `f99b62ccadd9d625c64c4b68f89eda544ea8cac5986970d0a21473d9fcb3fd76`.
3. Click Frame model to clear selection and frame the whole model.
4. Keep the tab visible; run the browser/GPU check and export GPU evidence.
   Confirm RTX 5060, source hash, zero selected IDs, loaded counts and batches.
5. Compare against the v0.7.9 full-model probe: 5.9 FPS, 21,238 draw calls in
   that frame. Camera/culling and selection affected the previous run, so the
   original frame is not a strictly controlled performance baseline.
6. Exercise orbit/pan/zoom, direct picking, issue selection, pair highlighting,
   x-ray/fade/isolate, clear selection and resize. Check transparent surfaces.

Backend extraction performance, six world-bounds discrepancies and 122 shape
metric discrepancies from the user's evidence remain unresolved. No clearance,
clash or project-compliance acceptance is implied by this viewer change.

Three.js references: [BufferGeometry](https://threejs.org/docs/pages/BufferGeometry.html),
[Raycaster](https://threejs.org/docs/pages/Raycaster.html),
[Material](https://threejs.org/docs/pages/Material.html).
