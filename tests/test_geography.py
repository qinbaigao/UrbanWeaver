import importlib.util
import tempfile
import unittest
from pathlib import Path

from cityg.ccwp import build_world_program
from cityg.geometry import GeometryCompiler, GeometryValidator
from cityg.geometry.geography import polygon_mesh, primitive_footprint
from cityg.geometry.incremental import merge_building_scene
from cityg.geometry.model import GeometryScene
from cityg.observation import AdaptiveObservationPlanner
from cityg.planning import BaselineCityPlanner
from cityg.polygons import box_shape, geos, inscribed_bounds, parcel_shape, river_shape, rings
from cityg.schemas import (Bounds2D, Bridge, City, CitySpec, Junction, Parcel, Point2D,
                           River, RoadNetwork, RoadSegment, District)
from cityg.serialization import city_from_dict, to_primitive
from cityg.validation import ValidationReport
from cityg.validation import CityValidator
from cityg.validation.geography import validate_geography, validate_geography_geometry
from cityg.usd import UsdaWriter


HAS_GEOS = importlib.util.find_spec("shapely") is not None


def waterfront_fixture():
    a, b = Point2D(0,60), Point2D(160,60)
    road = RoadSegment("road", "a", "b", (a,b), width_m=10, sidewalk_width_m=2)
    river = River("river", "Test river", (Point2D(80,0),Point2D(80,120)), 20, 4, 6)
    city = City("test_waterfront", "Waterfront", Bounds2D(0,0,160,120),
        RoadNetwork([Junction("a",a),Junction("b",b)],[road]),
        rivers=[river], bridges=[Bridge("bridge","road","river",60,100)])
    city.world_program = build_world_program(city, producer="test", seed=0)
    return city


