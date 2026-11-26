import json
import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path

from cityg.agents import HierarchicalPlanningAgent, RepairAgent, RequirementAgent
from cityg.closed_loop import (
    ClosedLoopBudget,
    ClosedLoopCoordinator,
    IssueRouter,
)
from repair_fixtures import inject_error
from cityg.schemas import CitySpec
from cityg.serialization import to_primitive
from cityg.services import ManifestBackend, OpenUSDBackend
from cityg.validation import ValidationReport


class FakeService:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def complete(self, messages, response_schema=None):
        self.calls.append((messages, response_schema))
        response = self.responses.pop(0)
        if callable(response):
            response = response()
        return response if isinstance(response, str) else json.dumps(response)


def final(program):
    return {
        "action": "final",
        "detail_keys": [],
        "program_json": json.dumps(program),
    }


def responses(extra=()):
    spec = {
        "name": "closed_loop_test",
        "width_m": 180,
        "depth_m": 160,
        "building_count": 2,
        "min_floors": 2,
        "max_floors": 2,
        "rooms_per_floor": 3,
        "road_width_m": 10,
        "sidewalk_width_m": 2,
        "parcel_setback_m": 3,
        "seed": 7,
        "zones": [{"name": "homes", "function": "residential", "weight": 1}],
    }
    urban = {
        "district_order": ["zone_00"],
        "road_pattern": "connected_grid",
        "block_traversal": "row_major",
        "collector_policy": "perimeter",
    }
    building = {
        "profiles": [
            {
                "function": "residential",
                "floor_policy": "midpoint",
                "entrance_side": "west",
                "prototype_id": "residential_slab",
            }
        ]
    }
    skyline = {
        "profiles": [
            {
                "function": "residential",
                "min_floors": 2,
                "max_floors": 2,
                "centrality_bias": "core",
                "height_role": "lowrise",
            }
        ],
        "highrise_ratio": 0.0,
        "landmark_count": 0,
        "landmark_functions": [],
        "skyline_strength": 0.7,
    }
    floor = {
        "profiles": [
            {
                "function": "residential",
                "layout": "double_loaded_corridor",
                "corridor_ratio": 0.18,
                "room_function_cycle": ["living_room", "bedroom", "kitchen"],
            }
        ]
    }
    floor_space = {
        "profiles": [
            {
                "function": "residential",
                "archetypes": [
                    {
                        "role": "ground",
                        "preferred_room_count": 4,
                        "min_room_count": 3,
                        "max_room_count": 7,
                        "target_room_area_m2": 38,
                        "min_room_width_m": 3.0,
                        "room_function_cycle": ["living_room", "kitchen", "bedroom"],
                        "unit_group_size": 3,
                    },
                    {
                        "role": "typical",
                        "preferred_room_count": 8,
                        "min_room_count": 5,
                        "max_room_count": 12,
                        "target_room_area_m2": 26,
                        "min_room_width_m": 2.8,
                        "room_function_cycle": ["living_room", "bedroom", "kitchen"],
                        "unit_group_size": 3,
                    },
                ],
            }
        ]
    }
    return [
        json.dumps(spec),
        final(urban),
        final(skyline),
        final(building),
        final(floor_space),
        final(floor),
        *extra,
    ]


def coordinator(service, **kwargs):
    return ClosedLoopCoordinator(
        RequirementAgent(service, model_id="fake"),
        HierarchicalPlanningAgent(service, model_id="fake"),
        RepairAgent(service, model_id="fake"),
        simulation_backend=ManifestBackend(),
        export_viewer=False,
        **kwargs,
    )


class IssueRouterTests(unittest.TestCase):
    def test_single_scope_is_locally_repairable(self):
        report = ValidationReport()
        report.add(
            "error",
            "example",
            "repair me",
            "room_1",
            allowed_patch_scope="building_1",
        )
        route = IssueRouter().route(report)
        self.assertEqual(route.action, "repair")
        self.assertEqual(route.scope_id, "building_1")

    def test_multiple_scopes_require_replanning(self):
        report = ValidationReport()
        report.add("error", "a", "a", "a", allowed_patch_scope="building_1")
        report.add("error", "b", "b", "b", allowed_patch_scope="building_2")
        route = IssueRouter().route(report)
        self.assertEqual(route.action, "replan")
        self.assertIn("multiple", route.reason)


