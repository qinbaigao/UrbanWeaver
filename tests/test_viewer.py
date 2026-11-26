import json
import tempfile
import unittest
from pathlib import Path

from cityg.planning import BaselineCityPlanner
from cityg.schemas import CitySpec
from cityg.serialization import save_json
from cityg.viewer import (
    build_viewer_dataset,
    export_portable_viewer,
    viewer_static_dir,
)


class ViewerTests(unittest.TestCase):
    def test_city_manifest_is_compiled_in_memory(self):
        city = BaselineCityPlanner().plan(
            CitySpec(
                name="viewer_test",
                width_m=180,
                depth_m=160,
                building_count=2,
                min_floors=1,
                max_floors=2,
                rooms_per_floor=2,
            )
        )
        with tempfile.TemporaryDirectory() as temporary:
            city_path = save_json(city, Path(temporary) / "city.json")
            dataset = build_viewer_dataset(city_path)
        self.assertEqual(dataset.source, "derived_in_memory")
        self.assertIn("geometry_manifest.json", dataset.files)
        geometry = json.loads(dataset.files["geometry_manifest.json"])
        self.assertTrue(geometry["primitives"])
        self.assertTrue(json.loads(dataset.files["geometry_validation_report.json"])["ok"])

    def test_compiled_directory_is_loaded_without_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "geometry_manifest.json").write_text('{"primitives": []}')
            (root / "city.json").write_text('{"id": "test"}')
            dataset = build_viewer_dataset(root)
        self.assertEqual(dataset.source, "compiled_manifests")
        self.assertEqual(json.loads(dataset.files["city.json"])["id"], "test")

    def test_compiled_glb_asset_is_exposed_and_exported(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "geometry_manifest.json").write_text('{"primitives": []}')
            (root / "city.json").write_text('{"id": "test"}')
            assets = root / "assets"
            assets.mkdir()
            (assets / "chair.glb").write_bytes(b"glTF-test")
            (assets / "asset_registry.json").write_text(json.dumps({
                "schema_version": "cityg.assets.v1",
                "assets": [{
                    "asset_id": "demo_chair",
                    "category": "office_chair",
                    "geometry_path": "chair.glb",
                }],
            }))
            dataset = build_viewer_dataset(root)
            self.assertEqual(dataset.assets["demo_chair"], b"glTF-test")
            output = export_portable_viewer(root, root / "portable_viewer")
            self.assertEqual((output / "assets" / "demo_chair.glb").read_bytes(), b"glTF-test")

    def test_bundled_frontend_exists_after_build(self):
        index = viewer_static_dir() / "index.html"
        self.assertTrue(index.is_file())
        html = index.read_text()
        self.assertIn('id="quality-select"', html)
        self.assertIn('value="review"', html)
        self.assertIn('value="high_fidelity"', html)
        self.assertIn('id="high-fidelity-toggle"', html)
        self.assertIn('id="camera-high-fidelity"', html)
        self.assertIn('id="floor-camera-presets"', html)
        self.assertIn('data-floor-camera="corridor"', html)

    def test_material_textures_are_packaged_for_portable_viewer(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            texture = root / "brick.png"
            texture.write_bytes(b"png-test")
            (root / "geometry_manifest.json").write_text(json.dumps({
                "primitives": [],
                "materials": [{
                    "id": "brick",
                    "base_color_path": str(texture),
                    "normal_path": None,
                    "roughness_path": None,
                }],
            }))
            (root / "city.json").write_text('{"id": "texture_test"}')
            dataset = build_viewer_dataset(root)
            self.assertEqual(dataset.textures["brick_base_color.png"], b"png-test")
            self.assertEqual(
                dataset.material_textures["brick"]["base_color"],
                "brick_base_color.png",
            )

    def test_portable_export_contains_scene_and_launcher(self):
        city = BaselineCityPlanner().plan(
            CitySpec(name="portable", width_m=140, depth_m=140, building_count=1)
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            city_path = save_json(city, root / "city.json")
            output = export_portable_viewer(city_path, root / "portable_viewer")
            self.assertTrue((output / "index.html").is_file())
            self.assertIn('id="export-render-view-button"', (output / "index.html").read_text())
            self.assertIn('Export render view', (output / "index.html").read_text())
            self.assertTrue((output / "scene" / "geometry_manifest.json").is_file())
            self.assertTrue((output / "serve.py").is_file())
            launcher = (output / "serve.py").read_text()
            self.assertIn('"--open-browser"', launcher)
            self.assertIn('"--no-browser"', launcher)
            self.assertIn("default=True", launcher)
            self.assertIn("if args.open_browser:", launcher)
            self.assertLess(
                launcher.index("if args.open_browser:"),
                launcher.index(
                    "threading.Timer(0.3, lambda: webbrowser.open(url)).start()"
                ),
            )
            config = json.loads((output / "viewer-config.json").read_text())
            self.assertEqual(config["source"], "portable_export")


if __name__ == "__main__":
    unittest.main()
