import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cityg.asset_curation import _read_gltf
from cityg.assets import AssetRecord, AssetRegistry
from cityg.facade_runtime import _selected_bounds
from cityg.geometry.asset_fitting import fit_outdoor_asset, outdoor_asset_ground_offset
from cityg.geometry.model import Vec3
from scripts.prepare_exterior_assets import (
    acquire, assemble_roots, build_plan, bundle_files, checked_url, local_files, local_source,
    prepare_record, promote, safe_relative,
)


def source_fixture(staging, *, manual=False, budget=200000):
    directory = staging / "sources/test_bench"
    directory.mkdir(parents=True)
    document = {
        "asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, "translation": [7, 2, -4], "scale": [2, 3, 4]}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}],
        "accessors": [{"componentType": 5126, "count": 3, "type": "VEC3",
                       "min": [-1, 0, -.5], "max": [1, 1, .5]}],
    }
    path = directory / "test_bench_1k.gltf"
    path.write_text(json.dumps(document))
    entry = {"id": "test_bench", "category": "street_bench", "tags": ["bench"],
             "contexts": ["park"], "height_m": .9, "manual_only": manual,
             "files": {path.name: {"md5": hashlib.md5(path.read_bytes()).hexdigest(),
                                   "size": path.stat().st_size}}}
    record = prepare_record(entry, "1k", staging, budget)
    AssetRegistry(staging / "candidate_registry.json").register(record)
    return record


