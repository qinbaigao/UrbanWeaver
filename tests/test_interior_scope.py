import unittest

from cityg.planning import BaselineCityPlanner
from cityg.schemas import CitySpec
from cityg.planning.interior_scope import select_scope, floor_enabled
from cityg.planning.interiors import FloorDetailAgent
from cityg.refinement.selection import select_hero_rooms
from cityg.geometry import GeometryCompiler, GeometryValidator


class InteriorScopeTests(unittest.TestCase):
    def test_access_dependencies_do_not_expand_detail_authority(self):
        from cityg.planning.interior_scope import materialize_access_dependencies
        city = BaselineCityPlanner().plan(CitySpec(name="Access dependencies", building_count=2,
            min_floors=7, max_floors=7, width_m=140, depth_m=140, seed=17))
        building = next(city.iter_buildings())
        targets = {building.id: [3, 6]}
        objects_before = [o.id for o in city.iter_objects()]
        city.metadata['interior_scope'] = {'building_levels': {building.id: [3, 6]}}
        scope = materialize_access_dependencies(city, targets)
        self.assertEqual(targets, {building.id: [3, 6]})
        self.assertEqual(scope['detail_building_levels'], targets)
        self.assertEqual(scope['building_levels'][building.id], list(range(7)))
        self.assertEqual(scope['access_dependency_levels'][building.id], [0, 1, 2, 4, 5])
        self.assertEqual([o.id for o in city.iter_objects()], objects_before)

    def test_sparse_upper_floors_do_not_compile_or_navigate_missing_stairs(self):
        city = BaselineCityPlanner().plan(CitySpec(name="Sparse upper floors", building_count=2,
            min_floors=7, max_floors=7, width_m=140, depth_m=140, seed=17))
        building = next(city.iter_buildings())
        city.metadata['interior_scope'] = {'building_levels': {building.id: [3, 6]}}
        scene = GeometryCompiler().compile(city)
        self.assertFalse(any(p.semantic_class == 'stair_tread' for p in scene.primitives))
        self.assertFalse(any(e.traversal == 'stairs' for e in scene.navigation.edges))
        city.metadata['interior_scope']['building_levels'][building.id] = list(range(7))
        scene = GeometryCompiler().compile(city)
        self.assertTrue(any(p.semantic_class == 'stair_tread' for p in scene.primitives))
        stairs = [e for e in scene.navigation.edges if e.traversal == 'stairs']
        self.assertTrue(stairs)
        nodes = {n.id: n for n in scene.navigation.nodes}
        self.assertTrue(all(abs(nodes[e.start_node_id].level - nodes[e.end_node_id].level) == 1
                            for e in stairs))

    def test_scoped_geometry_furniture_and_selection(self):
        city=BaselineCityPlanner().plan(CitySpec(name="Scoped interiors",building_count=4,
            min_floors=3,max_floors=3,width_m=160,depth_m=160,seed=17))
        scope=select_scope(city,2,2)
        self.assertEqual(len(scope["building_levels"]),2)
        from cityg.geometry.incremental import building_fingerprints
        before=building_fingerprints(city)
        key=next(iter(scope["building_levels"]))
        scope["building_levels"][key].append(2)
        self.assertNotEqual(before[key],building_fingerprints(city)[key])
        scope["building_levels"][key].pop()
        FloorDetailAgent().populate(city,seed=17)
        allowed={r.id for b in city.iter_buildings() for f in b.floors
                 if floor_enabled(city,b,f) for r in f.rooms}
        self.assertTrue(set(select_hero_rooms(city,max_rooms=10).room_ids)<=allowed)
        for b in city.iter_buildings():
            for f in b.floors:
                if not floor_enabled(city,b,f):self.assertEqual(f.objects,[])
        scene=GeometryCompiler().compile(city)
        report=GeometryValidator().validate(city,scene)
        self.assertTrue(report.ok,report.to_dict())
        for b in city.iter_buildings():
            for f in b.floors:
                if not floor_enabled(city,b,f):
                    self.assertFalse(any(p.layer_id==f"floor:{f.id}" for p in scene.primitives))
                    self.assertFalse(any(n.owner_id in {r.id for r in f.rooms} for n in scene.navigation.nodes))


if __name__=="__main__":unittest.main()
