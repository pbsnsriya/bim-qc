from pathlib import Path
import unittest

from ifcqc.geometry_checks import GeometryConfig, run_geometry_checks


ROOT = Path(__file__).resolve().parents[1]


class GeometryCheckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = (ROOT / "samples/geometry_demo.ifc").read_text()

    def test_demo_detects_duplicate_and_mep_structure_clashes(self):
        result = run_geometry_checks(self.content)
        self.assertEqual("ifcopenshell", result["engine"])
        self.assertEqual(1, result["by_rule"]["probable_duplicate_element"])
        self.assertEqual(2, result["by_rule"]["hard_clash"])
        duplicate = next(
            issue for issue in result["issues"]
            if issue["rule_id"] == "probable_duplicate_element"
        )
        self.assertEqual(104, duplicate["entity_id"])
        self.assertEqual(57, duplicate["related_entity_id"])
        clash_entities = {
            (issue["entity_id"], issue["related_entity_id"])
            for issue in result["issues"] if issue["rule_id"] == "hard_clash"
        }
        self.assertEqual({(103, 57), (103, 104)}, clash_entities)

    def test_demo_reports_missing_connection_data_without_false_failure(self):
        result = run_geometry_checks(self.content)
        self.assertEqual(1, result["summary"]["connectivity_unverifiable"])
        issue = next(
            issue for issue in result["issues"]
            if issue["rule_id"] == "connectivity_data_missing"
        )
        self.assertEqual("info", issue["severity"])
        self.assertIsNone(issue["entity_id"])

    def test_checks_can_be_configured(self):
        result = run_geometry_checks(self.content, {
            "hard_clashes": False,
            "clearance_clashes": False,
            "duplicates": False,
            "connectivity": False,
            "alignment": False,
            "dimensions": False,
        })
        self.assertEqual({}, result["by_rule"])
        self.assertEqual(0, result["summary"]["issues"])

    def test_invalid_tolerance_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "clearance_mm"):
            GeometryConfig.from_dict({"clearance_mm": -1})


if __name__ == "__main__":
    unittest.main()
