"""Offline input isolation and fixture-only attribution regressions."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from run_visual_input_ablation import local_context, progressive_context
from check_visual_input_repairs import attribute
import test_visual_grounding as grounding_fixtures
from cityg.schemas import Point2D


class VisualInputAblationTests(unittest.TestCase):
    def setUp(self):
        fixture=grounding_fixtures.VisualGroundingTests();fixture.setUp()
        self.city,self.f,self.r,self.obj=fixture.city,fixture.f,fixture.r,fixture.obj

    def test_input_arms_add_only_intended_information(self):
        identity=local_context(self.city,'identity_images')
        geometry=local_context(self.city,'geometry_images')
        full=local_context(self.city,'contract_images')
        text=local_context(self.city,'contract_text')
        self.assertNotIn('metric_geometry',identity)
        self.assertIn('metric_geometry',geometry)
        self.assertNotIn('intended_design',geometry)
        self.assertIn('intended_design',full)
        self.assertEqual(full['metric_geometry'],text['metric_geometry'])
        self.assertEqual(full['intended_design'],text['intended_design'])
        self.assertFalse(text['images_provided'])

    def test_cached_errors_and_private_metadata_do_not_leak(self):
        self.r.metadata['private_truth']='injected_secret'
        self.r.metadata['room_design']['constraint_checks']={'bad':'injected_secret'}
        self.r.metadata['room_design']['intent']='injected_secret'
        self.obj.metadata['error_label']='injected_secret'
        for arm in ('identity_images','geometry_images','contract_images','contract_text'):
            self.assertNotIn('injected_secret',json.dumps(local_context(self.city,arm)))

    def test_progressive_requests_keep_context_neighbors_without_edit_authorization(self):
        other=deepcopy(self.obj);other.id='other';other.position=Point2D(1.7,3)
        other.metadata['group_key']='neighbor';self.f.objects.append(other)
        distant=deepcopy(self.obj);distant.id='far';distant.position=Point2D(7,6)
        distant.metadata['group_key']='distant';self.f.objects.append(distant)
        c=progressive_context(self.city,{'groups_to_inspect':['north'],'observations':[],'reason':'uncertain'})
        ids={o['object_id'] for o in c['metric_geometry']['objects']}
        self.assertEqual(ids,{'shelf','other'})
        self.assertEqual(c['disclosure']['requested_groups'],['north'])
        self.assertTrue(c['disclosure']['nearby_objects_are_read_only'])

    def test_attribution_rejects_wrong_object_even_if_room_contains_fault(self):
        self.obj.position=Point2D(4,.3)
        innocent=deepcopy(self.obj);innocent.id='innocent';innocent.position=Point2D(6,5)
        innocent.metadata['group_key']='work';self.f.objects.append(innocent)
        bad={'kind':'door_blocked','object_ids':['innocent'],'group_ids':['work']}
        self.assertEqual(attribute(self.city,bad)['status'],'not_supported')
        good={'kind':'door_blocked','object_ids':['shelf'],'group_ids':['north']}
        self.assertEqual(attribute(self.city,good)['status'],'confirmed')

    def test_containment_cannot_borrow_another_objects_failure(self):
        self.obj.position=Point2D(-2,3)
        innocent=deepcopy(self.obj);innocent.id='innocent';innocent.position=Point2D(6,5)
        innocent.metadata['group_key']='work';self.f.objects.append(innocent)
        self.assertEqual(attribute(self.city,{'kind':'outside','object_ids':['innocent'],
            'group_ids':['work']})['status'],'not_supported')


if __name__=='__main__':unittest.main()
