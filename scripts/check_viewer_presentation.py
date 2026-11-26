"""Exercise real full-city quality switches and WebGL recovery without opening a browser."""
import argparse
import asyncio
import base64
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
from threading import Thread
import time


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


async def check(url, output, cycles, recovery, width, height, local_view=None):
    from playwright.async_api import async_playwright
    errors, messages, records = [], [], []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=[
            '--disable-dev-shm-usage', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'])
        page = await browser.new_page(viewport={'width':width,'height':height})
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('console', lambda m: messages.append(m.text) if m.type in ('warning','error') else None)
        await page.add_init_script("window.__CITYG_RENDER_PROFILE__='navigation'")
        await page.goto(url, wait_until='commit')
        await page.wait_for_function('window.citygObservation?.ready', timeout=180000)
        view = dict(mode='overview', kind='global',
            render_profile='navigation', camera_position=[2350,-1750,2400], look_at=[640,500,0],
            up=[0,0,1], fov_deg=48, show_grid=False, show_labels=False, show_outlines=False,
            auto_cutaway=False, sky_preset='clear')
        view.update(local_view or {})
        await page.evaluate('v=>citygObservation.setView(v)', view)
        print('Full city Navigation ready', flush=True)
        for cycle in range(cycles):
            for profile in ('presentation', 'navigation'):
                start=time.monotonic()
                await page.select_option('#quality-select',profile)
                await page.wait_for_function('(p)=>citygObservation.getViewState().render_profile===p',
                                             arg=profile, timeout=180000)
                print(f'{cycle}: {profile} selected', flush=True)
                async def monitor():
                    while True:
                        await asyncio.sleep(20)
                        value=await page.evaluate('citygObservation.getAssetStatus()')
                        print('Loading: '+json.dumps({k:value[k] for k in ('pending','loaded','gpu')}),flush=True)
                monitor_task=asyncio.create_task(monitor())
                status=await page.evaluate('()=>citygObservation.waitForAssets({timeout_ms:300000})')
                monitor_task.cancel()
                print(f'{cycle}: {profile} asset barrier ready={status["ready"]}',flush=True)
                if not status['ready'] or status.get('failed') or status.get('fallback'):
                    raise AssertionError(status)
                # Actual rendered readback forces GPU completion, not just a JS loading barrier.
                data=await page.evaluate('citygObservation.captureFrame()')
                (output/f'{cycle}_{profile}.png').write_bytes(base64.b64decode(data.split(',',1)[1]))
                status=await page.evaluate('citygObservation.getAssetStatus()')
                record={'cycle':cycle,'profile':profile,'seconds':round(time.monotonic()-start,2),'status':status}
                records.append(record)
                print(json.dumps({k:record[k] for k in ('cycle','profile','seconds')} | {'gpu':status['gpu']}),flush=True)
                (output/'progress.json').write_text(json.dumps(records,indent=2))
                assert not status['gpu']['context_lost'] and status['gpu']['context_losses']==0,status
        if recovery:
            before=await page.evaluate('citygObservation.getViewState()')
            supported=await page.evaluate('''() => {
                const gl=document.querySelector('#scene-canvas').getContext('webgl2');
                window.testLoss=gl.getExtension('WEBGL_lose_context');
                window.testLoss?.loseContext(); return !!window.testLoss;
            }''')
            assert supported,'WEBGL_lose_context unavailable'
            await page.wait_for_function('citygObservation.getAssetStatus().gpu.context_lost', timeout=10000)
            assert await page.locator('#gpu-recovery-notice').is_visible()
            await page.evaluate('window.testLoss.restoreContext()')
            await page.wait_for_function('!citygObservation.getAssetStatus().gpu.context_lost',timeout=60000)
            after=await page.evaluate('citygObservation.getViewState()')
            (output/'recovery_camera.json').write_text(json.dumps({'before':before,'after':after},indent=2))
            assert after['render_profile']=='navigation' and math.dist(after['camera_position'],before['camera_position'])<1e-6
            assert math.dist(after['look_at'],before['look_at'])<1e-6
            status=await page.evaluate('citygObservation.getAssetStatus()')
            records.append({'recovery':status})
            data=await page.evaluate('citygObservation.captureFrame()')
            (output/'recovered.png').write_bytes(base64.b64decode(data.split(',',1)[1]))
            print('Injected WebGL loss restored; camera preserved',flush=True)
        await browser.close()
    graphics_errors=[m for m in messages if 'INVALID_OPERATION' in m or 'OUT_OF_MEMORY' in m]
    report={'records':records,'errors':errors,'graphics_errors':graphics_errors,'console':messages}
    (output/'render_check.json').write_text(json.dumps(report,indent=2))
    assert not errors,errors
    assert not graphics_errors,graphics_errors


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('viewer',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--cycles',type=int,default=3)
    parser.add_argument('--recovery',action='store_true')
    parser.add_argument('--width',type=int,default=1100)
    parser.add_argument('--height',type=int,default=800)
    parser.add_argument('--building',help='Optional local facade inspection instead of city-wide view')
    args=parser.parse_args(); args.output.mkdir(parents=True,exist_ok=True)
    local_view=None
    if args.building:
        city=json.loads((args.viewer/'scene/city.json').read_text())
        building=next(b for d in city['districts'] for p in d['parcels'] for b in p['buildings']
                      if b['id']==args.building)
        f=building['footprint'];x=(f['min_x']+f['max_x'])/2;y=(f['min_y']+f['max_y'])/2
        span=max(f['max_x']-f['min_x'],f['max_y']-f['min_y'])
        local_view=dict(camera_position=[x+span*1.6,y-span*2,span*1.5+40],look_at=[x,y,15])
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=str(args.viewer.resolve())))
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        asyncio.run(asyncio.wait_for(check(f'http://127.0.0.1:{server.server_port}',args.output,
                                         args.cycles,args.recovery,args.width,args.height,local_view),1800))
    finally:
        server.shutdown();server.server_close();thread.join(5)
