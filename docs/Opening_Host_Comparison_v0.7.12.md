# Opening host comparison — v0.7.12

This increment adds host context to Stage 2 opening-pair review. It does not
decide whether coincident openings or their hosts are accidental duplicates.

## Run and locate the control

1. Stop the previous local server, extract this release and start it using
   `start_windows.bat`, or install the project and run `python server.py`.
2. Refresh the browser (Ctrl+F5), and confirm the header says **v0.7.12**.
3. Upload the same IFC and complete its Stage 1 readiness prerequisites.
   Completed evidence can be reused only within the same running server session;
   restarting this release requires a new validation session.
4. Run **Validate exact duplicates**, and open the opening candidate's
   **Compare #A ↔ #B** disclosure under its issue card.
5. Check the **Host element (IfcRelVoidsElement)** row. Click **Highlight hosts**
   below the table to select and frame the host elements together.
6. Use the existing X-ray, fade or isolate modes; then **Clear selection**.
   Decisions and reviewer notes remain unchanged.

## Expected result on the supplied office model

Source: `01-ARK_NordicLCA_Office_Timber_As-Built_Revit.ifc`, 81,357,305 bytes.

SHA-256: `f99b62ccadd9d625c64c4b68f89eda544ea8cac5986970d0a21473d9fcb3fd76`.

| Opening | Host element | Host name | Host type |
| --- | --- | --- | --- |
| #66095 | IfcWall #65997 | Basic Wall:KS-2:1347201 | KS-2 |
| #108767 | IfcWall #108613 | Basic Wall:KS-1:1493966 | KS-1 |

The two hosts differ. This is contextual information, not an additional physical
failure or an automatic intentional-overlap verdict. The opening pair retains
0 physical differences and 0 property value differences. Phase/status and
assembly remain 2 unknown physical fields. The absent type, material and
load-bearing fields now account for 3 **Not applicable** physical fields rather
than unknowns. Absent type record ID and type Tag are also marked Not applicable
in the identity section.

The supplied column regressions remain:

| Pair | Physical differences | Property value differences | Unknown physical fields |
| --- | ---: | ---: | ---: |
| #63877 / #106773 | 1 | 3 | 2 |
| #63912 / #106808 | 0 | 0 | 2 |

## Relationship and missing-data semantics

Host context is read from `IfcOpeningElement.VoidsElements` and
`IfcRelVoidsElement.RelatingBuildingElement`, following the buildingSMART
[IFC4 opening definition](https://standards.buildingsmart.org/IFC/RELEASE/IFC4/FINAL/HTML/schema/ifcproductextension/lexical/ifcopeningelement.htm).
An opening represents a void within a physical element, not another solid wall.
The code supports IFC2x3 and IFC4 inverse relationship access.

- Host metadata comes from the related element; no name/proximity inference.
- Host context is not included in physical or property difference counts.
- Missing host relationships are explicitly Not evaluated, independently of
  those counts. An absent relationship does not prove why it is absent.
- If only one host is supplied, that host can be selected; the other remains
  unknown. If neither is supplied, Highlight hosts is disabled.
- Shared host IDs are selected once. Host aggregate selection uses the existing
  geometric-child mapping where applicable.
- Not applicable refers only to absent type/material/load-bearing metadata on
  opening voids. Exported values are shown, and physical elements are unchanged.
- Viewer selection failure, partial selection and unresolved Stage 1 host
  geometry are disclosed. No new host tessellation is triggered by the button.
- Geometrical coincidence, identical bounds or different hosts do not establish
  author intent; manual review remains necessary.

## Verification boundary

Backend tests cover distinct/shared/missing hosts, IFC2x3 relationships,
host type metadata, applicability and physical-element regressions. HTTP tests
cover the stored-model comparison and its matching fingerprint.

Frontend integration uploads the known opening fixture, runs Stage 1 and Stage 2,
opens the live API comparison and verifies selection of the host IDs, data-map
sync, clear/reset, unavailable/partial geometry messages, and unchanged decisions
and notes. These tests use a viewer stub; actual WebGL rendering is not certified
by the integration suite. Existing geometry selection and batching tests are
also run.

The supplied office model was independently parsed and its opening host pair
and two column comparison regressions verified with IfcOpenShell 0.8.5.
The next local acceptance check is whether both wall hosts visibly highlight
and frame on the user's browser. Near-duplicate tolerances are a later increment.
