"""Stage 1 diagnostics for the IfcOpenShell geometry foundation."""

from __future__ import annotations

from collections import Counter
from math import isfinite
from os import cpu_count
from time import perf_counter


MINIMUM_GEOMETRY_COVERAGE = 0.95
LARGE_COORDINATE_WARNING_METRES = 100_000.0


def _physical_products(model) -> list:
    return [
        element for element in model.by_type("IfcProduct")
        if not element.is_a("IfcSpatialStructureElement")
        and not element.is_a("IfcAnnotation")
    ]


def _unit_details(model) -> tuple[str, float]:
    import ifcopenshell.util.unit

    scale = float(ifcopenshell.util.unit.calculate_unit_scale(model))
    try:
        unit = ifcopenshell.util.unit.get_project_unit(model, "LENGTHUNIT")
    except (AttributeError, TypeError):
        unit = None
    if unit is None:
        return "metre (assumed)", scale
    prefix = getattr(unit, "Prefix", None)
    name = getattr(unit, "Name", None) or unit.is_a()
    label = " ".join(value for value in (prefix, name) if value).replace("_", " ").lower()
    return label, scale


def _failure(element, error: str) -> dict:
    return {
        "step_id": element.id(),
        "type": element.is_a(),
        "global_id": getattr(element, "GlobalId", None),
        "name": getattr(element, "Name", None),
        "error": error,
    }


