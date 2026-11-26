import unittest

import test_dense_greenery
from cityg.assets import AssetRegistry
from cityg.geometry import GeometryCompiler
from cityg.geometry.geography import primitive_footprint
from cityg.geometry.model import Vec3
from cityg.geometry.validation import GeometryValidator
from cityg.geometry.street_tree_infill import compile_street_tree_infill, KEY, VERSION
from cityg.paths import PlanarPath2D
from cityg.polygons import geos, parcel_shape, road_shape
from cityg.schemas import Bounds2D, Building, Parcel, Point2D, RoadSegment
from cityg.serialization import to_primitive
from cityg.validation import ValidationReport


class StreetTreeInfillTests(unittest.TestCase):
    def setUp(self):
        test_dense_greenery.DenseGreeneryTests.setUp(self)
        b=Building('south_b','south','residential',Bounds2D(55,-100,85,-70),Point2D(70,-70))
        self.south=Parcel('south_parcel',Bounds2D(0,-160,150,-20),[b])
        self.city.districts[0].parcels.append(self.south)
        self.city.bounds=Bounds2D(0,-160,150,140)
        self.city.metadata={KEY:{'enabled':True,'version':VERSION}}
        self.road=RoadSegment('road','j0','j1',(Point2D(-20,-10),Point2D(170,-10)))
        self.city.road_network.segments=[self.road]
        self.bed=self.compiler._box('existing_bed',self.parcel.id,Vec3(30,6,.1),Vec3(25,8,.1),0,
                                    'parcel_planting_bed','mulch_warm','roads')
        self.scene.primitives.append(self.bed)

    def test_only_roadside_trees_both_sides_and_unchanged_old_scene(self):
        before=to_primitive(self.scene.primitives)
        report=compile_street_tree_infill(self.compiler,self.city,self.scene)
        self.assertGreater(report['new_asset_instances'],4)
        self.assertEqual(set(report['side_counts']),{'left','right'})
        self.assertGreater(len(report['asset_counts']),1)
        self.assertEqual(before,to_primitive(self.scene.primitives[:2]))
        path=PlanarPath2D(self.road.centerline)
        for p in self.scene.primitives[2:]:
            self.assertEqual(p.semantic_class,'street_tree_asset')
            self.assertEqual(p.metadata['planting_role'],'canopy')
            self.assertLessEqual(p.metadata['roadside_inset_m'],9)
            proj=path.project(Point2D(p.center.x,p.center.y))
            self.assertLessEqual(abs(proj.lateral),self.road.width_m/2+self.road.sidewalk_width_m+9+1e-6)
            parcel=self.parcel if p.owner_id==self.parcel.id else self.south
            fp=primitive_footprint(p)
            self.assertTrue(parcel_shape(parcel).covers(fp))
            self.assertFalse(fp.intersects(road_shape(self.road,.65)))
            self.assertFalse(fp.intersects(primitive_footprint(self.path)))
        first=to_primitive(self.scene.primitives)
        compile_street_tree_infill(self.compiler,self.city,self.scene)
        self.assertEqual(first,to_primitive(self.scene.primitives))

    def test_follows_curved_road_not_endpoint_chord(self):
        self.road.centerline=(Point2D(-20,-10),Point2D(70,-3),Point2D(170,-10))
        report=compile_street_tree_infill(self.compiler,self.city,self.scene)
        self.assertGreater(report['new_asset_instances'],2)
        for p in self.scene.primitives[2:]:
            self.assertFalse(primitive_footprint(p).intersects(road_shape(self.road,.65)))

    def test_construction_and_unoccupied_parcels_excluded(self):
        self.city.metadata['construction_sites']={'sites':[{'parcel_id':self.parcel.id}]}
        self.south.buildings=[]
        report=compile_street_tree_infill(self.compiler,self.city,self.scene)
        self.assertEqual(report['new_asset_instances'],0)
        self.assertEqual(self.scene.primitives,[self.path,self.bed])

    def test_junction_clearance(self):
        self.city.road_network.segments=[
            RoadSegment('a','j0','cross',(Point2D(-20,-10),Point2D(70,-10))),
            RoadSegment('b','cross','j1',(Point2D(70,-10),Point2D(170,-10))),
            RoadSegment('c','cross','j2',(Point2D(70,-10),Point2D(70,140)))]
        compile_street_tree_infill(self.compiler,self.city,self.scene)
        keep_clear=geos().Point(70,-10).buffer(12.5)
        self.assertGreater(len(self.scene.primitives),2)
        for p in self.scene.primitives[2:]:
            self.assertFalse(primitive_footprint(p).intersects(keep_clear))

    def test_missing_assets_and_invalid_density_do_not_erase(self):
        compile_street_tree_infill(GeometryCompiler(AssetRegistry()),self.city,self.scene)
        self.assertEqual(self.scene.primitives,[self.path,self.bed])
        compile_street_tree_infill(self.compiler,self.city,self.scene)
        old=to_primitive(self.scene.primitives)
        compile_street_tree_infill(GeometryCompiler(AssetRegistry()),self.city,self.scene)
        self.assertEqual(old,to_primitive(self.scene.primitives))
        self.city.metadata[KEY]['density']=float('nan')
        with self.assertRaises(ValueError):compile_street_tree_infill(self.compiler,self.city,self.scene)
        self.assertEqual(old,to_primitive(self.scene.primitives))

    def test_export_validator_recognizes_greenbelt_but_rejects_spoofed_domain(self):
        compile_street_tree_infill(self.compiler,self.city,self.scene)
        report=ValidationReport()
        GeometryValidator._validate_streetscape(self.city,self.scene,report)
        self.assertFalse(report.issues)
        tree=self.scene.primitives[-1]
        original=tree.center
        tree.center=Vec3(40,40,tree.center.z)
        report=ValidationReport()
        GeometryValidator._validate_streetscape(self.city,self.scene,report)
        self.assertIn('roadside_tree_outside_greenbelt',[i.code for i in report.issues])
        tree.center=original
        tree.metadata.pop('placement_domain')
        report=ValidationReport()
        GeometryValidator._validate_streetscape(self.city,self.scene,report)
        self.assertIn('street_tree_outside_furniture_strip',[i.code for i in report.issues])


if __name__=='__main__':unittest.main()
