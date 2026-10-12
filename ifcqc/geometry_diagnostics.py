"""Stage 1 diagnostics for the IfcOpenShell geometry foundation."""

from __future__ import annotations

from collections import Counter
from math import isfinite
from os import cpu_count
from pathlib import Path
from time import perf_counter
from typing import Callable


MINIMUM_GEOMETRY_COVERAGE = 0.95
LARGE_COORDINATE_WARNING_METRES = 100_000.0
CROSS_ENGINE_TOLERANCE_METRES = 0.001


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


def _compare_browser_evidence(
    backend_ids: set[int], backend_extents: dict[int, list[float]], browser: dict | None,
) -> dict:
    if not browser:
        return {
            "status": "not_run",
            "tolerance_metres": CROSS_ENGINE_TOLERANCE_METRES,
            "message": "Browser web-ifc measurements were not supplied.",
            "missing_in_browser": sorted(backend_ids),
            "extra_in_browser": [],
            "compared_elements": 0,
            "maximum_extent_delta_metres": None,
        }
    try:
        browser_ids = {int(value) for value in browser.get("element_ids", [])}
        browser_extents = {
            int(key): [float(value) for value in values]
            for key, values in browser.get("element_extents_metres", {}).items()
        }
    except (TypeError, ValueError):
        return {
            "status": "fail",
            "tolerance_metres": CROSS_ENGINE_TOLERANCE_METRES,
            "message": "Browser evidence has an invalid structure.",
            "missing_in_browser": sorted(backend_ids),
            "extra_in_browser": [],
            "compared_elements": 0,
            "maximum_extent_delta_metres": None,
        }

    missing = sorted(backend_ids - browser_ids)
    extra = sorted(browser_ids - backend_ids)
    extent_deltas: dict[int, float] = {}
    for element_id in sorted(backend_ids & browser_ids):
        candidate = browser_extents.get(element_id)
        expected = backend_extents.get(element_id)
        if candidate is None or expected is None or len(candidate) != 3:
            continue
        extent_deltas[element_id] = max(abs(a - b) for a, b in zip(expected, candidate))
    maximum_delta = max(extent_deltas.values(), default=None)
    missing_extents = sorted((backend_ids & browser_ids) - set(extent_deltas))
    passed = (
        not missing
        and not missing_extents
        and maximum_delta is not None
        and maximum_delta <= CROSS_ENGINE_TOLERANCE_METRES
    )
    if passed:
        message = (
            f"IfcOpenShell and web-ifc agree for {len(extent_deltas)} element(s) "
            f"within {CROSS_ENGINE_TOLERANCE_METRES * 1000:g} mm."
        )
    else:
        message = (
            "IfcOpenShell and web-ifc do not agree on all generated element IDs "
            "and extents within the configured tolerance."
        )
    return {
        "status": "pass" if passed else "fail",
        "tolerance_metres": CROSS_ENGINE_TOLERANCE_METRES,
        "message": message,
        "missing_in_browser": missing,
        "extra_in_browser": extra,
        "missing_extent_ids": missing_extents,
        "compared_elements": len(extent_deltas),
        "maximum_extent_delta_metres": round(maximum_delta, 9) if maximum_delta is not None else None,
        "element_extent_delta_metres": {
            str(key): round(value, 9) for key, value in extent_deltas.items()
        },
        "browser_origin_mode": browser.get("origin_mode", "unknown"),
        "browser_axis_mapping": browser.get("axis_mapping", "unknown"),
    }


ProgressCallback = Callable[[dict], None]


