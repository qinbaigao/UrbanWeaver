import json
import tempfile
import unittest
from pathlib import Path

from cityg.facade_assets import FacadeAssetIndex, classify_facade_asset
from cityg.facade_visual_review import (
    FacadeSheetReview,
    FacadeVisualReviewAgent,
    apply_facade_visual_reviews,
    plan_facade_visual_expansion,
    plan_facade_visual_review,
)


def _record(name: str, source: str = "pack") -> dict:
    return classify_facade_asset(
        name,
        source_asset_id=name,
        source_id=source,
        style="photoreal_weathered_pbr",
        realism_level="photoreal_pbr",
        source_front_axis="+Z",
        front_axis_confidence="medium",
        extent_xyz=(1, 2, .2),
        selector={"kind": "whole_asset"},
        geometry_path="asset.glb",
        license_id="CC0-1.0",
        source_url="https://example.com",
        quality_score=.9,
        technical={"texture_count": 2},
    )


class _FakeService:
    def __init__(self, payload):
        self.payload = payload

    def complete(self, messages, response_schema=None):
        return json.dumps(self.payload)


class FacadeVisualReviewTests(unittest.TestCase):
    def test_planner_round_robins_semantic_strata(self):
        records = [_record("wall-window-a"), _record("wall-window-b"), _record("roof-flat-a")]
        payload = {
            "schema_version": "cityg.facade_asset_annotations.v1",
            "summary": {"asset_count": 3},
            "assets": records,
        }
        selected = plan_facade_visual_review(FacadeAssetIndex(payload), max_assets=2)
        self.assertEqual({item.record["semantic_type"] for item in selected}, {"window_bay", "roof_module"})

    def test_small_budget_round_robins_source_coordinate_conventions(self):
        records = [_record("wall-window-a", "polyhaven"), _record("wall-window-b", "kenney")]
        payload = {
            "schema_version": "cityg.facade_asset_annotations.v1",
            "summary": {"asset_count": 2},
            "assets": records,
        }
        selected = plan_facade_visual_review(FacadeAssetIndex(payload), max_assets=2)
        self.assertEqual({item.record["source_id"] for item in selected}, {"polyhaven", "kenney"})

    def test_agent_rejects_invented_panel_binding(self):
        record = _record("wall-window-a")
        payload = {
            "sheet_id": "sheet_1", "summary": "bad", "reviews": [{
                "panel_id": "invented", "asset_id": record["asset_id"],
                "semantic_assessment": "correct", "suggested_semantic_type": None,
                "front_axis_assessment": "correct", "suggested_source_front_axis": None,
                "upright": True, "scale_assessment": "plausible", "visual_quality": .8,
                "placement_readiness": "ready", "confidence": .95, "issues": [], "reason": "ok",
            }],
        }
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "sheet.png"; image.write_bytes(b"png")
            result = FacadeVisualReviewAgent(_FakeService(payload)).review(
                {"sheet_id": "sheet_1", "image_path": str(image), "panels": [{
                    "panel_id": "F001", "asset_id": record["asset_id"], "display_name": record["display_name"],
                    "semantic_type": record["semantic_type"], "source_id": record["source_id"],
                    "source_front_axis": "+Z", "native_extent_xyz": [1, 2, .2], "native_scale_confidence": "high",
                }]},
                allowed_semantic_types=(record["semantic_type"],),
            )
        self.assertFalse(result.available)
        self.assertIn("invalid panel binding", result.error)

    def test_unrecognized_semantic_suggestion_is_deferred_without_losing_sheet(self):
        record = _record("wall-window-a")
        payload = {
            "sheet_id": "sheet_1", "summary": "reviewed", "reviews": [{
                "panel_id": "F001", "asset_id": record["asset_id"],
                "semantic_assessment": "incorrect", "suggested_semantic_type": "invented_type",
                "front_axis_assessment": "correct", "suggested_source_front_axis": None,
                "upright": True, "scale_assessment": "plausible", "visual_quality": .8,
                "placement_readiness": "needs_review", "confidence": .92, "issues": [], "reason": "unclear",
            }],
        }
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "sheet.png"; image.write_bytes(b"png")
            result = FacadeVisualReviewAgent(_FakeService(payload)).review(
                {"sheet_id": "sheet_1", "image_path": str(image), "panels": [{
                    "panel_id": "F001", "asset_id": record["asset_id"], "display_name": record["display_name"],
                    "semantic_type": record["semantic_type"], "source_id": record["source_id"],
                    "source_front_axis": "+Z", "alignment_mode": "front_normal",
                    "native_extent_xyz": [1, 2, .2], "native_scale_confidence": "high",
                }]},
                allowed_semantic_types=(record["semantic_type"],),
            )
        self.assertTrue(result.available)
        self.assertIsNone(result.reviews[0]["suggested_semantic_type"])
        self.assertIn("unrecognized semantic suggestion", result.reviews[0]["issues"][0])

    def test_high_confidence_opposite_axis_is_flipped_but_low_confidence_is_deferred(self):
        first, second = _record("wall-window-a"), _record("wall-window-b")
        payload = {
            "schema_version": "cityg.facade_asset_annotations.v1",
            "annotation_policy": {},
            "summary": {
                "asset_count": 2,
                "semantic_type_counts": {"window_bay": 2},
                "selection_status_counts": {"usable": 2},
            },
            "assets": [first, second],
        }
        def review(record, panel, confidence):
            return {
                "panel_id": panel, "asset_id": record["asset_id"],
                "semantic_assessment": "correct", "suggested_semantic_type": None,
                "front_axis_assessment": "opposite", "suggested_source_front_axis": "-Z",
                "upright": True, "scale_assessment": "plausible", "visual_quality": .9,
                "placement_readiness": "ready", "confidence": confidence, "issues": [], "reason": "front is reversed",
            }
        sheet = FacadeSheetReview(True, "sheet", (review(first, "F1", .96), review(second, "F2", .70)))
        updated, stats = apply_facade_visual_reviews(payload, [sheet])
        by_id = {item["asset_id"]: item for item in updated["assets"]}
        self.assertEqual(by_id[first["asset_id"]]["orientation"]["source_front_axis"], "-Z")
        self.assertEqual(by_id[second["asset_id"]]["orientation"]["source_front_axis"], "+Z")
        self.assertEqual(stats["orientation_flipped"], 1)
        self.assertEqual(stats["low_confidence"], 1)

    def test_problematic_representative_expands_only_its_stratum(self):
        records = [_record("wall-window-a"), _record("wall-window-b"), _record("roof-flat-a")]
        payload = {
            "schema_version": "cityg.facade_asset_annotations.v1",
            "summary": {"asset_count": 3},
            "assets": records,
        }
        index = FacadeAssetIndex(payload)
        observed = plan_facade_visual_review(index, max_assets=2, representatives_per_stratum=1)
        window = next(item for item in observed if item.record["semantic_type"] == "window_bay")
        review = FacadeSheetReview(True, "sheet", ({
            "panel_id": window.panel_id, "asset_id": window.record["asset_id"],
            "semantic_assessment": "uncertain", "suggested_semantic_type": None,
            "front_axis_assessment": "uncertain", "suggested_source_front_axis": None,
            "upright": True, "scale_assessment": "plausible", "visual_quality": .7,
            "placement_readiness": "needs_review", "confidence": .7, "issues": [], "reason": "unclear",
        },))
        expansion = plan_facade_visual_expansion(index, observed, [review], max_assets=2)
        self.assertEqual(len(expansion), 1)
        self.assertEqual(expansion[0].record["semantic_type"], "window_bay")


if __name__ == "__main__":
    unittest.main()
