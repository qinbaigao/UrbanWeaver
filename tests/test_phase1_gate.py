import unittest

from cityg.evaluation import random_city_specs
from cityg.planning import BaselineCityPlanner
from cityg.validation import CityValidator


class RandomizedPhase1GateTests(unittest.TestCase):
    def test_one_hundred_random_specs_are_valid(self):
        planner = BaselineCityPlanner()
        validator = CityValidator()
        for spec in random_city_specs():
            with self.subTest(spec=spec.name):
                city = planner.plan(spec)
                report = validator.validate(city)
                self.assertTrue(report.ok, report.to_dict())
                entity_ids = [entity.id for entity, _, _ in city.iter_entities()]
                self.assertEqual(len(entity_ids), len(set(entity_ids)))
                self.assertEqual(
                    set(entity_ids),
                    {node.entity_id for node in city.world_program.nodes},
                )


if __name__ == "__main__":
    unittest.main()
