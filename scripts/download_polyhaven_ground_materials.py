#!/usr/bin/env python3
"""Download a small CC0 tileable ground-material pack from Poly Haven.

The script downloads only the 2K JPG channels consumed by CityG's portable
Viewer and OpenUSD material export: diffuse, tangent-space normal, roughness,
and ambient occlusion.  Every file is checksum verified and provenance is
stored alongside the material so the pack can be redistributed or replaced
without changing compiler code.
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


MATERIALS = {
    "grass_path_2": "grass",
    "concrete_pavement": "concrete",
    "brick_pavement": "brick",
    "gravel_ground_01": "gravel",
}
API_ROOT = "https://api.polyhaven.com"
USER_AGENT = "CityG-ground-material-downloader/1.0 (+https://polyhaven.com)"
CHANNELS = {
    "base_color": "Diffuse",
    "normal": "nor_gl",
    "roughness": "Rough",
    "ambient_occlusion": "AO",
}


def request_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last_error: Exception | None = None
    for attempt in range(4):
        try:
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
            with urllib.request.urlopen(request, timeout=180) as response, temporary.open("wb") as output:
                while block := response.read(1024 * 1024):
                    output.write(block)
            actual_md5 = md5(temporary)
            if actual_md5 != expected_md5:
                raise RuntimeError(f"checksum mismatch: {actual_md5} != {expected_md5}")
            temporary.replace(destination)
            return destination, "downloaded"
        except Exception as error:
            last_error = error
            temporary.unlink(missing_ok=True)
            time.sleep(2**attempt)
    raise RuntimeError(f"failed to download {url}: {last_error}")


def pick_channel(files: dict[str, Any], channel: str, resolution: str) -> dict[str, Any]:
    group = files[CHANNELS[channel]][resolution]
    # JPG keeps the browser path lightweight and is supported by both the
    # portable Viewer and the OpenUSD texture reader.
    return group.get("jpg") or group.get("png") or group["exr"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resolution", choices=("1k", "2k", "4k"), default="2k")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    pack_root = project_root / "assets" / "incoming" / "ground_materials"
    tasks: list[tuple[str, Path, str]] = []
    manifests: list[tuple[Path, dict[str, Any]]] = []
    for asset_id, semantic in MATERIALS.items():
        files = request_json(f"{API_ROOT}/files/{asset_id}")
        info = request_json(f"{API_ROOT}/info/{asset_id}")
        asset_root = pack_root / asset_id
        upstream_files: dict[str, dict[str, Any]] = {}
        channel_paths: dict[str, str] = {}
        for channel in CHANNELS:
            item = pick_channel(files, channel, args.resolution)
            suffix = Path(item["url"]).suffix.lower() or ".jpg"
            filename = f"{asset_id}_{channel}_{args.resolution}{suffix}"
            destination = asset_root / filename
            tasks.append((item["url"], destination, item["md5"]))
            upstream_files[filename] = {
                "url": item["url"],
                "md5": item["md5"],
                "size_bytes": item["size"],
                "channel": channel,
            }
            channel_paths[channel] = str(Path("incoming") / "ground_materials" / asset_id / filename)
        manifests.append(
            (
                asset_root / "source.json",
                {
                    "schema_version": "cityg.ground_material_source.v1",
                    "asset_id": asset_id,
                    "semantic_role": semantic,
                    "display_name": info.get("name", asset_id),
                    "source": "Poly Haven",
                    "source_page": f"https://polyhaven.com/a/{asset_id}",
                    "license_id": "CC0-1.0",
                    "resolution": args.resolution,
                    "channels": channel_paths,
                    "upstream_files": upstream_files,
                },
            )
        )

    print(f"Preparing {len(tasks)} PBR files")
    counts = {"downloaded": 0, "cached": 0}
    with ThreadPoolExecutor(max_workers=max(1, min(args.workers, os.cpu_count() or 2))) as pool:
        futures = [pool.submit(download, url, path, checksum) for url, path, checksum in tasks]
        for future in as_completed(futures):
            path, status = future.result()
            counts[status] += 1
            print(f"[{status}] {path.relative_to(project_root)}")
    for path, manifest in manifests:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    pack_manifest = {
        "schema_version": "cityg.ground_material_source_pack.v1",
        "source": "Poly Haven",
        "license_id": "CC0-1.0",
        "license_url": "https://polyhaven.com/license",
        "resolution": args.resolution,
        "materials": MATERIALS,
    }
    (pack_root / "pack.json").write_text(
        json.dumps(pack_manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Complete: {counts['downloaded']} downloaded, {counts['cached']} cached")


if __name__ == "__main__":
    main()
