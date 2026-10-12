# OpenBIM Public QC Baseline v1

Prepared: 2026-10-03
Project: independent OpenBIM AI Quality & Mapping Assistant
Status: proposed acceptance profile; not a certification or a completed validation report.

This original checklist uses public references. It requires no employer information. Publishing a rule here does not mean it has been implemented or tested. All model-result rows begin as Not evaluated until a run supplies traceable evidence.

## Rule authority

- **Schema:** a requirement from the specific released IFC schema declared by the file. Record the entity, attribute, formal rule and release.
- **Guidance:** a published method for organizing quality review. It does not automatically supply a numerical tolerance.
- **Demo profile:** a requirement or threshold we explicitly choose for this independent demonstration. It must never be presented as a universal industry requirement.
- **Benchmark:** documented expected behavior of a test case; its scope is limited to that case.

## Public references

| Ref | Source | Use and boundary |
| --- | --- | --- |
| S1 | [IFC4 ADD2 TC1: IfcRoot](https://standards.buildingsmart.org/IFC/RELEASE/IFC4/ADD2_TC1/HTML/schema/ifckernel/lexical/ifcroot.htm) | GlobalId is required and has uniqueness rule UR1 for IfcRoot instances. Name is optional at this base entity; subtype rules may differ. Use the corresponding publication for other schema versions. |
| S2 | [Penn State BIM execution-plan template, guide v3.0, Appendix G](https://psu.pb.unizin.org/bimprojectexecutionplanning/back-matter/appendix-g-bim-project-execution-plan-template/) | Public planning framework with sections for quality control, model structure, information exchanges and deliverables. Our numerical rules below are not taken from this template. |
| S3 | [buildingSMART IFC specification models](https://github.com/buildingSMART/IFC4.x-specification-models) | Focused geometry/placement examples with documentation and automated checks. Informative examples, not a substitute for normative specifications. Development-schema examples must not be silently treated as released IFC4 examples. |
| S4 | [buildingSMART IDS documentation](https://github.com/buildingSMART/IDS/blob/development/Documentation/README.md) and [test-case guidance](https://github.com/buildingSMART/IDS/blob/development/Documentation/ImplementersDocumentation/TestCases/scripts.md) | IDS/IFC pairs provide documented behavioral tests for information checking. Pin the commit and supported IDS version before execution; exclude unsupported versions explicitly. |
| S5 | [buildingSMART IDS user manual](https://github.com/buildingSMART/IDS/blob/development/Documentation/UserManual/specifications.md) | Information requirements for entities, attributes, classifications, properties, materials and relationships; general geometry and drawing comparison require separate checking. |
| S6 | [UK BIM Framework ISO 19650 guidance, Part 2, Edition 5, September 2020](https://ukbimframework.org/wp-content/uploads/2020/09/Guidance-Part-2_Parties-teams-and-processes-for-the-delivery-phase-of-assets_Edition-5.pdf) | Sections discussing clauses 5.6.4, 5.6.5 and 5.7.2 link review to defined requirements, acceptance criteria and review procedures. This is guidance, not the ISO standard text or certification. |
| S7 | [buildingSMART IFC validation service](https://validate.buildingsmart.org/) | Separate IFC-conformance evidence. Record the report's actual rules and scope; an IFC validation result is not drawing, coordination or site approval. |

Additional checklist lead: [COBIM 2012, buildingSMART Finland](https://wiki.buildingsmart.fi/en/04_Julkaisut_ja_Standardit/YTV), Series 6 Quality assurance. Its publication listing was accessible; the complete QA PDF was not retrievable during this research. No detailed clause or threshold below is attributed to that unread PDF.

## Measurable checklist

Every row requires rule/version, applicability, expected value, actual value, reference, affected GlobalIds and STEP IDs, and verdict. Future milestones are retained for scope planning, not claimed as implemented.

| ID | Check | Authority | Proposed measurement and acceptance | Evidence needed / missing-reference behavior | Stage |
| --- | --- | --- | --- | --- | --- |
| QC-01 | IFC syntax and schema | Schema; S7 | Execute applicable schema and formal-rule validation. Report each violation and validator limitation separately. Parsing alone is insufficient. | Declared schema, validator/version and report; unsupported checks are Not evaluated. | Foundation |
| QC-02 | Identity | Schema; S1 | Check GlobalId presence, encoding and uniqueness across all IfcRoot instances, including relationships and property definitions. Do not require GlobalId on resource entities. | Offending instances and applicable schema rule. STEP IDs are file-local identifiers, not substitutes for GlobalIds. | Foundation |
| QC-03 | Length units | Geometry benchmark; S3; demo profile | Decode units and compare known fixtures in metres. Proposed fixture numerical tolerance: 1 mm, explicitly our profile choice. | Declared unit, scale, analytic dimension and measurement; missing project units need an explicit assumption or unresolved status. | Stage 1 |
| QC-04 | World placement | Geometry benchmark; S3; demo profile | Compare independently specified translation, rotation and nested placements. Measure positions as well as extents. | Expected transform and bounds in common coordinates. Extent-size agreement alone cannot pass this row. | Stage 1 |
| QC-05 | Geometry coverage | Demo profile | Account for every in-scope product as extracted, documented metadata/aggregate/void/curve case, or unresolved. For demonstration acceptance require no unresolved critical solids; aggregate percentage remains diagnostic. | Per-element representation category and outcome. Optional representation is not universally an IFC error. Define required solids in the profile. | Stage 1 |
| QC-06 | Openings and geometry shape | Geometry benchmark; S3; demo profile | Test net/gross geometry, mapped instances, curves, tessellations and cutouts. Record bounds, measured dimensions and appropriate volume or surface deviation. | Known analytic results or an independent reviewed reference. Curves and surfaces must not be judged by solid-volume rules. | Stage 1 |
| QC-07 | Engine discrepancy | Demo profile | Compare IDs, position and appropriate shape metrics in the same units/coordinates. Publish each discrepancy; agreement supports consistency but is not absolute truth. | Backend/browser versions and per-element evidence. Missing comparison is Not evaluated. | Stage 1 |
| QC-08 | Required names, types, properties and classifications | IDS mechanism; S4/S5; demo profile content | Apply a versioned sample IDS with explicit classes, cardinality and permitted values. Properties are mandatory only within that specification. | The exact IDS and pass/fail test expectations. No IDS means requirement compliance is Not evaluated. Revit Family is not a universal IFC requirement. | Semantic QC / IDS |
| QC-09 | Spatial containment and assigned storey | Applicable schema plus demo profile | Separate schema relationship validity from whether an element is assigned to the intended level. Use explicit exceptions for multistorey and aggregated elements. | For intended-level checking: expected schedule, reference model or documented assignment rule; otherwise Not evaluated. | Semantic QC |
| QC-10 | Exact and near duplicate candidates | Demo profile | Coincident copies should be detected; translated repeated components should not be rejected solely for identical shape. Include different-property duplicates and intentional-repeat controls. | Known injected pairs, expected IDs, geometry/placement tolerance and reviewer intent decision. Candidate detection alone cannot prove accidental duplication. | Stage 2 |
| QC-11 | Hard and clearance clashes | Demo profile; S2 coordination planning | Use exact intersection/distance with specified element sets, exclusions and approved demo tolerances. Test crossing, touching, separated and permitted-opening cases. | Ground-truth intersecting pair or explicit clearance rule. Missing clearance requirement is Not evaluated; broad-phase box overlap is only a candidate. | Future clash stage |
| QC-12 | Connections | Demo profile | Test explicit IFC ports/relationships and endpoints against a declared connection specification, including diameter and angle where required. | Known network, terminal exceptions and tolerance. Absent exported connectivity is unknown, not automatic proof of disconnection. | Future connection stage |
| QC-13 | Dimensions and alignment | Demo profile | Compare measured dimensions/axes/offsets against expected dimensions, grid, level or schedule with a versioned tolerance. | Missing expected value or reference is Not evaluated, even if geometry can be measured. | Future dimension/alignment stage |
| QC-14 | Missing elements versus reference | Demo profile | Align an explicit reference model/drawing; compare its labelled expected objects with model objects and measure false positives/negatives. | Reference revision, object correspondence, units and transformation; absent reference is Not evaluated. | Future drawing-comparison stage |
| QC-15 | Issue review and evidence | Guidance S2/S6; our implementation profile | Preserve pair/element IDs, rule source, measurements, screenshot/viewpoint, reviewer decision and rationale. Check exported issue IDs resolve to the exact model revision. | Review log and model fingerprint; unsupported export/review behavior is Not evaluated. | Across stages |
| QC-16 | Performance and completeness | Demo profile | Measure opening, tessellation, targeted retries, comparison, serialization and peak memory where supported. Record timeout as inconclusive. Compare versions only on the exact same bytes/settings/hardware. | SHA-256, size, schema, engine/app versions, platform, settings and timestamps. No speed guarantee or universal industry runtime limit. | Stage 1 |

## Verdicts

- **Pass:** specified applicable criterion was evaluated and satisfied.
- **Fail:** specified criterion was evaluated and violated; distinguish confirmed model defect from checker/extraction failure.
- **Needs review:** engine disagreement, ambiguous intent or unresolved representation.
- **Not evaluated:** missing required reference, unsupported validator/check, unimplemented check, or no run.
- **Not applicable:** justified exclusion with recorded reason.
- **Inconclusive:** interrupted, cancelled, timed-out or incomplete run.

Never combine these into a global industry-compliant label. Produce separate summaries for tool benchmarks, IFC conformance, demo-profile compliance and unresolved findings. Critical unresolved defects remain visible regardless of percentage coverage.

## Test corpus and factual reference

1. Retain original synthetic fixtures with analytic expected units, coordinates and dimensions. They are mathematical controls, not externally certified models.
2. Select published buildingSMART geometry examples compatible with the supported schema; pin source commit, file hash and each example's documented purpose. Their stated automated validation scope is not whole-project QA approval.
3. Run version-compatible official IDS/IFC test pairs and compare actual decisions with the documented expected outcomes. Report unsupported cases rather than silently skipping them.
4. Use the supplied NordicLCA IFCs as realistic performance and interoperability inputs. Do not call them approved or defect-free without accompanying reports. The earlier 81.36 MB evidence and current 63.66 MB office file are different byte sets; their historical runtimes are not a controlled speed comparison.
5. Generate our own positive/negative models containing labelled duplicate IDs, duplicate solids, intentional repeats, missing required properties, openings and changed placements. Keep a manifest of expected issue IDs and exceptions. Do not redistribute modified third-party samples unless their licence permits it.
6. For shape correctness and ambiguous errors, retain independent inspection/measurement evidence. Two parsers agreeing is corroboration, not design approval.

## Next milestone: only Stage 1

Implement this rule register and evidence statuses, strengthen placement/shape fixtures, inspect remaining extraction failures, and export a repeatable Stage 1 acceptance report. Run small factual controls before realistic large models. Proceed to Stage 2 after Stage 1 discrepancies have documented dispositions.

No third-party models have been downloaded or run as part of creating this checklist. No new application checks are claimed as implemented by this document.


## Implementation/evidence addendum — v0.7.9 (2026-10-03)

This addendum records prototype verification; all original public-reference authority boundaries remain in force.

| Checklist scope | Implemented evidence | Current office-model disposition |
| --- | --- | --- |
| QC-03 units | Explicit unit and positive scale; an assumed unit is Not evaluated | Measured; see per-run JSON |
| QC-04 placement | Actual transformed vertices, inverse web-ifc recentering, signed Y-up/Z-up conversion and 1 mm world-bound comparison | Compared bounds pass at 128 circle segments; three required placement references are absent |
| QC-05 coverage | Each failed representation listed; leaf IfcElement with no own representation or aggregate/nested children is conservatively unresolved under this demo scope. Spatial/annotation/metadata products are not treated as required standalone solids. Coverage is diagnostic; no unresolved critical geometry allowed for readiness | 8,780/8,783 generated; three confirmed placement defects plus six leaf physical representations need review. Aggregate coverage cannot pass this gate |
| QC-06 shape | Known host opening, cylinder, mapped instances and nested placements; per-element area/volume diagnostics | 21 cross-engine metric outliers require investigation. Complete surface correspondence/manifold checks remain Not evaluated |
| QC-07 engine evidence | IDs, world bounds, shape metrics, versions, settings and exact file SHA-256; independent WASM controls | All nine renderable fixtures pass. Office-model strict agreement remains FAIL; see discrepancy IDs |
| QC-01, QC-13, QC-14, project acceptance | Explicit Not evaluated rows when complete validators or expected references are absent | Not evaluated |

Chosen profile: world-bound tolerance 0.001 m; shape tolerance = 0.001 m²/m³ + 0.5% of backend value. These values are demo decisions, not tolerances extracted from ISO 19650, buildingSMART or a BIM firm. Numerical agreement is supportive evidence, not universal factual truth.

The measured file is 61,308,928 bytes, SHA-256 `80f2a8fa581e490120e7719b136ccbf057e222f97c6389ec043ab32ef85fca2a`. Archived v0.7.8 completes this file in 372.12 seconds here; this does not confirm earlier differently sized files or Windows/GPU behavior. See `docs/Stage1_Verification_v0.7.9.md` in the project archive and `docs/evidence/office-stage1.json`. Desktop-viewer inspection and the user's physical GPU check remain Not evaluated.
