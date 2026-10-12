"""Necessary-condition screening of explicit IFC opening/host relationships.

Separation between world-axis bounds disproves contact between the measured
geometries. Overlapping bounds cannot establish an intersection or a valid cut.
"""

from __future__ import annotations

from math import isfinite, sqrt

DEFAULT_GAP_TOLERANCE_MM = 1.0
NUMERIC_SLACK_MM = 0.000001


def bounds_gap_mm(opening_bounds: dict, host_bounds: dict) -> tuple[list[float], float]:
    """Euclidean AABB distance: a lower bound on the body-to-body distance."""
    for box in (opening_bounds, host_bounds):
        minimum, maximum = box["minimum"], box["maximum"]
        if len(minimum) != 3 or len(maximum) != 3 or any(
            not isfinite(v) for v in (*minimum, *maximum)
        ) or any(a > b for a, b in zip(minimum, maximum)):
            raise ValueError("Bounds must have three finite, ordered coordinates.")
    gaps = [max(hlo - ohi, olo - hhi, 0.0) * 1000 for olo, ohi, hlo, hhi in zip(
        opening_bounds["minimum"], opening_bounds["maximum"],
        host_bounds["minimum"], host_bounds["maximum"],
    )]
    return gaps, sqrt(sum(value * value for value in gaps))


def _body_bounds(element) -> dict:
    """Measure every Body representation, including occurrence placement, in SI."""
    import numpy as np
    import ifcopenshell.geom
    import ifcopenshell.util.shape

    body = [rep for rep in getattr(element.Representation, "Representations", ())
            if rep.RepresentationIdentifier == "Body"]
    if not body:
        return {"status": "not_evaluated", "bounds": None,
                "message": "No Body representation supplied; axes and annotations are not host bodies."}
    try:
        settings = ifcopenshell.geom.settings()
        settings.set("use-world-coords", True)
        settings.set("disable-opening-subtractions", True)
        minimum, maximum = np.full(3, np.inf), np.full(3, -np.inf)
        for representation in body:
            # An explicit representation excludes Axis/annotation geometry.
            shape = ifcopenshell.geom.create_shape(settings, element, representation)
            vertices = ifcopenshell.util.shape.get_vertices(shape.geometry)
            if not len(vertices) or not len(shape.geometry.faces) or not np.isfinite(vertices).all():
                raise ValueError("Body tessellation did not return finite surface/solid geometry.")
            minimum = np.minimum(minimum, vertices.min(axis=0))
            maximum = np.maximum(maximum, vertices.max(axis=0))
        return {"status": "measured", "bounds": {"minimum": minimum.tolist(), "maximum": maximum.tolist()},
                "message": "All supplied Body representations measured with IFC opening subtractions disabled."}
    except Exception as exc:
        return {"status": "unavailable", "bounds": None,
                "message": f"Body extraction unavailable: {str(exc)[:400]}"}


