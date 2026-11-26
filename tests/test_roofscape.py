import unittest
from dataclasses import replace

from cityg.geometry import GeometryCompiler
from cityg.geometry.geography import polygon_mesh, primitive_footprint
from cityg.geometry.model import GeometryScene,Vec3
from cityg.geometry.roof_surfaces import roof_surfaces,flat_top
from cityg.geometry.roofscape import compile_roofscape,VERSION,SIZES
from cityg.geometry.roof_assemblies import furnish_roof_zone
from cityg.polygons import geos
from cityg.planning import BaselineCityPlanner
from cityg.schemas import CitySpec
from cityg.serialization import to_primitive


class RoofscapeTests(unittest.TestCase):
    def setUp(self):
        self.compiler=GeometryCompiler(include_interiors=False)
        self.city=BaselineCityPlanner().plan(CitySpec(building_count=1,min_floors=2,max_floors=2))
        self.b=next(self.city.iter_buildings());self.b.metadata['roof_program']={'profile':'mixed'}
        self.scene=GeometryScene(self.city.id,self.city.coordinate_system,materials=self.compiler._materials())
        self.roof=self.compiler._box('roof',self.b.id,Vec3(0,0,10),Vec3(60,45,.2),0,'roof','roof','shell:'+self.b.id)
        self.scene.primitives=[self.roof]

    def test_surface_union_excludes_holes_and_upper_tower(self):
        s=geos();shape=s.box(-30,-25,30,25).difference(s.box(-5,-5,5,5))
        lower=polygon_mesh('lower',self.b.id,shape,10,.2,'roof','roof')
        upper=replace(self.roof,id='upper',center=Vec3(15,0,20),size=Vec3(10,10,.2))
        surfaces=roof_surfaces([lower,upper])
        self.assertEqual(len(surfaces),2)
        self.assertFalse(surfaces[0]['shape'].intersects(s.box(-4,-4,4,4)))
        self.assertFalse(surfaces[0]['shape'].intersection(primitive_footprint(upper)).area)
        self.assertAlmostEqual(surfaces[0]['z'],10)

    def test_sloped_roof_not_treated_as_flat(self):
        p=polygon_mesh('slope',self.b.id,geos().box(0,0,10,10),lambda x,y:10+x*.3,.2,'roof','roof')
        self.assertIsNone(flat_top(p))
        self.assertIsNone(flat_top(replace(self.roof,metadata={'roof_style':'pitched'})))

    def test_service_path_extrusion_omits_repeated_ring_coordinate(self):
        shape=geos().Polygon([(0,0),(10,0),(10,0),(10,5),(0,5),(0,0)])
        p=polygon_mesh('path',self.b.id,shape,10,.025,'roof_surface_detail','roof')
        self.assertTrue(all(len(set(f))==3 for f in p.metadata['mesh_triangles']))
        self.assertAlmostEqual(primitive_footprint(p).area,shape.area)

    def test_compact_zones_on_narrow_roof_ignore_superseded_envelope(self):
        self.b.metadata['roof_program']={'profile':'garden'}
        self.scene.primitives=[replace(self.roof,size=Vec3(55,10,.2)),
            replace(self.roof,id='obsolete_proxy',semantic_class='collision_envelope',
                    center=Vec3(0,0,12),metadata={'collision_representation':'superseded_planning_envelope'})]
        report=compile_roofscape(self.compiler,self.city,self.scene)
        self.assertGreater(report['zone_counts'].get('garden',0),0,report)

    def test_explicit_agent_palette_rejects_unsupported_profile(self):
        from cityg.planning.programs import BuildingProgram, BuildingProfile
        from cityg.schemas import ZoneSpec
        spec=CitySpec(zones=(ZoneSpec('homes','residential',1.0),))
        profile=BuildingProfile.from_dict(dict(function='residential',floor_policy='midpoint',
            entrance_side='west',prototype_id='residential_slab',roof_profile_palette=['garden','solar']))
        BuildingProgram((profile,)).validate(spec)
        with self.assertRaisesRegex(ValueError,'roof profile'):
            BuildingProgram((replace(profile,roof_profile_palette=('invalid',)),)).validate(spec)

    def test_all_assemblies_supported_bounded_and_clear_apron(self):
        s=geos()
        from cityg.geometry.roof_surfaces import to_world
        for angle in (0,33,90):
            for kind,(w,d) in SIZES.items():
                bounds=(-w/2,-d/2,w/2,d/2);origin=(31,25)
                pad=to_world(s.box(*bounds),origin,angle)
                parts=furnish_roof_zone(self.compiler,self.b,'zone',kind,bounds,origin,angle,12,{'support_z':12})
                self.assertGreater(len(parts),3)
                apron=to_world(s.box(-w/2,-d/2,w/2,-d/2+1.3),origin,angle)
                for p in parts:
                    self.assertTrue(pad.buffer(1e-6).covers(primitive_footprint(p)),p.id)
                    self.assertGreaterEqual(p.center.z-p.size.z/2,12-1e-6,p.id)
                    if p.metadata.get('ground_obstacle'):
                        self.assertLess(primitive_footprint(p).intersection(apron).area,1e-6,p.id)

    def test_idempotent_preserves_original_and_realizes_varied_zones(self):
        original=to_primitive(self.roof)
        report=compile_roofscape(self.compiler,self.city,self.scene)
        self.assertEqual(report['building_count'],1)
        self.assertGreater(sum(report['zone_counts'].values()),0,report)
        self.assertEqual(to_primitive(self.roof),original)
        first=to_primitive(self.scene)
        compile_roofscape(self.compiler,self.city,self.scene)
        self.assertEqual(first,to_primitive(self.scene))
        for p in self.scene.primitives:
            if p.metadata.get('roof_system')==VERSION:
                self.assertTrue(primitive_footprint(self.roof).buffer(1e-5).covers(primitive_footprint(p)))

    def test_normal_compiler_and_scoped_compiler_integration(self):
        city=BaselineCityPlanner().plan(CitySpec(building_count=2,min_floors=2,max_floors=2))
        city.metadata['roofscape']={'enabled':True}
        full=self.compiler.compile(city)
        self.assertGreater(full.metadata['roofscape']['new_primitives'],0)
        target=next(city.iter_buildings()).id
        subset=self.compiler.compile(city,building_ids={target})
        self.assertEqual({p.owner_id for p in subset.primitives if p.metadata.get('roof_system')},{target})

    def test_unrequested_and_invalid_program_leave_geometry_intact(self):
        self.b.metadata.pop('roof_program');before=to_primitive(self.scene)
        self.assertEqual(compile_roofscape(self.compiler,self.city,self.scene)['status'],'not_requested')
        self.assertEqual(before,to_primitive(self.scene))
        self.b.metadata['roof_program']={'profile':'unknown'}
        with self.assertRaises(ValueError):compile_roofscape(self.compiler,self.city,self.scene)
        self.assertEqual(before,to_primitive(self.scene))


if __name__=='__main__':unittest.main()
