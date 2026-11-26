import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from scripts.annotate_hssd_assets import (largest_rectangle, front_accessible,
    discover_supports, validate_decisions, annotate, gallery)
from cityg.assets import AssetRegistry
import test_hssd_asset_preparation as preparation_tests


def plane(z, x0=-.5, x1=.5, y0=-.5, y1=.5):
    return np.array([[[x0,y0,z],[x1,y0,z],[x1,y1,z]],
                     [[x0,y0,z],[x1,y1,z],[x0,y1,z]]],dtype=float)


class HssdAnnotationTests(unittest.TestCase):
    def test_largest_rectangle_does_not_span_hole(self):
        mask=np.ones((7,7),dtype=bool);mask[3,3]=False
        a,b,c,d=largest_rectangle(mask)
        self.assertTrue(mask[a:b,c:d].all())
        self.assertEqual((b-a)*(d-c),21)
        self.assertIsNone(largest_rectangle(np.zeros((3,4),dtype=bool)))

    def test_top_support_and_hole(self):
        mesh=plane(.5)
        supports,_=discover_supports(mesh,(1,1,1),"top")
        self.assertTrue(supports)
        self.assertEqual(supports[0]["geometry_probe"]["samples"],169)
        hole=np.concatenate([plane(.5,-.5,-.15),plane(.5,.15,.5),
                            plane(.5,-.15,.15,-.5,-.15),plane(.5,-.15,.15,.15,.5)])
        supports,_=discover_supports(hole,(1,1,1),"top")
        self.assertTrue(supports)
        for s in supports:
            x,y,_=s["center"];w,d=s["size"]
            self.assertFalse(abs(x)<w/2 and abs(y)<d/2)

    def test_shelves_need_known_ceiling_and_open_front(self):
        shelf=plane(0)
        supports,_=discover_supports(shelf,(1,1,1),"shelves")
        self.assertEqual(supports,[])
        opened=np.concatenate([shelf,plane(.3)])
        supports,_=discover_supports(opened,(1,1,1),"shelves")
        self.assertTrue(supports)
        self.assertAlmostEqual(supports[0]["clearance_m"],.295)
        self.assertEqual(supports[0]["geometry_probe"]["front_access"]["samples"],49)
        # Closed cabinet front x=.5, blocking access to an otherwise valid plane.
        door=np.array([[[.5,-.5,0],[.5,.5,0],[.5,.5,.3]],
                       [[.5,-.5,0],[.5,.5,.3],[.5,-.5,.3]]])
        closed=np.concatenate([opened,door])
        self.assertFalse(front_accessible(closed,0,0,0,(1,1,1)))
        self.assertTrue(front_accessible(closed,0,0,0,(1,1,1),"-X"))
        supports,_=discover_supports(closed,(1,1,1),"shelves")
        self.assertEqual(supports,[])

    def fixture(self,stage):
        helper=preparation_tests.HssdAssetPreparationTests()
        _,entry,plan=helper.fixture(stage)
        from scripts.prepare_hssd_assets import prepare_one
        record=prepare_one(entry,plan,stage)
        candidate=stage/"candidate_registry.json"
        candidate.write_text(json.dumps({"assets":[record.to_dict()]}))
        preview=stage/"review/previews"/(record.asset_id+".png")
        preview.parent.mkdir(parents=True);preview.write_bytes(b"inspected")
        spec={"review_index":1,"asset_id":record.asset_id,"output_sha256":record.metadata["output_sha256"],
            "preview_sha256":hashlib.sha256(preview.read_bytes()).hexdigest(),"front_axis":"-Y",
            "front_kind":"functional_or_display","note":"fixture observation","category":"cabinet",
            "room_types":["bedroom"],"placement_kind":"floor","disposition":"trial","support_policy":"none",
            "style":"modern","colors":["brown"],"material_appearance":["wood"]}
        return {"candidate_registry_sha256":hashlib.sha256(candidate.read_bytes()).hexdigest(),
                "assets":[spec],"max_trial_triangles":120000,"review_method":"fixture"}

    def test_snapshot_full_coverage_and_no_production_promotion(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage=Path(tmp);config=self.fixture(stage)
            original=(stage/"candidate_registry.json").read_bytes()
            registry=AssetRegistry(stage/"candidate_registry.json")
            validate_decisions(config,registry,stage)
            bad=copy.deepcopy(config);bad["assets"].append(bad["assets"][0])
            with self.assertRaises(ValueError):validate_decisions(bad,registry,stage)
            bad=copy.deepcopy(config);bad["assets"][0]["preview_sha256"]="0"*64
            with self.assertRaises(ValueError):validate_decisions(bad,registry,stage)
            with patch("scripts.annotate_hssd_assets.triangles",return_value=np.concatenate([plane(-.5),plane(.5)])):
                annotate(config,stage)
            self.assertEqual(original,(stage/"candidate_registry.json").read_bytes())
            a=json.loads((stage/"annotated_registry.json").read_text())["assets"][0]
            self.assertEqual(a["category"],"cabinet")
            self.assertFalse(a["metadata"]["runtime_enabled"])
            self.assertEqual(a["license_id"],"CC-BY-NC-4.0")
            self.assertEqual(a["metadata"]["orientation"]["canonical_forward_axis"],"-Y")
            self.assertEqual(a["metadata"]["support_annotation_status"],"not_approved")
            trial=json.loads((stage/"placement_registry.json").read_text())["assets"][0]
            self.assertTrue(trial["metadata"]["runtime_enabled"])
            self.assertTrue(Path(trial["geometry_path"]).is_absolute())
            gallery(stage)

    def test_hold_adapter_and_triangle_budget_never_enabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage=Path(tmp);config=self.fixture(stage)
            for state in ("hold","adapter"):
                config["assets"][0]["disposition"]=state
                annotate(config,stage)
                self.assertEqual(json.loads((stage/"placement_registry.json").read_text())["assets"],[])
            config["assets"][0]["disposition"]="trial";config["max_trial_triangles"]=0
            annotate(config,stage)
            self.assertEqual(json.loads((stage/"placement_registry.json").read_text())["assets"],[])

    def test_complete_config_has_annotations_for_all_candidates(self):
        config=json.loads(Path("configs/hssd_asset_annotations.json").read_text())
        self.assertEqual(len(config["assets"]),132)
        self.assertEqual(len({s["asset_id"] for s in config["assets"]}),132)
        self.assertTrue(all(s["note"] and s["front_axis"] and s["style"] for s in config["assets"]))


if __name__=="__main__":unittest.main()
