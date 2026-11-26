import json
import tempfile
import unittest
from pathlib import Path

from cityg.cli import main
from cityg.pipeline import GenerationPipeline
from cityg.schemas import CitySpec
from cityg.serialization import load_city


class PipelineTests(unittest.TestCase):
    def test_pipeline_writes_independent_manifest(self):
        spec = CitySpec(
            name="pipeline_test",
            width_m=220.0,
            depth_m=180.0,
            building_count=4,
            min_floors=1,
            max_floors=2,
            rooms_per_floor=2,
            seed=2,
        )
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            result = GenerationPipeline().run(spec, output)
            self.assertTrue(result.ok, result.validation.to_dict())
            self.assertTrue((output / "city.json").is_file())
            self.assertTrue((output / "validation_report.json").is_file())
            self.assertTrue((output / "summary.json").is_file())
            self.assertEqual(len(list(load_city(output / "city.json").iter_buildings())), 4)

    def test_cli_generate_and_validate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            spec_path = root / "spec.json"
            output = root / "generated"
            spec_path.write_text(
                json.dumps(
                    {
                        "name": "cli_test",
                        "width_m": 180,
                        "depth_m": 160,
                        "building_count": 2,
                        "min_floors": 1,
                        "max_floors": 1,
                        "rooms_per_floor": 2,
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                main(["generate", "--spec", str(spec_path), "--output", str(output)]), 0
            )
            self.assertEqual(main(["validate", str(output / "city.json")]), 0)


if __name__ == "__main__":
    unittest.main()

