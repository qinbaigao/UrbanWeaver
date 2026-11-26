import unittest
from pathlib import Path

from cityg.planning.urban_prototypes import UrbanPrototypeLibrary
from scripts.test_prototype_e2e import CASES, validate_selection


class PrototypeE2ERunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.library = UrbanPrototypeLibrary(Path(__file__).resolve().parents[1]/'configs/layout_prototypes/v1')

    def choice(self, key='urban_waterfront_v1'):
        return {'prototype_id': key, 'overrides': {'building_count': 20, 'seed': 1703}, 'reason': '滨水契合需求'}

    def test_supported_selection(self):
        self.assertEqual(validate_selection(self.choice(), self.library, CASES['03_waterfront']), self.choice())

    def test_explicit_river_cannot_be_silently_lost(self):
        with self.assertRaisesRegex(ValueError, 'river'):
            validate_selection(self.choice('urban_residential_v1'), self.library, CASES['03_waterfront'])

    def test_unknown_recipe_and_unbounded_adjustments(self):
        for data in (self.choice('invented'),
                     {**self.choice(), 'overrides': {'building_count': 200, 'seed': 1703}},
                     {**self.choice(), 'overrides': {'building_count': 20, 'seed': 1703, 'width_m': 999}},
                     {**self.choice(), 'extra': True}):
            with self.assertRaises(ValueError):
                validate_selection(data, self.library, CASES['03_waterfront'])


if __name__ == '__main__':
    unittest.main()
