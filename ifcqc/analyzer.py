"""Application-facing IFC analysis service."""

from collections import Counter

from .backends import inspect_with_ifcopenshell
from .parser import parse_ifc
from .rules import PROFILES, is_product, issue_summary, run_rules


def analyze_ifc(text: str, filename: str = "model.ifc", profile: str = "coordination") -> dict:
    model = parse_ifc(text)
    backend = inspect_with_ifcopenshell(text)
    if profile not in PROFILES:
        raise ValueError(f"Unknown QC profile: {profile}")
    enabled_rules = PROFILES[profile]
    issues = run_rules(model, enabled_rules)
    type_counts = Counter(entity.type_name for entity in model.entities)
    products = [entity for entity in model.entities if is_product(entity)]
    spatial = [
        entity for entity in model.entities
        if entity.type_name in {"IFCSITE", "IFCBUILDING", "IFCBUILDINGSTOREY", "IFCSPACE"}
    ]
    return {
        "filename": filename,
        "schema": model.schema,
        "profile": profile,
        "backend": backend,
        "enabled_rules": list(enabled_rules),
        "summary": {
            "entities": len(model.entities),
            "products": len(products),
            "spatial_elements": len(spatial),
            "issues": len(issues),
            **issue_summary(issues),
        },
        "type_counts": [
            {"type": type_name, "count": count}
            for type_name, count in type_counts.most_common(12)
        ],
        "elements": [
            {
                "step_id": entity.step_id,
                "type": entity.type_name,
                "global_id": entity.global_id,
                "name": entity.name,
            }
            for entity in products[:500]
        ],
        "issues": [issue.to_dict() for issue in issues],
    }
