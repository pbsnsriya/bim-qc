"""Backend discovery for the local IFC application."""

from __future__ import annotations

from importlib.util import find_spec


def _available(module: str) -> bool:
    try:
        return find_spec(module) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def capabilities() -> dict:
    """Describe the engines available to this local installation."""
    ifcopenshell = _available("ifcopenshell")
    ifctester = _available("ifctester")
    return {
        "semantic_backend": "ifcopenshell" if ifcopenshell else "unavailable",
        "semantic_backend_required": True,
        "ids_backend": "builtin-subset",
        "ifcopenshell_available": ifcopenshell,
        "stage3_solid_available": ifcopenshell and _available("manifold3d"),
        "ifctester_available": ifctester,
        "ifctester_adapter": "pending" if ifctester else "not-installed",
        "builtin_ids_facets": ["entity", "attribute:GlobalId", "attribute:Name", "attribute:Description"],
    }


def inspect_with_ifcopenshell(ifc_text: str) -> dict:
    """Parse through IfcOpenShell when installed and report its model view."""
    if not _available("ifcopenshell"):
        return {"engine": "lightweight-step", "available": False}
    try:
        import ifcopenshell

        model = ifcopenshell.file.from_string(ifc_text)
        return {
            "engine": "ifcopenshell",
            "available": True,
            "schema": model.schema,
            "entities": len(list(model)),
            "products": len(model.by_type("IfcProduct")),
        }
    except Exception as exc:  # optional backend must not disable fallback QC
        return {
            "engine": "ifcopenshell",
            "available": True,
            "error": f"IfcOpenShell could not parse this model: {exc}",
        }
