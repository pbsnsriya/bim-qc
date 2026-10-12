"""Known-answer matrix for Stage 2 exact duplicate candidates."""

from __future__ import annotations

from pathlib import Path
from time import perf_counter

from .geometry_checks import (
    EXACT_DUPLICATE_TOLERANCE_METRES,
    _duplicate_opening_geometry_issues,
    _exact_duplicate_geometry_issues,
    _physical_products,
    _shape_data,
)


DEFAULT_FIXTURE = (
    Path(__file__).resolve().parents[1] / "samples" / "golden" / "duplicate_exact_matrix.ifc"
)


def run_duplicate_acceptance_matrix(fixture: Path = DEFAULT_FIXTURE) -> dict:
    import ifcopenshell

    started = perf_counter()
    model = ifcopenshell.file.from_string(fixture.read_text(encoding="utf-8"))
    products = _physical_products(model)
    _, vertices, _ = _shape_data(model)
    issues = _exact_duplicate_geometry_issues(products, vertices)
    opening_issues = _duplicate_opening_geometry_issues(model, products, vertices)
    pairs = sorted((item["entity_id"], item["related_entity_id"]) for item in issues)
    expected_pairs = [(41, 40)]
    assertions = [
        {
            "name": "exact_same_class_pair_detected",
            "passed": pairs == expected_pairs,
            "expected": expected_pairs,
            "actual": pairs,
        },
        {
            "name": "shifted_same_class_excluded",
            "passed": all(42 not in pair for pair in pairs),
            "expected": "IfcBuildingElementProxy #42 excluded",
            "actual": pairs,
        },
        {
            "name": "same_geometry_different_class_excluded",
            "passed": all(43 not in pair for pair in pairs),
            "expected": "IfcWall #43 excluded",
            "actual": pairs,
        },
        {
            "name": "pair_selection_metadata",
            "passed": len(issues) == 1 and issues[0].get("selection_ids") == [41, 40],
            "expected": [41, 40],
            "actual": issues[0].get("selection_ids") if issues else None,
        },
        {
            "name": "subtraction_features_excluded_from_physical_duplicates",
            "passed": all(44 not in pair and 45 not in pair for pair in pairs),
            "expected": "IfcOpeningElement records excluded from physical duplicates",
            "actual": pairs,
        },
        {
            "name": "duplicate_opening_maps_to_hosts",
            "passed": (
                len(opening_issues) == 1
                and opening_issues[0].get("opening_ids") == [45, 44]
                and opening_issues[0].get("selection_ids") == [49, 48]
            ),
            "expected": {"opening_ids": [45, 44], "selection_ids": [49, 48]},
            "actual": ({
                "opening_ids": opening_issues[0].get("opening_ids"),
                "selection_ids": opening_issues[0].get("selection_ids"),
            } if opening_issues else None),
        },
    ]
    return {
        "name": "Stage 2 exact-duplicate known-answer matrix",
        "source_of_truth": (
            "Original synthetic IFC fixture containing one known exact same-class pair, "
            "one shifted same-class element, one coincident different-class element, and "
            "one duplicate opening pair related to two selectable hosts."
        ),
        "fixture": str(fixture.relative_to(Path(__file__).resolve().parents[1])),
        "tolerance_metres": EXACT_DUPLICATE_TOLERANCE_METRES,
        "passed": all(item["passed"] for item in assertions),
        "passed_cases": sum(item["passed"] for item in assertions),
        "total_cases": len(assertions),
        "duration_ms": round((perf_counter() - started) * 1000, 1),
        "assertions": assertions,
        "claim_boundary": (
            "A pass proves deterministic detection for exact tessellated geometry in this "
            "fixture. It does not prove that a candidate is an authoring mistake or detect "
            "near duplicates, mirrored elements, or intended repeated components. Opening "
            "candidates are separated and mapped to their host elements for review."
        ),
    }
