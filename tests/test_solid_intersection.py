import unittest
from unittest.mock import patch
from pathlib import Path
import numpy as np
import manifold3d as md
import ifcopenshell

from ifcqc.solid_intersection import make_body,intersect_bodies,minimum_translation
from ifcqc.hard_clashes import run_hard_clash_model

ROOT=Path(__file__).resolve().parents[1]

def body(solid):
    mesh=solid.to_mesh64()
    return make_body(np.array(mesh.vert_properties)[:,:3],np.array(mesh.tri_verts))

class SolidIntersectionTests(unittest.TestCase):
    def test_coplanar_positive_volume_and_threshold_dimensions_are_measured(self):
        a=body(md.Manifold.cube((1,1,1)))
        for offset,volume,depth in [(.75,.25,250),(.997,.003,3),(.999,.001,1),(.998,.002,2)]:
            b=body(md.Manifold.cube((1,1,1)).translate((offset,0,0)))
            r=intersect_bodies(a,b)
            self.assertAlmostEqual(volume,r['intersection_volume_m3'])
            self.assertAlmostEqual(depth,r['minimum_translation_mm'])

    def test_touching_and_positive_gap_are_not_hard_intersections(self):
        a=body(md.Manifold.cube((1,1,1)))
        for offset in [(1,0,0),(1,1,0),(1,1,1),(1.00001,0,0)]:
            r=intersect_bodies(a,body(md.Manifold.cube((1,1,1)).translate(offset)))
            self.assertEqual(0,r['intersection_volume_m3'])
            self.assertEqual('no_positive_volume_intersection',r['intersection_status'])

    def test_containment_is_translation_to_exit_not_interval_overlap(self):
        a=body(md.Manifold.cube((1,1,1)))
        b=body(md.Manifold.cube((.5,.5,.5)).translate((.25,.25,.25)))
        for first,second in [(a,b),(b,a)]:
            r=intersect_bodies(first,second)
            self.assertAlmostEqual(.125,r['intersection_volume_m3'])
            self.assertAlmostEqual(750,r['minimum_translation_mm'])

    def test_arbitrary_rigid_rotation_and_reversal_preserve_measurements(self):
        a=md.Manifold.cube((1,1,1))
        b=a.translate((.75,0,0))
        a,b=body(a.rotate((23,17,41))),body(b.rotate((23,17,41)))
        for first,second in [(a,b),(b,a)]:
            r=intersect_bodies(first,second)
            self.assertAlmostEqual(.25,r['intersection_volume_m3'])
            self.assertAlmostEqual(250,r['minimum_translation_mm'])
            translation=np.array(r['translation_vector_metres'])
            # Independent Boolean check: the reported vector really separates
            # the solids; 10% less translation must still intersect.
            moved=first.solid.translate(tuple(translation*1.00001))
            shifted_second=second.solid.translate(tuple(second.centre-first.centre))
            self.assertLess((moved^shifted_second).volume(),1e-12)
            self.assertGreater((first.solid.translate(tuple(translation*.9))^shifted_second).volume(),0.)

    def test_large_world_coordinates_retain_three_mm_overlap(self):
        cube=md.Manifold.cube((1,1,1))
        a=body(cube.translate((1e6,-2e6,1000)))
        b=body(cube.translate((1e6+.997,-2e6,1000)))
        r=intersect_bodies(a,b)
        self.assertAlmostEqual(3,r['minimum_translation_mm'],places=4)
        self.assertAlmostEqual(.003,r['intersection_volume_m3'])

    def test_nonconvex_positive_intersection_does_not_invent_depth(self):
        a=body(md.Manifold.cube((.2,1,1))+md.Manifold.cube((.2,1,1)).translate((.8,0,0)))
        b=body(md.Manifold.cube((.2,.2,.2)).translate((.1,.4,.4)))
        r=intersect_bodies(a,b)
        self.assertAlmostEqual(.004,r['intersection_volume_m3'])
        self.assertIsNone(r['minimum_translation_mm'])
        self.assertEqual('not_evaluated',r['depth_status'])
        self.assertIsNone(minimum_translation(a,b))

    def test_invalid_and_open_meshes_are_rejected_without_repair(self):
        mesh=md.Manifold.cube((1,1,1)).to_mesh64()
        v,f=np.array(mesh.vert_properties)[:,:3],np.array(mesh.tri_verts)
        for vertices,faces in [(v,f[:-1]),(v,[[999,0,1]]*4),(v*np.nan,f)]:
            with self.assertRaises(ValueError): make_body(vertices,faces)

    def test_model_size_cap_applies_before_any_tessellation(self):
        m=ifcopenshell.file(schema='IFC4')
        for _ in range(101): m.create_entity('IfcDuctSegment')
        with patch('ifcopenshell.geom.create_shape') as extraction:
            with self.assertRaisesRegex(ValueError,'Whole-model tessellation was not started'): run_hard_clash_model(m)
            extraction.assert_not_called()

    def test_rejected_body_makes_scope_incomplete_and_remains_visible(self):
        m=ifcopenshell.open(str(ROOT/'samples/golden/hard_clash_pilot.ifc'))
        element=m.by_id(32); element.Representation=None
        r=run_hard_clash_model(m,element_ids=[20,32])
        self.assertFalse(r['complete_for_selected_scope'])
        self.assertEqual(32,r['skipped_elements'][0]['element_id'])

if __name__=='__main__': unittest.main()