class ExteriorAssetPreparationTests(unittest.TestCase):
    def test_explicit_material_exclusion_rejects_unknown_and_whole_mesh(self):
        from scripts.prepare_exterior_assets import exclude_material_primitives
        doc = {'materials':[{'name':'frame'},{'name':'glass'}],
               'meshes':[{'primitives':[{'material':0},{'material':1}]}]}
        exclude_material_primitives(doc, ['glass'])
        self.assertEqual(doc['meshes'][0]['primitives'], [{'material':0}])
        for names in (['missing'], ['frame'], 'glass'):
            with self.assertRaises(ValueError):exclude_material_primitives(doc, names)
        self.assertEqual(doc['meshes'][0]['primitives'], [{'material':0}])

    def test_kit_assembly_is_explicit_and_preserves_rotation(self):
        document = {"nodes": [{"name": "leg", "rotation": [0, 0, 0, 1]}]}
        assemble_roots(document, [0], {"leg": [1, 2, 3]})
        self.assertEqual(document["nodes"][0]["translation"], [1, 2, 3])
        self.assertEqual(document["nodes"][0]["rotation"], [0, 0, 0, 1])
        for transforms in ({"missing": [1, 2, 3]}, {"leg": [float("nan"), 2, 3]}, {"leg": [1]}):
            with self.assertRaises(ValueError):
                assemble_roots(document, [0], transforms)
        document["nodes"][0]["matrix"] = [1] * 16
        with self.assertRaises(ValueError):
            assemble_roots(document, [0], {"leg": [1, 2, 3]})

    def test_local_reuse_keeps_provider_and_avoids_network_or_source_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original_stage = root / "assets/original"
            source_fixture(original_stage)
            source = original_stage / "sources/test_bench/test_bench_1k.gltf"
            entry = {"id": "reused", "local_source": str(source.relative_to(root)),
                     "provider": "opengameart", "license_id": "CC0-1.0",
                     "source_url": "https://opengameart.org/content/test", "height_m": .9,
                     "category": "street_bench", "tags": ["bench"], "contexts": ["park"],
                     "style": "textured_low_poly", "quality_score": .86}
            config = {"assets": [entry], "resolution": "1k", "max_download_mib": 0}
            stage = root / "assets/reused"
            with patch("scripts.prepare_exterior_assets.ROOT", root), patch("scripts.prepare_exterior_assets.fetch") as fetch:
                plan = build_plan(config, stage)
                self.assertEqual(plan["total_bytes"], 0)
                acquire(plan, stage)
                record = prepare_record(plan["assets"][0], "1k", stage, 200000)
                fetch.assert_not_called()
                self.assertEqual(record.asset_id, "prepared_opengameart_reused")
                self.assertEqual(record.source, "opengameart_exterior_prepared")
                self.assertEqual(record.metadata["style"], "textured_low_poly")
                self.assertTrue(source.is_file())
                self.assertFalse((stage / "sources/reused/test_bench_1k.gltf").exists())
                source.write_text(source.read_text() + " ")
                with self.assertRaises(ValueError):
                    prepare_record(plan["assets"][0], "1k", stage, 200000)

    def test_local_reuse_rejects_outputs_and_escaping_dependencies(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch("scripts.prepare_exterior_assets.ROOT", root):
                with self.assertRaises(ValueError):
                    local_source({"local_source": "outputs/model.gltf"})
            path = root / "test.gltf"
            path.write_text(json.dumps({"buffers": [{"uri": "../private.bin"}]}))
            with self.assertRaises(ValueError):
                local_files(path)

    def test_authored_soil_plane_is_not_leaf_card_bottom(self):
        record = AssetRecord("plant", "plant", metadata={"ground_anchor_fraction": .2})
        self.assertAlmostEqual(outdoor_asset_ground_offset(record, Vec3(1, 1, .5)), .1)
    def test_runtime_fit_preserves_proportions_inside_envelope(self):
        record = AssetRecord("bench", "street_bench", dimensions_m=(2, .5, 1),
                             metadata={"preserve_physical_proportions": True})
        size = fit_outdoor_asset(record, Vec3(3, 1, 1))
        self.assertEqual(size, Vec3(2, .5, 1))
        legacy = AssetRecord("old", "street_bench", dimensions_m=(2, .5, 1))
        self.assertEqual(fit_outdoor_asset(legacy, Vec3(3, 1, 1)), Vec3(3, 1, 1))

    def test_quarter_turn_keeps_long_planter_inside_placement(self):
        record = AssetRecord("planter", "street_planter", dimensions_m=(.5, 2, 1),
                             metadata={"preserve_physical_proportions": True, "placement_yaw_offset_deg": 90})
        self.assertEqual(fit_outdoor_asset(record, Vec3(2, .5, 1)), Vec3(.5, 2, 1))

    def test_explicit_node_group_removes_unrelated_objects(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp)
            source_fixture(stage)
            path = stage / "sources/test_bench/test_bench_1k.gltf"
            document = json.loads(path.read_text())
            document["nodes"][0]["name"] = "selected"
            document["nodes"].append({"name": "unrelated", "mesh": 0, "translation": [100, 0, 0]})
            document["scenes"][0]["nodes"].append(1)
            path.write_text(json.dumps(document))
            entry = {"id": "test_bench", "key": "single", "nodes": ["selected"],
                     "category": "street_bench", "height_m": .9, "tags": ["bench"], "contexts": ["park"],
                     "files": {path.name: {"md5": hashlib.md5(path.read_bytes()).hexdigest(), "size": path.stat().st_size}}}
            record = prepare_record(entry, "1k", stage, 200000)
            self.assertAlmostEqual(record.dimensions_m[1], 1.2)
            result, _ = _read_gltf(stage / record.geometry_path)
            self.assertNotIn("unrelated", [node.get("name") for node in result["nodes"]])
            entry["nodes"] = ["does_not_exist"]
            with self.assertRaises(ValueError):
                prepare_record(entry, "1k", stage, 200000)

    def test_preparing_changed_source_does_not_overwrite_prior_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp)
            first = source_fixture(stage)
            original_path = stage / first.geometry_path
            original_bytes = original_path.read_bytes()
            path = stage / "sources/test_bench/test_bench_1k.gltf"
            document = json.loads(path.read_text())
            document["nodes"][0]["name"] = "updated-source"
            path.write_text(json.dumps(document))
            entry = {"id": "test_bench", "category": "street_bench", "height_m": .9,
                     "tags": ["bench"], "contexts": ["park"],
                     "files": {path.name: {"md5": hashlib.md5(path.read_bytes()).hexdigest(), "size": path.stat().st_size}}}
            second = prepare_record(entry, "1k", stage, 200000)
            self.assertNotEqual(first.geometry_path, second.geometry_path)
            self.assertEqual(original_path.read_bytes(), original_bytes)

    def test_dependency_paths_cannot_escape(self):
        for name in ("../secret", "/tmp/secret", "C:/secret", "textures\\secret", ""):
            with self.subTest(name=name), self.assertRaises(ValueError):
                safe_relative(name)
        self.assertEqual(safe_relative("textures/a.jpg"), Path("textures/a.jpg"))

    def test_only_https_provider_hosts(self):
        for url in ("http://dl.polyhaven.org/a", "https://evil.example/a",
                    "https://dl.polyhaven.org.evil.example/a", "https://user@dl.polyhaven.org/a"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                checked_url(url)

    def test_bundle_checks_dependencies(self):
        files = {"gltf": {"1k": {"gltf": {"url": "https://dl.polyhaven.org/a.gltf",
                  "md5": "a" * 32, "size": 100, "include": {
                      "../../secret": {"url": "https://dl.polyhaven.org/a.bin", "md5": "b" * 32, "size": 5}}}}}}
        with self.assertRaises(ValueError):
            bundle_files("test", files, "1k")

    def test_download_budget_fails_before_payload_download(self):
        with tempfile.TemporaryDirectory() as tmp:
            files = {"gltf": {"1k": {"gltf": {"url": "https://dl.polyhaven.org/a.gltf",
                     "md5": "a" * 32, "size": 2 * 1024**2}}}}
            config = {"assets": [{"id": "test"}], "resolution": "1k", "max_download_mib": 1}
            with patch("scripts.prepare_exterior_assets.metadata", return_value=files), self.assertRaises(ValueError):
                build_plan(config, Path(tmp))

    def test_world_bounds_normalized_and_physical_proportions_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = source_fixture(root)
            document, _ = _read_gltf(root / record.geometry_path)
            low, high = _selected_bounds(document, document["scenes"][0]["nodes"])
            for axis in range(3):
                self.assertAlmostEqual(low[axis], -.5)
                self.assertAlmostEqual(high[axis], .5)
            self.assertEqual(record.metadata["outdoor_pack_status"], "candidate")
            self.assertAlmostEqual(record.dimensions_m[0], 1.2)
            self.assertAlmostEqual(record.dimensions_m[1], 1.2)
            self.assertAlmostEqual(record.dimensions_m[2], .9)

    def test_promotion_is_additive_and_backs_up(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stage = root / "stage"
            record = source_fixture(stage)
            production = root / "production.json"
            AssetRegistry(production).register(AssetRecord("existing", "vehicle"))
            original = production.read_bytes()
            self.assertEqual(promote(stage, production, [record.asset_id], "Four views inspected", 200000), 1)
            registry = AssetRegistry(production)
            self.assertIsNotNone(registry.get("existing"))
            imported = registry.require(record.asset_id)
            self.assertEqual(imported.metadata["outdoor_pack_status"], "ready")
            self.assertTrue(registry.resolve_path(imported.geometry_path).is_file())
            self.assertEqual(next((stage / "registry_backups").glob("*.json")).read_bytes(), original)

    def test_manual_bundles_cannot_be_promoted_as_single_props(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = source_fixture(root / "stage", manual=True)
            with self.assertRaises(ValueError):
                promote(root / "stage", root / "prod.json", [record.asset_id], "review", 200000)
            self.assertFalse((root / "prod.json").exists())

    def test_high_poly_and_unreviewed_assets_are_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = source_fixture(root / "stage")
            with self.assertRaises(ValueError):
                promote(root / "stage", root / "prod.json", [record.asset_id], "review", 0)
            with self.assertRaises(ValueError):
                promote(root / "stage", root / "prod.json", [record.asset_id], "", 200000)

    def test_tampered_candidate_is_not_promoted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = source_fixture(root / "stage")
            (root / "stage" / record.geometry_path).write_bytes(b"changed")
            with self.assertRaises(ValueError):
                promote(root / "stage", root / "prod.json", [record.asset_id], "review", 200000)


if __name__ == "__main__":
    unittest.main()
