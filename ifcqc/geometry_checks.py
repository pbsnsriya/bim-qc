"""IfcOpenShell-backed geometry and coordination quality checks."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from math import acos, degrees
from os import cpu_count

from .rules import Issue, issue_summary


STRUCTURAL_CLASSES = (
    "IfcWall", "IfcSlab", "IfcBeam", "IfcColumn", "IfcFooting",
    "IfcPile", "IfcRoof", "IfcRamp", "IfcStair",
)
ALIGNMENT_CLASSES = (
    "IfcWall", "IfcBeam", "IfcColumn", "IfcMember", "IfcPipeSegment",
    "IfcDuctSegment", "IfcCableCarrierSegment",
)
EXACT_DUPLICATE_TOLERANCE_METRES = 0.000001


@dataclass(frozen=True)
class GeometryConfig:
    identifiers: bool = True
    hard_clashes: bool = True
    clearance_clashes: bool = True
    duplicates: bool = True
    connectivity: bool = True
    alignment: bool = True
    dimensions: bool = True
    hard_tolerance_mm: float = 2.0
    clearance_mm: float = 50.0
    alignment_tolerance_degrees: float = 1.0
    minimum_dimension_mm: float = 5.0

    @classmethod
    def from_dict(cls, raw: dict | None) -> "GeometryConfig":
        raw = raw or {}

        def number(name: str, default: float, low: float, high: float) -> float:
            try:
                value = float(raw.get(name, default))
            except (TypeError, ValueError):
                raise ValueError(f"{name} must be a number.") from None
            if not low <= value <= high:
                raise ValueError(f"{name} must be between {low} and {high}.")
            return value

        return cls(
            identifiers=bool(raw.get("identifiers", True)),
            hard_clashes=bool(raw.get("hard_clashes", True)),
            clearance_clashes=bool(raw.get("clearance_clashes", True)),
            duplicates=bool(raw.get("duplicates", True)),
            connectivity=bool(raw.get("connectivity", True)),
            alignment=bool(raw.get("alignment", True)),
            dimensions=bool(raw.get("dimensions", True)),
            hard_tolerance_mm=number("hard_tolerance_mm", 2.0, 0.0, 1000.0),
            clearance_mm=number("clearance_mm", 50.0, 0.0, 10_000.0),
            alignment_tolerance_degrees=number(
                "alignment_tolerance_degrees", 1.0, 0.0, 45.0,
            ),
            minimum_dimension_mm=number("minimum_dimension_mm", 5.0, 0.0, 10_000.0),
        )


def _issue(rule: str, severity: str, title: str, message: str, entity, **extra) -> dict:
    item = Issue(
        rule, severity, title, message,
        entity.id() if entity is not None else None,
        entity.is_a() if entity is not None else None,
        getattr(entity, "GlobalId", None) if entity is not None else None,
        getattr(entity, "Name", None) if entity is not None else None,
    ).to_dict()
    item.update(extra)
    return item


def _physical_products(model) -> list:
    return [
        element for element in model.by_type("IfcProduct")
        if not element.is_a("IfcSpatialStructureElement")
        and not element.is_a("IfcAnnotation")
    ]


def _shape_data(model):
    import ifcopenshell.geom
    import numpy as np

    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    product_count = len(model.by_type("IfcProduct"))
    threads = 1 if product_count > 500 else max(1, min(cpu_count() or 1, 8))
    iterator = ifcopenshell.geom.iterator(settings, model, threads)
    shapes: dict[int, object] = {}
    vertices: dict[int, object] = {}
    tree = ifcopenshell.geom.tree()
    if iterator.initialize():
        while True:
            shape = iterator.get()
            shapes[shape.id] = shape
            verts = np.asarray(shape.geometry.verts, dtype=float).reshape((-1, 3))
            vertices[shape.id] = verts
            tree.add_element(shape)
            if not iterator.next():
                break
    return shapes, vertices, tree


def _pair_issue(rule: str, severity: str, title: str, message: str, first, second, **extra):
    return _issue(
        rule, severity, title, message, first,
        related_entity_id=second.id(),
        related_entity_type=second.is_a(),
        related_global_id=getattr(second, "GlobalId", None),
        **extra,
    )


def _identifier_issues(products: list) -> list[dict]:
    issues: list[dict] = []
    tags: dict[str, list] = defaultdict(list)
    for element in products:
        if not getattr(element, "GlobalId", None):
            issues.append(_issue(
                "missing_global_id", "error", "Missing GlobalId",
                f"{element.is_a()} #{element.id()} has no GlobalId.", element,
            ))
        tag = getattr(element, "Tag", None)
        if tag:
            tags[str(tag).strip().casefold()].append(element)
    for grouped in tags.values():
        if len(grouped) < 2:
            continue
        for element in grouped:
            issues.append(_issue(
                "duplicate_tag", "warning", "Duplicate element tag",
                f"Tag '{getattr(element, 'Tag', '')}' is used by {len(grouped)} elements.",
                element,
            ))
    return issues


def _exact_duplicate_geometry_issues(products: list, vertices: dict[int, object]) -> list[dict]:
    """Return same-class elements with identical tessellated world vertices.

    Coordinates are quantised to one micrometre to absorb floating-point noise.
    A match is deliberately a review candidate, not a claim that one element
    should be deleted: coincident same-class elements can be intentional.
    """
    import numpy as np

    signatures: dict[tuple, list] = defaultdict(list)
    for element in products:
        # Opening/recess geometry is a subtraction operand, not an independently
        # visible building element. It is reviewed separately through its host.
        if element.is_a("IfcFeatureElementSubtraction"):
            continue
        verts = vertices.get(element.id())
        if verts is None or not len(verts):
            continue
        quantised = np.rint(verts / EXACT_DUPLICATE_TOLERANCE_METRES).astype(np.int64)
        ordered = np.asarray(sorted(map(tuple, quantised)), dtype=np.int64)
        signature = (element.is_a(), ordered.shape, ordered.tobytes())
        signatures[signature].append(element)
    issues: list[dict] = []
    for grouped in signatures.values():
        if len(grouped) < 2:
            continue
        original = grouped[0]
        for duplicate in grouped[1:]:
            issues.append(_pair_issue(
                "exact_duplicate_candidate", "warning", "Exact duplicate candidate",
                f"{duplicate.is_a()} #{duplicate.id()} has the same class and world-space "
                f"tessellated geometry as #{original.id()} within 0.001 mm; review both "
                "before deleting either element.",
                duplicate, original,
                confidence="exact_geometry_match",
                tolerance_mm=EXACT_DUPLICATE_TOLERANCE_METRES * 1000,
                selection_ids=[duplicate.id(), original.id()],
                detection_basis="same IFC class and canonical world-space vertex multiset",
            ))
    return issues


def _duplicate_opening_geometry_issues(model, products: list, vertices: dict[int, object]) -> list[dict]:
    """Return coincident subtraction features with selectable host metadata."""
    import numpy as np

    hosts_by_opening: dict[int, list] = defaultdict(list)
    for relation in model.by_type("IfcRelVoidsElement"):
        opening = getattr(relation, "RelatedOpeningElement", None)
        host = getattr(relation, "RelatingBuildingElement", None)
        if opening is not None and host is not None:
            hosts_by_opening[opening.id()].append(host)

    signatures: dict[tuple, list] = defaultdict(list)
    for element in products:
        if not element.is_a("IfcFeatureElementSubtraction"):
            continue
        verts = vertices.get(element.id())
        if verts is None or not len(verts):
            continue
        quantised = np.rint(verts / EXACT_DUPLICATE_TOLERANCE_METRES).astype(np.int64)
        ordered = np.asarray(sorted(map(tuple, quantised)), dtype=np.int64)
        signature = (element.is_a(), ordered.shape, ordered.tobytes())
        signatures[signature].append(element)

    issues: list[dict] = []
    for grouped in signatures.values():
        if len(grouped) < 2:
            continue
        original = grouped[0]
        for duplicate in grouped[1:]:
            duplicate_hosts = hosts_by_opening.get(duplicate.id(), [])
            original_hosts = hosts_by_opening.get(original.id(), [])
            host_ids = list(dict.fromkeys(
                host.id() for host in [*duplicate_hosts, *original_hosts]
            ))
            host_description = ", ".join(
                f"{host.is_a()} #{host.id()}"
                for host in [*duplicate_hosts, *original_hosts]
            ) or "no exported host"
            issues.append(_pair_issue(
                "duplicate_opening_candidate", "warning", "Duplicate opening void candidate",
                f"{duplicate.is_a()} #{duplicate.id()} has the same subtraction geometry as "
                f"#{original.id()} within 0.001 mm. The viewer highlights host element(s): "
                f"{host_description}. Review the openings and hosts before changing either.",
                duplicate, original,
                confidence="exact_subtraction_geometry_match",
                tolerance_mm=EXACT_DUPLICATE_TOLERANCE_METRES * 1000,
                selection_ids=host_ids,
                opening_ids=[duplicate.id(), original.id()],
                host_entity_ids=host_ids,
                detection_basis="same subtraction-feature class and canonical world-space vertex multiset",
            ))
    return issues


def _clash_issues(model, shape_ids: set[int], tree, config: GeometryConfig) -> list[dict]:
    structural = [
        element for class_name in STRUCTURAL_CLASSES for element in model.by_type(class_name)
        if element.id() in shape_ids
    ]
    mep = [
        element for element in model.by_type("IfcDistributionElement")
        if element.id() in shape_ids
    ]
    issues: list[dict] = []
    hard_pairs: set[tuple[int, int]] = set()
    if config.hard_clashes and structural and mep:
        clashes = tree.clash_intersection_many(
            mep, structural, tolerance=config.hard_tolerance_mm / 1000.0, check_all=True,
        )
        for clash in clashes:
            first, second = clash.a, clash.b
            pair = tuple(sorted((first.id(), second.id())))
            if pair in hard_pairs:
                continue
            hard_pairs.add(pair)
            issues.append(_pair_issue(
                "hard_clash", "error", "Hard geometry clash",
                f"{first.is_a()} #{first.id()} intersects {second.is_a()} #{second.id()} "
                f"by approximately {clash.distance * 1000:.1f} mm.",
                first, second,
                distance_mm=round(float(clash.distance) * 1000, 3),
                clash_type=str(tree.get_clash_type(clash.clash_type)).lower(),
            ))
    if config.clearance_clashes and config.clearance_mm > 0 and structural and mep:
        clashes = tree.clash_clearance_many(
            mep, structural, clearance=config.clearance_mm / 1000.0, check_all=False,
        )
        for clash in clashes:
            first, second = clash.a, clash.b
            pair = tuple(sorted((first.id(), second.id())))
            if pair in hard_pairs:
                continue
            issues.append(_pair_issue(
                "clearance_clash", "warning", "Clearance violation",
                f"{first.is_a()} #{first.id()} is only {clash.distance * 1000:.1f} mm "
                f"from {second.is_a()} #{second.id()} (required {config.clearance_mm:g} mm).",
                first, second,
                distance_mm=round(float(clash.distance) * 1000, 3),
                required_clearance_mm=config.clearance_mm,
            ))
    return issues


def _connectivity_issues(model) -> tuple[list[dict], int]:
    mep = list(model.by_type("IfcDistributionElement"))
    ports_by_element: dict[int, set[int]] = defaultdict(set)
    connected_ports: set[int] = set()
    for relation in model.by_type("IfcRelConnectsPortToElement"):
        ports_by_element[relation.RelatedElement.id()].add(relation.RelatingPort.id())
    for relation in model.by_type("IfcRelNests"):
        if relation.RelatingObject.is_a("IfcDistributionElement"):
            for child in relation.RelatedObjects:
                if child.is_a("IfcDistributionPort"):
                    ports_by_element[relation.RelatingObject.id()].add(child.id())
    for relation in model.by_type("IfcRelConnectsPorts"):
        connected_ports.update((relation.RelatingPort.id(), relation.RelatedPort.id()))

    issues: list[dict] = []
    unverifiable = 0
    for element in mep:
        ports = ports_by_element.get(element.id(), set())
        if not ports:
            unverifiable += 1
            continue
        open_ports = ports - connected_ports
        if open_ports:
            issues.append(_issue(
                "disconnected_mep", "warning", "Disconnected MEP endpoint",
                f"{element.is_a()} #{element.id()} has {len(open_ports)} unconnected "
                f"of {len(ports)} IFC port(s).",
                element, open_port_ids=sorted(open_ports),
            ))
    if unverifiable:
        issues.append(_issue(
            "connectivity_data_missing", "info", "Connectivity could not be fully checked",
            f"{unverifiable} MEP element(s) contain no exported IFC ports. "
            "Their physical connections require endpoint-proximity review.",
            None, unverifiable_elements=unverifiable,
        ))
    return issues, unverifiable


def _alignment_issues(model, vertices: dict[int, object], tolerance_degrees: float) -> list[dict]:
    import numpy as np

    issues: list[dict] = []
    candidates = {
        element.id(): element
        for class_name in ALIGNMENT_CLASSES
        for element in model.by_type(class_name)
    }
    for element_id, element in candidates.items():
        verts = vertices.get(element_id)
        if verts is None or len(verts) < 3:
            continue
        centered = verts - verts.mean(axis=0)
        values, vectors = np.linalg.eigh(np.cov(centered, rowvar=False))
        direction = vectors[:, int(np.argmax(values))]
        deviation = degrees(acos(float(np.clip(np.max(np.abs(direction)), 0.0, 1.0))))
        if deviation > tolerance_degrees:
            issues.append(_issue(
                "alignment_review", "warning", "Element is off orthogonal alignment",
                f"{element.is_a()} #{element.id()} is {deviation:.2f}° from the nearest "
                f"global axis (tolerance {tolerance_degrees:g}°). Confirm design intent.",
                element, deviation_degrees=round(deviation, 3),
            ))
    return issues


def _dimension_issues(products: list, vertices: dict[int, object], minimum_mm: float) -> list[dict]:
    import numpy as np

    issues: list[dict] = []
    if minimum_mm <= 0:
        return issues
    for element in products:
        verts = vertices.get(element.id())
        if verts is None or not len(verts):
            continue
        extents_mm = (np.max(verts, axis=0) - np.min(verts, axis=0)) * 1000.0
        positive = extents_mm[extents_mm > 0.01]
        if len(positive) and float(np.min(positive)) < minimum_mm:
            issues.append(_issue(
                "minimum_dimension", "warning", "Element dimension below threshold",
                f"{element.is_a()} #{element.id()} has extents "
                f"{', '.join(f'{value:.1f}' for value in extents_mm)} mm; "
                f"minimum configured dimension is {minimum_mm:g} mm.",
                element, dimensions_mm=[round(float(value), 3) for value in extents_mm],
            ))
    return issues


def run_geometry_checks(ifc_text: str, raw_config: dict | None = None) -> dict:
    """Run deterministic model coordination checks using IfcOpenShell geometry."""
    try:
        import ifcopenshell
    except ImportError as exc:
        raise RuntimeError(
            "IfcOpenShell is required for geometry checks. Install the project geometry dependencies."
        ) from exc

    config = GeometryConfig.from_dict(raw_config)
    try:
        model = ifcopenshell.file.from_string(ifc_text)
    except Exception as exc:
        raise ValueError(f"IfcOpenShell could not open this IFC model: {exc}") from exc

    products = _physical_products(model)
    shapes, vertices, tree = _shape_data(model)
    issues = _identifier_issues(products) if config.identifiers else []
    if config.duplicates:
        issues.extend(_exact_duplicate_geometry_issues(products, vertices))
        issues.extend(_duplicate_opening_geometry_issues(model, products, vertices))
    issues.extend(_clash_issues(model, set(shapes), tree, config))
    unverifiable = 0
    if config.connectivity:
        connection_issues, unverifiable = _connectivity_issues(model)
        issues.extend(connection_issues)
    if config.alignment:
        issues.extend(_alignment_issues(model, vertices, config.alignment_tolerance_degrees))
    if config.dimensions:
        issues.extend(_dimension_issues(products, vertices, config.minimum_dimension_mm))

    severity_order = {"error": 0, "warning": 1, "info": 2}
    issues.sort(key=lambda issue: (
        severity_order.get(issue["severity"], 9), issue["rule_id"], issue.get("entity_id") or 0,
    ))
    counts = issue_summary([Issue(**{key: value for key, value in issue.items() if key in Issue.__dataclass_fields__}) for issue in issues])
    by_rule: dict[str, int] = defaultdict(int)
    for issue in issues:
        by_rule[issue["rule_id"]] += 1
    result = {
        "engine": "ifcopenshell",
        "schema": model.schema,
        "config": config.__dict__,
        "summary": {
            "products": len(products),
            "geometric_products": len(shapes),
            "issues": len(issues),
            "connectivity_unverifiable": unverifiable,
            **counts,
        },
        "by_rule": dict(sorted(by_rule.items())),
        "issues": issues,
    }
    if config.duplicates:
        from .duplicate_acceptance import run_duplicate_acceptance_matrix

        result["duplicate_acceptance_matrix"] = run_duplicate_acceptance_matrix()
    return result
