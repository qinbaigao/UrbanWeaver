import unittest
from dataclasses import asdict, replace

from cityg.planning.spatial_program import FloorSpatialProgram, SpaceRequirement
from cityg.planning.spatial_layout import solve_spatial_floor, shared_boundary, SpatialLayoutInfeasible
from cityg.planning.programs import FloorArchetype, FloorProfile, VerticalFloorZone
from cityg.planning.programmed import ProgrammedCityPlanner
from cityg.planning.baseline import BaselineCityPlanner
from cityg.schemas import Bounds2D, Point2D, CitySpec
from cityg.geometry import GeometryCompiler


def sample_program(family):
    if family == "double_loaded":
        spaces = [SpaceRequirement(f"office_{i}", "office", area, 18, 150)
                  for i, area in enumerate((24, 42, 65, 32, 50, 75))]
    elif family == "residential_clusters":
        spaces = []
        for i in range(4):
            key = f"unit_{i}"
            spaces += [SpaceRequirement(key+"_living", "living_room", 45, 20, 100, group=key),
                       SpaceRequirement(key+"_bed", "bedroom", 28, 12, 70, group=key, access_via=key+"_living", daylight="required"),
                       SpaceRequirement(key+"_bath", "bathroom", 20, 8, 65, group=key, access_via=key+"_living", daylight="none")]
    else:
        spaces = []
        for i in range(2):
            key = f"team_{i}"
            spaces.append(SpaceRequirement(key, "open_office", 110, 50, 250, capacity=12, group=key, enclosure="open"))
            for j, area in enumerate((30, 45, 35)):
                spaces.append(SpaceRequirement(f"{key}_support_{j}", "office", area, 15, 90, group=key, access_via=key))
    return FloorSpatialProgram(family, tuple(spaces))


def solve(program, **kwargs):
    args = dict(floor_id="test_floor_00", level=0, height=3.2,
                footprint=Bounds2D(0, 0, 24, 22), corridor_depth=3,
                core_bounds=Bounds2D(10, 9.5, 14, 12.5), entrance=Point2D(0, 11),
                min_width=2.4, max_aspect=2.8, max_depth=12)
    args.update(kwargs)
    return solve_spatial_floor(program, **args)


