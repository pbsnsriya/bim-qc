"""Known-answer acceptance matrix for the Stage 1 geometry engine."""

from __future__ import annotations

from pathlib import Path
from math import pi
from hashlib import sha256
from time import perf_counter

from .geometry_diagnostics import diagnose_geometry


DEFAULT_TOLERANCE_METRES = 0.001

CASES = (
    {
        "id": "ifc4_metre_cube",
        "file": "golden/cube_metre.ifc",
        "purpose": "Known 1 m cube in IFC4 metre units",
        "schema": "IFC4",
        "unit_scale": 1.0,
        "generated_shapes": 1,
        "minimum": [0.0, 0.0, 0.0],
        "maximum": [1.0, 1.0, 1.0],
        "core_ready": True,
    },
    {
        "id": "ifc4_millimetre_cube",
        "file": "golden/cube_millimetre.ifc",
        "purpose": "1000 mm input must become a 1 m world-space cube",
        "schema": "IFC4",
        "unit_scale": 0.001,
        "generated_shapes": 1,
        "minimum": [0.0, 0.0, 0.0],
        "maximum": [1.0, 1.0, 1.0],
        "core_ready": True,
    },
    {
        "id": "nested_rotated_placement",
        "file": "golden/nested_rotated.ifc",
        "purpose": "Nested placement and 90-degree rotation in world coordinates",
        "schema": "IFC4",
        "unit_scale": 1.0,
        "generated_shapes": 1,
        "minimum": [11.0, 20.0, 3.0],
        "maximum": [12.0, 22.0, 4.0],
        "core_ready": True,
    },
    {
        "id": "ifc2x3_metre_cube",
        "file": "golden/cube_ifc2x3.ifc",
        "purpose": "Equivalent known geometry through the IFC2X3 schema",
        "schema": "IFC2X3",
        "unit_scale": 1.0,
        "generated_shapes": 1,
        "minimum": [0.0, 0.0, 0.0],
        "maximum": [1.0, 1.0, 1.0],
        "core_ready": True,
    },
    {
        "id": "large_world_coordinates",
        "file": "golden/large_coordinates.ifc",
        "purpose": "Preserve world placement and trigger the GPU precision warning",
        "schema": "IFC4",
        "unit_scale": 1.0,
        "generated_shapes": 1,
        "minimum": [200000.0, 300000.0, 0.0],
        "maximum": [200001.0, 300001.0, 1.0],
        "core_ready": True,
        "warning_contains": "GPU precision",
    },
    {
        "id": "missing_representation_rejection",
        "file": "clean_demo.ifc",
        "purpose": "A product with no representation must be rejected by the gate",
        "schema": "IFC4",
        "unit_scale": 1.0,
        "generated_shapes": 0,
        "minimum": None,
        "maximum": None,
        "core_ready": False,
    },
    {"id": "opening_cutout", "file": "golden/opening_cutout.ifc",
     "purpose": "4 x 0.3 x 3 m wall minus a 1 x 0.3 x 2 m cutout: host volume 3 m3",
     "schema": "IFC4", "unit_scale": 1.0, "generated_shapes": 2,
     "minimum": [0.0, -0.1, 0.0], "maximum": [4.0, 0.4, 3.0], "core_ready": True,
     "metrics": {"20": {"volume_m3": 3.0, "surface_area_m2": 25.4}}},
    {"id": "curved_cylinder", "file": "golden/curved_cylinder.ifc",
     "purpose": "Radius 1 m, height 2 m cylinder: volume 2*pi, area 6*pi",
     "schema": "IFC4", "unit_scale": 1.0, "generated_shapes": 1,
     "minimum": [4.0, 6.0, 3.0], "maximum": [6.0, 8.0, 5.0], "core_ready": True,
     "metrics": {"18": {"volume_m3": 2*pi, "surface_area_m2": 6*pi}}},
    {"id": "mapped_instances", "file": "golden/mapped_instances.ifc",
     "purpose": "Same mapped 2 x 1 x 1 m box in distinct placements, one rotated 90 degrees",
     "schema": "IFC4", "unit_scale": 1.0, "generated_shapes": 2,
     "minimum": [0.0, 0.0, 0.0], "maximum": [5.0, 5.0, 1.0], "core_ready": True,
     "element_bounds": {"27": {"minimum": [0,0,0], "maximum": [2,1,1]},
                        "37": {"minimum": [4,3,0], "maximum": [5,5,1]}},
     "metrics": {"27": {"volume_m3": 2.0, "surface_area_m2": 10.0},
                 "37": {"volume_m3": 2.0, "surface_area_m2": 10.0}}},
    {"id": "complex_placement", "file": "golden/complex_placement.ifc",
     "purpose": "Three nested placements with two rotations; world box [7,21,4] to [9,22,5]",
     "schema": "IFC4", "unit_scale": 1.0, "generated_shapes": 1,
     "minimum": [7.0, 21.0, 4.0], "maximum": [9.0, 22.0, 5.0], "core_ready": True,
     "metrics": {"28": {"volume_m3": 2.0, "surface_area_m2": 10.0}}},

)


