#!/usr/bin/env python3
"""Remove registry records whose successfully rendered review PNG was deleted."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from cityg.assets import AssetRegistry


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("review_dir", type=Path)
    parser.add_argument("--registry", type=Path, default=Path("assets/asset_registry.json"))
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args()


def deleted_asset_ids(review_dir: Path) -> list[str]:
    manifest_path = review_dir / "preview_manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "cityg.asset_preview_review.v1":
        raise ValueError("Unsupported or missing asset preview manifest")
    previews = review_dir / "previews"
    return sorted(
        str(item["asset_id"])
        for item in payload.get("assets", [])
        if item.get("status") == "rendered"
        and not (previews / str(item["preview_file"])).is_file()
    )


def main() -> None:
    args = _parse_args()
    review_dir = args.review_dir.resolve()
    registry_path = args.registry.resolve()
    deleted = deleted_asset_ids(review_dir)
    print(json.dumps({"deleted_preview_count": len(deleted), "asset_ids": deleted}, indent=2))
    if not args.apply or not deleted:
        print("Dry run only. Pass --apply after checking the exact asset_ids.")
        return
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = registry_path.with_name(f"{registry_path.stem}.before_review_{timestamp}{registry_path.suffix}")
    shutil.copy2(registry_path, backup)
    registry = AssetRegistry(registry_path)
    missing = [asset_id for asset_id in deleted if registry.get(asset_id) is None]
    if missing:
        raise ValueError(f"Review manifest references unknown registry ids: {missing}")
    removed = registry.remove_many(deleted)
    print(f"Removed {removed} registry records. Backup: {backup}")
    print("Geometry files were retained; orphan cleanup remains a separate recoverable step.")


if __name__ == "__main__":
    main()
