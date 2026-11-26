"""Exercise real PNG download and camera/profile restoration without desktop tabs."""
import argparse
import asyncio
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import struct
from threading import Thread

from cityg.serialization import save_json


def assert_same_view(before, after):
    for key, value in before.items():
        if isinstance(value, list):
            assert all(math.isclose(a, b, rel_tol=0, abs_tol=1e-8)
                       for a, b in zip(value, after[key])), (key, value, after[key])
        else:
            assert value == after[key], (key, value, after[key])


async def check(url, output, long_edge, button, failure_test):
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=[
            '--disable-dev-shm-usage', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'])
        page = await browser.new_page(viewport={'width':1200, 'height':800}, accept_downloads=True)
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        await page.add_init_script("window.__CITYG_RENDER_PROFILE__ = 'navigation'")
        await page.goto(url, wait_until='commit')
        await page.wait_for_function('window.citygObservation?.ready', timeout=120000)
        # Keep navigation active to verify that export upgrades it temporarily.
        await page.evaluate("""() => citygObservation.setView({kind:'global', mode:'overview',
          render_profile:'navigation',appearance:'presentation',
          show_grid:false,show_labels:false,show_outlines:false})""")
        before = await page.evaluate('citygObservation.getViewState()')
        await page.locator('#hq-screenshot-button').wait_for(state='visible')
        async with page.expect_download(timeout=240000) as pending:
            if button:
                await page.locator('#hq-screenshot-button').click()
                await page.wait_for_function('window.citygObservation.lastSnapshot', timeout=240000)
                result = await page.evaluate('citygObservation.lastSnapshot')
            else:
                result = await asyncio.wait_for(page.evaluate(
                    '(longEdge) => citygObservation.saveHighQualityImage({longEdge})', long_edge), 240)
        download = await pending.value
        png = output/'hq_snapshot.png'
        await download.save_as(str(png))
        await page.wait_for_function("!document.querySelector('#hq-screenshot-button').disabled")
        after = await page.evaluate('citygObservation.getViewState()')
        assert_same_view(before, after)
        header = png.read_bytes()[:24]
        assert header[:8] == b'\x89PNG\r\n\x1a\n'
        dimensions = struct.unpack('>II', header[16:24])
        assert dimensions == (result['width'], result['height'])
        assert result['assets']['shading']['shadows']
        assert result['assets']['shading']['physical_glass']
        assert result['assets']['shading']['textures']
        if result['assets']['environment_state'] != 'not_requested':
            assert result['assets']['shading']['environment']
            assert result['assets']['environment_state'] == 'ready'
        assert await page.evaluate("!document.querySelector('#viewport').inert")
        if failure_test:
            await page.evaluate("""() => {
              window.originalToBlob = HTMLCanvasElement.prototype.toBlob;
              HTMLCanvasElement.prototype.toBlob = function(callback) {callback(null);};
            }""")
            failure = await page.evaluate("""async () => {
              try {await citygObservation.saveHighQualityImage({longEdge:320,download:false});return null;}
              catch(error) {return String(error.message);}
              finally {HTMLCanvasElement.prototype.toBlob=window.originalToBlob;}
            }""")
            assert 'PNG encoding failed' in (failure or ''), failure
            assert_same_view(before, await page.evaluate('citygObservation.getViewState()'))
            assert await page.evaluate("!document.querySelector('#viewport').inert && !document.querySelector('#hq-screenshot-button').disabled")
            result['encode_failure_restore_passed'] = True
        assert not errors, errors
        result.update({'camera_and_profile_restored':True, 'download_verified':True,
            'button_clicked':button, 'renderer':'SwiftShader (software)', 'page_errors':errors})
        save_json(result, output/'snapshot_check.json')
        print(json.dumps(result, ensure_ascii=False), flush=True)
        await browser.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('viewer', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--long-edge', type=int, default=640)
    parser.add_argument('--button', action='store_true', help='Click real 2560px UI button')
    parser.add_argument('--failure-test', action='store_true')
    args = parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        parser.error('Use a new output directory')
    args.output.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(SimpleHTTPRequestHandler, directory=str(args.viewer.resolve())))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        asyncio.run(check(f'http://127.0.0.1:{server.server_port}', args.output,
            args.long_edge, args.button, args.failure_test))
    except Exception as exc:
        save_json({'ok': False, 'error': type(exc).__name__, 'message': str(exc),
            'viewer': str(args.viewer), 'renderer': 'SwiftShader (software)',
            'long_edge': 2560 if args.button else args.long_edge}, args.output/'snapshot_failure.json')
        raise
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)


if __name__ == '__main__':
    main()
