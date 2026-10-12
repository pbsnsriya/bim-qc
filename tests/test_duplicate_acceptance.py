from pathlib import Path
import unittest

from ifcqc.duplicate_acceptance import run_duplicate_acceptance_matrix
from ifcqc.geometry_checks import run_geometry_checks


ROOT = Path(__file__).resolve().parents[1]


class DuplicateAcceptanceTests(unittest.TestCase):
    def test_exact_duplicate_known_answer_matrix_passes(self):
        result = run_duplicate_acceptance_matrix()
        self.assertTrue(result["passed"])
        self.assertEqual(6, result["passed_cases"])
        self.assertEqual(6, result["total_cases"])
        self.assertEqual(0.000001, result["tolerance_metres"])

    def test_fixture_separates_physical_and_opening_pairs(self):
        content = (ROOT / "samples/golden/duplicate_exact_matrix.ifc").read_text()
        result = run_geometry_checks(content, {
            "identifiers": False,
            "duplicates": True,
            "hard_clashes": False,
            "clearance_clashes": False,
            "connectivity": False,
            "alignment": False,
            "dimensions": False,
        })
        issues = result["issues"]
        self.assertEqual(2, len(issues))
        physical = next(issue for issue in issues if issue["rule_id"] == "exact_duplicate_candidate")
        opening = next(issue for issue in issues if issue["rule_id"] == "duplicate_opening_candidate")
        self.assertEqual([41, 40], physical["selection_ids"])
        self.assertEqual([45, 44], opening["opening_ids"])
        self.assertEqual([49, 48], opening["selection_ids"])
        self.assertEqual([49, 48], opening["host_entity_ids"])


if __name__ == "__main__":
    unittest.main()
