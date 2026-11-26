import unittest
from copy import deepcopy

from cityg.geometry import GeometryCompiler
from cityg.geometry.residential_groups import compile_group_paths
from cityg.geometry.geography import primitive_footprint
from cityg.geometry.roof_surfaces import roof_surfaces
from cityg.planning import BaselineCityPlanner
from cityg.planning.residential_groups import replace_residential_groups, group_layout
from cityg.polygons import box_shape, geos, parcel_shape
from cityg.schemas import CitySpec, ZoneSpec
from cityg.serialization import to_primitive
from cityg.subtree_transactions import _refresh_world_program
from cityg.validation import CityValidator


class ResidentialGroupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = BaselineCityPlanner().plan(CitySpec(building_count=4, width_m=650, depth_m=650,
            layout_style='regular_grid', buildings_per_block=1, min_floors=4, max_floors=4,
            rooms_per_floor=2, height_strategy='uniform_random', zones=(ZoneSpec('homes','residential',1.),)))
        cls.source.metadata['interior_scope'] = {'policy':'prototype_exterior_only','building_levels':{}}

    def test_plan_is_valid_deterministic_and_source_unchanged(self):
        before = to_primitive(self.source)
        city, report = replace_residential_groups(self.source,1,1)
        other, r = replace_residential_groups(self.source,1,1)
        self.assertEqual(report,r); self.assertEqual(to_primitive(city),to_primitive(other))
        self.assertEqual(before,to_primitive(self.source))
        self.assertEqual(report['after_buildings'],13)
        _refresh_world_program(city,producer='groups_test',changed_ids={b.id for b in city.iter_buildings()})
        validation = CityValidator().validate(city)
        self.assertTrue(validation.ok,validation.to_dict())

    def test_rows_fit_have_real_party_walls_and_consistent_style(self):
        city, _ = replace_residential_groups(self.source,1,1)
        for p in city.iter_parcels():
            if len(p.buildings) == 1: continue
            self.assertEqual(len({b.metadata['facade_style_override'] for b in p.buildings}),1)
            self.assertTrue(all(parcel_shape(p).covers(box_shape(b.footprint)) for b in p.buildings))
            by_id = {b.id:b for b in p.buildings}
            for b in p.buildings:
                for side, neighbor in b.metadata['residential_group']['neighbors'].items():
                    a,c = box_shape(b.footprint),box_shape(by_id[neighbor].footprint)
                    self.assertAlmostEqual(a.intersection(c).area,0)
                    self.assertAlmostEqual(a.boundary.intersection(c.boundary).length,b.footprint.depth)

    def test_gables_no_party_windows_and_incremental_scope(self):
        city,_ = replace_residential_groups(self.source,0,1)
        homes = [b for b in city.iter_buildings() if b.metadata.get('residential_group')]
        _refresh_world_program(city,producer='test',changed_ids={b.id for b in homes})
        compiler = GeometryCompiler(include_interiors=False)
        scene = compiler.compile(city,building_ids={homes[1].id})
        roofs = [p for p in scene.primitives if p.semantic_class == 'roof']
        self.assertEqual(len(roofs),1); self.assertEqual(roofs[0].owner_id,homes[1].id)
        self.assertEqual(roof_surfaces(roofs),[])
        self.assertFalse(any(p.metadata.get('facade_side') in {'east','west'} for p in scene.primitives))
        self.assertAlmostEqual(roofs[0].size.x,homes[1].footprint.width)
        self.assertEqual(len(roofs[0].metadata['mesh_vertices']),3*len(roofs[0].metadata['mesh_triangles']))

    def test_paths_connect_every_entrance_without_crossing_buildings(self):
        city,_ = replace_residential_groups(self.source,1,1)
        _refresh_world_program(city,producer='test',changed_ids={b.id for b in city.iter_buildings()})
        compiler = GeometryCompiler(include_interiors=False)
        scene = compiler.compile(city,building_ids=set())
        records = compile_group_paths(compiler,city,scene)
        self.assertEqual(sum(r['connected_entrances'] for r in records),11)
        # Units in a row share the same last cross-walk before their door apron.
        homes = [b for b in city.iter_buildings() if b.metadata.get('residential_group',{}).get('kind')=='townhouses']
        for row in (0,1):
            row_homes = [b for b in homes if b.metadata['residential_group']['row']==row]
            self.assertEqual(len({tuple(b.metadata['group_access']['points'][-3]) for b in row_homes}),1)
        shapes = geos().union_all([box_shape(b.footprint) for b in city.iter_buildings()])
        for p in scene.primitives:
            if p.metadata.get('residential_group_paths'):
                self.assertLess(primitive_footprint(p).intersection(shapes).area,1e-5)

    def test_no_silent_partial_or_repeat_edit(self):
        with self.assertRaises(ValueError): replace_residential_groups(self.source,6,4)
        city,_ = replace_residential_groups(self.source,1,1)
        with self.assertRaises(ValueError): replace_residential_groups(city,1,1)
        source = deepcopy(self.source); source.metadata['interior_scope']['building_levels']={'building_000':[0]}
        with self.assertRaises(ValueError): replace_residential_groups(source,1,1)

    def test_bad_route_is_not_an_access_validation_bypass(self):
        from cityg.planning.group_access import group_access_valid
        city,_ = replace_residential_groups(self.source,0,1)
        b = next(b for b in city.iter_buildings() if b.metadata.get('group_access'))
        self.assertTrue(group_access_valid(city,b))
        b.metadata['group_access']['points'][-2] = [b.entrance.x,b.entrance.y+2]
        self.assertFalse(group_access_valid(city,b))
        _refresh_world_program(city,producer='test',changed_ids={b.id})
        self.assertFalse(CityValidator().validate(city).ok)

    def test_navigation_uses_route_vertices_not_a_direct_shortcut(self):
        city,_ = replace_residential_groups(self.source,0,1)
        _refresh_world_program(city,producer='test',changed_ids={b.id for b in city.iter_buildings()})
        scene = GeometryCompiler(include_interiors=False).compile(city,building_ids=set())
        b = next(b for b in city.iter_buildings() if b.metadata.get('group_access'))
        edges = [e for e in scene.navigation.edges if e.id.startswith('nav_group_access_'+b.id+'_')]
        self.assertEqual(len(edges),len(b.metadata['group_access']['points']))
        self.assertFalse(any(e.id.startswith('nav_access_'+b.id+'_') for e in scene.navigation.edges))

    def test_moving_one_attached_unit_requires_joint_replanning(self):
        from dataclasses import replace
        city,_ = replace_residential_groups(self.source,0,1)
        homes = [b for b in city.iter_buildings() if b.metadata.get('residential_group')]
        _refresh_world_program(city,producer='test',changed_ids={b.id for b in homes})
        b = homes[1]; b.footprint = replace(b.footprint,min_x=b.footprint.min_x+.5)
        with self.assertRaisesRegex(ValueError,'share a complete wall'):
            GeometryCompiler(include_interiors=False).compile(city,building_ids={b.id})


if __name__ == '__main__': unittest.main()
