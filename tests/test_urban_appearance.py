import copy
import json
import math
import tempfile
import unittest
from pathlib import Path

from cityg.assets import AssetRecord, AssetRegistry
from cityg.geometry import GeometryCompiler, GeometryValidator
from cityg.agents.streetscape import StreetscapeAgent
from cityg.planning import BaselineCityPlanner, default_urban_appearance_program
from cityg.planning.streetscape import StreetSegmentProgram
from cityg.schemas import CitySpec, Point2D, ZoneSpec


class UrbanAppearanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.city = BaselineCityPlanner().plan(
            CitySpec(
                name="urban_appearance_test",
                width_m=220,
                depth_m=190,
                building_count=4,
                min_floors=2,
                max_floors=4,
                rooms_per_floor=3,
                open_space_ratio=0.25,
                seed=27,
            )
        )

    def test_streetscape_is_topology_bound_and_valid(self):
        scene = GeometryCompiler().compile(self.city)
        report = GeometryValidator().validate(self.city, scene)
        self.assertTrue(report.ok, report.to_dict())
        semantics = {item.semantic_class for item in scene.primitives}
        self.assertTrue({
            "curb", "lane_marking", "crosswalk", "street_tree_trunk",
            "street_light", "vehicle_body", "pedestrian_body",
        }.issubset(semantics))
        self.assertGreater(report.metrics["street_tree_count"], 0)
        self.assertGreater(report.metrics["vehicle_snapshot_count"], 0)
        self.assertGreater(report.metrics["pedestrian_snapshot_count"], 0)

    def test_contextual_tree_species_preferences_are_deterministic(self):
        compiler = GeometryCompiler().streetscape_compiler
        local = next(item for item in self.city.road_network.segments if item.road_class == "local")
        collector = next(item for item in self.city.road_network.segments if item.road_class == "collector")
        residential = StreetSegmentProgram(
            road_id=local.id,
            archetype="residential_green_street",
            dominant_function="residential",
            activity_level="medium",
            frontage_treatment="residential",
        )
        ordinary = StreetSegmentProgram(
            road_id=local.id,
            archetype="neighborhood_street",
            dominant_function="mixed",
            activity_level="low",
            frontage_treatment="mixed",
        )
        residential_variants = {
            compiler._tree_variant(self.city, local, index, residential)[0]
            for index in range(12)
        }
        ordinary_variants = {
            compiler._tree_variant(self.city, local, index, ordinary)[0]
            for index in range(12)
        }
        gateway_variants = {
            compiler._tree_variant(self.city, collector, index, ordinary)[0]
            for index in range(24)
        }
        self.assertIn("pine_sapling", residential_variants)
        self.assertTrue({"island", "tree_small_02"}.issubset(ordinary_variants))
        self.assertTrue({"jacaranda", "quiver"}.issubset(gateway_variants))

    def test_agent_authored_spacing_changes_density_without_coordinates(self):
        dense = GeometryCompiler().compile(self.city)
        sparse_city = copy.deepcopy(self.city)
        program = default_urban_appearance_program().to_dict()
        for profile in program["road_profiles"]:
            profile["tree_spacing_m"] = 80.0
            profile["vehicle_spacing_m"] = 100.0
            profile["pedestrian_spacing_m"] = 100.0
        sparse_city.metadata["urban_appearance_program"] = program
        sparse = GeometryCompiler().compile(sparse_city)
        self.assertLess(
            sparse.metadata["streetscape_stats"]["street_tree_count"],
            dense.metadata["streetscape_stats"]["street_tree_count"],
        )
        self.assertEqual(
            sparse.metadata["urban_appearance_program"]["version"],
            "urban_appearance.v1",
        )

    def test_public_space_density_tiers_are_explicit_and_monotonic(self):
        program = default_urban_appearance_program()
        lush = program.profile_for_landscape("park")
        sparse = program.profile_for_landscape("park", "sparse")
        self.assertEqual(lush.density_tier, "lush")
        self.assertGreater(lush.tree_density, sparse.tree_density)
        self.assertGreater(lush.shrub_density, sparse.shrub_density)
        self.assertGreater(lush.flower_density, 0.0)
        self.assertGreaterEqual(lush.seating_count, sparse.seating_count)

    def test_realized_street_program_covers_every_road_and_avoids_lane_conflicts(self):
        city = BaselineCityPlanner().plan(
            CitySpec(
                name="street_program_context_test",
                width_m=300,
                depth_m=260,
                building_count=12,
                min_floors=2,
                max_floors=3,
                rooms_per_floor=3,
                seed=31,
                zones=(
                    ZoneSpec("homes", "residential", 3),
                    ZoneSpec("shops", "commercial", 2),
                    ZoneSpec("civic", "public_service", 1),
                    ZoneSpec("industry", "industrial", 1),
                ),
            )
        )
        scene = GeometryCompiler().compile(city)
        program = scene.metadata["street_network_program"]
        self.assertEqual(
            {item["road_id"] for item in program["segments"]},
            {road.id for road in city.road_network.segments},
        )
        self.assertGreaterEqual(
            len({item["archetype"] for item in program["segments"]}), 4
        )
        self.assertGreaterEqual(
            len({item["placement_pattern"] for item in program["segments"]}), 3
        )
        for item in program["segments"]:
            self.assertFalse(
                set(item["parking_sides"]) & set(item["bicycle_lane_sides"])
            )
        semantics = {item.semantic_class for item in scene.primitives}
        self.assertTrue(
            {
                "bicycle_lane_surface",
                "parking_bay",
                "sidewalk_furnishing_strip",
                "sidewalk_frontage_strip",
                "frontage_connector",
                "frontage_planter",
            }.issubset(semantics)
        )
        stats = scene.metadata["streetscape_stats"]
        self.assertEqual(
            stats["street_program_count"], len(city.road_network.segments)
        )
        self.assertGreater(stats["frontage_connector_count"], 0)

        # Parking paint must leave asphalt visible, not introduce a raised slab.
        bays = [p for p in scene.primitives if p.semantic_class == "parking_bay"]
        self.assertEqual(len(bays), stats["parking_bay_count"])
        for bay in bays:
            self.assertEqual(bay.material_id, "road_marking")
            self.assertFalse(bay.collision_enabled)
            self.assertLessEqual(bay.center.z + bay.size.z / 2, .003)
            vertices = bay.metadata["mesh_vertices"]
            area = 0.0
            for indices in bay.metadata["mesh_triangles"]:
                a, b, c = [vertices[i] for i in indices]
                area += abs((b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0])) / 2
                signs = [p[0]*q[1]-p[1]*q[0] for p, q in ((a,b),(b,c),(c,a))]
                self.assertFalse(all(s >= -1e-12 for s in signs) or all(s <= 1e-12 for s in signs), "Paint covers the bay center")
            self.assertGreater(area, 0)
            self.assertLess(area, .2, "Parking paint fills too much of the asphalt bay")

    def test_activity_modes_are_contextual_and_bound_to_realized_primitives(self):
        city = BaselineCityPlanner().plan(
            CitySpec(
                name="street_activity_test",
                width_m=300,
                depth_m=260,
                building_count=14,
                min_floors=2,
                max_floors=5,
                rooms_per_floor=3,
                seed=91,
                zones=(
                    ZoneSpec("homes", "residential", 3),
                    ZoneSpec("shops", "commercial", 3),
                    ZoneSpec("civic", "public_service", 2),
                    ZoneSpec("industry", "industrial", 1),
                ),
            )
        )
        scene = GeometryCompiler().compile(city)
        segments = scene.metadata["street_network_program"]["segments"]
        self.assertTrue(any(item["activity_modes"] for item in segments))
        self.assertTrue(
            all(0 <= item["activity_cluster_count"] <= 6 for item in segments)
        )
        motifs = [
            item.metadata.get("activity_motif")
            for item in scene.primitives
            if item.metadata.get("activity_motif")
        ]
        self.assertTrue(motifs)
        self.assertIn("intersection_waiting", motifs)
        self.assertIn("retail_browsing", motifs)
        self.assertTrue(
            all(
                item.metadata.get("activity_cluster_id")
                and item.metadata.get("activity_role")
                and item.metadata.get("activity_binding")
                for item in scene.primitives
                if item.metadata.get("activity_motif")
            )
        )
        self.assertGreater(scene.metadata["streetscape_stats"]["activity_person_count"], 0)
        self.assertTrue(GeometryValidator().validate(city, scene).ok)

    def test_agent_authored_segment_program_overrides_semantics_not_coordinates(self):
        city = copy.deepcopy(self.city)
        road = city.road_network.segments[0]
        city.metadata["street_network_program"] = {
            "version": "street_network_program.v1",
            "segments": [
                {
                    "road_id": road.id,
                    "archetype": "pedestrian_shared_street",
                    "dominant_function": "commercial",
                    "activity_level": "high",
                    "frontage_treatment": "retail",
                    "parking_sides": [],
                    "bicycle_lane_sides": [],
                    "amenity_types": ["planter", "cafe_terrace"],
                }
            ],
        }
        scene = GeometryCompiler().compile(city)
        selected = next(
            item
            for item in scene.metadata["street_network_program"]["segments"]
            if item["road_id"] == road.id
        )
        self.assertEqual(selected["archetype"], "pedestrian_shared_street")
        self.assertEqual(selected["frontage_treatment"], "retail")
        self.assertEqual(selected["source"], "agent_authored")

    def test_streetscape_agent_personalizes_exact_realized_road_and_merges_fallbacks(self):
        road = self.city.road_network.segments[0]

        class Service:
            def __init__(self):
                self.calls = 0

            def complete(self, messages, response_schema=None):
                self.calls += 1
                if self.calls == 1:
                    return json.dumps({
                        "action": "request_details",
                        "detail_keys": ["realized_segments"],
                        "program_json": "{}",
                    })
                return json.dumps({
                    "action": "final",
                    "detail_keys": [],
                    "program_json": json.dumps({
                        "version": "street_network_program.v1",
                        "segments": [{
                            "road_id": road.id,
                            "archetype": "civic_avenue",
                            "activity_level": "high",
                            "frontage_treatment": "civic",
                            "parking_sides": [],
                            "bicycle_lane_sides": [],
                            "amenity_types": ["planter", "bench", "bicycle_rack"],
                            "placement_pattern": "staggered",
                            "tree_palette": ["columnar", "deciduous"],
                            "light_family": "square",
                        }],
                    }),
                })

        result = StreetscapeAgent(Service(), model_id="fake", max_calls=2).plan(self.city)
        self.assertEqual(len(result.program.segments), len(self.city.road_network.segments))
        personalized = result.program.for_road(road.id)
        self.assertEqual(personalized.archetype, "civic_avenue")
        self.assertEqual(personalized.placement_pattern, "staggered")
        self.assertEqual(personalized.tree_palette, ("columnar", "deciduous"))
        self.assertEqual(personalized.light_family, "square")
        self.assertEqual(personalized.source, "agent_authored")
        self.assertEqual(len(result.disclosures), 1)
        self.assertTrue(all(item.road_id for item in result.program.segments))

    def test_street_program_rejects_unbounded_density_values(self):
        with self.assertRaises(ValueError):
            StreetSegmentProgram(
                road_id="road_test",
                archetype="neighborhood_street",
                dominant_function="mixed",
                activity_level="medium",
                frontage_treatment="mixed",
                pedestrian_spacing_m=0.01,
            )

    def test_street_program_rejects_unknown_rhythm(self):
        with self.assertRaises(ValueError):
            StreetSegmentProgram(
                road_id="road_test",
                archetype="neighborhood_street",
                dominant_function="mixed",
                activity_level="medium",
                frontage_treatment="mixed",
                placement_pattern="perfect_grid",
            )

    def test_tree_and_light_rhythms_are_deterministic_but_not_mirrored(self):
        first = GeometryCompiler().compile(self.city)
        second = GeometryCompiler().compile(self.city)

        def placements(scene, semantics):
            result = {}
            for primitive in scene.primitives:
                if primitive.semantic_class not in semantics:
                    continue
                metadata = primitive.metadata
                if "longitudinal_m" not in metadata:
                    continue
                key = (metadata["road_id"], metadata["placement_side"])
                result.setdefault(key, []).append(float(metadata["longitudinal_m"]))
            return {key: sorted(set(values)) for key, values in result.items()}

        first_trees = placements(
            first, {"street_tree_asset", "street_tree_trunk"}
        )
        second_trees = placements(
            second, {"street_tree_asset", "street_tree_trunk"}
        )
        self.assertEqual(first_trees, second_trees)
        long_rows = [values for values in first_trees.values() if len(values) >= 4]
        self.assertTrue(long_rows)
        self.assertTrue(
            any(
                len(
                    {
                        round(right - left, 2)
                        for left, right in zip(values, values[1:])
                    }
                )
                >= 2
                for values in long_rows
            )
        )
        road_ids = {road_id for road_id, _side in first_trees}
        self.assertTrue(
            any(
                first_trees.get((road_id, "left"))
                != first_trees.get((road_id, "right"))
                for road_id in road_ids
            )
        )

        lights = placements(first, {"street_light_asset", "street_light"})
        self.assertTrue(lights)
        self.assertTrue(
            any(
                lights.get((road_id, "left"))
                != lights.get((road_id, "right"))
                for road_id in {key[0] for key in lights}
            )
        )

    def test_junctions_do_not_place_trees_or_lights_on_other_roads(self):
        scene = GeometryCompiler().compile(self.city)

        def distance_to_segment(point, start, end):
            dx, dy = end.x - start.x, end.y - start.y
            length_sq = dx * dx + dy * dy
            factor = 0.0 if length_sq <= 1e-9 else max(
                0.0,
                min(1.0, ((point.x - start.x) * dx + (point.y - start.y) * dy) / length_sq),
            )
            return math.hypot(
                point.x - (start.x + factor * dx),
                point.y - (start.y + factor * dy),
            )

        facilities = [
            item for item in scene.primitives
            if item.semantic_class in {
                "street_tree_asset", "street_tree_trunk", "street_light", "street_light_asset"
            }
        ]
        self.assertTrue(facilities)
        for item in facilities:
            owner_road = item.metadata.get("road_id")
            for road in self.city.road_network.segments:
                if road.id == owner_road:
                    continue
                clearance = distance_to_segment(item.center, *road.centerline) - road.width_m / 2
                self.assertGreater(
                    clearance,
                    0.0,
                    f"{item.id} intrudes into {road.id}",
                )
        self.assertTrue(
            any(item.semantic_class == "junction_surface" for item in scene.primitives)
        )

    def test_sidewalk_slabs_are_block_constrained(self):
        scene = GeometryCompiler().compile(self.city)

        def corners(item):
            angle = math.radians(item.rotation_z_deg)
            ux, uy = math.cos(angle), math.sin(angle)
            nx, ny = -uy, ux
            hx, hy = item.size.x / 2, item.size.y / 2
            return [
                (item.center.x + ux * sx * hx + nx * sy * hy,
                 item.center.y + uy * sx * hx + ny * sy * hy)
                for sx, sy in ((-1, -1), (-1, 1), (1, -1), (1, 1))
            ]

        sidewalks = [item for item in scene.primitives if item.semantic_class == "sidewalk"]
        self.assertTrue(sidewalks)
        for item in sidewalks:
            self.assertTrue(item.metadata.get("block_constrained"), item.id)
            for road in self.city.road_network.segments:
                if road.id == item.owner_id:
                    continue
                if item.metadata.get("sidewalk_infill"):
                    # A concave patch can wrap around an oblique carriageway.
                    # Check every point of the physical patch, including its edges.
                    from cityg.geometry.geography import primitive_footprint
                    from cityg.polygons import line_shape
                    self.assertGreater(primitive_footprint(item).distance(line_shape(road.centerline)),
                                       road.width_m / 2, item.id)
                    continue
                for x, y in corners(item):
                    start, end = road.centerline
                    # Reuse the same projection calculation as the geometry
                    # code without coupling this test to an implementation
                    # helper.
                    dx, dy = end.x - start.x, end.y - start.y
                    length_sq = dx * dx + dy * dy
                    factor = 0.0 if length_sq <= 1e-9 else max(
                        0.0,
                        min(1.0, ((x - start.x) * dx + (y - start.y) * dy) / length_sq),
                    )
                    distance = math.hypot(
                        x - (start.x + factor * dx),
                        y - (start.y + factor * dy),
                    )
                    self.assertGreater(
                        distance - road.width_m / 2,
                        0.0,
                        f"{item.id} intrudes into {road.id}",
                    )

    def test_programmed_street_bands_and_frontages_avoid_other_carriageways(self):
        scene = GeometryCompiler().compile(self.city)
        constrained = [
            item
            for item in scene.primitives
            if item.semantic_class
            in {
                "bicycle_lane_surface",
                "parking_bay",
                "sidewalk_furnishing_strip",
                "sidewalk_frontage_strip",
                "frontage_connector",
            }
        ]
        self.assertTrue(constrained)
        for item in constrained:
            angle = math.radians(item.rotation_z_deg)
            ux, uy = math.cos(angle), math.sin(angle)
            nx, ny = -uy, ux
            samples = []
            for along in (-0.5, 0.0, 0.5):
                for across in (-0.5, 0.0, 0.5):
                    samples.append(
                        (
                            item.center.x
                            + ux * along * item.size.x
                            + nx * across * item.size.y,
                            item.center.y
                            + uy * along * item.size.x
                            + ny * across * item.size.y,
                        )
                    )
            for road in self.city.road_network.segments:
                if road.id == item.owner_id:
                    continue
                start, end = road.centerline
                dx, dy = end.x - start.x, end.y - start.y
                length_sq = dx * dx + dy * dy
                for x, y in samples:
                    factor = 0.0 if length_sq <= 1e-9 else max(
                        0.0,
                        min(
                            1.0,
                            ((x - start.x) * dx + (y - start.y) * dy)
                            / length_sq,
                        ),
                    )
                    distance = math.hypot(
                        x - (start.x + factor * dx),
                        y - (start.y + factor * dy),
                    )
                    self.assertGreater(
                        distance - road.width_m / 2,
                        -1e-5,
                        f"{item.id} intrudes into {road.id}",
                    )

    def test_crosswalks_skip_shared_space_and_service_roads(self):
        scene = GeometryCompiler().compile(self.city)
        road_classes = {road.id: road.road_class for road in self.city.road_network.segments}
        for item in scene.primitives:
            if item.semantic_class != "crosswalk":
                continue
            self.assertIn(road_classes[item.owner_id], {"arterial", "collector", "local"})

    def test_landscape_has_layered_vegetation_and_programmed_features(self):
        scene = GeometryCompiler().compile(self.city)
        semantics = {item.semantic_class for item in scene.primitives}
        self.assertIn("landscape_shrub", semantics)
        self.assertTrue(
            semantics.intersection({"playground_equipment", "flower_bed", "water_feature"})
        )

    def test_occupied_parcels_receive_function_aware_site_details(self):
        scene = GeometryCompiler().compile(self.city)
        stats = scene.metadata["parcel_landscape_stats"]
        occupied = sum(
            bool(parcel.buildings)
            for district in self.city.districts
            for parcel in district.parcels
        )
        self.assertEqual(stats["parcel_count"], occupied)
        self.assertEqual(stats["ground_treatment_count"], occupied)
        self.assertEqual(stats["site_amenity_count"], occupied)
        self.assertGreaterEqual(stats["planting_bed_count"], occupied)
        self.assertTrue(
            any(item.semantic_class == "parcel_ground" for item in scene.primitives)
        )
        self.assertTrue(
            any(item.semantic_class == "parcel_planting_bed" for item in scene.primitives)
        )
        self.assertGreater(stats["shrub_count"] + stats["tree_count"], 0)
        self.assertGreater(stats["surface_patch_count"], 0)
        self.assertGreaterEqual(scene.metadata["surface_material_variant_count"], 2)
        surface_patches = [
            item
            for item in scene.primitives
            if item.semantic_class
            in {"parcel_surface_patch", "landscape_surface_patch"}
        ]
        self.assertTrue(surface_patches)
        material_ids = {material.id for material in scene.materials}
        self.assertTrue(all(item.material_id in material_ids for item in surface_patches))

        footprints = [
            building.footprint
            for building in self.city.iter_buildings()
        ]
        for item in scene.primitives:
            if not item.semantic_class.startswith("parcel_") or item.semantic_class == "parcel_ground":
                continue
            self.assertFalse(
                any(
                    footprint.contains_point(Point2D(item.center.x, item.center.y))
                    for footprint in footprints
                ),
                item.id,
            )

        for item in surface_patches:
            if item.semantic_class != "parcel_surface_patch":
                continue
            angle = math.radians(item.rotation_z_deg)
            for local_x, local_y in (
                (-item.size.x / 2, -item.size.y / 2),
                (-item.size.x / 2, item.size.y / 2),
                (item.size.x / 2, -item.size.y / 2),
                (item.size.x / 2, item.size.y / 2),
            ):
                point = Point2D(
                    item.center.x + local_x * math.cos(angle) - local_y * math.sin(angle),
                    item.center.y + local_x * math.sin(angle) + local_y * math.cos(angle),
                )
                self.assertFalse(
                    any(footprint.contains_point(point) for footprint in footprints),
                    item.id,
                )

    def test_semantic_outdoor_registry_replaces_street_furniture_fallback(self):
        with tempfile.TemporaryDirectory() as temporary:
            geometry = Path(temporary) / "bench.glb"
            geometry.write_bytes(b"glTF-test")
            registry = AssetRegistry()
            registry.register(
                AssetRecord(
                    asset_id="bench_pack_v1",
                    category="street_bench",
                    tags=("public", "street", "bench", "wood", "metal"),
                    dimensions_m=(1.9, .62, .86),
                    geometry_path=str(geometry),
                    source="curated_test",
                    license_id="CC0-1.0",
                    quality_score=.9,
                    metadata={"outdoor_slot": "street_bench_wood_metal", "outdoor_pack_status": "ready"},
                )
            )
            scene = GeometryCompiler(asset_registry=registry).compile(self.city)
            resolved = [
                item for item in scene.primitives
                if item.metadata.get("asset_id") == "bench_pack_v1"
            ]
            self.assertTrue(resolved)
            self.assertTrue(all(item.semantic_class == "bench" for item in resolved))
            self.assertGreater(scene.metadata["streetscape_stats"]["resolved_outdoor_asset_count"], 0)

    def test_configured_registry_never_emits_legacy_procedural_tree_proxy(self):
        """Production/curated renders must omit, rather than regress to, cyan blobs."""

        scene = GeometryCompiler(asset_registry=AssetRegistry()).compile(self.city)
        proxy_semantics = {
            item.semantic_class
            for item in scene.primitives
            if item.semantic_class in {"tree_trunk", "tree_canopy", "street_tree_trunk", "street_tree_canopy"}
        }
        self.assertEqual(proxy_semantics, set())


if __name__ == "__main__":
    unittest.main()
