import json
import struct
import tempfile
import unittest
from pathlib import Path

from cityg.asset_curation import (
    ExternalAssetSourceCatalog,
    IncomingAssetCurator,
    _classify,
)
from cityg.assets import AssetRegistry


def _minimal_glb(path: Path) -> None:
    document = {
        "asset": {"version": "2.0"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}],
        "accessors": [
            {
                "componentType": 5126,
                "count": 3,
                "type": "VEC3",
                "min": [-0.75, 0.0, -2.25],
                "max": [0.75, 1.5, 2.25],
            }
        ],
        "buffers": [{"byteLength": 0}],
    }
    payload = json.dumps(document, separators=(",", ":")).encode()
    while len(payload) % 4:
        payload += b" "
    binary = b""
    total = 12 + 8 + len(payload) + 8
    path.parent.mkdir(parents=True)
    path.write_bytes(
        struct.pack("<4sII", b"glTF", 2, total)
        + struct.pack("<II", len(payload), 0x4E4F534A)
        + payload
        + struct.pack("<II", len(binary), 0x004E4942)
    )


class ExternalAssetSourceCatalogTest(unittest.TestCase):
    def test_search_plan_keeps_three_sources_and_ranks_vehicle_search(self):
        plan = ExternalAssetSourceCatalog().search_plan(
            "photorealistic delivery vehicle", category="vehicle"
        )
        self.assertEqual(len(plan["sources"]), 3)
        self.assertEqual(plan["sources"][0]["source_id"], "sketchfab")
        self.assertIn("delivery+vehicle", plan["sources"][0]["search_url"])
        self.assertEqual(
            {item["source_id"] for item in plan["sources"]},
            {"polyhaven", "sketchfab", "khronos_gltf_assets"},
        )


class IncomingAssetCuratorTest(unittest.TestCase):
    def test_street_lamp_is_not_misclassified_as_tree(self):
        classification = _classify(
            "street_lamp_01_1k",
            "polyhaven_outdoor_models",
            {"min": [-0.5, 0.0, -0.5], "max": [0.5, 4.0, 0.5], "extent": [1.0, 4.0, 1.0]},
        )
        self.assertEqual(classification["category"], "street_light")
        self.assertEqual(classification["subtype"], "heritage")

    def test_curates_canonical_external_vehicle_and_ignores_missing_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            incoming = root / "assets" / "incoming"
            source = incoming / "kenney_car-kit" / "Models" / "GLB format" / "sedan.glb"
            _minimal_glb(source)
            (incoming / "kenney_car-kit" / "License.txt").write_text("CC0")
            registry_path = root / "assets" / "asset_registry.json"
            registry = AssetRegistry(registry_path)
            manifest = root / "assets" / "incoming_manifest.json"
            payload = IncomingAssetCurator(
                registry,
                incoming_root=incoming,
                cache_root=root / "assets" / "external_cache",
            ).curate(manifest)

            self.assertEqual(payload["asset_count"], 1)
            record = registry.search("sedan", category="vehicle", require_geometry=True)[0][0]
            self.assertEqual(record.dimensions_m, (4.55, 1.82, 1.48))
            self.assertEqual(record.metadata["orientation"]["canonical_up_axis"], "+Z")
            canonical = registry.resolve_path(record.geometry_path)
            self.assertEqual(canonical.read_bytes()[:4], b"glTF")
            canonical.unlink()
            self.assertEqual(
                registry.search("sedan", category="vehicle", require_geometry=True), []
            )


if __name__ == "__main__":
    unittest.main()
