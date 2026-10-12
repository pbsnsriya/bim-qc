"""Bounded, translation-only review of nearby tessellated physical elements."""

from collections import defaultdict
from hashlib import sha256
from itertools import product
from math import floor
from pathlib import Path
from time import perf_counter

from .geometry_checks import EXACT_DUPLICATE_TOLERANCE_METRES, _pair_issue


DEFAULT_FIXTURE = Path(__file__).resolve().parents[1] / "samples/golden/duplicate_near_matrix.ifc"
DISTANCE_SLACK_METRES = 1e-9


def _canonical_surface(faces, vertices, centre):
    """Sort quantised triangle coordinates, retaining the actual coordinates for verification.

    A fingerprint is a conservative filter. A matching fingerprint is followed
    by measured vertex correspondence residuals; bounds alone never qualify.
    Different tessellations may fail to match and are outside this first increment.
    """
    import numpy as np

    faces = np.asarray(faces, dtype=np.int64)
    if not len(faces) or len(faces) % 3 or faces.min() < 0 or faces.max() >= len(vertices):
        raise ValueError("No usable triangular surface.")
    triangles = (vertices - centre)[faces.reshape(-1, 3)]
    scaled = triangles / EXACT_DUPLICATE_TOLERANCE_METRES
    if not np.isfinite(scaled).all() or np.abs(scaled).max() >= np.iinfo(np.int64).max / 2:
        raise ValueError("Surface coordinates cannot be normalised safely.")
    quantised = np.rint(scaled).astype(np.int64)
    vertex_order = np.lexsort((quantised[:, :, 2], quantised[:, :, 1], quantised[:, :, 0]), axis=1)
    quantised = np.take_along_axis(quantised, vertex_order[:, :, None], axis=1)
    triangles = np.take_along_axis(triangles, vertex_order[:, :, None], axis=1)
    flat = quantised.reshape(-1, 9)
    triangle_order = np.lexsort(tuple(flat[:, index] for index in range(8, -1, -1)))
    ordered = flat[triangle_order].astype('<i8', copy=False)
    return sha256(ordered.tobytes()).digest(), triangles[triangle_order]


def near_duplicate_issues(products, triangle_faces, vertices, tolerance_mm, *, exact_pairs=(),
                         max_comparisons=250_000, max_results=5_000):
    """Find translation-equivalent surfaces whose world bounds centres are nearby.

    Spatial cells cover adjacent bins to avoid missing pairs at cell boundaries.
    Search work and returned results are bounded; reaching a limit is explicitly
    incomplete. Exact/coincident geometry and subtraction features are excluded.
    """
    import numpy as np

    tolerance = tolerance_mm / 1000.0
    if not 0.00001 <= tolerance <= 0.1:
        raise ValueError("near_duplicate_tolerance_mm must be between 0.01 and 100.")
    exact_pairs = set(exact_pairs)
    started = perf_counter()
    stats = {"complete": True, "tolerance_mm": tolerance_mm,
             "shape_tolerance_mm": EXACT_DUPLICATE_TOLERANCE_METRES * 1000,
             "eligible_products": 0, "unavailable_product_ids": [], "compared_pairs": 0,
             "candidate_pairs": 0, "comparison_limit": max_comparisons,
             "result_limit": max_results, "limit_reason": None,
             "claim_boundary": "Translation-only tessellated surface candidates; author intent and project compliance are not evaluated. Different triangulations or rotated shapes may be missed."}
    records = []
    for element in sorted(products, key=lambda e: e.id()):
        if element.is_a("IfcFeatureElementSubtraction"):
            continue
        verts = vertices.get(element.id())
        faces = triangle_faces.get(element.id())
        if verts is None or faces is None or not len(faces) or not len(verts) or not np.isfinite(verts).all():
            if element.Representation is not None:
                stats["unavailable_product_ids"].append(element.id())
            continue
        minimum, maximum = verts.min(axis=0), verts.max(axis=0)
        centre = minimum + (maximum - minimum) / 2
        count = len(faces)
        records.append((element, centre, maximum - minimum, count, verts, faces))
    stats["eligible_products"] = len(records)
    cells = defaultdict(list)
    fingerprints = {}
    unavailable = set(stats["unavailable_product_ids"])
    issues = []
    stopped = False
    for record in records:
        element, centre, extents, count, verts, shape = record
        cell = tuple(floor(float(value) / (tolerance + DISTANCE_SLACK_METRES)) for value in centre)
        for offset in product((-1, 0, 1), repeat=3):
            key = (element.is_a(), count, *(cell[axis] + offset[axis] for axis in range(3)))
            for other in cells.get(key, ()):
                if stats["compared_pairs"] >= max_comparisons:
                    stats.update(complete=False, limit_reason="comparison_limit")
                    stopped = True
                    break
                stats["compared_pairs"] += 1
                original, other_centre, other_extents, _, other_verts, other_shape = other
                pair = tuple(sorted((element.id(), original.id())))
                delta = centre - other_centre
                distance = float(np.linalg.norm(delta))
                if pair in exact_pairs or distance <= EXACT_DUPLICATE_TOLERANCE_METRES:
                    continue
                if distance > tolerance + DISTANCE_SLACK_METRES:
                    continue
                if np.max(np.abs(extents - other_extents)) > 2 * EXACT_DUPLICATE_TOLERANCE_METRES:
                    continue
                for item in (record, other):
                    obj, position, _, _, points, mesh = item
                    if obj.id() not in fingerprints:
                        try:
                            fingerprints[obj.id()] = _canonical_surface(mesh, points, position)[0]
                        except ValueError:
                            fingerprints[obj.id()] = None
                            unavailable.add(obj.id())
                if fingerprints[element.id()] is None or fingerprints[element.id()] != fingerprints[original.id()]:
                    continue
                # Recompute only a matched pair; do not retain large normalised meshes.
                _, first = _canonical_surface(shape, verts, centre)
                _, second = _canonical_surface(other_shape, other_verts, other_centre)
                residual = float(np.linalg.norm(first - second, axis=2).max())
                if residual > EXACT_DUPLICATE_TOLERANCE_METRES:
                    continue
                if len(issues) >= max_results:
                    stats.update(complete=False, limit_reason="result_limit")
                    stopped = True
                    break
                issues.append(_pair_issue(
                    "near_duplicate_candidate", "warning", "Near duplicate candidate",
                    f"{element.is_a()} #{element.id()} matches the translation-normalised "
                    f"tessellated surface of #{original.id()}; world bounds centre offset "
                    f"{distance * 1000:.6g} mm (configured limit {tolerance_mm:g} mm), "
                    f"shape residual {residual * 1000:.6g} mm. Review whether the overlap is intentional.",
                    element, original, selection_ids=[element.id(), original.id()],
                    confidence="translated_tessellated_surface_match", tolerance_mm=tolerance_mm,
                    placement_offset_mm=distance * 1000, translation_mm=(delta * 1000).tolist(),
                    shape_residual_mm=residual * 1000,
                    shape_tolerance_mm=EXACT_DUPLICATE_TOLERANCE_METRES * 1000,
                    detection_basis="same IFC class, translation-normalised canonical triangles and measured correspondence residual; world bounds centre distance within configured limit",
                ))
            if stopped:
                break
        if stopped:
            break
        cells[(element.is_a(), count, *cell)].append(record)
    stats["unavailable_product_ids"] = sorted(unavailable)
    stats["candidate_pairs"] = len(issues)
    stats["duration_ms"] = round((perf_counter() - started) * 1000, 1)
    return issues, stats


