"""Independent, analytic expectations for the diagnostic Stage 3 kernel probe.

Expected answers come from specified box coordinates and the explicit opening,
not from a previous kernel result. A failed positive case blocks advancement.
"""
from datetime import datetime, timezone
from pathlib import Path

from .hard_clashes import run_hard_clashes_file
from .legacy_hard_clash_probe import run_hard_clashes_file as run_legacy_probe
from .version import APP_VERSION

# Label, intersection volume m³, expected candidate above the 2 mm threshold,
# analytic explanation. Volume is a reference fact, NOT a measured output.
CONTROLS = (
    ("Overlap 250 mm", .25, True, "Two unit boxes overlap 0.25 m along X and 1 m along Y/Z; coplanar faces must not hide the intersection."),
    ("Separated 100 mm", 0., False, "Unit boxes are separated by 0.1 m along X."),
    ("Touching", 0., False, "Shared face only; no positive-volume intersection."),
    ("Below threshold 1 mm", .001, False, "1 mm overlap is below the application screening threshold."),
    ("Boundary 2 mm", .002, False, "Exactly 2 mm is excluded by the explicit strict-greater-than policy."),
    ("Above threshold 3 mm", .003, True, "3 mm overlap exceeds the threshold; faces align along Y/Z."),
    ("Contained box", .125, True, "A 0.5 m cube is wholly inside a unit cube, 0.25 m from each host face."),
    ("Through opening", 0., False, "The duct passes through the explicitly subtracted opening with 0.1 m clearance on X/Z."),
    ("Bounds overlap only", 0., False, "The duct sits between two disjoint wall solids. Overlapping combined bounds do not imply contact."),
    ("Rotated overlap 250 mm", .25, True, "Both boxes and their offset are rotated 45 degrees; overlap remains 0.25 m³ and minimum translation 250 mm."),
    ("Large-coordinate overlap 3 mm", .003, True, "Boxes at million-metre world coordinates overlap 3 mm; shared local calculation avoids float32 loss."),
    ("Identical boxes", 1., True, "Identical unit cubes intersect by 1 m³ and require 1000 mm translation to boundary contact."),
    ("Non-convex intersection depth unknown", .004, None, "A duct overlaps one of two disconnected wall solids by 0.004 m³; convex threshold depth must remain Not evaluated."),
    ("Edge touching", 0., False, "Shared edge only; no positive-volume intersection."),
    ("Vertex touching", 0., False, "Shared vertex only; no positive-volume intersection."),
)

EXPECTED_TRANSLATION_MM={"Overlap 250 mm":250.,"Below threshold 1 mm":1.,"Boundary 2 mm":2.,
    "Above threshold 3 mm":3.,"Contained box":750.,"Rotated overlap 250 mm":250.,
    "Large-coordinate overlap 3 mm":3.,"Identical boxes":1000.}


def run_hard_clash_acceptance(samples):
    import ifcopenshell
    cases, fixtures = [], []
    baseline_passed=0
    for suffix, unit in [("", "metre"), ("_millimetre", "millimetre")]:
        path = Path(samples) / "golden" / f"hard_clash_matrix{suffix}.ifc"
        report = run_hard_clashes_file(path, tolerance_mm=2.)
        model=ifcopenshell.open(str(path))
        original_names={item[0] for item in CONTROLS[:9]}
        original_ids=[e.id() for e in model.by_type('IfcProduct') if e.Name in original_names or e.Name in {'Host: '+n for n in original_names}]
        baseline=run_legacy_probe(path,tolerance_mm=2.,element_ids=original_ids)
        baseline_names={issue['name'] for issue in baseline['issues']}
        baseline_passed+=sum((name in baseline_names)==expected for name,_,expected,_ in CONTROLS[:9])
        fixtures.append({"filename": path.name, "source_sha256": report["source_sha256"],
                         "probe": report,"original_kernel_probe":baseline})
        measured={item['name']:item for item in report['pair_measurements']}
        for name, volume, expected, explanation in CONTROLS:
            measurement=measured.get(name,{"intersection_volume_m3":0.,"threshold_status":"not_applicable"})
            geometry_complete=report['extraction_complete_for_selected_scope']
            detected=measurement['threshold_status']=='exceeds_threshold'
            expected_status='not_evaluated' if expected is None else 'exceeds_threshold' if expected else 'no_candidate'
            actual_status=measurement['threshold_status'] if measurement['threshold_status'] in {'not_evaluated','exceeds_threshold'} else 'no_candidate'
            actual_volume=measurement.get('intersection_volume_m3')
            actual_depth=measurement.get('minimum_translation_mm')
            expected_depth=EXPECTED_TRANSLATION_MM.get(name)
            volume_agrees=actual_volume is not None and abs(actual_volume-volume)<=1e-8
            depth_agrees=(actual_depth is None) if expected_depth is None else actual_depth is not None and abs(actual_depth-expected_depth)<=1e-4
            passed=geometry_complete and expected_status==actual_status and volume_agrees and depth_agrees
            cases.append({"id": f"{unit}:{name}", "name": name, "unit": unit,
                          "expected_candidate": expected, "measured_candidate": detected,
                          "expected_intersection_volume_m3": volume,
                          "measured_intersection_volume_m3":actual_volume,
                          "expected_minimum_translation_mm":expected_depth,"minimum_translation_mm":actual_depth,
                          "expected_threshold_status":expected_status,"measured_threshold_status":actual_status,
                          "original_kernel_candidate":name in baseline_names if name in original_names else None,
                          "geometry_complete": geometry_complete, "passed": passed,
                          "result": "PASS" if passed else "FALSE_NEGATIVE" if expected and not detected and geometry_complete else "FAIL",
                          "reference_basis": explanation})
    passed_cases = sum(case["passed"] for case in cases)
    return {"stage": 3, "report_type": "Hard-clash reference matrix",
            "app_version": APP_VERSION, "engine": "ifcopenshell", "engine_version": ifcopenshell.version,
            "solid_engine":"manifold3d","solid_engine_version":fixtures[0]['probe']['solid_engine_version'],
            "generated_at": datetime.now(timezone.utc).isoformat(), "tolerance_mm": 2.,
            "passed": passed_cases == len(cases), "passed_cases": passed_cases,
            "total_cases": len(cases), "failed_cases": len(cases)-passed_cases,
            "model_clash_checking_enabled": passed_cases==len(cases),
            "gate_status": "blocked_reference_failure" if passed_cases != len(cases) else "bounded_pilot_available",
            "original_kernel_baseline":{"passed_cases":baseline_passed,"total_cases":18,"threshold_mm":2.,"metric":"kernel protrusion/pierce distance"},
            "original_controls_passed":all(c['passed'] for c in cases if c['name'] in original_names),
            "measurement_tolerances":{"volume_absolute_m3":1e-8,"minimum_translation_absolute_mm":1e-4},
            "cases": cases, "fixtures": fixtures,
            "claim_boundary": "Synthetic reference validation enables only a bounded MEP/structure pilot. Positive intersection volume is measured by Manifold; threshold uses convex minimum translation, not the original kernel distance. Non-convex positive intersections retain depth Not evaluated. Passing controls does not prove accuracy on every IFC, project compliance or design intent.",
            "sources": ["scripts/generate_hard_clash_fixture.py",
                        "https://docs.ifcopenshell.org/ifcopenshell-python/geometry_tree.html",
                        "https://github.com/IfcOpenShell/IfcOpenShell/issues/4594",
                        "https://github.com/IfcOpenShell/IfcOpenShell/issues/6109"]}
