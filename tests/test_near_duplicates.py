from pathlib import Path
import unittest

import ifcopenshell
import numpy as np

from ifcqc.geometry_checks import GeometryConfig, _physical_products, _shape_data, run_geometry_checks
from ifcqc.near_duplicates import near_duplicate_issues, run_near_duplicate_acceptance_matrix


ROOT = Path(__file__).resolve().parents[1]
CONFIG = dict(identifiers=False, duplicates=True, near_duplicates=True, hard_clashes=False,
              clearance_clashes=False, connectivity=False, alignment=False, dimensions=False)


class NearDuplicateTests(unittest.TestCase):
    def setUp(self):
        self.model = ifcopenshell.open(str(ROOT / 'samples/golden/duplicate_near_matrix.ifc'))
        self.elements = {e.Name: e for e in self.model.by_type('IfcElement')}
        self.faces = {}
        _, self.vertices, _ = _shape_data(self.model, self.faces)

    def pair(self):
        return [self.elements['Original'], self.elements['Near 2mm']]

    def detect(self, products=None, **kwargs):
        return near_duplicate_issues(products or _physical_products(self.model), self.faces, self.vertices, 5., **kwargs)

    def test_reference_matrix_boundary_and_negative_cases(self):
        for tolerance in (0.01, 2., 5., 6., 100.):
            result = run_near_duplicate_acceptance_matrix(tolerance)
            self.assertTrue(result['passed'], result['assertions'])
            self.assertEqual(12, result['passed_cases'])

    def test_measured_vector_distance_shape_and_selection(self):
        issues, scan = self.detect(self.pair())
        self.assertTrue(scan['complete'])
        self.assertEqual(1, len(issues))
        item = issues[0]
        self.assertAlmostEqual(2., item['placement_offset_mm'], places=7)
        np.testing.assert_allclose([2., 0., 0.], item['translation_mm'], atol=1e-7)
        self.assertLessEqual(item['shape_residual_mm'], .001)
        self.assertEqual([self.pair()[1].id(), self.pair()[0].id()], item['selection_ids'])

    def test_distance_is_euclidean_not_per_axis(self):
        shifted = self.pair()[1].id()
        self.vertices[shifted] += [.002, .004, 0.]
        issues, _ = self.detect(self.pair())
        self.assertEqual([], issues, '4 mm on two axes exceeds the 5 mm radial tolerance')

    def test_cell_boundary_and_negative_coordinates_are_not_missed(self):
        for obj in self.pair():
            self.vertices[obj.id()] -= [.001, 0., 0.]
        issues, _ = self.detect(self.pair())
        self.assertEqual(1, len(issues))

    def test_vertex_and_triangle_order_do_not_change_match(self):
        obj = self.pair()[1].id()
        faces = self.faces[obj].reshape(-1, 3)[::-1, [2, 0, 1]].copy().reshape(-1)
        self.faces[obj] = faces
        issues, _ = self.detect(self.pair())
        self.assertEqual(1, len(issues))

    def test_surface_connectivity_matters_beyond_vertices_and_bounds(self):
        obj = self.pair()[1].id()
        self.faces[obj] = self.faces[obj].copy()
        self.faces[obj][:3] = self.faces[obj][3:6]
        issues, _ = self.detect(self.pair())
        self.assertEqual([], issues)

    def test_large_world_coordinates(self):
        for obj in self.pair():
            self.vertices[obj.id()] += [1e6, -1e6, 1e6]
        issues, _ = self.detect(self.pair())
        self.assertEqual(1, len(issues))
        self.assertAlmostEqual(2., issues[0]['placement_offset_mm'], places=5)

    def test_ifc_millimetre_units_are_normalised(self):
        unit = next(u for u in self.model.by_type('IfcSIUnit') if u.UnitType == 'LENGTHUNIT')
        unit.Prefix = 'MILLI'
        for point in self.model.by_type('IfcCartesianPoint'):
            point.Coordinates = tuple(float(v) * 1000 for v in point.Coordinates)
        for profile in self.model.by_type('IfcRectangleProfileDef'):
            profile.XDim *= 1000
            profile.YDim *= 1000
        for solid in self.model.by_type('IfcExtrudedAreaSolid'):
            solid.Depth *= 1000
        result = run_geometry_checks(self.model.to_string(), CONFIG)
        item = next(i for i in result['issues'] if i['rule_id'] == 'near_duplicate_candidate')
        self.assertAlmostEqual(2., item['placement_offset_mm'], places=6)

    def test_search_and_result_limits_are_explicitly_incomplete(self):
        for options, reason in [({'max_comparisons': 1}, 'comparison_limit'), ({'max_results': 1}, 'result_limit')]:
            _, stats = self.detect(**options)
            self.assertFalse(stats['complete'])
            self.assertEqual(reason, stats['limit_reason'])

    def test_unavailable_geometry_is_not_a_negative_verdict(self):
        obj = self.pair()[1].id()
        del self.vertices[obj]
        issues, stats = self.detect(self.pair())
        self.assertEqual([], issues)
        self.assertEqual([obj], stats['unavailable_product_ids'])

    def test_invalid_surface_identifies_only_failed_record(self):
        bad = self.pair()[1].id()
        self.faces[bad] = self.faces[bad].copy()
        self.faces[bad][0] = 999999
        issues, stats = self.detect(self.pair())
        self.assertEqual([], issues)
        self.assertEqual([bad], stats['unavailable_product_ids'])

    def test_invalid_settings_rejected(self):
        for value in (-1, 0, .001, 101, float('nan'), float('inf'), True, 'invalid'):
            with self.assertRaises(ValueError):
                GeometryConfig.from_dict({'near_duplicate_tolerance_mm': value})
        with self.assertRaises(ValueError):
            GeometryConfig.from_dict({'near_duplicates': 'false'})

    def test_result_config_and_exact_pair_stay_separate(self):
        result = run_geometry_checks(self.model.to_string(), {**CONFIG, 'near_duplicate_tolerance_mm': 5})
        self.assertEqual(4, result['by_rule']['near_duplicate_candidate'])
        self.assertEqual(1, result['by_rule']['exact_duplicate_candidate'])
        self.assertTrue(result['near_duplicate_acceptance_matrix']['passed'])
        self.assertEqual(5., result['config']['near_duplicate_tolerance_mm'])
        exact_pair = {self.elements['Original'].id(), self.elements['Exact'].id()}
        self.assertFalse(any({i['entity_id'], i['related_entity_id']} == exact_pair
                             for i in result['issues'] if i['rule_id'] == 'near_duplicate_candidate'))
        disabled = run_geometry_checks(self.model.to_string(), {**CONFIG, 'near_duplicates': False})
        self.assertNotIn('near_duplicate_candidate', disabled['by_rule'])
        self.assertNotIn('near_duplicate_scan', disabled)