def run_near_duplicate_acceptance_matrix(tolerance_mm=5.0):
    """Use independently specified placements and exclusions in a supplied fixture."""
    import ifcopenshell
    from .geometry_checks import _physical_products, _shape_data

    model = ifcopenshell.open(str(DEFAULT_FIXTURE))
    triangle_faces = {}
    _, vertices, _ = _shape_data(model, triangle_faces)
    issues, scan = near_duplicate_issues(_physical_products(model), triangle_faces, vertices, tolerance_mm)
    actual = {tuple(sorted((i["entity_id"], i["related_entity_id"]))) for i in issues}
    labels = {e.Name: e.id() for e in model.by_type("IfcElement")}
    checks = []
    for name, left, right, offset, allowed in (
        ("shift_2mm", "Original", "Near 2mm", 2., True),
        ("boundary_5mm", "Boundary original", "Boundary 5mm", 5., True),
        ("outside_5_001mm", "Outside original", "Outside 5.001mm", 5.001, True),
        ("exact_not_repeated", "Original", "Exact", 0., False),
        ("different_class_excluded", "Class original", "Different class", 2., False),
        ("different_shape_excluded", "Shape original", "Different shape", 2., False),
        ("rotated_asymmetric_shape_excluded", "Rotation original", "Rotated shape", 2., False),
        ("opening_voids_excluded", "Opening original", "Opening near", 2., False),
        ("spaced_repeated_objects_excluded", "Spaced original", "Spaced repeat", 1000., False),
        ("different_properties_detected", "Property original", "Property near", 2., True),
        ("same_bounds_different_surface_excluded", "Bounds original", "Different surface", 2., False),
    ):
        pair = tuple(sorted((labels[left], labels[right])))
        expected = allowed and offset <= tolerance_mm
        detected = pair in actual
        checks.append({"name": name, "passed": detected == expected,
                       "expected": expected, "actual": detected, "pair": list(pair), "known_offset_mm": offset})
    expected_pairs = {tuple(sorted((labels[a], labels[b]))) for a, b, offset in (
        ("Original", "Near 2mm", 2.), ("Exact", "Near 2mm", 2.),
        ("Boundary original", "Boundary 5mm", 5.),
        ("Outside original", "Outside 5.001mm", 5.001),
        ("Property original", "Property near", 2.),
    ) if offset <= tolerance_mm}
    checks.append({"name": "complete_expected_pair_set", "passed": actual == expected_pairs and scan["complete"],
                   "expected": sorted(expected_pairs), "actual": sorted(actual)})
    return {"name": "Stage 2 near-duplicate known-answer matrix", "fixture": str(DEFAULT_FIXTURE.name),
            "source_of_truth": "Synthetic placements of 0, 2, 5, 5.001 and 1000 mm with independent class, shape, rotation, void and property cases.",
            "tolerance_mm": tolerance_mm, "passed": all(c["passed"] for c in checks),
            "passed_cases": sum(c["passed"] for c in checks), "total_cases": len(checks), "assertions": checks,
            "claim_boundary": scan["claim_boundary"]}
