"""Stage 1 diagnostics for the IfcOpenShell geometry foundation."""

from __future__ import annotations

from collections import Counter
from math import isfinite
from os import cpu_count
from pathlib import Path
from hashlib import sha256
from datetime import datetime, timezone
import platform
import sys
import re
from time import perf_counter
from typing import Callable

from .geometry_evidence import (mesh_metrics, extraction_failure, representation_details, rule_register,
    POSITION_TOLERANCE_M, SHAPE_ABSOLUTE_TOLERANCES, SHAPE_RELATIVE_TOLERANCE, PROFILE_VERSION)


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
    return extraction_failure(element, error)


def _compare_browser_evidence(
    backend_ids: set[int], backend_extents: dict[int, list[float]], browser: dict | None,
    backend_bounds: dict | None = None, backend_metrics: dict | None = None,
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
    except (TypeError, ValueError, AttributeError):
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
        if candidate is None or expected is None or len(candidate) != 3 or not all(isfinite(v) for v in candidate + expected):
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
    position_deltas, shape_deltas, missing_positions, missing_metrics = {}, {}, [], []
    position_invalid, metric_invalid = [], []
    position_ready = browser.get("bounds_frame") == "IFC world Z-up metres"
    for element_id in sorted(backend_ids & browser_ids):
        key = str(element_id)
        try:
            candidate = browser.get("element_bounds_metres", {}).get(key)
            expected = (backend_bounds or {}).get(element_id)
            if not position_ready or not candidate or not expected:
                missing_positions.append(element_id)
            else:
                values = [float(candidate[edge][axis]) for edge in ("minimum", "maximum") for axis in range(3)]
                reference = [float(expected[edge][axis]) for edge in ("minimum", "maximum") for axis in range(3)]
                if not all(isfinite(v) for v in values) or any(values[i] > values[i + 3] for i in range(3)):
                    raise ValueError("non-finite or inverted bounds")
                position_deltas[element_id] = max(abs(a - b) for a, b in zip(values, reference))
        except (ValueError, TypeError, KeyError, IndexError, AttributeError):
            position_invalid.append(element_id)
        try:
            candidate = browser.get("element_shape_metrics", {}).get(key)
            expected = (backend_metrics or {}).get(element_id)
            if not candidate or not expected or any(expected.get(metric) is None for metric in SHAPE_ABSOLUTE_TOLERANCES):
                missing_metrics.append(element_id)
            else:
                measurements = {}
                for metric, absolute in SHAPE_ABSOLUTE_TOLERANCES.items():
                    actual = float(candidate[metric])
                    if not isfinite(actual) or actual < 0:
                        raise ValueError("invalid shape metric")
                    delta = abs(actual - expected[metric])
                    allowed = absolute + SHAPE_RELATIVE_TOLERANCE * abs(expected[metric])
                    measurements[metric] = {"delta": delta, "allowed": allowed, "passed": delta <= allowed}
                shape_deltas[element_id] = measurements
        except (ValueError, TypeError, KeyError, AttributeError):
            metric_invalid.append(element_id)
    position_outliers = sorted(k for k, v in position_deltas.items() if v > POSITION_TOLERANCE_M)
    metric_outliers = sorted(k for k, values in shape_deltas.items() if not all(v["passed"] for v in values.values()))
    legacy_passed = passed
    passed = passed and not extra and not missing_positions and not missing_metrics and not position_invalid and not metric_invalid and not position_outliers and not metric_outliers
    incomplete = legacy_passed and not extra and not position_invalid and not metric_invalid and not position_outliers and not metric_outliers and bool(missing_positions or missing_metrics)
    if passed:
        message = (
            f"IfcOpenShell and web-ifc agree for {len(extent_deltas)} element(s) "
            f"for world bounds within {CROSS_ENGINE_TOLERANCE_METRES * 1000:g} mm and triangulated shape metrics within the demo profile."
        )
    elif incomplete:
        message = "Not evaluated: complete world-position and shape-metric evidence was not supplied."
    else:
        message = (
            "IfcOpenShell and web-ifc do not agree on all generated element IDs "
            "world bounds and shape metrics within the configured demo tolerances."
        )
    return {
        "status": "pass" if passed else "not_evaluated" if incomplete else "fail",
        "position_comparison": {"missing_ids": missing_positions, "invalid_ids": position_invalid, "outlier_ids": position_outliers, "element_delta_metres": {str(k): v for k, v in position_deltas.items()}},
        "shape_comparison": {"missing_ids": missing_metrics, "invalid_ids": metric_invalid, "outlier_ids": metric_outliers, "element_deltas": {str(k): v for k, v in shape_deltas.items()}, "relative_tolerance": SHAPE_RELATIVE_TOLERANCE, "absolute_tolerances": SHAPE_ABSOLUTE_TOLERANCES, "scope": "Triangulated surface area and signed-volume diagnostics; not complete shape equivalence."},
        "tolerance_authority": "demo_profile",
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
    element_bounds: dict[int, dict] = {}
    element_metrics: dict[int, dict] = {}
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
            successful_ids.append(element_id)
            return
        vertices = np.asarray(shape.geometry.verts, dtype=float).reshape((-1, 3))
        successful_ids.append(element_id)
        vertex_count += int(len(vertices))
        faces = getattr(shape.geometry, "faces", ())
        triangle_count += int(len(faces) // 3)
        if len(vertices) and np.isfinite(vertices).all():
            minimum = np.minimum(minimum, vertices.min(axis=0))
            maximum = np.maximum(maximum, vertices.max(axis=0))
            element_extents[element_id] = [float(value) for value in np.ptp(vertices, axis=0)]
            element_bounds[element_id] = {"minimum": vertices.min(axis=0).tolist(), "maximum": vertices.max(axis=0).tolist()}
            element_metrics[element_id] = mesh_metrics(vertices, faces)
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

    missing_representation_elements = [element for element in products
        if not getattr(element, "Representation", None)
        and element.is_a("IfcElement")
        and not getattr(element, "IsDecomposedBy", ())
        and not getattr(element, "IsNestedBy", ())]
    critical_unresolved_ids = sorted({item["step_id"] for item in failed_elements
        if item["blocks_extraction_readiness"]} | set(invalid_vertex_elements)
        | {element.id() for element in missing_representation_elements})
    core_checks = [
        {"id": "critical_geometry", "status": "fail" if critical_unresolved_ids else "pass",
         "message": f"{len(critical_unresolved_ids)} unresolved critical geometry element(s); percentage coverage cannot override this gate."},
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
            "status": "pass" if isfinite(unit_scale) and unit_scale > 0 and "assumed" not in unit_name else "not_evaluated",
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
        browser_expected_ids, element_extents, browser_evidence, element_bounds, element_metrics,
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
        "acceptance_profile": PROFILE_VERSION,
        "critical_unresolved_ids": critical_unresolved_ids,
        "missing_representation_elements": [{"step_id": e.id(), "type": e.is_a(), "global_id": getattr(e, "GlobalId", None)} for e in missing_representation_elements],
        "project_compliance": {"verdict": "not_evaluated", "reason": "No project acceptance specification has been supplied."},
        "full_shape_equivalence": {"verdict": "not_evaluated", "reason": "Bounds, area and volume are diagnostics; complete surface correspondence is not measured."},
        "ready": ready,
        "core_ready": core_ready,
        "duplicate_prerequisites_ready": duplicate_prerequisites_ready,
        "duplicate_readiness_message": duplicate_readiness_message,
        "claim": "geometry_extraction_consistency",
        "claim_boundary": (
            "A pass supports extraction consistency for measured IDs, world bounds, area and volume under this demo profile; it does not prove complete shape equivalence. "
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
        "element_bounds_metres": {str(k): v for k, v in element_bounds.items()},
        "element_shape_metrics": {str(k): v for k, v in element_metrics.items()},
        "cross_engine": cross_engine,
        "checks": checks,
        "warnings": warnings,
        "failed_elements": failed_elements[:100],
        "failed_elements_truncated": len(failed_elements) > 100,
    }
    result["rule_evidence"] = rule_register(result)
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
    digest = sha256()
    with source.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    # Confirm dangling references from the raw STEP text, rather than treating
    # an engine exception alone as evidence of a model defect.
    placement_failures = {item['model_defect_evidence']['placement_step_id']: item
        for item in result['failed_elements'] if item.get('model_defect_evidence')}
    references = {}
    if placement_failures:
        with source.open('r', encoding='utf-8', errors='replace') as handle:
            for line in handle:
                match = re.match(r'\s*#(\d+)\s*=\s*IFCLOCALPLACEMENT\((.*)\);', line, re.I)
                if match and int(match[1]) in placement_failures:
                    relative = match[2].split(',')[-1].strip()
                    references[int(match[1])] = (line.strip(), int(relative[1:]) if relative.startswith('#') else None, relative)
        targets = {entry[1] for entry in references.values() if entry[1] is not None}
        defined = set()
        with source.open('r', encoding='utf-8', errors='replace') as handle:
            for line in handle:
                match = re.match(r'\s*#(\d+)\s*=', line)
                if match and int(match[1]) in targets:
                    defined.add(int(match[1]))
        for placement_id, item in placement_failures.items():
            raw, target, value = references.get(placement_id, (None, None, None))
            confirmed = raw is not None and (value == '$' or target is not None and target not in defined)
            item['confirmed_model_defect'] = confirmed
            item['classification'] = 'confirmed_model_defect' if confirmed else 'unresolved_extraction_failure'
            item['model_defect_evidence'].update(raw_step_line=raw, referenced_step_id=target,
                referenced_definition_present=target in defined if target is not None else None,
                raw_confirmation=confirmed)
    result['rule_evidence'] = rule_register(result)
    comparison_sha = (browser_evidence or {}).get('source_sha256')
    result['model_identity'] = {'expected_sha256': digest.hexdigest(), 'measured_sha256': comparison_sha,
        'verdict': 'pass' if comparison_sha == digest.hexdigest() else 'fail' if comparison_sha else 'not_evaluated',
        'source': 'Exact bytes uploaded to the backend and decoded by the comparison engine'}
    if comparison_sha and comparison_sha != digest.hexdigest():
        result['ready'] = result['duplicate_prerequisites_ready'] = False
        result['cross_engine']['status'] = 'fail'
        result['cross_engine']['message'] = 'Comparison evidence belongs to a different IFC SHA-256; it cannot validate this file.'
        for check in result['checks']:
            if check['id'] == 'cross_engine_agreement':
                check.update(status='fail', message=result['cross_engine']['message'])
        result['rule_evidence'] = rule_register(result)
    result["provenance"] = {
        "model_filename": source.name, "model_sha256": digest.hexdigest(),
        "model_size_bytes": source.stat().st_size, "generated_at": datetime.now(timezone.utc).isoformat(),
        "app_version": "0.7.10", "python_version": sys.version.split()[0], "platform": platform.platform(),
        "settings": {"use_world_coords": True, "batch_size": result["performance_profile"]["iterator_batch_size"], "threads": result["threads"]},
        "browser_engine_version": (browser_evidence or {}).get("engine_version"),
    }
    try:
        import resource
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        result["performance_profile"]["process_peak_rss_bytes"] = int(peak if sys.platform == "darwin" else peak * 1024)
        result["performance_profile"]["memory_scope"] = "Peak RSS of this worker process, not total application/browser memory."
    except ImportError:
        result["performance_profile"]["process_peak_rss_bytes"] = None
        result["performance_profile"]["memory_scope"] = "Not evaluated: peak RSS unavailable on this platform."
    return result
