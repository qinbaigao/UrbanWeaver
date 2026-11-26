from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

from cityg.planning.floor_prototypes import FloorPrototypeLibrary
from cityg.planning.floor_prototype_lab import make_floor_lab
from cityg.planning.prototype_adaptation import (adapt_floor_reference, boundary_map,
    rotated_design, rotate_uv, room_candidates, populate_adapted_room)
from cityg.planning.room_envelope import metric_envelope

ROOT=Path(__file__).resolve().parents[1]/'configs/layout_prototypes/v1'


class PrototypeAdaptationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.lib=FloorPrototypeLibrary(ROOT)

    def test_plain_shell_is_not_shrunk_by_unused_massing(self):
        city,_=make_floor_lab(self.lib,['office_mixed_v1'])
        b=next(city.iter_buildings());f=b.floors[0];r=f.rooms[1]
        result=metric_envelope(b,f,r)
        self.assertEqual(result['source'],'rectangular_shell_v1')
        self.assertEqual(result['bounds'],r.bounds)
        self.assertEqual(result['scale'],[1,1])

    def test_boundary_adjustment_preserves_inventory_core_sizes_and_source(self):
        key='office_mixed_v1';before=deepcopy(self.lib.floors[key])
        r,checks=adapt_floor_reference(self.lib,key,y_knots=[[0,0],[8,6.4],[16,14.4],[24,22.4]])
        self.assertEqual(self.lib.floors[key],before)
        self.assertTrue(checks['layout']['ok']);self.assertTrue(checks['circulation']['ok'])
        self.assertEqual([c['width_m'] for c in r['connections']],[c['width_m'] for c in before['connections']])
        for a,b in zip(r['cores'],before['cores']):
            for lo,hi in ((0,2),(1,3)):
                self.assertAlmostEqual(a['bounds_m'][hi]-a['bounds_m'][lo],b['bounds_m'][hi]-b['bounds_m'][lo])

    def test_invalid_maps_and_core_locks_fail_without_mutation(self):
        original=deepcopy(self.lib.floors)
        for knots in ([[0,0],[10,8],[5,20]], [[1,0],[24,24]], [[0,0],[24,40]], [[0,0],[24,float('nan')]]):
            with self.assertRaises(ValueError):boundary_map(knots,24,.2)
        with self.assertRaises(ValueError):adapt_floor_reference(self.lib,'office_mixed_v1',locked_cores={})
        locks={c['stack_key']:c['bounds_m'] for c in original['office_mixed_v1']['cores']}
        r,_=adapt_floor_reference(self.lib,'office_mixed_v1',locked_cores=locks)
        self.assertEqual(r['cores'],original['office_mixed_v1']['cores'])
        locks=deepcopy(locks);locks['stair_a'][2]+=.2
        with self.assertRaisesRegex(ValueError,'dimensions'):adapt_floor_reference(self.lib,'office_mixed_v1',locked_cores=locks)
        self.assertEqual(self.lib.floors,original)

    def test_rotation_moves_constraints_not_local_member_relations(self):
        p=self.lib.room_library.materialize('coworking_open_v1');before=p.design.to_dict()
        rotated=p
        for _ in range(4):rotated=rotated_design(rotated,1)
        self.assertEqual(rotated.design.to_dict(),before)
        self.assertEqual(rotate_uv([0,0,.5,1],1),[0,0,1,.5])
        self.assertEqual(rotated_design(p,1).design.surface_items,p.design.surface_items)

    def test_door_adjustments_keep_shared_edge_and_width(self):
        key='residential_spine_v1';before=deepcopy(self.lib.floors[key])
        proposal={'a':'s1_bed_a','b':'s1_hall','fraction':.3}
        record,_=adapt_floor_reference(self.lib,key,door_fractions=[proposal])
        old=next(c for c in before['connections'] if c['a']=='s1_bed_a')
        new=next(c for c in record['connections'] if c['a']=='s1_bed_a')
        self.assertEqual(new['width_m'],old['width_m']);self.assertEqual(new['fraction'],.3)
        with self.assertRaises(ValueError):
            adapt_floor_reference(self.lib,key,door_fractions=[{**proposal,'fraction':.1}])
        self.assertEqual(self.lib.floors[key],before)

    def test_rotated_room_candidates_do_not_relax_library_applicability(self):
        lib=deepcopy(self.lib)
        r,_=adapt_floor_reference(lib,'office_mixed_v1',y_knots=[[0,0],[8,6.4],[16,14.4],[24,22.4]])
        lib.floors[r['id']]=r
        city,_=make_floor_lab(lib,[r['id']]);b=next(city.iter_buildings());f=b.floors[0]
        room=next(r for r in f.rooms if r.function=='office')
        cs=room_candidates(lib.room_library,b,f,room)
        self.assertTrue(any(c['prototype_id']=='office_four_v1' and c['quarter_turns']==2 for c in cs))
        # Legacy north entrances still fail; only the explicit adapter rotates.
        self.assertFalse(lib.room_library.compatible('office_four_v1',room_type='office',width_m=8,
            depth_m=6.4,height_m=3.4,door_wall='north'))
        before=deepcopy(city)
        with self.assertRaisesRegex(ValueError,'review-only'):
            populate_adapted_room(city,b,f,room,lib.room_library,None,cs[0])
        with patch('cityg.planning.prototype_adaptation.reference_registry',return_value=None), \
             patch('cityg.planning.prototype_adaptation.FloorDetailAgent.populate_rooms',side_effect=ValueError('rejected')):
            with self.assertRaises(ValueError):
                populate_adapted_room(city,b,f,room,lib.room_library,None,cs[0],review_only=True)
        self.assertEqual(city,before)

    def test_multiple_doors_are_not_dropped_from_the_metric_room(self):
        from dataclasses import replace
        from cityg.schemas import Point2D
        lib=deepcopy(self.lib)
        r,_=adapt_floor_reference(lib,'office_mixed_v1',y_knots=[[0,0],[8,6.4],[16,14.4],[24,22.4]])
        lib.floors[r['id']]=r
        city,_=make_floor_lab(lib,[r['id']]);b=next(city.iter_buildings());f=b.floors[0]
        room=next(r for r in f.rooms if r.function=='office')
        door=next(d for d in f.doors if room.id in (d.room_a_id,d.room_b_id))
        f.doors.append(replace(door,id='additional_test_door',position=Point2D(room.bounds.min_x+1.2,room.bounds.max_y)))
        self.assertEqual(len(metric_envelope(b,f,room)['floor'].doors),2)
        self.assertTrue(all(c['door_count']==2 for c in room_candidates(lib.room_library,b,f,room)))


if __name__=='__main__':unittest.main()
