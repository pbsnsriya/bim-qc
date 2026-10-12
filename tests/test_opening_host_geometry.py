from math import sqrt
from pathlib import Path
from unittest.mock import patch
import unittest

import ifcopenshell

from ifcqc.element_comparison import compare_model_elements
from ifcqc.opening_host_geometry import _body_bounds, bounds_gap_mm, screen_opening_hosts

ROOT = Path(__file__).resolve().parents[1]


class OpeningHostGeometryTests(unittest.TestCase):
    def setUp(self):
        self.model = ifcopenshell.open(str(ROOT / "samples/golden/opening_host_matrix.ifc"))
        self.openings = {e.Name: e for e in self.model.by_type("IfcOpeningElement")}

    def check(self, name):
        opening = self.openings[name]
        return screen_opening_hosts(self.model, [{"step_id": opening.id(), "is_opening": True}])["results"][0]

    def test_independent_gap_matrix_and_conservative_overlap(self):
        expected = {
            "Coincident A — host overlaps": ("bounds_overlap", 0),
            "Coincident B — wrong distant host": ("separated", 8000),
            "Within threshold 0.5 mm": ("within_tolerance", .5),
            "Threshold boundary 1 mm": ("within_tolerance", 1),
            "Beyond threshold 1.001 mm": ("separated", 1.001),
            "Touching bounds": ("bounds_overlap", 0),
            # The opening sits between two disjoint host solids. Bounds alone
            # cannot establish contact, even though they fully enclose it.
            "Bounds overlap without body contact": ("bounds_overlap", 0),
        }
        for name, (status, gap) in expected.items():
            with self.subTest(name=name):
                result = self.check(name)
                self.assertEqual(status, result["status"])
                self.assertAlmostEqual(gap, result["bounds_distance_lower_bound_mm"], places=7)
                self.assertNotIn("passed", result)

    def test_coincident_pair_has_distinct_host_findings_and_no_review_decision(self):
        ids = [self.openings[name].id() for name in ["Coincident A — host overlaps", "Coincident B — wrong distant host"]]
        result = compare_model_elements(self.model, ids)
        evidence = result["opening_host_checks"]
        self.assertEqual(1, evidence["separated_count"])
        self.assertEqual(1, evidence["unresolved_count"])
        self.assertEqual(0, evidence["not_evaluated_count"])
        self.assertEqual(0, result["physical_difference_count"])
        self.assertTrue(evidence["settings"]["disable_opening_subtractions"])
        self.assertNotIn("review_status", result)
        self.assertEqual("same", next(r for r in result["rows"] if r["key"] == "position_metres")["status"])

    def test_gap_is_lower_bound_in_three_dimensions_not_centre_distance(self):
        a = {"minimum": [0, 0, 0], "maximum": [1, 1, 1]}
        b = {"minimum": [4, 5, 13], "maximum": [5, 6, 14]}
        gaps, distance = bounds_gap_mm(a, b)
        self.assertEqual([3000, 4000, 12000], gaps)
        self.assertEqual(13000, distance)
        self.assertAlmostEqual(sqrt(169) * 1000, distance)

    def test_missing_relationship_and_missing_bodies_are_not_evaluated(self):
        name = "Coincident A — host overlaps"
        opening = self.openings[name]
        host = opening.VoidsElements[0].RelatingBuildingElement
        host.Representation = None
        result = self.check(name)
        self.assertEqual("not_evaluated", result["status"])
        self.assertIsNone(result["bounds_distance_lower_bound_mm"])
        self.assertIn("Host", result["reason"])
        opening.Representation = None
        self.assertIn("Opening", self.check(name)["reason"])
        self.model.remove(opening.VoidsElements[0])
        missing = self.check(name)
        self.assertIsNone(missing["host_id"])
        self.assertEqual([], missing["relationship_ids"])
        self.assertEqual("not_evaluated", missing["status"])

    def test_axis_only_representation_is_not_used_as_a_body(self):
        opening = self.openings["Coincident A — host overlaps"]
        host = opening.VoidsElements[0].RelatingBuildingElement
        host.Representation.Representations[0].RepresentationIdentifier = "Axis"
        self.assertEqual("not_evaluated", self.check(opening.Name)["status"])

    def test_failed_extraction_is_visible_and_never_overlap(self):
        with patch("ifcopenshell.geom.create_shape", side_effect=RuntimeError("Unsupported control geometry")):
            result = self.check("Coincident A — host overlaps")
        self.assertEqual("not_evaluated", result["status"])
        self.assertIn("Unsupported control geometry", result["reason"])
        self.assertEqual("unavailable", result["host_geometry_status"])

    def test_opening_subtraction_does_not_shrink_the_measured_host(self):
        opening = self.openings["Coincident A — host overlaps"]
        host = opening.VoidsElements[0].RelatingBuildingElement
        # Expand the opening to remove the left half of the host. Its fresh
        # uncut Body bounds must still include x=0, not only the remainder.
        item = opening.Representation.Representations[0].Items[0]
        item.SweptArea.XDim = 6.
        item.SweptArea.Position.Location.Coordinates = (-1., .25)
        item.Depth = 5.
        measured = _body_bounds(host)
        self.assertEqual("measured", measured["status"])
        self.assertEqual([0, 0, 0], measured["bounds"]["minimum"])
        self.assertEqual([4, .3, 3], measured["bounds"]["maximum"])

    def test_millimetre_units_nested_rotated_placements(self):
        unit = self.model.by_type("IfcSIUnit")[0]
        unit.Prefix = "MILLI"
        name = "Coincident B — wrong distant host"
        # Shared parent rotation and translation must not change separation.
        opening = self.openings[name]
        host = opening.VoidsElements[0].RelatingBuildingElement
        parent = self.model.create_entity("IfcLocalPlacement", RelativePlacement=self.model.create_entity(
            "IfcAxis2Placement3D", self.model.create_entity("IfcCartesianPoint", (1000., 2000., 3000.)),
            self.model.create_entity("IfcDirection", (0., 0., 1.)), self.model.create_entity("IfcDirection", (0., 1., 0.))))
        for entity in (opening, host):
            entity.ObjectPlacement.PlacementRelTo = parent
        result = self.check(name)
        self.assertEqual("separated", result["status"])
        self.assertAlmostEqual(8., result["bounds_distance_lower_bound_mm"], places=7)
        self.assertAlmostEqual(3., result["opening_bounds_metres"]["minimum"][2])

    def test_same_host_is_measured_once_and_multiple_relationships_are_disclosed(self):
        a, b = [self.openings[name] for name in ["Coincident A — host overlaps", "Coincident B — wrong distant host"]]
        b.VoidsElements[0].RelatingBuildingElement = a.VoidsElements[0].RelatingBuildingElement
        with patch("ifcqc.opening_host_geometry._body_bounds", wraps=_body_bounds) as measurement:
            checks = screen_opening_hosts(self.model, [{"step_id": e.id(), "is_opening": True} for e in [a, b]])
        self.assertEqual(3, measurement.call_count)
        self.assertEqual(2, len(checks["results"]))
        # Invalid IFC cardinality must not silently discard a second relation.
        other_host = self.model.by_type("IfcWall")[-1]
        rel = self.model.create_entity("IfcRelVoidsElement", GlobalId=ifcopenshell.guid.new(),
            RelatingBuildingElement=other_host, RelatedOpeningElement=a)
        checks = screen_opening_hosts(self.model, [{"step_id": a.id(), "is_opening": True}])
        self.assertEqual(2, len(checks["results"]))
        self.assertTrue(any(rel.id() in result["relationship_ids"] for result in checks["results"]))

    def test_non_openings_and_invalid_measurements(self):
        self.assertIsNone(screen_opening_hosts(self.model, [{"is_opening": False}]))
        for tolerance in [True, -1, float("nan"), float("inf")]:
            with self.assertRaises(ValueError): screen_opening_hosts(self.model, [], tolerance)
        for invalid in [{"minimum": [0, 0, 0], "maximum": [1, 1]},
                        {"minimum": [float("nan"), 0, 0], "maximum": [1, 1, 1]},
                        {"minimum": [2, 0, 0], "maximum": [1, 1, 1]}]:
            with self.assertRaises(ValueError): bounds_gap_mm(invalid, invalid)


if __name__ == "__main__":
    unittest.main()
