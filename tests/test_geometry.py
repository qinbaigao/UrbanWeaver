import math
from copy import deepcopy
import unittest

from cityg.geometry import GeometryCompiler, GeometryValidator
from cityg.planning import (
    BaselineCityPlanner,
    BuildingProfile,
    BuildingProgram,
    FloorProfile,
    FloorProgram,
    HierarchicalProgram,
    ProgrammedCityPlanner,
    UrbanProgram,
    VerticalFloorZone,
)
from cityg.runtime import (
    ActivationManager,
    InteractionRuntime,
    NavigationQuery,
    run_interaction_smoke,
)
from cityg.schemas import CitySpec, ZoneSpec
from cityg.serialization import to_primitive
from cityg.validation import CityValidator


class GeometryCompilerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.city = BaselineCityPlanner().plan(
            CitySpec(
                name="geometry_test",
                width_m=280,
                depth_m=240,
                building_count=4,
                min_floors=2,
                max_floors=2,
                rooms_per_floor=3,
                seed=12,
                zones=(
                    ZoneSpec("homes", "residential", 1),
                    ZoneSpec("offices", "commercial", 1),
                    ZoneSpec("factory", "industrial", 1),
                ),
            )
        )
        cls.scene = GeometryCompiler().compile(cls.city)

    def test_geometry_is_valid_and_deterministic(self):
        report = GeometryValidator().validate(self.city, self.scene)
        self.assertTrue(report.ok, report.to_dict())
        replay = GeometryCompiler().compile(self.city)
        self.assertEqual(to_primitive(self.scene), to_primitive(replay))
        self.assertEqual(report.metrics["outdoor_to_room_path_ratio"], 1.0)

    def test_leaf_fit_runs_after_conformance_without_changing_walls_or_openings(self):
        from unittest.mock import patch
        with patch('cityg.geometry.door_kinematics.fit_door_leaf', side_effect=lambda p:p):
            unfitted=GeometryCompiler().compile(self.city)
        original={p.id:p for p in unfitted.primitives}
        count=0
        for p in self.scene.primitives:
            before=original[p.id]
            if p.semantic_class=='door' and p.primitive_type=='box':
                count+=1
                self.assertEqual(p.center,before.center)
                self.assertEqual(p.rotation_z_deg,before.rotation_z_deg)
                self.assertEqual(p.metadata['aperture_size_m'],
                    [before.size.x,before.size.y,before.size.z])
                self.assertEqual(p.metadata['door_fit_version'],'corner_hinge_v1')
            else:
                self.assertEqual(p,before)
        self.assertGreater(count,0)
        self.assertEqual(unfitted.navigation,self.scene.navigation)
        self.assertEqual(unfitted.state_machines,self.scene.state_machines)

    def test_city_scale_shell_only_compile_is_valid_and_keeps_macro_layers(self):
        scene = GeometryCompiler(include_interiors=False).compile(self.city)
        report = GeometryValidator().validate(self.city, scene)
        self.assertTrue(report.ok, report.to_dict())
        self.assertFalse(scene.metadata["interiors_compiled"])
        self.assertTrue(any(item.semantic_class == "city_ground" for item in scene.primitives))
        self.assertTrue(any(item.semantic_class == "parcel_edge" for item in scene.primitives))
        self.assertIn("urban_morphology", self.city.metadata)
        self.assertIn("rendering_profile", scene.metadata)

    def test_three_building_prototypes_are_present(self):
        self.assertTrue(
            {"residential_slab", "commercial_tower", "industrial_hall"}.issubset(
                set(self.scene.building_prototypes.values())
            )
        )

    def test_required_geometry_and_physics_metadata_exist(self):
        semantics = {primitive.semantic_class for primitive in self.scene.primitives}
        self.assertTrue(
            {
                "road_surface",
                "sidewalk",
                "floor_slab",
                "exterior_wall",
                "interior_wall",
                "door",
                "stair_tread",
                "roof",
            }.issubset(semantics)
        )
        doors = [
            primitive
            for primitive in self.scene.primitives
            if primitive.body_type == "articulated"
        ]
        self.assertTrue(doors)
        self.assertTrue(all(item.metadata["mass_kg"] > 0 for item in doors))

    def test_facade_grammar_adds_visual_only_windows_and_frames(self):
        facade_semantics = {
            "facade_window",
            "storefront_window",
            "facade_frame",
            "facade_fin",
            "entrance_portal",
            "balcony_slab",
            "balcony_rail",
        }
        facade = [
            item
            for item in self.scene.primitives
            if item.semantic_class in facade_semantics
        ]
        self.assertTrue(facade)
        self.assertTrue(all(not item.collision_enabled for item in facade))
        self.assertTrue(
            {"facade_window", "facade_frame"}.issubset(
                {item.semantic_class for item in facade}
            )
        )
        report = GeometryValidator().validate(self.city, self.scene)
        self.assertGreater(report.metrics["facade_window_count"], 0)
        self.assertEqual(
            report.metrics["facade_primitive_count"],
            len(
                [
                    item
                    for item in self.scene.primitives
                    if item.semantic_class.startswith(
                        ("facade_", "storefront_", "balcony_")
                    )
                    or item.semantic_class == "entrance_portal"
                ]
            ),
        )

    def test_entrance_and_canopy_share_one_realized_facade_anchor(self):
        entrances_by_building = {}
        for primitive in self.scene.primitives:
            if primitive.semantic_class not in {
                "entrance_portal",
                "facade_asset_entrance",
            }:
                continue
            building_id = primitive.metadata.get("building_id")
            entrances_by_building.setdefault(building_id, []).append(primitive)

        self.assertEqual(
            set(entrances_by_building),
            {building.id for building in self.city.iter_buildings()},
        )
        self.assertTrue(
            all(len(entrances) == 1 for entrances in entrances_by_building.values())
        )

        canopies = [
            primitive
            for primitive in self.scene.primitives
            if primitive.semantic_class == "entrance_canopy"
        ]
        self.assertTrue(canopies)
        for canopy in canopies:
            entrance = entrances_by_building[canopy.metadata["building_id"]][0]
            self.assertEqual(
                canopy.metadata["entrance_anchor_id"],
                entrance.metadata["entrance_anchor_id"],
            )
            self.assertAlmostEqual(
                canopy.metadata["entrance_anchor_tangent_m"],
                entrance.metadata["entrance_anchor_tangent_m"],
            )
            self.assertTrue(canopy.metadata["aligned_to_facade_entry"])

    def test_furnishings_compile_as_collision_aware_massing_fitted_proxies(self):
        objects = {item.id for item in self.city.iter_objects()}
        furniture = [
            item
            for item in self.scene.primitives
            if item.semantic_class.startswith("furniture_")
        ]
        self.assertTrue(objects)
        self.assertEqual({item.owner_id for item in furniture}, objects)
        self.assertTrue(all(item.collision_enabled for item in furniture))
        self.assertTrue(all(item.metadata.get("massing_fitted") for item in furniture))
        semantics = {item.semantic_class for item in furniture}
        self.assertTrue(
            {"furniture_table", "furniture_seating", "furniture_storage"}.issubset(
                semantics
            )
        )
        report = GeometryValidator().validate(self.city, self.scene)
        self.assertEqual(report.metrics["furnished_room_ratio"], 1.0)
        self.assertEqual(report.metrics["furnishing_object_count"], len(objects))
        self.assertEqual(
            report.metrics["furnishing_primitive_count"],
            report.metrics["massing_fitted_furnishing_primitive_count"],
        )

    def test_complete_door_panels_fit_inside_realized_massing(self):
        """Door thickness must not protrude at setbacks or concave corners."""

        buildings = {building.id: building for building in self.city.iter_buildings()}
        for door in [item for item in self.scene.primitives if item.semantic_class == "door"]:
            building = next(
                candidate
                for candidate in buildings.values()
                if door.owner_id
                in {item.id for floor in candidate.floors for item in floor.doors}
            )
            frame = GeometryCompiler._massing_frame(building)
            angle = math.radians(frame["rotation"])
            dx = door.center.x - building.footprint.center.x
            dy = door.center.y - building.footprint.center.y
            local_x = dx * math.cos(angle) + dy * math.sin(angle)
            local_y = -dx * math.sin(angle) + dy * math.cos(angle)
            corners = [
                (local_x + sx * door.size.x / 2, local_y + sy * door.size.y / 2)
                for sx in (-1, 1)
                for sy in (-1, 1)
            ]
            self.assertTrue(
                any(
                    all(
                        GeometryCompiler._point_in_part(x, y, part, tolerance=1e-5)
                        for x, y in corners
                    )
                    for part in frame["parts"]
                ),
                door.id,
            )

    def test_setback_roofs_stop_complete_floor_details_from_protruding(self):
        """A stepped roof must never cut through doors, headers, or walls."""

        city = BaselineCityPlanner().plan(
            CitySpec(
                name="setback_roof_floor_alignment",
                width_m=150,
                depth_m=150,
                building_count=1,
                min_floors=4,
                max_floors=4,
                rooms_per_floor=5,
                seed=31,
                zones=(ZoneSpec("homes", "residential", 1.0),),
            )
        )
        building = next(city.iter_buildings())
        building.metadata["massing_style"] = "t_shape"
        building.metadata["orientation_deg"] = 17.0
        scene = GeometryCompiler().compile(city)
        frame = GeometryCompiler._massing_frame(building)
        building_top = max(
            floor.elevation_m + floor.height_m for floor in building.floors
        )
        floor_tops = {
            round(floor.elevation_m + floor.height_m, 6)
            for floor in building.floors
        }
        part_tops = {
            round(building_top * part["height_scale"], 6)
            for part in frame["parts"]
        }
        self.assertTrue(part_tops.issubset(floor_tops))
        self.assertTrue(any(top < round(building_top, 6) for top in part_tops))

        floor_by_layer = {
            f"floor:{floor.id}": floor for floor in building.floors
        }
        inspected = [
            primitive
            for primitive in scene.primitives
            if primitive.layer_id in floor_by_layer
            and (
                primitive.semantic_class == "door"
                or (
                    primitive.semantic_class == "interior_wall"
                    and not primitive.metadata.get("viewer_room_only")
                )
                or primitive.semantic_class.startswith("furniture_")
            )
        ]
        self.assertTrue(inspected)
        angle = math.radians(frame["rotation"])
        cos_angle = math.cos(angle)
        sin_angle = math.sin(angle)
        for primitive in inspected:
            floor = floor_by_layer[primitive.layer_id]
            dx = primitive.center.x - building.footprint.center.x
            dy = primitive.center.y - building.footprint.center.y
            local_x = dx * cos_angle + dy * sin_angle
            local_y = -dx * sin_angle + dy * cos_angle
            corners = [
                (
                    local_x + sx * primitive.size.x / 2,
                    local_y + sy * primitive.size.y / 2,
                )
                for sx in (-1, 1)
                for sy in (-1, 1)
            ]
            primitive_top = primitive.center.z + primitive.size.z / 2
            # Doors and their headers form one complete opening, so the
            # selected massing tier must support the whole floor ceiling.
            required_top = (
                floor.elevation_m + floor.height_m
                if primitive.semantic_class == "door"
                or primitive.metadata.get("wall_role") == "door_header"
                else primitive_top
            )
            self.assertTrue(
                any(
                    building_top * part["height_scale"] + 1e-5 >= required_top
                    and all(
                        GeometryCompiler._point_in_part(
                            x, y, part, tolerance=0.04
                        )
                        for x, y in corners
                    )
                    for part in frame["parts"]
                ),
                primitive.id,
            )

    def test_visual_massing_and_landscape_compile_without_replacing_collision_core(self):
        city = BaselineCityPlanner().plan(
            CitySpec(
                name="massing_landscape",
                width_m=360,
                depth_m=300,
                building_count=8,
                min_floors=2,
                max_floors=3,
                rooms_per_floor=3,
                seed=19,
            )
        )
        scene = GeometryCompiler().compile(city)
        report = GeometryValidator().validate(city, scene)
        self.assertTrue(report.ok, report.to_dict())
        semantics = {item.semantic_class for item in scene.primitives}
        self.assertTrue(
            {
                "collision_envelope",
                "exterior_wall",
                "grass",
                "landscape_path",
                "tree_trunk",
                "tree_canopy",
                "bench",
                "street_light",
            }.issubset(semantics)
        )
        visual_walls = [
            item for item in scene.primitives if item.semantic_class == "exterior_wall"
        ]
        proxies = [
            item for item in scene.primitives if item.semantic_class == "collision_envelope"
        ]
        self.assertTrue(any(item.rotation_z_deg != 0 for item in visual_walls))
        self.assertTrue(all(not item.collision_enabled for item in visual_walls))
        self.assertTrue(proxies)
        self.assertTrue(all(item.collision_enabled for item in proxies))

        building_ids = {building.id for building in city.iter_buildings()}
        whole_building_massing = [
            item
            for item in scene.primitives
            if item.semantic_class == "exterior_wall"
            and "_massing_" in item.id
        ]
        self.assertTrue(whole_building_massing)
        self.assertTrue(
            all(item.owner_id in building_ids for item in whole_building_massing)
        )

        floor_to_building = {
            floor.id: building
            for building in city.iter_buildings()
            for floor in building.floors
        }
        clipped_walls = [
            item for item in scene.primitives if item.semantic_class == "interior_wall"
        ]
        self.assertTrue(clipped_walls)
        self.assertTrue(
            all(item.metadata.get("massing_clipped") for item in clipped_walls)
        )
        for wall in clipped_walls:
            building = floor_to_building[wall.owner_id]
            frame = GeometryCompiler._massing_frame(building)
            angle = math.radians(frame["rotation"])
            dx = wall.center.x - building.footprint.center.x
            dy = wall.center.y - building.footprint.center.y
            local_x = dx * math.cos(angle) + dy * math.sin(angle)
            local_y = -dx * math.sin(angle) + dy * math.cos(angle)
            corners = [
                (local_x + sx * wall.size.x / 2, local_y + sy * wall.size.y / 2)
                for sx in (-1, 1)
                for sy in (-1, 1)
            ]
            self.assertTrue(
                any(
                    all(
                        GeometryCompiler._point_in_part(x, y, part, tolerance=1e-5)
                        for x, y in corners
                    )
                    for part in frame["parts"]
                )
            )

        detail_semantics = {"door", "stair_tread"}
        conformed_details = [
            item for item in scene.primitives if item.semantic_class in detail_semantics
        ]
        self.assertTrue(conformed_details)
        self.assertTrue(
            all(item.metadata.get("massing_conformed") for item in conformed_details)
        )

    def test_navigation_respects_closed_doors_and_interaction(self):
        query = NavigationQuery(self.scene.navigation)
        runtime = InteractionRuntime(self.scene.state_machines)
        outdoor = next(
            node.id for node in self.scene.navigation.nodes if node.node_type == "outdoor_junction"
        )
        room = next(
            node.id for node in self.scene.navigation.nodes if node.node_type == "room"
        )
        self.assertIsNone(
            query.shortest_path(
                outdoor, room, runtime=runtime, allow_interaction=False
            )
        )
        self.assertIsNotNone(query.shortest_path(outdoor, room, allow_interaction=True))
        for machine_id in runtime.machines:
            runtime.trigger(machine_id, "open")
        for _ in range(8):
            runtime.step(0.1)
        self.assertIsNotNone(
            query.shortest_path(
                outdoor, room, runtime=runtime, allow_interaction=False
            )
        )

    def test_interaction_persistence_and_activation(self):
        self.assertTrue(run_interaction_smoke(self.scene).ok)
        manager = ActivationManager(self.scene)
        building = next(self.city.iter_buildings())
        floor = building.floors[0]
        overview = manager.select("overview")
        active_floor = manager.select(
            "active_floor", building_id=building.id, floor_id=floor.id
        )
        self.assertGreater(
            manager.primitive_count(active_floor), manager.primitive_count(overview)
        )

    def test_programmed_prototype_override_reaches_geometry(self):
        spec = CitySpec(
            name="prototype_override",
            width_m=160,
            depth_m=160,
            building_count=1,
            min_floors=1,
            max_floors=1,
            rooms_per_floor=2,
            zones=(ZoneSpec("experimental", "residential", 1),),
        )
        program = HierarchicalProgram(
            UrbanProgram(("zone_00",)),
            BuildingProgram(
                (
                    BuildingProfile(
                        "residential", "minimum", "west", "public_civic"
                    ),
                )
            ),
            FloorProgram(
                (
                    FloorProfile(
                        "residential",
                        "double_loaded_corridor",
                        0.18,
                        ("living_room", "bedroom"),
                    ),
                )
            ),
        )
        city = ProgrammedCityPlanner(program).plan(spec)
        scene = GeometryCompiler().compile(city)
        self.assertEqual(scene.building_prototypes["building_000"], "public_civic")

    def test_building_specific_vertical_zones_reach_floor_metadata(self):
        spec = CitySpec(
            name="vertical_zone_override",
            width_m=180,
            depth_m=160,
            building_count=1,
            min_floors=8,
            max_floors=8,
            rooms_per_floor=3,
            zones=(ZoneSpec("tower", "residential", 1),),
        )
        base = FloorProfile(
            "residential", "double_loaded_corridor", 0.18,
            ("living_room", "bedroom", "kitchen", "bathroom"),
        )
        program = HierarchicalProgram(
            UrbanProgram(("zone_00",)),
            BuildingProgram((BuildingProfile("residential", "minimum", "west", "residential_slab"),)),
            FloorProgram((base,)),
        )

        def zone(zone_id, start, end, role, use_type, preferred, cycle):
            return VerticalFloorZone(
                zone_id, start, end, role, use_type,
                preferred, max(1, preferred - 2), min(32, preferred + 2),
                24.0, 2.8, cycle, 4,
            )

        override = FloorProfile(
            "residential", "double_loaded_corridor", 0.18,
            ("living_room", "bedroom", "kitchen", "bathroom"),
            (),
            (
                zone("ground_lobby", 0, 0, "ground", "entrance", 3, ("reception", "storage")),
                zone("shared_podium", 1, 2, "podium", "amenity", 5, ("living_room", "kitchen", "restroom")),
                zone("residential_lower", 3, 5, "typical", "residential", 14, ("living_room", "bedroom", "kitchen", "bathroom")),
                zone("sky_amenity", 6, 6, "amenity", "amenity", 4, ("living_room", "study", "restroom")),
                zone("top_residential", 7, 7, "top", "residential", 8, ("living_room", "bedroom", "bathroom")),
            ),
        )
        city = ProgrammedCityPlanner(
            program, floor_program_overrides={"building_000": override}
        ).plan(spec)
        building = next(city.iter_buildings())
        self.assertEqual(
            [floor.metadata["vertical_zone_id"] for floor in building.floors],
            [
                "ground_lobby", "shared_podium", "shared_podium",
                "residential_lower", "residential_lower", "residential_lower",
                "sky_amenity", "top_residential",
            ],
        )
        self.assertEqual(building.floors[6].metadata["vertical_role"], "amenity")
        self.assertEqual(
            building.metadata["vertical_zoning"]["source"],
            "building_specific_floor_agent_v1",
        )
        self.assertTrue(CityValidator().validate(city).ok)


class HighRiseGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.city = BaselineCityPlanner().plan(
            CitySpec(
                name="highrise_geometry",
                width_m=180,
                depth_m=160,
                building_count=1,
                min_floors=10,
                max_floors=10,
                rooms_per_floor=2,
                seed=44,
                zones=(ZoneSpec("core", "commercial", 1.0),),
                height_strategy="uniform_random",
            )
        )
        cls.scene = GeometryCompiler().compile(cls.city)

    def test_highrise_geometry_navigation_and_interaction_close_the_loop(self):
        self.assertTrue(CityValidator().validate(self.city).ok)
        report = GeometryValidator().validate(self.city, self.scene)
        self.assertTrue(report.ok, report.to_dict())
        semantics = {item.semantic_class for item in self.scene.primitives}
        self.assertTrue(
            {"elevator_shaft", "elevator_cabin", "elevator_landing_door"}.issubset(
                semantics
            )
        )
        elevators = [
            item
            for item in self.scene.state_machines
            if item.state_type == "elevator_controller"
        ]
        self.assertEqual(len(elevators), 1)
        self.assertEqual(len(elevators[0].states), 10)
        self.assertTrue(
            any(item.traversal == "elevator" for item in self.scene.navigation.edges)
        )
        self.assertTrue(run_interaction_smoke(self.scene).ok)

    def test_controlled_highrise_variants_preserve_full_height_tower(self):
        building = next(self.city.iter_buildings())
        expected_part_counts = {
            "standard": 2,
            "setback": 3,
            "offset": 2,
            "slender_landmark": 3,
        }
        signatures = set()
        for variant, expected_count in expected_part_counts.items():
            candidate = deepcopy(building)
            candidate.metadata["highrise"]["massing_variant"] = variant
            parts = GeometryCompiler._massing_parts(candidate)
            self.assertEqual(len(parts), expected_count)
            full_height = [part for part in parts if part["height_scale"] == 1.0]
            self.assertEqual(len(full_height), 1)
            signatures.add(
                tuple(
                    (round(part["width"], 3), round(part["depth"], 3))
                    for part in parts
                )
            )
        self.assertEqual(len(signatures), len(expected_part_counts))

    def test_roof_details_anchor_to_highest_massing_part(self):
        """Tower/podium roof details must not float over the low podium."""
        spec = CitySpec(
            name="roof_detail_anchor",
            width_m=180,
            depth_m=160,
            building_count=1,
            min_floors=12,
            max_floors=12,
            rooms_per_floor=4,
            seed=44,
            zones=(ZoneSpec("core", "commercial", 1.0),),
            height_strategy="uniform_random",
        )
        profile = FloorProfile(
            "commercial",
            "double_loaded_corridor",
            0.18,
            ("office", "meeting_room", "restroom", "storage"),
        )
        program = HierarchicalProgram(
            UrbanProgram(("zone_00",)),
            BuildingProgram(
                (BuildingProfile("commercial", "minimum", "west", "commercial_tower"),)
            ),
            FloorProgram((profile,)),
        )
        city = ProgrammedCityPlanner(program).plan(spec)
        building = next(city.iter_buildings())
        scene = GeometryCompiler().compile(city)
        highest = max(
            GeometryCompiler._massing_parts(building),
            key=lambda part: float(part["height_scale"]),
        )
        details = [
            item
            for item in scene.primitives
            if item.owner_id == building.id
            and item.semantic_class in {"mechanical_roof", "roof_equipment", "roof_monitor"}
        ]
        self.assertTrue(details)
        for item in details:
            self.assertAlmostEqual(item.center.x, highest["center_x"], places=6)
            self.assertAlmostEqual(item.center.y, highest["center_y"], places=6)

    def test_programmed_highrise_walls_follow_realized_room_boundaries(self):
        spec = CitySpec(
            name="realized_highrise_walls",
            width_m=180,
            depth_m=160,
            building_count=1,
            min_floors=18,
            max_floors=18,
            rooms_per_floor=10,
            seed=44,
            zones=(ZoneSpec("core", "commercial", 1.0),),
            height_strategy="uniform_random",
        )
        profile = FloorProfile(
            "commercial",
            "double_loaded_corridor",
            0.18,
            ("office", "meeting_room", "restroom", "storage"),
        )
        program = HierarchicalProgram(
            UrbanProgram(("zone_00",)),
            BuildingProgram(
                (BuildingProfile("commercial", "minimum", "west", "commercial_tower"),)
            ),
            FloorProgram((profile,)),
        )
        city = ProgrammedCityPlanner(program).plan(spec)
        scene = GeometryCompiler().compile(city)
        building = next(city.iter_buildings())
        floor = building.floors[11]
        rooms = [room for room in floor.rooms if room.function != "corridor"]
        self.assertTrue(rooms)
        for room in rooms:
            walls = [
                primitive
                for primitive in scene.primitives
                if primitive.semantic_class == "interior_wall"
                and room.id in primitive.metadata.get("room_ids", [])
            ]
            self.assertTrue(walls, room.id)
            for boundary in (room.bounds.min_y, room.bounds.max_y):
                horizontal = [
                    wall
                    for wall in walls
                    if wall.size.x >= wall.size.y
                    and abs(wall.metadata.get("canonical_boundary", 1e9) - boundary)
                    <= 1e-5
                ]
                self.assertTrue(horizontal, (room.id, boundary))
                self.assertTrue(
                    all(
                        abs(wall.center.y - boundary)
                        <= wall.size.y / 2 + 1e-5
                        for wall in horizontal
                    ),
                    (room.id, boundary),
                )
            for boundary in (room.bounds.min_x, room.bounds.max_x):
                vertical = [
                    wall
                    for wall in walls
                    if wall.size.y >= wall.size.x
                    and abs(wall.metadata.get("canonical_boundary", 1e9) - boundary)
                    <= 1e-5
                ]
                self.assertTrue(vertical, (room.id, boundary))
                self.assertTrue(
                    all(
                        abs(wall.center.x - boundary)
                        <= wall.size.x / 2 + 1e-5
                        for wall in vertical
                    ),
                    (room.id, boundary),
                )
            # Adjacent wall segments must reach the room corners.  Door
            # openings may create an interior gap along a side, but they must
            # not cause the two orthogonal wall runs to be independently
            # trimmed at their endpoints.
            for boundary in (room.bounds.min_y, room.bounds.max_y):
                horizontal = [
                    wall
                    for wall in walls
                    if wall.size.x >= wall.size.y
                    and abs(wall.metadata.get("canonical_boundary", 1e9) - boundary)
                    <= 1e-5
                ]
                if horizontal:
                    self.assertLessEqual(
                        min(w.center.x - w.size.x / 2 for w in horizontal),
                        room.bounds.min_x + 1e-5,
                        (room.id, boundary, "left corner"),
                    )
                    self.assertGreaterEqual(
                        max(w.center.x + w.size.x / 2 for w in horizontal),
                        room.bounds.max_x - 1e-5,
                        (room.id, boundary, "right corner"),
                    )
            for boundary in (room.bounds.min_x, room.bounds.max_x):
                vertical = [
                    wall
                    for wall in walls
                    if wall.size.y >= wall.size.x
                    and abs(wall.metadata.get("canonical_boundary", 1e9) - boundary)
                    <= 1e-5
                ]
                if vertical:
                    self.assertLessEqual(
                        min(w.center.y - w.size.y / 2 for w in vertical),
                        room.bounds.min_y + 1e-5,
                        (room.id, boundary, "lower corner"),
                    )
                    self.assertGreaterEqual(
                        max(w.center.y + w.size.y / 2 for w in vertical),
                        room.bounds.max_y - 1e-5,
                        (room.id, boundary, "upper corner"),
                    )
            # Doors and furnishings remain in the metric floor-plate frame;
            # they must not be remapped through the larger building footprint.
            room_doors = [
                door for door in floor.doors
                if room.id in {door.room_a_id, door.room_b_id}
            ]
            for door in room_doors:
                matches = [
                    primitive for primitive in scene.primitives
                    if primitive.semantic_class == "door"
                    and primitive.owner_id == door.id
                ]
                self.assertTrue(matches, door.id)
                self.assertTrue(
                    any(
                        abs(primitive.center.x - door.position.x) <= 1e-5
                        and abs(primitive.center.y - door.position.y) <= 1e-5
                        for primitive in matches
                    ),
                    door.id,
                )
            object_ids = set(room.object_ids)
            for primitive in scene.primitives:
                if primitive.layer_id != f"floor:{floor.id}" or primitive.owner_id not in object_ids:
                    continue
                # Component proxies carry their canonical object center and
                # offset; all components should remain inside the room bounds.
                self.assertGreaterEqual(primitive.center.x, room.bounds.min_x - 1e-5)
                self.assertLessEqual(primitive.center.x, room.bounds.max_x + 1e-5)
                self.assertGreaterEqual(primitive.center.y, room.bounds.min_y - 1e-5)
                self.assertLessEqual(primitive.center.y, room.bounds.max_y + 1e-5)
        report = GeometryValidator().validate(city, scene)
        self.assertTrue(report.ok, report.to_dict())


if __name__ == "__main__":
    unittest.main()
