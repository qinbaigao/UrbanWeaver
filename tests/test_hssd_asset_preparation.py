import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from scripts.prepare_hssd_assets import (align_document, dimensions, select_assets,
    validate_plan, verify_file, prepare_one, gallery, review, LICENSE)
from cityg.asset_curation import _read_gltf, _write_glb
from cityg.assets import AssetRegistry
from test_exterior_asset_preparation import source_fixture


class HssdAssetPreparationTests(unittest.TestCase):
    def row(self, n=1, **values):
        return {"id": f"{n:040x}", "name": "Office furniture", "wnsynsetkey": "desk.n.01",
                "aligned.dims": "2,1,1", "up": "", "front": "", "hasMultipleObjects": "false", **values}

    def config(self):
        return {"seed": "test", "max_asset_bytes": 1000, "max_download_bytes": 2000,
                "categories": [{"category": "desk", "count": 3, "synsets": ["desk.n.01"],
                                "room_types": ["office"], "placement_kind": "floor"}]}

    def test_bounded_selection_excludes_bundles_outdoor_and_duplicate_clusters(self):
        rows = [self.row(1, simClusterIds="same"), self.row(2, simClusterIds="same"),
                self.row(3, hasMultipleObjects="true"), self.row(4, name="Outdoor table"),
                self.row(5, decomposedFrom="parent"), self.row(6)]
        files = {r["id"]: {"size": 900} for r in rows}
        chosen, gaps = select_assets(rows, files, self.config())
        self.assertEqual(len(chosen), 2)
        self.assertIn(f"{6:040x}", [e["id"] for e in chosen])
        self.assertEqual(gaps[0]["selected"], 2)
        again, _ = select_assets(list(reversed(rows)), files, self.config())
        self.assertEqual(chosen, again)

    def test_invalid_dimensions_and_size_rejected(self):
        for text in ("1,nan,2", "1,0,2", "1,2", "-1,2,3"):
            with self.assertRaises(ValueError): dimensions({"aligned.dims": text})
        row = self.row()
        selected, _ = select_assets([row], {row["id"]: {"size": 1001}}, self.config())
        self.assertEqual(selected, [])

    def fixture(self, stage):
        source_fixture(stage)
        path = stage/"sources/test_bench/test_bench_1k.gltf"
        document, buffers = _read_gltf(path)
        data = _write_glb(document, buffers, path.parent)
        row = self.row()
        target = stage/"sources/objects"/(row["id"] + ".glb")
        target.parent.mkdir(parents=True); target.write_bytes(data)
        entry = {"id": row["id"], "category": "desk", "room_types": ["office"],
                 "placement_kind": "floor", "metadata": row,
                 "file": {"path": "objects/" + target.name, "size": len(data),
                          "sha256": hashlib.sha256(data).hexdigest()}}
        plan = {"models_repo": "hssd/hssd-models", "models_revision": "a"*40,
                "metadata_revision": "b"*40, "license_id": LICENSE,
                "max_download_bytes": 2000000000, "metadata_bytes": 0,
                "source_bytes": len(data), "max_runtime_triangles": 120000,
                "selection_config": {"max_asset_bytes": 30000000}, "assets": [entry]}
        return target, entry, plan

    def test_plan_and_file_integrity(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, entry, plan = self.fixture(Path(tmp))
            validate_plan(plan); verify_file(path, entry)
            for change in ({"source_bytes": 0}, {"max_download_bytes": 1}, {"models_revision": "main"}):
                with self.assertRaises(ValueError): validate_plan({**plan, **change})
            bad = copy.deepcopy(plan); bad["assets"][0]["file"]["path"] = "../other.glb"
            with self.assertRaises(ValueError): validate_plan(bad)
            path.write_bytes(path.read_bytes()[:-1] + b"x")
            with self.assertRaises(ValueError): verify_file(path, entry)

    def test_alignment_rotates_metadata_axes_and_flags_defaults(self):
        document = {"nodes": [{}], "scenes": [{"nodes": [0]}]}
        status = align_document(document, {"up": "0,0,-1", "front": "0,1,0"})
        matrix = np.array(document["nodes"][-1]["matrix"]).reshape(4,4).T[:3,:3]
        np.testing.assert_allclose(matrix @ [0,0,-1], [0,1,0])
        np.testing.assert_allclose(matrix @ [0,1,0], [0,0,1])
        self.assertAlmostEqual(np.linalg.det(matrix), 1)
        self.assertEqual(status, "source_metadata_unreviewed")
        self.assertEqual(align_document({"nodes": [{}], "scenes": [{"nodes": [0]}]}, {}), "assumed_gltf_axes_unreviewed")
        with self.assertRaises(ValueError):
            align_document(document, {"up": "0,1,0", "front": "0,1,0"})

    def test_candidate_license_is_not_cc0_and_never_auto_enabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp); _, entry, plan = self.fixture(stage)
            record = prepare_one(entry, plan, stage)
            self.assertEqual(record.license_id, LICENSE)
            self.assertFalse(record.metadata["runtime_enabled"])
            self.assertEqual(record.metadata["redistribution_policy"], "user_download_required")
            self.assertEqual(record.room_types, ("office",))
            self.assertEqual(record.metadata["support_annotation_status"], "unreviewed")
            registry = AssetRegistry(); registry.register(record)
            self.assertEqual(registry.search("desk", category="desk"), [])
            self.assertEqual(prepare_one(entry, plan, stage).metadata["output_sha256"], record.metadata["output_sha256"])
            (stage/"candidate_registry.json").write_text(json.dumps({"assets": [record.to_dict()]}))
            gallery(stage)
            page = (stage/"gallery/index.html").read_text()
            self.assertIn("CC BY-NC 4.0", page)
            self.assertNotIn("CC0", page)

    def test_production_config_is_bounded(self):
        cfg = json.loads(Path("configs/hssd_asset_pack.json").read_text())
        self.assertLessEqual(cfg["max_download_bytes"], 2000000000)
        self.assertLessEqual(sum(s["count"] for s in cfg["categories"]), 200)
        self.assertEqual(len({s["category"] for s in cfg["categories"]}), len(cfg["categories"]))

    def test_review_rejects_changed_previews_and_never_promotes(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp); _, entry, plan = self.fixture(stage)
            record = prepare_one(entry, plan, stage)
            candidate = stage/"candidate_registry.json"
            candidate.write_text(json.dumps({"assets": [record.to_dict()]}))
            preview = stage/"review/previews"/(record.asset_id + ".png")
            preview.parent.mkdir(parents=True); preview.write_bytes(b"observed-image")
            original = candidate.read_bytes()
            config = {"candidate_registry_sha256": hashlib.sha256(original).hexdigest(),
                      "decisions": [{"asset_id": record.asset_id, "status": "visual_checked",
                                     "note": "fixture", "preview_sha256": hashlib.sha256(preview.read_bytes()).hexdigest()}]}
            review(stage, config)
            self.assertEqual(original, candidate.read_bytes())
            self.assertFalse(json.loads((stage/"visual_review.json").read_text())["assets"][record.asset_id]["runtime_enabled"])
            preview.write_bytes(b"changed-image")
            with self.assertRaises(ValueError): review(stage, config)
            gallery(stage)
            self.assertIn("旧验收失效", (stage/"gallery/index.html").read_text())


if __name__ == "__main__":
    unittest.main()
