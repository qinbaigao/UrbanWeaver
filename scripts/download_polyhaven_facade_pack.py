#!/usr/bin/env python3
"""Download a compact, reproducible CC0 facade material pack from Poly Haven."""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


TEXTURE_IDS = (
    "concrete_wall_007",
    "concrete_wall_008",
    "plastered_wall_03",
    "grey_plaster_02",
    "brick_wall_003",
    "brick_wall_09",
    "granite_wall",
    "rectangular_facade_tiles",
    "metal_plate_02",
    "box_profile_metal_sheet",
    "roof_tiles",
)
CHANNELS = {
    "Diffuse": "base_color",
    "nor_gl": "normal_gl",
    "Rough": "roughness",
    "AO": "ambient_occlusion",
}
HDRI_ID = "urban_street_02"
RESOLUTION = "2k"
API_ROOT = "https://api.polyhaven.com"
USER_AGENT = "CityG-asset-downloader/1.0 (+https://polyhaven.com)"


def request_json(url: str) -> dict:
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=90) as response:
                return json.loads(response.read())
        except Exception as error:
            last_error = error
            time.sleep(2 ** attempt)
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
            with urllib.request.urlopen(request, timeout=120) as response, temporary.open("wb") as output:
                while block := response.read(1024 * 1024):
                    output.write(block)
            actual_md5 = md5(temporary)
            if actual_md5 != expected_md5:
                raise RuntimeError(
                    f"checksum mismatch for {destination.name}: {actual_md5} != {expected_md5}"
                )
            temporary.replace(destination)
            return destination, "downloaded"
        except Exception as error:  # network failures are retried with backoff
            last_error = error
            temporary.unlink(missing_ok=True)
            time.sleep(2 ** attempt)
    raise RuntimeError(f"failed to download {url}: {last_error}")


def select_texture_file(files: dict, channel: str) -> dict:
    variants = files[channel][RESOLUTION]
    for extension in ("jpg", "png"):
        if extension in variants:
            return {**variants[extension], "extension": extension}
    raise KeyError(f"No JPG/PNG {RESOLUTION} variant for {channel}")


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    texture_root = project_root / "assets" / "incoming" / "facade_materials"
    hdri_root = project_root / "assets" / "incoming" / "hdri"
    texture_root.mkdir(parents=True, exist_ok=True)
    hdri_root.mkdir(parents=True, exist_ok=True)

    tasks: list[tuple[str, Path, str]] = []
    material_manifests: list[tuple[Path, dict]] = []
    total_bytes = 0
    for asset_id in TEXTURE_IDS:
        files = request_json(f"{API_ROOT}/files/{asset_id}")
        info = request_json(f"{API_ROOT}/info/{asset_id}")
        directory = texture_root / asset_id
        maps = {}
        upstream_files = {}
        for upstream_channel, local_channel in CHANNELS.items():
            selected = select_texture_file(files, upstream_channel)
            filename = f"{asset_id}_{local_channel}_{RESOLUTION}.{selected['extension']}"
            destination = directory / filename
            maps[local_channel] = filename
            upstream_files[local_channel] = {
                "url": selected["url"],
                "md5": selected["md5"],
                "size_bytes": selected["size"],
            }
            tasks.append((selected["url"], destination, selected["md5"]))
            total_bytes += int(selected["size"])
        dimensions = info.get("dimensions") or []
        dimensions_m = [round(float(value) / 1000.0, 4) for value in dimensions]
        manifest = {
            "schema_version": "cityg.source_material.v1",
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
            "physical_dimensions_m": dimensions_m,
            "resolution": RESOLUTION,
            "normal_convention": "OpenGL",
            "maps": maps,
            "upstream_files": upstream_files,
        }
        material_manifests.append((directory / "source.json", manifest))

    hdri_files = request_json(f"{API_ROOT}/files/{HDRI_ID}")
    hdri_info = request_json(f"{API_ROOT}/info/{HDRI_ID}")
    hdri = hdri_files["hdri"][RESOLUTION]["hdr"]
    hdri_destination = hdri_root / f"{HDRI_ID}_{RESOLUTION}.hdr"
    tasks.append((hdri["url"], hdri_destination, hdri["md5"]))
    total_bytes += int(hdri["size"])

    print(f"Preparing {len(tasks)} files ({total_bytes / 1024 / 1024:.1f} MiB upstream)")
    counts = {"downloaded": 0, "cached": 0}
    # Poly Haven's CDN occasionally closes concurrent urllib transfers early.
    # Three workers keeps throughput reasonable while avoiding burst failures;
    # every completed file is still accepted only after its official MD5 passes.
    with ThreadPoolExecutor(max_workers=min(3, (os.cpu_count() or 2))) as pool:
        futures = [pool.submit(download, url, path, checksum) for url, path, checksum in tasks]
        for future in as_completed(futures):
            path, status = future.result()
            counts[status] += 1
            print(f"[{status}] {path.relative_to(project_root)}")

    for path, manifest in material_manifests:
        path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    hdri_manifest = {
        "schema_version": "cityg.source_environment.v1",
        "asset_id": HDRI_ID,
        "display_name": hdri_info.get("name", HDRI_ID),
        "source": "Poly Haven",
        "source_page": f"https://polyhaven.com/a/{HDRI_ID}",
        "license_id": "CC0-1.0",
        "authors": hdri_info.get("authors", {}),
        "description": hdri_info.get("description", ""),
        "resolution": RESOLUTION,
        "file": hdri_destination.name,
        "upstream_file": {
            "url": hdri["url"],
            "md5": hdri["md5"],
            "size_bytes": hdri["size"],
        },
    }
    (hdri_root / "source.json").write_text(
        json.dumps(hdri_manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    pack_manifest = {
        "schema_version": "cityg.facade_source_pack.v1",
        "source": "Poly Haven",
        "license_id": "CC0-1.0",
        "resolution": RESOLUTION,
        "material_ids": list(TEXTURE_IDS),
        "environment_id": HDRI_ID,
    }
    (texture_root / "pack.json").write_text(
        json.dumps(pack_manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Complete: {counts['downloaded']} downloaded, {counts['cached']} cached")


if __name__ == "__main__":
    main()
