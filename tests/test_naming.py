import unittest
import tempfile
from copy import deepcopy
from pathlib import Path

from cityg.ccwp import build_world_program
from cityg.naming import (
    IDENTITY_SCHEMA_VERSION,
    alias_index,
    identity_registry,
    resolve_alias,
)
from cityg.planning import BaselineCityPlanner
from cityg.schemas import CitySpec
from cityg.serialization import load_city, save_json


class NamingIdentityTests(unittest.TestCase):
    def _city(self):
        city = BaselineCityPlanner().plan(
            CitySpec(
                name="naming_test",
                width_m=160,
                depth_m=140,
                building_count=2,
                min_floors=1,
                max_floors=2,
                rooms_per_floor=2,
                seed=9,
            )
        )
        city.world_program = build_world_program(city, producer="test", seed=9)
        return city

    def test_registry_covers_all_entities_and_ccwp_tags(self):
        city = self._city()
        records = identity_registry(city)
        ids = {entity.id for entity, _, _ in city.iter_entities()}
        self.assertEqual(set(records), ids)
        self.assertEqual(city.metadata["identity_registry"]["schema_version"], IDENTITY_SCHEMA_VERSION)
        building = next(city.iter_buildings())
        record = records[building.id]
        self.assertEqual(record["entity_type"], "building")
        self.assertIn(f"uid:{record['uid']}", next(n for n in city.world_program.nodes if n.entity_id == building.id).intent.tags)
        self.assertEqual(resolve_alias(city, record["uid"]), building.id)
        self.assertEqual(resolve_alias(city, record["path"]), building.id)

    def test_display_name_is_independent_from_uid(self):
        city = self._city()
        building = next(city.iter_buildings())
        before = identity_registry(city)[building.id]
        building.name = "Landmark Tower"
        city.world_program = build_world_program(city, producer="test", seed=9)
        after = identity_registry(city)[building.id]
        self.assertEqual(before["uid"], after["uid"])
        self.assertEqual(after["display_name"], "Landmark Tower")

    def test_duplicate_display_names_are_not_resolved(self):
        city = self._city()
        buildings = list(city.iter_buildings())
        buildings[0].name = buildings[1].name = "Twin"
        city.world_program = build_world_program(city, producer="test", seed=9)
        aliases = alias_index(city)
        self.assertEqual(len(aliases["Twin"]), 2)
        self.assertIsNone(resolve_alias(city, "Twin"))

    def test_legacy_manifest_is_enriched_on_load(self):
        city = self._city()
        legacy = deepcopy(city)
        legacy.metadata.pop("identity_registry", None)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "city.json"
            save_json(legacy, path)
            loaded = load_city(path)
            self.assertEqual(len(identity_registry(loaded)), len(list(loaded.iter_entities())))
            self.assertIn("identity_registry", loaded.metadata)


if __name__ == "__main__":
    unittest.main()
