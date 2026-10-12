"""Read-only, targeted comparison of two IFC products."""

from __future__ import annotations

from hashlib import sha256
from math import isclose, isfinite
from pathlib import Path


def validate_pair_ids(ids) -> list[int]:
    if not isinstance(ids, list) or len(ids) != 2:
        raise ValueError("Select exactly two IFC element IDs.")
    if any(type(value) is not int or value <= 0 for value in ids) or ids[0] == ids[1]:
        raise ValueError("Pair IDs must be two distinct positive integers.")
    return ids


def _json_value(value):
    if isinstance(value, float):
        return value if isfinite(value) else None
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(k): _json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(v) for v in value]
    return str(value)


def _equal(a, b, absolute=1e-9):
    if type(a) is bool or type(b) is bool:
        return type(a) is type(b) and a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return isclose(a, b, rel_tol=1e-9, abs_tol=absolute)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_equal(x, y, absolute) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_equal(a[k], b[k], absolute) for k in a)
    return a == b


def _row(key, label, a, b, *, identity=False, absolute=1e-9, applicable=(True, True)):
    if not any(applicable):
        status = "not_applicable"
    elif not all(applicable):
        status = "not_evaluated"
    elif a is None or b is None:
        status = "not_evaluated" if a is None and b is None else "missing"
    else:
        status = "same" if _equal(a, b, absolute) else "different"
    return {"key": key, "label": label, "a": a, "b": b,
            "status": status, "category": "identity" if identity else "physical",
            "a_applicable": applicable[0], "b_applicable": applicable[1]}


def _opening_hosts(element):
    """Resolve explicit void relationships; never infer a host from a name or proximity."""
    import ifcopenshell.util.element as util

    if not element.is_a("IfcOpeningElement"):
        return None
    hosts = {}
    for rel in getattr(element, "VoidsElements", ()):
        host = rel.RelatingBuildingElement
        if host is None:
            continue
        typ = util.get_type(host)
        hosts[host.id()] = {
            "step_id": host.id(), "class": host.is_a(), "name": host.Name,
            "global_id": host.GlobalId, "tag": getattr(host, "Tag", None),
            "type_name": typ.Name if typ else None,
        }
    return [hosts[key] for key in sorted(hosts)] or None


def _element(model, element):
    import numpy as np
    import ifcopenshell.geom
    import ifcopenshell.util.element as util
    import ifcopenshell.util.placement as placement
    import ifcopenshell.util.shape as shape_util
    import ifcopenshell.util.unit as unit

    typ = util.get_type(element)
    container = util.get_container(element, ifc_class="IfcBuildingStorey")
    psets = {}
    for scope, obj in (("Occurrence", element), ("Type", typ)):
        if obj is not None:
            for name, props in util.get_psets(obj, should_inherit=False).items():
                for key, value in props.items():
                    if key != "id":
                        psets[f"{scope} · {name}.{key}"] = _json_value(value)
    phases = {key: value for key, value in psets.items()
              if any(term in key.lower() for term in ("phase", "status", "designoption", "design option"))}
    parents = [rel.RelatingObject for rel in (*element.Decomposes, *getattr(element, "Nests", ()))]
    data = {
        "step_id": element.id(), "name": element.Name, "class": element.is_a(),
        "global_id": element.GlobalId, "tag": getattr(element, "Tag", None),
        "type_name": typ.Name if typ else None, "type_id": typ.id() if typ else None,
        "type_tag": getattr(typ, "Tag", None) if typ else None,
        "material": sorted({mat.Name for mat in util.get_materials(element) if mat.Name}) or None,
        "storey": {"name": container.Name, "global_id": container.GlobalId} if container else None,
        "load_bearing": util.get_pset(element, "Pset_ColumnCommon", "LoadBearing"),
        "phase_status": phases or None,
        "assembly_parent": [f"{p.is_a()} #{p.id()} · {p.Name or 'Unnamed'}" for p in parents] or None,
        "properties": psets, "dimensions_mm": None, "position_metres": None,
        "geometry_status": "not_evaluated", "geometry_message": "No Body representation supplied.",
        "is_opening": element.is_a("IfcOpeningElement"),
        "opening_hosts": _opening_hosts(element),
    }
    # LoadBearing occurs in several common property sets, not just columns.
    load_values = [value for key, value in psets.items() if key.endswith(".LoadBearing")]
    if load_values:
        data["load_bearing"] = load_values[0] if all(v == load_values[0] for v in load_values) else load_values
    if element.Representation is not None:
        try:
            settings = ifcopenshell.geom.settings()
            settings.set("use-world-coords", True)
            shape = ifcopenshell.geom.create_shape(settings, element)
            vertices = shape_util.get_vertices(shape.geometry)
            if not len(vertices) or not np.isfinite(vertices).all():
                raise ValueError("No finite vertices were returned.")
            minimum, maximum = vertices.min(axis=0), vertices.max(axis=0)
            data["position_metres"] = ((minimum + maximum) / 2).tolist()
            if element.ObjectPlacement is not None:
                matrix = placement.get_local_placement(element.ObjectPlacement).copy()
                matrix[:3, 3] *= unit.calculate_unit_scale(model)
                homogeneous = np.column_stack((vertices, np.ones(len(vertices))))
                local = (np.linalg.inv(matrix) @ homogeneous.T).T[:, :3]
                data["dimensions_mm"] = ((local.max(axis=0) - local.min(axis=0)) * 1000).tolist()
            data["geometry_status"] = "measured"
            data["geometry_message"] = "Fresh targeted tessellation; dimensions are bounds along occurrence axes, not nominal sizes."
        except Exception as exc:
            data["geometry_status"] = "unavailable"
            data["geometry_message"] = f"Targeted extraction did not produce usable geometry: {str(exc)[:400]}"
    return data


