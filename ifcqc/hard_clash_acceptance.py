"""Independent, analytic expectations for the diagnostic Stage 3 kernel probe.

Expected answers come from specified box coordinates and the explicit opening,
not from a previous kernel result. A failed positive case blocks advancement.
"""
from datetime import datetime, timezone
from pathlib import Path

from .hard_clashes import run_hard_clashes_file
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
)


def run_hard_clash_acceptance(samples):
    import ifcopenshell
    cases, fixtures = [], []
    for suffix, unit in [("", "metre"), ("_millimetre", "millimetre")]:
        path = Path(samples) / "golden" / f"hard_clash_matrix{suffix}.ifc"
        report = run_hard_clashes_file(path, tolerance_mm=2.)
        fixtures.append({"filename": path.name, "source_sha256": report["source_sha256"],
                         "probe": report})
        measured = {issue["name"]: issue for issue in report["issues"]}
        for name, volume, expected, explanation in CONTROLS:
            issue = measured.get(name)
            # Missing geometry is never an accepted negative reference answer.
            geometry_complete = report["extraction_complete_for_selected_scope"]
            detected = issue is not None
            passed = geometry_complete and detected == expected and not report["unresolved_collisions"]
            cases.append({"id": f"{unit}:{name}", "name": name, "unit": unit,
                          "expected_candidate": expected, "measured_candidate": detected,
                          "expected_intersection_volume_m3": volume,
                          "kernel_distance_mm": issue["distance_mm"] if issue else None,
                          "geometry_complete": geometry_complete, "passed": passed,
                          "result": "PASS" if passed else "FALSE_NEGATIVE" if expected and not detected and geometry_complete else "FAIL",
                          "reference_basis": explanation})
    passed_cases = sum(case["passed"] for case in cases)
    return {"stage": 3, "report_type": "Hard-clash reference matrix",
            "app_version": APP_VERSION, "engine": "ifcopenshell", "engine_version": ifcopenshell.version,
            "generated_at": datetime.now(timezone.utc).isoformat(), "tolerance_mm": 2.,
            "passed": passed_cases == len(cases), "passed_cases": passed_cases,
            "total_cases": len(cases), "failed_cases": len(cases)-passed_cases,
            "model_clash_checking_enabled": False,
            "gate_status": "blocked_reference_failure" if passed_cases != len(cases) else "reference_passed_model_scan_not_released",
            "cases": cases, "fixtures": fixtures,
            "claim_boundary": "Synthetic reference validation only. Model clash checking is not released in this version. Passing these controls would not prove accuracy on every IFC, project compliance or design intent. Expected volumes are analytic reference facts; this probe does not measure intersection volume.",
            "sources": ["scripts/generate_hard_clash_fixture.py",
                        "https://docs.ifcopenshell.org/ifcopenshell-python/geometry_tree.html",
                        "https://github.com/IfcOpenShell/IfcOpenShell/issues/4594",
                        "https://github.com/IfcOpenShell/IfcOpenShell/issues/6109"]}
