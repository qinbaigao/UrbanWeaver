from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from cityg.geometry import GeometryCompiler, GeometryValidator
from cityg.geometry.construction_sites import SiteBuilder, plan_construction_sites, compile_construction_sites
from cityg.assets import AssetRecord, AssetRegistry
from cityg.geometry.model import GeometryScene, NavigationNode, NavigationEdge, Vec3
from cityg.geometry.geography import primitive_footprint
from cityg.planning import BaselineCityPlanner
from cityg.polygons import parcel_shape
from cityg.schemas import CitySpec
from cityg.serialization import to_primitive
from cityg.subtree_transactions import _refresh_world_program
from cityg.validation import CityValidator


class ConstructionTests(unittest.TestCase):
    def setUp(self):
        self.city=BaselineCityPlanner().plan(CitySpec(width_m=800,depth_m=800,building_count=3,
            min_floors=1,max_floors=1))
        self.compiler=GeometryCompiler(include_interiors=False)
        self.target=next(self.city.iter_buildings()).id

    def test_invalid_request_is_atomic(self):
        before=to_primitive(self.city)
        with self.assertRaises(ValueError):plan_construction_sites(self.city,[self.target,'missing'])
        self.assertEqual(before,to_primitive(self.city))

    def test_retirement_and_valid_canonical_city(self):
        plan_construction_sites(self.city,[self.target])
        _refresh_world_program(self.city,producer='test',changed_ids={self.city.id})
        self.assertEqual(len(list(self.city.iter_buildings())),2)
        self.assertTrue(CityValidator().validate(self.city).ok)
        with self.assertRaises(ValueError):plan_construction_sites(self.city,[self.target])

    def test_compile_preserves_unrelated_geometry_and_prunes_navigation(self):
        plan=plan_construction_sites(self.city,[self.target])
        scene=GeometryScene(self.city.id,self.city.coordinate_system,materials=self.compiler._materials())
        survivor=self.compiler._box('keep',self.city.id,Vec3(-20,-20,1),Vec3(1,1,1),0,'test','concrete','roads')
        old=deepcopy(survivor);old.id='remove';old.owner_id=self.target
        scene.primitives=[survivor,old]
        scene.navigation.nodes=[NavigationNode('keep_node',self.city.id,Vec3(0,0,0),'outdoor'),
            NavigationNode('retired_node',self.target,Vec3(2,0,0),'entrance')]
        scene.navigation.edges=[NavigationEdge('old_edge','keep_node','retired_node',2,2,'walk')]
        report=compile_construction_sites(self.compiler,self.city,scene)
        self.assertIn('remove',report['removed_primitive_ids'])
        self.assertEqual(scene.primitives[0],survivor)
        self.assertEqual(len(scene.navigation.nodes),1)
        self.assertEqual(scene.navigation.edges,[])
        before=to_primitive(scene.primitives)
        compile_construction_sites(self.compiler,self.city,scene)
        self.assertEqual(before,to_primitive(scene.primitives))
        parcel=next(p for p in self.city.iter_parcels() if p.id==plan['sites'][0]['parcel_id'])
        for p in scene.primitives[1:]:
            if p.semantic_class=='construction_access':continue
            self.assertTrue(parcel_shape(parcel).buffer(.01).covers(primitive_footprint(p)),p.id)

    def test_full_compile_geometry_valid(self):
        plan_construction_sites(self.city,[self.target])
        _refresh_world_program(self.city,producer='test',changed_ids={self.city.id})
        scene=self.compiler.compile(self.city)
        report=GeometryValidator().validate(self.city,scene)
        self.assertTrue(report.ok,[x.message for x in report.errors])
        self.assertTrue(any(p.semantic_class=='construction_slab' for p in scene.primitives))
        self.assertFalse(any(p.owner_id==self.target for p in scene.primitives))

    def test_asset_review_gate_fit_and_crane_anchor(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'fixture.glb';path.touch()
            registry=AssetRegistry()
            record=AssetRecord('construction_innerscene_tower_crane','construction_equipment',
                dimensions_m=(40,4,28),geometry_path=str(path),metadata={
                    'outdoor_pack_status':'ready','visual_review':{'status':'accepted'},
                    'mast_anchor_x_fraction':-.25})
            registry.register(record)
            compiler=GeometryCompiler(registry,include_interiors=False)
            b=SiteBuilder(compiler,dict(id='site',parcel_id='parcel',work_bounds=[0,0,120,100]))
            self.assertTrue(b.asset('tower_crane',30,50,scale=1.2,mast_anchor=True))
            mesh=b.primitives[0]
            self.assertAlmostEqual(mesh.center.x-.25*mesh.size.x,30)
            self.assertAlmostEqual(mesh.center.z-mesh.size.z/2,.18)
            self.assertFalse(b.asset('tower_crane',118,50,mast_anchor=True))
            record.metadata['visual_review']['status']='pending'
            self.assertFalse(b.asset('tower_crane',30,50,mast_anchor=True))


if __name__=='__main__':unittest.main()
