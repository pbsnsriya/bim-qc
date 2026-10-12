"""Analytically specified solid/intersection controls for Stage 3."""
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5
from math import cos,sin,pi
import ifcopenshell

ROOT = Path(__file__).resolve().parents[1]


def build_fixture(millimetres=False,include_large_coordinates=True):
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

    def product(cls, name, xyz, items, rotation=0):
        rep = m.create_entity("IfcShapeRepresentation", context, "Body", "SweptSolid", tuple(items))
        shape = m.create_entity("IfcProductDefinitionShape", Representations=(rep,))
        placement=axis(xyz)
        if rotation: placement.RefDirection=m.create_entity('IfcDirection',(cos(rotation),sin(rotation),0.))
        return m.create_entity(cls, GlobalId=guid(name), Name=name, ObjectPlacement=m.create_entity("IfcLocalPlacement", None, placement), Representation=shape)

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
        ("Rotated overlap 250 mm", (.75,0,0), (1,1,1)),
        ("Large-coordinate overlap 3 mm", (.997,0,0), (1,1,1)),
        ("Identical boxes", (0,0,0), (1,1,1)),
        ("Non-convex intersection depth unknown", (.1,.4,.4), (.2,.2,.2)),
        ("Edge touching", (1,1,0), (1,1,1)),
        ("Vertex touching", (1,1,1), (1,1,1)),
    ]
    for index, (name, offset, size) in enumerate(cases):
        if not include_large_coordinates and name=='Large-coordinate overlap 3 mm': continue
        y = index * 10
        host_items = [box()] if name not in {"Bounds overlap only","Non-convex intersection depth unknown"} else [box((.2,1,1)), box((.2,1,1),(.8,0,0))]
        rotation=pi/4 if name=='Rotated overlap 250 mm' else 0
        base=(1e6,y-2e6,1000) if name=='Large-coordinate overlap 3 mm' else (0,y,0)
        transformed=(offset[0]*cos(rotation)-offset[1]*sin(rotation),offset[0]*sin(rotation)+offset[1]*cos(rotation),offset[2])
        host = product("IfcWall", "Host: "+name, base, host_items,rotation)
        product("IfcDuctSegment", name, tuple(base[i]+transformed[i] for i in range(3)), [box(size)],rotation)
        if name == "Through opening":
            opening = product("IfcOpeningElement", "Clear opening", (.3,y-.2,.3), [box((.4,1.4,.4))])
            m.create_entity("IfcRelVoidsElement", GlobalId=guid("void"), RelatingBuildingElement=host, RelatedOpeningElement=opening)
    return m


if __name__ == "__main__":
    for suffix, mm in [("", False),("_millimetre", True)]:
        path = ROOT / f"samples/golden/hard_clash_matrix{suffix}.ifc"
        build_fixture(mm).write(str(path)); print(path)
    path=ROOT/'samples/golden/hard_clash_pilot.ifc'
    build_fixture(include_large_coordinates=False).write(str(path)); print(path)
