"""IfcOpenShell-backed semantic model rules and selection metadata."""

from __future__ import annotations

from collections import defaultdict

from .rules import Issue, PROFILES


def quality_elements(model) -> list:
    """Return physical/logical elements suitable for element-level QC.

    Feature elements such as openings are operands used to modify a host rather
    than independently visible building elements, so they are not subjected to
    normal element-information rules.
    """
    return [
        element for element in model.by_type("IfcElement")
        if not element.is_a("IfcFeatureElement")
    ]


def _issue(rule: str, severity: str, title: str, message: str, entity) -> Issue:
    return Issue(
        rule, severity, title, message, entity.id(), entity.is_a().upper(),
        getattr(entity, "GlobalId", None), getattr(entity, "Name", None),
    )


def _parents(element) -> list:
    parents = []
    for inverse_name in ("Decomposes", "Nests"):
        for relation in getattr(element, inverse_name, ()) or ():
            parent = getattr(relation, "RelatingObject", None)
            if parent is not None:
                parents.append(parent)
    return parents


def _has_spatial_assignment(element) -> bool:
    pending = [element]
    visited = set()
    while pending:
        candidate = pending.pop()
        if candidate.id() in visited:
            continue
        visited.add(candidate.id())
        if getattr(candidate, "ContainedInStructure", ()):
            return True
        pending.extend(_parents(candidate))
    return False


def _get_type(element):
    try:
        import ifcopenshell.util.element

        return ifcopenshell.util.element.get_type(element)
    except (AttributeError, TypeError):
        return None


def _has_classification(element) -> bool:
    candidates = [element]
    element_type = _get_type(element)
    if element_type is not None:
        candidates.append(element_type)
    return any(
        relation.is_a("IfcRelAssociatesClassification")
        for candidate in candidates
        for relation in (getattr(candidate, "HasAssociations", ()) or ())
    )


def duplicate_global_ids(model) -> list[Issue]:
    grouped = defaultdict(list)
    for entity in model.by_type("IfcRoot"):
        global_id = getattr(entity, "GlobalId", None)
        if global_id:
            grouped[str(global_id)].append(entity)
    return [
        _issue(
            "duplicate_global_id", "error", "Duplicate GlobalId",
            f"GlobalId {global_id} is used by {len(grouped_entities)} IfcRoot entities.",
            entity,
        )
        for global_id, grouped_entities in grouped.items() if len(grouped_entities) > 1
        for entity in grouped_entities
    ]


def missing_containment(model) -> list[Issue]:
    return [
        _issue(
            "missing_spatial_containment", "error", "Missing spatial containment",
            f"{element.is_a()} #{element.id()} is not contained directly or through an aggregate.",
            element,
        )
        for element in quality_elements(model) if not _has_spatial_assignment(element)
    ]


def missing_names(model) -> list[Issue]:
    return [
        _issue(
            "missing_name", "warning", "Missing element name",
            f"{element.is_a()} #{element.id()} has no Name value.", element,
        )
        for element in quality_elements(model) if not getattr(element, "Name", None)
    ]


def missing_type_assignments(model) -> list[Issue]:
    return [
        _issue(
            "missing_type", "info", "No type assignment",
            f"{element.is_a()} #{element.id()} has no IfcType assignment.", element,
        )
        for element in quality_elements(model) if _get_type(element) is None
    ]


def missing_classifications(model) -> list[Issue]:
    return [
        _issue(
            "missing_classification", "info", "No classification",
            f"{element.is_a()} #{element.id()} has no classification association.", element,
        )
        for element in quality_elements(model) if not _has_classification(element)
    ]


RULE_BY_ID = {
    "duplicate_global_id": duplicate_global_ids,
    "missing_spatial_containment": missing_containment,
    "missing_name": missing_names,
    "missing_type": missing_type_assignments,
    "missing_classification": missing_classifications,
}


def run_semantic_rules(model, enabled_rule_ids: tuple[str, ...]) -> list[Issue]:
    unknown = set(enabled_rule_ids) - set(RULE_BY_ID)
    if unknown:
        raise ValueError(f"Unknown QC rules: {', '.join(sorted(unknown))}")
    issues = [
        issue for rule_id in enabled_rule_ids
        for issue in RULE_BY_ID[rule_id](model)
    ]
    order = {"error": 0, "warning": 1, "info": 2}
    return sorted(
        issues,
        key=lambda issue: (order.get(issue.severity, 9), issue.rule_id, issue.entity_id or 0),
    )


def _geometric_descendants(element) -> list[int]:
    targets = []
    pending = [element]
    visited = {element.id()}
    while pending:
        candidate = pending.pop()
        for inverse_name in ("IsDecomposedBy", "IsNestedBy"):
            for relation in getattr(candidate, inverse_name, ()) or ():
                for child in getattr(relation, "RelatedObjects", ()) or ():
                    if child.id() in visited:
                        continue
                    visited.add(child.id())
                    if getattr(child, "Representation", None):
                        targets.append(child.id())
                    pending.append(child)
    return sorted(set(targets))


def selection_metadata(entity) -> dict:
    """Describe how an IFC entity can be represented in the browser viewer."""
    if entity is None or not entity.is_a("IfcProduct"):
        return {
            "geometry_status": "metadata_only",
            "selection_ids": [],
            "geometry_message": "This IFC record is metadata or a relationship, not a 3D product.",
        }
    if entity.is_a("IfcFeatureElementSubtraction"):
        hosts = sorted({
            relation.RelatingBuildingElement.id()
            for relation in (getattr(entity, "VoidsElements", ()) or ())
            if getattr(relation, "RelatingBuildingElement", None) is not None
        })
        return {
            "geometry_status": "void_feature",
            "selection_ids": hosts,
            "geometry_message": (
                "This is a subtractive void feature. Its host element is selected because "
                "the opening is not normally rendered as a separate solid."
            ),
        }
    if getattr(entity, "Representation", None):
        return {
            "geometry_status": "direct",
            "selection_ids": [entity.id()],
            "geometry_message": "The IFC product has a direct geometric representation.",
        }
    descendants = _geometric_descendants(entity)
    if descendants:
        return {
            "geometry_status": "children",
            "selection_ids": descendants,
            "geometry_message": (
                f"The parent has no direct solid; {len(descendants)} geometric child "
                "element(s) are selected instead."
            ),
        }
    return {
        "geometry_status": "no_representation",
        "selection_ids": [],
        "geometry_message": "The IFC product has no direct representation or geometric child.",
    }


def profile_rules(profile: str) -> tuple[str, ...]:
    if profile not in PROFILES:
        raise ValueError(f"Unknown QC profile: {profile}")
    return PROFILES[profile]
