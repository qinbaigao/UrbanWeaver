import json
import tempfile
import unittest
from pathlib import Path

from scripts.sync_asset_review_deletions import deleted_asset_ids


class AssetPreviewReviewTests(unittest.TestCase):
    def test_only_missing_successful_previews_are_interpreted_as_rejections(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            previews = root / "previews"
            previews.mkdir()
            (previews / "kept.png").write_bytes(b"png")
            (root / "preview_manifest.json").write_text(
                json.dumps(
                    {
                        "schema_version": "cityg.asset_preview_review.v1",
                        "assets": [
                            {
                                "asset_id": "kept",
                                "preview_file": "kept.png",
                                "status": "rendered",
                            },
                            {
                                "asset_id": "rejected",
                                "preview_file": "rejected.png",
                                "status": "rendered",
                            },
                            {
                                "asset_id": "render_failure",
                                "preview_file": "render_failure.png",
                                "status": "failed",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(deleted_asset_ids(root), ["rejected"])

    def test_unknown_manifest_version_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "preview_manifest.json").write_text(
                json.dumps({"schema_version": "future.v9", "assets": []}),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                deleted_asset_ids(root)


if __name__ == "__main__":
    unittest.main()
