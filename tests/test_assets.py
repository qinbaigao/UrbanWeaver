import json
import tempfile
import unittest
from pathlib import Path

from cityg.assets import (
    AssetRecord,
    AssetRegistry,
    AssetResolver,
    MaterialLibrary,
    MaterialRecord,
    choose_asset_variant,
)
from cityg.geometry import GeometryCompiler
from cityg.planning import BaselineCityPlanner
from cityg.planning.interiors import FloorDetailAgent
from cityg.schemas import CitySpec, ZoneSpec
from cityg.usd import UsdaWriter


class AssetRegistryTests(unittest.TestCase):
    @unittest.skipUnless(Path("assets/incoming/ground_materials").exists(),
                         "Optional textures: run scripts/download_polyhaven_ground_materials.py")
    def test_project_ground_materials_have_portable_base_color_textures(self):
        library = MaterialLibrary(Path("assets/material_library.json"))
        expected = {
            "parcel_lawn": 5.0,
            "courtyard_paving": 4.0,
            "civic_forecourt": 6.0,
            "service_yard": 8.0,
            "grass": 5.0,
            "plaza_paving": 6.0,
            "landscape_path": 4.0,
        }
        for material_id, scale_m in expected.items():
            record = library.get(material_id)
            self.assertIsNotNone(record, material_id)
            self.assertEqual(record.texture_scale_m, scale_m)
            self.assertTrue(record.base_color_path)
            self.assertTrue(library.resolve_path(record.base_color_path).is_file())

    @unittest.skipUnless(Path("assets/incoming/ground_materials").exists(),
                         "Optional textures: run scripts/download_polyhaven_ground_materials.py")
    def test_ground_pbr_pack_has_all_required_channels(self):
        library = MaterialLibrary(Path("assets/material_library.json"))
        expected = {"grass", "courtyard_paving", "brick_paving", "gravel_warm"}
        for material_id in expected:
            record = library.get(material_id)
            self.assertIsNotNone(record, material_id)
            self.assertTrue(record.has_pbr_textures)
            for channel in (
                record.base_color_path,
                record.normal_path,
                record.roughness_path,
                record.ambient_occlusion_path,
            ):
                self.assertIsNotNone(channel, material_id)
                self.assertTrue(library.resolve_path(channel).is_file(), material_id)

    def test_repeated_asset_selection_excludes_hero_scale_meshes(self):
        regular = AssetRecord(
            asset_id="tree_regular",
            category="street_tree",
            tags=("tree",),
            geometry_path="regular.glb",
            metadata={"mesh_validation": {"triangle_count": 120_000}},
        )
        hero = AssetRecord(
            asset_id="tree_hero",
            category="street_tree",
            tags=("tree",),
            geometry_path="hero.glb",
            quality_score=1.0,
            metadata={
                "style": "photorealistic_pbr",
                "mesh_validation": {"triangle_count": 2_000_000},
            },
        )
        selected = choose_asset_variant(
            [(hero, 2.0), (regular, 2.0)],
            "street-tree-instance",
            max_triangle_count=500_000,
        )
        self.assertEqual(selected, regular)

    def test_context_tags_filter_indoor_outdoor_and_room_type(self):
        registry = AssetRegistry()
        registry.register_many(
            (
                AssetRecord(
                    asset_id="public_bench",
                    category="waiting_bench",
                    tags=("bench", "outdoor"),
                    environment="outdoor",
                    geometry_path="public.glb",
                ),
                AssetRecord(
                    asset_id="clinic_waiting_bench",
                    category="waiting_bench",
                    tags=("bench", "interior"),
                    environment="indoor",
                    room_types=("waiting_room", "reception"),
                    geometry_path="clinic.glb",
                ),
            )
        )
        matches = registry.search(
            "waiting bench",
            category="waiting_bench",
            environment="indoor",
            room_type="reception",
            require_geometry=True,
        )
        self.assertEqual([item.asset_id for item, _ in matches], ["clinic_waiting_bench"])
        self.assertFalse(
            registry.require("public_bench").supports(
                environment="indoor", room_type="reception"
            )
        )

    def test_legacy_records_infer_environment_and_room_types(self):
        record = AssetRecord.from_dict(
            {
                "asset_id": "legacy_desk",
                "category": "desk",
                "tags": ["office", "furniture"],
            }
        )
        self.assertEqual(record.environment, "indoor")
        self.assertIn("office", record.room_types)

    def test_search_can_require_a_concrete_subtype_token(self):
        registry = AssetRegistry()
        registry.register_many(
            (
                AssetRecord(
                    asset_id="sedan_v1",
                    category="vehicle",
                    tags=("sedan",),
                    geometry_path="sedan.glb",
                ),
                AssetRecord(
                    asset_id="bus_v1",
                    category="vehicle",
                    tags=("bus",),
                    geometry_path="bus.glb",
                ),
            )
        )
        matches = registry.search(
            "bus vehicle",
            category="vehicle",
            require_geometry=True,
            required_tokens=("bus",),
        )
        self.assertEqual([item.asset_id for item, _score in matches], ["bus_v1"])

    def test_registry_asset_flows_from_floor_planning_into_geometry(self):
        with tempfile.TemporaryDirectory() as temporary:
            geometry = Path(temporary) / "office_chair.glb"
            geometry.write_bytes(b"glTF-test")
            registry = AssetRegistry()
            registry.register(
                AssetRecord(
                    asset_id="hunyuan_office_chair_v1",
                    category="office_chair",
                    tags=("office", "chair", "generated"),
                    dimensions_m=(0.58, 0.58, 1.0),
                    geometry_path=str(geometry),
                    source="hunyuan3d2_local",
                    license_id="model-license",
                )
            )
            city = BaselineCityPlanner(
                floor_detail_agent=FloorDetailAgent(
                    asset_resolver=AssetResolver(registry)
                )
            ).plan(
                CitySpec(
                    name="asset_planning_test",
                    width_m=180,
                    depth_m=160,
                    building_count=1,
                    min_floors=1,
                    max_floors=1,
                    rooms_per_floor=3,
                    seed=4,
                    zones=(ZoneSpec("office", "commercial", 1.0),),
                )
            )
            chairs = [
                item for item in city.iter_objects() if item.category == "office_chair"
            ]
            self.assertTrue(chairs)
            self.assertTrue(
                all(item.asset_id == "hunyuan_office_chair_v1" for item in chairs)
            )
            scene = GeometryCompiler(asset_registry=registry).compile(city)
            chair_ids = {item.id for item in chairs}
            resolved = [
                primitive
                for primitive in scene.primitives
                if primitive.owner_id in chair_ids
                and primitive.metadata.get("resolved_asset")
            ]
            self.assertEqual(len(resolved), len(chairs))

    def test_resolver_only_invokes_explicit_provider_after_local_miss(self):
        class Generator:
            name = "local_generator"

            def __init__(self):
                self.calls = 0

            def acquire(self, query, *, category=None, dimensions_m=None):
                self.calls += 1
                return AssetRecord(
                    asset_id="generated_lamp_v1",
                    category=category or "lamp",
                    tags=(query, "generated"),
                    geometry_path="lamp.usda",
                    source=self.name,
                )

        provider = Generator()
        registry = AssetRegistry()
        resolver = AssetResolver(registry, [provider])
        record = resolver.resolve("novel lamp", category="lamp")
        self.assertEqual(record.asset_id, "generated_lamp_v1")
        self.assertEqual(provider.calls, 1)
        self.assertIs(registry.get("generated_lamp_v1"), record)
        resolver.resolve("novel lamp", category="lamp")
        self.assertEqual(provider.calls, 1)

    def test_generated_asset_inherits_bounded_context_tags(self):
        class Generator:
            name = "local_generator"

            def acquire(self, query, *, category=None, dimensions_m=None):
                return AssetRecord(
                    asset_id="generated_reception_desk",
                    category=category or "desk",
                    geometry_path="desk.glb",
                )

        resolver = AssetResolver(AssetRegistry(), [Generator()])
        record = resolver.resolve(
            "reception desk",
            category="reception_desk",
            environment="indoor",
            room_type="reception",
        )
        self.assertEqual(record.environment, "indoor")
        self.assertIn("reception", record.room_types)
        self.assertIn("indoor", record.tags)

    def test_resolver_bounds_provider_calls_and_negative_caches_failures(self):
        class FailingGenerator:
            name = "failing_generator"

            def __init__(self):
                self.calls = 0

            def acquire(self, query, *, category=None, dimensions_m=None):
                self.calls += 1
                raise RuntimeError("worker unavailable")

        provider = FailingGenerator()
        resolver = AssetResolver(
            AssetRegistry(),
            [provider],
            max_provider_calls=1,
            strict_provider_errors=False,
        )
        self.assertIsNone(resolver.resolve("chair", category="chair"))
        self.assertIsNone(resolver.resolve("chair", category="chair"))
        self.assertIsNone(resolver.resolve("table", category="table"))
        self.assertEqual(provider.calls, 1)
        stats = resolver.stats()
        self.assertEqual(stats["provider_calls"], 1)
        self.assertEqual(stats["generated_assets"], 0)
        self.assertEqual(stats["budget_skips"], 1)
        self.assertEqual(len(stats["failures"]), 1)

    def test_registry_roundtrip_and_deterministic_search(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "asset_registry.json"
            registry = AssetRegistry(path)
            registry.register(
                AssetRecord(
                    asset_id="chair_modern_black_v1",
                    category="office_chair",
                    tags=("chair", "modern", "black"),
                    dimensions_m=(0.6, 0.6, 1.0),
                    source="generated",
                    license_id="model-license",
                    quality_score=0.9,
                )
            )
            registry.register(
                AssetRecord(
                    asset_id="chair_wood_v1",
                    category="dining_chair",
                    tags=("chair", "wood"),
                    dimensions_m=(0.5, 0.5, 0.9),
                )
            )
            restored = AssetRegistry(path)
            results = restored.search("modern black chair", limit=2)
            self.assertEqual(results[0][0].asset_id, "chair_modern_black_v1")
            self.assertEqual(restored.require("chair_wood_v1").category, "dining_chair")
            payload = json.loads(path.read_text())
            self.assertEqual(payload["schema_version"], "cityg.assets.v1")

    def test_material_library_roundtrip_preserves_color_fallback(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "material_library.json"
            library = MaterialLibrary(path)
            library.register(
                MaterialRecord(
                    material_id="furniture_wood",
                    display_color=(0.4, 0.2, 0.1),
                    roughness=0.72,
                    source="generated",
                    license_id="internal",
                )
            )
            restored = MaterialLibrary(path)
            material = restored.get("furniture_wood")
            self.assertIsNotNone(material)
            self.assertEqual(material.display_color, (0.4, 0.2, 0.1))
            self.assertFalse(material.has_pbr_textures)

    def test_normalized_usd_asset_replaces_procedural_furniture_proxy(self):
        city = BaselineCityPlanner().plan(
            CitySpec(
                name="asset_mesh_test",
                width_m=180,
                depth_m=160,
                building_count=1,
                min_floors=1,
                max_floors=1,
                rooms_per_floor=2,
                seed=3,
            )
        )
        obj = next(city.iter_objects())
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "chair.usda"
            source.write_text(
                '#usda 1.0\ndef Xform "Asset" {}\n', encoding="utf-8"
            )
            registry = AssetRegistry()
            registry.register(
                AssetRecord(
                    asset_id=obj.asset_id,
                    category=obj.category,
                    tags=(obj.category,),
                    geometry_path=str(source),
                    material_id="furniture_blue",
                    source="generated",
                    license_id="internal",
                ),
                overwrite=True,
            )
            scene = GeometryCompiler(asset_registry=registry).compile(city)
            resolved = [
                item
                for item in scene.primitives
                if item.owner_id == obj.id and item.metadata.get("resolved_asset")
            ]
            self.assertEqual(len(resolved), 1)
            self.assertEqual(resolved[0].primitive_type, "mesh")
            self.assertEqual(resolved[0].metadata["asset_source"], "generated")

            output = Path(temporary) / "usd"
            UsdaWriter().write(city, scene, output)
            floor_layers = list((output / "layers" / "floors").glob("*.usda"))
            floor_text = "\n".join(path.read_text(encoding="utf-8") for path in floor_layers)
            self.assertIn("assetGeometryPath", floor_text)
            self.assertIn("assets/", floor_text)
            self.assertTrue(list((output / "assets").glob("*.usda")))


if __name__ == "__main__":
    unittest.main()
