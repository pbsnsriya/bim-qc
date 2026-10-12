# Portfolio Brief

## OpenBIM QC Assistant

**Problem:** BIM teams spend significant time finding missing or inconsistent
model information before coordination and handover.

**Solution:** A local-first web application that reads IFC files, creates a
model index, executes deterministic quality rules, and exports traceable issue
reports without sending project files to a third party.

## Demonstrated engineering skills

- IFC-SPF parsing and OpenBIM concepts
- Rule-oriented software architecture
- HTTP and JSON API design
- Accessible responsive frontend development
- File handling and defensive validation
- Automated testing with known clean and defective fixtures
- IfcOpenShell spatial geometry processing and clash detection
- Configurable engineering tolerances and conservative confidence reporting
- Privacy-conscious local processing

## Current result

Stage 1 now provides a formal IfcOpenShell geometry-foundation gate. It reports
schema and length units, represented/generated shape coverage, world-coordinate
bounds, STEP-id mapping, invalid geometry, vertices/triangles, processing time,
and element-level extraction failures. The synthetic demonstration model passes
with seven of seven represented products and 100% extraction coverage.

Duplicate geometry, duplicate tags, MEP-to-structure clashes, IFC-port
connectivity, off-axis placement, and minimum-dimension rules remain visible as
experimental prototypes. They unlock only after Stage 1 passes and will be
tested and refined one milestone at a time.

## Planned production evolution

- Pair highlighting and camera/snapshot BCF viewpoints
- Reference IFC/DWG drawing comparison
- IfcOpenShell IFC writeback with correction review
- Full IfcTester IDS result mapping
- Safe AI commands compiled to allow-listed operations
- PostgreSQL-backed projects and model revisions
