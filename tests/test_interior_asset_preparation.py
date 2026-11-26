import json
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.prepare_interior_assets import build_plan, prepare_indoor_record, prepare, verify_source, apply_review
from scripts.prepare_exterior_assets import local_files
from test_exterior_asset_preparation import source_fixture


class InteriorAssetPreparationTests(unittest.TestCase):
    def test_indoor_record_keeps_provenance_without_outdoor_taxonomy(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp)
            source_fixture(stage)
            path = stage/"sources/test_bench/test_bench_1k.gltf"
            entry = {"id": "test_bench", "category": "desk_lamp", "height_m": .4,
                     "tags": ["lamp"], "room_types": ["office"], "files": local_files(path)}
            record = prepare_indoor_record(entry, "1k", stage, 120000)
            self.assertEqual(record.environment, "indoor")
            self.assertEqual(record.room_types, ("office",))
            self.assertEqual(record.metadata["placement_kind"], "surface")
            self.assertFalse(record.metadata["runtime_enabled"])
            self.assertNotIn("outdoor", record.tags)
            self.assertNotIn("outdoor_pack_status", record.metadata)
            self.assertEqual(record.metadata["indoor_pack_status"], "candidate")
            self.assertTrue(record.metadata["output_sha256"])
            self.assertTrue(record.asset_id.startswith("interior_polyhaven_"))

    def test_curated_longest_side_preserves_proportions(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp)
            source_fixture(stage)
            path = stage/"sources/test_bench/test_bench_1k.gltf"
            entry = {"id": "test_bench", "category": "pencil", "height_m": .4,
                     "tags": [], "room_types": ["office"], "files": local_files(path),
                     "placement_kind": "surface"}
            original = prepare_indoor_record(entry, "1k", stage, 120000)
            sized = prepare_indoor_record({**entry, "longest_side_m": .18}, "1k", stage, 120000)
            self.assertAlmostEqual(max(sized.dimensions_m), .18)
            self.assertAlmostEqual(original.dimensions_m[0]/original.dimensions_m[1],
                                   sized.dimensions_m[0]/sized.dimensions_m[1])
            for invalid in (0, -1, float("nan")):
                with self.assertRaises(ValueError):
                    prepare_indoor_record({**entry, "longest_side_m": invalid}, "1k", stage, 120000)

    def test_deferred_source_is_verified_and_reported_without_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp)
            source_fixture(stage)
            path = stage/"sources/test_bench/test_bench_1k.gltf"
            entry = {"id": "test_bench", "files": local_files(path)}
            (stage/"download_plan.json").write_text(json.dumps({"resolution": "1k", "assets": [entry]}))
            config = {"resolution": "1k", "max_runtime_triangles": 1000,
                      "assets": [{"id": "test_bench", "defer_reason": "animation needs review"}]}
            prepare(config, stage)
            audit = json.loads((stage/"audit.json").read_text())
            self.assertEqual(audit["candidate_count"], 0)
            self.assertEqual(len(audit["pending_conversion"]), 1)
            self.assertFalse(audit["production_registry_changed"])
            path.write_text("changed")
            with self.assertRaises(ValueError): verify_source(entry, stage)

    def test_blend_sources_are_acquired_not_silently_dropped(self):
        blob = {"url": "https://dl.polyhaven.org/test.blend", "md5": "a"*32, "size": 10,
                "include": {"textures/diff.png": {"url": "https://dl.polyhaven.org/diff.png", "md5": "b"*32, "size": 20}}}
        config = {"assets": [{"id": "books"}], "resolution": "1k", "max_download_mib": 1}
        with tempfile.TemporaryDirectory() as tmp, patch("scripts.prepare_interior_assets.metadata", return_value={"blend": {"1k": {"blend": blob}}}):
            plan = build_plan(config, Path(tmp))
            self.assertEqual(plan["assets"][0]["source_format"], "blend")
            self.assertEqual(plan["total_bytes"], 30)
            self.assertIn("books_1k.blend", plan["assets"][0]["files"])
            config["max_download_mib"] = 0
            with self.assertRaises(ValueError): build_plan(config, Path(tmp))

    def test_config_is_bounded_and_has_function_tags(self):
        config = json.loads(Path("configs/interior_asset_pack.json").read_text())
        self.assertLessEqual(config["max_download_mib"], 2200)
        self.assertEqual(len({e["id"] for e in config["assets"]}), len(config["assets"]))
        self.assertTrue(all(e["room_types"] and e["height_m"] > 0 for e in config["assets"]))

    def test_review_is_snapshot_bound_and_never_promotes(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp)
            record = source_fixture(stage)
            preview = stage/"review/previews"/f"{record.asset_id}.png"
            preview.parent.mkdir(parents=True)
            preview.write_bytes(b"test-preview")
            candidate = stage/"candidate_registry.json"
            original = candidate.read_bytes()
            hashes = {record.asset_id: hashlib.sha256(preview.read_bytes()).hexdigest()}
            config = {"candidate_registry_sha256": hashlib.sha256(original).hexdigest(),
                      "previews_sha256": hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest(),
                      "decisions": [{"sources": ["test_bench"], "status": "visual_checked", "note": "fixture"}]}
            apply_review(stage, config)
            self.assertEqual(candidate.read_bytes(), original)
            decision = json.loads((stage/"visual_review.json").read_text())["assets"][record.asset_id]
            self.assertFalse(decision["runtime_enabled"])
            preview.write_bytes(b"changed-preview")
            with self.assertRaisesRegex(ValueError, "Preview snapshot"):
                apply_review(stage, config)
            candidate.write_bytes(original+b" ")
            with self.assertRaisesRegex(ValueError, "Candidate snapshot"):
                apply_review(stage, config)


if __name__ == "__main__": unittest.main()
