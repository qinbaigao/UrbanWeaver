#!/usr/bin/env python3
"""Render one deletion-friendly four-view preview per concrete registry asset."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import threading
from dataclasses import dataclass, replace
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

from cityg.assets import AssetRecord, AssetRegistry


PLANAR_CATEGORIES = frozenset({"road_module", "bridge_module"})


@dataclass(frozen=True)
class PreviewItem:
    record: AssetRecord
    geometry_path: Path
    relative_geometry_path: str
    preview_name: str
    front_axis: str
    up_axis: str
    view_mode: str


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, default=Path("assets/asset_registry.json"))
    parser.add_argument("--output", type=Path, default=Path("outputs/asset_library_review"))
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--size", type=int, default=960)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--category", action="append", default=[])
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--view-mode", choices=["four_view", "four_view_planar"],
                        help="Override cameras for supplementary top/oblique inspection")
    return parser.parse_args()


def _safe_name(asset_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", asset_id) + ".png"


def _orientation(record: AssetRecord) -> tuple[str, str]:
    orientation = record.metadata.get("orientation")
    if not isinstance(orientation, dict):
        orientation = {}
    up = str(
        orientation.get("canonical_up_axis")
        or ("+Z" if "z_up" in str(record.metadata.get("coordinate_system", "")) else "+Z")
    )
    front = str(
        orientation.get("canonical_forward_axis")
        or orientation.get("front_axis")
        or record.metadata.get("front_axis")
        # Current Hunyuan normalization keeps generated subjects facing -Y;
        # curated packs carry an explicit canonical forward axis.
        or ("-Y" if record.source.startswith("hunyuan") else "+Y")
    )
    return front, up


def collect_items(
    registry: AssetRegistry,
    project_root: Path,
    categories: set[str],
) -> list[PreviewItem]:
    result: list[PreviewItem] = []
    for record in registry.list_all():
        if categories and record.category not in categories:
            continue
        if not record.geometry_path:
            continue
        geometry = registry.resolve_path(record.geometry_path).resolve()
        if not geometry.is_file() or geometry.suffix.lower() != ".glb":
            continue
        try:
            relative = geometry.relative_to(project_root).as_posix()
        except ValueError as error:
            raise ValueError(f"Asset is outside project root: {geometry}") from error
        front, up = _orientation(record)
        result.append(
            PreviewItem(
                record=record,
                geometry_path=geometry,
                relative_geometry_path=relative,
                preview_name=_safe_name(record.asset_id),
                front_axis=front,
                up_axis=up,
                view_mode=(
                    "four_view_planar"
                    if record.category in PLANAR_CATEGORIES
                    else "four_view"
                ),
            )
        )
    return result


def _start_server(project_root: Path) -> tuple[ThreadingHTTPServer, str, threading.Thread]:
    handler = partial(_QuietHandler, directory=str(project_root))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, name="asset-preview", daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    return server, f"http://{host}:{port}", thread


def _manifest_entry(item: PreviewItem, status: str, **extra: Any) -> dict[str, Any]:
    dimensions = list(item.record.dimensions_m) if item.record.dimensions_m else None
    return {
        "asset_id": item.record.asset_id,
        "category": item.record.category,
        "source": item.record.source,
        "license_id": item.record.license_id,
        "geometry_path": item.record.geometry_path,
        "resolved_geometry_path": str(item.geometry_path),
        "preview_file": item.preview_name,
        "front_axis": item.front_axis,
        "up_axis": item.up_axis,
        "view_mode": item.view_mode,
        "dimensions_m": dimensions,
        "status": status,
        **extra,
    }


async def _render(args: argparse.Namespace, items: list[PreviewItem]) -> list[dict[str, Any]]:
    try:
        from playwright.async_api import async_playwright
    except ImportError as error:
        raise RuntimeError(
            "Playwright is required: python -m pip install playwright && "
            "python -m playwright install chromium"
        ) from error

    project_root = args.project_root.resolve()
    output = args.output.resolve()
    previews = output / "previews"
    previews.mkdir(parents=True, exist_ok=True)
    server, base_url, thread = _start_server(project_root)
    queue: asyncio.Queue[PreviewItem] = asyncio.Queue()
    for item in items:
        queue.put_nowait(item)
    results: list[dict[str, Any]] = []
    result_lock = asyncio.Lock()
    completed = 0

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-dev-shm-usage",
                "--use-angle=swiftshader",
                "--enable-unsafe-swiftshader",
                "--ignore-gpu-blocklist",
            ],
        )

        async def worker(worker_id: int) -> None:
            nonlocal completed
            page = await browser.new_page(
                viewport={"width": args.size, "height": args.size},
                device_scale_factor=1,
            )
            try:
                while not queue.empty():
                    try:
                        item = queue.get_nowait()
                    except asyncio.QueueEmpty:
                        return
                    destination = previews / item.preview_name
                    if args.resume and destination.is_file():
                        entry = _manifest_entry(item, "rendered", resumed=True)
                    else:
                        dimensions = (
                            " × ".join(f"{value:.2f}m" for value in item.record.dimensions_m)
                            if item.record.dimensions_m
                            else "unknown scale"
                        )
                        query = urlencode(
                            {
                                "asset": "/" + item.relative_geometry_path,
                                "id": item.record.asset_id,
                                "category": item.record.category,
                                "source": item.record.source,
                                "front": item.front_axis,
                                "up": item.up_axis,
                                "view": item.view_mode,
                                "dimensions": dimensions,
                                "dimensions_m": json.dumps(item.record.dimensions_m),
                                "ground_anchor_fraction": item.record.metadata.get("ground_anchor_fraction", 0),
                            },
                            quote_via=quote,
                            safe="/",
                        )
                        url = f"{base_url}/scripts/asset_preview/index.html?{query}"
                        try:
                            await page.goto(
                                url,
                                wait_until="domcontentloaded",
                                timeout=int(args.timeout * 1000),
                            )
                            await page.wait_for_function(
                                "window.citygAssetPreview && "
                                "(window.citygAssetPreview.ready || window.citygAssetPreview.error)",
                                timeout=int(args.timeout * 1000),
                            )
                            status = await page.evaluate("() => window.citygAssetPreview")
                            if not status.get("ready"):
                                raise RuntimeError(str(status.get("error") or "preview failed"))
                            await page.locator("#frame").screenshot(path=str(destination))
                            entry = _manifest_entry(
                                item,
                                "rendered",
                                rendered_extent=status.get("rendered_extent"),
                            )
                        except Exception as error:  # keep the batch auditable
                            entry = _manifest_entry(item, "failed", error=str(error))
                    async with result_lock:
                        results.append(entry)
                        completed += 1
                        if completed % 25 == 0 or completed == len(items):
                            print(f"Rendered {completed}/{len(items)}", flush=True)
                    queue.task_done()
            finally:
                await page.close()

        try:
            worker_count = max(1, min(args.workers, len(items) or 1))
            await asyncio.gather(*(worker(index) for index in range(worker_count)))
        finally:
            await browser.close()
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
    return sorted(results, key=lambda item: item["asset_id"])


def main() -> None:
    args = _parse_args()
    if args.workers <= 0 or args.size < 256 or args.timeout <= 0:
        raise SystemExit("workers and timeout must be positive; size must be >= 256")
    args.project_root = args.project_root.resolve()
    args.registry = args.registry.resolve()
    args.output = args.output.resolve()
    registry = AssetRegistry(args.registry)
    items = collect_items(registry, args.project_root, set(args.category))
    if args.view_mode:
        items = [replace(item, view_mode=args.view_mode) for item in items]
    if args.limit is not None:
        items = items[: max(0, args.limit)]
    if not items:
        raise SystemExit("No resolvable GLB assets matched the request")
    print(f"Rendering {len(items)} assets to {args.output / 'previews'}", flush=True)
    results = asyncio.run(_render(args, items))
    payload = {
        "schema_version": "cityg.asset_preview_review.v1",
        "registry_path": str(args.registry),
        "review_rule": (
            "Delete unwanted PNG files under previews/. Only entries with status=rendered "
            "are eligible for deletion sync; failed renders are never interpreted as rejection."
        ),
        "rendered_count": sum(item["status"] == "rendered" for item in results),
        "failed_count": sum(item["status"] == "failed" for item in results),
        "assets": results,
    }
    manifest = args.output / "preview_manifest.json"
    manifest.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (args.output / "README.md").write_text(
        "# CityG asset visual review\n\n"
        "1. Open `previews/` in Finder and inspect the PNG files.\n"
        "2. Delete only PNG files for assets you want to reject. Do not rename kept files.\n"
        "3. Keep `preview_manifest.json`; it is the authoritative PNG-to-asset mapping.\n"
        "4. After review, run the sync command without `--apply` and inspect the exact IDs.\n\n"
        "```bash\n"
        f"PYTHONPATH=src python scripts/sync_asset_review_deletions.py {args.output}\n"
        "```\n\n"
        "CityG only removes registry records after a separate `--apply` pass. The registry "
        "is backed up first, and GLB files are retained until a later orphan cleanup.\n",
        encoding="utf-8",
    )
    print(manifest)


if __name__ == "__main__":
    main()