def screen_opening_hosts(model, elements: list[dict], tolerance_mm: float = DEFAULT_GAP_TOLERANCE_MM) -> dict | None:
    """Targeted, read-only screening; each distinct body is tessellated once."""
    import ifcopenshell

    if isinstance(tolerance_mm, bool) or not isfinite(tolerance_mm) or tolerance_mm < 0:
        raise ValueError("Opening-host gap tolerance must be a finite, non-negative number.")
    openings = [data for data in elements if data["is_opening"]]
    if not openings:
        return None
    cache = {}

    def measure(entity):
        if entity.id() not in cache:
            cache[entity.id()] = _body_bounds(entity)
        return cache[entity.id()]

    results = []
    for data in openings:
        opening = model.by_id(data["step_id"])
        relationships = {}
        for rel in getattr(opening, "VoidsElements", ()):
            if rel.RelatingBuildingElement is not None:
                relationships.setdefault(rel.RelatingBuildingElement.id(), []).append(rel.id())
        # Missing relationship stays unknown. No name/proximity-based inference.
        if not relationships:
            results.append({"opening_id": opening.id(), "host_id": None, "relationship_ids": [],
                            "status": "not_evaluated", "reason": "Explicit IfcRelVoidsElement host relationship not supplied.",
                            "opening_bounds_metres": None, "host_bounds_metres": None,
                            "axis_gaps_mm": None, "bounds_distance_lower_bound_mm": None,
                            "tolerance_mm": tolerance_mm})
            continue
        opening_measurement = measure(opening)
        for host_id, rel_ids in sorted(relationships.items()):
            host_measurement = measure(model.by_id(host_id))
            item = {
                "opening_id": opening.id(), "host_id": host_id, "relationship_ids": sorted(rel_ids),
                "status": "not_evaluated", "reason": "",
                "opening_bounds_metres": opening_measurement["bounds"],
                "host_bounds_metres": host_measurement["bounds"],
                "opening_geometry_status": opening_measurement["status"],
                "host_geometry_status": host_measurement["status"],
                "axis_gaps_mm": None, "bounds_distance_lower_bound_mm": None,
                "tolerance_mm": tolerance_mm,
            }
            if opening_measurement["bounds"] is None or host_measurement["bounds"] is None:
                item["reason"] = " ".join(f"{label} #{entity_id}: {measurement['message']}"
                    for label, entity_id, measurement in [("Opening", opening.id(), opening_measurement),
                                                          ("Host", host_id, host_measurement)]
                    if measurement["bounds"] is None)
            else:
                gaps, distance = bounds_gap_mm(opening_measurement["bounds"], host_measurement["bounds"])
                item["axis_gaps_mm"], item["bounds_distance_lower_bound_mm"] = gaps, distance
                if distance > tolerance_mm + NUMERIC_SLACK_MM:
                    item["status"] = "separated"
                    item["reason"] = "Measured opening and assigned host Body bounds are separated beyond the screening threshold. Investigate the exported geometry and relationship; this does not decide duplication or author intent."
                elif distance > NUMERIC_SLACK_MM:
                    item["status"] = "within_tolerance"
                    item["reason"] = "Measured bounds are separated, but within the screening threshold. Actual contact/cut validity remains unresolved."
                else:
                    item["status"] = "bounds_overlap"
                    item["reason"] = "Bounds overlap or touch. Actual body intersection, a valid cut and author intent remain unresolved."
            results.append(item)
    return {
        "rule_id": "opening_host_bounds_consistency", "evidence_version": 1,
        "engine": "ifcopenshell", "engine_version": ifcopenshell.version,
        "bounds_frame": "IFC world Z-up metres", "tolerance_mm": tolerance_mm,
        "numeric_slack_mm": NUMERIC_SLACK_MM,
        "rule_source": "Explicit IfcRelVoidsElement + necessary contact condition for measured Body bounds.",
        "expected": "Opening and assigned host body can contact or overlap; measured bounds gap should not exceed the screening threshold.",
        "threshold_source": "Application screening default; not an industry or project acceptance standard. Independent of near-duplicate placement tolerance.",
        "measurement": "Euclidean separation between world-axis Body bounding boxes; a lower bound on geometry distance, not the exact surface distance.",
        "settings": {"use_world_coords": True, "disable_opening_subtractions": True, "representation_identifier": "Body"},
        "claim_boundary": "IFC opening subtractions are disabled for this measurement. Holes already embedded in exported Body geometry remain. Overlapping bounds are Unresolved, never a valid-cut PASS. Missing or failed Body geometry is Not evaluated. Review decisions are unchanged.",
        "results": results,
        "separated_count": sum(item["status"] == "separated" for item in results),
        "unresolved_count": sum(item["status"] in {"within_tolerance", "bounds_overlap"} for item in results),
        "not_evaluated_count": sum(item["status"] == "not_evaluated" for item in results),
    }
