import unittest

from cityg.ccwp import DependencyGraph
from cityg.migration import LEGACY_SCHEMA_VERSION
from cityg.planning import BaselineCityPlanner
from cityg.schemas import CCWP_SCHEMA_VERSION, CitySpec
from cityg.serialization import city_from_dict, to_primitive
from cityg.validation import CityValidator


class CCWPTests(unittest.TestCase):
    def setUp(self):
        self.city = BaselineCityPlanner().plan(
            CitySpec(
                name="ccwp_test",
                width_m=180,
                depth_m=160,
                building_count=2,
                min_floors=2,
                max_floors=2,
                rooms_per_floor=2,
                seed=4,
            )
        )

    def test_program_covers_every_canonical_entity(self):
        expected = {entity.id for entity, _, _ in self.city.iter_entities()}
        actual = {node.entity_id for node in self.city.world_program.nodes}
        self.assertEqual(self.city.schema_version, CCWP_SCHEMA_VERSION)
        self.assertEqual(actual, expected)
        self.assertTrue(self.city.world_program.contracts)
        self.assertTrue(self.city.world_program.relations)
        self.assertTrue(self.city.world_program.artifacts)
        self.assertTrue(self.city.world_program.provenance)
        self.assertTrue(CityValidator().validate(self.city).ok)

    def test_dependency_graph_resolves_hierarchy_scope(self):
        graph = DependencyGraph(self.city)
        building = next(self.city.iter_buildings())
        room = building.floors[0].rooms[0]
        self.assertTrue(graph.is_within_scope(room.id, building.id))
        self.assertEqual(graph.hierarchy_path(building.id, room.id)[0], building.id)
        self.assertEqual(graph.hierarchy_path(building.id, room.id)[-1], room.id)
        self.assertEqual(graph.lowest_common_ancestor([building.id, room.id]), building.id)

    def test_legacy_manifest_migrates_to_current_ccwp(self):
        legacy = to_primitive(self.city)
        legacy["schema_version"] = LEGACY_SCHEMA_VERSION
        legacy.pop("world_program")
        loaded = city_from_dict(legacy)
        self.assertEqual(loaded.schema_version, CCWP_SCHEMA_VERSION)
        self.assertEqual(
            loaded.metadata["migrated_from_schema_version"], LEGACY_SCHEMA_VERSION
        )
        self.assertTrue(loaded.world_program.nodes)
        self.assertTrue(CityValidator().validate(loaded).ok)

    def test_future_manifest_version_is_rejected(self):
        data = to_primitive(self.city)
        data["schema_version"] = "99.0.0"
        with self.assertRaisesRegex(ValueError, "Unsupported CityG schema"):
            city_from_dict(data)


if __name__ == "__main__":
    unittest.main()
