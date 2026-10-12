from pathlib import Path
import math
import unittest

from ifcqc.geometry_diagnostics import diagnose_geometry


ROOT = Path(__file__).resolve().parents[1]


class GeometryDiagnosticTests(unittest.TestCase):
    def test_geometry_demo_passes_stage_one_gate(self):
        result = diagnose_geometry((ROOT / "samples/geometry_demo.ifc").read_text())
        self.assertTrue(result["ready"])
        self.assertEqual(1, result["stage"])
        self.assertEqual("IFC4", result["schema"])
        self.assertEqual(7, result["counts"]["represented_products"])
        self.assertEqual(7, result["counts"]["generated_shapes"])
        self.assertEqual(100.0, result["coverage_percent"])
        self.assertEqual([], result["failed_elements"])
        self.assertTrue(all(check["status"] == "pass" for check in result["checks"]))

    def test_units_bounds_and_mapping_are_reported(self):
        result = diagnose_geometry((ROOT / "samples/geometry_demo.ifc").read_text())
        self.assertTrue(math.isfinite(result["units"]["metres_per_project_unit"]))
        self.assertGreater(result["units"]["metres_per_project_unit"], 0)
        self.assertEqual(3, len(result["bounds_metres"]["minimum"]))
        self.assertTrue(any(value > 0 for value in result["bounds_metres"]["extents"]))
        self.assertEqual([], result["mapping"]["duplicate_shape_ids"])
        self.assertEqual([], result["mapping"]["unexpected_shape_ids"])

    def test_model_without_representation_fails_cleanly(self):
        result = diagnose_geometry((ROOT / "samples/clean_demo.ifc").read_text())
        self.assertFalse(result["ready"])
        self.assertEqual(0, result["counts"]["generated_shapes"])
        self.assertIn("geometry_present", {
            check["id"] for check in result["checks"] if check["status"] == "fail"
        })


if __name__ == "__main__":
    unittest.main()
