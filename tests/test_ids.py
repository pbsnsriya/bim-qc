from pathlib import Path
import unittest

from ifcqc.ids_validator import validate_ids


ROOT = Path(__file__).resolve().parents[1]


class IdsValidationTests(unittest.TestCase):
    def test_sample_ids_links_failure_to_unnamed_wall(self):
        result = validate_ids(
            (ROOT / "samples/geometry_demo.ifc").read_text(),
            (ROOT / "samples/wall-naming.ids").read_text(),
            "wall-naming.ids",
        )
        self.assertTrue(result["complete"])
        self.assertEqual(4, result["summary"]["applicable"])
        self.assertEqual(1, result["summary"]["failed"])
        self.assertEqual(73, result["issues"][0]["entity_id"])
        self.assertEqual("ids:wall-name", result["issues"][0]["rule_id"])

    def test_unsupported_facet_marks_result_partial(self):
        ids = """<ids xmlns="http://standards.buildingsmart.org/IDS">
          <specifications><specification name="Property check">
            <applicability><entity><name><simpleValue>IFCWALL</simpleValue></name></entity></applicability>
            <requirements><property><propertySet><simpleValue>Pset_WallCommon</simpleValue></propertySet></property></requirements>
          </specification></specifications></ids>"""
        result = validate_ids((ROOT / "samples/geometry_demo.ifc").read_text(), ids)
        self.assertFalse(result["complete"])
        self.assertIn("requirement:property", result["unsupported"])

    def test_invalid_xml_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "IDS XML is not valid"):
            validate_ids((ROOT / "samples/geometry_demo.ifc").read_text(), "<ids>")


if __name__ == "__main__":
    unittest.main()
