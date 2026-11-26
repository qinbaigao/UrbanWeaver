import json
import random
import unittest
from collections import Counter
from pathlib import Path

from cityg.morphology import path_metrics
from cityg.planning import BaselineCityPlanner
from cityg.planning.adaptive_streets import adaptive_streets
from cityg.planning.road_paths import road_path_issues
from cityg.schemas import CitySpec


class AdaptiveStreetsTests(unittest.TestCase):
    def network(self, spec):
        planner = BaselineCityPlanner()
        cols, rows = planner._grid_shape(spec)
        xs = planner._road_axes(spec, spec.width_m, cols, random.Random(spec.seed), .3)
        ys = planner._road_axes(spec, spec.depth_m, rows, random.Random(spec.seed+1), .3)
        seed = planner._make_road_network(spec, xs, ys)
        return adaptive_streets(spec, seed)

    def assert_topology(self, network):
        nodes = {j.id: j.position for j in network.junctions}
        graph = {j: set() for j in nodes}
        self.assertEqual(len(nodes), len(network.junctions))
        self.assertEqual(len({r.id for r in network.segments}), len(network.segments))
        for road in network.segments:
            self.assertEqual(road.centerline[0], nodes[road.start_junction_id])
            self.assertEqual(road.centerline[-1], nodes[road.end_junction_id])
            graph[road.start_junction_id].add(road.end_junction_id)
            graph[road.end_junction_id].add(road.start_junction_id)
        reached, pending = set(), [next(iter(nodes))]
        while pending:
            node = pending.pop()
            if node not in reached:
                reached.add(node)
                pending.extend(graph[node]-reached)
        self.assertEqual(reached, set(nodes))
        self.assertIn(3, Counter(map(len, graph.values())))
        self.assertFalse(list(road_path_issues(network.segments)))

    def test_local_curves_straight_majority_and_connected_topology(self):
        for seed in (2, 7, 29):
            with self.subTest(seed=seed):
                spec = CitySpec(width_m=750, depth_m=650, building_count=12,
                                buildings_per_block=1, road_pattern='landscape_adaptive',
                                river_mode='meandering', seed=seed)
                network, rivers = self.network(spec)
                self.assert_topology(network)
                roads = [path_metrics(r.centerline) for r in network.segments]
                straight = sum(r['length_m'] for r in roads if r['max_deviation_m'] < .05)
                self.assertGreater(straight / sum(r['length_m'] for r in roads), .75)
                self.assertGreater(path_metrics(rivers[0].centerline)['max_deviation_m'], 70)
                self.assertEqual((network, rivers), self.network(spec))

    def test_without_river_no_global_curvature(self):
        spec = CitySpec(width_m=600, depth_m=600, building_count=12,
                        buildings_per_block=1, road_pattern='landscape_adaptive')
        network, rivers = self.network(spec)
        self.assertFalse(rivers)
        self.assertTrue(all(len(r.centerline) == 2 for r in network.segments))
        self.assert_topology(network)

    def test_200_building_skeleton_stays_straight_dominated(self):
        source = json.loads((Path(__file__).parents[1]/'examples/city200_morphology_showcase.json').read_text())
        network, rivers = self.network(CitySpec.from_dict(source))
        self.assert_topology(network)
        metrics = [path_metrics(r.centerline) for r in network.segments]
        self.assertGreater(sum(r['length_m'] for r in metrics if r['max_deviation_m'] < .05)
                           / sum(r['length_m'] for r in metrics), .9)
        self.assertGreater(path_metrics(rivers[0].centerline)['max_deviation_m'], 150)

    def test_insufficient_dry_land_rejected(self):
        spec = CitySpec(width_m=300, depth_m=500, building_count=4,
                        road_pattern='landscape_adaptive', river_mode='meandering')
        with self.assertRaisesRegex(ValueError, 'Insufficient dry land'):
            self.network(spec)


if __name__ == '__main__':
    unittest.main()
