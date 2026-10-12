"""Small analytic opening/host controls; gaps are specified independently in metres."""
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5
import ifcopenshell

ROOT = Path(__file__).resolve().parents[1]


def build_fixture():
    model = ifcopenshell.file(schema="IFC4")
    guid = lambda label: ifcopenshell.guid.compress(uuid5(NAMESPACE_URL, f"openbim-host-check/{label}").hex)
    point = lambda xyz: model.create_entity("IfcCartesianPoint", tuple(float(v) for v in xyz))
    z = model.create_entity("IfcDirection", (0., 0., 1.))
    x = model.create_entity("IfcDirection", (1., 0., 0.))
    axis = lambda xyz=(0, 0, 0): model.create_entity("IfcAxis2Placement3D", point(xyz), z, x)
    context = model.create_entity("IfcGeometricRepresentationContext", ContextType="Model",
        CoordinateSpaceDimension=3, Precision=1e-6, WorldCoordinateSystem=axis())
    units = model.create_entity("IfcUnitAssignment", (model.create_entity("IfcSIUnit", UnitType="LENGTHUNIT", Name="METRE"),))
    model.create_entity("IfcProject", GlobalId=guid("project"), Name="Opening host factual controls",
        RepresentationContexts=(context,), UnitsInContext=units)

    def box(width, depth, height, origin=(0, 0, 0)):
        profile = model.create_entity("IfcRectangleProfileDef", ProfileType="AREA",
            Position=model.create_entity("IfcAxis2Placement2D", point((width / 2, depth / 2))),
            XDim=float(width), YDim=float(depth))
        return model.create_entity("IfcExtrudedAreaSolid", profile, axis(origin), z, float(height))

    def product(cls, label, xyz, items):
        representation = model.create_entity("IfcShapeRepresentation", context, "Body", "SweptSolid", tuple(items))
        shape = model.create_entity("IfcProductDefinitionShape", Representations=(representation,))
        return model.create_entity(cls, GlobalId=guid(label), Name=label,
            ObjectPlacement=model.create_entity("IfcLocalPlacement", None, axis(xyz)), Representation=shape)

    cases = [
        ("Coincident A — host overlaps", (0, 0, 0), (1, -.1, 0)),
        ("Coincident B — wrong distant host", (10, 0, 0), (1, -.1, 0)),
        ("Within threshold 0.5 mm", (0, 10, 0), (4.0005, 9.9, 0)),
        ("Threshold boundary 1 mm", (0, 20, 0), (4.001, 19.9, 0)),
        ("Beyond threshold 1.001 mm", (0, 30, 0), (4.001001, 29.9, 0)),
        ("Touching bounds", (0, 40, 0), (4, 39.9, 0)),
        ("Bounds overlap without body contact", (0, 50, 0), (1.5, 49.9, 0)),
    ]
    for label, host_xyz, opening_xyz in cases:
        items = [box(4, .3, 3)] if "without body contact" not in label else [box(1, .3, 3), box(1, .3, 3, (3, 0, 0))]
        host = product("IfcWall", f"Host: {label}", host_xyz, items)
        opening = product("IfcOpeningElement", label, opening_xyz, [box(1, .5, 2)])
        model.create_entity("IfcRelVoidsElement", GlobalId=guid(f"Relationship: {label}"),
            RelatingBuildingElement=host, RelatedOpeningElement=opening)
    return model


if __name__ == "__main__":
    target = ROOT / "samples/golden/opening_host_matrix.ifc"
    build_fixture().write(str(target))
    print(target)
