from pathlib import Path
import unittest

from ifcqc.geometry_acceptance import run_acceptance_matrix


ROOT = Path(__file__).resolve().parents[1]


class GeometryAcceptanceTests(unittest.TestCase):
    def test_all_known_answer_cases_pass(self):
        result = run_acceptance_matrix(ROOT / "samples")
        self.assertTrue(result["passed"])
        self.assertEqual(6, result["passed_cases"])
        self.assertEqual(6, result["total_cases"])
        self.assertEqual(0.001, result["tolerance_metres"])

    def test_matrix_includes_units_placements_schema_and_rejection(self):
        result = run_acceptance_matrix(ROOT / "samples")
        ids = {item["id"] for item in result["cases"]}
        self.assertEqual({
            "ifc4_metre_cube", "ifc4_millimetre_cube", "nested_rotated_placement",
            "ifc2x3_metre_cube", "large_world_coordinates",
            "missing_representation_rejection",
        }, ids)


if __name__ == "__main__":
    unittest.main()
