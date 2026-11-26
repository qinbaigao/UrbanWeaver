import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cityg.assets import AssetRecord, AssetRegistry
from scripts.accept_hssd_assets import (eligible, fingerprint, placement_one,
    promote, sha256, validate_review, visual_pass)
import scripts.accept_hssd_assets as acceptance


class HssdAcceptanceTests(unittest.TestCase):
    def record(self):
        return AssetRecord("test_asset","cup",environment="indoor",room_types=("office",),
            dimensions_m=(.09,.09,.11),geometry_path="cup.glb",license_id="CC-BY-NC-4.0",
            metadata={"placement_kind":"surface","runtime_enabled":True,
                "visual_review":{"preview_sha256":"image"},"curation":{"disposition":"trial"}})

    def review(self):
        return {"asset_id":"test_asset","decision":"pass","confidence":.95,
            "category_match":True,"orientation_match":True,"complete_standalone_object":True,
            "issues":[],"reason":"Visible complete upright cup"}

    def evidence(self,r):
        return {"review":self.review(),"record_sha256":fingerprint(r),"model":"test-vlm",
                "finish_reason":"stop","image_sha256":["image"]}

    def test_verdict_fail_closed(self):
        v=self.review();self.assertTrue(visual_pass(validate_review(v,"test_asset")))
        for changes in ({"confidence":.79},{"orientation_match":False},{"issues":["broken mesh"]},
                        {"complete_standalone_object":False},{"decision":"hold"}):
            self.assertFalse(visual_pass({**v,**changes}))
        for changes in ({"asset_id":"other"},{"confidence":float("nan")},{"confidence":True},
                        {"category_match":"true"},{"reason":""}):
            with self.assertRaises(ValueError):validate_review({**v,**changes},"test_asset")

    def test_both_gates_and_exact_evidence_required(self):
        r=self.record();v=self.evidence(r);p={"record_sha256":fingerprint(r),"pass":True}
        self.assertTrue(eligible(r,v,p))
        self.assertFalse(eligible(r,v,{**p,"pass":False}))
        for change in ({"record_sha256":"stale"},{"finish_reason":"length"},{"image_sha256":["other"]}):
            with self.assertRaises(ValueError):eligible(r,{**v,**change},p)

    def test_unimplemented_categories_not_promoted_by_visual_quality(self):
        from dataclasses import replace
        r=replace(self.record(),category="armchair",metadata={"placement_kind":"floor"})
        self.assertEqual(placement_one(r),{"pass":False,"reason":"placement_category_not_implemented"})

    def test_additive_promotion_preserves_existing_and_backs_up(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);output=root/"audit";output.mkdir();(output/"visual").mkdir()
            geom=root/"cup.glb";geom.write_bytes(b"test")
            from dataclasses import replace
            r=self.record();r=replace(r,geometry_path=str(geom),metadata={**r.metadata,
                "annotation_geometry_sha256":sha256(geom)})
            registry=AssetRegistry();registry.register(r)
            old={"assets":[{"asset_id":"old","category":"tree","extra":"preserve me"}],"extra_root":42}
            prod=root/"registry.json";prod.write_text(json.dumps(old));before=prod.read_bytes()
            (output/"visual/test_asset.json").write_text(json.dumps(self.evidence(r)))
            (output/"placement.json").write_text(json.dumps({"validator_sha256":acceptance.validator_signature(),
                "assets":[{"asset_id":r.asset_id,"record_sha256":fingerprint(r),"pass":True}]}))
            promote(registry,output,prod)
            after=json.loads(prod.read_text())
            self.assertEqual(after["assets"][0],old["assets"][0]);self.assertEqual(after["extra_root"],42)
            self.assertEqual((output/"production_registry.before.json").read_bytes(),before)
            self.assertEqual(after["assets"][1]["license_id"],"CC-BY-NC-4.0")
            self.assertEqual(after["assets"][1]["geometry_path"],"cup.glb")
            promoted=prod.read_bytes()
            with self.assertRaises(ValueError):promote(registry,output,prod)
            self.assertEqual(prod.read_bytes(),promoted)


if __name__=="__main__":unittest.main()