def _vector_matches(actual, expected, tolerance: float) -> bool:
    if actual is None or expected is None:
        return actual is expected
    return len(actual) == len(expected) and all(
        abs(float(first) - float(second)) <= tolerance
        for first, second in zip(actual, expected)
    )


def run_acceptance_matrix(samples: Path) -> dict:
    started = perf_counter()
    results = []
    for case in CASES:
        diagnostic = diagnose_geometry((samples / case["file"]).read_text(encoding="utf-8"))
        assertions = [
            {
                "name": "schema",
                "passed": diagnostic["schema"] == case["schema"],
                "expected": case["schema"],
                "actual": diagnostic["schema"],
            },
            {
                "name": "unit_scale",
                "passed": abs(diagnostic["units"]["metres_per_project_unit"] - case["unit_scale"]) <= 1e-12,
                "expected": case["unit_scale"],
                "actual": diagnostic["units"]["metres_per_project_unit"],
            },
            {
                "name": "generated_shapes",
                "passed": diagnostic["counts"]["generated_shapes"] == case["generated_shapes"],
                "expected": case["generated_shapes"],
                "actual": diagnostic["counts"]["generated_shapes"],
            },
            {
                "name": "minimum_bounds",
                "passed": _vector_matches(
                    diagnostic["bounds_metres"]["minimum"], case["minimum"], DEFAULT_TOLERANCE_METRES,
                ),
                "expected": case["minimum"],
                "actual": diagnostic["bounds_metres"]["minimum"],
            },
            {
                "name": "maximum_bounds",
                "passed": _vector_matches(
                    diagnostic["bounds_metres"]["maximum"], case["maximum"], DEFAULT_TOLERANCE_METRES,
                ),
                "expected": case["maximum"],
                "actual": diagnostic["bounds_metres"]["maximum"],
            },
            {
                "name": "expected_gate_outcome",
                "passed": diagnostic["core_ready"] is case["core_ready"],
                "expected": case["core_ready"],
                "actual": diagnostic["core_ready"],
            },
        ]
        for element_id, expected_box in case.get("element_bounds", {}).items():
            actual_box = diagnostic["element_bounds_metres"].get(element_id, {})
            for edge in ("minimum", "maximum"):
                assertions.append({"name": f"{element_id}_{edge}", "passed": _vector_matches(actual_box.get(edge), expected_box[edge], DEFAULT_TOLERANCE_METRES), "expected": expected_box[edge], "actual": actual_box.get(edge), "tolerance": DEFAULT_TOLERANCE_METRES})
        for element_id, expected_metrics in case.get("metrics", {}).items():
            for metric, expected in expected_metrics.items():
                actual = diagnostic["element_shape_metrics"].get(element_id, {}).get(metric)
                tolerance = 0.001 + 0.005 * abs(expected)
                assertions.append({"name": f"{element_id}_{metric}", "passed": actual is not None and abs(actual - expected) <= tolerance, "expected": expected, "actual": actual, "tolerance": tolerance})
        warning_text = " ".join(diagnostic["warnings"])
        if case.get("warning_contains"):
            assertions.append({
                "name": "expected_warning",
                "passed": case["warning_contains"] in warning_text,
                "expected": case["warning_contains"],
                "actual": warning_text,
            })
        for assertion in assertions:
            assertion.setdefault("tolerance", DEFAULT_TOLERANCE_METRES if "bounds" in assertion["name"] else 1e-12 if assertion["name"] == "unit_scale" else None)
            assertion["source"] = "Original analytic fixture specification; demo profile, not an industry threshold."
        results.append({
            "id": case["id"],
            "purpose": case["purpose"],
            "fixture": case["file"],
            "fixture_sha256": sha256((samples / case["file"]).read_bytes()).hexdigest(),
            "passed": all(item["passed"] for item in assertions),
            "assertions": assertions,
        })
    return {
        "name": "Stage 1 known-answer geometry matrix",
        "source_of_truth": "Original synthetic IFC fixtures with analytically predetermined units, placements, bounds, cutouts and area/volume. No third-party certification is claimed.",
        "tolerance_metres": DEFAULT_TOLERANCE_METRES,
        "tolerance_authority": "demo_profile",
        "shape_relative_tolerance": 0.005,
        "passed": all(item["passed"] for item in results),
        "passed_cases": sum(item["passed"] for item in results),
        "total_cases": len(results),
        "duration_ms": round((perf_counter() - started) * 1000, 1),
        "cases": results,
    }
