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

Stage 1 now provides a formal geometry-extraction evidence gate. Six synthetic
IFC fixtures provide analytically predetermined units, placements, bounds,
schema behavior, large-coordinate warnings, and expected rejection outcomes.
IfcOpenShell and browser web-ifc independently measure the uploaded model's
element IDs and extents and must agree within 1 mm. The downloadable evidence
report records the complete matrix, tolerances, engine measurements, and claim
boundary. The demonstration model passes with seven of seven represented
products and 100% extraction coverage.

The claim is intentionally limited to extraction consistency. Agreement with
approved drawings, schedules, survey control, design intent, or site reality
requires a future externally referenced validation stage.

The application now uses IfcOpenShell schema traversal for production semantic
QC instead of inferring IFC attributes from raw STEP argument positions. Only
IfcRoot objects participate in GlobalId checks, physical elements receive
element-quality rules, aggregate parents resolve to geometric children, and
subtractive openings resolve to their host. The local upload path accepts IFC
files up to 100 MiB and caps DOM rendering to 250 issue rows while retaining all
findings for filtering and export. It has been exercised with models around
77–78 MiB, including an 809,333-entity IFC.

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
