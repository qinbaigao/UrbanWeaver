#!/usr/bin/env python3
"""Capture a CityG Web Viewer page without a desktop session.

Start the Viewer separately, for example:
  PYTHONPATH=src python -m cityg view outputs/.../openusd --host 127.0.0.1 --port 5187 --no-browser
Then run this script against http://127.0.0.1:5187.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True, help="Viewer URL")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--width", type=int, default=1600)
    parser.add_argument("--height", type=int, default=1000)
    parser.add_argument("--wait-ms", type=int, default=3000)
    parser.add_argument(
        "--quality-profile",
        choices=("interactive", "review", "presentation", "high_fidelity"),
        default="review",
    )
    parser.add_argument(
        "--mode",
        choices=("overview", "building", "floor", "floor_plan", "room", "full"),
        default="overview",
    )
    parser.add_argument(
        "--high-fidelity-overview", action="store_true",
        help="Load real outdoor GLB assets in the city-wide overview",
    )
    parser.add_argument(
        "--no-sandbox", action="store_true",
        help="Use only when the server/container cannot create a Chromium sandbox",
    )
    return parser.parse_args()


async def capture(args: argparse.Namespace) -> None:
    try:
        from playwright.async_api import async_playwright
    except ImportError as error:
        raise SystemExit(
            "Playwright is not installed. Run: python -m pip install playwright "
            "and python -m playwright install chromium"
        ) from error

    args.output.parent.mkdir(parents=True, exist_ok=True)
    launch_args = [
        "--disable-dev-shm-usage",
        "--use-angle=swiftshader",
        "--enable-unsafe-swiftshader",
        "--ignore-gpu-blocklist",
    ]
    if args.no_sandbox:
        launch_args.append("--no-sandbox")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True, args=launch_args)
        page = await browser.new_page(
            viewport={"width": args.width, "height": args.height},
            device_scale_factor=1,
        )
        initial_view = {"mode": args.mode}
        if args.high_fidelity_overview:
            initial_view["high_fidelity_overview"] = True
        await page.add_init_script(
            "window.__CITYG_INITIAL_OBSERVATION_VIEW__ = "
            + json.dumps(initial_view)
            + "; window.__CITYG_RENDER_PROFILE__ = "
            + json.dumps(args.quality_profile)
            + ";"
        )
        # Viewer pages may keep a connection alive for telemetry/assets, so
        # networkidle is not a reliable readiness condition for WebGL scenes.
        await page.goto(args.url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_function(
            "window.citygObservation && window.citygObservation.ready",
            timeout=180000,
        )
        status = await page.evaluate(
            """async () => window.citygObservation?.waitForAssets
                ? window.citygObservation.waitForAssets({ timeout_ms: 60000, quiet_ms: 180 })
                : { ready: true, signal_available: false }"""
        )
        if not status.get("ready"):
            raise RuntimeError(f"Viewer assets did not become ready: {status}")
        await page.wait_for_timeout(max(0, args.wait_ms))
        data_url = await page.evaluate(
            """async () => window.citygObservation?.captureFrame
                ? window.citygObservation.captureFrame()
                : (() => {
                    const canvas = document.querySelector('#scene-canvas');
                    return canvas && canvas.width && canvas.height
                        ? canvas.toDataURL('image/png') : null;
                })()"""
        )
        if not data_url:
            raise RuntimeError("Viewer scene-canvas was not ready for screenshot")
        args.output.write_bytes(base64.b64decode(data_url.split(",", 1)[1]))
        await browser.close()
    print(args.output.resolve())


if __name__ == "__main__":
    asyncio.run(capture(parse_args()))