@unittest.skipUnless(HAS_GEOS, "Install cityg[geospatial] for polygon/water tests")
class GeographyTests(unittest.TestCase):
    def report(self, city):
        result = ValidationReport()
        validate_geography(city, result)
        return result

    def test_polygon_planning_with_and_without_river(self):
        for seed, river_mode in ((12, "meandering"), (2, "meandering"), (7, "none")):
            with self.subTest(seed=seed, river_mode=river_mode):
                city = BaselineCityPlanner().plan(CitySpec(
                    name="geography_test", width_m=400, depth_m=360,
                    building_count=4, min_floors=2, max_floors=3,
                    rooms_per_floor=2, seed=seed, parcel_layout="polygonal",
                    river_mode=river_mode, road_pattern="curved_hierarchy"))
                report = CityValidator().validate(city)
                self.assertTrue(report.ok, report.to_dict())
                self.assertEqual(len(list(city.iter_buildings())), 4)
                self.assertTrue(all(p.boundary for p in city.iter_parcels()))
                self.assertEqual(bool(city.bridges), river_mode != "none")

    def test_roundtrip_and_identity_relations(self):
        city = waterfront_fixture()
        copy = city_from_dict(to_primitive(city))
        self.assertEqual(copy.rivers, city.rivers)
        self.assertEqual(copy.bridges, city.bridges)
        self.assertIn("river", copy.metadata["identity_registry"]["entities"])
        self.assertTrue(any(r.relation_type == "crosses_water" for r in city.world_program.relations))
        self.assertTrue(self.report(copy).ok)

    def test_unbridged_crossing_and_dangling_reference_rejected(self):
        city = waterfront_fixture()
        city.bridges.clear()
        self.assertIn("unbridged_road_crossing", [i.code for i in self.report(city).errors])
        city = waterfront_fixture()
        city.bridges[0].river_id = "missing"
        self.assertIn("invalid_bridge", [i.code for i in self.report(city).errors])

    def test_short_bridge_clearance_and_floating_bridge_rejected(self):
        for field, value in (("end_m",75), ("min_clearance_m",6), ("deck_elevation_m",3), ("structural_depth_m",.1)):
            city = waterfront_fixture()
            setattr(city.bridges[0],field,value)
            self.assertFalse(self.report(city).ok, (field,value))

    def test_self_intersecting_parcel_rejected(self):
        city = waterfront_fixture()
        parcel = Parcel("p", Bounds2D(10,10,30,30), boundary=(Point2D(10,10),Point2D(30,30),Point2D(10,30),Point2D(30,10)))
        city.districts.append(District("d","D","mixed_use",parcel.bounds,[parcel]))
        self.assertIn("invalid_parcel_polygon", [i.code for i in self.report(city).errors])

    def test_polygon_hole_roundtrip_and_inscribed_envelope(self):
        s = geos()
        shape = s.box(0,0,60,60).difference(s.box(20,20,40,40))
        boundary, holes = rings(shape)
        parcel = Parcel("p",Bounds2D(0,0,60,60),boundary=boundary,holes=holes)
        city=waterfront_fixture()
        city.districts.append(District("d","D","mixed_use",parcel.bounds,[parcel]))
        loaded = city_from_dict(to_primitive(city))
        self.assertEqual(len(next(loaded.iter_parcels()).holes),1)
        self.assertAlmostEqual(parcel_shape(next(loaded.iter_parcels())).area,shape.area)
        bounds = inscribed_bounds(shape,min_size=8)
        self.assertTrue(shape.covers(box_shape(bounds)))

    def test_constrained_mesh_has_exact_area_and_closed_edges(self):
        s = geos()
        polygon = s.Polygon([(0,0),(8,0),(8,3),(5,3),(5,9),(0,9)],holes=[[(1,1),(1,2),(2,2),(2,1)]])
        primitive = polygon_mesh("p","p",polygon,0,.2,"parcel_ground","grass")
        self.assertLess(primitive_footprint(primitive).symmetric_difference(polygon).area,1e-7)
        incidence={}
        for a,b,c in primitive.metadata["mesh_triangles"]:
            for edge in ((a,b),(b,c),(c,a)):
                key=tuple(sorted(edge));incidence[key]=incidence.get(key,0)+1
        self.assertTrue(all(count==2 for count in incidence.values()))

    def test_bridge_navigation_ground_hole_and_noncolliding_water(self):
        city=waterfront_fixture()
        scene=GeometryCompiler(include_interiors=False).compile(city)
        report=GeometryValidator().validate(city,scene)
        # This isolated road/river fixture intentionally has no rooms.
        self.assertEqual([i.code for i in report.errors], ["empty_navigation_graph"], report.to_dict())
        bridge_edges=[e for e in scene.navigation.edges if e.bridge_id == "bridge"]
        self.assertEqual(len(bridge_edges),1)
        self.assertAlmostEqual(sum(e.distance_m for e in bridge_edges),40)
        water=next(p for p in scene.primitives if p.semantic_class=="river_water")
        ground=next(p for p in scene.primitives if p.semantic_class=="city_ground")
        self.assertFalse(water.collision_enabled)
        self.assertTrue(ground.collision_enabled)
        self.assertLess(primitive_footprint(ground).intersection(river_shape(city.rivers[0],"banks")).area,1e-6)
        scene.navigation.edges=[e for e in scene.navigation.edges if e.bridge_id is None]
        report=ValidationReport();validate_geography_geometry(city,scene,report)
        self.assertIn("bridge_navigation_gap",[i.code for i in report.errors])

    def test_observation_has_water_and_bridge_views(self):
        views=AdaptiveObservationPlanner()._waterfront_views(waterfront_fixture(),["bridge"])
        self.assertEqual(len(views),2)
        self.assertTrue(any("bridge" in v.target_entity_ids for v in views))

    def test_invalid_water_level_or_dimensions_rejected(self):
        for field,value in (("width_m",-1),("water_elevation_m",1),("bed_elevation_m",0),("setback_m",float("nan"))):
            city=waterfront_fixture();setattr(city.rivers[0],field,value)
            self.assertFalse(self.report(city).ok)

    def test_river_geometry_and_materials_survive_building_merge(self):
        city=waterfront_fixture()
        compiler=GeometryCompiler(include_interiors=False)
        previous=compiler.compile(city)
        subset=compiler.compile(city,building_ids=set())
        merged,_=merge_building_scene(city,previous,subset,set(),previous_city=city)
        self.assertIn("river_water",{m.id for m in merged.materials})
        report = GeometryValidator().validate(city,merged)
        self.assertEqual([i.code for i in report.errors], ["empty_navigation_graph"], report.to_dict())

    def test_usd_water_mesh_has_no_physics_api(self):
        city=waterfront_fixture();scene=GeometryCompiler(include_interiors=False).compile(city)
        with tempfile.TemporaryDirectory() as root:
            UsdaWriter().write(city,scene,root)
            content=(Path(root)/"layers/roads.usda").read_text()
            chunk=content.split('def Mesh "river_water"',1)[1].split('\n    }',1)[0]
            self.assertNotIn("PhysicsCollisionAPI",chunk)
            self.assertIn('def Mesh "bridge_deck"',content)


if __name__ == "__main__":
    unittest.main()
