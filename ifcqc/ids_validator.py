"""Dependency-free IDS validation for a deliberately small, honest subset.

The validator understands entity applicability and presence requirements for
the three stable IfcRoot attributes. It reports unsupported facets rather than
silently treating them as satisfied.
"""

from __future__ import annotations

from dataclasses import dataclass
from xml.etree import ElementTree as ET

from .parser import Entity, IfcModel, parse_ifc, unquote
from .rules import Issue


SUPPORTED_ATTRIBUTES = {"GLOBALID": 0, "NAME": 2, "DESCRIPTION": 3}


def _local(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1].lower()


def _children(element: ET.Element, name: str) -> list[ET.Element]:
    wanted = name.lower()
    return [child for child in element.iter() if _local(child) == wanted]


def _restriction_values(element: ET.Element) -> list[str]:
    simple = [node.text.strip() for node in _children(element, "simpleValue") if node.text and node.text.strip()]
    if simple:
        return simple
    return [
        node.attrib["value"].strip()
        for node in _children(element, "enumeration")
        if node.attrib.get("value", "").strip()
    ]


def _named_values(facet: ET.Element, child_name: str) -> list[str]:
    direct = next((child for child in facet if _local(child) == child_name.lower()), None)
    return _restriction_values(direct) if direct is not None else []


def _attribute_value(entity: Entity, name: str) -> str | None:
    index = SUPPORTED_ATTRIBUTES.get(name.upper())
    if index is None or len(entity.args) <= index:
        return None
    value = unquote(entity.args[index])
    return None if value in {"", "$", "*"} else value


@dataclass(frozen=True)
class ParsedSpecification:
    name: str
    identifier: str
    entity_types: tuple[str, ...]
    attributes: tuple[tuple[str, str, tuple[str, ...]], ...]
    min_occurs: int
    unsupported: tuple[str, ...]


def _parse_specification(node: ET.Element, index: int) -> ParsedSpecification:
    name = node.attrib.get("name") or f"Specification {index}"
    identifier = node.attrib.get("identifier") or f"spec-{index}"
    applicability = next((child for child in node if _local(child) == "applicability"), None)
    requirements = next((child for child in node if _local(child) == "requirements"), None)
    entity_types: list[str] = []
    unsupported: list[str] = []

    if applicability is not None:
        for facet in applicability:
            facet_name = _local(facet)
            if facet_name == "entity":
                entity_types.extend(value.upper() for value in _named_values(facet, "name"))
            else:
                unsupported.append(f"applicability:{facet_name}")

    attributes: list[tuple[str, str, tuple[str, ...]]] = []
    if requirements is not None:
        for facet in requirements:
            facet_name = _local(facet)
            if facet_name != "attribute":
                unsupported.append(f"requirement:{facet_name}")
                continue
            names = _named_values(facet, "name")
            cardinality = facet.attrib.get("cardinality", "required").lower()
            values = tuple(_named_values(facet, "value"))
            for attribute_name in names:
                if attribute_name.upper() not in SUPPORTED_ATTRIBUTES:
                    unsupported.append(f"attribute:{attribute_name}")
                else:
                    attributes.append((attribute_name, cardinality, values))

    raw_min = applicability.attrib.get("minOccurs", "0") if applicability is not None else "0"
    try:
        min_occurs = max(0, int(raw_min))
    except ValueError:
        min_occurs = 0
    return ParsedSpecification(
        name, identifier, tuple(dict.fromkeys(entity_types)), tuple(attributes), min_occurs,
        tuple(dict.fromkeys(unsupported)),
    )


def _issue(spec: ParsedSpecification, entity: Entity | None, title: str, message: str) -> Issue:
    return Issue(
        f"ids:{spec.identifier}", "error", title, message,
        entity.step_id if entity else None,
        entity.type_name if entity else None,
        entity.global_id if entity else None,
        entity.name if entity else None,
    )


def validate_ids(ifc_text: str, ids_text: str, filename: str = "requirements.ids") -> dict:
    """Validate an IFC model against the supported offline IDS subset."""
    model = parse_ifc(ifc_text)
    try:
        root = ET.fromstring(ids_text)
    except ET.ParseError as exc:
        raise ValueError(f"The IDS XML is not valid: {exc}") from exc
    if _local(root) != "ids":
        raise ValueError("The requirements file does not have an IDS root element.")

    specification_nodes = _children(root, "specification")
    if not specification_nodes:
        raise ValueError("No IDS specifications were found.")

    all_issues: list[Issue] = []
    results: list[dict] = []
    unsupported_all: list[str] = []
    for index, node in enumerate(specification_nodes, 1):
        spec = _parse_specification(node, index)
        applicable = [
            entity for entity in model.entities
            if not spec.entity_types or entity.type_name in spec.entity_types
        ]
        issues: list[Issue] = []
        if len(applicable) < spec.min_occurs:
            issues.append(_issue(
                spec, None, "IDS applicability not satisfied",
                f"{spec.name} requires at least {spec.min_occurs} applicable object(s); found {len(applicable)}.",
            ))
        for entity in applicable:
            for attribute_name, cardinality, allowed_values in spec.attributes:
                value = _attribute_value(entity, attribute_name)
                if cardinality == "prohibited" and value is not None:
                    issues.append(_issue(
                        spec, entity, f"Prohibited {attribute_name} value",
                        f"{entity.type_name} {entity.ref} must not provide {attribute_name}.",
                    ))
                elif cardinality != "optional" and value is None:
                    issues.append(_issue(
                        spec, entity, f"Missing required {attribute_name}",
                        f"{entity.type_name} {entity.ref} requires an IDS {attribute_name} value.",
                    ))
                elif value is not None and allowed_values and value not in allowed_values:
                    issues.append(_issue(
                        spec, entity, f"Invalid {attribute_name} value",
                        f"{entity.type_name} {entity.ref} has {attribute_name} '{value}', which is not allowed by the IDS.",
                    ))
        all_issues.extend(issues)
        unsupported_all.extend(spec.unsupported)
        results.append({
            "name": spec.name,
            "identifier": spec.identifier,
            "applicable": len(applicable),
            "failed": len(issues),
            "passed": max(0, len(applicable) - len({issue.entity_id for issue in issues if issue.entity_id is not None})),
            "unsupported": list(spec.unsupported),
        })

    unsupported = list(dict.fromkeys(unsupported_all))
    return {
        "filename": filename,
        "engine": "builtin-ids-subset",
        "complete": not unsupported,
        "summary": {
            "specifications": len(results),
            "applicable": sum(result["applicable"] for result in results),
            "passed": sum(result["passed"] for result in results),
            "failed": len(all_issues),
            "unsupported_facets": len(unsupported),
        },
        "unsupported": unsupported,
        "specifications": results,
        "issues": [issue.to_dict() for issue in all_issues],
    }
