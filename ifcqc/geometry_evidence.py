"""Measured geometry and explicit prototype acceptance rules (not certification)."""
from __future__ import annotations

import numpy as np

PROFILE_VERSION = "public-stage1-v1"
POSITION_TOLERANCE_M = 0.001
SHAPE_RELATIVE_TOLERANCE = 0.005
SHAPE_ABSOLUTE_TOLERANCES = {"volume_m3": 0.001, "surface_area_m2": 0.001}


def mesh_metrics(vertices, faces) -> dict:
    triangles = np.asarray(faces, dtype=int).reshape((-1, 3))
    if not len(triangles):
        return {"volume_m3": None, "surface_area_m2": None}
    points = vertices[triangles] - vertices[0]
    crosses = np.cross(points[:, 1] - points[:, 0], points[:, 2] - points[:, 0])
    return {
        "surface_area_m2": float(np.linalg.norm(crosses, axis=1).sum() / 2),
        "volume_m3": float(abs(np.einsum("ij,ij->i", points[:, 0], np.cross(points[:, 1], points[:, 2])).sum() / 6)),
    }


def representation_details(element) -> list[dict]:
    rep = getattr(element, "Representation", None)
    return [{"step_id": item.id(), "identifier": item.RepresentationIdentifier,
             "representation_type": item.RepresentationType,
             "item_types": [x.is_a() for x in item.Items]}
            for item in getattr(rep, "Representations", ())]


def extraction_failure(element, error: str) -> dict:
    reps = representation_details(element)
    placement = getattr(element, 'ObjectPlacement', None)
    missing_relative_placement = bool(placement and placement.is_a('IfcLocalPlacement') and placement.RelativePlacement is None)
    curve_types = {"Curve2D", "Curve3D", "GeometricCurveSet"}
    is_curve = bool(reps) and all(r["representation_type"] in curve_types for r in reps)
    return {
        "step_id": element.id(), "type": element.is_a(),
        "global_id": getattr(element, "GlobalId", None), "name": getattr(element, "Name", None),
        "error": error, "representations": reps,
        "classification": "confirmed_model_defect" if missing_relative_placement else "non_solid_representation_needs_review" if is_curve else "unresolved_extraction_failure",
        "blocks_extraction_readiness": not is_curve,
        "confirmed_model_defect": missing_relative_placement,
        "model_defect_evidence": {"placement_step_id": placement.id(), "required_attribute": "IfcLocalPlacement.RelativePlacement", "measured_value": None, "schema": element.wrapped_data.file.schema, "source": "IFC declared schema: IfcLocalPlacement.RelativePlacement is not OPTIONAL"} if missing_relative_placement else None,
        "disposition": "Required local placement is unresolved in the loaded IFC; independently verify raw references before repair." if missing_relative_placement else "Needs independent inspection; extraction failure alone cannot establish a model defect.",
    }


def rule_register(result: dict) -> list[dict]:
    profile = {"authority": "demo_profile", "reference": "docs/OpenBIM_Public_QC_Baseline_v1.md", "version": PROFILE_VERSION}
    rows = []
    definitions = {
        "geometry_present": ("QC-05", "at least one measured representation", result["counts"]["generated_shapes"], None),
        "geometry_coverage": ("QC-05", "95% diagnostic threshold only; not a model approval threshold", result["coverage_percent"], 95),
        "critical_geometry": ("QC-05", "zero unresolved in-scope solid or missing physical-element representations", result["critical_unresolved_ids"], 0),
        "id_mapping": ("QC-07", "zero duplicate or unexpected generated STEP IDs", result["mapping"], 0),
        "finite_world_bounds": ("QC-04", "finite measurable world bounds", result["bounds_metres"], None),
        "length_unit": ("QC-03", "explicit positive finite project length-unit scale", result["units"], None),
        "cross_engine_agreement": ("QC-07", "IDs, world bounds and triangulated shape metrics agree within profile tolerances", result["cross_engine"], {"world_bounds_m": POSITION_TOLERANCE_M, "shape_relative": SHAPE_RELATIVE_TOLERANCE, "shape_absolute": SHAPE_ABSOLUTE_TOLERANCES}),
    }
    for check in result["checks"]:
        code, expected, actual, tolerance = definitions[check["id"]]
        rows.append({"rule_id": check["id"], "checklist_id": code, "source": profile,
                     "expected": expected, "actual": actual, "tolerance": tolerance,
                     "verdict": check["status"], "message": check["message"]})
    for code, label, reason in [
        ("QC-01", "IFC normative conformance", "Complete syntax/schema/formal-rule validation has not been run by Stage 1."),
        ("QC-13", "Design dimensions and alignment", "No approved expected dimensions/grid/schedule has been supplied."),
        ("QC-14", "Drawing completeness", "No labelled drawing or reference model has been supplied."),
        ("PROJECT", "Project/industry acceptance", "This is a prototype extraction profile, not project acceptance or standards certification."),
    ]:
        rows.append({"rule_id": code, "source": profile, "expected": label, "actual": None,
                     "tolerance": None, "verdict": "not_evaluated", "message": reason})
    return rows
