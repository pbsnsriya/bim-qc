from pathlib import Path
import math
import unittest

from ifcqc.geometry_diagnostics import diagnose_geometry


ROOT = Path(__file__).resolve().parents[1]


class GeometryDiagnosticTests(unittest.TestCase):
    def test_geometry_demo_passes_stage_one_gate(self):
        result = diagnose_geometry((ROOT / "samples/geometry_demo.ifc").read_text())
        self.assertTrue(result["core_ready"])
        self.assertFalse(result["ready"])
        self.assertFalse(result["duplicate_prerequisites_ready"])
        self.assertEqual(1, result["stage"])
        self.assertEqual("IFC4", result["schema"])
        self.assertEqual(7, result["counts"]["represented_products"])
        self.assertEqual(7, result["counts"]["generated_shapes"])
        self.assertEqual(100.0, result["coverage_percent"])
        self.assertEqual([], result["failed_elements"])
        self.assertEqual("not_run", result["cross_engine"]["status"])

    def test_units_bounds_and_mapping_are_reported(self):
        result = diagnose_geometry((ROOT / "samples/geometry_demo.ifc").read_text())
        self.assertTrue(math.isfinite(result["units"]["metres_per_project_unit"]))
        self.assertGreater(result["units"]["metres_per_project_unit"], 0)
        self.assertEqual(3, len(result["bounds_metres"]["minimum"]))
        self.assertTrue(any(value > 0 for value in result["bounds_metres"]["extents"]))
        self.assertEqual([], result["mapping"]["duplicate_shape_ids"])
        self.assertEqual([], result["mapping"]["unexpected_shape_ids"])

    def test_matching_browser_evidence_completes_the_gate(self):
        backend = diagnose_geometry((ROOT / "samples/geometry_demo.ifc").read_text())
        browser = {
            "origin_mode": "model-centred",
            "element_ids": [int(key) for key in backend["element_extents_metres"]],
            "element_extents_metres": backend["element_extents_metres"],
            "bounds_frame": "IFC world Z-up metres",
            "element_bounds_metres": backend["element_bounds_metres"],
            "element_shape_metrics": backend["element_shape_metrics"],
        }
        result = diagnose_geometry(
            (ROOT / "samples/geometry_demo.ifc").read_text(), browser,
        )
        self.assertTrue(result["ready"])
        self.assertIn("performance_profile", result)
        self.assertIn("iterator_tessellation", result["performance_profile"]["phase_timings_ms"])
        self.assertGreaterEqual(result["performance_profile"]["fallback_retry_count"], 0)
        self.assertTrue(result["duplicate_prerequisites_ready"])
        self.assertEqual("pass", result["cross_engine"]["status"])
        self.assertEqual(7, result["cross_engine"]["compared_elements"])

    def test_browser_extent_disagreement_fails_the_gate(self):
        backend = diagnose_geometry((ROOT / "samples/geometry_demo.ifc").read_text())
        extents = dict(backend["element_extents_metres"])
        extents[next(iter(extents))] = [999.0, 999.0, 999.0]
        result = diagnose_geometry((ROOT / "samples/geometry_demo.ifc").read_text(), {
            "element_ids": [int(key) for key in extents],
            "element_extents_metres": extents,
        })
        self.assertFalse(result["ready"])
        self.assertEqual("fail", result["cross_engine"]["status"])
        self.assertTrue(result["duplicate_prerequisites_ready"])

    def test_missing_browser_id_blocks_duplicate_stage(self):
        backend = diagnose_geometry((ROOT / "samples/geometry_demo.ifc").read_text())
        element_ids = [int(key) for key in backend["element_extents_metres"]]
        missing_id = element_ids.pop()
        result = diagnose_geometry((ROOT / "samples/geometry_demo.ifc").read_text(), {
            "element_ids": element_ids,
            "element_extents_metres": {
                key: value for key, value in backend["element_extents_metres"].items()
                if int(key) != missing_id
            },
        })
        self.assertFalse(result["duplicate_prerequisites_ready"])
        self.assertIn(missing_id, result["cross_engine"]["missing_in_browser"])

    def test_model_without_representation_fails_cleanly(self):
        result = diagnose_geometry((ROOT / "samples/clean_demo.ifc").read_text())
        self.assertFalse(result["ready"])
        self.assertEqual(0, result["counts"]["generated_shapes"])
        self.assertIn("geometry_present", {
            check["id"] for check in result["checks"] if check["status"] == "fail"
        })

    def test_equal_sizes_do_not_hide_changed_world_position(self):
        from copy import deepcopy
        source = (ROOT / 'samples/golden/nested_rotated.ifc').read_text()
        backend = diagnose_geometry(source)
        browser = self.full_evidence(backend)
        key = next(iter(browser['element_bounds_metres']))
        for edge in ('minimum', 'maximum'):
            browser['element_bounds_metres'][key][edge][0] += 1
        result = diagnose_geometry(source, browser)
        self.assertEqual('fail', result['cross_engine']['status'])
        self.assertEqual(0, result['cross_engine']['maximum_extent_delta_metres'])
        self.assertEqual([int(key)], result['cross_engine']['position_comparison']['outlier_ids'])

    @staticmethod
    def full_evidence(backend):
        from copy import deepcopy
        return deepcopy({'element_ids': list(map(int, backend['element_extents_metres'])),
            'element_extents_metres': backend['element_extents_metres'],
            'bounds_frame': 'IFC world Z-up metres',
            'element_bounds_metres': backend['element_bounds_metres'],
            'element_shape_metrics': backend['element_shape_metrics']})

    def test_missing_opening_is_detected_despite_identical_bounds(self):
        source = (ROOT / 'samples/golden/opening_cutout.ifc').read_text()
        backend = diagnose_geometry(source)
        browser = self.full_evidence(backend)
        # Subtractive features are not separately visible; wall expected volume is 3 m3.
        browser['element_ids'].remove(32)
        browser['element_shape_metrics']['20']['volume_m3'] = 3.6
        result = diagnose_geometry(source, browser)
        self.assertEqual(0, result['cross_engine']['maximum_extent_delta_metres'])
        self.assertEqual([20], result['cross_engine']['shape_comparison']['outlier_ids'])
        self.assertFalse(result['ready'])

    def test_legacy_extents_cannot_claim_complete_comparison(self):
        source = (ROOT / 'samples/golden/cube_metre.ifc').read_text()
        browser = self.full_evidence(diagnose_geometry(source))
        del browser['element_shape_metrics']
        result = diagnose_geometry(source, browser)
        self.assertEqual('not_evaluated', result['cross_engine']['status'])
        self.assertFalse(result['ready'])

    def test_invalid_geometry_evidence_cannot_pass(self):
        source = (ROOT / 'samples/golden/cube_metre.ifc').read_text()
        backend = diagnose_geometry(source)
        browser = self.full_evidence(backend)
        key = next(iter(browser['element_bounds_metres']))
        browser['element_bounds_metres'][key]['minimum'][0] = float('nan')
        self.assertEqual('fail', diagnose_geometry(source, browser)['cross_engine']['status'])
        browser = self.full_evidence(backend)
        browser['element_shape_metrics'][key]['volume_m3'] = float('inf')
        self.assertEqual('fail', diagnose_geometry(source, browser)['cross_engine']['status'])
        browser['element_shape_metrics'] = []
        self.assertEqual('fail', diagnose_geometry(source, browser)['cross_engine']['status'])

    def test_critical_missing_geometry_blocks_high_coverage(self):
        import ifcopenshell
        model = ifcopenshell.file.from_string((ROOT / 'samples/golden/cube_metre.ifc').read_text())
        cube = model.by_type('IfcBuildingElementProxy')[0]
        for _ in range(99):
            model.create_entity('IfcBuildingElementProxy', GlobalId=ifcopenshell.guid.new(),
                ObjectPlacement=cube.ObjectPlacement, Representation=cube.Representation)
        missing = model.create_entity('IfcBuildingElementProxy', GlobalId=ifcopenshell.guid.new())
        result = diagnose_geometry(model.to_string())
        self.assertEqual(100, result['coverage_percent'])
        self.assertIn(missing.id(), result['critical_unresolved_ids'])
        self.assertFalse(result['core_ready'])
        self.assertFalse(result['duplicate_prerequisites_ready'])

    def test_rules_record_sources_and_missing_references(self):
        result = diagnose_geometry((ROOT / 'samples/golden/cube_metre.ifc').read_text())
        self.assertTrue(all({'source', 'expected', 'actual', 'tolerance', 'verdict'} <= row.keys()
                            for row in result['rule_evidence']))
        self.assertEqual('not_evaluated', result['project_compliance']['verdict'])

    def test_confirmed_defect_requires_missing_mandatory_placement(self):
        import ifcopenshell
        from ifcqc.geometry_evidence import extraction_failure
        model = ifcopenshell.file.from_string((ROOT / 'samples/golden/cube_metre.ifc').read_text())
        element = model.by_type('IfcBuildingElementProxy')[0]
        self.assertFalse(extraction_failure(element, 'unknown error')['confirmed_model_defect'])
        placement_id = element.ObjectPlacement.id()
        import re
        invalid_text = re.sub(r'#' + str(placement_id) + r'=IFCLOCALPLACEMENT\([^;]*\);', '#' + str(placement_id) + '=IFCLOCALPLACEMENT($,#999999);', model.to_string())
        element = ifcopenshell.file.from_string(invalid_text).by_type('IfcBuildingElementProxy')[0]
        defect = extraction_failure(element, 'topology error')
        self.assertEqual('confirmed_model_defect', defect['classification'])
        self.assertEqual('IfcLocalPlacement.RelativePlacement', defect['model_defect_evidence']['required_attribute'])

    def test_comparison_hash_of_another_file_blocks_readiness(self):
        import tempfile
        from ifcqc.geometry_diagnostics import diagnose_geometry_file
        source = ROOT / 'samples/golden/cube_metre.ifc'
        browser = self.full_evidence(diagnose_geometry(source.read_text()))
        browser['source_sha256'] = 'different file'
        result = diagnose_geometry_file(source, browser)
        self.assertFalse(result['ready'])
        self.assertFalse(result['duplicate_prerequisites_ready'])
        self.assertEqual('fail', result['model_identity']['verdict'])

    def test_file_failure_confirms_absent_raw_placement_reference(self):
        import ifcopenshell, re, tempfile
        from ifcqc.geometry_diagnostics import diagnose_geometry_file
        model = ifcopenshell.file.from_string((ROOT / 'samples/golden/cube_metre.ifc').read_text())
        placement_id = model.by_type('IfcBuildingElementProxy')[0].ObjectPlacement.id()
        raw = re.sub(r'#' + str(placement_id) + r'=IFCLOCALPLACEMENT\([^;]*\);',
            '#' + str(placement_id) + '=IFCLOCALPLACEMENT($,#999999);', model.to_string())
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'broken.ifc'
            source.write_text(raw)
            result = diagnose_geometry_file(source)
        failure = result['failed_elements'][0]
        self.assertTrue(failure['confirmed_model_defect'])
        self.assertTrue(failure['model_defect_evidence']['raw_confirmation'])
        self.assertFalse(failure['model_defect_evidence']['referenced_definition_present'])
        self.assertEqual(999999, failure['model_defect_evidence']['referenced_step_id'])
        self.assertFalse(result['core_ready'])


if __name__ == "__main__":
    unittest.main()
