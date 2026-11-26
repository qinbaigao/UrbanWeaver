"""Additive street/building planting must leave circulation and architecture intact."""
import unittest

import test_dense_greenery
from cityg.assets import AssetRecord, AssetRegistry
from cityg.geometry import GeometryCompiler
from cityg.geometry.dense_greenery import obstacle_index
from cityg.geometry.geography import primitive_footprint
from cityg.geometry.urban_greenbelts import compile_urban_greenbelts, KEY, VERSION
from cityg.polygons import geos, parcel_shape
from cityg.schemas import Point2D, RoadSegment
from cityg.serialization import to_primitive


class UrbanGreenbeltTests(unittest.TestCase):
    def setUp(self):
        # Reuse fixture setup only, not the original test methods.
        test_dense_greenery.DenseGreeneryTests.setUp(self)
        mesh=self.compiler.asset_registry.list_all()[0].geometry_path
        for tag in ('fern_02','shrub_sorrel_01','grass_medium_01','medium_fir'):
            tree=tag=='medium_fir'
            self.compiler.asset_registry.register(AssetRecord(tag,'street_tree' if tree else 'plant',
                tags=(tag,'tree') if tree else (tag,),geometry_path=mesh,environment='outdoor',
                dimensions_m=(4,4,7) if tree else (1.8,1.6,.85),metadata={'style':'photorealistic_pbr'}))
        self.city.metadata={KEY:{'enabled':True,'version':VERSION}}
        self.city.road_network.segments=[RoadSegment('road','j0','j1',(Point2D(-10,-10),Point2D(160,-10)))]

    def test_beds_and_plants_safe_diverse_and_idempotent(self):
        original=to_primitive(self.scene.primitives)
        blocked=geos().union_all(obstacle_index(self.city,self.scene.primitives,include_vegetation=False).geometries)
        report=compile_urban_greenbelts(self.compiler,self.city,self.scene)
        self.assertGreater(report['new_asset_instances'],80)
        self.assertGreater(len(report['asset_counts']),5)
        self.assertGreater(report['bed_counts']['street_border'],0)
        self.assertGreater(report['bed_counts']['building_garden'],0)
        self.assertEqual(original,to_primitive(self.scene.primitives[:1]))
        for p in self.scene.primitives[1:]:
            fp=primitive_footprint(p)
            self.assertTrue(parcel_shape(self.parcel).buffer(1e-8).covers(fp),p.id)
            self.assertLess(blocked.intersection(fp).area,1e-8,p.id)
        ids=[p.id for p in self.scene.primitives]
        self.assertEqual(len(ids),len(set(ids)))
        first=to_primitive(self.scene.primitives)
        compile_urban_greenbelts(self.compiler,self.city,self.scene)
        self.assertEqual(first,to_primitive(self.scene.primitives))

    def test_missing_assets_no_empty_soil_and_existing_layer_retained(self):
        compile_urban_greenbelts(GeometryCompiler(AssetRegistry()),self.city,self.scene)
        self.assertEqual(self.scene.primitives,[self.path])
        compile_urban_greenbelts(self.compiler,self.city,self.scene)
        before=to_primitive(self.scene.primitives)
        compile_urban_greenbelts(GeometryCompiler(AssetRegistry()),self.city,self.scene)
        self.assertEqual(before,to_primitive(self.scene.primitives))

    def test_construction_and_periphery_untouched(self):
        self.city.metadata['construction_sites']={'sites':[{'parcel_id':self.parcel.id}]}
        self.city.metadata['edge_landscape_extension']={'park_bounds':dict(min_x=160,min_y=0,max_x=260,max_y=140)}
        report=compile_urban_greenbelts(self.compiler,self.city,self.scene)
        self.assertEqual(report['new_primitives'],0)
        self.assertEqual(self.scene.primitives,[self.path])

    def test_irregular_parcel_holes_and_invalid_density(self):
        self.parcel.boundary=tuple(Point2D(x,y) for x,y in [(0,0),(150,10),(120,140),(15,120)])
        self.parcel.holes=(tuple(Point2D(x,y) for x,y in [(20,40),(45,40),(45,65),(20,65)]),)
        compile_urban_greenbelts(self.compiler,self.city,self.scene)
        self.assertGreater(len(self.scene.primitives),30)
        for p in self.scene.primitives[1:]:
            self.assertTrue(parcel_shape(self.parcel).buffer(1e-8).covers(primitive_footprint(p)))
        before=to_primitive(self.scene.primitives)
        self.city.metadata[KEY]['density']=float('nan')
        with self.assertRaises(ValueError):compile_urban_greenbelts(self.compiler,self.city,self.scene)
        self.assertEqual(before,to_primitive(self.scene.primitives))


if __name__=='__main__':unittest.main()
