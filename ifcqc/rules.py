"""Deterministic IFC quality rules."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from typing import Callable

from .parser import Entity, IfcModel, REFERENCE_RE


PRODUCT_PREFIXES = (
    "IFCWALL", "IFCSLAB", "IFCBEAM", "IFCCOLUMN", "IFCDOOR", "IFCWINDOW",
    "IFCROOF", "IFCSTAIR", "IFCRAILING", "IFCFURNISHINGELEMENT",
    "IFCFLOW", "IFCDISTRIBUTION", "IFCENERGYCONVERSIONDEVICE",
)


@dataclass(frozen=True)
class Issue:
    rule_id: str
    severity: str
    title: str
    message: str
    entity_id: int | None = None
    entity_type: str | None = None
    global_id: str | None = None
    name: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def is_product(entity: Entity) -> bool:
    return entity.type_name.startswith(PRODUCT_PREFIXES) and not entity.type_name.endswith("TYPE")


def related_object_ids(relation: Entity) -> set[int]:
    """Read RelatedObjects, the fifth root-relation attribute."""
    if len(relation.args) < 5:
        return set()
    return {int(value) for value in REFERENCE_RE.findall(relation.args[4])}


def missing_names(model: IfcModel) -> list[Issue]:
    return [
        Issue(
            "missing_name", "warning", "Missing element name",
            f"{entity.type_name} {entity.ref} has no Name value.",
            entity.step_id, entity.type_name, entity.global_id, entity.name,
        )
        for entity in model.entities if is_product(entity) and not entity.name
    ]


def duplicate_global_ids(model: IfcModel) -> list[Issue]:
    grouped: dict[str, list[Entity]] = defaultdict(list)
    for entity in model.entities:
        if entity.global_id:
            grouped[entity.global_id].append(entity)
    issues: list[Issue] = []
    for global_id, entities in grouped.items():
        if len(entities) < 2:
            continue
        for entity in entities:
            issues.append(Issue(
                "duplicate_global_id", "error", "Duplicate GlobalId",
                f"GlobalId {global_id} is used by {len(entities)} entities.",
                entity.step_id, entity.type_name, global_id, entity.name,
            ))
    return issues


def missing_containment(model: IfcModel) -> list[Issue]:
    contained: set[int] = set()
    for relation in model.of_type("IFCRELCONTAINEDINSPATIALSTRUCTURE"):
        contained.update(related_object_ids(relation))
    return [
        Issue(
            "missing_spatial_containment", "error", "Missing spatial containment",
            f"{entity.type_name} {entity.ref} is not assigned to a spatial container.",
            entity.step_id, entity.type_name, entity.global_id, entity.name,
        )
        for entity in model.entities if is_product(entity) and entity.step_id not in contained
    ]


def missing_type_assignments(model: IfcModel) -> list[Issue]:
    typed: set[int] = set()
    for relation in model.of_type("IFCRELDEFINESBYTYPE"):
        typed.update(related_object_ids(relation))
    return [
        Issue(
            "missing_type", "info", "No type assignment",
            f"{entity.type_name} {entity.ref} has no IfcType assignment.",
            entity.step_id, entity.type_name, entity.global_id, entity.name,
        )
        for entity in model.entities if is_product(entity) and entity.step_id not in typed
    ]


def missing_classifications(model: IfcModel) -> list[Issue]:
    classified: set[int] = set()
    for relation in model.of_type("IFCRELASSOCIATESCLASSIFICATION"):
        classified.update(related_object_ids(relation))
    return [
        Issue(
            "missing_classification", "info", "No classification",
            f"{entity.type_name} {entity.ref} has no classification association.",
            entity.step_id, entity.type_name, entity.global_id, entity.name,
        )
        for entity in model.entities if is_product(entity) and entity.step_id not in classified
    ]


RULES: tuple[Callable[[IfcModel], list[Issue]], ...] = (
    duplicate_global_ids,
    missing_containment,
    missing_names,
    missing_type_assignments,
    missing_classifications,
)

RULE_BY_ID = {
    "duplicate_global_id": duplicate_global_ids,
    "missing_spatial_containment": missing_containment,
    "missing_name": missing_names,
    "missing_type": missing_type_assignments,
    "missing_classification": missing_classifications,
}

PROFILES = {
    "coordination": tuple(RULE_BY_ID),
    "handover": ("missing_name", "missing_type", "missing_classification"),
    "model_health": ("duplicate_global_id", "missing_spatial_containment", "missing_name"),
}


def run_rules(model: IfcModel, enabled_rule_ids: tuple[str, ...] | None = None) -> list[Issue]:
    selected = enabled_rule_ids or tuple(RULE_BY_ID)
    unknown = set(selected) - set(RULE_BY_ID)
    if unknown:
        raise ValueError(f"Unknown QC rules: {', '.join(sorted(unknown))}")
    issues = [issue for rule_id in selected for issue in RULE_BY_ID[rule_id](model)]
    order = {"error": 0, "warning": 1, "info": 2}
    return sorted(issues, key=lambda issue: (order[issue.severity], issue.rule_id, issue.entity_id or 0))


def issue_summary(issues: list[Issue]) -> dict[str, int]:
    counts = Counter(issue.severity for issue in issues)
    return {key: counts.get(key, 0) for key in ("error", "warning", "info")}
