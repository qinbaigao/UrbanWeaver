import json
import unittest
import tempfile
from pathlib import Path

from cityg.agent_pipeline import HierarchicalAgenticGenerationPipeline
from cityg.agents import AgentGenerationError, HierarchicalPlanningAgent, RequirementAgent
from cityg.agents.context import ContextSection, ProgressiveContext
from cityg.agents.hierarchy import BuildingAgent, FloorAgent, SkylineAgent, UrbanAgent, _ProgressiveProgramAgent
from cityg.planning import HierarchicalProgram, ProgrammedCityPlanner
from cityg.schemas import CitySpec, ZoneSpec
from cityg.validation import CityValidator


class FakeService:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def complete(self, messages, response_schema=None):
        self.calls.append((messages, response_schema))
        response = self.responses.pop(0)
        return response if isinstance(response, str) else json.dumps(response)


def request(*keys):
    return {"action": "request_details", "detail_keys": list(keys), "program_json": "{}"}


def final(program):
    return {
        "action": "final",
        "detail_keys": [],
        "program_json": json.dumps(program),
    }


class ProgressiveContextTests(unittest.TestCase):
    def test_role_keyed_archetypes_inside_array_preserve_floor_roles_and_counts(self):
        from cityg.planning.programs import FloorSpaceProfile
        roles = {'ground': {'role':'ground','preferred_room_count':4},
                 'typical': {'role':'typical','preferred_room_count':7}}
        parse = lambda value: FloorSpaceProfile.from_dict({'function':'residential','archetypes':value})
        profile = parse([roles])
        self.assertEqual(profile, parse(roles))
        profile.validate()
        self.assertEqual([a.preferred_room_count for a in profile.archetypes], [4,7])
        with self.assertRaises(ValueError):
            parse([{'ground':{'role':'typical'}}])

    def test_unknown_and_repeated_sections_are_rejected(self):
        context = ProgressiveContext(
            {"small": True}, (ContextSection("detail", "one detail", {"x": 1}),)
        )
        with self.assertRaisesRegex(ValueError, "unknown detail"):
            context.disclose(["missing"])
        self.assertEqual(context.disclose(["detail"])["details"], {"detail": {"x": 1}})
        with self.assertRaisesRegex(ValueError, "already disclosed"):
            context.disclose(["detail"])

    def test_character_budget_is_enforced(self):
        context = ProgressiveContext(
            {}, (ContextSection("large", "large", "x" * 100),), max_disclosed_chars=10
        )
        with self.assertRaisesRegex(ValueError, "character budget"):
            context.disclose(["large"])


