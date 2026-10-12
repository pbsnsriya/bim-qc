from pathlib import Path
import unittest

from ifcqc.duplicate_acceptance import run_duplicate_acceptance_matrix
from ifcqc.geometry_checks import run_geometry_checks


ROOT = Path(__file__).resolve().parents[1]


class DuplicateAcceptanceTests(unittest.TestCase):
    def test_exact_duplicate_known_answer_matrix_passes(self):
        result = run_duplicate_acceptance_matrix()
        self.assertTrue(result["passed"])
        self.assertEqual(4, result["passed_cases"])
        self.assertEqual(4, result["total_cases"])
        self.assertEqual(0.000001, result["tolerance_metres"])

    def test_fixture_detects_only_the_known_pair(self):
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
        self.assertEqual(1, len(issues))
        self.assertEqual("exact_duplicate_candidate", issues[0]["rule_id"])
        self.assertEqual([41, 40], issues[0]["selection_ids"])


if __name__ == "__main__":
    unittest.main()
