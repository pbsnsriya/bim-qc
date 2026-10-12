"""Application-facing IfcOpenShell semantic analysis service."""

from pathlib import Path

from collections import Counter

from .rules import issue_summary
from .semantic_rules import (
    profile_rules, quality_elements, run_semantic_rules, selection_metadata,
)


def _analyze_model(model, filename: str, profile: str) -> dict:
    """Build the application result from an already-open IfcOpenShell model."""
    import ifcopenshell

    enabled_rules = profile_rules(profile)
    issues = run_semantic_rules(model, enabled_rules)
    products = quality_elements(model)
    try:
        spatial = list(model.by_type("IfcSpatialElement"))
    except RuntimeError:  # IFC2X3 uses the older superclass name.
        spatial = list(model.by_type("IfcSpatialStructureElement"))
    type_counts = Counter(entity.is_a().upper() for entity in products)
    entities_by_id = {entity.id(): entity for entity in model}
    entity_count = len(entities_by_id)

    element_rows = []
    for entity in products:
        element_rows.append({
            "step_id": entity.id(),
            "type": entity.is_a().upper(),
            "global_id": getattr(entity, "GlobalId", None),
            "name": getattr(entity, "Name", None),
            **selection_metadata(entity),
        })

    issue_rows = []
    for issue in issues:
        row = issue.to_dict()
        row.update(selection_metadata(entities_by_id.get(issue.entity_id)))
        issue_rows.append(row)
    return {
        "filename": filename,
        "schema": model.schema,
        "profile": profile,
        "backend": {
            "engine": "ifcopenshell",
            "available": True,
            "version": str(getattr(ifcopenshell, "version", "unknown")),
            "schema": model.schema,
            "entities": entity_count,
            "products": len(products),
        },
        "enabled_rules": list(enabled_rules),
        "summary": {
            "entities": entity_count,
            "products": len(products),
            "spatial_elements": len(spatial),
            "issues": len(issues),
            **issue_summary(issues),
        },
        "type_counts": [
            {"type": type_name, "count": count}
            for type_name, count in type_counts.most_common(12)
        ],
        "elements": element_rows,
        "issues": issue_rows,
    }


def analyze_ifc(text: str, filename: str = "model.ifc", profile: str = "coordination") -> dict:
    try:
        import ifcopenshell
    except ImportError as exc:
        raise RuntimeError("IfcOpenShell is required for semantic IFC analysis.") from exc
    try:
        model = ifcopenshell.file.from_string(text)
    except Exception as exc:
        raise ValueError(f"IfcOpenShell could not open this IFC model: {exc}") from exc

    return _analyze_model(model, filename, profile)


def analyze_ifc_file(path: str | Path, filename: str = "model.ifc", profile: str = "coordination") -> dict:
    """Analyse an IFC directly from disk, avoiding a second 100 MB text copy."""
    try:
        import ifcopenshell
    except ImportError as exc:
        raise RuntimeError("IfcOpenShell is required for semantic IFC analysis.") from exc
    try:
        model = ifcopenshell.open(str(path))
    except Exception as exc:
        raise ValueError(f"IfcOpenShell could not open this IFC model: {exc}") from exc
    return _analyze_model(model, filename, profile)