def compare_model_elements(model, ids: list[int]) -> dict:
    validate_pair_ids(ids)
    elements = []
    for value in ids:
        try:
            element = model.by_id(value)
        except RuntimeError:
            element = None
        if element is None or not element.is_a("IfcElement"):
            raise ValueError(f"#{value} is not an IFC element in this model.")
        elements.append(_element(model, element))
    a, b = elements
    definitions = [
        ("class", "IFC class", False), ("type_name", "Assigned type name", False),
        ("material", "Material names", False), ("storey", "Containing storey", False),
        ("load_bearing", "Load-bearing", False),
        ("dimensions_mm", "Dimensions X / Y / Z (mm, occurrence axes)", False),
        ("position_metres", "World bounds centre X / Y / Z (m)", False),
        ("phase_status", "Exported phase / status", False),
        ("assembly_parent", "Assembly / nested parent", False),
        ("global_id", "GlobalId", True), ("tag", "Element Tag", True),
        ("type_id", "Type record ID", True), ("type_tag", "Type Tag", True),
    ]
    void_fields = {"type_name", "type_id", "type_tag", "material", "load_bearing"}
    rows = [_row(key, label, a[key], b[key], identity=identity,
                 applicable=tuple(not (e["is_opening"] and key in void_fields and e[key] is None)
                                  for e in elements),
                 absolute=0.001 if key == "dimensions_mm" else 1e-6 if key == "position_metres" else 1e-9)
            for key, label, identity in definitions]
    if a["is_opening"] or b["is_opening"]:
        host_row = _row("opening_hosts", "Host element (IfcRelVoidsElement)", a["opening_hosts"], b["opening_hosts"],
                        applicable=(a["is_opening"], b["is_opening"]))
        host_row["category"] = "context"
        rows.insert(2, host_row)
    keys = sorted(a["properties"].keys() | b["properties"].keys())
    property_rows = [_row(key, key, a["properties"].get(key), b["properties"].get(key)) for key in keys]
    physical = [row for row in rows if row["category"] == "physical"]
    return {
        "schema": model.schema, "engine": "ifcopenshell", "elements": elements,
        "rows": rows, "property_rows": property_rows[:500],
        "property_rows_total": len(property_rows), "property_rows_truncated": len(property_rows) > 500,
        "physical_difference_count": sum(row["status"] == "different" for row in physical),
        "property_difference_count": sum(row["status"] == "different" for row in property_rows),
        "not_evaluated_count": sum(row["status"] in {"not_evaluated", "missing"} for row in physical),
        "not_applicable_count": sum(row["status"] == "not_applicable" for row in physical),
        "host_entity_ids": sorted({host["step_id"] for e in elements for host in e["opening_hosts"] or []}),
        "length_unit_scale_to_metres": _length_scale(model),
        "claim_boundary": "Matching properties or bounds do not prove full shape equality or author intent. Review decisions are unchanged.",
    }


def _length_scale(model):
    import ifcopenshell.util.unit
    return ifcopenshell.util.unit.calculate_unit_scale(model)


def compare_elements_file(path: Path, ids: list[int], source_sha256: str | None = None) -> dict:
    validate_pair_ids(ids)
    import ifcopenshell
    result = compare_model_elements(ifcopenshell.open(str(path)), ids)
    result["source_sha256"] = source_sha256 or sha256(path.read_bytes()).hexdigest()
    return result


def compare_elements(ifc_text: str, ids: list[int]) -> dict:
    validate_pair_ids(ids)
    import ifcopenshell
    result = compare_model_elements(ifcopenshell.file.from_string(ifc_text), ids)
    result["source_sha256"] = sha256(ifc_text.encode("utf-8")).hexdigest()
    return result
