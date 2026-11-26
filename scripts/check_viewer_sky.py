"""Check outdoor sky/terrain transitions on real ground with building proxies.

No city regeneration, GLB downloads, visible browser, or vLLM required.
Uses the small ground fixture to isolate sky rendering from asset complexity.
"""
import argparse
import asyncio
import base64
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
from threading import Thread

from check_viewer_ground import fixture
from cityg.viewer import viewer_static_dir


async def check(url, target, output):
    from playwright.async_api import async_playwright
    city = json.loads((target / 'scene/city.json').read_text())
    b = city['bounds']
    x, y = (b['min_x'] + b['max_x']) / 2, (b['min_y'] + b['max_y']) / 2
    span = max(b['max_x'] - b['min_x'], b['max_y'] - b['min_y'])
    views = {
        'aerial_oblique': ([x + span*.9, y - span*1.1, span*.8], [x, y, 20]),
        'aerial_high': ([x + span*.9, y - span*1.1, span*1.8], [x, y, 0]),
        # Look away from the city: foreground, far outskirts, horizon and sky.
        'street_horizon': ([x, b['min_y']-10, 1.7], [x, b['min_y']-span, 35]),
    }
    errors, results = [], {}
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=[
            '--disable-dev-shm-usage', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'])
        page = await browser.new_page(viewport={'width':1200, 'height':900})
        page.on('pageerror', lambda e: errors.append(str(e)))
        # Portable bootstrap probes /api/config and optional reports; their 404s
        # are expected. Required assets are checked by the readiness barrier.
        page.on('console', lambda m: errors.append(m.text)
                if m.type == 'error' and 'Failed to load resource' not in m.text else None)
        await page.add_init_script("window.__CITYG_RENDER_PROFILE__='navigation'")
        await page.goto(url, wait_until='commit')
        await page.wait_for_function('window.citygObservation?.ready', timeout=120000)
        for name, (camera, look_at) in views.items():
            await page.evaluate('v=>citygObservation.setView(v)', dict(
                kind='global', mode='overview', appearance='presentation',
                render_profile='presentation', camera_position=camera, look_at=look_at,
                up=[0,0,1], fov_deg=44, show_grid=False, show_labels=False,
                show_outlines=False, auto_cutaway=False, sky_preset='clear'))
            status = await page.evaluate('()=>citygObservation.waitForAssets({timeout_ms:120000})')
            assert status['ready'] and not status.get('fallback'), status
            data = await page.evaluate('citygObservation.captureFrame()')
            (output / f'{name}.png').write_bytes(base64.b64decode(data.split(',', 1)[1]))
            results[name] = {'assets':status, 'view':await page.evaluate('citygObservation.getViewState()')}
            print(name, flush=True)
        (output / 'sky_check.json').write_text(json.dumps({'views':results, 'errors':errors}, indent=2))
        assert not errors, errors
        await browser.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--reuse-fixture', action='store_true', help='Refresh frontend and recheck an existing sky fixture')
    args = parser.parse_args()
    if args.reuse_fixture:
        target = args.output / 'viewer'
        if not (target / 'scene/geometry_manifest.json').is_file():
            raise ValueError('Missing fixture geometry')
        shutil.copytree(viewer_static_dir(), target, dirs_exist_ok=True)
    else:
        args.output.mkdir(parents=True, exist_ok=False)
        target, _, count = fixture(args.source, args.output)
        print(f'Sky fixture: {count} primitives', flush=True)
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(SimpleHTTPRequestHandler, directory=str(target.resolve())))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        asyncio.run(check(f'http://127.0.0.1:{server.server_port}', target, args.output))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)


if __name__ == '__main__':
    main()
