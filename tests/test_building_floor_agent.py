import json
import unittest

from cityg.agents.building_floor import BuildingFloorAgent
from cityg.planning import (
    BaselineCityPlanner,
    FloorArchetype,
    FloorProfile,
)
from cityg.schemas import CitySpec, ZoneSpec


def final(program):
    return {
        "action": "final",
        "detail_keys": [],
        "program_json": json.dumps(program),
    }


class FakeService:
    def __init__(self, responses):
        self.responses = list(responses)

    def complete(self, messages, response_schema=None):
        response = self.responses.pop(0)
        return response if isinstance(response, str) else json.dumps(response)


class BuildingFloorAgentTests(unittest.TestCase):
    def setUp(self):
        self.spec = CitySpec(
            name="building_floor_test",
            width_m=220,
            depth_m=180,
            building_count=2,
            min_floors=2,
            max_floors=3,
            rooms_per_floor=4,
            seed=8,
            zones=(ZoneSpec("homes", "residential", 1.0),),
        )
        self.city = BaselineCityPlanner().plan(self.spec)
        self.base = FloorProfile(
            "residential",
            "double_loaded_corridor",
            0.18,
            ("living_room", "bedroom", "kitchen", "bathroom"),
            (
                FloorArchetype(
                    "ground", 5, 3, 8, 35, 3.0,
                    ("living_room", "kitchen", "bathroom"), 3,
                ),
                FloorArchetype(
                    "typical", 12, 8, 20, 24, 2.8,
                    ("living_room", "bedroom", "kitchen", "bathroom"), 4,
                ),
            ),
        )

    @staticmethod
    def _vertical_zones(floor_count):
        common = {
            "preferred_room_count": 6,
            "min_room_count": 4,
            "max_room_count": 10,
            "target_room_area_m2": 32,
            "min_room_width_m": 2.8,
            "room_function_cycle": ["living_room", "bedroom", "kitchen", "bathroom"],
            "unit_group_size": 4,
        }
        zones = [{
            **common,
            "zone_id": "ground_lobby",
            "start_level": 0,
            "end_level": 0,
            "role": "ground",
            "use_type": "entrance",
        }]
        if floor_count > 1:
            zones.append({
                **common,
                "zone_id": "top_residential",
                "start_level": 1,
                "end_level": floor_count - 1,
                "role": "top",
                "use_type": "residential",
            })
        return zones

    def test_building_specific_program_is_valid_and_cached(self):
        floor_count = len(next(self.city.iter_buildings()).floors)
        response = final(
            {
                "BuildingFloorProgram": {
                    "building_function": "residential",
                    "layout": "double_loaded_corridor",
                    "corridor_ratio": 0.2,
                    "room_function_cycle": ["living_room", "bedroom", "kitchen"],
                    "space_archetypes": [
                        {
                            "role": "ground",
                            "preferred_room_count": 6,
                            "min_room_count": 4,
                            "max_room_count": 10,
                            "target_room_area_m2": 38,
                            "min_room_width_m": 3.2,
                            "room_function_cycle": ["living_room", "kitchen", "bathroom"],
                            "unit_group_size": 3,
                        },
                        {
                            "role": "typical",
                            "preferred_room_count": 16,
                            "min_room_count": 10,
                            "max_room_count": 24,
                            "target_room_area_m2": 22,
                            "min_room_width_m": 2.8,
                            "room_function_cycle": ["living_room", "bedroom", "kitchen", "bathroom"],
                            "unit_group_size": 4,
                        },
                    ],
                    "vertical_zones": self._vertical_zones(floor_count),
                }
            }
        )
        result = BuildingFloorAgent(FakeService([response]), model_id="fake").plan(
            next(self.city.iter_buildings()), self.base, self.spec
        )
        self.assertEqual(result.program.profile.corridor_ratio, 0.2)
        self.assertEqual(result.program.profile.for_role("typical").max_room_count, 24)

        buildings = list(self.city.iter_buildings())
        buildings[1].footprint = buildings[0].footprint
        buildings[1].floors = buildings[0].floors
        buildings[1].metadata["entrance_side"] = buildings[0].metadata.get("entrance_side")
        buildings[1].metadata["prototype_id"] = buildings[0].metadata.get("prototype_id")
        buildings[1].metadata['massing_style'] = buildings[0].metadata.get('massing_style')
        buildings[1].metadata['orientation_deg'] = buildings[0].metadata.get('orientation_deg',0)
        agent = BuildingFloorAgent(FakeService([response]), model_id="fake")
        batch = agent.plan_city(
            self.city,
            {"residential": self.base},
            self.spec,
            max_unique_calls=1,
        )
        self.assertEqual(len(batch.overrides), 2)
        self.assertEqual(sum(batch.cache_hits.values()), 1)
        self.assertEqual(len(batch.attempts), 1)

    def test_role_keyed_semantic_room_lists_are_normalized(self):
        floor_count = len(next(self.city.iter_buildings()).floors)
        response = final({
            "building_function": "residential",
            "layout": "double_loaded_corridor",
            "corridor_ratio": 0.17,
            "room_function_cycle": ["living_unit", "bedroom", "kitchen"],
            "space_archetypes": {
                "ground": [
                    {"function": "lobby", "preferred_count": 1, "target_area_m2": 40},
                    {"function": "utility_room", "preferred_count": 1, "target_area_m2": 12},
                ],
                "typical": [
                    {"function": "living_unit", "preferred_count": 6, "target_area_m2": 60},
                    {"function": "bedroom", "preferred_count": 12, "target_area_m2": 15},
                    {"function": "bathroom", "preferred_count": 6, "target_area_m2": 8},
                ],
            },
            "vertical_zones": self._vertical_zones(floor_count),
        })
        result = BuildingFloorAgent(FakeService([response]), model_id="fake").plan(
            next(self.city.iter_buildings()), self.base, self.spec
        )
        profile = result.program.profile
        self.assertIn("living_room", profile.room_function_cycle)
        self.assertNotIn("living_unit", profile.room_function_cycle)
        self.assertEqual(profile.for_role("ground").role, "ground")
        self.assertEqual(profile.for_role("typical").preferred_room_count, 24)
        self.assertEqual(profile.vertical_zones[-1].end_level, floor_count - 1)

    def test_zero_room_service_band_does_not_replace_typical_archetype(self):
        building = next(self.city.iter_buildings())
        floor_count = len(building.floors)
        response = final({
            "building_function": "residential",
            "layout": "residential_units",
            "corridor_ratio": 0.18,
            "room_function_cycle": "residential_units",
            "space_archetypes": [
                {
                    "role": "residential_unit",
                    "preferred_room_count": 8,
                    "min_room_count": 6,
                    "max_room_count": 10,
                    "target_room_area_m2": 30,
                    "min_room_width_m": 3.0,
                    "room_function_cycle": [
                        "living_room", "bedroom", "kitchen", "bathroom"
                    ],
                    "unit_group_size": 4,
                },
                {
                    "role": "corridor_service",
                    "preferred_room_count": 0,
                    "min_room_count": 0,
                    "max_room_count": 0,
                    "target_room_area_m2": 0,
                    "min_room_width_m": 0,
                    "room_function_cycle": "service",
                    "unit_group_size": 0,
                },
            ],
            "vertical_zones": self._vertical_zones(floor_count),
        })
        profile = BuildingFloorAgent(
            FakeService([response]), model_id="fake"
        ).plan(building, self.base, self.spec).program.profile
        self.assertEqual(profile.for_role("typical").preferred_room_count, 8)
        self.assertEqual(profile.for_role("typical").unit_group_size, 4)

    def test_batch_falls_back_when_one_building_plan_fails(self):
        agent = BuildingFloorAgent(
            FakeService([{"action": "final", "detail_keys": [], "program_json": "{}"}]),
            model_id="fake",
            max_calls=1,
        )
        building = next(self.city.iter_buildings())
        one_building_city = BaselineCityPlanner().plan(
            CitySpec(
                name="building_floor_fallback",
                width_m=160,
                depth_m=140,
                building_count=1,
                min_floors=2,
                max_floors=2,
                rooms_per_floor=4,
                seed=9,
                zones=(ZoneSpec("homes", "residential", 1.0),),
            )
        )
        result = agent.plan_city(
            one_building_city,
            {"residential": self.base},
            self.spec,
            max_unique_calls=1,
        )
        failed_id = next(one_building_city.iter_buildings()).id
        self.assertEqual(result.overrides, {})
        self.assertIn(failed_id, result.failed_buildings)
        self.assertIn(failed_id, result.skipped_buildings)
        self.assertEqual(len(result.attempts), 1)


if __name__ == "__main__":
    unittest.main()
