"""Broad-phase pruning must not change exact road geometry or contacts."""
import random
import unittest
from unittest.mock import patch

from cityg.geometry.model import GeometryScene
from cityg.geometry.path_mesh import compile_path_roads
from cityg.geometry.streetscape import StreetscapeCompiler
from cityg.geometry.parcel_landscape import ParcelLandscapeCompilerMixin
from cityg.ccwp import point_segment_distance
from cityg.paths import PlanarPath2D, RoadClearanceQuery, sample_cubic_bezier
from cityg.schemas import Bounds2D, City, Junction, Point2D, RoadNetwork, RoadSegment
from cityg.serialization import to_primitive


class PathBroadPhaseTests(unittest.TestCase):
    def test_landscape_clearance_exact_with_more_roads_than_shared_cache(self):
        rng = random.Random(617)
        roads = [RoadSegment(str(i), 'a', 'b', tuple(
            Point2D(i*12+j*3, 50+8*j-j*j) for j in range(5)), width_m=4+i%12)
            for i in range(300)]
        roads.append(RoadSegment('wide', 'a', 'b', (Point2D(-5, -10), Point2D(5000, -10)), width_m=30))
        query = RoadClearanceQuery(roads)
        for p in [Point2D(5, 5), Point2D(5, 5-1e-8), Point2D(5, 5+1e-8)] + [
            Point2D(rng.uniform(-100, 4000), rng.uniform(-60, 150)) for _ in range(100)]:
            expected = min(point_segment_distance(p, r.centerline)-r.width_m/2 for r in roads)
            self.assertEqual(query(p), expected)
        with self.assertRaises(ValueError):
            RoadClearanceQuery([])(Point2D(0, 0))

    def test_public_landscape_geometry_matches_brute_force(self):
        from cityg.geometry import GeometryCompiler
        from cityg.planning import BaselineCityPlanner
        from cityg.schemas import CitySpec
        city = BaselineCityPlanner().plan(CitySpec(name='public_bounds', building_count=2,
            min_floors=1, max_floors=1, rooms_per_floor=2, seed=23))
        # Exercise full public-landscape placement, not only occupied parcels.
        city.metadata['landscape_sites'] = [{'id': 'test_park', 'style': 'park',
            'bounds': {'min_x': 210, 'min_y': 210, 'max_x': 270, 'max_y': 270}}]
        actual = GeometryCompiler(include_interiors=False).compile(city)
        def brute(self, p):
            return min(point_segment_distance(p, points)-half for points, _, _, half in self.entries)
        with patch.object(RoadClearanceQuery, '__call__', brute):
            expected = GeometryCompiler(include_interiors=False).compile(city)
        self.assertEqual(to_primitive(actual), to_primitive(expected))

    def test_parcel_geometry_matches_brute_force(self):
        from cityg.geometry import GeometryCompiler
        from cityg.planning import BaselineCityPlanner
        from cityg.schemas import CitySpec
        city = BaselineCityPlanner().plan(CitySpec(name='bounds', building_count=2,
            min_floors=1, max_floors=1, rooms_per_floor=2, seed=23))
        actual = GeometryCompiler(include_interiors=False).compile(city)
        def brute(self, city, point, clearance):
            return all(point_segment_distance(point, road.centerline) >= road.width_m/2+clearance
                       for road in city.road_network.segments)
        with patch.object(ParcelLandscapeCompilerMixin, '_point_clear_of_roads', brute):
            expected = GeometryCompiler(include_interiors=False).compile(city)
        self.assertEqual(to_primitive(actual), to_primitive(expected))

    def test_streetscape_matches_exact_including_replaced_centerline(self):
        rng = random.Random(23)
        roads = [RoadSegment(str(i), 'a', 'b', tuple(
            Point2D(rng.uniform(-100, 100), rng.uniform(-100, 100)) for _ in range(4)),
            width_m=4+i) for i in range(8)]
        city = City('test', 'test', Bounds2D(-200, -200, 200, 200), RoadNetwork([], roads))
        compiler = StreetscapeCompiler()
        parcels = ParcelLandscapeCompilerMixin()
        for _ in range(200):
            p = Point2D(rng.uniform(-200, 200), rng.uniform(-200, 200))
            margin = rng.choice([-.1, 0, .08, 2])
            expected = any(point_segment_distance(p, r.centerline) <= r.width_m/2+margin
                           for r in roads if r.id != '0')
            self.assertEqual(compiler._inside_other_road(city, '0', p, margin), expected)
            clear = all(point_segment_distance(p, r.centerline) >= r.width_m/2+margin for r in roads)
            self.assertEqual(parcels._point_clear_of_roads(city, p, margin), clear)
        from dataclasses import replace
        city.road_network.segments[1] = replace(roads[1], centerline=(Point2D(500, 0), Point2D(600, 0)))
        self.assertTrue(compiler._inside_other_road(city, '0', Point2D(550, 0)))
        self.assertFalse(parcels._point_clear_of_roads(city, Point2D(550, 0), 0))

    def test_parcel_clearance_keeps_equal_boundary(self):
        road = RoadSegment('r', 'a', 'b', (Point2D(0, 0), Point2D(100, 0)), width_m=10)
        city = City('test', 'test', Bounds2D(-10, -10, 110, 10), RoadNetwork([], [road]))
        parcels = ParcelLandscapeCompilerMixin()
        self.assertTrue(parcels._point_clear_of_roads(city, Point2D(50, 5), 0))
        self.assertFalse(parcels._point_clear_of_roads(city, Point2D(50, 5-1e-7), 0))

    def test_curved_extent_and_inclusive_threshold(self):
        path = PlanarPath2D([Point2D(-10, 0), Point2D(0, 80), Point2D(10, 0)])
        self.assertEqual(path.bounds, (-10, 0, 10, 80))
        self.assertTrue(path.bounds_overlap((0, 82, 0, 82), 2))
        self.assertTrue(path.bounds_overlap((-12, 0, -12, 0), 2))
        self.assertFalse(path.bounds_overlap((0, 83, 0, 83), 2))

    def test_random_distance_contacts_never_pruned(self):
        rng = random.Random(812)
        for _ in range(40):
            path = PlanarPath2D([Point2D(rng.uniform(-100, 100), rng.uniform(-100, 100))
                                 for _ in range(6)])
            for _ in range(40):
                p = Point2D(rng.uniform(-150, 150), rng.uniform(-150, 150))
                radius = path.project(p).separation
                self.assertTrue(path.bounds_overlap((p.x, p.y, p.x, p.y), radius))

    def test_intersections_equal_unfiltered(self):
        rng = random.Random(923)
        for _ in range(50):
            a, b = [PlanarPath2D([Point2D(rng.uniform(-100, 100), rng.uniform(-100, 100))
                                  for _ in range(4)]) for _ in range(2)]
            for endpoints in (False, True):
                actual = a.intersections(b, include_endpoints=endpoints)
                with patch.object(PlanarPath2D, 'bounds_overlap', return_value=True):
                    expected = a.intersections(b, include_endpoints=endpoints)
                self.assertEqual(actual, expected)

    def test_meshes_identical_and_projection_count_reduced(self):
        junctions, roads = [], []
        def road(name, start, end, points, width):
            roads.append(RoadSegment(name, start, end, tuple(points), width_m=width))
            junctions.extend([Junction(start, points[0]), Junction(end, points[-1])])
        # Split four-way junction with unequal road widths and sampled strips.
        for name, end, width in [('east', Point2D(80, 0), 8),
                                 ('west', Point2D(-80, 0), 12),
                                 ('north', Point2D(0, 80), 10),
                                 ('south', Point2D(0, -80), 6)]:
            road(name, 'center', name, [Point2D(end.x*i/20, end.y*i/20)
                                       for i in range(21)], width)
        # Curved path well outside its endpoint chord, plus distant roads.
        road('curve', 'c0', 'c1', sample_cubic_bezier(
            Point2D(150, -80), Point2D(250, -40), Point2D(250, 40), Point2D(150, 80)), 8)
        for i in range(8):
            road(f'far{i}', f'f{i}a', f'f{i}b',
                 [Point2D(400+i*40, y) for y in range(-80, 81, 4)], 6+i)
        city = City('test', 'test', Bounds2D(-100, -100, 800, 100),
                    RoadNetwork(list({j.id: j for j in junctions}.values()), roads))
        project = PlanarPath2D.project
        def compile_count():
            scene = GeometryScene(city.id, city.coordinate_system)
            with patch.object(PlanarPath2D, 'project', autospec=True, side_effect=project) as spy:
                compile_path_roads(city, scene)
                return to_primitive(scene), spy.call_count
        actual, fast_calls = compile_count()
        with patch.object(PlanarPath2D, 'bounds_overlap', return_value=True):
            expected, brute_calls = compile_count()
        self.assertEqual(actual, expected)
        self.assertGreater(brute_calls, 0)
        self.assertLess(fast_calls, brute_calls / 5)


if __name__ == '__main__':
    unittest.main()
