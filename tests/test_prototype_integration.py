from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

from cityg.planning.floor_prototypes import FloorPrototypeLibrary
from cityg.planning.floor_prototype_lab import make_floor_lab
from cityg.planning.prototype_integration import (
    can_stack_unchanged, floor_candidates, integration_preflight, room_reference_preflight)

ROOT=Path(__file__).resolve().parents[1]/'configs/layout_prototypes/v1'


class IntegrationPreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.lib=FloorPrototypeLibrary(ROOT)

    def test_stack_contract_is_not_only_same_footprint(self):
        a=self.lib.floors['office_open_floor_v1'];b=self.lib.floors['coworking_cluster_v1']
        self.assertEqual(a['reference']['width_m'],b['reference']['width_m'])
        self.assertFalse(can_stack_unchanged(a,b))
        self.assertTrue(can_stack_unchanged(a,deepcopy(a)))

    def test_room_prefilter_checks_door_orientation_and_metric_size(self):
        r={'reference':{'height_m':3.4},'entry':{'space':'hall'},
            'spaces':[{'id':'hall','function':'corridor','bounds_m':[0,0,6.4,2]},
                {'id':'meeting','function':'meeting_room','bounds_m':[0,2,6.4,7.8],
                 'room_reference_hints':['meeting_six_v1']}],
            'connections':[{'a':'hall','b':'meeting','fraction':.2,'width_m':1.,'kind':'door'}]}
        result=room_reference_preflight(r,self.lib.room_library)[0]
        self.assertTrue(result['candidates']);self.assertFalse(result['placement_executed'])
        r['spaces'][0]['bounds_m']=[0,5.8,6.4,7.8];r['spaces'][1]['bounds_m']=[0,0,6.4,5.8]
        result=room_reference_preflight(r,self.lib.room_library)[0]
        self.assertFalse(result['candidates'])
        self.assertIn('door_orientation_needs_adapter',result['rejected'][0]['reasons'])
        r['spaces'][1]['function']='classroom'
        self.assertIn('function_mismatch',room_reference_preflight(r,self.lib.room_library)[0]['rejected'][0]['reasons'])

    def test_preflight_is_read_only_and_not_approval(self):
        city,_=make_floor_lab(self.lib,['office_mixed_v1','hotel_guest_v1'])
        before=deepcopy(city);records=deepcopy(self.lib.floors)
        report=integration_preflight(city,self.lib,max_buildings=2,max_floors=2)
        self.assertEqual(city,before);self.assertEqual(records,self.lib.floors)
        self.assertFalse(report['layout_applied']);self.assertFalse(report['production_enabled'])
        self.assertEqual(report['summary']['sampled_floors'],4)
        self.assertEqual(len(report['floor_to_room']),14)
        self.assertEqual(report['summary']['floors_with_candidates'],4)
        for row in report['floor_candidates']:
            original=row['building_id'].removesuffix('_building')
            self.assertIn(original,{c['prototype_id'] for c in row['candidates']})
        # Asking for up to three floors must still inspect both in a two-floor building.
        self.assertEqual(integration_preflight(city,self.lib,max_buildings=2,max_floors=3)['summary']['sampled_floors'],4)

    def test_outline_and_variation_guards(self):
        city,_=make_floor_lab(self.lib,['office_mixed_v1']);b=next(city.iter_buildings());f=b.floors[0]
        for limit in (-.1,.4,float('nan'),True,None,'0.2'):
            with self.assertRaises(ValueError):floor_candidates(b,f,self.lib,variation_limit=limit)
        b.metadata['massing_style']='test_massing'
        with patch('cityg.planning.prototype_integration.metric_envelope',return_value={'status':'unavailable','reason':'non_rectangular_or_narrow_realized_room'}):
            report=floor_candidates(b,f,self.lib)
            self.assertEqual(report['status'],'unsupported_active_outline');self.assertFalse(report['candidates'])
        with self.assertRaises(ValueError):integration_preflight(city,self.lib,max_buildings=0)


if __name__=='__main__':unittest.main()