class SpatialFloorTests(unittest.TestCase):
    def test_all_families_geometry_access_and_unequal_areas(self):
        for family in ("double_loaded", "residential_clusters", "open_office"):
            with self.subTest(family=family):
                floor = solve(sample_program(family))
                rooms = {r.id: r for r in floor.rooms}
                self.assertEqual(floor.metadata["spatial_layout"]["status"], "accepted")
                self.assertAlmostEqual(sum(r.bounds.area for r in floor.rooms), 24*22)
                areas = {round(r.bounds.area, 1) for r in floor.rooms if r.function != "corridor"}
                self.assertGreater(len(areas), 1)
                for door in floor.doors:
                    if door.room_b_id:
                        edge = shared_boundary(rooms[door.room_a_id].bounds, rooms[door.room_b_id].bounds)
                        self.assertIsNotNone(edge)
                        self.assertGreater(edge[3]-edge[2], door.width_m+.5)

    def test_residential_private_rooms_do_not_open_to_public_corridor(self):
        floor = solve(sample_program("residential_clusters"))
        rooms = {r.id: r for r in floor.rooms}
        for door in floor.doors:
            if rooms[door.room_a_id].function in {"bedroom", "bathroom"}:
                self.assertEqual(rooms[door.room_b_id].function, "living_room")

    def test_merged_requirements_preserve_bindings(self):
        program = sample_program("double_loaded")
        spaces = list(program.spaces)
        spaces[0] = replace(spaces[0], merge_with=(spaces[1].key,))
        floor = solve(replace(program, spaces=tuple(spaces)))
        report = floor.metadata["spatial_layout"]
        self.assertEqual(report["bindings"][spaces[0].key], report["bindings"][spaces[1].key])
        self.assertEqual(report["realized_room_count"], 5)
        self.assertEqual(report["merged_space_count"], 1)

    def test_contract_roundtrip_and_validation(self):
        program = sample_program("residential_clusters")
        self.assertEqual(FloorSpatialProgram.from_dict(asdict(program)), program)
        archetype = FloorArchetype("typical", 12, 8, 16, 35, 2.4,
                                  ("living_room", "bedroom", "bathroom"), spatial_program=program)
        profile = FloorProfile("residential", "residential_units", .15,
                               archetype.room_function_cycle, (archetype,))
        restored = FloorProfile.from_dict(asdict(profile))
        self.assertEqual(restored.space_archetypes[0].spatial_program, program)
        zone = VerticalFloorZone("homes", 1, 4, "typical", "residential", 12, 8, 16, 35, 2.4,
                                 archetype.room_function_cycle, spatial_program=program)
        self.assertEqual(VerticalFloorZone.from_dict(asdict(zone), "residential").archetype.spatial_program, program)

    def test_bad_references_cycles_and_nonfinite_rejected(self):
        program = sample_program("double_loaded")
        for changes in ({"access_via": "missing"}, {"target_area_m2": float("nan")},
                        {"capacity": 1.5}, {"near_entrance": "yes"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(program, spaces=(replace(program.spaces[0], **changes), *program.spaces[1:])).validate()
        with self.assertRaises(ValueError):
            FloorSpatialProgram("double_loaded", (
                SpaceRequirement("a", "office", 20, access_via="b"),
                SpaceRequirement("b", "office", 20, access_via="a"))).validate()

    def test_infeasible_not_silently_relaxed(self):
        with self.assertRaises(SpatialLayoutInfeasible):
            solve(sample_program("residential_clusters"), footprint=Bounds2D(0,0,6,6),
                  core_bounds=None, entrance=Point2D(0,3))
        spaces = tuple(replace(s, min_area_m2=500, target_area_m2=500, max_area_m2=600)
                       for s in sample_program("double_loaded").spaces)
        with self.assertRaises(SpatialLayoutInfeasible):
            solve(FloorSpatialProgram("double_loaded", spaces))

    def test_core_preserved_reproducible_and_non_equal_bands(self):
        program = sample_program("double_loaded")
        floor = solve(program)
        self.assertEqual(asdict(floor), asdict(solve(program)))
        self.assertTrue(floor.rooms[0].bounds.contains_bounds(Bounds2D(10,9.5,14,12.5)))
        targets = {s.key: s.target_area_m2 for s in program.spaces}
        ratios = [r.bounds.area/targets[r.metadata["space_requirement_keys"][0]]
                  for r in floor.rooms[1:]]
        self.assertLess(max(ratios)/min(ratios), 1.6)

    def test_required_adjacency_and_separation_are_checked(self):
        p = sample_program("double_loaded")
        spaces = list(p.spaces)
        spaces[0] = replace(spaces[0], adjacent_to=(spaces[1].key,))
        floor = solve(replace(p, spaces=tuple(spaces)))
        bind = floor.metadata["spatial_layout"]["bindings"]
        rooms = {r.id:r for r in floor.rooms}
        self.assertIsNotNone(shared_boundary(rooms[bind[spaces[0].key]].bounds, rooms[bind[spaces[1].key]].bounds))
        spaces[0] = replace(spaces[0], separate_from=("circulation",))
        with self.assertRaises(SpatialLayoutInfeasible):
            solve(replace(p, spaces=tuple(spaces)))

    def test_invalid_downstream_access_reference_is_value_error(self):
        with self.assertRaises(ValueError):
            FloorSpatialProgram("open_office", (
                SpaceRequirement("a", "office", 20, access_via="b"),
                SpaceRequirement("b", "office", 20, access_via="missing"))).validate()

    def test_planner_transaction_and_reported_fallback(self):
        planner = object.__new__(ProgrammedCityPlanner)
        planner.floor_height_m = 3.2
        a = FloorArchetype("typical", 6, 4, 12, 40, 2.4, ("office",),
                           spatial_program=sample_program("double_loaded"))
        kwargs = dict(building_function="commercial", program_role="typical", archetype=a)
        floor = planner._make_programmed_floor("b", 1, Bounds2D(0,0,24,22), .15,
                                               ("office",), 6, Point2D(0,11), **kwargs)
        self.assertEqual(floor.metadata["spatial_layout"]["status"], "accepted")
        floor = planner._make_programmed_floor("b", 1, Bounds2D(0,0,8,8), .15,
                                               ("office",), 6, Point2D(0,4), **kwargs)
        self.assertEqual(floor.metadata["spatial_layout"]["status"], "fallback")
        self.assertFalse(floor.metadata["spatial_layout"]["requirements_satisfied"])
        floor = planner._make_programmed_floor("b", 1, Bounds2D(0,0,24,22), .15,
                                               ("office",), 6, Point2D(0,11),
                                               floor_plate_contract={"spatial_footprint_supported": False}, **kwargs)
        self.assertEqual(floor.metadata["spatial_layout"]["status"], "fallback")

    def test_fixed_count_not_silently_replaced(self):
        planner = object.__new__(ProgrammedCityPlanner)
        planner.floor_height_m = 3.2
        a = FloorArchetype("typical", 6, 4, 12, 40, 2.4, ("office",),
                           spatial_program=sample_program("double_loaded"))
        floor = planner._make_programmed_floor("b", 1, Bounds2D(0,0,24,22), .15,
                                               ("office",), 4, Point2D(0,11),
                                               building_function="commercial", program_role="typical", archetype=a,
                                               space_contract={"source":"fixed_rooms_per_floor"})
        self.assertEqual(floor.metadata["spatial_layout"]["status"], "fallback")

    def test_agent_coercion_keeps_spatial_program(self):
        from cityg.agents.building_floor import BuildingFloorAgent
        p = sample_program("double_loaded")
        a = FloorArchetype("ground", 6, 4, 12, 40, 2.4, ("office",), spatial_program=p)
        data = {"building_function":"commercial", "layout":"office_core", "corridor_ratio":.15,
                "room_function_cycle":["office"], "space_archetypes":[asdict(a), asdict(replace(a,role="typical"))]}
        result = BuildingFloorAgent._coerce_semantic_program(data, "commercial")
        self.assertEqual(result["space_archetypes"][0]["spatial_program"], asdict(p))

    def test_generic_wall_compiler_emits_private_horizontal_walls_and_door_headers(self):
        city = BaselineCityPlanner().plan(CitySpec(name="spatial_test", building_count=1, min_floors=1, max_floors=1))
        building = next(city.iter_buildings())
        building.footprint = Bounds2D(0,0,24,22)
        floor = solve(sample_program("residential_clusters"), floor_id=building.floors[0].id)
        building.floors = [floor]
        building.vertical_connectors = []
        scene = GeometryCompiler().compile(city)
        walls = [p for p in scene.primitives if p.metadata.get("wall_role") == "spatial_shared_boundary"]
        self.assertTrue(walls)
        self.assertEqual({p.metadata["canonical_axis"] for p in walls}, {"x", "y"})
        self.assertTrue(all(len(p.metadata["room_ids"]) == 2 for p in walls))
        headers = [p for p in scene.primitives if p.metadata.get("wall_role") == "door_header"]
        self.assertEqual(len(headers), len(floor.doors)-1)


if __name__ == "__main__":
    unittest.main()
