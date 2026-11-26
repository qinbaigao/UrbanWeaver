import json
import tempfile
import unittest
from pathlib import Path

from cityg.asset_curation import _read_gltf, _write_glb
from cityg.assets import AssetRegistry
from cityg.facade_assets import FacadeAssetIndex
from cityg.facade_runtime import FacadeAssetRuntime, canonical_facade_glb
from cityg.geometry import GeometryCompiler, GeometryValidator
from cityg.planning import BaselineCityPlanner
from cityg.schemas import CitySpec


def _minimal_source(path: Path) -> None:
    document = {
        "asset": {"version": "2.0"},
        "scene": 0,
        "scenes": [{"nodes": [0, 1]}],
        "nodes": [
            {"name": "wanted", "mesh": 0, "translation": [5, 0, 0]},
            {"name": "unrelated", "mesh": 1, "translation": [-20, 0, 0]},
        ],
        "meshes": [
            {"primitives": [{"attributes": {"POSITION": 0}}]},
            {"primitives": [{"attributes": {"POSITION": 1}}]},
        ],
        "accessors": [
            {"componentType": 5126, "count": 3, "type": "VEC3", "min": [-.1, 0, -1], "max": [.1, 2, 1]},
            {"componentType": 5126, "count": 3, "type": "VEC3", "min": [-10, 0, -10], "max": [10, 10, 10]},
        ],
        "buffers": [{"byteLength": 0}],
    }
    path.write_bytes(_write_glb(document, [b""], path.parent))


def _record(path: str, asset_id: str = "facade_test_window") -> dict:
    return {
        "asset_id": asset_id,
        "source_id": "test_pack",
        "source_asset_id": "wanted",
        "display_name": "wanted window",
        "geometry_path": path,
        "selector": {"kind": "gltf_node", "node_index": 0, "node_name": "wanted"},
        "semantic_type": "window_bay",
        "tags": ["window", "realistic"],
        "compatible_building_functions": ["residential", "commercial", "mixed_use", "public_service"],
        "compatible_facade_zones": ["podium", "shaft"],
        "placement": {"mount_surface": "wall"},
        "orientation": {"source_front_axis": "+X", "visual_review_required": False},
        "scale": {"native_extent_xyz": [.2, 2, 2]},
        "repeatability": {"mode": "horizontal_grid", "repeatable": True},
        "appearance": {
            "realism_level": "realistic",
            "pbr_textured": True,
            "compatible_design_languages": ["contemporary_urban"],
        },
        "quality": {"score": .9, "vlm_visual_quality_score": .86},
        "selection_status": "usable",
        "technical": {},
        "provenance": {"license_id": "CC0-1.0"},
    }


class FacadeRuntimeTests(unittest.TestCase):
    def test_registry_rebind_invalidates_prepared_records(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);_minimal_source(root/'source.glb')
            record=_record('source.glb')
            runtime=FacadeAssetRuntime(FacadeAssetIndex({'schema_version':'cityg.facade_asset_annotations.v1','assets':[record]}),AssetRegistry(),
                project_root=root,cache_root=root/'cache')
            runtime.prepare(record)
            original=runtime.asset_registry
            target=AssetRegistry()
            runtime.bind_registry(target)
            prepared=runtime.prepare(record)
            self.assertIs(runtime.asset_registry,target)
            self.assertIs(target.get(prepared.asset_id),prepared)
            self.assertTrue(target.resolve_path(prepared.geometry_path).is_file())
            self.assertEqual(len(original.list_all()),1)

    def test_node_extraction_excludes_unrelated_scene_geometry(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source.glb"
            _minimal_source(source)
            payload = canonical_facade_glb(source, _record(str(source)))
            output = Path(temporary) / "canonical.glb"
            output.write_bytes(payload)
            document, _ = _read_gltf(output)
        self.assertEqual(len(document["meshes"]), 1)
        self.assertEqual(document["asset"]["extras"]["cityg_asset_id"], "facade_test_window")
        self.assertEqual(document["scenes"][0]["nodes"], [1])

    def test_runtime_registers_only_selected_portable_assets(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _minimal_source(root / "source.glb")
            payload = {
                "schema_version": "cityg.facade_asset_annotations.v1",
                "summary": {"asset_count": 1},
                "assets": [_record("source.glb")],
            }
            registry = AssetRegistry(root / "registry.json")
            registry.save()
            runtime = FacadeAssetRuntime(
                FacadeAssetIndex(payload), registry, project_root=root, cache_root=root / "cache"
            )
            city = BaselineCityPlanner().plan(CitySpec(
                name="facade_runtime", width_m=100, depth_m=100,
                building_count=1, min_floors=2, max_floors=2,
                rooms_per_floor=2, seed=2,
            ))
            scene = GeometryCompiler(
                asset_registry=registry, facade_asset_runtime=runtime
            ).compile(city)
            resolved = [
                item for item in scene.primitives
                if item.metadata.get("facade_asset_role") == "window"
            ]
            record = registry.get("facade_test_window")
            self.assertTrue(resolved)
            self.assertIsNotNone(record)
            self.assertTrue(registry.resolve_path(record.geometry_path).is_file())
            self.assertTrue(all(not item.collision_enabled for item in resolved))
            self.assertTrue(GeometryValidator().validate(city, scene).ok)
            self.assertEqual(
                scene.metadata["resolved_asset_primitive_count"], len(resolved)
            )


if __name__ == "__main__":
    unittest.main()
