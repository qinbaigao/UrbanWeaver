import json
import tempfile
import unittest
from pathlib import Path
from dataclasses import replace

from cityg.assets import AssetRecord, AssetRegistry
from cityg.facade_assets import FacadeAssetIndex
from cityg.buildings import BuildingSelector
from cityg.buildings.selector import BuildingSelectionContext
from cityg.planning import BaselineCityPlanner
from cityg.planning.interiors import FloorDetailAgent
from cityg.refinement import (
    BuildingRefinementAgent,
    BuildingRefinementPlan,
    RoomProgramAgent,
    RoomLayoutRefinementAgent,
    RoomLayoutRefinementPlan,
    RoomObjectAdjustment,
    apply_room_layout_refinement,
    apply_building_refinement,
    room_archetype_key,
    select_refinement_candidates,
    apply_streetscape_visual_refinement,
)
from cityg.refinement.selection import mark_room_detail, select_hero_rooms
from cityg.schemas import CitySpec
from cityg.visual_review import VisualReviewAgent
from cityg.adaptive_review import aggregate_visual_reviews, route_visual_issues


class FakeService:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0
        self.last_messages = None

    def complete(self, messages, response_schema=None):
        self.calls += 1
        self.last_messages = messages
        return json.dumps(self.payload)


class FakeVision:
    def __init__(self, payload):
        self.payload = payload

    def review(self, prompt, image_paths):
        return json.dumps(self.payload)


