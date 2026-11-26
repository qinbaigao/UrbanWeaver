import unittest
import tempfile
from pathlib import Path

from cityg.assets import AssetRegistry, AssetRecord
from cityg.geometry import GeometryCompiler
from cityg.geometry.courtyard_furnishings import furnish_courtyard
from cityg.geometry.geography import primitive_footprint
from cityg.geometry.model import GeometryScene, Vec3
from cityg.geometry.parcel_courtyards import compile_parcel_courtyards, VERSION, SIZES, oriented_rectangle
from cityg.polygons import geos, parcel_shape, box_shape
from cityg.schemas import Bounds2D, Building, City, District, Floor, Parcel, Point2D, RoadNetwork
from cityg.serialization import to_primitive


class CourtyardTests(unittest.TestCase):
    def setUp(self):
        self.compiler=GeometryCompiler(AssetRegistry(),include_interiors=False)
        b=Building('b','test','residential',Bounds2D(35,35,75,75),Point2D(55,35))
        self.parcel=Parcel('p',Bounds2D(0,0,110,110),[b])
        self.city=City('city','test',self.parcel.bounds,RoadNetwork(),
            [District('d','d','residential',self.parcel.bounds,[self.parcel])])
        entry=self.compiler._box('entry','road',Vec3(55,17,.13),Vec3(3.5,34,.1),0,
            'frontage_connector','concrete','roads',metadata={'building_id':'b'})
        self.scene=GeometryScene('city',self.city.coordinate_system,primitives=[entry])
        self.city.metadata['parcel_courtyard_programs']={'p':{'theme':'mixed_use'}}

    def test_no_opt_in_leaves_scene_unchanged(self):
        self.city.metadata.clear()
        before=to_primitive(self.scene)
        self.assertEqual(compile_parcel_courtyards(self.compiler,self.city,self.scene)['status'],'not_requested')
        self.assertEqual(before,to_primitive(self.scene))

    def test_all_assemblies_fit_and_keep_walking_spine_clear_at_any_yaw(self):
        s=geos()
        for kind,(width,depth) in SIZES.items():
            for angle in (0,.7,1.57):
                pad,xy=oriented_rectangle(s,15,17,width,depth,angle)
                parts=furnish_courtyard(self.compiler,'p','node',kind,(15,17),angle,pad,{})
                self.assertGreaterEqual(len(parts),20 if kind=='pocket' else 25)
                spine=s.LineString([xy(0,-depth/2),xy(0,depth/2)]).buffer(1.)
                for p in parts:
                    self.assertTrue(pad.buffer(1e-7).covers(primitive_footprint(p)),p.id)
                    if p.metadata.get('ground_obstacle'):
                        self.assertLess(primitive_footprint(p).intersection(spine).area,1e-6,p.id)

    def test_dense_rotated_planting_stays_in_its_soil_bed(self):
        with tempfile.TemporaryDirectory() as temp:
            mesh=Path(temp)/'plant.glb';mesh.touch()
            for tag in ('flower_gazania','grass_medium_02','flower_ursinia','periwinkle','shrub_02','searsia'):
                category='shrub' if tag in {'shrub_02','searsia'} else 'plant'
                self.compiler.asset_registry.register(AssetRecord(tag,category,
                    tags=(tag,category,'ornamental'),geometry_path=str(mesh),environment='outdoor',
                    metadata={'style':'photorealistic_pbr'}))
            for angle in (0,.4,1.7):
                pad,_=oriented_rectangle(geos(),15,17,16,10,angle)
                parts=furnish_courtyard(self.compiler,'p','garden','garden',(15,17),angle,pad,{})
                plants=[p for p in parts if p.metadata.get('asset_category') in {'plant','shrub'}]
                self.assertGreaterEqual(len(plants),38)
                beds=geos().union_all([primitive_footprint(p) for p in parts if p.semantic_class=='parcel_planting_bed'])
                for plant in plants:
                    self.assertTrue(beds.covers(primitive_footprint(plant)),plant.id)

    def test_connected_safe_repeatable_and_no_original_changed(self):
        before=to_primitive(self.scene.primitives[0])
        report=compile_parcel_courtyards(self.compiler,self.city,self.scene)
        self.assertEqual(report['changed_parcel_count'],1)
        self.assertEqual(len(report['parcels'][0]['nodes']),4)
        shape=parcel_shape(self.parcel);building=box_shape(self.parcel.buildings[0].footprint)
        for p in self.scene.primitives[1:]:
            self.assertTrue(shape.covers(primitive_footprint(p)),p.id)
            self.assertFalse(building.intersects(primitive_footprint(p)),p.id)
        self.assertEqual(before,to_primitive(self.scene.primitives[0]))
        original=to_primitive(self.scene.primitives)
        compile_parcel_courtyards(self.compiler,self.city,self.scene)
        self.assertEqual(original,to_primitive(self.scene.primitives))
        self.assertFalse(report['navigation_graph_extended'])

    def test_grove_uses_registry_street_tree_categories_and_real_species_tags(self):
        with tempfile.TemporaryDirectory() as temp:
            mesh=Path(temp)/'tree.glb';mesh.touch()
            for name,tags in [('island',('island','tree','broadleaf')),('small',('tree','small','02','broadleaf'))]:
                self.compiler.asset_registry.register(AssetRecord(name,'street_tree',tags=tags,
                    geometry_path=str(mesh),environment='outdoor',metadata={'style':'photorealistic_pbr'}))
            for angle in (0,.7):
                pad,xy=oriented_rectangle(geos(),0,0,26,20,angle)
                parts=furnish_courtyard(self.compiler,'p','grove','grove',(0,0),angle,pad,{})
                trees=[p for p in parts if p.metadata.get('asset_category')=='street_tree']
                self.assertEqual(len(trees),4)
                self.assertEqual({p.metadata['asset_id'] for p in trees},{'island','small'})
                spine=geos().LineString([xy(0,-10),xy(0,10)]).buffer(1.)
                for tree in trees:
                    self.assertTrue(pad.covers(primitive_footprint(tree)))
                    self.assertFalse(spine.intersects(primitive_footprint(tree)))

    def test_missing_entry_skipped_not_fabricated(self):
        self.scene.primitives=[]
        result=compile_parcel_courtyards(self.compiler,self.city,self.scene)
        self.assertEqual(result['skips']['no_existing_connected_approach'],1)
        self.assertFalse(self.scene.primitives)

    def test_realized_floor_overrides_oversized_planning_envelope(self):
        b=self.parcel.buildings[0]
        b.footprint=Bounds2D(5,5,105,105)
        b.floors=[Floor('f',0,0,3.5)]
        slab=self.compiler._box('slab','f',Vec3(55,55,0),Vec3(20,20,.14),0,
            'floor_slab','concrete','roads')
        column=self.compiler._box('column','b',Vec3(25,25,1.5),Vec3(5,5,3),0,
            'exterior_wall','concrete','roads')
        self.scene.primitives.extend([slab,column])
        report=compile_parcel_courtyards(self.compiler,self.city,self.scene)
        self.assertEqual(report['parcels'][0]['footprint_sources']['b'],'compiled_ground_floor')
        self.assertEqual(len(report['parcels'][0]['nodes']),4)
        additions=[p for p in self.scene.primitives if p.metadata.get('site_system')==VERSION]
        self.assertTrue(any(box_shape(b.footprint).covers(primitive_footprint(p)) for p in additions))
        for p in additions:
            self.assertFalse(primitive_footprint(p).intersects(primitive_footprint(slab)),p.id)
            self.assertFalse(primitive_footprint(p).intersects(primitive_footprint(column)),p.id)

    def test_exterior_collision_replacement_is_reversible_and_not_used_for_interiors(self):
        from cityg.geometry.courtyard_collision import realize_exterior_collisions, restore_collision_overrides
        b=self.parcel.buildings[0];b.floors=[Floor('f',0,0,3.5)]
        mass=self.compiler._box('mass','b',Vec3(55,55,8),Vec3(20,20,16),0,
            'exterior_wall','concrete','roads',collision_enabled=False,metadata={'visual_proxy':True})
        proxy=self.compiler._box('proxy','f',Vec3(55,25,1.5),Vec3(50,.2,3),0,
            'collision_envelope','concrete','roads',collision_enabled=True)
        self.scene.primitives.extend([mass,proxy])
        original=to_primitive(self.scene)
        changes=realize_exterior_collisions(self.compiler,self.city,self.scene,self.city.metadata['parcel_courtyard_programs'])
        self.assertEqual(set(changes),{'mass','proxy'})
        self.assertTrue(mass.collision_enabled)
        self.assertFalse(proxy.collision_enabled)
        restore_collision_overrides(self.scene)
        self.assertEqual(original,to_primitive(self.scene))
        self.scene.metadata['interiors_compiled']=True
        self.assertEqual(realize_exterior_collisions(self.compiler,self.city,self.scene,{'p':{}}),{})
        self.assertTrue(proxy.collision_enabled)

    def test_citywide_briefs_preserve_worksites_and_scale_with_free_space(self):
        from cityg.geometry.courtyard_programs import citywide_programs, adaptive_features
        self.assertEqual(citywide_programs(self.city),{'p':{'theme':'residential','adaptive':True}})
        self.city.metadata['construction_sites']={'sites':[{'parcel_id':'p'}]}
        self.assertEqual(citywide_programs(self.city),{})
        self.assertEqual(adaptive_features('residential',250,3),['pocket','pocket'])
        large=adaptive_features('commercial',5000,3)
        self.assertEqual(len(large),8)
        self.assertIn('pavilion',large)
        self.assertIn('promenade',large)

    def test_adaptive_program_has_large_groups_and_reports_requested_kind(self):
        self.city.metadata['parcel_courtyard_programs']={'p':{'theme':'civic','adaptive':True}}
        report=compile_parcel_courtyards(self.compiler,self.city,self.scene)
        self.assertEqual(report['changed_parcel_count'],1)
        nodes=report['parcels'][0]['nodes']
        self.assertTrue(any(n['size_m'][0]>=26 for n in nodes))
        self.assertTrue(all('requested_kind' in n for n in nodes))
        self.assertEqual(report['omitted_parcels'],[])

    def test_adaptive_small_site_falls_back_without_changing_the_entry(self):
        self.parcel.bounds=Bounds2D(0,0,18,28)
        self.parcel.buildings=[]
        self.scene.primitives[0].owner_id='p'
        self.scene.primitives[0].semantic_class='parcel_walkway'
        self.scene.primitives[0].center=Vec3(9,4,.13)
        self.scene.primitives[0].size=Vec3(3,7,.1)
        self.scene.primitives[0].metadata={'connection':'sidewalk_setback_link'}
        self.city.metadata['parcel_courtyard_programs']={'p':{'theme':'residential','adaptive':True}}
        before=to_primitive(self.scene.primitives[0])
        report=compile_parcel_courtyards(self.compiler,self.city,self.scene)
        self.assertEqual(report['changed_parcel_count'],1)
        self.assertTrue(all(n['kind']=='pocket' for n in report['parcels'][0]['nodes']))
        self.assertEqual(before,to_primitive(self.scene.primitives[0]))

    def test_invalid_program_is_atomic(self):
        self.city.metadata['parcel_courtyard_programs']['p']['features']=['airport']
        before=to_primitive(self.scene)
        with self.assertRaises(ValueError):compile_parcel_courtyards(self.compiler,self.city,self.scene)
        self.assertEqual(before,to_primitive(self.scene))

    def test_explicit_empty_program_removes_only_own_layer(self):
        before=to_primitive(self.scene.primitives)
        compile_parcel_courtyards(self.compiler,self.city,self.scene)
        self.city.metadata['parcel_courtyard_programs']={}
        compile_parcel_courtyards(self.compiler,self.city,self.scene)
        self.assertEqual(before,to_primitive(self.scene.primitives))

    def test_certified_site_path_can_be_a_root_without_reinventing_an_entry(self):
        entry=self.scene.primitives[0]
        entry.owner_id='p'
        entry.semantic_class='parcel_walkway'
        entry.metadata={'connection':'sidewalk_setback_link'}
        report=compile_parcel_courtyards(self.compiler,self.city,self.scene)
        self.assertEqual(report['changed_parcel_count'],1)
        self.assertEqual(report['parcels'][0]['nodes'][0]['connection'],'existing_connected_site_path')

    def test_existing_obstacles_and_protected_pads_are_preserved(self):
        obstacle=self.compiler._box('protected','p',Vec3(20,80,1.5),Vec3(25,35,3),0,
            'metro_entrance','concrete','roads',metadata={'metro_system':'existing'})
        old_pad=self.compiler._box('old_pad','p',Vec3(90,15,.1),Vec3(20,20,.1),0,
            'parcel_activity_pad','concrete','roads')
        self.scene.primitives.extend([obstacle,old_pad])
        compile_parcel_courtyards(self.compiler,self.city,self.scene)
        for p in self.scene.primitives:
            if p.metadata.get('site_system')==VERSION:
                self.assertFalse(primitive_footprint(p).intersects(primitive_footprint(obstacle)),p.id)
                self.assertFalse(primitive_footprint(p).intersects(primitive_footprint(old_pad)),p.id)


if __name__=='__main__':unittest.main()
