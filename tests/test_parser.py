import unittest
from pathlib import Path

from ifcqc.analyzer import analyze_ifc
from ifcqc.parser import parse_ifc, split_arguments


ROOT = Path(__file__).resolve().parents[1]


class ParserTests(unittest.TestCase):
    def test_nested_argument_splitting(self):
        values = split_arguments("'id',$,'Wall',(1.,2.,(#4,#5)),.NOTDEFINED.")
        self.assertEqual(5, len(values))
        self.assertEqual("(1.,2.,(#4,#5))", values[3])

    def test_parse_demo(self):
        model = parse_ifc((ROOT / "samples/qc_demo.ifc").read_text())
        self.assertEqual("IFC4", model.schema)
        self.assertGreater(len(model.entities), 10)

    def test_detect_known_demo_issues(self):
        result = analyze_ifc((ROOT / "samples/qc_demo.ifc").read_text())
        rule_ids = [issue["rule_id"] for issue in result["issues"]]
        self.assertIn("duplicate_global_id", rule_ids)
        self.assertIn("missing_name", rule_ids)
        self.assertIn("missing_spatial_containment", rule_ids)
        self.assertEqual(3, result["summary"]["error"])  # duplicate pair plus uncontained window

    def test_clean_demo_has_no_errors_or_warnings(self):
        result = analyze_ifc((ROOT / "samples/clean_demo.ifc").read_text())
        self.assertEqual(0, result["summary"]["error"])
        self.assertEqual(0, result["summary"]["warning"])


if __name__ == "__main__":
    unittest.main()
