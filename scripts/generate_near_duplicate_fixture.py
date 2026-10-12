"""Generate independently specified near-duplicate placement and shape cases."""
from math import cos, sin, radians
from pathlib import Path
import ifcopenshell

ROOT = Path(__file__).resolve().parents[1]
model = ifcopenshell.open(str(ROOT / 'samples/golden/cube_metre.ifc'))
for element in list(model.by_type('IfcElement')):
    model.remove(element)
context = model.by_type('IfcGeometricRepresentationContext')[0]


def point(values):
    return model.create_entity('IfcCartesianPoint', tuple(float(v) for v in values))


def axis3(location=(0, 0, 0), angle=0):
    return model.create_entity('IfcAxis2Placement3D', Location=point(location),
        Axis=model.create_entity('IfcDirection', (0., 0., 1.)),
        RefDirection=model.create_entity('IfcDirection', (cos(angle), sin(angle), 0.)))


def element(name, x, y=0., z=0., cls='IfcBuildingElementProxy', width=1., depth=1., angle=0., triangle=False):
    if triangle:
        polygon = model.create_entity('IfcPolyline', Points=[point(p) for p in
            [(-.5, -.5), (.5, -.5), (-.5, .5), (-.5, -.5)]])
        profile = model.create_entity('IfcArbitraryClosedProfileDef', ProfileType='AREA', OuterCurve=polygon)
    else:
        profile = model.create_entity('IfcRectangleProfileDef', ProfileType='AREA',
            Position=model.create_entity('IfcAxis2Placement2D', Location=point((0, 0))), XDim=width, YDim=depth)
    solid = model.create_entity('IfcExtrudedAreaSolid', SweptArea=profile, Position=axis3(),
        ExtrudedDirection=model.create_entity('IfcDirection', (0., 0., 1.)), Depth=1.)
    body = model.create_entity('IfcShapeRepresentation', ContextOfItems=context,
        RepresentationIdentifier='Body', RepresentationType='SweptSolid', Items=[solid])
    return model.create_entity(cls, GlobalId=ifcopenshell.guid.new(), Name=name, Tag=name,
        ObjectPlacement=model.create_entity('IfcLocalPlacement', RelativePlacement=axis3((x, y, z), angle)),
        Representation=model.create_entity('IfcProductDefinitionShape', Representations=[body]))

original = element('Original', 0)
exact = element('Exact', 0)
near = element('Near 2mm', .002)
element('Boundary original', 10)
element('Boundary 5mm', 10.005)
element('Outside original', 20)
element('Outside 5.001mm', 20.005001)
element('Class original', 30)
element('Different class', 30.002, cls='IfcWall')
element('Shape original', 40)
element('Different shape', 40.002, width=1.1)
element('Rotation original', 50, width=2.)
element('Rotated shape', 50.002, width=2., angle=radians(1.))
element('Opening original', 60, cls='IfcOpeningElement')
element('Opening near', 60.002, cls='IfcOpeningElement')
element('Spaced original', 70)
element('Spaced repeat', 71)
a = element('Property original', 90)
b = element('Property near', 90.002)
for obj, value in [(a, 'A'), (b, 'B')]:
    prop = model.create_entity('IfcPropertySingleValue', Name='Reference', NominalValue=model.create_entity('IfcLabel', value))
    pset = model.create_entity('IfcPropertySet', GlobalId=ifcopenshell.guid.new(), Name='Pset_Test', HasProperties=[prop])
    model.create_entity('IfcRelDefinesByProperties', GlobalId=ifcopenshell.guid.new(), RelatedObjects=[obj], RelatingPropertyDefinition=pset)
element('Bounds original', 100)
element('Different surface', 100.002, triangle=True)
model.write(str(ROOT / 'samples/golden/duplicate_near_matrix.ifc'))
print('Generated',len(model.by_type('IfcElement')),'independent elements.')
