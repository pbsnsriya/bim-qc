"""Known-answer acceptance matrix for the Stage 1 geometry engine."""

from __future__ import annotations

from pathlib import Path
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
        warning_text = " ".join(diagnostic["warnings"])
        if case.get("warning_contains"):
            assertions.append({
                "name": "expected_warning",
                "passed": case["warning_contains"] in warning_text,
                "expected": case["warning_contains"],
                "actual": warning_text,
            })
        results.append({
            "id": case["id"],
            "purpose": case["purpose"],
            "fixture": case["file"],
            "passed": all(item["passed"] for item in assertions),
            "assertions": assertions,
        })
    return {
        "name": "Stage 1 known-answer geometry matrix",
        "source_of_truth": "Original synthetic IFC fixtures with analytically predetermined units, placements, and bounds.",
        "tolerance_metres": DEFAULT_TOLERANCE_METRES,
        "passed": all(item["passed"] for item in results),
        "passed_cases": sum(item["passed"] for item in results),
        "total_cases": len(results),
        "duration_ms": round((perf_counter() - started) * 1000, 1),
        "cases": results,
    }