class ClosedLoopCoordinatorTests(unittest.TestCase):
    def test_urban_capacity_failure_is_replan_with_separate_evidence(self):
        from unittest.mock import patch
        from cityg.urban_requirements import UrbanPlanningConflict
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            with patch('cityg.closed_loop.ProgrammedCityPlanner.plan',
                       side_effect=UrbanPlanningConflict('capacity conflict', {'attempts': []})):
                result = coordinator(FakeService(responses())).run('build a city', output)
            self.assertEqual(result.run.status, 'replan_required')
            self.assertTrue((output/'failures'/'urban_planning.json').is_file())
            self.assertFalse((output/'failures'/'interior_requirements.json').exists())

    def test_cli_defaults_to_unlimited_total_tokens(self):
        from cityg.cli import _parser
        args = _parser().parse_args([
            "agent-build", "--requirement", "test city", "--output", "unused"])
        self.assertEqual(args.max_total_tokens, 0)
        self.assertEqual(args.max_tokens, 6144)

    def test_stagnant_repair_stops_without_token_quota(self):
        from cityg.repair import WorldPatch
        from unittest.mock import Mock

        pipeline = coordinator(FakeService(responses()), candidate_transform=lambda city:
                               inject_error(city, "disconnected_entrance", variant=0))
        def unchanged(city, report):
            return SimpleNamespace(
                city=city, validation=report, attempts=(), touched_entity_ids=(),
                patch=WorldPatch("no_progress", "building_000", (), {}),
                trace_dict=lambda: {"test": "unchanged repair"},
            )
        pipeline.repair_agent.repair = Mock(side_effect=unchanged)
        with tempfile.TemporaryDirectory() as temporary:
            result = pipeline.run("test repeated validation", Path(temporary) / "run")
        self.assertEqual(result.run.status, "budget_exhausted")
        self.assertIn("repeated validation issue", result.run.error["message"])
        self.assertEqual(pipeline.repair_agent.repair.call_count, 2)

    def test_unlimited_tokens_keep_usage_and_optional_cap_still_works(self):
        class HighUsageService(FakeService):
            def complete_with_metadata(self, messages, response_schema=None):
                return SimpleNamespace(
                    content=self.complete(messages, response_schema), finish_reason="stop",
                    usage={"prompt_tokens": 500_000, "completion_tokens": 10_000},
                )

        self.assertEqual(ClosedLoopBudget().max_total_tokens, 0)
        for cap, status in ((0, "success"), (140_000, "budget_exhausted")):
            with self.subTest(cap=cap), tempfile.TemporaryDirectory() as temporary:
                result = coordinator(HighUsageService(responses()),
                                     budget=ClosedLoopBudget(max_total_tokens=cap)).run(
                    "build a small community", Path(temporary) / "run")
                self.assertEqual(result.run.status, status, result.run.error)
                self.assertGreater(result.run.metrics.total_tokens, 140_000)
                record = json.loads((Path(temporary) / "run/run.json").read_text())
                self.assertEqual(record["budget"]["max_total_tokens"], cap)
                self.assertEqual(record["metrics"]["total_tokens"], result.run.metrics.total_tokens)
                if cap:
                    self.assertIn("model tokens", result.run.error["message"])

    def test_only_token_budget_accepts_zero_and_negative_is_invalid(self):
        with self.assertRaisesRegex(ValueError, "non-negative"):
            ClosedLoopBudget(max_total_tokens=-1)
        for name in ("max_total_model_calls", "max_repair_rounds", "max_wall_time_s",
                     "max_touched_entities", "repeated_issue_limit"):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "positive"):
                ClosedLoopBudget(**{name: 0})

    def test_unlimited_tokens_do_not_allow_endless_invalid_planning(self):
        service = FakeService(responses()[:1] + [final({"action_error": True})] * 4)
        with tempfile.TemporaryDirectory() as temporary:
            result = coordinator(service).run("build a small community", Path(temporary) / "run")
            self.assertEqual(result.run.status, "model_failure")
            self.assertIn("repeated 3 times", result.run.error["message"])
            self.assertEqual(len(service.calls), 4)  # requirement + three rejected urban plans
            self.assertTrue((Path(temporary) / "run/failures/hierarchy_urban.json").is_file())

    def test_first_pass_success_writes_replayable_run(self):
        service = FakeService(responses())
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "run"
            result = coordinator(service).run("build a small community", output)
            self.assertTrue(result.ok, result.run.to_dict())
            self.assertEqual(result.run.status, "success")
            self.assertEqual(result.run.metrics.model_calls, 6)
            self.assertTrue((output / "run.json").is_file())
            self.assertTrue((output / "events.jsonl").is_file())
            self.assertTrue((output / "requirement" / "requested_spec.json").is_file())
            self.assertTrue((output / "programs" / "hierarchical_program.json").is_file())
            self.assertTrue((output / "final" / "city.json").is_file())
            self.assertTrue((output / "final" / "manifest" / "city.json").is_file())
            events = [json.loads(line) for line in (output / "events.jsonl").read_text().splitlines()]
            self.assertEqual(
                [event["sequence"] for event in events], list(range(1, len(events) + 1))
            )
            self.assertEqual(events[-1]["detail"]["status"], "success")

    def test_single_scope_error_is_repaired_and_revalidated(self):
        removed = {}

        def transform(city):
            relation = next(
                item
                for item in city.world_program.relations
                if item.relation_type == "accessible_from"
                and item.source_id == "building_000"
            )
            removed["relation"] = to_primitive(relation)
            return inject_error(city, "disconnected_entrance", variant=0)

        def repair_response():
            return json.dumps(
                {
                    "reason": "restore required pedestrian access",
                    "operations": [
                        {
                            "op": "add_relation",
                            "target_id": "building_000",
                            "path": "",
                            "value_json": json.dumps(removed["relation"]),
                        }
                    ],
                }
            )

        service = FakeService(responses((repair_response,)))
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "run"
            result = coordinator(service, candidate_transform=transform).run(
                "build and repair", output
            )
            self.assertTrue(result.ok, result.run.to_dict())
            self.assertEqual(result.run.status, "repaired_success")
            self.assertEqual(result.run.metrics.repair_rounds, 1)
            self.assertEqual(
                result.run.metrics.distinct_touched_entity_ids, {"building_000"}
            )
            self.assertTrue((output / "repairs" / "round_01" / "patch.json").is_file())
            self.assertTrue(result.validation.ok)

    def test_openusd_and_portable_viewer_complete_the_delivery_path(self):
        service = FakeService(responses())
        pipeline = ClosedLoopCoordinator(
            RequirementAgent(service, model_id="fake"),
            HierarchicalPlanningAgent(service, model_id="fake"),
            RepairAgent(service, model_id="fake"),
            simulation_backend=OpenUSDBackend(),
            export_viewer=True,
        )
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "run"
            result = pipeline.run("build a simulation package", output)
            self.assertTrue(result.ok, result.run.to_dict())
            self.assertTrue(
                (output / "final" / "openusd" / "usd" / "city.usda").is_file()
            )
            self.assertTrue(
                (output / "final" / "openusd" / "geometry_manifest.json").is_file()
            )
            self.assertTrue((output / "viewer" / "serve.py").is_file())
            self.assertTrue(
                (output / "viewer" / "scene" / "navigation.json").is_file()
            )

    def test_total_model_call_budget_stops_at_stage_boundary(self):
        service = FakeService(responses())
        budget = ClosedLoopBudget(max_total_model_calls=3)
        with tempfile.TemporaryDirectory() as temporary:
            result = coordinator(service, budget=budget).run(
                "budgeted build", Path(temporary) / "run"
            )
            self.assertFalse(result.ok)
            self.assertEqual(result.run.status, "budget_exhausted")
            self.assertIn("model calls", result.run.error["message"])

    def test_nonempty_output_is_rejected_before_mutation(self):
        service = FakeService(responses())
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            marker = output / "keep.txt"
            marker.write_text("owned by user")
            with self.assertRaisesRegex(ValueError, "must be empty"):
                coordinator(service).run("do not overwrite", output)
            self.assertEqual(marker.read_text(), "owned by user")
            self.assertFalse(service.calls)

    def test_repeated_trials_share_fingerprint_but_have_unique_run_ids(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = coordinator(FakeService(responses())).run("same request", root / "a")
            second = coordinator(FakeService(responses())).run("same request", root / "b")
            self.assertEqual(
                first.run.requirement_fingerprint,
                second.run.requirement_fingerprint,
            )
            self.assertNotEqual(first.run.run_id, second.run.run_id)


if __name__ == "__main__":
    unittest.main()
