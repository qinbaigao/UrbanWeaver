import unittest
import tempfile
from pathlib import Path
from cityg.assets import AssetRegistry,AssetRecord
from cityg.geometry import GeometryCompiler
from cityg.geometry.model import GeometryScene,Vec3
from cityg.geometry.geography import primitive_footprint
from cityg.geometry.parcel_sites import compile_parcel_sites,VERSION
from cityg.geometry.site_routing import route_in_polygon
from cityg.geometry.site_furnishings import furnish_site
from cityg.polygons import geos,parcel_shape,box_shape
from cityg.schemas import Bounds2D,Building,City,District,Parcel,Point2D,RoadNetwork
from cityg.serialization import to_primitive


class ParcelSiteTests(unittest.TestCase):
    def setUp(self):
        self.c=GeometryCompiler(AssetRegistry(),include_interiors=False)
        b=Building('b','test','residential',Bounds2D(25,25,65,65),Point2D(45,25))
        self.p=Parcel('p',Bounds2D(0,0,100,90),[b])
        self.city=City('city','test',self.p.bounds,RoadNetwork(),[District('d','d','residential',self.p.bounds,[self.p])])
        entry=self.c._box('entry','road',Vec3(45,12,.13),Vec3(3,24,.1),0,'frontage_connector','concrete','roads',metadata={'building_id':'b'})
        self.scene=GeometryScene('city',self.city.coordinate_system,primitives=[entry])
        self.city.metadata['parcel_site_programs']={'p':{'features':['pergola','cycle_shelter','service_hut']}}

    def test_routing_respects_full_width_and_does_not_cut_corners(self):
        s=geos();free=s.box(0,0,30,30).difference(s.box(10,0,20,22))
        path=route_in_polygon((5,5),(25,5),free)
        self.assertIsNotNone(path)
        self.assertTrue(free.covers(s.LineString(path).buffer(.9)))
        self.assertIsNone(route_in_polygon((5,5),(25,5),free.difference(s.box(0,23,30,30))))

    def test_nodes_are_connected_and_repeatable(self):
        report=compile_parcel_sites(self.c,self.city,self.scene)
        self.assertEqual(report['changed_parcel_count'],1)
        self.assertGreaterEqual(sum(report['node_counts'].values()),2)
        shape=parcel_shape(self.p);building=box_shape(self.p.buildings[0].footprint)
        for item in self.scene.primitives:
            if item.metadata.get('site_system')!=VERSION:continue
            footprint=primitive_footprint(item)
            self.assertTrue(shape.covers(footprint),item.id)
            self.assertFalse(building.intersects(footprint),item.id)
        original=to_primitive(self.scene.primitives)
        compile_parcel_sites(self.c,self.city,self.scene)
        self.assertEqual(original,to_primitive(self.scene.primitives))
        self.assertFalse(report['navigation_graph_extended'])

    def test_no_street_connection_means_no_disconnected_furniture(self):
        self.scene.primitives=[]
        report=compile_parcel_sites(self.c,self.city,self.scene)
        self.assertEqual(report['changed_parcel_count'],0)
        self.assertEqual(self.scene.primitives,[])

    def test_invalid_authored_program_is_not_silently_reinterpreted(self):
        self.city.metadata['parcel_site_programs']['p']['features']=['airport']
        report=compile_parcel_sites(self.c,self.city,self.scene)
        self.assertEqual(report['skips']['invalid_program'],1)
        self.assertEqual(len(self.scene.primitives),1)

    def test_person_variants_do_not_require_redundant_outdoor_keyword(self):
        with tempfile.TemporaryDirectory() as temp:
            mesh=Path(temp)/'person.glb';mesh.touch()
            for name,tags,style in [('a',('person','standing','outdoor'),'textured_authored'),
                                    ('b',('person','standing'),'textured_authored'),
                                    ('cartoon',('person','standing'),'stylized_low_poly')]:
                self.c.asset_registry.register(AssetRecord(name,'person',tags=tags,
                    geometry_path=str(mesh),environment='outdoor',metadata={'style':style}))
            seen=set()
            for i in range(20):
                parts=furnish_site(self.c,'p',f'node_{i}','pergola',(10,10),0,geos().box(5,5,15,15),{})
                seen.update(p.metadata['asset_id'] for p in parts if p.metadata.get('asset_id'))
            self.assertEqual(seen,{'a','b'})


if __name__=='__main__':unittest.main()
