"""Headless regression for sky presets, solar rotation, indoor suppression and HQ export."""
import argparse
import asyncio
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from threading import Thread


async def check(url, output):
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True,args=['--disable-dev-shm-usage','--use-angle=swiftshader','--enable-unsafe-swiftshader'])
        page=await browser.new_page(viewport={'width':1200,'height':800},accept_downloads=True)
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('console',lambda m:errors.append(m.text) if m.type=='error' and 'Failed to load resource' not in m.text else None)
        await page.add_init_script("window.__CITYG_RENDER_PROFILE__='navigation'")
        await page.goto(url,wait_until='commit')
        await page.wait_for_function('window.citygObservation?.ready',timeout=120000)
        await page.evaluate("""()=>citygObservation.setView({kind:'global',mode:'overview',render_profile:'navigation',
          appearance:'presentation',camera_position:[280,-65,45],look_at:[100,110,55],
          show_grid:false,show_labels:false,show_outlines:false})""")
        results={}
        for preset in ['clear','cloudy','sunset']:
            await page.select_option('#sky-select',preset)
            async with page.expect_download(timeout=180000) as pending:
                result=await asyncio.wait_for(page.evaluate('()=>citygObservation.saveHighQualityImage({longEdge:960})'),180)
            await (await pending.value).save_as(str(output/f'{preset}.png'))
            assert result['assets']['sky']['active'],result
            assert result['assets']['sky']['selected']==preset
            assert result['assets']['environment_state']=='ready'
            results[preset]=result
        # A texture being cached must not leak into indoor inspection or night.
        for mode in ['floor','floor_plan','room']:
            await page.evaluate('mode=>citygObservation.setView({mode,render_profile:"presentation",sky_preset:"clear"})',mode)
            status=await page.evaluate('()=>citygObservation.waitForAssets({timeout_ms:60000})')
            assert status['ready'] and not status['sky']['active'],status
        await page.evaluate('()=>citygObservation.setView({mode:"overview",render_profile:"presentation",sky_preset:"clear",sky_rotation_deg:0})')
        original=await page.evaluate('()=>citygObservation.waitForAssets({timeout_ms:60000})')
        await page.evaluate('()=>citygObservation.setView({mode:"overview",render_profile:"presentation",sky_rotation_deg:90})')
        rotated=await page.evaluate('()=>citygObservation.waitForAssets({timeout_ms:60000})')
        a=original['sky']['sun_direction'];b=rotated['sky']['sun_direction']
        assert abs(a[2]-b[2])<1e-6
        assert abs(b[0]+a[1])<1e-6 and abs(b[1]-a[0])<1e-6,(a,b)
        await page.evaluate('()=>citygObservation.setView({mode:"overview",daylight:false})')
        assert not (await page.evaluate('citygObservation.getAssetStatus()'))['sky']['active']
        await page.evaluate('()=>citygObservation.setView({mode:"overview",daylight:true,sky_preset:"none"})')
        assert not (await page.evaluate('citygObservation.getAssetStatus()'))['sky']['active']
        assert not errors,errors
        results.update(indoor_suppression=True,solar_rotation=True,night_and_plain=True,page_errors=errors)
        (output/'sky_check.json').write_text(json.dumps(results,indent=2))
        print(json.dumps({k:v['assets']['sky'] for k,v in results.items() if isinstance(v,dict)}),flush=True)
        await browser.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('viewer',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    a=parser.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(SimpleHTTPRequestHandler,directory=str(a.viewer.resolve())))
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    try:asyncio.run(check(f'http://127.0.0.1:{server.server_port}',a.output))
    finally:server.shutdown();server.server_close();thread.join(5)


if __name__=='__main__':main()
