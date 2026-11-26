import hashlib
import tempfile
import unittest
from pathlib import Path

from cityg.assets import AssetRecord, choose_asset_variant
from scripts.convert_outdoor_sources import validate_approval


class OutdoorConversionTests(unittest.TestCase):
    def test_rejected_best_match_does_not_hide_ready_asset(self):
        candidate = AssetRecord('candidate', 'person', metadata={'outdoor_pack_status':'candidate'})
        ready = AssetRecord('ready', 'person', metadata={'outdoor_pack_status':'ready'})
        self.assertEqual(choose_asset_variant([(candidate,1.0),(ready,.2)], 'key'), ready)

    def test_manual_records_are_never_auto_selected(self):
        for asset in (AssetRecord('a','vehicle',tags=('manual_only',)),
                      AssetRecord('b','vehicle',metadata={'manual_only':True})):
            self.assertIsNone(choose_asset_variant([(asset,1)],'key'))

    def test_approval_is_bound_to_payload_and_all_checks(self):
        with tempfile.TemporaryDirectory() as directory:
            payload=Path(directory)/'asset.glb'
            payload.write_bytes(b'fixture')
            digest=hashlib.sha256(payload.read_bytes()).hexdigest()
            asset=AssetRecord('a','vehicle',metadata={'output_sha256':digest,
                'mesh_validation':{'triangle_count':100},'preparation':{'runtime_triangle_budget':200}})
            review={'status':'accepted','note':'four-view review','sha256':digest,
                    'front_checked':True,'scale_checked':True,'materials_checked':True,'pose_checked':True}
            validate_approval(asset,review,payload)
            for key in ('front_checked','scale_checked','materials_checked','pose_checked'):
                with self.assertRaises(ValueError):
                    validate_approval(asset,{**review,key:False},payload)
            with self.assertRaises(ValueError):
                validate_approval(asset,{**review,'sha256':'stale'},payload)
            payload.write_bytes(b'modified')
            with self.assertRaises(ValueError):
                validate_approval(asset,review,payload)

    def test_over_budget_and_manual_cannot_be_promoted(self):
        with tempfile.TemporaryDirectory() as directory:
            payload=Path(directory)/'asset.glb'
            payload.write_bytes(b'fixture')
            digest=hashlib.sha256(payload.read_bytes()).hexdigest()
            for metadata in ({'manual_only':True},
                {'mesh_validation':{'triangle_count':201},'preparation':{'runtime_triangle_budget':200}}):
                asset=AssetRecord('a','person',metadata={'output_sha256':digest,**metadata})
                with self.assertRaises(ValueError):
                    validate_approval(asset,{'status':'accepted','note':'review','sha256':digest},payload)
