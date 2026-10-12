from pathlib import Path
import unittest
from unittest.mock import patch

import ifcopenshell
from ifcqc.element_comparison import compare_model_elements, validate_pair_ids

ROOT = Path(__file__).resolve().parents[1]


class ElementComparisonTests(unittest.TestCase):
    def setUp(self):
        self.model = ifcopenshell.open(str(ROOT / "samples/golden/duplicate_exact_matrix.ifc"))

    def rows(self, result):
        return {row["key"]: row for row in result["rows"]}

    def test_same_shape_identity_and_unknown_are_distinct(self):
        result = compare_model_elements(self.model, [40, 41])
        rows = self.rows(result)
        self.assertEqual("same", rows["dimensions_mm"]["status"])
        self.assertEqual([1000, 1000, 1000], rows["dimensions_mm"]["a"])
        self.assertEqual("same", rows["position_metres"]["status"])
        self.assertEqual("different", rows["global_id"]["status"])
        self.assertEqual("identity", rows["global_id"]["category"])
        self.assertEqual("not_evaluated", rows["phase_status"]["status"])
        self.assertEqual(0, result["physical_difference_count"])

    def test_type_and_boolean_property_differences(self):
        for number, type_name, load in [(40, "PI-1", False), (41, "PI-2", True)]:
            typ = self.model.create_entity("IfcBuildingElementProxyType", GlobalId=ifcopenshell.guid.new(), Name=type_name, PredefinedType="NOTDEFINED")
            self.model.create_entity("IfcRelDefinesByType", GlobalId=ifcopenshell.guid.new(), RelatingType=typ, RelatedObjects=[self.model.by_id(number)])
            prop = self.model.create_entity("IfcPropertySingleValue", Name="LoadBearing", NominalValue=self.model.create_entity("IfcBoolean", load))
            pset = self.model.create_entity("IfcPropertySet", GlobalId=ifcopenshell.guid.new(), Name="Pset_TestCommon", HasProperties=[prop])
            self.model.create_entity("IfcRelDefinesByProperties", GlobalId=ifcopenshell.guid.new(), RelatedObjects=[self.model.by_id(number)], RelatingPropertyDefinition=pset)
        result = compare_model_elements(self.model, [40, 41])
        rows = self.rows(result)
        self.assertEqual("different", rows["type_name"]["status"])
        self.assertIs(False, rows["load_bearing"]["a"])
        self.assertEqual("different", rows["load_bearing"]["status"])
        self.assertEqual(2, result["physical_difference_count"])
        self.assertEqual(1, result["property_difference_count"])
        self.assertFalse(any(row["key"].endswith(".id") for row in result["property_rows"]))

    def test_shifted_shape_has_position_difference(self):
        rows = self.rows(compare_model_elements(self.model, [40, 42]))
        self.assertEqual("different", rows["position_metres"]["status"])
        self.assertEqual("same", rows["dimensions_mm"]["status"])

    def test_millimetre_units_and_rotated_occurrence_axes(self):
        length_unit = next(u for u in self.model.by_type("IfcSIUnit") if u.UnitType == "LENGTHUNIT")
        length_unit.Prefix = "MILLI"
        profile = self.model.by_id(40).Representation.Representations[0].Items[0].SweptArea
        profile.XDim, profile.YDim = 2., 1.
        self.model.by_id(40).Representation.Representations[0].Items[0].Depth = 3.
        self.model.by_id(40).ObjectPlacement.RelativePlacement = self.model.create_entity(
            "IfcAxis2Placement3D", Location=self.model.create_entity("IfcCartesianPoint", (0., 0., 0.)),
            Axis=self.model.create_entity("IfcDirection", (0., 0., 1.)),
            RefDirection=self.model.create_entity("IfcDirection", (0., 1., 0.)),
        )
        result = compare_model_elements(self.model, [40, 41])
        self.assertEqual(0.001, result["length_unit_scale_to_metres"])
        self.assertEqual([2, 1, 3], self.rows(result)["dimensions_mm"]["a"])

    def test_failed_extraction_is_not_reported_as_matching_geometry(self):
        with patch("ifcopenshell.geom.create_shape", side_effect=RuntimeError("Unsupported test shape")):
            result = compare_model_elements(self.model, [40, 41])
        self.assertEqual("not_evaluated", self.rows(result)["dimensions_mm"]["status"])
        self.assertEqual("unavailable", result["elements"][0]["geometry_status"])
        self.assertIn("Unsupported test shape", result["elements"][0]["geometry_message"])

    def test_non_element_and_invalid_ids_rejected(self):
        for ids in [[40, 40], [40], [True, 41], [40, "41"], [-1, 41], None]:
            with self.assertRaises(ValueError): validate_pair_ids(ids)
        for ids in [[40, 999999], [40, 1]]:
            with self.assertRaises(ValueError): compare_model_elements(self.model, ids)

    def test_opening_hosts_are_explicit_context_not_physical_failures(self):
        result = compare_model_elements(self.model, [44, 45])
        rows = self.rows(result)
        self.assertEqual([48, 49], result["host_entity_ids"])
        self.assertEqual("Opening host A", result["elements"][0]["opening_hosts"][0]["name"])
        self.assertEqual("IfcBuildingElementProxy", result["elements"][0]["opening_hosts"][0]["class"])
        self.assertEqual("different", rows["opening_hosts"]["status"])
        self.assertEqual("context", rows["opening_hosts"]["category"])
        self.assertEqual(0, result["physical_difference_count"])
        self.assertEqual(3, result["not_applicable_count"])
        for key in ["type_name", "material", "load_bearing", "type_id", "type_tag"]:
            self.assertEqual("not_applicable", rows[key]["status"])
        self.assertEqual("not_evaluated", rows["phase_status"]["status"])
        self.assertEqual("not_evaluated", rows["assembly_parent"]["status"])

    def test_same_host_deduplicates_selection_and_does_not_compare_relationship_ids(self):
        self.model.by_id(47).RelatingBuildingElement = self.model.by_id(48)
        result = compare_model_elements(self.model, [44, 45])
        self.assertEqual([48], result["host_entity_ids"])
        self.assertEqual("same", self.rows(result)["opening_hosts"]["status"])

    def test_missing_hosts_are_unknown_and_not_inferred_from_names(self):
        self.model.remove(self.model.by_id(46))
        one_missing = compare_model_elements(self.model, [44, 45])
        self.assertEqual([49], one_missing["host_entity_ids"])
        self.assertEqual("missing", self.rows(one_missing)["opening_hosts"]["status"])
        self.model.remove(self.model.by_id(47))
        self.model.by_id(44).Name = "Opening host A"
        both_missing = compare_model_elements(self.model, [44, 45])
        self.assertEqual([], both_missing["host_entity_ids"])
        self.assertEqual("not_evaluated", self.rows(both_missing)["opening_hosts"]["status"])

    def test_physical_elements_keep_missing_fields_unknown(self):
        result = compare_model_elements(self.model, [40, 41])
        rows = self.rows(result)
        self.assertNotIn("opening_hosts", rows)
        self.assertEqual([], result["host_entity_ids"])
        self.assertEqual(0, result["not_applicable_count"])
        self.assertEqual("not_evaluated", rows["material"]["status"])
        mixed = self.rows(compare_model_elements(self.model, [44, 40]))
        self.assertFalse(mixed["material"]["a_applicable"])
        self.assertTrue(mixed["material"]["b_applicable"])
        self.assertEqual("not_evaluated", mixed["material"]["status"])

    def test_exported_opening_metadata_remains_visible(self):
        host_type = self.model.create_entity("IfcBuildingElementProxyType", GlobalId=ifcopenshell.guid.new(), Name="Host type", PredefinedType="NOTDEFINED")
        self.model.create_entity("IfcRelDefinesByType", GlobalId=ifcopenshell.guid.new(), RelatingType=host_type, RelatedObjects=[self.model.by_id(48)])
        material = self.model.create_entity("IfcMaterial", Name="Exported material")
        self.model.create_entity("IfcRelAssociatesMaterial", GlobalId=ifcopenshell.guid.new(), RelatedObjects=[self.model.by_id(44)], RelatingMaterial=material)
        result = compare_model_elements(self.model, [44, 45])
        self.assertEqual("Host type", result["elements"][0]["opening_hosts"][0]["type_name"])
        self.assertEqual(["Exported material"], self.rows(result)["material"]["a"])
        self.assertTrue(self.rows(result)["material"]["a_applicable"])

    def test_ifc2x3_opening_host_inverse(self):
        model = ifcopenshell.open(str(ROOT / "samples/golden/cube_ifc2x3.ifc"))
        host = model.by_type("IfcElement")[0]
        openings = [model.create_entity("IfcOpeningElement", GlobalId=ifcopenshell.guid.new(),
                                       Name="Opening", ObjectPlacement=host.ObjectPlacement,
                                       Representation=host.Representation) for _ in range(2)]
        for opening in openings:
            model.create_entity("IfcRelVoidsElement", GlobalId=ifcopenshell.guid.new(),
                                RelatingBuildingElement=host, RelatedOpeningElement=opening)
        result = compare_model_elements(model, [e.id() for e in openings])
        self.assertEqual([host.id()], result["host_entity_ids"])
        self.assertEqual("same", self.rows(result)["opening_hosts"]["status"])
