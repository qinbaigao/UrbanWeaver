import json
import math
import unittest
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import replace

from cityg.geometry.model import GeometryScene, Vec3
from cityg.geometry.primitives import PrimitiveFactoryMixin
from cityg.geometry.surface_dressing import compile_surface_items, surfaces, overlaps
from cityg.planning.furnishing_brief import capacity_context, check_capacity
from cityg.planning.interiors import ASSET_CATALOG, FloorDetailAgent, FurnishingProgram
from cityg.planning.room_design import RoomDesign
from cityg.planning.room_groups import place_room_design, RoomDesignInfeasible
from cityg.planning.surface_items import SURFACE_CATALOG
from cityg.refinement.room import RoomProgramAgent
from cityg.schemas import Bounds2D, Room, Floor, InteriorObject, Point2D


def fixture_design():
    return RoomDesign("work and read", "warm", ({"id": "work", "purpose": "work", "position": "center"},),
        ({"id": "station", "zone": "work", "anchor": {"id": "desk", "category": "desk"},
          "members": [{"id": "chair", "category": "office_chair", "side": "front", "slot": 0,
                       "gap_m": .25, "face_anchor": True}]},),
        furnishing_brief={"occupants": 1, "capacity_reason": "One-person private office",
            "items": [{"category": c, "minimum": 1, "target": 1, "purpose": "Workstation"}
                      for c in ("desk", "office_chair")], "tradeoffs": ""},
        surface_items=tuple({"id": c, "support_member_id": "desk", "surface": "top",
                            "category": c, "count": 1, "placement": p}
                            for c, p in (("monitor", "back"), ("keyboard", "front"), ("cup", "right"))))


