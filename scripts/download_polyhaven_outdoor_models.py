#!/usr/bin/env python3
"""Download a compact CC0 outdoor model pack from the Poly Haven API.

The chosen 1K bundles balance close-view quality with portable Viewer size.
Files are checksum-verified and kept under ``assets/incoming``; CityG's normal
asset curation command converts each glTF bundle into a self-contained,
canonical GLB and records its provenance in the asset registry.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any


ASSET_IDS = (
    "street_lamp_01",
    "tree_small_02",
    # Photorealistic botanical variants used by the presentation streetscape.
    # Keep these separate from the legacy low-poly Kenney/Quaternius pack so
    # the resolver can explicitly prefer PBR vegetation.
    "jacaranda_tree",
    "island_tree_01",
    "island_tree_02",
    "shrub_01",
    "shrub_03",
    "periwinkle_plant",
    "flower_empodium",
    "dandelion_01",
    "fir_sapling",
    "pine_sapling_small",
    "searsia_lucida",
    "quiver_tree_02",
)
API_ROOT = "https://api.polyhaven.com"
USER_AGENT = "CityG-asset-downloader/1.0 (+https://polyhaven.com)"


def request_json(url: str) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            completed = subprocess.run(
                [
                    "curl",
                    "--fail",
                    "--silent",
                    "--show-error",
                    "--location",
                    "--http1.1",
                    "--tlsv1.2",
                    "--max-time",
                    "90",
                    "--user-agent",
                    USER_AGENT,
                    url,
                ],
                check=True,
                capture_output=True,
            )
            return json.loads(completed.stdout)
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
    if temporary.is_file() and md5(temporary) == expected_md5:
        temporary.replace(destination)
        return destination, "downloaded"
    last_error: Exception | None = None
    for attempt in range(5):
        try:
            subprocess.run(
                [
                    "curl",
                    "--fail",
                    "--silent",
                    "--show-error",
                    "--location",
                    "--http1.1",
                    "--tlsv1.2",
                    "--retry",
                    "5",
                    "--retry-all-errors",
                    "--continue-at",
                    "-",
                    "--max-time",
                    "600",
                    "--user-agent",
                    USER_AGENT,
                    "--output",
                    str(temporary),
                    url,
                ],
                check=True,
            )
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
            time.sleep(2**attempt)
    raise RuntimeError(f"failed to download {url}: {last_error}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resolution", choices=("1k", "2k"), default="1k")
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    pack_root = project_root / "assets" / "incoming" / "polyhaven-outdoor-models"
    pack_root.mkdir(parents=True, exist_ok=True)
    tasks: list[tuple[str, Path, str]] = []
    manifests: list[tuple[Path, dict[str, Any]]] = []
    total_bytes = 0

    for asset_id in ASSET_IDS:
        files = request_json(f"{API_ROOT}/files/{asset_id}")
        info = request_json(f"{API_ROOT}/info/{asset_id}")
        bundle = files["gltf"][args.resolution]["gltf"]
        asset_root = pack_root / asset_id
        bundle_files = {f"{asset_id}_{args.resolution}.gltf": bundle}
        bundle_files.update(bundle.get("include", {}))
        upstream: dict[str, dict[str, Any]] = {}
        for relative_name, item in bundle_files.items():
            if not isinstance(item, dict) or not {"url", "md5", "size"} <= item.keys():
                continue
            tasks.append((item["url"], asset_root / relative_name, item["md5"]))
            total_bytes += int(item["size"])
            upstream[relative_name] = {
                "url": item["url"],
                "md5": item["md5"],
                "size_bytes": item["size"],
            }
        manifests.append(
            (
                asset_root / "source.json",
                {
                    "schema_version": "cityg.source_model.v1",
                    "asset_id": asset_id,
                    "display_name": info.get("name", asset_id),
                    "source": "Poly Haven",
                    "source_page": f"https://polyhaven.com/a/{asset_id}",
                    "source_api": f"{API_ROOT}/files/{asset_id}",
                    "license_id": "CC0-1.0",
                    "authors": info.get("authors", {}),
                    "description": info.get("description", ""),
                    "category": info.get("category", ""),
                    "tags": info.get("tags", []),
                    "resolution": args.resolution,
                    "entrypoint": f"{asset_id}_{args.resolution}.gltf",
                    "upstream_files": upstream,
                },
            )
        )

    print(
        f"Preparing {len(ASSET_IDS)} assets / {len(tasks)} files "
        f"({total_bytes / 1024 / 1024:.1f} MiB upstream)"
    )
    counts = {"downloaded": 0, "cached": 0}
    workers = max(1, min(args.workers, os.cpu_count() or 2))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(download, url, path, checksum) for url, path, checksum in tasks]
        for future in as_completed(futures):
            path, status = future.result()
            counts[status] += 1
            print(f"[{status}] {path.relative_to(project_root)}")

    for path, manifest in manifests:
        path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    (pack_root / "License.txt").write_text(
        "Poly Haven assets are licensed CC0 1.0.\n"
        "Source: https://polyhaven.com/license\n",
        encoding="utf-8",
    )
    (pack_root / "pack.json").write_text(
        json.dumps(
            {
                "schema_version": "cityg.outdoor_source_pack.v1",
                "source": "Poly Haven",
                "license_id": "CC0-1.0",
                "license_url": "https://polyhaven.com/license",
                "resolution": args.resolution,
                "asset_ids": list(ASSET_IDS),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Complete: {counts['downloaded']} downloaded, {counts['cached']} cached")


if __name__ == "__main__":
    main()
