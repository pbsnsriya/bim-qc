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
- Privacy-conscious local processing

## Current result

The third milestone adds bidirectional element selection: clicking a QC issue
highlights and frames its IFC geometry, while clicking model geometry identifies
the corresponding element and issue. The offline viewer includes three
selectable QC profiles and detects duplicate GlobalIds, missing element
names, missing spatial containment, absent type assignments, and absent
classification associations, then exports traceable JSON or CSV findings. The
included synthetic building produces five verified mesh groups and a
reproducible set of known findings.

## Planned production evolution

- IfcOpenShell parsing and IFC writeback
- IDS-defined requirements
- BCF issue export
- Safe AI commands compiled to allow-listed operations
- PostgreSQL-backed projects and model revisions
