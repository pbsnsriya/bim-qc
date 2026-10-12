"""Analytically specified solid/intersection controls for Stage 3."""
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5
import ifcopenshell

ROOT = Path(__file__).resolve().parents[1]


def build_fixture(millimetres=False):
    m = ifcopenshell.file(schema="IFC4")
    scale = 1000 if millimetres else 1
    point = lambda xyz: m.create_entity("IfcCartesianPoint", tuple(float(v * scale) for v in xyz))
    z, x = [m.create_entity("IfcDirection", xyz) for xyz in [(0., 0., 1.), (1., 0., 0.)]]
    axis = lambda xyz=(0, 0, 0): m.create_entity("IfcAxis2Placement3D", point(xyz), z, x)
    context = m.create_entity("IfcGeometricRepresentationContext", ContextType="Model", CoordinateSpaceDimension=3, Precision=1e-7 * scale, WorldCoordinateSystem=axis())
    units = m.create_entity("IfcUnitAssignment", (m.create_entity("IfcSIUnit", UnitType="LENGTHUNIT", Prefix="MILLI" if millimetres else None, Name="METRE"),))
    guid = lambda name: ifcopenshell.guid.compress(uuid5(NAMESPACE_URL, "openbim-clash/"+name).hex)
    m.create_entity("IfcProject", GlobalId=guid("project"), Name="Analytic Stage 3 hard clashes", RepresentationContexts=(context,), UnitsInContext=units)

    def box(size=(1,1,1), origin=(0,0,0)):
        w, d, h = size
        profile = m.create_entity("IfcRectangleProfileDef", ProfileType="AREA", Position=m.create_entity("IfcAxis2Placement2D", point((w/2,d/2))), XDim=float(w*scale), YDim=float(d*scale))
        return m.create_entity("IfcExtrudedAreaSolid", profile, axis(origin), z, float(h*scale))

    def product(cls, name, xyz, items):
        rep = m.create_entity("IfcShapeRepresentation", context, "Body", "SweptSolid", tuple(items))
        shape = m.create_entity("IfcProductDefinitionShape", Representations=(rep,))
        return m.create_entity(cls, GlobalId=guid(name), Name=name, ObjectPlacement=m.create_entity("IfcLocalPlacement", None, axis(xyz)), Representation=shape)

    cases = [
        ("Overlap 250 mm", (.75,0,0), (1,1,1)),
        ("Separated 100 mm", (1.1,0,0), (1,1,1)),
        ("Touching", (1,0,0), (1,1,1)),
        ("Below threshold 1 mm", (.999,0,0), (1,1,1)),
        ("Boundary 2 mm", (.998,0,0), (1,1,1)),
        ("Above threshold 3 mm", (.997,0,0), (1,1,1)),
        ("Contained box", (.25,.25,.25), (.5,.5,.5)),
        ("Through opening", (.4,-.5,.4), (.2,2,.2)),
        ("Bounds overlap only", (.4,.4,.4), (.2,.2,.2)),
    ]
    for index, (name, offset, size) in enumerate(cases):
        y = index * 10
        host_items = [box()] if name != "Bounds overlap only" else [box((.2,1,1)), box((.2,1,1),(.8,0,0))]
        host = product("IfcWall", "Host: "+name, (0,y,0), host_items)
        product("IfcDuctSegment", name, (offset[0],offset[1]+y,offset[2]), [box(size)])
        if name == "Through opening":
            opening = product("IfcOpeningElement", "Clear opening", (.3,y-.2,.3), [box((.4,1.4,.4))])
            m.create_entity("IfcRelVoidsElement", GlobalId=guid("void"), RelatingBuildingElement=host, RelatedOpeningElement=opening)
    return m


if __name__ == "__main__":
    for suffix, mm in [("", False),("_millimetre", True)]:
        path = ROOT / f"samples/golden/hard_clash_matrix{suffix}.ifc"
        build_fixture(mm).write(str(path)); print(path)
