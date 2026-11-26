from pathlib import Path
import tempfile
import unittest

from cityg.assets import AssetRecord, AssetRegistry
from cityg.geometry import GeometryCompiler
from cityg.geometry.dense_greenery import compile_dense_greenery, obstacle_index, KEY, VERSION, TREES
from cityg.geometry.geography import primitive_footprint
from cityg.geometry.model import GeometryScene, Vec3
from cityg.polygons import geos, parcel_shape
from cityg.schemas import Bounds2D, Building, City, District, Parcel, Point2D, RoadNetwork
from cityg.serialization import to_primitive


class DenseGreeneryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        mesh=Path(self.temp.name)/'plant.glb';mesh.touch();registry=AssetRegistry()
        specs=[(tag,'street_tree',tags,(4,3.5,6)) for tag,tags in TREES.items()]
        specs += [(tag,'shrub',(tag,'shrub','ornamental'),(1.4,1.2,1.6)) for tag in ('shrub_02','searsia','shrub')]
        specs += [(tag,'plant',(tag,),(1,1,.6)) for tag in ('grass_medium_02','flower_gazania','flower_heliophila','flower_ursinia','periwinkle')]
        for tag,category,tags,size in specs:
            registry.register(AssetRecord(tag,category,tags=(*tags,'tree'),geometry_path=str(mesh),environment='outdoor',
                dimensions_m=size,metadata={'style':'photorealistic_pbr'}))
        self.compiler=GeometryCompiler(registry,include_interiors=False)
        b=Building('b','housing','residential',Bounds2D(55,55,85,85),Point2D(70,55))
        self.parcel=Parcel('parcel_test',Bounds2D(0,0,150,140),[b])
        self.city=City('c','test',self.parcel.bounds,RoadNetwork(),
            [District('d','d','residential',self.parcel.bounds,[self.parcel])],metadata={KEY:{'enabled':True}})
        self.path=self.compiler._box('path','road',Vec3(70,26,.1),Vec3(4,52,.2),0,'frontage_connector','concrete','roads')
        self.scene=GeometryScene('c',self.city.coordinate_system,primitives=[self.path])

    def test_layered_proportional_assets_safe_and_idempotent(self):
        base=to_primitive(self.scene.primitives);index=obstacle_index(self.city,self.scene.primitives)
        report=compile_dense_greenery(self.compiler,self.city,self.scene)
        self.assertGreater(report['role_counts']['canopy'],20)
        self.assertGreater(report['role_counts']['understory'],20)
        self.assertGreater(len(report['asset_counts']),5)
        self.assertEqual(base,to_primitive(self.scene.primitives[:1]))
        blocked=geos().union_all(index.geometries)
        for p in self.scene.primitives[1:]:
            fp=primitive_footprint(p)
            self.assertTrue(parcel_shape(self.parcel).covers(fp))
            self.assertFalse(blocked.intersects(fp))
            dims=self.compiler.asset_registry.get(p.metadata['asset_id']).dimensions_m
            self.assertAlmostEqual(p.size.x/p.size.z,dims[0]/dims[2])
            self.assertAlmostEqual(p.center.z-p.size.z/2,.1)
        first=to_primitive(self.scene.primitives)
        compile_dense_greenery(self.compiler,self.city,self.scene)
        self.assertEqual(first,to_primitive(self.scene.primitives))

    def test_irregular_parcel_with_hole(self):
        self.parcel.boundary=tuple(Point2D(x,y) for x,y in [(0,0),(150,20),(120,140),(15,120)])
        self.parcel.holes=(tuple(Point2D(x,y) for x,y in [(20,40),(45,40),(45,65),(20,65)]),)
        compile_dense_greenery(self.compiler,self.city,self.scene)
        self.assertGreater(len(self.scene.primitives),10)
        for p in self.scene.primitives[1:]:
            self.assertTrue(parcel_shape(self.parcel).covers(primitive_footprint(p)))

    def test_off_missing_assets_and_invalid_config_preserve_scene(self):
        self.city.metadata={};compile_dense_greenery(self.compiler,self.city,self.scene)
        self.assertEqual(self.scene.primitives,[self.path])
        self.city.metadata={KEY:{'enabled':True}}
        compile_dense_greenery(GeometryCompiler(AssetRegistry()),self.city,self.scene)
        self.assertEqual(self.scene.primitives,[self.path])
        compile_dense_greenery(self.compiler,self.city,self.scene)
        old=to_primitive(self.scene.primitives)
        compile_dense_greenery(GeometryCompiler(AssetRegistry()),self.city,self.scene)
        self.assertEqual(old,to_primitive(self.scene.primitives))
        self.city.metadata[KEY]['density']=float('nan')
        with self.assertRaises(ValueError):compile_dense_greenery(self.compiler,self.city,self.scene)
        self.assertEqual(old,to_primitive(self.scene.primitives))

    def test_construction_parcels_not_planted(self):
        self.city.metadata['construction_sites']={'sites':[{'parcel_id':self.parcel.id}]}
        report=compile_dense_greenery(self.compiler,self.city,self.scene)
        self.assertEqual(report['new_asset_instances'],0)
        self.assertEqual(self.scene.primitives,[self.path])

    def test_landscape_site_binds_to_existing_city_owner(self):
        self.city.metadata['landscape_sites']=[{'id':'river_garden','boundary':[
            {'x':x,'y':y} for x,y in [(160,0),(260,0),(260,140),(160,140)]]}]
        compile_dense_greenery(self.compiler,self.city,self.scene)
        plants=[p for p in self.scene.primitives if p.metadata.get('landscape_site')=='river_garden']
        self.assertTrue(plants)
        self.assertTrue(all(p.owner_id==self.city.id for p in plants))

    def test_edge_hill_root_contact_and_path_clearance(self):
        self.city.metadata['edge_landscape_extension']={
            'park_bounds':dict(min_x=160,min_y=0,max_x=260,max_y=140),
            'hill_bounds':dict(min_x=270,min_y=0,max_x=370,max_y=140),
            'hill_height_m':24,'grid_step_m':6}
        path=self.compiler._box('park_walk','c',Vec3(210,70,.1),Vec3(4,140,.2),0,'landscape_path','concrete','roads')
        self.scene.primitives.append(path)
        compile_dense_greenery(self.compiler,self.city,self.scene)
        from cityg.geometry.edge_landscape import Heightfield
        plan=self.city.metadata['edge_landscape_extension']
        field=Heightfield(plan['hill_bounds'],24,6)
        hill=[p for p in self.scene.primitives if p.metadata.get('site')=='hill']
        self.assertTrue(hill)
        for p in hill:
            self.assertAlmostEqual(p.center.z-p.size.z/2,field(p.center.x,p.center.y))
        for p in self.scene.primitives:
            if p.metadata.get('site')=='park':
                self.assertFalse(primitive_footprint(p).intersects(primitive_footprint(path)))


if __name__=='__main__':unittest.main()
