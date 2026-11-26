import json
import unittest
from pathlib import Path

from cityg.planning import BaselineCityPlanner
from cityg.schemas import CitySpec
from cityg.serialization import to_primitive
from cityg.validation import CityValidator


class ResearchSpecTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec_dir = Path(__file__).resolve().parents[1] / "examples" / "research_specs"
        cls.spec_paths = sorted(cls.spec_dir.glob("*.json"))

    def test_phase0_contains_ten_specs(self):
        self.assertEqual(len(self.spec_paths), 10)

    def test_every_spec_is_reproducible_and_valid(self):
        planner = BaselineCityPlanner()
        validator = CityValidator()
        for path in self.spec_paths:
            with self.subTest(spec=path.name):
                data = json.loads(path.read_text(encoding="utf-8"))
                spec = CitySpec.from_dict(data)
                first = planner.plan(spec)
                second = planner.plan(spec)
                self.assertEqual(len(list(first.iter_buildings())), spec.building_count)
                self.assertTrue(validator.validate(first).ok)
                self.assertEqual(to_primitive(first), to_primitive(second))


if __name__ == "__main__":
    unittest.main()

