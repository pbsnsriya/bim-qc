# Roadmap

Work proceeds one milestone at a time, with analytic controls, model-specific evidence and human review recorded separately.

| Milestone | Current state | Next acceptance work |
| --- | --- | --- |
| Stage 1 geometry foundation | Implemented; per-model discrepancies can remain | Explain every readiness blocker and investigate extraction/position/shape disagreements without hiding critical geometry |
| Stage 2 duplicate candidates | Exact and translation-only near candidates, pair comparisons and review ledger implemented | Broader independent truth cases; intentional-repeat rule configuration; independently log missed cases before claiming recall |
| Stage 3 hard clashes | 30-control reference gate and bounded MEP/structure pilot implemented | Verify local browser highlighting; review selected real-model subsets; extend complex depth handling and establish scaling/performance evidence |
| Clearance checks | Experimental internal prototype only | Define rule-specific clearances, controls, exclusions and selected-scope evidence before release |
| Improper connections | Experimental internal prototype only | Validate exported IFC ports/relationships and disclose absent connection data |
| Alignment/dimensions | Experimental internal prototypes only | Supply measurable reference axes/dimensions and project tolerances before compliance verdicts |
| Drawing/reference completeness | Planned | Begin with reference IFC or structured DWG, explicit units/coordinates/layer mapping and reviewed truth cases |
| Complete IDS validation | Planned | Integrate full IfcTester facets and restrictions with traceable results; keep unsupported rules Not evaluated |
| Corrections and versions | Planned | Preview proposed changes, approve individual operations, write corrected IFC and save before/after models |
| AI-assisted workflows | Planned | Structured, allow-listed commands over existing measured data; AI explains findings and suggests edits while deterministic geometry decides numerical results |

## Possible production stack

React/TypeScript and That Open Components/Fragments can be evaluated for frontend evolution; FastAPI for typed APIs/background job integration; PostgreSQL for projects, issues and model revisions; Pandas/openpyxl for Excel reports; Docker for reproducible deployment. These are proposals, not features present in v0.7.16.

RVT import and zero-loss conversion are not supported by this IFC-focused application. Any future authoring-format integration needs its own conversion and data-retention evidence.
