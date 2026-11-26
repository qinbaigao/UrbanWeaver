from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cityg.geometry import GeometryCompiler
from cityg.planning.baseline import BaselineCityPlanner
from cityg.planning.generation_prototypes import DeferredFurniture
from cityg.schemas import CitySpec
from scripts.profile_method_scaling import equivalent, run


class MethodScalingTests(unittest.TestCase):
    def test_comparison_ignores_order_but_detects_missing_geometry(self):
        city = BaselineCityPlanner(floor_detail_agent=DeferredFurniture()).plan(
            CitySpec(building_count=2, min_floors=2, max_floors=2,
                     width_m=180, depth_m=140))
        scene = GeometryCompiler().compile(city)
        candidate = deepcopy(scene)
        candidate.primitives.reverse()
        self.assertTrue(all(equivalent(scene, candidate).values()))
        candidate.primitives.pop()
        self.assertFalse(equivalent(scene, candidate)['primitives'])

    def test_failed_fixture_is_retained_not_counted_as_measurement(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'profile'
            with patch('scripts.profile_method_scaling.BaselineCityPlanner') as planner:
                planner.return_value.plan.side_effect = ValueError('no fitting archetype')
                rows = run(output, [100], 1)
            self.assertEqual(rows[0]['status'], 'fixture_failed')
            self.assertIsNone(rows[0]['speedup_if_equivalent'])
            self.assertEqual(json.loads((output / 'summary.json').read_text())['rows'], rows)
