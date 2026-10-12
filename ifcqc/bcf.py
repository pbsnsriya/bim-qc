"""Minimal BCF 2.1 archive writer for interoperable issue exchange."""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from uuid import uuid4
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile


def _text(parent: ET.Element, tag: str, value: object) -> ET.Element:
    node = ET.SubElement(parent, tag)
    node.text = str(value)
    return node


def _xml(element: ET.Element) -> bytes:
    return ET.tostring(element, encoding="utf-8", xml_declaration=True)


def _markup(issue: dict, topic_guid: str, viewpoint_guid: str, viewpoint_file: str) -> bytes:
    root = ET.Element("Markup")
    topic = ET.SubElement(root, "Topic", {"Guid": topic_guid, "TopicType": "Issue", "TopicStatus": "Open"})
    _text(topic, "Title", issue.get("title") or "OpenBIM QC issue")
    _text(topic, "Priority", str(issue.get("severity", "warning")).capitalize())
    _text(topic, "Index", issue.get("entity_id") or 0)
    labels = ET.SubElement(topic, "Labels")
    _text(labels, "Label", issue.get("rule_id") or "quality-check")
    _text(topic, "CreationDate", datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
    _text(topic, "CreationAuthor", "openbim-qc@local")
    _text(topic, "Description", issue.get("message") or "")
    viewpoints = ET.SubElement(root, "Viewpoints")
    viewpoint = ET.SubElement(viewpoints, "ViewPoint", {"Guid": viewpoint_guid})
    _text(viewpoint, "Viewpoint", viewpoint_file)
    return _xml(root)


def _viewpoint(issue: dict, viewpoint_guid: str) -> bytes:
    root = ET.Element("VisualizationInfo", {"Guid": viewpoint_guid})
    components = ET.SubElement(root, "Components")
    if issue.get("global_id"):
        selection = ET.SubElement(components, "Selection")
        attributes = {"IfcGuid": str(issue["global_id"])}
        if issue.get("entity_id") is not None:
            attributes["AuthoringToolId"] = str(issue["entity_id"])
        ET.SubElement(selection, "Component", attributes)
    return _xml(root)


def build_bcfzip(issues: list[dict]) -> bytes:
    """Create a BCF 2.1 archive containing one topic per issue."""
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        version = ET.Element("Version", {"VersionId": "2.1"})
        _text(version, "DetailedVersion", "2.1")
        archive.writestr("bcf.version", _xml(version))
        for issue in issues:
            topic_guid = str(uuid4())
            viewpoint_guid = str(uuid4())
            viewpoint_file = "viewpoint.bcfv"
            archive.writestr(
                f"{topic_guid}/markup.bcf",
                _markup(issue, topic_guid, viewpoint_guid, viewpoint_file),
            )
            archive.writestr(f"{topic_guid}/{viewpoint_file}", _viewpoint(issue, viewpoint_guid))
    return output.getvalue()