def _diagnose_model(
    model,
    source_size: int,
    browser_evidence: dict | None = None,
    progress_callback: ProgressCallback | None = None,
) -> dict:
    """Verify geometry for an open model, optionally emitting bounded progress."""
    started = perf_counter()
    phase_timings_ms: dict[str, float] = {}
    try:
        import ifcopenshell
        import ifcopenshell.geom
        import numpy as np
    except ImportError as exc:
        raise RuntimeError(
            "IfcOpenShell is required for geometry diagnostics. Install the project dependencies."
        ) from exc

    phase_started = perf_counter()
    products = _physical_products(model)
    represented = [element for element in products if getattr(element, "Representation", None)]
    represented_by_id = {element.id(): element for element in represented}
    phase_timings_ms["inventory"] = round((perf_counter() - phase_started) * 1000, 1)
    # Every worker may hold substantial OpenCASCADE state. Large IFCs are kept
    # single-threaded to avoid multiplying tessellation memory and killing the
    # local server process.
    large_model = source_size > 25 * 1024 * 1024 or len(represented) > 500
    thread_count = 1 if large_model else max(1, min(cpu_count() or 1, 8))
    unit_name, unit_scale = _unit_details(model)
    if progress_callback:
        progress_callback({
            "phase": "tessellating",
            "processed": 0,
            "total": len(represented),
            "percent": 0.0,
            "message": f"Preparing {len(represented)} represented product(s).",
        })

    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    successful_ids: list[int] = []
    vertex_count = 0
    triangle_count = 0
    invalid_vertex_elements: list[int] = []
    element_extents: dict[int, list[float]] = {}
    minimum = np.array([np.inf, np.inf, np.inf], dtype=float)
    maximum = np.array([-np.inf, -np.inf, -np.inf], dtype=float)
    iterator_errors: list[str] = []
    slowest_elements: list[dict] = []
    iterator_started = perf_counter()
    failed_elements: list[dict] = []
    fallback_slowest: list[dict] = []
    fallback_retry_count = 0
    fallback_elapsed_ms = 0.0

    def record_shape(shape, element_id: int) -> None:
        nonlocal vertex_count, triangle_count, minimum, maximum
        if element_id in element_extents:
            return
        successful_ids.append(element_id)
        vertices = np.asarray(shape.geometry.verts, dtype=float).reshape((-1, 3))
        vertex_count += int(len(vertices))
        faces = getattr(shape.geometry, "faces", ())
        triangle_count += int(len(faces) // 3)
        if len(vertices) and np.isfinite(vertices).all():
            minimum = np.minimum(minimum, vertices.min(axis=0))
            maximum = np.maximum(maximum, vertices.max(axis=0))
            element_extents[element_id] = [float(value) for value in np.ptp(vertices, axis=0)]
        else:
            invalid_vertex_elements.append(element_id)

    # One malformed shape can abort an entire IfcOpenShell iterator. Bounded
    # batches keep bulk tessellation for the rest of the model and restrict
    # individual retries to the affected batch.
    batch_size = 250 if large_model else max(len(represented), 1)
    for batch_number, offset in enumerate(range(0, len(represented), batch_size), start=1):
        batch = represented[offset:offset + batch_size]
        batch_ids = {element.id() for element in batch}
        before_ids = set(successful_ids)
        try:
            iterator = ifcopenshell.geom.iterator(
                settings, model, thread_count, include=batch,
            ) if batch else None
            if iterator is not None and iterator.initialize():
                while True:
                    element_started = perf_counter()
                    shape = iterator.get()
                    element_id = int(shape.id)
                    record_shape(shape, element_id)
                    slowest_elements.append({
                        "step_id": element_id,
                        "type": represented_by_id.get(element_id).is_a()
                        if element_id in represented_by_id else "unknown",
                        "elapsed_ms": round((perf_counter() - element_started) * 1000, 1),
                        "measurement": "iterator_get_and_result_processing",
                    })
                    slowest_elements = sorted(
                        slowest_elements, key=lambda item: item["elapsed_ms"], reverse=True,
                    )[:10]
                    if not iterator.next():
                        break
        except Exception as exc:
            iterator_errors.append(f"Batch {batch_number}: {str(exc) or exc.__class__.__name__}")

        recovered_ids = set(successful_ids) - before_ids
        for element_id in sorted(batch_ids - recovered_ids):
            fallback_retry_count += 1
            element = represented_by_id[element_id]
            retry_started = perf_counter()
            try:
                record_shape(ifcopenshell.geom.create_shape(settings, element), element_id)
            except Exception as exc:
                failed_elements.append(_failure(element, str(exc) or exc.__class__.__name__))
            fallback_elapsed_ms += (perf_counter() - retry_started) * 1000
            fallback_slowest.append({
                "step_id": element_id,
                "type": element.is_a(),
                "elapsed_ms": round((perf_counter() - retry_started) * 1000, 1),
            })
            fallback_slowest = sorted(
                fallback_slowest, key=lambda item: item["elapsed_ms"], reverse=True,
            )[:10]

        processed = min(offset + len(batch), len(represented))
        if progress_callback:
            progress_callback({
                "phase": "tessellating",
                "processed": processed,
                "total": len(represented),
                "percent": round(processed * 100 / max(len(represented), 1), 1),
                "message": (
                    f"Processed {processed} of {len(represented)} represented product(s); "
                    f"{fallback_retry_count} targeted fallback retry/retries."
                ),
            })

    combined_geometry_ms = (perf_counter() - iterator_started) * 1000
    phase_timings_ms["iterator_tessellation"] = round(
        max(0.0, combined_geometry_ms - fallback_elapsed_ms), 1,
    )
    unique_successful_ids = set(successful_ids)
    omitted_ids = sorted(set(represented_by_id) - unique_successful_ids)
    phase_timings_ms["fallback_retries"] = round(fallback_elapsed_ms, 1)

    duplicate_shape_ids = sorted(item for item, count in Counter(successful_ids).items() if count > 1)
    unexpected_shape_ids = sorted(unique_successful_ids - set(represented_by_id))
    coverage = len(unique_successful_ids & set(represented_by_id)) / len(represented) if represented else 0.0
    finite_bounds = bool(len(unique_successful_ids) and np.isfinite(minimum).all() and np.isfinite(maximum).all())
    extents = maximum - minimum if finite_bounds else np.zeros(3)
    nonzero_extent = bool(finite_bounds and np.any(extents > 1e-9))
    global_id_count = sum(bool(getattr(element, "GlobalId", None)) for element in represented)

    core_checks = [
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
    if iterator_errors:
        warnings.append(
            f"Geometry iterator recovery was used for {len(iterator_errors)} batch(es): "
            + "; ".join(iterator_errors[:3])
        )

    browser_expected_ids = {
        element.id() for element in represented
        if not element.is_a("IfcFeatureElementSubtraction")
    } & unique_successful_ids
    expected_browser_omissions = [
        {
            "step_id": element.id(),
            "type": element.is_a(),
            "name": getattr(element, "Name", None),
            "reason": "Subtractive void features are not expected as separate visible solids.",
        }
        for element in represented
        if element.id() in unique_successful_ids
        and element.is_a("IfcFeatureElementSubtraction")
    ]
    comparison_started = perf_counter()
    cross_engine = _compare_browser_evidence(
        browser_expected_ids, element_extents, browser_evidence,
    )
    phase_timings_ms["cross_engine_comparison"] = round(
        (perf_counter() - comparison_started) * 1000, 1,
    )
    cross_engine["expected_browser_omissions"] = expected_browser_omissions
    cross_engine_check = {
        "id": "cross_engine_agreement",
        "status": cross_engine["status"],
        "message": cross_engine["message"],
    }
    checks = [*core_checks, cross_engine_check]
    core_ready = all(check["status"] == "pass" for check in core_checks)
    ready = core_ready and cross_engine["status"] == "pass"
    duplicate_prerequisites_ready = (
        core_ready
        and cross_engine.get("compared_elements", 0) > 0
        and not cross_engine.get("missing_in_browser", [])
        and not cross_engine.get("missing_extent_ids", [])
    )
    duplicate_readiness_message = (
        "Core extraction and browser STEP-id mapping passed. Exact duplicate "
        "analysis may run even though extent differences remain under Stage 1 review."
        if duplicate_prerequisites_ready
        else "Exact duplicate analysis requires passing core extraction and complete browser STEP-id mapping."
    )

    result = {
        "stage": 1,
        "ready": ready,
        "core_ready": core_ready,
        "duplicate_prerequisites_ready": duplicate_prerequisites_ready,
        "duplicate_readiness_message": duplicate_readiness_message,
        "claim": "geometry_extraction_consistency",
        "claim_boundary": (
            "A pass proves extraction consistency against known fixtures and two engines. "
            "It does not prove that the model matches drawings, design intent, or site reality."
        ),
        "engine": "ifcopenshell",
        "engine_version": str(getattr(ifcopenshell, "version", "unknown")),
        "schema": model.schema,
        "threads": thread_count,
        "memory_mode": "large-model-conservative" if large_model else "standard",
        "duration_ms": round((perf_counter() - started) * 1000, 1),
        "performance_profile": {
            "phase_timings_ms": phase_timings_ms,
            "iterator_omission_count": len(omitted_ids),
            "fallback_retry_count": fallback_retry_count,
            "iterator_batch_size": batch_size,
            "iterator_error_count": len(iterator_errors),
            "iterator_errors": iterator_errors[:10],
            "slowest_iterator_results": slowest_elements,
            "slowest_fallback_retries": fallback_slowest,
            "thread_count": thread_count,
            "profile_scope": (
                "Iterator timings measure result retrieval and local processing. "
                "IfcOpenShell may perform part of the next shape computation inside iterator.next()."
            ),
        },
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
        "element_extents_metres": {
            str(key): [round(value, 6) for value in values]
            for key, values in sorted(element_extents.items())
        },
        "cross_engine": cross_engine,
        "checks": checks,
        "warnings": warnings,
        "failed_elements": failed_elements[:100],
        "failed_elements_truncated": len(failed_elements) > 100,
    }
    if progress_callback:
        progress_callback({
            "phase": "complete",
            "processed": len(represented),
            "total": len(represented),
            "percent": 100.0,
            "message": "Geometry extraction evidence is complete.",
        })
    return result


def diagnose_geometry(ifc_text: str, browser_evidence: dict | None = None) -> dict:
    """Verify geometry from IFC text (legacy/small-model API)."""
    try:
        import ifcopenshell
    except ImportError as exc:
        raise RuntimeError(
            "IfcOpenShell is required for geometry diagnostics. Install the project dependencies."
        ) from exc
    try:
        model = ifcopenshell.file.from_string(ifc_text)
    except Exception as exc:
        raise ValueError(f"IfcOpenShell could not open this IFC model: {exc}") from exc
    return _diagnose_model(model, len(ifc_text.encode("utf-8")), browser_evidence)


def diagnose_geometry_file(
    path: str | Path,
    browser_evidence: dict | None = None,
    progress_callback: ProgressCallback | None = None,
) -> dict:
    """Verify geometry directly from an IFC file without duplicating it as JSON text."""
    try:
        import ifcopenshell
    except ImportError as exc:
        raise RuntimeError(
            "IfcOpenShell is required for geometry diagnostics. Install the project dependencies."
        ) from exc
    source = Path(path)
    opening_started = perf_counter()
    try:
        model = ifcopenshell.open(str(source))
    except Exception as exc:
        raise ValueError(f"IfcOpenShell could not open this IFC model: {exc}") from exc
    opening_ms = round((perf_counter() - opening_started) * 1000, 1)
    result = _diagnose_model(model, source.stat().st_size, browser_evidence, progress_callback)
    result["performance_profile"]["phase_timings_ms"]["ifc_open"] = opening_ms
    result["performance_profile"]["end_to_end_ms"] = round(
        opening_ms + result["duration_ms"], 1,
    )
    return result
