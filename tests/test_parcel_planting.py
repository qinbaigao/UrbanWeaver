from pathlib import Path
import tempfile
import unittest

from cityg.assets import AssetRecord, AssetRegistry
from cityg.geometry import GeometryCompiler
from cityg.geometry.geography import primitive_footprint
from cityg.geometry.model import GeometryScene, Vec3
from cityg.geometry.parcel_planting import enrich_paved_parcels, PALETTES, VERSION
from cityg.polygons import box_shape, parcel_shape
from cityg.schemas import Bounds2D, Building, City, District, Parcel, Point2D, RoadNetwork
from cityg.serialization import to_primitive


class ParcelPlantingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        mesh = Path(self.temp.name)/'fixture.glb'; mesh.touch()
        registry = AssetRegistry()
        for tag in sorted({tag for p in PALETTES for tag in p[1:]}):
            registry.register(AssetRecord(tag, 'shrub' if tag in {'searsia','shrub_02'} else 'plant',
                tags=(tag,'shrub','ornamental'), geometry_path=str(mesh), environment='outdoor',
                dimensions_m=(.8,.8,.6), metadata={'style':'photorealistic_pbr','preserve_physical_proportions':True}))
        self.compiler = GeometryCompiler(registry,include_interiors=False)
        b = Building('b','office','commercial',Bounds2D(25,25,65,65),Point2D(45,25))
        self.parcel = Parcel('parcel_test',Bounds2D(0,0,100,90),[b])
        self.city = City('c','test',self.parcel.bounds,RoadNetwork(),[District('d','d','commercial',self.parcel.bounds,[self.parcel])])
        self.scene = GeometryScene('c',self.city.coordinate_system)

    def test_real_mixed_borders_fit_and_repeat_without_accumulation(self):
        report = enrich_paved_parcels(self.compiler,self.city,self.scene)
        self.assertGreaterEqual(report['new_asset_instances'],8)
        self.assertGreaterEqual(len(report['asset_counts']),3)
        for p in self.scene.primitives:
            self.assertTrue(parcel_shape(self.parcel).covers(primitive_footprint(p)))
            self.assertFalse(box_shape(self.parcel.buildings[0].footprint).intersects(primitive_footprint(p)))
        original = to_primitive(self.scene.primitives)
        enrich_paved_parcels(self.compiler,self.city,self.scene)
        self.assertEqual(original,to_primitive(self.scene.primitives))

    def test_residential_and_missing_asset_cases_preserve_existing_planting(self):
        old = self.compiler._sphere('old','parcel_test',Vec3(10,10,.5),Vec3(1,1,1),0,'parcel_shrub','landscape_shrub','roads')
        self.scene.primitives=[old]
        self.parcel.buildings[0].function='residential'
        enrich_paved_parcels(self.compiler,self.city,self.scene)
        self.assertEqual(self.scene.primitives,[old])
        self.parcel.buildings[0].function='commercial'
        enrich_paved_parcels(GeometryCompiler(AssetRegistry()),self.city,self.scene)
        self.assertEqual(self.scene.primitives,[old])

    def test_irregular_boundary_and_entrance_connector_are_excluded(self):
        self.parcel.boundary=tuple(Point2D(x,y) for x,y in [(0,0),(100,10),(90,90),(15,80)])
        connector=self.compiler._box('entry','road',Vec3(45,13,.1),Vec3(5,26,.2),0,'frontage_connector','concrete','roads')
        self.scene.primitives=[connector]
        enrich_paved_parcels(self.compiler,self.city,self.scene)
        plants=[p for p in self.scene.primitives if p.metadata.get('planting_system')==VERSION]
        self.assertTrue(plants)
        for p in plants:
            self.assertTrue(parcel_shape(self.parcel).covers(primitive_footprint(p)))
            self.assertFalse(primitive_footprint(connector).intersects(primitive_footprint(p)))


if __name__ == '__main__':
    unittest.main()