class RefinementTests(unittest.TestCase):
    def setUp(self):
        self.city = BaselineCityPlanner().plan(
            CitySpec(
                name="refinement_test", width_m=180, depth_m=160,
                building_count=4, min_floors=2, max_floors=2,
                rooms_per_floor=4, seed=8,
            )
        )

    def test_building_agent_proposal_is_applied_as_versioned_patch(self):
        building = next(self.city.iter_buildings())
        service = FakeService({
            "building_id": building.id,
            "reason": "differentiate a frontage building",
            "confidence": 0.9,
            "adjustments": {"massing_variant": None, "facade_style_override": "frontage", "podium_floors": None},
        })
        agent = BuildingRefinementAgent(service)
        plan, attempts = agent.propose(self.city, building.id)
        result = apply_building_refinement(self.city, plan, attempts=attempts, model_id="fake")
        self.assertTrue(result.validation.ok)
        updated = next(item for item in result.city.iter_buildings() if item.id == building.id)
        self.assertEqual(updated.metadata["facade_style_override"], "frontage")
        node = next(item for item in result.city.world_program.nodes if item.entity_id == building.id)
        self.assertEqual(node.version, 2)

    def test_building_agent_can_commit_catalog_archetype(self):
        building = next(self.city.iter_buildings())
        archetype_id = building.metadata["archetype_id"]
        service = FakeService({
            "building_id": building.id,
            "reason": "select a catalog-grounded facade family",
            "confidence": 0.91,
            "adjustments": {
                "archetype_id": archetype_id,
                "massing_variant": None,
                "facade_style_override": None,
                "podium_floors": None,
            },
        })
        plan, attempts = BuildingRefinementAgent(service).propose(
            self.city,
            building.id,
            visual_feedback={
                "issues": [{
                    "description": "facade repetition",
                    "candidate_archetype_ids": [archetype_id],
                }]
            },
        )
        result = apply_building_refinement(self.city, plan, attempts=attempts)
        updated = next(item for item in result.city.iter_buildings() if item.id == building.id)
        self.assertEqual(updated.metadata["archetype_id"], archetype_id)
        self.assertTrue(result.validation.ok)

    def test_building_agent_facade_assets_are_bound_to_supplied_candidates(self):
        building = next(self.city.iter_buildings())
        facade_asset_id = "facade_reviewed_window"
        record = {
            "asset_id": facade_asset_id,
            "display_name": "reviewed window",
            "semantic_type": "window_bay",
            "source_id": "test",
            "compatible_building_functions": [building.function],
            "compatible_facade_zones": ["podium", "shaft"],
            "placement": {},
            "repeatability": {},
            "orientation": {"visual_review_required": False},
            "appearance": {},
            "quality": {"score": .9, "vlm_visual_quality_score": .86},
            "selection_status": "usable",
            "tags": ["window"],
        }
        index = FacadeAssetIndex({
            "schema_version": "cityg.facade_asset_annotations.v1",
            "assets": [record],
        })
        service = FakeService({
            "building_id": building.id,
            "reason": "use the reviewed opening module",
            "confidence": .91,
            "adjustments": {
                "massing_variant": None,
                "podium_floors": None,
                "facade_style_override": None,
                "facade_asset_ids": [facade_asset_id],
            },
        })
        plan, attempts = BuildingRefinementAgent(
            service, facade_asset_index=index
        ).propose(self.city, building.id)
        result = apply_building_refinement(self.city, plan, attempts=attempts)
        updated = next(
            item for item in result.city.iter_buildings() if item.id == building.id
        )
        self.assertEqual(updated.metadata["facade_asset_ids"], [facade_asset_id])
        self.assertIn(facade_asset_id, service.last_messages[1].content)

    def test_building_agent_cannot_escape_rendered_contact_sheet(self):
        building = next(self.city.iter_buildings())
        compatible = [
            item for item in BuildingSelector().candidates(
                BuildingSelectionContext.from_building(building)
            )
        ]
        self.assertGreaterEqual(len(compatible), 2)
        service = FakeService({
            "building_id": building.id,
            "reason": "choose an unrendered alternative",
            "confidence": 0.9,
            "adjustments": {
                "archetype_id": compatible[1].archetype_id,
                "massing_variant": None,
                "facade_style_override": None,
                "podium_floors": None,
            },
        })
        with self.assertRaises(Exception):
            BuildingRefinementAgent(service, max_attempts=1).propose(
                self.city,
                building.id,
                visual_feedback={
                    "contact_sheet_comparison": {
                        "available": True,
                        "candidate_archetype_ids": [compatible[0].archetype_id],
                    }
                },
            )

    def test_lowrise_highrise_only_adjustments_are_normalized(self):
        building = next(self.city.iter_buildings())
        service = FakeService({
            "building_id": building.id,
            "reason": "try a tower-like facade",
            "confidence": 0.8,
            "adjustments": {
                "massing_variant": "setback",
                "facade_style_override": "contextual_midrise",
                "podium_floors": 2,
            },
        })
        agent = BuildingRefinementAgent(service)
        plan, _ = agent.propose(self.city, building.id)
        self.assertEqual(plan.adjustments, {"facade_style_override": "contextual_midrise"})
        self.assertEqual(
            plan.normalization_notes,
            ("dropped massing_variant for non-high-rise building", "dropped podium_floors for non-high-rise building"),
        )

    def test_room_program_is_cached_by_archetype_and_remapped_to_room_id(self):
        building = next(self.city.iter_buildings())
        floor = building.floors[0]
        room = next(item for item in floor.rooms if item.function != "corridor")
        payload = {
            "room_id": room.id, "style": "compact", "density": 0.4,
            "requests": [{"category": "desk", "count": 1, "placement": "wall_back", "required": True}],
        }
        agent = RoomProgramAgent(FakeService(payload))
        first = agent.propose(self.city, building, floor, room)
        self.assertEqual(first.program.room_id, room.id)
        other_room = replace(room, id=f"{room.id}_archetype_copy")
        # Cache reuse is safe only with the same openings, not merely a similar
        # area/function. Remap the copied door graph as well as the room ID.
        other_floor = replace(floor, objects=[replace(o,room_id=other_room.id) for o in floor.objects if o.room_id==room.id], doors=[replace(d,
            room_a_id=other_room.id if d.room_a_id == room.id else d.room_a_id,
            room_b_id=other_room.id if d.room_b_id == room.id else d.room_b_id)
            for d in floor.doors])
        second = agent.propose(self.city, building, other_floor, other_room)
        self.assertEqual(second.program.room_id, other_room.id)
        self.assertEqual(first.archetype_key, second.archetype_key)

    def test_grouped_room_cannot_accept_requests_only_patch(self):
        from cityg.agents.requirement import AgentGenerationError
        building = next(self.city.iter_buildings())
        floor = building.floors[0]
        room = next(item for item in floor.rooms if item.function != "corridor")
        room.metadata["room_design"] = {"status": "accepted"}
        agent = RoomProgramAgent(FakeService({
            "room_id": room.id, "style": "minimal", "density": .4,
            "requests": [{"category":"desk", "count":1, "placement":"center", "required":True}]
        }))
        with self.assertRaises(AgentGenerationError):
            agent.propose(self.city, building, floor, room)

    def test_room_program_accepts_semantic_relations_and_cache_preserves_them(self):
        building = next(self.city.iter_buildings())
        floor = building.floors[0]
        room = next(item for item in floor.rooms if item.function != "corridor")
        payload = {
            "room_id": room.id, "style": "hero", "density": 0.5,
            "requests": [
                {"category": "desk", "count": 1, "placement": "wall_back", "required": True},
                {"category": "office_chair", "count": 1, "placement": "center", "required": True},
            ],
            "relations": [{
                "subject_category": "office_chair", "relation": "faces",
                "target_category": "desk", "distance_m": 0.7, "required": True,
            }],
        }
        agent = RoomProgramAgent(FakeService(payload))
        first = agent.propose(self.city, building, floor, room)
        second = agent.propose(self.city, building, floor, room)
        self.assertEqual(len(first.program.relations), 1)
        self.assertEqual(second.program.relations[0].relation, "faces")

    def test_room_layout_agent_emits_object_local_semantic_operations(self):
        building = next(self.city.iter_buildings())
        floor = building.floors[0]
        room = next(item for item in floor.rooms if item.object_ids)
        obj = next(item for item in floor.objects if item.room_id == room.id)
        payload = {
            "room_id": room.id,
            "reason": "free the circulation path",
            "confidence": 0.88,
            "operations": [{
                "object_id": obj.id,
                "action": "move",
                "placement": "wall_side",
                "facing": "room_center",
                "target_object_id": None,
                "replacement_category": None,
                "reason": "the current position blocks circulation",
            }],
        }
        service = FakeService(payload)
        proposal = RoomLayoutRefinementAgent(service).propose(
            self.city,
            building,
            floor,
            room,
            visual_feedback={"issues": [{"description": "object blocks aisle"}]},
        )
        self.assertEqual(proposal.plan.operations[0].object_id, obj.id)
        self.assertEqual(proposal.plan.operations[0].placement, "wall_side")
        prompt = service.last_messages[-1].content
        self.assertIn("Never output coordinates", prompt)

    def test_layout_subject_is_limited_to_grounded_group_even_if_model_ignores_schema(self):
        from cityg.agents.requirement import AgentGenerationError
        building = next(self.city.iter_buildings())
        floor = building.floors[0]
        room = next(r for r in floor.rooms if len(r.object_ids) >= 2)
        first, neighbor = [o for o in floor.objects if o.room_id == room.id][:2]
        room.metadata['room_design'] = {'groups':[{'id':'fault'}]}
        first.metadata['group_key'] = 'fault'
        payload = {'room_id':room.id, 'reason':'turn chair', 'confidence':.9, 'operations':[
            {'object_id':neighbor.id,'action':'rotate','placement':'preserve','facing':'target_object',
             'target_object_id':first.id,'replacement_category':None,'reason':'turn to desk'}]}
        class Service(FakeService):
            def complete(self, messages, response_schema):
                enum=response_schema['properties']['operations']['items']['properties']['object_id']['enum']
                assert enum == [first.id]
                return super().complete(messages,response_schema)
        agent=RoomLayoutRefinementAgent(Service(payload),max_attempts=1)
        def propose():
            return agent.propose(self.city,building,floor,room,visual_feedback={'target_group_ids':['fault']})
        with self.assertRaises(AgentGenerationError):
            propose()
        payload['operations'][0].update(object_id=first.id,target_object_id=neighbor.id)
        self.assertEqual(propose().plan.operations[0].target_object_id,neighbor.id)

    def test_room_layout_commit_is_transactional_and_collision_checked(self):
        building = next(self.city.iter_buildings())
        floor = building.floors[0]
        room = next(item for item in floor.rooms if item.object_ids)
        obj = next(item for item in floor.objects if item.room_id == room.id)
        original_position = (obj.position.x, obj.position.y)
        plan = RoomLayoutRefinementPlan(
            room_id=room.id,
            reason="move one object away from circulation",
            confidence=0.9,
            operations=(
                RoomObjectAdjustment(
                    object_id=obj.id,
                    action="move",
                    placement="wall_side",
                    facing="room_center",
                    reason="VLM found it in the circulation path",
                ),
            ),
        )
        result = apply_room_layout_refinement(self.city, plan, seed=31)
        self.assertTrue(result.validation.ok)
        self.assertTrue(result.changed)
        updated = next(
            item for item in result.city.iter_objects() if item.id == obj.id
        )
        self.assertEqual((obj.position.x, obj.position.y), original_position)
        self.assertEqual(
            updated.metadata["planner"],
            "RoomLayoutRefinementAgent+FloorDetailAgent",
        )

    def test_room_layout_gate_rejects_barren_regression(self):
        detail = FloorDetailAgent()
        detail.populate(self.city, seed=21)
        building = next(self.city.iter_buildings())
        floor = building.floors[0]
        room = next(item for item in floor.rooms if len(item.object_ids) >= 4)
        objects = [item for item in floor.objects if item.room_id == room.id]
        plan = RoomLayoutRefinementPlan(
            room_id=room.id,
            reason="intentionally over-aggressive sparse rewrite",
            confidence=0.99,
            operations=tuple(
                RoomObjectAdjustment(
                    object_id=item.id,
                    action="remove",
                    reason="remove for gate regression test",
                )
                for item in objects[:-1]
            ),
        )
        result = apply_room_layout_refinement(self.city, plan, seed=21)
        self.assertFalse(result.changed)
        self.assertFalse(result.gate["ok"])
        self.assertEqual(result.gate["code"], "furnishing_non_degradation")
        restored = next(item for item in result.city.iter_rooms() if item.id == room.id)
        self.assertEqual(len(restored.object_ids), len(objects))

    def test_room_layout_gate_allows_non_destructive_reposition(self):
        detail = FloorDetailAgent()
        detail.populate(self.city, seed=22)
        building = next(self.city.iter_buildings())
        floor = building.floors[0]
        room = next(item for item in floor.rooms if item.object_ids)
        obj = next(item for item in floor.objects if item.room_id == room.id)
        plan = RoomLayoutRefinementPlan(
            room_id=room.id,
            reason="reorient an existing object",
            confidence=0.9,
            operations=(RoomObjectAdjustment(
                object_id=obj.id,
                action="rotate",
                facing="room_center",
                reason="improve facing",
            ),),
        )
        result = apply_room_layout_refinement(self.city, plan, seed=22)
        self.assertTrue(result.changed)
        self.assertTrue(result.gate["ok"])

    def test_room_layout_normalizes_incompatible_asset_move_to_remove(self):
        building = next(self.city.iter_buildings())
        floor = building.floors[0]
        room = next(item for item in floor.rooms if item.object_ids)
        obj = next(item for item in floor.objects if item.room_id == room.id)
        registry = AssetRegistry()
        registry.register(
            AssetRecord(
                asset_id=obj.asset_id,
                category=obj.category,
                environment="outdoor",
            )
        )
        payload = {
            "room_id": room.id,
            "reason": "remove an outdoor-looking obstruction",
            "confidence": 0.91,
            "operations": [{
                "object_id": obj.id,
                "action": "move",
                "placement": "wall_side",
                "facing": "room_center",
                "target_object_id": None,
                "replacement_category": None,
                "reason": "move it away from circulation",
            }],
        }
        proposal = RoomLayoutRefinementAgent(
            FakeService(payload), asset_registry=registry
        ).propose(
            self.city,
            building,
            floor,
            room,
            visual_feedback="the object looks inappropriate and blocks circulation",
        )
        self.assertEqual(proposal.plan.operations[0].action, "remove")
        self.assertTrue(proposal.normalization_notes)

    def test_hero_room_selection_is_bounded_diverse_and_marked(self):
        selection = select_hero_rooms(self.city, max_rooms=3)
        self.assertLessEqual(len(selection.room_ids), 3)
        self.assertEqual(len(selection.room_ids), len(set(selection.room_ids)))
        mark_room_detail(self.city, set(selection.room_ids), status="selected", selection=selection)
        selected = {
            room.id: room
            for room in self.city.iter_rooms()
            if room.id in selection.room_ids
        }
        self.assertEqual(len(selected), len(selection.room_ids))
        self.assertTrue(all(room.metadata["detail_tier"] == "hero" for room in selected.values()))

    def test_visual_gate_reports_missing_image_without_calling_model(self):
        result = VisualReviewAgent(FakeVision({})).review("inspect", ["/does/not/exist.png"])
        self.assertFalse(result.available)
        self.assertIn("missing image", result.error)

    def test_multiview_review_aggregates_and_routes_known_entities(self):
        building = next(self.city.iter_buildings())
        room = next(item for item in building.floors[0].rooms if item.function != "corridor")
        payload = {
            "issues": [
                {"issue_id": "b1", "severity": "warning", "category": "facade", "entity_id": building.id,
                 "confidence": .95, "binding_confidence": .95, "binding_basis": "exact_view_target",
                 "description": "facade variation is weak", "suggested_action": "personalize facade",
                 "candidate_archetype_ids": [building.metadata["archetype_id"]]},
                {"issue_id": "r1", "severity": "info", "category": "room", "entity_id": room.id,
                 "confidence": .95, "binding_confidence": .95, "binding_basis": "exact_view_target",
                 "description": "room is sparse", "suggested_action": "add a few objects",
                 "target_group_ids": ["workstation"],
                 "asset_requests": [{"category": "office_chair", "count": 2, "description": "desk seating"}]},
            ],
            "summary": "two visible issues",
        }
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "view.png"
            image.write_bytes(b"not-a-real-png")
            (Path(directory)/'asset_load_status.json').write_text(json.dumps({'views':{
                'view':{'ready':True,'signal_available':True,'geometry_streaming':{'ready':True}}}}))
            report = aggregate_visual_reviews(
                {"selected_views": [{
                    "view_id": "view", "kind": "global",
                    "target_entity_ids": [self.city.id, building.id, room.id],
                }]},
                directory,
                VisualReviewAgent(FakeVision(payload), max_images=4),
                scene_id=self.city.id,
            )
        route = route_visual_issues(self.city, report)
        self.assertEqual(route["building_refinement_ids"], [building.id])
        self.assertEqual(route["room_refinement_ids"], [room.id])
        self.assertFalse(route["deferred_patch_issues"])
        room_issue = next(item for item in report["aggregated_issues"] if item["entity_id"] == room.id)
        self.assertEqual(room_issue["asset_requests"][0]["category"], "office_chair")
        self.assertEqual(room_issue["target_group_ids"], ["workstation"])
        building_issue = next(item for item in report["aggregated_issues"] if item["entity_id"] == building.id)
        self.assertEqual(building_issue["candidate_archetype_ids"], [building.metadata["archetype_id"]])

    def test_populate_rooms_preserves_unselected_room_objects(self):
        detail = FloorDetailAgent()
        detail.populate(self.city, seed=4)
        building = next(self.city.iter_buildings())
        floor = building.floors[0]
        rooms = [item for item in floor.rooms if item.function != "corridor"]
        untouched = rooms[1]
        before = tuple(untouched.object_ids)
        stats = detail.populate_rooms(self.city, {rooms[0].id}, seed=9)
        self.assertEqual(stats["matched_room_count"], 1)
        self.assertEqual(tuple(untouched.object_ids), before)

    def test_low_confidence_binding_is_deferred(self):
        building = next(self.city.iter_buildings())
        route = route_visual_issues(self.city, {
            "aggregated_issues": [{
                "issue_id": "ambiguous",
                "category": "facade",
                "entity_id": building.id,
                "entity_type": "building",
                "binding_confidence": 0.41,
            }]
        })
        self.assertEqual(route["building_refinement_ids"], [])
        self.assertEqual(
            route["deferred_patch_issues"][0]["route_reason"],
            "low_binding_confidence_or_type_mismatch",
        )

    def test_known_entity_does_not_authorize_uncertain_visual_claim(self):
        building=next(self.city.iter_buildings())
        for confidence in (None,.4,float('nan'),1.1,'0.99',True):
            issue={'entity_id':building.id,'entity_type':'building','category':'facade',
                   'binding_confidence':.99}
            if confidence is not None: issue['confidence']=confidence
            route=route_visual_issues(self.city,{'aggregated_issues':[issue]})
            self.assertEqual(route['building_refinement_ids'],[])
            self.assertEqual(route['deferred_patch_issues'][0]['route_reason'],
                             'low_or_missing_issue_confidence')

    def test_room_entity_can_route_layout_category_to_room_refinement(self):
        building = next(self.city.iter_buildings())
        room = next(item for item in building.floors[0].rooms if item.function != "corridor")
        route = route_visual_issues(self.city, {
            "aggregated_issues": [{
                "issue_id": "room_layout",
                "category": "layout",
                "entity_id": room.id,
                "entity_type": "room",
                "binding_confidence": 0.86,
                "confidence": .9,
            }]
        })
        self.assertEqual(route["room_refinement_ids"], [room.id])

    def test_room_entity_can_route_non_room_visual_category(self):
        building = next(self.city.iter_buildings())
        room = next(item for item in building.floors[0].rooms if item.function != "corridor")
        route = route_visual_issues(self.city, {
            "aggregated_issues": [{
                "issue_id": "room_lighting",
                "category": "lighting",
                "entity_id": room.id,
                "entity_type": "room",
                "binding_confidence": 0.84,
                "confidence": .9,
            }]
        })
        self.assertEqual(route["room_refinement_ids"], [room.id])

    def test_exact_road_issue_routes_and_commits_semantic_streetscape_patch(self):
        road = self.city.road_network.segments[0]
        issue = {
            "issue_id": "street-empty",
            "category": "road",
            "issue_code": "street_underfurnished",
            "entity_id": road.id,
            "entity_type": "road",
            "binding_confidence": 0.91,
            "confidence": .9,
            "description": "The street is visibly sparse",
            "suggested_action": "add bounded street furniture",
        }
        route = route_visual_issues(self.city, {"aggregated_issues": [issue]})
        self.assertEqual(route["streetscape_refinement_ids"], [road.id])
        result = apply_streetscape_visual_refinement(self.city, [issue], max_roads=1)
        self.assertTrue(result.changed)
        self.assertEqual(result.changed_road_ids, (road.id,))
        program = result.city.metadata["street_network_program"]
        selected = next(item for item in program["segments"] if item["road_id"] == road.id)
        self.assertEqual(selected["source"], "vlm_refined")
        self.assertEqual(self.city.metadata.get("street_network_program"), None)


if __name__ == "__main__":
    unittest.main()
