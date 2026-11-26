"""Scene package context must reach room planning and rollback compilation."""
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from cityg.assets import AssetRecord, AssetRegistry, AssetResolver
from cityg.editing import SceneReference, _edit_asset_context, rollback_scene
from cityg.serialization import save_json
from test_editing import _city


class EditAssetContextTests(unittest.TestCase):
    def test_accepted_local_role_survives_stricter_global_room_tags(self):
        from cityg.planning.interiors import ASSET_CATALOG, FloorDetailAgent
        registry=AssetRegistry()
        registry.register(AssetRecord(asset_id='office_desk',category='desk',geometry_path='/desk.glb',
                                      room_types=('office',),dimensions_m=(1.4,.7,.75)))
        detail=FloorDetailAgent(asset_resolver=AssetResolver(registry,(),max_provider_calls=0))
        self.assertIsNone(detail._resolve_asset(ASSET_CATALOG['desk'],room_type='living_room'))
        asset=detail._resolve_asset(ASSET_CATALOG['desk'],room_type='living_room',preferred_asset_id='office_desk')
        self.assertEqual(asset.id,'office_desk')
        self.assertEqual(registry.require('office_desk').room_types,('office',))
        with self.assertRaisesRegex(ValueError,'Previously used room asset'):
            detail._resolve_asset(ASSET_CATALOG['desk'],room_type='living_room',preferred_asset_id='missing')

    def test_renamed_major_object_cannot_downgrade_to_a_proxy(self):
        from types import SimpleNamespace as NS
        from cityg.validation.local_room import room_mesh_retention
        old=[NS(id='old',asset_id='real',category='desk')]
        new=[NS(id='new',asset_id='procedural::desk::v1',category='desk')]
        before=NS(primitives=[NS(owner_id='old',primitive_type='mesh',metadata={'asset_id':'real'})])
        # A cup mesh on a procedural table must not count as a table mesh.
        after=NS(primitives=[NS(owner_id='new',primitive_type='mesh',metadata={'asset_id':'cup'})])
        self.assertFalse(room_mesh_retention(old,new,before,after)['ok'])
        new=[NS(id='new',asset_id='other_mesh',category='desk')]
        after=NS(primitives=[NS(owner_id='new',primitive_type='mesh',metadata={'asset_id':'other_mesh'})])
        self.assertTrue(room_mesh_retention(old,new,before,after)['ok'])

    def test_no_explicit_registry_uses_detached_local_package_resolver(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            pinned=AssetRegistry(root/'assets/asset_registry.json')
            pinned.register(AssetRecord(asset_id='chair',category='office_chair',geometry_path='chair.glb'))
            before=pinned.manifest_path.read_bytes()
            reference=SceneReference(str(root),root/'city.json',root,root)
            resolver=_edit_asset_context(reference,None)
            self.assertIsNotNone(resolver)
            self.assertIsNone(resolver.registry.manifest_path)
            self.assertEqual(resolver.providers,())
            self.assertEqual(resolver.max_provider_calls,0)
            self.assertEqual(resolver.registry.require('chair').geometry_path,str(root/'assets/chair.glb'))
            resolver.registry.register(AssetRecord(asset_id='new',category='desk'))
            self.assertEqual(pinned.manifest_path.read_bytes(),before)

    def test_explicit_resolver_keeps_provider_configuration_but_pinned_ids_win(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            pinned=AssetRegistry(root/'assets/asset_registry.json')
            record=AssetRecord(asset_id='chair',category='office_chair',geometry_path='chair.glb')
            pinned.register(record)
            global_registry=AssetRegistry()
            global_registry.register(replace(record,geometry_path='/wrong.glb'))
            provider=object()
            supplied=AssetResolver(global_registry,(provider,),max_provider_calls=2)
            reference=SceneReference(str(root),root/'city.json',root,root)
            resolver=_edit_asset_context(reference,supplied)
            self.assertIsNot(resolver,supplied)
            self.assertEqual(resolver.providers,(provider,))
            self.assertEqual(resolver.max_provider_calls,2)
            self.assertEqual(resolver.registry.require('chair').geometry_path,str(root/'assets/chair.glb'))
            self.assertEqual(supplied.registry.require('chair').geometry_path,'/wrong.glb')

    def test_rollback_preserves_facades_and_exterior_only_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'source'
            save_json(_city(),source/'city.json')
            metadata={'interiors_compiled':False,'facade_asset_system_enabled':True,
                      'facade_asset_runtime_context':{'index':{'reviewed':True},'project_root':'/project'}}
            save_json({'metadata':metadata},source/'geometry_manifest.json')
            pinned=AssetRegistry(source/'assets/asset_registry.json')
            pinned.register(AssetRecord(asset_id='chair',category='office_chair',geometry_path='chair.glb'))
            before={p:p.read_bytes() for p in source.rglob('*') if p.is_file()}
            runtime=object()
            with patch('cityg.compilation_context.restore_facade_runtime',return_value=runtime) as restore, \
                 patch('cityg.geometry.incremental.scene_from_manifest',return_value='saved-scene'), \
                 patch('cityg.editing.OpenUSDBackend') as backend:
                rollback_scene(source,root/'rollback',target_scene=source,no_viewer=True)
                compiler=backend.call_args.kwargs['geometry_compiler']
                self.assertFalse(compiler.include_interiors)
                self.assertIs(compiler.facade_asset_runtime,runtime)
                self.assertEqual(restore.call_args.args[0],metadata)
                backend.return_value.compile.assert_called_once()
                self.assertEqual(backend.return_value.compile.call_args.kwargs['_scene_override'],'saved-scene')
            for path,data in before.items():
                self.assertEqual(path.read_bytes(),data)
