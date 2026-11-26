import math
import random
import unittest

from cityg.planning import (
    BaselineCityPlanner,
    BuildingProfile,
    BuildingProgram,
    FloorProgram,
    HeightCandidate,
    HeightDecision,
    FloorProfile,
    HierarchicalProgram,
    ProgrammedCityPlanner,
    SkylinePlanner,
    SkylineProgram,
    StreetAlignmentPlanner,
    UrbanProgram,
)
from cityg.schemas import CitySpec, Point2D, ZoneSpec
from cityg.serialization import city_from_dict, to_primitive
from cityg.validation import CityValidator


class BaselinePlannerTests(unittest.TestCase):
    def setUp(self):
        self.spec = CitySpec(
            name="test_city",
            width_m=320.0,
            depth_m=260.0,
            building_count=8,
            min_floors=2,
            max_floors=3,
            rooms_per_floor=4,
            seed=11,
            zones=(
                ZoneSpec("homes", "residential", 0.6),
                ZoneSpec("shops", "commercial", 0.4),
            ),
        )

    def test_generates_requested_hierarchy(self):
        city = BaselineCityPlanner().plan(self.spec)
        buildings = list(city.iter_buildings())
        self.assertEqual(len(buildings), 8)
        self.assertEqual(len(city.districts), 2)
        self.assertTrue(city.road_network.junctions)
        self.assertTrue(city.road_network.segments)
        for building in buildings:
            self.assertGreaterEqual(len(building.floors), 2)
            self.assertEqual(len(building.vertical_connectors), 1)
            for floor in building.floors:
                self.assertEqual(len(floor.rooms), 5)  # requested rooms + corridor

    def test_output_passes_deterministic_validation(self):
        city = BaselineCityPlanner().plan(self.spec)
        report = CityValidator().validate(city)
        self.assertTrue(report.ok, report.to_dict())

    def test_generation_is_reproducible(self):
        first = BaselineCityPlanner().plan(self.spec)
        second = BaselineCityPlanner().plan(self.spec)
        self.assertEqual(to_primitive(first), to_primitive(second))

    def test_organic_layout_varies_blocks_and_building_masses(self):
        city = BaselineCityPlanner().plan(self.spec)
        layout = city.metadata["site_layout"]
        self.assertGreater(layout["open_block_count"], 0)

        x_axes = sorted({item.position.x for item in city.road_network.junctions})
        x_gaps = {round(right - left, 4) for left, right in zip(x_axes, x_axes[1:])}
        self.assertGreater(len(x_gaps), 1)

        buildings = list(city.iter_buildings())
        widths = {round(item.footprint.width, 4) for item in buildings}
        entrance_sides = {item.metadata["entrance_side"] for item in buildings}
        self.assertGreater(len(widths), 1)
        self.assertGreater(len(entrance_sides), 1)

    def test_organic_hierarchy_builds_clusters_and_non_orthogonal_roads(self):
        city = BaselineCityPlanner().plan(self.spec)
        buildings = list(city.iter_buildings())
        urban_blocks = {item.metadata["urban_block_id"] for item in buildings}
        self.assertLess(len(urban_blocks), len(buildings))
        self.assertTrue(any(item.metadata["cluster_size"] > 1 for item in buildings))

        secondary = [
            item
            for item in city.road_network.segments
            if item.road_class in {"service", "shared_space"}
        ]
        self.assertTrue(secondary)
        angles = []
        for road in secondary:
            start, end = road.centerline
            angles.append(
                abs(math.degrees(math.atan2(end.y - start.y, end.x - start.x)))
                % 90
            )
        self.assertTrue(any(1.0 < angle < 89.0 for angle in angles))

    def test_road_cross_sections_follow_hierarchy_and_are_not_uniform(self):
        city = BaselineCityPlanner().plan(
            CitySpec(
                name="road_cross_section_test",
                width_m=300,
                depth_m=260,
                building_count=12,
                min_floors=2,
                max_floors=4,
                rooms_per_floor=3,
                road_pattern="organic_hierarchy",
                seed=23,
            )
        )
        primary = [
            item for item in city.road_network.segments
            if item.road_class in {"collector", "local"}
        ]
        self.assertGreater(len({round(item.width_m, 2) for item in primary}), 2)
        collectors = [item for item in primary if item.road_class == "collector"]
        locals_ = [item for item in primary if item.road_class == "local"]
        self.assertTrue(collectors and locals_)
        self.assertGreater(min(item.width_m for item in collectors), max(item.width_m for item in locals_))
        self.assertGreater(
            min(item.sidewalk_width_m for item in collectors),
            min(item.sidewalk_width_m for item in locals_),
        )
        self.assertTrue(all(item.lane_count >= 2 for item in collectors))

    def test_city_scale_road_hierarchy_adds_sparse_arterial_spine(self):
        city = BaselineCityPlanner().plan(
            CitySpec(name="arterial_city", width_m=600, depth_m=600, building_count=24, seed=5)
        )
        roads = city.road_network.segments
        arterials = [road for road in roads if road.road_class == "arterial"]
        self.assertTrue(arterials)
        self.assertLessEqual(len(arterials) / len(roads), 0.12)
        self.assertTrue(all(road.lane_count == 4 for road in arterials))
        self.assertTrue(all(road.median_width_m > 0 and not road.parking_allowed for road in arterials))
        self.assertTrue(all(road.bike_lane and road.bus_lane for road in arterials))

    def test_building_massing_varies_but_orientation_follows_urban_context(self):
        city = BaselineCityPlanner().plan(self.spec)
        buildings = list(city.iter_buildings())
        styles = {item.metadata["massing_style"] for item in buildings}
        self.assertGreaterEqual(len(styles), 3)
        contracts = [item.metadata["orientation_contract"] for item in buildings]
        strict = [item for item in contracts if item["strict_alignment"]]
        rotated = [item for item in contracts if abs(item["offset_deg"]) > 1e-9]
        self.assertTrue(strict)
        self.assertTrue(rotated)
        self.assertTrue(all(item["offset_deg"] == 0.0 for item in strict))
        self.assertTrue(
            all(item["urban_context"] != "urban_core" for item in rotated)
        )
        for building in buildings:
            contract = building.metadata["orientation_contract"]
            self.assertEqual(
                building.metadata["orientation_deg"], contract["orientation_deg"]
            )
            if contract["urban_context"] == "urban_core":
                self.assertEqual(contract["offset_deg"], 0.0)
            if building.function == "commercial":
                self.assertTrue(contract["strict_alignment"])
                self.assertEqual(contract["offset_deg"], 0.0)
        self.assertEqual(
            city.metadata["orientation_plan"]["contextual_rotation_count"],
            len(rotated),
        )
        self.assertTrue(
            all(
                item.metadata["interior_core_policy"]
                == "rectangular_navigation_core"
                for item in buildings
            )
        )
        self.assertEqual(city.metadata["height_plan"]["strategy"], "zoned_skyline")
        self.assertTrue(
            all(
                item.metadata["height_contract"]["realized_floors"]
                == len(item.floors)
                for item in buildings
            )
        )

    def test_manifest_round_trip(self):
        original = BaselineCityPlanner().plan(self.spec)
        loaded = city_from_dict(to_primitive(original))
        self.assertEqual(to_primitive(original), to_primitive(loaded))
        self.assertTrue(CityValidator().validate(loaded).ok)

    def test_highrise_core_and_typical_floor_contract(self):
        city = BaselineCityPlanner().plan(
            CitySpec(
                name="highrise_contract",
                width_m=180,
                depth_m=160,
                building_count=1,
                min_floors=18,
                max_floors=18,
                rooms_per_floor=2,
                seed=44,
                zones=(ZoneSpec("core", "commercial", 1.0),),
                height_strategy="uniform_random",
            )
        )
        building = next(city.iter_buildings())
        connectors = [item.connector_type for item in building.vertical_connectors]
        self.assertEqual(connectors.count("stairs"), 2)
        self.assertEqual(connectors.count("elevator"), 2)
        self.assertEqual(building.metadata["massing_style"], "tower_podium")
        self.assertEqual(building.metadata["highrise"]["podium_floors"], 3)
        self.assertIn(
            building.metadata["highrise"]["massing_variant"],
            {"standard", "setback", "offset", "slender_landmark"},
        )
        self.assertEqual(
            building.metadata["highrise"]["massing_constraint"],
            "single_continuous_core",
        )
        reuse = building.metadata["highrise"]["typical_floor_reuse"]
        self.assertGreater(max(item["instance_count"] for item in reuse), 5)
        self.assertTrue(CityValidator().validate(city).ok)

    def test_programmed_highrise_floor_rooms_follow_realized_plate(self):
        spec = CitySpec(
            name="highrise_realized_floor_plate",
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
        building = next(city.iter_buildings())
        self.assertEqual(
            building.metadata["floor_plate_contract"]["source"],
            "highrise_massing_outline_v1",
        )
        first = building.floors[0].metadata["realized_floor_plate"]["bounds"]
        upper = building.floors[-1].metadata["realized_floor_plate"]["bounds"]
        self.assertLessEqual(
            (upper["max_x"] - upper["min_x"]) * (upper["max_y"] - upper["min_y"]),
            (first["max_x"] - first["min_x"]) * (first["max_y"] - first["min_y"]),
        )
        for floor in building.floors:
            plate = floor.metadata["realized_floor_plate"]["bounds"]
            for room in floor.rooms:
                self.assertGreaterEqual(room.bounds.min_x, plate["min_x"] - 1e-6)
                self.assertLessEqual(room.bounds.max_x, plate["max_x"] + 1e-6)
                self.assertGreaterEqual(room.bounds.min_y, plate["min_y"] - 1e-6)
                self.assertLessEqual(room.bounds.max_y, plate["max_y"] + 1e-6)
            corridor = next(
                room for room in floor.rooms if room.function == "corridor"
            )
            for connector in building.vertical_connectors:
                self.assertTrue(
                    corridor.bounds.contains_bounds(connector.bounds),
                    (floor.level, corridor.bounds, connector.bounds),
                )
        report = CityValidator().validate(city)
        self.assertTrue(
            report.ok,
            [(issue.code, issue.entity_id) for issue in report.issues],
        )

    def test_key_facade_aligns_to_arbitrary_street_bearing(self):
        decision = StreetAlignmentPlanner.plan(
            entrance_side="west",
            function="commercial",
            centrality=0.85,
            cluster_size=2,
            highrise=True,
            landmark=False,
            layout_style="organic_grid",
            building_index=3,
            seed=11,
            street_axis_deg=32.0,
            frontage_road_id="road_diagonal",
        )
        realized_facade_axis = (
            decision.local_facade_axis_deg + decision.orientation_deg
        ) % 180.0
        self.assertAlmostEqual(realized_facade_axis, 32.0)
        self.assertEqual(decision.offset_deg, 0.0)
        self.assertTrue(decision.strict_alignment)
        self.assertEqual(decision.frontage_road_id, "road_diagonal")

    def test_floor_detail_agent_populates_valid_canonical_objects(self):
        city = BaselineCityPlanner().plan(self.spec)
        detail = city.metadata["interior_detail"]
        self.assertEqual(detail["asset_backend"], "procedural_proxy")
        self.assertEqual(detail["furnished_room_ratio"], 1.0)
        objects = list(city.iter_objects())
        self.assertTrue(objects)
        self.assertGreaterEqual(len({item.category for item in objects}), 8)
        for floor in city.iter_floors():
            by_room = {}
            for obj in floor.objects:
                by_room.setdefault(obj.room_id, []).append(obj)
            for room in floor.rooms:
                self.assertEqual(
                    set(room.object_ids),
                    {item.id for item in by_room.get(room.id, [])},
                )
                for obj in by_room.get(room.id, []):
                    self.assertTrue(room.bounds.contains_bounds(obj.bounds))



class CitySpecTests(unittest.TestCase):
    def test_unknown_fields_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unknown CitySpec"):
            CitySpec.from_dict({"name": "bad", "unexpected": True})

    def test_invalid_floor_range_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Floor range"):
            CitySpec.from_dict({"min_floors": 4, "max_floors": 2})

    def test_invalid_layout_controls_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "layout_style"):
            CitySpec.from_dict({"layout_style": "random_sprawl"})
        with self.assertRaisesRegex(ValueError, "open_space_ratio"):
            CitySpec.from_dict({"open_space_ratio": 0.5})
        with self.assertRaisesRegex(ValueError, "layout_irregularity"):
            CitySpec.from_dict({"layout_irregularity": -0.1})
        with self.assertRaisesRegex(ValueError, "road_pattern"):
            CitySpec.from_dict({"road_pattern": "radial"})
        with self.assertRaisesRegex(ValueError, "buildings_per_block"):
            CitySpec.from_dict({"buildings_per_block": 5})
        with self.assertRaisesRegex(ValueError, "branch_road_ratio"):
            CitySpec.from_dict({"branch_road_ratio": 1.1})
        with self.assertRaisesRegex(ValueError, "height_strategy"):
            CitySpec.from_dict({"height_strategy": "random_towers"})
        with self.assertRaisesRegex(ValueError, "highrise_ratio"):
            CitySpec.from_dict({"highrise_ratio": 0.8})


