import tempfile
import unittest
from pathlib import Path

from cityg.assets import AssetRegistry,AssetRecord
from cityg.geometry import GeometryCompiler
from cityg.geometry.geography import primitive_footprint
from cityg.geometry.model import GeometryScene,Vec3
from cityg.geometry.metro_sites import compile_metro_entrances,VERSION
from cityg.polygons import geos,parcel_shape,box_shape
from cityg.schemas import Bounds2D,Building,City,District,Parcel,Point2D,RoadNetwork
from cityg.serialization import to_primitive


class MetroSiteTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        asset=Path(self.temp.name)/'metro.glb';asset.touch()
        registry=AssetRegistry()
        registry.register(AssetRecord('station','metro_entrance',geometry_path=str(asset),
            dimensions_m=(10,5,7),environment='outdoor',metadata={'outdoor_pack_status':'ready',
            'ground_anchor_fraction':.5,'metro_placement':{'reviewed':True,'front_axis':'+X',
                'opening_unit_bounds':[-.4,-.3,.2,.3]}}))
        self.c=GeometryCompiler(registry,include_interiors=False)
        building=Building('b','b','commercial',Bounds2D(30,30,65,65),Point2D(45,30))
        self.p=Parcel('p',Bounds2D(0,0,100,100),[building])
        self.city=City('c','c',self.p.bounds,RoadNetwork(),[District('d','d','commercial',self.p.bounds,[self.p])],
            metadata={'metro_entrances':{'count':1,'min_spacing_m':0}})
        self.entry=self.c._box('frontage','b',Vec3(45,15,.13),Vec3(3,30,.1),0,
            'frontage_connector','concrete','roads',metadata={'building_id':'b'})
        self.ground=self.c._box('ground','c',Vec3(50,50,-.1),Vec3(100,100,.2),0,
            'city_ground','concrete','roads',metadata={'ground_plane':True})
        self.scene=GeometryScene('c',self.city.coordinate_system,primitives=[self.entry,self.ground])

    def test_placement_connection_opening_and_repeatability(self):
        report=compile_metro_entrances(self.c,self.city,self.scene)
        self.assertEqual(report['placed_count'],1,report)
        node=report['entrances'][0];hole=geos().Polygon(node['opening_polygon'])
        mesh=next(p for p in self.scene.primitives if p.semantic_class=='metro_entrance')
        self.assertTrue(parcel_shape(self.p).covers(primitive_footprint(mesh)))
        self.assertFalse(box_shape(self.p.buildings[0].footprint).intersects(primitive_footprint(mesh)))
        self.assertFalse(primitive_footprint(self.entry).intersects(primitive_footprint(mesh)))
        self.assertAlmostEqual(mesh.center.z,.13)
        ground=next(p for p in self.scene.primitives if p.id=='ground')
        self.assertLess(primitive_footprint(ground).intersection(hole).area,1e-7)
        self.assertEqual(to_primitive(self.entry),to_primitive(self.scene.primitives[0]))
        before=to_primitive(self.scene)
        compile_metro_entrances(self.c,self.city,self.scene)
        self.assertEqual(before,to_primitive(self.scene))
        self.assertFalse(report['underground_simulated'])

    def test_disabled_restores_ground_and_removes_only_metro(self):
        compile_metro_entrances(self.c,self.city,self.scene)
        self.city.metadata['metro_entrances']['enabled']=False
        compile_metro_entrances(self.c,self.city,self.scene)
        self.assertEqual(to_primitive(self.scene.primitives),to_primitive([self.entry,self.ground]))

    def test_unreviewed_or_missing_asset_is_not_substituted(self):
        record=self.c.asset_registry.require('station');record.metadata['metro_placement']['reviewed']=False
        report=compile_metro_entrances(self.c,self.city,self.scene)
        self.assertEqual(report['status'],'skipped_no_reviewed_asset')
        self.assertEqual(len(self.scene.primitives),2)

    def test_no_existing_connection_no_disconnected_station(self):
        self.scene.primitives=[self.ground]
        report=compile_metro_entrances(self.c,self.city,self.scene)
        self.assertEqual(report['placed_count'],0)

    def test_occupied_parcel_is_skipped(self):
        obstruction=self.c._box('busy','another_owner',Vec3(50,50,2),Vec3(100,100,4),0,'street_asset','concrete','roads')
        self.scene.primitives.append(obstruction)
        self.assertEqual(compile_metro_entrances(self.c,self.city,self.scene)['placed_count'],0)

    def test_invalid_count_is_rejected(self):
        self.city.metadata['metro_entrances']['count']=-1
        with self.assertRaises(ValueError):compile_metro_entrances(self.c,self.city,self.scene)

    def test_explicit_decoration_budget_is_bounded_reversible_and_repeatable(self):
        shrub=self.c._box('shrub','p',Vec3(50,50,1),Vec3(100,100,2),0,'parcel_shrub_asset','concrete','roads')
        self.scene.primitives.append(shrub)
        original=to_primitive(self.scene.primitives)
        self.assertEqual(compile_metro_entrances(self.c,self.city,self.scene)['placed_count'],0)
        self.city.metadata['metro_entrances']['max_decor_removals_per_entrance']=1
        report=compile_metro_entrances(self.c,self.city,self.scene)
        self.assertEqual(report['placed_count'],1,report)
        self.assertEqual(report['removed_decoration_ids'],['shrub'])
        snapshot=to_primitive(self.scene)
        compile_metro_entrances(self.c,self.city,self.scene)
        self.assertEqual(snapshot,to_primitive(self.scene))
        self.city.metadata['metro_entrances']['enabled']=False
        compile_metro_entrances(self.c,self.city,self.scene)
        self.assertEqual(original,to_primitive(self.scene.primitives))


if __name__=='__main__':unittest.main()
