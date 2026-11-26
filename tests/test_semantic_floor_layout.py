import unittest

from cityg.geometry import GeometryCompiler
from cityg.planning import ProgrammedCityPlanner
from cityg.planning import BaselineCityPlanner
from cityg.planning.programs import FloorArchetype
from cityg.schemas import Bounds2D, CitySpec, Door, Point2D, Room


class SemanticFloorLayoutTests(unittest.TestCase):
    def setUp(self):
        self.archetype = FloorArchetype(
            role="typical",
            preferred_room_count=8,
            min_room_count=4,
            max_room_count=12,
            target_room_area_m2=24.0,
            min_room_width_m=3.0,
            room_function_cycle=("office", "open_office"),
            unit_group_size=1,
            max_room_depth_m=12.0,
            max_room_aspect_ratio=2.4,
            layout_template="office_core",
        )

    def test_function_and_role_select_semantic_templates(self):
        self.assertEqual(
            ProgrammedCityPlanner._layout_template(
                "commercial", "ground", self.archetype
            ),
            "office_core",
        )
        auto = FloorArchetype(
            role="typical",
            preferred_room_count=8,
            min_room_count=4,
            max_room_count=12,
            target_room_area_m2=24.0,
            min_room_width_m=3.0,
            room_function_cycle=("living_room", "bedroom"),
        )
        self.assertEqual(
            ProgrammedCityPlanner._layout_template("residential", "typical", auto),
            "residential_units",
        )
        self.assertEqual(
            ProgrammedCityPlanner._layout_template("commercial", "podium", auto),
            "podium_core",
        )

    def test_oversized_enclosed_room_is_split(self):
        room = Room(
            "room",
            "Office",
            "office",
            Bounds2D(0.0, 0.0, 30.0, 8.0),
            metadata={"space_kind": "enclosed_room"},
        )
        corridor = Room(
            "corridor",
            "Corridor",
            "corridor",
            Bounds2D(0.0, -3.0, 30.0, 0.0),
        )
        door = Door("door", "room", "corridor", Point2D(15.0, 0.0))
        rooms, doors, stats = ProgrammedCityPlanner._split_oversized_rooms(
            "floor", [corridor, room], [door], self.archetype
        )
        parts = [item for item in rooms if item.function != "corridor"]
        self.assertGreater(len(parts), 1)
        self.assertEqual(stats["split_source_room_count"], 1)
        self.assertTrue(
            all(item.metadata["large_space_policy"] == "split_enclosed_space" for item in parts)
        )
        self.assertTrue(all(any(door.room_a_id == item.id for door in doors) for item in parts))

    def test_oversized_open_plan_is_preserved_and_marked(self):
        room = Room(
            "open",
            "Open Office",
            "open_office",
            Bounds2D(0.0, 0.0, 30.0, 8.0),
            metadata={"space_kind": "open_plan", "open_plan": True},
        )
        rooms, _, stats = ProgrammedCityPlanner._split_oversized_rooms(
            "floor", [room], [], self.archetype
        )
        self.assertEqual(len(rooms), 1)
        self.assertEqual(stats["preserved_open_space_count"], 1)
        self.assertEqual(rooms[0].metadata["large_space_policy"], "preserve_as_open_plan")
        self.assertGreater(rooms[0].metadata["nominal_capacity_zones"], 1)

    def test_compiled_interior_walls_bind_to_rooms(self):
        city = BaselineCityPlanner().plan(
            CitySpec(name="room_wall_binding", building_count=1, min_floors=1, max_floors=1)
        )
        scene = GeometryCompiler().compile(city)
        walls = [item for item in scene.primitives if item.semantic_class == "interior_wall"]
        self.assertTrue(walls)
        self.assertTrue(any(item.metadata.get("room_ids") for item in walls))

    def test_corridor_wall_ownership_is_split_at_room_boundaries(self):
        city = BaselineCityPlanner().plan(
            CitySpec(
                name="room_wall_spatial_binding",
                building_count=1,
                min_floors=1,
                max_floors=1,
                rooms_per_floor=8,
            )
        )
        scene = GeometryCompiler().compile(city)
        rooms = {room.id: room for room in city.iter_rooms()}
        walls = [
            item
            for item in scene.primitives
            if item.semantic_class == "interior_wall"
            and item.metadata.get("wall_role") == "corridor_boundary"
        ]
        self.assertTrue(walls)
        for wall in walls:
            room_ids = wall.metadata["room_ids"]
            non_corridor_ids = [
                room_id
                for room_id in room_ids
                if rooms[room_id].function != "corridor"
            ]
            self.assertLessEqual(len(non_corridor_ids), 1)
            span_start, span_end = wall.metadata["canonical_span"]
            for room_id in non_corridor_ids:
                bounds = rooms[room_id].bounds
                self.assertGreaterEqual(span_start, bounds.min_x - 1e-5)
                self.assertLessEqual(span_end, bounds.max_x + 1e-5)

    def test_exterior_room_boundaries_are_isolated_viewer_geometry(self):
        city = BaselineCityPlanner().plan(
            CitySpec(
                name="room_exterior_wall_binding",
                building_count=1,
                min_floors=1,
                max_floors=1,
                rooms_per_floor=6,
            )
        )
        scene = GeometryCompiler().compile(city)
        boundaries = [
            item
            for item in scene.primitives
            if item.metadata.get("wall_role") == "room_exterior_boundary"
        ]
        self.assertTrue(boundaries)
        self.assertTrue(all(len(item.metadata["room_ids"]) == 1 for item in boundaries))
        self.assertTrue(all(item.metadata.get("viewer_room_only") for item in boundaries))
        self.assertTrue(all(not item.collision_enabled for item in boundaries))


if __name__ == "__main__":
    unittest.main()