class SkylinePlannerTests(unittest.TestCase):
    def test_building_floor_policy_only_nudges_skyline_recommendation(self):
        decision = HeightDecision(
            building_index=4,
            function="commercial",
            height_zone="core",
            height_role="highrise",
            min_floors=10,
            max_floors=26,
            recommended_floors=18,
            centrality=0.8,
            source="llm_skyline_program",
        )
        spec = CitySpec(min_floors=2, max_floors=30)
        rng = random.Random(1)
        self.assertEqual(
            ProgrammedCityPlanner._floor_count(
                "seeded_uniform", spec, rng, 4, decision
            ),
            18,
        )
        self.assertEqual(
            ProgrammedCityPlanner._floor_count("maximum", spec, rng, 4, decision),
            20,
        )
        self.assertEqual(
            ProgrammedCityPlanner._floor_count("minimum", spec, rng, 4, decision),
            16,
        )
        self.assertEqual(
            ProgrammedCityPlanner._floor_count(
                "alternating", spec, rng, 5, decision
            ),
            20,
        )

    def test_landmark_keeps_exact_skyline_recommendation(self):
        decision = HeightDecision(
            building_index=1,
            function="commercial",
            height_zone="core",
            height_role="highrise",
            min_floors=12,
            max_floors=30,
            recommended_floors=29,
            centrality=0.95,
            highrise=True,
            landmark=True,
            source="llm_skyline_program",
        )
        result = ProgrammedCityPlanner._floor_count(
            "minimum", CitySpec(), random.Random(1), 1, decision
        )
        self.assertEqual(result, 29)

    def test_agent_authored_skyline_program_controls_safe_realization(self):
        spec = CitySpec(
            name="skyline_agent_test",
            width_m=600,
            depth_m=500,
            building_count=12,
            min_floors=2,
            max_floors=24,
            rooms_per_floor=2,
            seed=23,
            zones=(
                ZoneSpec("homes", "residential", 1),
                ZoneSpec("core", "commercial", 1),
                ZoneSpec("industry", "industrial", 1),
            ),
        )
        program = SkylineProgram.from_dict(
            {
                "profiles": [
                    {
                        "function": "residential",
                        "min_floors": 5,
                        "max_floors": 14,
                        "centrality_bias": "distributed",
                        "height_role": "mixed",
                    },
                    {
                        "function": "commercial",
                        "min_floors": 12,
                        "max_floors": 24,
                        "centrality_bias": "core",
                        "height_role": "highrise",
                    },
                    {
                        "function": "industrial",
                        "min_floors": 2,
                        "max_floors": 4,
                        "centrality_bias": "edge",
                        "height_role": "lowrise",
                    },
                ],
                "highrise_ratio": 0.25,
                "landmark_count": 2,
                "landmark_functions": ["commercial"],
                "skyline_strength": 0.9,
            }
        )
        functions = ["residential"] * 4 + ["commercial"] * 4 + ["industrial"] * 4
        candidates = [
            HeightCandidate(
                index,
                function,
                Point2D(80 + (index % 4) * 140, 90 + (index // 4) * 150),
            )
            for index, function in enumerate(functions)
        ]
        planner = SkylinePlanner()
        first = planner.plan(spec, candidates, program)
        second = planner.plan(spec, candidates, program)
        self.assertEqual(first, second)
        self.assertEqual(sum(item.landmark for item in first), 2)
        self.assertTrue(all(item.source == "llm_skyline_program" for item in first))
        for item in first:
            profile = program.for_function(item.function)
            self.assertGreaterEqual(item.recommended_floors, profile.min_floors)
            self.assertLessEqual(item.recommended_floors, profile.max_floors)
        commercial = [item.recommended_floors for item in first if item.function == "commercial"]
        industrial = [item.recommended_floors for item in first if item.function == "industrial"]
        self.assertGreater(sum(commercial) / len(commercial), sum(industrial) / len(industrial))


if __name__ == "__main__":
    unittest.main()
