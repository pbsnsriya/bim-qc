# Stage 2 pair comparison — v0.7.11

## Use

1. Extract this release into a new folder. Stop the old server and run
   `start_windows.bat`. Confirm **v0.7.11** in the page header.
2. Upload the IFC, complete the existing Stage 1 evidence gate, and run
   **Validate exact duplicates**.
3. Click a duplicate issue card. Both selection targets are highlighted and
   **Compare #A ↔ #B** opens under that card. Alternatively open the Compare
   disclosure directly to inspect the information without changing selection.
4. Physical/property differences are amber; identity differences are blue;
   missing fields display **Missing value** or **Not evaluated**. Expand
   **Source properties and quantities** for the detailed values.
5. Record your own **Decision** and **Reviewer note**. Reading the comparison
   does not change either field. Filter changes and saving the review preserve
   the comparison result in the page. Clear selection still restores the viewer.

## Supplied-model acceptance cases

Model SHA-256:
`f99b62ccadd9d625c64c4b68f89eda544ea8cac5986970d0a21473d9fcb3fd76`

| Pair | Expected panel result | Review decision |
|---|---|---|
| #63877 ↔ #106773 | PI-1 versus PI-2: one differing physical summary field; three differing Reference properties. Dimensions 400/400/3130 mm, position, material names, storey and load-bearing status match. PI-1 also lacks the Slope value present on PI-2. | Unresolved |
| #63912 ↔ #106808 | Zero differing physical summary fields and zero differing property values. Same dimensions and position; matching PI-2 type names and type tag. GlobalIds, occurrence Tags and type record IDs differ. | Unresolved |

Both pairs lack exported phase/status and assembly-parent information; these
rows are **Not evaluated**, never shown as passing. The supplied model is not
included in the distribution.

The independent source-profile review confirmed the coincident solids. The
comparison panel itself measures bounds and reads properties; it does not
perform a new analytic solid-equivalence proof or determine author intent.

## Measurement rules and limits

- Dimensions are total geometry bounds along occurrence placement axes,
  normalized to millimetres. They are not nominal width/diameter parameters.
- Position is the world bounds centre, in IFC Z-up metres, not the placement
  origin or browser-recentred coordinate.
- Dimension equality uses 0.001 mm absolute numerical tolerance; position uses
  0.000001 m. Numerical comparisons also allow a 1e-9 relative difference.
  These are diagnostic matching rules, not construction acceptance standards.
- Source property numbers use 1e-9 absolute/relative comparison. Different or
  absent values are review evidence, not automatic project failures.
- IFC source quantity/property units are retained. A model length scale of
  0.001 converts raw model lengths to metres; area/volume units can differ.
- Material names are compared. Layer order/thickness, constituent fractions,
  material usage offsets and representation topology are not compared here.
- Missing geometry/placement is explicitly unavailable/not evaluated. Matching
  dimensions alone do not establish matching full geometry.
- Occurrence and type properties are separate; property-set record IDs are
  excluded. At most 500 property rows are displayed, with an explicit notice
  if additional rows exist. The summary considers all extracted property rows.
- The comparison API accepts exactly two distinct positive IFC element IDs and
  returns the source fingerprint. The frontend rejects mismatched fingerprints.
- Large model parsing and complex individual geometry can take time. Cached
  pair results avoid repeating that work during review; the loaded IFC model
  itself is not retained in a new server memory cache.

## Verification

- Automated Python tests cover coincident versus shifted geometry, identity
  separation, type/property differences, false boolean values, millimetre
  units, rotated occurrence axes, extraction failure and invalid IDs.
- API integration checks that a stored model comparison returns the matching
  model fingerprint and requested elements.
- Frontend DOM integration checks automatic panel opening, side-by-side fields,
  pair highlighting, explicit unknowns, unchanged decisions, retry after an
  injected API failure and cached comparison survival after review saving.
- The supplied 77.59 MiB model's two column pairs were checked directly using
  the new comparison service and against the rendered table rows.
- Existing viewer/render-batch tests exercise selection, picking, pair
  highlighting and context restoration.

This release has automated DOM and geometry/API verification. It has not been
visually verified in a real GPU browser here; repeat the two-pair check on the
user's laptop before considering the user-facing increment accepted.