class HierarchyAgentTests(unittest.TestCase):
    def test_identical_failures_stop_early_even_with_large_call_budget(self):
        service = FakeService([final({})] * 10)
        def reject(program):
            raise ValueError("missing required functions")
        with self.assertRaisesRegex(AgentGenerationError, "repeated 3 times") as caught:
            _ProgressiveProgramAgent(service, max_calls=10)._run(
                ProgressiveContext({}, ()), "test", reject)
        self.assertEqual(len(service.calls), 3)
        self.assertEqual(len(caught.exception.attempts), 3)
        self.assertTrue(all(a.error for a in caught.exception.attempts))

    def test_two_failures_can_recover_and_changed_errors_still_have_call_limit(self):
        def validate(program):
            if "error" in program:
                raise ValueError(program["error"])
            return program
        service = FakeService([final({"error": "bad"})] * 2 + [final({"ok": True})])
        result = _ProgressiveProgramAgent(service, max_calls=6)._run(
            ProgressiveContext({}, ()), "test", validate)
        self.assertEqual(result.program, {"ok": True})
        self.assertEqual(len(result.attempts), 3)
        service = FakeService([final({"error": str(i)}) for i in range(4)])
        with self.assertRaisesRegex(AgentGenerationError, "after 4 model calls"):
            _ProgressiveProgramAgent(service, max_calls=4)._run(
                ProgressiveContext({}, ()), "test", validate)
        self.assertEqual(len(service.calls), 4)

    def test_valid_disclosure_breaks_consecutive_failure_streak(self):
        service = FakeService([final({})] * 2 + [request("detail")] +
                              [final({})] * 2 + [final({"ok": True})])
        def validate(program):
            if not program:
                raise ValueError("missing required functions")
            return program
        result = _ProgressiveProgramAgent(service, max_calls=6)._run(
            ProgressiveContext({}, (ContextSection("detail", "detail", {}),)),
            "test", validate)
        self.assertEqual(len(result.attempts), 6)

    def test_urban_enum_array_gets_typed_repair_feedback(self):
        from cityg.planning.programs import UrbanProgram
        program={'district_order':['zone_00','zone_01'],'road_pattern':'connected_grid',
                 'block_traversal':['row_major'],'collector_policy':'perimeter'}
        with self.assertRaisesRegex(ValueError,'one scalar string'):
            UrbanProgram.from_dict(program)
        service=FakeService([final(program),final({**program,'block_traversal':'row_major'})])
        result=UrbanAgent(service,max_calls=2).plan(self.spec)
        self.assertEqual(result.program.block_traversal,'row_major')
        self.assertIn('one scalar string',result.attempts[0].error)
        self.assertIn('not a list of options',service.calls[1][0][-1].content)

    def setUp(self):
        self.spec = CitySpec(
            name="hierarchy_test",
            width_m=320,
            depth_m=260,
            building_count=8,
            min_floors=2,
            max_floors=4,
            rooms_per_floor=4,
            seed=9,
            zones=(
                ZoneSpec("homes", "residential", 0.6),
                ZoneSpec("shops", "commercial", 0.4),
            ),
        )

    def _urban(self):
        service = FakeService(
            [
                request("zones"),
                final(
                    {
                        "district_order": ["zone_00", "zone_01"],
                        "road_pattern": "connected_grid",
                        "block_traversal": "column_major",
                        "collector_policy": "perimeter",
                    }
                ),
            ]
        )
        result = UrbanAgent(service, model_id="fake").plan(self.spec)
        self.assertEqual(len(result.disclosures), 1)
        self.assertEqual(result.disclosures[0].keys, ("zones",))
        self.assertEqual(len(result.attempts), 2)
        return result.program

    def _skyline(self, urban):
        service = FakeService(
            [
                request("planning_guidance"),
                final(
                    {
                        "profiles": [
                            {
                                "function": "residential",
                                "min_floors": 2,
                                "max_floors": 3,
                                "centrality_bias": "distributed",
                                "height_role": "lowrise",
                            },
                            {
                                "function": "commercial",
                                "min_floors": 3,
                                "max_floors": 4,
                                "centrality_bias": "core",
                                "height_role": "mixed",
                            },
                        ],
                        "highrise_ratio": 0.0,
                        "landmark_count": 0,
                        "landmark_functions": [],
                        "skyline_strength": 0.8,
                    }
                ),
            ]
        )
        result = SkylineAgent(service, model_id="fake").plan(self.spec, urban)
        self.assertEqual(result.disclosures[0].keys, ("planning_guidance",))
        return result.program

    def _building(self, urban, skyline=None):
        service = FakeService(
            [
                request("prototype_catalog"),
                final(
                    {
                        "profiles": [
                            {
                                "function": "residential",
                                "floor_policy": "alternating",
                                "entrance_side": "west",
                                "prototype_id": "residential_slab",
                                "roof_profile_palette": ["garden", "solar"],
                            },
                            {
                                "function": "commercial",
                                "floor_policy": "maximum",
                                "entrance_side": "east",
                                "prototype_id": "commercial_tower",
                            },
                        ]
                    }
                ),
            ]
        )
        return BuildingAgent(service).plan(self.spec, urban, skyline).program

    def test_building_agent_normalizes_known_archetype_used_as_prototype(self):
        urban = self._urban()
        service = FakeService(
            [
                final(
                    {
                        "profiles": [
                            {
                                "function": "residential",
                                "floor_policy": "midpoint",
                                "entrance_side": "west",
                                "prototype_id": "residential_bar_compact_compact_00",
                                "archetype_palette": [],
                            },
                            {
                                "function": "commercial",
                                "floor_policy": "midpoint",
                                "entrance_side": "east",
                                "prototype_id": "commercial_bar_deep_window_compact_01",
                                "archetype_palette": [],
                            },
                        ]
                    }
                )
            ]
        )
        program = BuildingAgent(service).plan(self.spec, urban).program
        profiles = {item.function: item for item in program.profiles}
        self.assertEqual(profiles["residential"].prototype_id, "residential_slab")
        self.assertEqual(profiles["commercial"].prototype_id, "commercial_tower")
        self.assertIn(
            "residential_bar_compact_compact_00",
            profiles["residential"].archetype_palette,
        )

    def _floor(self, building):
        space = {
            "profiles": [
                {
                    "function": "residential",
                    "archetypes": [
                        {
                            "role": "ground",
                            "preferred_room_count": 6,
                            "min_room_count": 4,
                            "max_room_count": 10,
                            "target_room_area_m2": 34,
                            "min_room_width_m": 3.0,
                            "room_function_cycle": ["living_room", "kitchen", "bedroom", "bathroom"],
                            "unit_group_size": 4,
                        },
                        {
                            "role": "typical",
                            "preferred_room_count": 12,
                            "min_room_count": 8,
                            "max_room_count": 18,
                            "target_room_area_m2": 24,
                            "min_room_width_m": 2.8,
                            "room_function_cycle": ["living_room", "kitchen", "bedroom", "bathroom"],
                            "unit_group_size": 4,
                        },
                    ],
                },
                {
                    "function": "commercial",
                    "archetypes": [
                        {
                            "role": "ground",
                            "preferred_room_count": 6,
                            "min_room_count": 3,
                            "max_room_count": 10,
                            "target_room_area_m2": 60,
                            "min_room_width_m": 3.6,
                            "room_function_cycle": ["shop", "reception", "service_room", "restroom"],
                            "unit_group_size": 1,
                        },
                        {
                            "role": "typical",
                            "preferred_room_count": 10,
                            "min_room_count": 6,
                            "max_room_count": 16,
                            "target_room_area_m2": 42,
                            "min_room_width_m": 3.2,
                            "room_function_cycle": ["open_office", "office", "meeting_room", "break_room"],
                            "unit_group_size": 1,
                        },
                    ],
                },
            ]
        }
        service = FakeService(
            [
                request("room_function_catalog"),
                final({"FloorSpaceProgram": space}),
                final(
                    {"FloorProgram": {
                        "profiles": [
                            {
                                "function": "residential",
                                "layout": "double_loaded_corridor",
                                "corridor_ratio": 0.18,
                                "room_function_cycle": [
                                    "living_room",
                                    "bedroom",
                                    "kitchen",
                                    "bathroom",
                                ],
                            },
                            {
                                "function": "commercial",
                                "layout": "double_loaded_corridor",
                                "corridor_ratio": 0.2,
                                "room_function_cycle": [
                                    "office",
                                    "meeting_room",
                                    "reception",
                                    "restroom",
                                ],
                            },
                        ]
                    }}
                ),
            ]
        )
        return FloorAgent(service).plan(self.spec, building).program

    def test_progressive_hierarchy_compiles_to_valid_city(self):
        urban = self._urban()
        skyline = self._skyline(urban)
        building = self._building(urban, skyline)
        floor = self._floor(building)
        city = ProgrammedCityPlanner(
            HierarchicalProgram(urban, building, floor, skyline)
        ).plan(self.spec)
        report = CityValidator().validate(city)
        self.assertTrue(report.ok, report.to_dict())
        self.assertEqual(city.metadata["planner"], "hierarchical_program_v2")
        buildings = list(city.iter_buildings())
        self.assertEqual(buildings[0].metadata["prototype_id"], "residential_slab")
        for item in buildings:
            if item.function == 'residential':
                self.assertIn(item.metadata['roof_program']['profile'], ('garden', 'solar'))
                self.assertEqual(item.metadata['roof_program']['source'], 'building_agent_profile_palette')
        commercial = next(item for item in buildings if item.function == "commercial")
        self.assertEqual(len(commercial.floors), self.spec.max_floors)
        self.assertEqual(commercial.entrance.x, commercial.footprint.max_x)
        realized_counts = [
            len(floor.rooms) - 1
            for item in buildings
            for floor in item.floors
        ]
        self.assertTrue(any(count != self.spec.rooms_per_floor for count in realized_counts))
        self.assertTrue(
            all(
                floor.metadata["space_program"]["source"]
                == "llm_floor_space_program_v1"
                for item in buildings
                for floor in item.floors
            )
        )
        residential = next(item for item in buildings if item.function == "residential")
        grouped_rooms = [
            room
            for room in residential.floors[-1].rooms
            if room.function != "corridor"
        ]
        self.assertTrue(grouped_rooms)
        self.assertTrue(
            all(room.metadata["space_group_type"] == "dwelling_unit" for room in grouped_rooms)
        )

    def test_invalid_program_receives_feedback_and_retries(self):
        service = FakeService(
            [
                final(
                    {
                        "district_order": ["invented"],
                        "road_pattern": "connected_grid",
                        "block_traversal": "row_major",
                        "collector_policy": "perimeter",
                    }
                ),
                request("zones"),
                final(
                    {
                        "district_order": ["zone_00", "zone_01"],
                        "road_pattern": "connected_grid",
                        "block_traversal": "row_major",
                        "collector_policy": "perimeter",
                    }
                ),
            ]
        )
        result = UrbanAgent(service, max_calls=3).plan(self.spec)
        self.assertIn("district_order", result.attempts[0].error)
        self.assertEqual(len(result.attempts), 3)

    def test_full_hierarchical_pipeline_writes_trace(self):
        spec_data = {
            "name": self.spec.name,
            "width_m": self.spec.width_m,
            "depth_m": self.spec.depth_m,
            "building_count": self.spec.building_count,
            "min_floors": self.spec.min_floors,
            "max_floors": self.spec.max_floors,
            "rooms_per_floor": self.spec.rooms_per_floor,
            "road_width_m": self.spec.road_width_m,
            "sidewalk_width_m": self.spec.sidewalk_width_m,
            "parcel_setback_m": self.spec.parcel_setback_m,
            "seed": self.spec.seed,
            "zones": [
                {"name": item.name, "function": item.function, "weight": item.weight}
                for item in self.spec.zones
            ],
        }
        urban = {
            "district_order": ["zone_00", "zone_01"],
            "road_pattern": "connected_grid",
            "block_traversal": "row_major",
            "collector_policy": "perimeter",
        }
        building = {
            "profiles": [
                {
                    "function": "residential",
                    "floor_policy": "seeded_uniform",
                    "entrance_side": "west",
                    "prototype_id": "residential_slab",
                },
                {
                    "function": "commercial",
                    "floor_policy": "midpoint",
                    "entrance_side": "west",
                    "prototype_id": "commercial_tower",
                },
            ]
        }
        skyline = {
            "profiles": [
                {
                    "function": "residential",
                    "min_floors": 2,
                    "max_floors": 3,
                    "centrality_bias": "distributed",
                    "height_role": "lowrise",
                },
                {
                    "function": "commercial",
                    "min_floors": 3,
                    "max_floors": 4,
                    "centrality_bias": "core",
                    "height_role": "mixed",
                },
            ],
            "highrise_ratio": 0.0,
            "landmark_count": 0,
            "landmark_functions": [],
            "skyline_strength": 0.8,
        }
        floor = {
            "profiles": [
                {
                    "function": "residential",
                    "layout": "double_loaded_corridor",
                    "corridor_ratio": 0.18,
                    "room_function_cycle": ["living_room", "bedroom", "kitchen"],
                },
                {
                    "function": "commercial",
                    "layout": "double_loaded_corridor",
                    "corridor_ratio": 0.2,
                    "room_function_cycle": ["office", "meeting_room", "reception"],
                },
            ]
        }
        floor_space = {
            "profiles": [
                {
                    "function": "residential",
                    "archetypes": [
                        {
                            "role": "ground",
                            "preferred_room_count": 5,
                            "min_room_count": 3,
                            "max_room_count": 8,
                            "target_room_area_m2": 36,
                            "min_room_width_m": 3.0,
                            "room_function_cycle": ["living_room", "kitchen", "bedroom"],
                            "unit_group_size": 3,
                        },
                        {
                            "role": "typical",
                            "preferred_room_count": 10,
                            "min_room_count": 6,
                            "max_room_count": 16,
                            "target_room_area_m2": 25,
                            "min_room_width_m": 2.8,
                            "room_function_cycle": ["living_room", "bedroom", "kitchen"],
                            "unit_group_size": 3,
                        },
                    ],
                },
                {
                    "function": "commercial",
                    "archetypes": [
                        {
                            "role": "ground",
                            "preferred_room_count": 5,
                            "min_room_count": 3,
                            "max_room_count": 9,
                            "target_room_area_m2": 55,
                            "min_room_width_m": 3.4,
                            "room_function_cycle": ["shop", "reception", "restroom"],
                            "unit_group_size": 1,
                        },
                        {
                            "role": "typical",
                            "preferred_room_count": 9,
                            "min_room_count": 5,
                            "max_room_count": 15,
                            "target_room_area_m2": 42,
                            "min_room_width_m": 3.0,
                            "room_function_cycle": ["open_office", "office", "meeting_room"],
                            "unit_group_size": 1,
                        },
                    ],
                },
            ]
        }
        service = FakeService(
            [
                json.dumps(spec_data),
                request("zones"),
                final(urban),
                request("planning_guidance"),
                final(skyline),
                request("prototype_catalog"),
                final(building),
                request("room_function_catalog"),
                final(floor_space),
                final(floor),
            ]
        )
        pipeline = HierarchicalAgenticGenerationPipeline(
            RequirementAgent(service, model_id="fake"),
            HierarchicalPlanningAgent(service, model_id="fake"),
        )
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            result = pipeline.run("build it", output)
            self.assertTrue(result.ok)
            self.assertTrue((output / "hierarchical_program.json").is_file())
            self.assertTrue((output / "hierarchy_trace.json").is_file())
            trace = json.loads((output / "hierarchy_trace.json").read_text())
            self.assertEqual(trace["totals"]["disclosure_rounds"], 4)


if __name__ == "__main__":
    unittest.main()
