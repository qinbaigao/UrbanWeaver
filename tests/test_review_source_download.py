import hashlib
import tempfile
import unittest
from pathlib import Path

from scripts.download_review_sources import blob_hash, select_files


def item(path, *, mode="100644"):
    return {"type": "blob", "path": path, "mode": mode, "sha": "a" * 40, "size": 10}


class ReviewSourceDownloadTests(unittest.TestCase):
    def test_exact_files_and_texture_patterns(self):
        tree = {"tree": [item("A/model.fbx"), item("A/textures/body.tga"), item("B/model.fbx")]}
        group = {"id": "a", "files": ["A/model.fbx"], "patterns": ["A/textures/*.tga"]}
        self.assertEqual([i["path"] for i in select_files(tree, group)], ["A/model.fbx", "A/textures/body.tga"])

    def test_missing_and_empty_patterns_are_not_success(self):
        tree = {"tree": [item("model.glb")]}
        for group in ({"id": "a", "files": ["missing.glb"]},
                      {"id": "a", "files": ["model.glb"], "patterns": ["textures/*.png"]}):
            with self.assertRaises(ValueError):
                select_files(tree, group)

    def test_reject_truncation_symlinks_and_escape_paths(self):
        for tree, name in (({"truncated": True, "tree": []}, "a.glb"),
                           ({"tree": [item("a.glb", mode="120000")]}, "a.glb"),
                           ({"tree": [item("../a.glb")]}, "../a.glb")):
            with self.assertRaises(ValueError):
                select_files(tree, {"id": "a", "files": [name]})

    def test_license_without_mesh_does_not_count_as_downloaded_model(self):
        with self.assertRaises(ValueError):
            select_files({"tree": [item("LICENSE")]}, {"id": "a", "files": ["LICENSE"]})

    def test_git_blob_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "data"
            path.write_bytes(b"hello")
            self.assertEqual(blob_hash(path), hashlib.sha1(b"blob 5\0hello").hexdigest())

    def test_upstream_executable_image_bit_is_inert_but_scripts_rejected(self):
        tree = {"tree": [item("a/model.obj"), item("a/texture.png", mode="100755")]}
        self.assertEqual(len(select_files(tree, {"id": "a", "patterns": ["a/*"]})), 2)
        tree["tree"].append(item("a/run.py", mode="100755"))
        with self.assertRaises(ValueError):
            select_files(tree, {"id": "a", "patterns": ["a/*"]})


if __name__ == "__main__":
    unittest.main()
