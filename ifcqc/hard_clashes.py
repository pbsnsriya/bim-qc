"""Stage 3 kernel probe. Diagnostic only until the reference gate is resolved."""
from datetime import datetime, timezone
from pathlib import Path
from hashlib import sha256
from math import isfinite
from time import perf_counter

from .geometry_checks import STRUCTURAL_CLASSES, _pair_issue
from .version import APP_VERSION

MAX_ELEMENTS = 500
MAX_TRIANGLES = 2_000_000
NUMERIC_SLACK_MM = .000001


def run_hard_clash_model(model, tolerance_mm=2., element_ids=None):
    import ifcopenshell
    import ifcopenshell.geom
    import numpy as np

    if type(tolerance_mm) is bool or not isinstance(tolerance_mm, (int, float)) or not isfinite(tolerance_mm) or not 0 <= tolerance_mm <= 1000:
        raise ValueError("Hard-clash threshold must be a finite number from 0 to 1000 mm.")
    eligible = {e.id(): e for e in model.by_type("IfcDistributionElement")}
    for cls in STRUCTURAL_CLASSES:
        eligible.update({e.id(): e for e in model.by_type(cls)})
    if element_ids is not None:
        if not isinstance(element_ids, list) or not element_ids or any(type(i) is not int or i <= 0 for i in element_ids):
            raise ValueError("Element IDs must be a non-empty list of positive integers.")
        invalid = sorted(set(element_ids) - eligible.keys())
        if invalid:
            raise ValueError(f"IDs outside the MEP/structure pilot scope: {invalid[:10]}.")
        eligible = {i: eligible[i] for i in sorted(set(element_ids))}
    if len(eligible) > MAX_ELEMENTS:
        raise ValueError(f"Stage 3 pilot supports at most {MAX_ELEMENTS} eligible elements. Select an explicit subset of IDs or load the small hard-clash sample; whole-model extraction was not started.")
    started = perf_counter()
    settings = ifcopenshell.geom.settings(); settings.set("use-world-coords", True)
    tree = ifcopenshell.geom.tree()
    shapes, measured, skipped = [], set(), []
    triangles = 0
    for eid, element in sorted(eligible.items()):
        try:
            if not any(rep.RepresentationIdentifier == "Body" for rep in getattr(element.Representation, "Representations", ())):
                raise ValueError("No Body representation supplied.")
            shape = ifcopenshell.geom.create_shape(settings, element)
            vertices = np.array(shape.geometry.verts).reshape(-1,3)
            faces = tuple(shape.geometry.faces)
            if not len(vertices) or not faces or not np.isfinite(vertices).all():
                raise ValueError("No finite surface geometry returned.")
            if not tree.is_manifold(faces):
                raise ValueError("Non-manifold mesh; reliable penetration depth is not evaluated.")
            triangles += len(faces)//3
            if triangles > MAX_TRIANGLES:
                raise ValueError("Stage 3 pilot triangle limit exceeded; scan not evaluated.")
            tree.add_element(shape); shapes.append(shape); measured.add(eid)
        except Exception as exc:
            if triangles > MAX_TRIANGLES:
                raise ValueError(str(exc)) from exc
            skipped.append({"element_id":eid, "class":element.is_a(), "reason":str(exc)[:400]})
    mep = [e for i,e in eligible.items() if i in measured and e.is_a("IfcDistributionElement")]
    structure = [e for i,e in eligible.items() if i in measured and not e.is_a("IfcDistributionElement")]
    issues, unresolved, seen = [], [], set()
    if mep and structure:
        for clash in tree.clash_intersection_many(mep, structure, tolerance=tolerance_mm/1000, check_all=True):
            # The tree returns C++ wrappers, not Python IFC entities. Resolve
            # them before exporting GlobalIds, names or relationship metadata.
            first, second = model.by_id(clash.a.id()), model.by_id(clash.b.id())
            pair = tuple(sorted((first.id(),second.id())))
            if pair in seen: continue
            seen.add(pair)
            distance_mm = float(clash.distance)*1000
            kind = str(tree.get_clash_type(clash.clash_type)).lower()
            if kind == "collision" or not isfinite(distance_mm):
                unresolved.append({"element_ids":list(pair), "reason":"Surface collision has no trustworthy penetration measure.", "clash_type":kind})
                continue
            # Application policy makes the threshold boundary explicit and
            # conservative, independent of the kernel's floating-point boundary.
            if distance_mm <= tolerance_mm + NUMERIC_SLACK_MM: continue
            issues.append(_pair_issue("hard_clash", "warning", "Hard-clash candidate",
                f"{first.is_a()} #{first.id()} versus {second.is_a()} #{second.id()}: kernel {kind} distance {distance_mm:.3f} mm exceeds the {tolerance_mm:g} mm screening threshold. Review coordination intent.",
                first, second, selection_ids=[first.id(),second.id()], distance_mm=distance_mm,
                tolerance_mm=tolerance_mm, clash_type=kind, witness_points_metres=[list(clash.p1),list(clash.p2)],
                review_status="unresolved", detection_basis="IfcOpenShell intersection of manifold tessellated bodies; not AABB overlap"))
    issues.sort(key=lambda i: (i["entity_id"],i["related_entity_id"]))
    groups_available = bool(mep and structure)
    return {"stage":3, "app_version":APP_VERSION, "engine":"ifcopenshell", "engine_version":ifcopenshell.version,
        "schema":model.schema, "generated_at":datetime.now(timezone.utc).isoformat(),
        "scope":"MEP versus structure" if element_ids is None else "Selected IDs; MEP versus structure only",
        "selected_element_ids":sorted(eligible), "tolerance_mm":tolerance_mm, "numeric_slack_mm":NUMERIC_SLACK_MM,
        "settings":{"use_world_coords":True,"disable_opening_subtractions":False,"check_all":True},
        "extraction_complete_for_selected_scope":groups_available and not skipped,
        "complete_for_selected_scope":False,
        "detection_completeness_status":"not_certified_reference_gate_required",
        "scope_status":"evaluated" if groups_available else "not_evaluated_missing_group",
        "summary":{"eligible_elements":len(eligible),"measured_elements":len(measured),"mep_elements":len(mep),"structural_elements":len(structure),"candidate_pairs":len(issues),"skipped_elements":len(skipped),"unresolved_collisions":len(unresolved),"triangles":triangles},
        "issues":issues,"skipped_elements":skipped,"unresolved_collisions":unresolved,"duration_ms":round((perf_counter()-started)*1000,1),
        "rule_source":"IfcOpenShell clash_intersection_many; application threshold, not an industry acceptance limit.",
        "claim_boundary":"Diagnostic kernel probe, not a released model clash verdict. Known aligned-overlap false negatives must be resolved before Stage 3 is enabled. Kernel protrusion/pierce distance is not overlap volume or a universal minimum-translation distance. IFC opening subtractions are enabled. No clearance, self-clash, project approval or author intent verdict. Missing/non-manifold geometry and absent groups remain Not evaluated; zero candidates does not prove a clash-free project."}


def run_hard_clashes_file(path, tolerance_mm=2., element_ids=None, source_sha256=None):
    import ifcopenshell
    path=Path(path)
    result=run_hard_clash_model(ifcopenshell.open(str(path)), tolerance_mm, element_ids)
    result["source_sha256"]=source_sha256 or sha256(path.read_bytes()).hexdigest()
    return result


def run_hard_clashes_text(content, tolerance_mm=2., element_ids=None):
    import ifcopenshell
    result=run_hard_clash_model(ifcopenshell.file.from_string(content), tolerance_mm, element_ids)
    result["source_sha256"]=sha256(content.encode()).hexdigest()
    return result
