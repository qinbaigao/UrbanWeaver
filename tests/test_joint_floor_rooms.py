from copy import deepcopy
import unittest

from cityg.geometry import GeometryCompiler
from cityg.planning.floor_repartition import options, propose_floor, repartition_city, validate_repartition
from cityg.planning.prototype_adaptation import room_candidates
import test_floor_repartition as fixtures


class JointFloorRoomTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.FloorRepartitionTests.setUpClass()
        cls.lib=fixtures.FloorRepartitionTests.lib

    def fixture(self):
        return fixtures.FloorRepartitionTests().fixture()

    def test_joint_dimensions_and_source_locks(self):
        city,b,f=self.fixture(); old=deepcopy(city)
        new,row=propose_floor(b,f,self.lib,options({'joint_room_planning':True}))
        self.assertTrue(row['joint_room_bindings'])
        self.assertEqual(new.doors[:len(f.doors)],f.doors)
        self.assertEqual(city,old)
        for binding in row['joint_room_bindings']:
            room=next(r for r in new.rooms if r.id==binding['room_id'])
            self.assertTrue(any(c['prototype_id']==binding['prototype_id'] for c in room_candidates(self.lib.room_library,b,new,room)))
        self.assertAlmostEqual(sum(r.bounds.area for r in new.rooms),sum(r.bounds.area for r in f.rooms))

    def test_deep_room_adds_access_without_reassigning_old_doors(self):
        _,b,f=self.fixture()
        for room in f.rooms[1:]: room.function='bedroom'
        new,row=propose_floor(b,f,self.lib,options({'joint_room_planning':True}))
        self.assertGreater(row['added_corridors'],0)
        self.assertEqual(next(r for r in new.rooms if r.id==f.rooms[0].id),f.rooms[0])
        for r in new.rooms:
            if r.metadata.get('joint_room_plan',{}).get('role')=='access_corridor':
                self.assertGreaterEqual(min(r.bounds.width,r.bounds.depth),1.5-1e-6)
        self.assertTrue(validate_repartition(b,f,new)['all_rooms_reachable'])

    def test_disabled_spine_does_not_force_incompatible_rooms(self):
        _,b,f=self.fixture()
        for room in f.rooms[1:]: room.function='bedroom'
        # 8m depth is outside both bedroom references; no corridor is authorized.
        with self.assertRaisesRegex(ValueError,'No safe'):
            propose_floor(b,f,self.lib,options({'joint_room_planning':True,'allow_secondary_corridor':False}))

    def test_compiled_new_access_and_locks(self):
        city,b,f=self.fixture()
        for room in f.rooms[1:]:room.function='bedroom'
        result,report=repartition_city(city,self.lib,GeometryCompiler(),
            {'enabled':True,'joint_room_planning':True,'levels':[0]})
        self.assertEqual(len(report['accepted']),1,report)
        row=report['accepted'][0]
        self.assertTrue(row['joint_room_bindings'])
        self.assertGreater(row['added_corridors'],0)
        self.assertTrue(row['compiled_locks_preserved'])
        self.assertTrue(row['new_door_core_clearance_verified'])
        self.assertTrue(row['outdoor_reachability_verified'])

    def test_joint_configuration_is_strict(self):
        for value in ({'joint_room_planning':1},{'allow_secondary_corridor':0},
                      {'secondary_corridor_width_m':1.0},{'secondary_corridor_width_m':float('nan')}):
            with self.assertRaises(ValueError):options(value)


if __name__=='__main__':unittest.main()
