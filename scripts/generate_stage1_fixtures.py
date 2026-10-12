"""Original analytic Stage 1 controls; expected answers are derived by hand."""
from pathlib import Path
import ifcopenshell
from ifcopenshell import guid

ROOT = Path(__file__).resolve().parents[1]


def fixture(name):
    m = ifcopenshell.file(schema='IFC4')
    point = lambda xyz: m.create_entity('IfcCartesianPoint', tuple(float(v) for v in xyz))
    z = m.create_entity('IfcDirection', (0., 0., 1.))
    x = m.create_entity('IfcDirection', (1., 0., 0.))
    axis = lambda xyz=(0, 0, 0), ref=x: m.create_entity('IfcAxis2Placement3D', point(xyz), z, ref)
    context = m.create_entity('IfcGeometricRepresentationContext', ContextType='Model', CoordinateSpaceDimension=3, Precision=1e-5, WorldCoordinateSystem=axis())
    units = m.create_entity('IfcUnitAssignment', (m.create_entity('IfcSIUnit', UnitType='LENGTHUNIT', Name='METRE'),))
    m.create_entity('IfcProject', GlobalId=guid.new(), Name=name, RepresentationContexts=(context,), UnitsInContext=units)
    def place(xyz=(0,0,0), parent=None, rotated=False):
        ref = m.create_entity('IfcDirection', (0.,1.,0.)) if rotated else x
        return m.create_entity('IfcLocalPlacement', parent, axis(xyz, ref))
    def box(a,b,h):
        loc=m.create_entity('IfcAxis2Placement2D',point((a/2,b/2)))
        profile=m.create_entity('IfcRectangleProfileDef',ProfileType='AREA',Position=loc,XDim=a,YDim=b)
        return m.create_entity('IfcExtrudedAreaSolid',profile,axis(),z,h)
    def shape(item, rep_type='SweptSolid'):
        rep=m.create_entity('IfcShapeRepresentation',context,'Body',rep_type,(item,))
        return m.create_entity('IfcProductDefinitionShape',Representations=(rep,))
    def product(cls, name, geometry, placement=None):
        return m.create_entity(cls,GlobalId=guid.new(),Name=name,ObjectPlacement=placement or place(),Representation=geometry)
    return m, point, axis, context, place, box, shape, product, z

m, point, axis, ctx, place, box, shape, product, z=fixture('Analytic opening')
wall=product('IfcWall','Wall with known rectangular cutout',shape(box(4.,.3,3.)))
opening=product('IfcOpeningElement','1 m wide by 2 m high cutout',shape(box(1.,.5,2.)),place((1.,-.1,0.)))
m.create_entity('IfcRelVoidsElement',GlobalId=guid.new(),RelatingBuildingElement=wall,RelatedOpeningElement=opening)
m.write(str(ROOT/'samples/golden/opening_cutout.ifc'))

m, point, axis, ctx, place, box, shape, product, z=fixture('Analytic cylinder')
profile=m.create_entity('IfcCircleProfileDef',ProfileType='AREA',Radius=1.)
solid=m.create_entity('IfcExtrudedAreaSolid',profile,axis(),z,2.)
product('IfcColumn','Radius 1 m, height 2 m cylinder',shape(solid),place((5.,7.,3.)))
m.write(str(ROOT/'samples/golden/curved_cylinder.ifc'))

m, point, axis, ctx, place, box, shape, product, z=fixture('Analytic mapped instances')
source=m.create_entity('IfcShapeRepresentation',ctx,'Body','SweptSolid',(box(2.,1.,1.),))
map_rep=m.create_entity('IfcRepresentationMap',axis(),source)
for label, xyz, rotation in [('Mapped A',(0,0,0),False),('Mapped B',(5,3,0),True)]:
    target=m.create_entity('IfcCartesianTransformationOperator3D',LocalOrigin=point((0,0,0)),Scale=1.)
    item=m.create_entity('IfcMappedItem',map_rep,target)
    product('IfcBuildingElementProxy',label,shape(item,'MappedRepresentation'),place(xyz,rotated=rotation))
m.write(str(ROOT/'samples/golden/mapped_instances.ifc'))

m, point, axis, ctx, place, box, shape, product, z=fixture('Analytic three-level transform')
p1=place((10,20,3),rotated=True)
p2=place((2,0,1),p1,True)
p3=place((1,0,0),p2)
product('IfcBuildingElementProxy','Three-level nested box',shape(box(2.,1.,1.)),p3)
m.write(str(ROOT/'samples/golden/complex_placement.ifc'))
