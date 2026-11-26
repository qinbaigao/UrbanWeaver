import math
import tempfile
import unittest
from pathlib import Path

from cityg.ccwp import build_world_program, closest_point_on_segment, point_segment_distance
from cityg.geometry import GeometryCompiler, GeometryValidator
from cityg.geometry.model import GeometryScene
from cityg.geometry.path_mesh import compile_path_roads, path_slab
from cityg.geometry.streetscape import StreetscapeCompiler
from cityg.observation import AdaptiveObservationPlanner
from cityg.paths import PlanarPath2D, sample_cubic_bezier
from cityg.planning import BaselineCityPlanner
from cityg.schemas import Bounds2D, City, CitySpec, Junction, Point2D, RoadNetwork, RoadSegment
from cityg.serialization import city_from_dict, to_primitive
from cityg.usd import UsdaWriter, UsdaPackageValidator
from cityg.validation import CityValidator


def curved_city():
    points = sample_cubic_bezier(Point2D(10, 30), Point2D(45, 30),
                                 Point2D(65, 80), Point2D(110, 80), max_step_m=2)
    city = City("curve_city", "Curve test", Bounds2D(0, 0, 120, 110),
        RoadNetwork([Junction("start", points[0]), Junction("end", points[-1])],
                    [RoadSegment("curve", "start", "end", points, width_m=10)]))
    city.world_program = build_world_program(city, producer="path_test", seed=0)
    return city


class PlanarPathTests(unittest.TestCase):
    def test_length_projection_slice_and_duplicate_points(self):
        path = PlanarPath2D((Point2D(0, 0), Point2D(0, 0), Point2D(3, 0), Point2D(3, 4)))
        self.assertEqual(path.length, 7)
        self.assertEqual(path.point(5), Point2D(3, 2))
        self.assertEqual(path.point(5, 1), Point2D(2, 2))
        projected = path.project(Point2D(2, 2))
        self.assertEqual(projected.distance, 5)
        self.assertEqual(projected.lateral, 1)
        self.assertEqual(path.slice(1, 6).length, 5)
        self.assertEqual(path.heading(5), 90)
        self.assertEqual(closest_point_on_segment(Point2D(2, 2), path.points), Point2D(3, 2))
        self.assertEqual(point_segment_distance(Point2D(2, 2), path.points), 1)

    def test_invalid_paths_and_tight_bends(self):
        for points in ((), (Point2D(0, 0),)*2, (Point2D(float("nan"), 0), Point2D(2, 0))):
            with self.assertRaises(ValueError):
                PlanarPath2D(points)
        with self.assertRaises(ValueError):
            PlanarPath2D((Point2D(0, 0), Point2D(2, 0), Point2D(2, 2))).validate_corridor(4)

    def test_bezier_sampling_and_miter(self):
        path = PlanarPath2D(curved_city().road_network.segments[0].centerline)
        self.assertTrue(all(b-a <= 2.000001 for a, b in zip(path.stations, path.stations[1:])))
        path.validate_corridor(7.5)
        self.assertGreater(path.length, math.hypot(100, 50))
        self.assertEqual(len(path.offset_points(5)), len(path.points))

    def test_crossing_at_sample_vertex_is_found_once(self):
        a = PlanarPath2D((Point2D(0, 0), Point2D(5, 0), Point2D(10, 0)))
        b = PlanarPath2D((Point2D(5, -5), Point2D(5, 0), Point2D(5, 5)))
        self.assertEqual(a.intersections(b), [(5, 5, Point2D(5, 0))])

    def test_path_crosses_occupied_envelope_without_sample_inside(self):
        path = PlanarPath2D((Point2D(0, 5), Point2D(20, 5)))
        self.assertTrue(path.intersects_bounds(Bounds2D(8, 4, 12, 6)))
        self.assertFalse(path.intersects_bounds(Bounds2D(8, 8, 12, 10)))
        self.assertTrue(path.intersects_bounds(Bounds2D(8, 8, 12, 10), padding=3.1))

    def test_serialization_roundtrip_preserves_samples(self):
        city = curved_city()
        copy = city_from_dict(to_primitive(city))
        self.assertEqual(copy.road_network, city.road_network)

    def test_frame_position_and_heading_follow_curve(self):
        road = curved_city().road_network.segments[0]
        path = PlanarPath2D(road.centerline)
        frame = StreetscapeCompiler._frame(road)
        p = frame.point(path.length * .35, 6)
        self.assertEqual(p, path.point(path.length * .35, 6))
        self.assertAlmostEqual(StreetscapeCompiler._rotation(frame, p), path.heading(path.project(p).distance))


class CurvedRoadIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.city = curved_city()
        cls.scene = GeometryCompiler(include_interiors=False).compile(cls.city)

    def test_navigation_follows_samples_not_chord(self):
        path = PlanarPath2D(self.city.road_network.segments[0].centerline)
        edges = [e for e in self.scene.navigation.edges if e.id.startswith("nav_edge_curve")]
        self.assertAlmostEqual(sum(e.distance_m for e in edges), path.length)
        self.assertGreater(len(edges), 3)
        self.assertTrue(all(e.distance_m < 2.001 for e in edges))

    def test_compiler_uses_watertight_sweep_for_collision(self):
        p = next(p for p in self.scene.primitives if p.id == "curve")
        self.assertEqual(p.primitive_type, "path_mesh")
        self.assertTrue(p.collision_enabled)
        incidence = {}
        for a, b, c in p.metadata["mesh_triangles"]:
            for edge in ((a, b), (b, c), (c, a)):
                key = tuple(sorted(edge))
                incidence[key] = incidence.get(key, 0) + 1
        self.assertTrue(all(count == 2 for count in incidence.values()))
        self.assertTrue(any(p.semantic_class == "curb" and p.primitive_type == "path_mesh" for p in self.scene.primitives))

    def test_road_observation_uses_curve(self):
        view = AdaptiveObservationPlanner()._road_views(self.city, [])[0]
        path = PlanarPath2D(self.city.road_network.segments[0].centerline)
        position = path.point(path.length * .22, 2.2)
        self.assertAlmostEqual(view.camera_position[0], position.x)
        self.assertAlmostEqual(view.camera_position[1], position.y)

    def test_usd_contains_true_mesh_not_bounding_box_collision(self):
        with tempfile.TemporaryDirectory() as root:
            UsdaWriter().write(self.city, self.scene, root)
            road_text = (Path(root) / "layers/roads.usda").read_text()
            self.assertIn('def Mesh "curve"', road_text)
            self.assertIn('token physics:approximation = "none"', road_text)
            self.assertNotIn('def Cube "collision_curve"', road_text)
            report = UsdaPackageValidator().validate(Path(root) / "city.usda")
            # This isolated road fixture deliberately has no building payloads.
            self.assertEqual([i.code for i in report.errors], ["missing_payloads"])

    def test_optional_openusd_schema_check(self):
        try:
            from pxr import Usd, UsdGeom, UsdPhysics
        except ImportError:
            self.skipTest("Optional pxr runtime is not installed")
        with tempfile.TemporaryDirectory() as root:
            UsdaWriter().write(self.city, self.scene, root)
            stage = Usd.Stage.Open(str(Path(root) / "city.usda"))
            prim = stage.GetPrimAtPath("/City/Roads/curve")
            self.assertTrue(prim.IsA(UsdGeom.Mesh))
            self.assertTrue(prim.HasAPI(UsdPhysics.CollisionAPI))

    def test_navigation_access_joins_curve_at_projection(self):
        from copy import deepcopy
        city = deepcopy(self.city)
        baseline = BaselineCityPlanner().plan(CitySpec(name="access", building_count=1,
            width_m=120, depth_m=110, min_floors=1, max_floors=1, rooms_per_floor=2))
        city.districts = baseline.districts
        city.world_program = build_world_program(city, producer="test", seed=0)
        # Exercise the navigation mixin independently: this synthetic building
        # is not a spatially valid development layout for this road-only fixture.
        scene = GeometryScene(city.id, city.coordinate_system)
        scene.navigation = GeometryCompiler(include_interiors=False)._compile_navigation(city, scene)
        building = next(city.iter_buildings())
        edge = next(e for e in scene.navigation.edges if e.id == f"nav_access_{building.id}_path")
        node = next(n for n in scene.navigation.nodes if n.id == edge.start_node_id)
        path = PlanarPath2D(city.road_network.segments[0].centerline)
        projection = path.project(building.entrance)
        self.assertAlmostEqual(edge.distance_m, projection.separation)
        self.assertAlmostEqual(node.position.x, projection.point.x)
        self.assertAlmostEqual(node.position.y, projection.point.y)

    def test_unsplit_t_junction_is_rejected(self):
        city = curved_city()
        path = PlanarPath2D(city.road_network.segments[0].centerline)
        point = path.point(path.length/2)
        city.road_network.segments.append(RoadSegment("branch", "missing", "terminal",
            (point, Point2D(point.x, 105))))
        with self.assertRaisesRegex(ValueError, "shared junction"):
            compile_path_roads(city, GeometryScene(city.id, city.coordinate_system))


if __name__ == "__main__":
    unittest.main()