class RoomEnrichmentTests(unittest.TestCase):
    def setUp(self):
        self.room = Room("r", "Office", "office", Bounds2D(0, 0, 8, 7))
        self.floor = Floor("f", 0, 0, 3, rooms=[self.room])
        self.design = fixture_design()
        self.compiler = PrimitiveFactoryMixin()

    def test_capacity_hints_scale_but_do_not_overwrite_requested_capacity(self):
        small = capacity_context(replace(self.room, bounds=Bounds2D(0, 0, 4, 4)))
        self.room.metadata["spatial_requirement"] = {"capacity": 2}
        big = capacity_context(self.room)
        self.assertGreater(big["advisory_occupants_range"][1], small["advisory_occupants_range"][1])
        self.assertEqual(big["requested_capacity"], 2)

    def test_brief_roundtrip_and_legacy_compatibility(self):
        self.design.validate(ASSET_CATALOG)
        self.assertEqual(RoomDesign.from_dict(json.loads(json.dumps(self.design.to_dict())), ASSET_CATALOG), self.design)
        legacy = self.design.to_dict()
        legacy.pop("furnishing_brief"); legacy.pop("surface_items")
        self.assertIsNone(RoomDesign.from_dict(legacy, ASSET_CATALOG).furnishing_brief)

    def test_essential_shortfall_rejected(self):
        bad = deepcopy(self.design)
        bad.furnishing_brief["items"][0].update(minimum=2, target=2)
        with self.assertRaisesRegex(ValueError, "essential furnishing shortfall"):
            bad.validate(ASSET_CATALOG)

    def test_optional_target_shortfall_requires_explanation(self):
        bad = deepcopy(self.design)
        bad.furnishing_brief["items"][0]["target"] = 2
        with self.assertRaisesRegex(ValueError, "explain target shortfall"):
            bad.validate(ASSET_CATALOG)
        bad.furnishing_brief["tradeoffs"] = "Keep a single desk for a private office."
        bad.validate(ASSET_CATALOG)

    def test_capacity_cannot_exceed_realized_workstations(self):
        bad = deepcopy(self.design)
        bad.furnishing_brief["occupants"] = 2
        with self.assertRaisesRegex(ValueError, "requires at least"):
            check_capacity(self.room, bad.furnishing_brief, bad.groups)

    def test_reduced_requested_capacity_requires_tradeoff(self):
        self.room.metadata["spatial_requirement"] = {"capacity": 4}
        with self.assertRaisesRegex(ValueError, "requested capacity"):
            check_capacity(self.room, self.design.furnishing_brief, self.design.groups)

    def test_invalid_support_and_budget_rejected(self):
        bad = deepcopy(self.design)
        bad.surface_items[0]["support_member_id"] = "missing"
        with self.assertRaises(ValueError): bad.validate(ASSET_CATALOG)
        many = tuple({**self.design.surface_items[0], "id": f"item_{i}", "count": 8} for i in range(7))
        with self.assertRaisesRegex(ValueError, "48"):
            replace(self.design, surface_items=many).validate(ASSET_CATALOG)

    def test_surface_request_budget_remains_bounded(self):
        requests = tuple({**self.design.surface_items[0], 'id': f'item_{i}', 'count': 1} for i in range(33))
        replace(self.design, surface_items=requests[:32]).validate(ASSET_CATALOG)
        with self.assertRaisesRegex(ValueError, '32'):
            replace(self.design, surface_items=requests).validate(ASSET_CATALOG)

    def setup_geometry(self, yaw=30):
        self.room.metadata["room_design"] = {"status": "accepted", **self.design.to_dict()}
        obj = InteriorObject("obj", "r", "desk", "procedural::desk::v1", Point2D(4, 4), 1.4, .7, .75,
                             metadata={"design_member_id": "desk", "front_axis": "+Y", "group_key": "station"})
        self.floor.objects = [obj]
        top = self.compiler._box("top", "obj", Vec3(40, 34, .70), Vec3(1.4, .7, .1), yaw,
            "furniture_table", "furniture_wood", "floor:f", metadata={"component": "top", "proxy_style": "table"})
        self.scene = GeometryScene("city", "z_up", primitives=[top])
        self.owners = {"obj": [top]}
        return top

    def compile(self):
        compile_surface_items(self.compiler, self.floor, self.room, self.scene, self.owners,
                              [p for p in self.scene.primitives if not p.metadata.get("surface_subentity")])
        return self.scene.metadata["room_surface_items"]["r"]

    def test_children_follow_realized_rotated_support_and_have_unique_identity(self):
        top = self.setup_geometry()
        report = self.compile()
        self.assertEqual(report["placed"], 3)
        children = [p for p in self.scene.primitives if p.metadata.get("surface_subentity")]
        self.assertEqual(len({p.metadata["subentity_id"] for p in children}), 3)
        for p in children:
            self.assertEqual(p.owner_id, "obj")
            self.assertEqual(p.metadata["room_ids"], ["r"])
            self.assertFalse(p.collision_enabled)
            self.assertGreaterEqual(p.center.z-p.size.z/2, .75-1e-6)
            a = math.radians(-top.rotation_z_deg)
            dx, dy = p.center.x-top.center.x, p.center.y-top.center.y
            x, y = dx*math.cos(a)-dy*math.sin(a), dx*math.sin(a)+dy*math.cos(a)
            self.assertLessEqual(abs(x)+p.size.x/2, top.size.x/2+1e-6)
            self.assertLessEqual(abs(y)+p.size.y/2, top.size.y/2+1e-6)
        monitor = next(i for i in report["items"] if i["category"] == "monitor")
        keyboard = next(i for i in report["items"] if i["category"] == "keyboard")
        self.assertLess(monitor["local_xy_m"][1], keyboard["local_xy_m"][1])

    def test_siblings_do_not_overlap_and_compile_is_deterministic(self):
        self.setup_geometry(90)
        first = deepcopy(self.compile())
        groups = defaultdict(list)
        for p in self.scene.primitives:
            if p.metadata.get("subentity_id"): groups[p.metadata["subentity_id"]].append(p)
        for aid, aps in groups.items():
            for bid, bps in groups.items():
                if aid != bid:
                    self.assertFalse(any(overlaps(a, b, gap=0) for a in aps for b in bps))
        self.setup_geometry(90)
        self.assertEqual(first, self.compile())

    def test_unknown_glb_surface_skipped_not_guessed(self):
        top = self.setup_geometry()
        top.metadata = {"resolved_asset": True}
        report = self.compile()
        self.assertEqual(report["placed"], 0)
        self.assertTrue(all(i["reason"] == "no_verified_surface" for i in report["skipped"]))

    def test_reviewed_glb_support_annotation(self):
        top = self.setup_geometry()
        top.metadata = {"resolved_asset": True, "asset_metadata": {"room_support_surfaces": [
            {"id": "desk_top", "verified": True, "kind": "top", "center": [0, 0, .5], "size": [1, 1]}]}}
        self.assertEqual(self.compile()["placed"], 3)
        top.metadata["asset_metadata"]["room_support_surfaces"][0]["center"] = [1, 0, .5]
        self.assertEqual(surfaces([top], "top"), [])

    def test_obstructed_surface_skips_without_moving_major_furniture(self):
        top = self.setup_geometry()
        blocker = self.compiler._box("blocker", "other", Vec3(40, 34, 1.2), Vec3(1.4, .7, 1), 30,
                                     "furniture_storage", "furniture_wood", "floor:f")
        self.scene.primitives.append(blocker)
        before = deepcopy(self.floor.objects)
        self.assertEqual(self.compile()["placed"], 0)
        self.assertEqual(before, self.floor.objects)

    def test_shelves_use_multiple_heights_without_crossing_upper_slab(self):
        self.setup_geometry(0)
        self.room.metadata["room_design"]["surface_items"] = [
            {"id": "books", "support_member_id": "desk", "surface": "shelves", "category": "book", "count": 8, "placement": "spread"}]
        shelves = [self.compiler._box(f"s{i}", "obj", Vec3(4, 4, z), Vec3(1.1, .38, .05), 0,
            "furniture_storage", "furniture_wood", "floor:f", metadata={"component": f"shelf_{i}", "proxy_style": "rack"})
            for i, z in enumerate((.1, .7, 1.3))]
        self.scene.primitives = shelves[:]; self.owners = {"obj": shelves}
        report = self.compile()
        self.assertEqual(report["placed"], 8)
        self.assertEqual(len({i["bottom_z_m"] for i in report["items"]}), 3)
        children = [p for p in self.scene.primitives if p.metadata.get("surface_subentity")]
        self.assertFalse(any(overlaps(c, s, gap=0) for c in children for s in shelves))

    def test_protected_groups_also_protect_surface_program(self):
        detail = FloorDetailAgent()
        program = FurnishingProgram("r", "office", "warm", .4, (), design=self.design)
        self.floor.objects = place_room_design(detail, None, self.floor, self.room, program, 17)
        self.room.metadata["room_design"] = {"status": "accepted", **self.design.to_dict()}
        bad = replace(self.design, protected_groups=("station",), surface_items=())
        with self.assertRaisesRegex(RoomDesignInfeasible, "surface items"):
            place_room_design(detail, None, self.floor, self.room, replace(program, design=bad), 17)

    def test_agent_contract_and_context(self):
        payload = {"room_id": "r", "style": "warm", "density": .4, "requests": [], "design": self.design.to_dict()}
        captured = []
        class Service:
            def complete(_, messages, schema):
                captured.append((messages, schema))
                return json.dumps(payload)
        city = type("C", (), {"name": "test"})()
        building = type("B", (), {"id": "b", "function": "office"})()
        result = RoomProgramAgent(Service()).propose(city, building, self.floor, self.room)
        self.assertEqual(result.program.design.furnishing_brief["occupants"], 1)
        self.assertEqual(len(result.program.design.surface_items), 3)
        prompt = json.loads(captured[0][0][1].content)
        self.assertIn("capacity_context", prompt)
        self.assertIn("surface_object_dimensions_m", prompt)
        self.assertIn("furnishing_brief", captured[0][1]["properties"]["design"]["required"])

    def test_compact_realized_desktop_can_hold_monitor_and_keyboard(self):
        top = self.setup_geometry()
        top.size = Vec3(1.2096, .4032, .12)  # actual massing-fitted fixture size
        self.assertEqual(self.compile()["placed"], 3)

    def test_surface_contents_do_not_change_major_object_budget(self):
        program = FurnishingProgram("r", "office", "warm", .4, (), design=self.design)
        self.assertEqual(program.requested_major_count, 2)
        self.assertEqual(sum(i["count"] for i in self.design.surface_items), 3)

    def test_incremental_merge_keeps_unaffected_surface_reports_and_ownership(self):
        from cityg.geometry.incremental import merge_building_scene
        from cityg.geometry.model import LayerDefinition
        from cityg.planning import BaselineCityPlanner
        from cityg.schemas import CitySpec
        city = BaselineCityPlanner().plan(CitySpec(name="support_merge", width_m=180, depth_m=160,
            building_count=2, min_floors=1, max_floors=1, rooms_per_floor=4, seed=19))
        buildings = list(city.iter_buildings())
        rooms = [b.floors[0].rooms[0] for b in buildings]
        layers = [LayerDefinition(f"floor:{b.floors[0].id}", b.floors[0].id, "floor", "unused", "local")
                  for b in buildings]
        primitives = [self.compiler._box(f"child_{i}", b.floors[0].objects[0].id, Vec3(0,0,1), Vec3(.1,.1,.1), 0,
            "room_decoration", "ceramic", layers[i].id, metadata={"surface_subentity": True})
            for i, b in enumerate(buildings)]
        previous = GeometryScene(city.id, "z_up", primitives=primitives, layers=layers,
            building_prototypes={b.id: "prototype" for b in buildings},
            metadata={"room_surface_items": {rooms[0].id: {"placed": 1}, rooms[1].id: {"placed": 2}, "deleted": {"placed": 3}}})
        changed = replace(primitives[0], id="new_child")
        subset = GeometryScene(city.id, "z_up", primitives=[changed], layers=layers,
            building_prototypes={buildings[0].id: "new_prototype"},
            metadata={"room_surface_items": {rooms[0].id: {"placed": 4}}})
        merged, _ = merge_building_scene(city, previous, subset, {buildings[0].id})
        self.assertEqual(merged.metadata["room_surface_items"], {rooms[0].id: {"placed": 4}, rooms[1].id: {"placed": 2}})
        self.assertEqual({p.id for p in merged.primitives}, {"new_child", "child_1"})


if __name__ == "__main__":
    unittest.main()
