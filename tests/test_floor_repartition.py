from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from cityg.geometry import GeometryCompiler
from cityg.planning.floor_prototypes import FloorPrototypeLibrary
from cityg.planning.floor_prototype_lab import make_floor_lab
from cityg.planning.floor_repartition import options, propose_floor, validate_repartition, repartition_city
from cityg.schemas import Room, Door, Point2D, Bounds2D

ROOT = Path(__file__).resolve().parents[1]


class FloorRepartitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lib = FloorPrototypeLibrary(ROOT/'configs/layout_prototypes/v1')

    def fixture(self):
        city, _ = make_floor_lab(self.lib, ['office_mixed_v1'])
        b = next(city.iter_buildings()); f = b.floors[0]; x, y = b.footprint.min_x, b.footprint.min_y
        f.objects = []; f.metadata = {}
        f.rooms = [Room(f.id+'_corridor', 'Hall', 'corridor', Bounds2D(x,y+8,x+36,y+16)),
                   Room(f.id+'_south', 'Office', 'office', Bounds2D(x,y,x+36,y+8)),
                   Room(f.id+'_north', 'Open office', 'open_office', Bounds2D(x,y+16,x+36,y+24))]
        f.doors = [Door(f.id+'_south_door', f.rooms[1].id, f.rooms[0].id, Point2D(x+18,y+8)),
                   Door(f.id+'_north_door', f.rooms[2].id, f.rooms[0].id, Point2D(x+18,y+16)),
                   Door(f.id+'_entrance', f.rooms[0].id, None, b.entrance, 1.8, 'exterior')]
        return city, b, f

    def test_partition_preserves_entry_core_circulation_and_source(self):
        city, b, f = self.fixture(); old = deepcopy(city)
        new, report = propose_floor(b, f, self.lib, options({}))
        self.assertGreater(len(new.rooms), len(f.rooms))
        self.assertEqual(new.rooms[0], f.rooms[0])
        self.assertEqual(new.doors[:len(f.doors)], f.doors)
        self.assertEqual(city, old)
        self.assertTrue(all(report['checks'].values()))
        again, _ = propose_floor(b, f, self.lib, options({}))
        self.assertEqual(new, again)

    def test_bad_existing_entrance_is_not_silently_rebound(self):
        _, b, f = self.fixture()
        f.doors[-1].position = Point2D(b.footprint.center.x, b.footprint.max_y)
        with self.assertRaises(ValueError):
            propose_floor(b, f, self.lib, options({}))

    def test_existing_inventory_and_private_units_are_protected(self):
        _, b, f = self.fixture()
        f.rooms[1].object_ids = ['existing_chair']
        new, _ = propose_floor(b, f, self.lib, options({}))
        self.assertEqual(next(r for r in new.rooms if r.id == f.rooms[1].id), f.rooms[1])
        f.metadata['dwelling_units'] = [{'id': 'private'}]
        with self.assertRaisesRegex(ValueError, 'unit-aware'):
            propose_floor(b, f, self.lib, options({}))

    def test_door_mutation_overlap_and_disconnection_rejected(self):
        _, b, f = self.fixture(); new, _ = propose_floor(b, f, self.lib, options({}))
        broken = deepcopy(new); broken.doors[0].width_m += .1
        with self.assertRaisesRegex(ValueError, 'door contract'):
            validate_repartition(b, f, broken)
        broken = deepcopy(new); broken.rooms[-1].bounds = broken.rooms[1].bounds
        with self.assertRaises(ValueError):
            validate_repartition(b, f, broken)
        broken = deepcopy(new); broken.doors.pop()
        with self.assertRaisesRegex(ValueError, 'Disconnected'):
            validate_repartition(b, f, broken)

    def test_compiler_failure_restores_floor_scope_and_source(self):
        city, _, _ = self.fixture(); city.metadata['interior_scope']={'building_levels':{}}
        old = deepcopy(city)
        compiler = SimpleNamespace(compile=lambda *a, **kw: (_ for _ in ()).throw(ValueError('compile failed')))
        result, report = repartition_city(city, self.lib, compiler, {'enabled':True,'levels':[0]})
        self.assertEqual(result, old); self.assertEqual(city, old)
        self.assertEqual(report['accepted'], [])
        self.assertIn('compile failed', report['attempts'][0]['reason'])

    def test_real_compiler_keeps_door_and_core_geometry(self):
        city, b, f = self.fixture(); old = deepcopy(city)
        result, report = repartition_city(city, self.lib, GeometryCompiler(), {'enabled':True,'levels':[0]})
        self.assertEqual(city, old)
        self.assertEqual(len(report['accepted']), 1, report)
        after = next(result.iter_buildings())
        self.assertEqual(after.vertical_connectors, b.vertical_connectors)
        self.assertEqual(after.floors[1], b.floors[1])
        self.assertTrue(report['accepted'][0]['compiled_locks_preserved'])

    def test_invalid_options(self):
        for opt in ({'enabled':1},{'max_floors':100},{'levels':[]},{'levels':[True]},
                    {'min_room_width_m':float('nan')},{'unknown':True}):
            with self.assertRaises(ValueError): options(opt)

    def test_core_in_private_room_is_rejected(self):
        _, b, f = self.fixture()
        b.vertical_connectors[0].bounds = f.rooms[1].bounds.inset(1)
        with self.assertRaisesRegex(ValueError, 'immutable circulation'):
            propose_floor(b, f, self.lib, options({}))

    def test_post_compile_lock_failure_rolls_back(self):
        city, _, _ = self.fixture(); city.metadata['interior_scope'] = {'building_levels': {}}
        old = deepcopy(city)
        with patch('cityg.planning.floor_repartition._compiled_locks', side_effect=[{'old':1}, {'changed':1}]):
            result, report = repartition_city(city, self.lib, GeometryCompiler(), {'enabled':True,'levels':[0]})
        self.assertEqual(result, old); self.assertEqual(report['accepted'], [])
        self.assertIn('geometry changed', report['attempts'][0]['reason'])

    def test_upper_floor_adds_access_dependencies_without_replanning_them(self):
        city, b, f = self.fixture(); upper = deepcopy(f)
        upper.id = f.id.replace('_00', '_01'); upper.level = 1; upper.elevation_m = f.height_m
        mapping = {r.id:r.id.replace('_floor_00', '_floor_01') for r in upper.rooms}
        for r in upper.rooms: r.id = mapping[r.id]
        upper.doors = [d for d in upper.doors if d.room_b_id is not None]
        for d in upper.doors:
            d.id = d.id.replace('_floor_00', '_floor_01')
            d.room_a_id = mapping[d.room_a_id]; d.room_b_id = mapping[d.room_b_id]
        b.floors[1] = upper; city.metadata['interior_scope'] = {'building_levels': {}}
        result, report = repartition_city(city, self.lib, GeometryCompiler(), {'enabled':True,'levels':[1]})
        self.assertEqual(len(report['accepted']), 1, report)
        self.assertEqual(result.metadata['interior_scope']['building_levels'][b.id], [0,1])
        self.assertEqual(next(result.iter_buildings()).floors[0], f)
        self.assertEqual(report['accepted'][0]['access_scope_added_levels'], [0,1])

    def test_compiled_core_blocking_new_door_is_rejected(self):
        from cityg.planning.floor_repartition import _check_compiled_access
        from cityg.geometry.model import GeometryScene, GeometryPrimitive, Vec3
        _, b, f = self.fixture(); new, _ = propose_floor(b, f, self.lib, options({}))
        door = next(d for d in new.doors if d.id not in {v.id for v in f.doors})
        corridor = f.rooms[0].bounds; y = door.position.y
        direction = 1 if corridor.center.y > y else -1
        scene = GeometryScene('test', 'z_up')
        scene.primitives.append(GeometryPrimitive('core', b.vertical_connectors[0].id, 'box',
            Vec3(door.position.x,y+direction*.3,1), Vec3(.6,.4,2), 0,
            'stair_tread','stairs','floor:'+f.id))
        scene.primitives.extend(GeometryPrimitive(d.id, d.id, 'box', Vec3(d.position.x,d.position.y,1),
            Vec3(.9,.1,2), 0, 'door','door','floor:'+f.id) for d in new.doors)
        with self.assertRaisesRegex(ValueError, 'clearance'):
            _check_compiled_access(scene,b,f,new)


if __name__ == '__main__': unittest.main()
