import unittest
import tempfile
from pathlib import Path
from dataclasses import replace
from unittest.mock import patch

from cityg.adaptive_review import run_adaptive_review
from cityg.cli import _parser
from cityg.assets import AssetRegistry, AssetRecord
from cityg.adaptive_review import _review_asset_registry


class ReviewCompilerConfigurationTests(unittest.TestCase):
    def test_pinned_package_assets_survive_global_registry_and_generation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = AssetRegistry(root / 'assets' / 'asset_registry.json')
            record = AssetRecord(asset_id='prototype_sink', category='sink', geometry_path='sink.glb')
            source.register(record)
            global_registry = AssetRegistry(root / 'global.json')
            global_registry.register(replace(record, geometry_path='wrong.glb'))
            global_registry.register(replace(record, asset_id='new_asset', geometry_path='extra.glb'))
            before = source.manifest_path.read_bytes()
            with patch('cityg.adaptive_review._city_path', return_value=root / 'city.json'):
                merged = _review_asset_registry(root, global_registry.manifest_path)
            self.assertIsNone(merged.manifest_path)
            self.assertEqual(merged.require('prototype_sink').geometry_path, str(root / 'assets/sink.glb'))
            self.assertEqual(merged.require('new_asset').geometry_path, str(root / 'extra.glb'))
            merged.register(replace(record, asset_id='generated'))
            self.assertEqual(source.manifest_path.read_bytes(), before)

    def test_mesh_to_boxes_cannot_pass_inventory_check(self):
        from cityg.planning.baseline import BaselineCityPlanner
        from cityg.schemas import CitySpec
        from cityg.validation.rendered_inventory import rendered_inventory_preserved
        city = BaselineCityPlanner().plan(CitySpec(building_count=1))
        obj = next(city.iter_objects())
        mesh = {'owner_id': obj.id, 'primitive_type': 'mesh', 'metadata': {'asset_id': obj.asset_id}}
        before = {'primitives': [mesh]}
        after = {'primitives': [{**mesh, 'primitive_type': 'box'}]}
        self.assertTrue(rendered_inventory_preserved(city, city, before, before)['ok'])
        self.assertFalse(rendered_inventory_preserved(city, city, before, after)['ok'])

    def test_cli_accepts_matching_facade_catalog(self):
        args = _parser().parse_args(['adaptive-review', '/tmp/source', '--output', '/tmp/review',
                                         '--facade-asset-index', '/tmp/catalog.json'])
        self.assertEqual(str(args.facade_asset_index), '/tmp/catalog.json')

    def test_enabled_source_cannot_silently_drop_modules(self):
        with patch('cityg.adaptive_review._geometry_manifest', return_value={
                'metadata': {'facade_asset_system_enabled': True}}):
            with self.assertRaisesRegex(ValueError, 'pass --facade-asset-index'):
                run_adaptive_review('/tmp/source', '/tmp/review')

    def test_missing_explicit_catalog_rejected_before_any_model_call(self):
        with self.assertRaisesRegex(ValueError, 'Facade asset index does not exist'):
            run_adaptive_review('/tmp/source', '/tmp/review',
                                facade_asset_index='/tmp/cityg_nonexistent_facade_catalog.json')
