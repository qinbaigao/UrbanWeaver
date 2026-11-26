#!/usr/bin/env python3
"""Download a compact CC0 facade-geometry pack from the Poly Haven API.

The pack complements CityG's procedural facades with real, textured modules.
Every upstream file is checksum-verified and every asset keeps provenance and
license metadata next to the downloaded glTF bundle.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any


ASSET_IDS = (
    "modular_urban_apartments_facade",
    "modular_factory_facade",
    "modular_fire_escape",
    "modular_metal_gutter",
    "modular_airduct_circular_01",
    "exterior_aircon_unit",
    "rollershutter_door",
    "rollershutter_window_01",
    "rollershutter_window_02",
    "rollershutter_window_03",
    "security_camera_01",
    "security_light",
    "utility_box_01",
    "utility_box_02",
)
API_ROOT = "https://api.polyhaven.com"
USER_AGENT = "CityG-asset-downloader/1.0 (+https://polyhaven.com)"


def request_json(url: str) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=90) as response:
                return json.loads(response.read())
        except Exception as error:
            last_error = error
            time.sleep(2**attempt)
    raise RuntimeError(f"failed to read metadata {url}: {last_error}")


def md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download(url: str, destination: Path, expected_md5: str) -> tuple[Path, str]:
    if destination.is_file() and md5(destination) == expected_md5:
        return destination, "cached"
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    last_error: Exception | None = None
    for attempt in range(5):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=180) as response, temporary.open(
                "wb"
            ) as output:
                while block := response.read(1024 * 1024):
                    output.write(block)
            actual_md5 = md5(temporary)
            if actual_md5 != expected_md5:
                raise RuntimeError(
                    f"checksum mismatch for {destination.name}: "
                    f"{actual_md5} != {expected_md5}"
                )
            temporary.replace(destination)
            return destination, "downloaded"
        except Exception as error:
            last_error = error
            temporary.unlink(missing_ok=True)
            time.sleep(2**attempt)
    raise RuntimeError(f"failed to download {url}: {last_error}")


def gltf_bundle(files: dict[str, Any], resolution: str) -> dict[str, Any]:
    try:
        return files["gltf"][resolution]["gltf"]
    except KeyError as error:
        raise KeyError(f"No glTF {resolution} bundle found") from error


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resolution", choices=("1k", "2k", "4k"), default="2k")
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    pack_root = project_root / "assets" / "incoming" / "facade_models_polyhaven"
    pack_root.mkdir(parents=True, exist_ok=True)

    tasks: list[tuple[str, Path, str]] = []
    asset_manifests: list[tuple[Path, dict[str, Any]]] = []
    total_bytes = 0
    for asset_id in ASSET_IDS:
        files = request_json(f"{API_ROOT}/files/{asset_id}")
        info = request_json(f"{API_ROOT}/info/{asset_id}")
        bundle = gltf_bundle(files, args.resolution)
        asset_root = pack_root / asset_id

        upstream_files: dict[str, dict[str, Any]] = {}
        bundle_files = {f"{asset_id}_{args.resolution}.gltf": bundle}
        bundle_files.update(bundle.get("include", {}))
        for relative_name, item in bundle_files.items():
            if not isinstance(item, dict) or not {"url", "md5", "size"} <= item.keys():
                continue
            destination = asset_root / relative_name
            tasks.append((item["url"], destination, item["md5"]))
            total_bytes += int(item["size"])
            upstream_files[relative_name] = {
                "url": item["url"],
                "md5": item["md5"],
                "size_bytes": item["size"],
            }

        manifest = {
            "schema_version": "cityg.source_model.v1",
            "asset_id": asset_id,
            "display_name": info.get("name", asset_id),
            "source": "Poly Haven",
            "source_page": f"https://polyhaven.com/a/{asset_id}",
            "source_api": f"{API_ROOT}/files/{asset_id}",
            "license_id": "CC0-1.0",
            "authors": info.get("authors", {}),
            "description": info.get("description", ""),
            "categories": info.get("categories", []),
            "tags": info.get("tags", []),
            "resolution": args.resolution,
            "entrypoint": f"{asset_id}_{args.resolution}.gltf",
            "upstream_files": upstream_files,
        }
        asset_manifests.append((asset_root / "source.json", manifest))

    print(
        f"Preparing {len(ASSET_IDS)} assets / {len(tasks)} files "
        f"({total_bytes / 1024 / 1024:.1f} MiB upstream)"
    )
    counts = {"downloaded": 0, "cached": 0}
    with ThreadPoolExecutor(max_workers=max(1, min(args.workers, os.cpu_count() or 2))) as pool:
        futures = [pool.submit(download, url, path, checksum) for url, path, checksum in tasks]
        for future in as_completed(futures):
            path, status = future.result()
            counts[status] += 1
            print(f"[{status}] {path.relative_to(project_root)}")

    for path, manifest in asset_manifests:
        path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    pack_manifest = {
        "schema_version": "cityg.facade_model_source_pack.v1",
        "source": "Poly Haven",
        "license_id": "CC0-1.0",
        "license_url": "https://polyhaven.com/license",
        "resolution": args.resolution,
        "asset_ids": list(ASSET_IDS),
        "redistribution_note": (
            "CC0 permits redistribution; source metadata is retained for reproducibility."
        ),
    }
    (pack_root / "pack.json").write_text(
        json.dumps(pack_manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Complete: {counts['downloaded']} downloaded, {counts['cached']} cached")


if __name__ == "__main__":
    main()
