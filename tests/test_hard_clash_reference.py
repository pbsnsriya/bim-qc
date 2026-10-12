from pathlib import Path
import unittest

import ifcopenshell
import ifcopenshell.geom
import numpy as np

from ifcqc.hard_clashes import run_hard_clash_model, run_hard_clashes_file
from ifcqc.hard_clash_acceptance import run_hard_clash_acceptance

ROOT = Path(__file__).resolve().parents[1]


class HardClashReferenceTests(unittest.TestCase):
    def test_known_false_negatives_block_stage3_instead_of_becoming_model_pass(self):
        report = run_hard_clash_acceptance(ROOT / "samples")
        self.assertEqual("0.8.5", report["engine_version"], "Re-baseline kernel controls explicitly when upgrading IfcOpenShell.")
        self.assertFalse(report["passed"])
        self.assertFalse(report["model_clash_checking_enabled"])
        self.assertEqual("blocked_reference_failure", report["gate_status"])
        self.assertEqual((14,18), (report["passed_cases"], report["total_cases"]))
        self.assertEqual({f"{unit}:{name}" for unit in ["metre", "millimetre"]
                          for name in ["Overlap 250 mm", "Above threshold 3 mm"]},
                         {c["id"] for c in report["cases"] if c["result"] == "FALSE_NEGATIVE"})
        self.assertTrue(all(c["geometry_complete"] for c in report["cases"]))
        self.assertTrue(all(len(f["source_sha256"]) == 64 for f in report["fixtures"]))

    def test_detected_containment_retains_ifc_identity_and_witnesses(self):
        report = run_hard_clashes_file(ROOT / "samples/golden/hard_clash_matrix.ifc")
        self.assertTrue(report["extraction_complete_for_selected_scope"])
        self.assertFalse(report["complete_for_selected_scope"])
        issue, = report["issues"]
        self.assertEqual("Contained box", issue["name"])
        self.assertTrue(issue["global_id"])
        self.assertTrue(issue["related_global_id"])
        self.assertEqual([176,164], issue["selection_ids"])
        self.assertAlmostEqual(250., issue["distance_mm"])
        self.assertEqual(2, len(issue["witness_points_metres"]))

    def test_positive_controls_are_real_axis_aligned_box_intersections_in_both_units(self):
        # Independently inspect the actual tessellated control coordinates.
        # AABB intersection is exact here because these specified controls are
        # single rectangular extrusions; it is NOT used for arbitrary IFCs.
        settings = ifcopenshell.geom.settings()
        settings.set("use-world-coords", True)
        for suffix in ["", "_millimetre"]:
            model = ifcopenshell.open(str(ROOT / f"samples/golden/hard_clash_matrix{suffix}.ifc"))
            for name, expected in [("Overlap 250 mm", .25), ("Above threshold 3 mm", .003)]:
                elements = [e for e in model.by_type("IfcProduct") if e.Name in [name, "Host: "+name]]
                self.assertEqual(2,len(elements))
                bounds = []
                for element in elements:
                    item, = element.Representation.Representations[0].Items
                    self.assertEqual("IfcExtrudedAreaSolid", item.is_a())
                    self.assertEqual("IfcRectangleProfileDef", item.SweptArea.is_a())
                    shape = ifcopenshell.geom.create_shape(settings, element)
                    vertices = np.array(shape.geometry.verts).reshape(-1,3)
                    bounds.append((vertices.min(axis=0), vertices.max(axis=0)))
                overlap = np.minimum(bounds[0][1],bounds[1][1])-np.maximum(bounds[0][0],bounds[1][0])
                np.testing.assert_allclose(overlap, [expected,1.,1.], atol=1e-8)
                self.assertAlmostEqual(expected, float(np.prod(overlap)))

    def test_threshold_and_scope_inputs_are_rejected_before_extraction(self):
        model = ifcopenshell.open(str(ROOT / "samples/golden/hard_clash_matrix.ifc"))
        for threshold in [True, -1, float("nan"),float("inf"),1001,"2"]:
            with self.assertRaises(ValueError): run_hard_clash_model(model, threshold)
        for ids in [[],[True],[-1],[999999],[20.5]]:
            with self.assertRaises(ValueError): run_hard_clash_model(model, element_ids=ids)
        selected = run_hard_clash_model(model, element_ids=[164,176,164])
        self.assertEqual([164,176],selected["selected_element_ids"])
        self.assertEqual(1,len(selected["issues"]))
        missing_group = run_hard_clash_model(model, element_ids=[20])
        self.assertEqual("not_evaluated_missing_group",missing_group["scope_status"])
        self.assertFalse(missing_group["complete_for_selected_scope"])


if __name__ == "__main__": unittest.main()
