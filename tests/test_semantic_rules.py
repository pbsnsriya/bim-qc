import unittest

import ifcopenshell

from ifcqc.semantic_rules import duplicate_global_ids, selection_metadata


class SemanticRuleTests(unittest.TestCase):
    def test_non_root_metadata_is_not_treated_as_a_global_id(self):
        model = ifcopenshell.file(schema="IFC4")
        model.create_entity("IfcSIUnit", UnitType="LENGTHUNIT", Name="METRE")
        model.create_entity("IfcWall", GlobalId="0DuplicateSemantic001")
        model.create_entity("IfcWall", GlobalId="0DuplicateSemantic001")
        issues = duplicate_global_ids(model)
        self.assertEqual(2, len(issues))
        self.assertTrue(all(issue.entity_type == "IFCWALL" for issue in issues))

    def test_parent_product_selects_geometric_child(self):
        model = ifcopenshell.file(schema="IFC4")
        ramp = model.create_entity("IfcRamp", GlobalId="0SemanticRampParent01")
        shape = model.create_entity("IfcProductDefinitionShape", Representations=[])
        flight = model.create_entity(
            "IfcRampFlight", GlobalId="0SemanticRampFlight01", Representation=shape,
        )
        model.create_entity(
            "IfcRelAggregates", GlobalId="0SemanticAggregate001",
            RelatingObject=ramp, RelatedObjects=[flight],
        )
        result = selection_metadata(ramp)
        self.assertEqual("children", result["geometry_status"])
        self.assertEqual([flight.id()], result["selection_ids"])

    def test_opening_selects_host_instead_of_void_solid(self):
        model = ifcopenshell.file(schema="IFC4")
        wall = model.create_entity("IfcWall", GlobalId="0SemanticOpeningHost1")
        opening = model.create_entity("IfcOpeningElement", GlobalId="0SemanticOpeningVoid1")
        model.create_entity(
            "IfcRelVoidsElement", GlobalId="0SemanticVoidsRel001",
            RelatingBuildingElement=wall, RelatedOpeningElement=opening,
        )
        result = selection_metadata(opening)
        self.assertEqual("void_feature", result["geometry_status"])
        self.assertEqual([wall.id()], result["selection_ids"])


if __name__ == "__main__":
    unittest.main()
