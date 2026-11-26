#!/usr/bin/env python3
"""Render selected CityG observation views through the portable Viewer.

Start a Viewer server first, then run:
  python scripts/render_observation_plan.py \
    --url http://127.0.0.1:5189 \
    --plan outputs/.../observation_plan.json \
    --output outputs/.../observations
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--width", type=int, default=1400)
    parser.add_argument("--height", type=int, default=900)
    parser.add_argument("--wait-ms", type=int, default=1200)
    parser.add_argument("--asset-timeout-ms", type=int, default=60000)
    parser.add_argument("--max-views", type=int)
    return parser.parse_args()


async def render(args: argparse.Namespace) -> None:
    try:
        from playwright.async_api import async_playwright
    except ImportError as error:
        raise SystemExit(
            "Playwright is not installed. Run: python -m pip install playwright "
            "and python -m playwright install chromium"
        ) from error

    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    views = plan.get("selected_views", [])
    if args.max_views is not None:
        views = views[: max(0, args.max_views)]
    if not views:
        raise SystemExit("Observation plan has no selected_views")
    args.output.mkdir(parents=True, exist_ok=True)
    launch_args = [
        "--disable-dev-shm-usage",
        "--use-angle=swiftshader",
        "--enable-unsafe-swiftshader",
        "--ignore-gpu-blocklist",
    ]
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True, args=launch_args)
        asset_statuses = {}
        page = await browser.new_page(
            viewport={"width": args.width, "height": args.height},
            device_scale_factor=1,
        )
        try:
            await page.add_init_script(
                "window.__CITYG_INITIAL_OBSERVATION_VIEW__ = "
                + json.dumps(views[0], ensure_ascii=False)
                + "; window.__CITYG_RENDER_PROFILE__ = 'review';"
            )
            await page.goto(args.url, wait_until="commit", timeout=60000)
            await page.wait_for_function(
                "window.citygObservation && window.citygObservation.ready",
                timeout=180000,
            )
            for index, view in enumerate(views):
                view_status = await page.evaluate(
                    "(view) => window.citygObservation.setView(view)", view
                )
                status = await page.evaluate(
                    """async (options) => {
                        if (!window.citygObservation?.waitForAssets) {
                            return { ready: true, signal_available: false };
                        }
                        const value = await window.citygObservation.waitForAssets(options);
                        return { ...value, signal_available: true };
                    }""",
                    {"timeout_ms": max(100, args.asset_timeout_ms), "quiet_ms": 180},
                )
                asset_statuses[str(view["view_id"])] = {
                    **status,
                    "view_status": view_status,
                }
                if not status.get("ready"):
                    raise RuntimeError(
                        f"Viewer assets did not become ready for {view['view_id']}: {status}"
                    )
                await page.wait_for_timeout(max(0, args.wait_ms))
                output = args.output / f"{view['view_id']}.png"
                try:
                    data_url = await asyncio.wait_for(
                        page.evaluate(
                            """() => window.citygObservation?.captureFrame
                                ? window.citygObservation.captureFrame()
                                : document.querySelector('#scene-canvas')?.toDataURL('image/png')"""
                        ),
                        timeout=30.0,
                    )
                    if not data_url:
                        raise RuntimeError("Viewer scene-canvas was not ready for screenshot")
                    output.write_bytes(base64.b64decode(data_url.split(",", 1)[1]))
                except asyncio.TimeoutError:
                    await page.locator("#scene-canvas").screenshot(
                        path=str(output), timeout=30_000
                    )
                print(f"[{index + 1}/{len(views)}] {output.resolve()}")
        finally:
            await page.close()
        (args.output / "asset_load_status.json").write_text(
            json.dumps(
                {
                    "policy": "viewer_generation_scoped_asset_barrier_v1",
                    "views": asset_statuses,
                },
                indent=2,
                ensure_ascii=False,
            ) + "\n",
            encoding="utf-8",
        )
        await browser.close()


if __name__ == "__main__":
    asyncio.run(render(parse_args()))