def diagnose_geometry(ifc_text: str) -> dict:
    """Verify the IFC-to-world-geometry pipeline before coordination rules run."""
    started = perf_counter()
    try:
        import ifcopenshell
        import ifcopenshell.geom
        import numpy as np
    except ImportError as exc:
        raise RuntimeError(
            "IfcOpenShell is required for geometry diagnostics. Install the project dependencies."
        ) from exc

    try:
        model = ifcopenshell.file.from_string(ifc_text)
    except Exception as exc:
        raise ValueError(f"IfcOpenShell could not open this IFC model: {exc}") from exc

    products = _physical_products(model)
    represented = [element for element in products if getattr(element, "Representation", None)]
    represented_by_id = {element.id(): element for element in represented}
    thread_count = max(1, min(cpu_count() or 1, 8))
    unit_name, unit_scale = _unit_details(model)

    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    successful_ids: list[int] = []
    vertex_count = 0
    triangle_count = 0
    invalid_vertex_elements: list[int] = []
    minimum = np.array([np.inf, np.inf, np.inf], dtype=float)
    maximum = np.array([-np.inf, -np.inf, -np.inf], dtype=float)
    iterator_error = None

    try:
        iterator = ifcopenshell.geom.iterator(
            settings, model, thread_count, include=represented,
        ) if represented else None
        if iterator is not None and iterator.initialize():
            while True:
                shape = iterator.get()
                element_id = int(shape.id)
                successful_ids.append(element_id)
                vertices = np.asarray(shape.geometry.verts, dtype=float).reshape((-1, 3))
                vertex_count += int(len(vertices))
                faces = getattr(shape.geometry, "faces", ())
                triangle_count += int(len(faces) // 3)
                if len(vertices) and np.isfinite(vertices).all():
                    minimum = np.minimum(minimum, vertices.min(axis=0))
                    maximum = np.maximum(maximum, vertices.max(axis=0))
                else:
                    invalid_vertex_elements.append(element_id)
                if not iterator.next():
                    break
    except Exception as exc:  # Iterator failures are reported with element-level retries below.
        iterator_error = str(exc)

    unique_successful_ids = set(successful_ids)
    failed_elements: list[dict] = []
    for element_id in sorted(set(represented_by_id) - unique_successful_ids):
        element = represented_by_id[element_id]
        try:
            ifcopenshell.geom.create_shape(settings, element)
            reason = "The iterator omitted this shape without reporting an error."
        except Exception as exc:
            reason = str(exc) or exc.__class__.__name__
        failed_elements.append(_failure(element, reason))

    duplicate_shape_ids = sorted(item for item, count in Counter(successful_ids).items() if count > 1)
    unexpected_shape_ids = sorted(unique_successful_ids - set(represented_by_id))
    coverage = len(unique_successful_ids & set(represented_by_id)) / len(represented) if represented else 0.0
    finite_bounds = bool(len(unique_successful_ids) and np.isfinite(minimum).all() and np.isfinite(maximum).all())
    extents = maximum - minimum if finite_bounds else np.zeros(3)
    nonzero_extent = bool(finite_bounds and np.any(extents > 1e-9))
    global_id_count = sum(bool(getattr(element, "GlobalId", None)) for element in represented)

    checks = [
        {
            "id": "geometry_present",
            "status": "pass" if represented and unique_successful_ids else "fail",
            "message": f"Generated geometry for {len(unique_successful_ids)} represented product(s).",
        },
        {
            "id": "geometry_coverage",
            "status": "pass" if represented and coverage >= MINIMUM_GEOMETRY_COVERAGE else "fail",
            "message": f"Shape extraction coverage is {coverage * 100:.1f}% (required {MINIMUM_GEOMETRY_COVERAGE * 100:.0f}%).",
        },
        {
            "id": "id_mapping",
            "status": "pass" if not duplicate_shape_ids and not unexpected_shape_ids else "fail",
            "message": "Every generated shape maps to one unique IFC STEP id."
            if not duplicate_shape_ids and not unexpected_shape_ids
            else "Generated shape ids are duplicated or do not map to represented products.",
        },
        {
            "id": "finite_world_bounds",
            "status": "pass" if finite_bounds and nonzero_extent and not invalid_vertex_elements else "fail",
            "message": "World-coordinate bounds are finite and non-zero."
            if finite_bounds and nonzero_extent and not invalid_vertex_elements
            else "World-coordinate bounds contain invalid or zero-sized geometry.",
        },
        {
            "id": "length_unit",
            "status": "pass" if isfinite(unit_scale) and unit_scale > 0 else "fail",
            "message": f"Project length unit is {unit_name}; one project unit equals {unit_scale:g} metre(s).",
        },
    ]
    warnings: list[str] = []
    without_representation = len(products) - len(represented)
    if without_representation:
        warnings.append(f"{without_representation} physical product(s) have no geometric representation.")
    if represented and global_id_count < len(represented):
        warnings.append(f"{len(represented) - global_id_count} represented product(s) have no GlobalId.")
    coordinate_magnitude = float(max(np.abs(minimum).max(), np.abs(maximum).max())) if finite_bounds else 0.0
    if coordinate_magnitude > LARGE_COORDINATE_WARNING_METRES:
        warnings.append(
            f"World coordinates reach {coordinate_magnitude:,.0f} m from the origin; browser GPU precision may be reduced."
        )
    if iterator_error:
        warnings.append(f"Geometry iterator reported: {iterator_error}")

    return {
        "stage": 1,
        "ready": all(check["status"] == "pass" for check in checks),
        "engine": "ifcopenshell",
        "engine_version": str(getattr(ifcopenshell, "version", "unknown")),
        "schema": model.schema,
        "threads": thread_count,
        "duration_ms": round((perf_counter() - started) * 1000, 1),
        "units": {"length": unit_name, "metres_per_project_unit": unit_scale},
        "counts": {
            "physical_products": len(products),
            "represented_products": len(represented),
            "generated_shapes": len(unique_successful_ids),
            "failed_shapes": len(failed_elements),
            "products_without_representation": without_representation,
            "represented_with_global_id": global_id_count,
            "vertices": vertex_count,
            "triangles": triangle_count,
        },
        "coverage_percent": round(coverage * 100, 1),
        "bounds_metres": {
            "minimum": [round(float(value), 6) for value in minimum] if finite_bounds else None,
            "maximum": [round(float(value), 6) for value in maximum] if finite_bounds else None,
            "extents": [round(float(value), 6) for value in extents] if finite_bounds else None,
            "maximum_coordinate_magnitude": round(coordinate_magnitude, 3),
        },
        "mapping": {
            "duplicate_shape_ids": duplicate_shape_ids,
            "unexpected_shape_ids": unexpected_shape_ids,
            "invalid_vertex_element_ids": sorted(invalid_vertex_elements),
        },
        "checks": checks,
        "warnings": warnings,
        "failed_elements": failed_elements[:100],
        "failed_elements_truncated": len(failed_elements) > 100,
    }
