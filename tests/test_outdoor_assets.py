import json
import tempfile
import unittest
from pathlib import Path

from cityg.assets import AssetRecord, AssetRegistry
from cityg.outdoor_assets import (
    OutdoorAssetPackBuilder,
    default_outdoor_slots,
    import_outdoor_asset,
)


class OutdoorAssetPackTests(unittest.TestCase):
    def test_pack_audits_a_semantically_tagged_glb(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            geometry = root / "bench.glb"
            geometry.write_bytes(b"glTF" + b"\x00" * 20)
            registry = AssetRegistry(root / "asset_registry.json")
            registry.register(
                AssetRecord(
                    asset_id="curated_bench_v1",
                    category="street_bench",
                    tags=("public", "street", "bench", "wood", "metal"),
                    dimensions_m=(1.9, 0.62, 0.86),
                    geometry_path=str(geometry),
                    source="curated_test_pack",
                    license_id="CC0-1.0",
                    quality_score=0.9,
                )
            )
            slot = next(
                item for item in default_outdoor_slots()
                if item.slot_id == "street_bench_wood_metal"
            )
            output = root / "outdoor" / "pack.json"
            payload = OutdoorAssetPackBuilder(registry).build(output, slots=(slot,))
            self.assertEqual(payload["summary"]["ready_count"], 1)
            tagged = registry.require("curated_bench_v1")
            self.assertEqual(tagged.metadata["outdoor_slot"], slot.slot_id)
            self.assertEqual(tagged.metadata["outdoor_pack_status"], "ready")
            self.assertEqual(json.loads(output.read_text())["schema_version"], "cityg.outdoor_assets.v1")

    def test_generation_policy_keeps_people_vehicles_and_trees_curated_first(self):
        slots = {item.slot_id: item for item in default_outdoor_slots()}
        self.assertFalse(slots["street_tree_deciduous"].generation_allowed)
        self.assertFalse(slots["sedan_modern"].generation_allowed)
        self.assertFalse(slots["pedestrian_walking"].generation_allowed)
        self.assertTrue(slots["street_bench_wood_metal"].generation_allowed)

    def test_import_copies_asset_into_self_contained_pack(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.glb"
            source.write_bytes(b"glTF" + b"curated")
            registry = AssetRegistry(root / "asset_registry.json")
            record = import_outdoor_asset(
                registry,
                slot_id="bollard_simple",
                geometry=source,
                asset_root=root / "outdoor" / "imported",
                source="example-curated-pack",
                license_id="CC0-1.0",
            )
            self.assertTrue(registry.resolve_path(record.geometry_path).is_file())
            self.assertNotEqual(registry.resolve_path(record.geometry_path), source)
            self.assertEqual(record.metadata["outdoor_slot"], "bollard_simple")

    def test_curated_first_generation_is_candidate_until_review(self):
        class Generator:
            name = "test_generator"

            def acquire(self, query, *, category=None, dimensions_m=None):
                return AssetRecord(
                    asset_id="generated_sedan_candidate",
                    category=category or "vehicle",
                    tags=("vehicle", "sedan"),
                    dimensions_m=dimensions_m,
                    geometry_path="candidate.glb",
                    source="test_generator",
                    license_id="test-license",
                    quality_score=.9,
                    metadata={"texture_status": "generated"},
                )

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "candidate.glb").write_bytes(b"glTF" + b"candidate")
            registry = AssetRegistry(root / "asset_registry.json")
            # Provider paths are resolved against the registry manifest.
            payload = OutdoorAssetPackBuilder(
                registry, providers=(Generator(),), max_generated_assets=1
            ).build(
                root / "pack.json",
                slots=(next(item for item in default_outdoor_slots() if item.slot_id == "sedan_modern"),),
                generate=True,
                force_generation=True,
            )
            self.assertEqual(payload["summary"]["candidate_count"], 1)
            self.assertEqual(registry.require("generated_sedan_candidate").metadata["outdoor_pack_status"], "candidate")


if __name__ == "__main__":
    unittest.main()
