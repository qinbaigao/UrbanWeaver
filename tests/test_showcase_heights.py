import unittest
from copy import deepcopy

from cityg.planning import BaselineCityPlanner
from cityg.planning.showcase_heights import floor_band, resize_floor_stack, vary_showcase_heights, select_landmarks
from cityg.schemas import CitySpec
from cityg.serialization import to_primitive
from cityg.subtree_transactions import _refresh_world_program
from cityg.validation import CityValidator


class ShowcaseHeightTests(unittest.TestCase):
    def fixture(self):
        city=BaselineCityPlanner().plan(CitySpec(building_count=3,min_floors=4,max_floors=7,seed=12))
        city.metadata['interior_scope']={'policy':'prototype_exterior_only','building_levels':{}}
        return city

    def test_seeded_bounded_edits_do_not_mutate_source_or_site(self):
        source=self.fixture();snapshot=to_primitive(source)
        a,report=vary_showcase_heights(source);b,other=vary_showcase_heights(source)
        self.assertEqual(snapshot,to_primitive(source));self.assertEqual(report,other)
        self.assertEqual(to_primitive(a),to_primitive(b))
        self.assertEqual(to_primitive(a.road_network),to_primitive(source.road_network))
        for before,after in zip(source.iter_buildings(),a.iter_buildings()):
            lo,hi=floor_band(before)
            self.assertLessEqual(lo,len(after.floors));self.assertLessEqual(len(after.floors),hi)
            self.assertEqual(before.footprint,after.footprint);self.assertEqual(before.entrance,after.entrance)
            self.assertEqual([f.height_m for f in after.floors],[before.floors[-1].height_m]*len(after.floors))
        _refresh_world_program(a,producer='test_height',changed_ids={x.id for x in a.iter_buildings()})
        validation=CityValidator().validate(a)
        self.assertTrue(validation.ok,validation.to_dict())

    def test_expansion_preserves_floor_height_and_rebinds_room_door_ids(self):
        city=self.fixture();b=next(city.iter_buildings());old=deepcopy(b)
        b.floors[-1].height_m=4.1
        top=b.floors[-1].elevation_m+4.1
        resize_floor_stack(b,len(b.floors)+2)
        self.assertEqual(b.floors[-2].elevation_m,top)
        self.assertAlmostEqual(b.floors[-1].elevation_m,top+4.1)
        new=b.floors[-1];ids={r.id for r in new.rooms}
        self.assertTrue(ids);self.assertTrue(all(i.startswith(new.id) for i in ids))
        for door in new.doors:
            self.assertIn(door.room_a_id,ids)
            if door.room_b_id:self.assertIn(door.room_b_id,ids)
        self.assertEqual(to_primitive(b.floors[0]),to_primitive(old.floors[0]))
        self.assertTrue(all(c.to_level==len(b.floors)-1 for c in b.vertical_connectors))
        resize_floor_stack(b,3)
        self.assertEqual([f.level for f in b.floors],[0,1,2])
        self.assertTrue(all(c.to_level==2 for c in b.vertical_connectors))

    def test_detailed_scenes_and_repeat_application_are_rejected(self):
        city=self.fixture();result,_=vary_showcase_heights(city)
        with self.assertRaises(ValueError):vary_showcase_heights(result)
        city.metadata['interior_scope']['building_levels']={'b':[0]}
        with self.assertRaises(ValueError):vary_showcase_heights(city)

    def test_lowrise_cannot_become_landmark_or_cross_core_threshold(self):
        bs=list(self.fixture().iter_buildings())
        self.assertEqual(select_landmarks(bs),[])
        for b in bs:self.assertLessEqual(floor_band(b)[1],9)
        b=bs[0];b.metadata['vertical_zoning']={'zones':[{'start_level':0,'end_level':3}]}
        before=to_primitive(b)
        with self.assertRaises(ValueError):resize_floor_stack(b,5)
        self.assertEqual(before,to_primitive(b))

    def test_landmarks_retain_safe_core_and_update_typical_floor_contract(self):
        city=BaselineCityPlanner().plan(CitySpec(building_count=3,width_m=900,depth_m=900,
            min_floors=18,max_floors=18,rooms_per_floor=2,seed=9))
        city.metadata['interior_scope']={'policy':'prototype_exterior_only','building_levels':{}}
        updated,report=vary_showcase_heights(city)
        self.assertGreater(len(report['landmarks']),0)
        for b in updated.iter_buildings():
            high=b.metadata['highrise']
            self.assertEqual(high['tower_floors']+high['podium_floors'],len(b.floors))
            levels=[level for template in high['typical_floor_reuse'] for level in template['levels']]
            self.assertEqual(sorted(levels),list(range(len(b.floors))))
            self.assertEqual(len(b.metadata['floor_plate_contract']['levels']),len(b.floors))
            if b.id in report['landmarks']:self.assertGreater(len(b.floors),23)
        _refresh_world_program(updated,producer='test_height',changed_ids={b.id for b in updated.iter_buildings()})
        validation=CityValidator().validate(updated)
        self.assertTrue(validation.ok,validation.to_dict())


if __name__=='__main__':unittest.main()
