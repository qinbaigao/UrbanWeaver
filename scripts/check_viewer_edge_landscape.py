"""Headless checks of the added park and terrain, with limited city-edge context."""
import argparse
import asyncio
import base64
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import re
from pathlib import Path
from threading import Thread

from check_viewer_facade_stability import fixture


async def check(url,plan,output,cpu_fast=False,profile='presentation'):
    from playwright.async_api import async_playwright
    park=plan['park_bounds'];hill=plan['hill_bounds']
    px=(park['min_x']+park['max_x'])/2;hx=(hill['min_x']+hill['max_x'])/2
    cy=(park['min_y']+park['max_y'])/2
    views=[('park_overview',[px-420,cy-560,480],[px,cy,0]),
           ('hill_overview',[hx+420,cy-540,260],[hx,cy,24]),
           ('hill_trail',[hx-150,cy-190,85],[hx,cy,40])]
    errors=[];result={}
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True,args=['--disable-dev-shm-usage','--use-angle=swiftshader','--enable-unsafe-swiftshader'])
        page=await browser.new_page(viewport={'width':1400,'height':1000})
        if cpu_fast:
            async def without_shadows(route):
                response=await route.fetch()
                body,count=re.subn(r'(\.shadowMap\.enabled=)[^,;]+',r'\1false',await response.text())
                assert count>=1,'Expected renderer shadow switch in test bundle'
                # Keep screen-space asset LOD and textures; omit multipass
                # shading only in the intercepted test bundle, never on disk.
                body=body.replace('physicalGlass:!0','physicalGlass:!1').replace('environment:!0','environment:!1')
                await route.fulfill(response=response,body=body)
            await page.route('**/assets/index-*.js',without_shadows)
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('console',lambda m:errors.append(m.text) if m.type=='error' and 'Failed to load resource' not in m.text else None)
        await page.add_init_script("window.__CITYG_RENDER_PROFILE__='navigation'")
        await page.goto(url,wait_until='commit')
        await page.wait_for_function('window.citygObservation?.ready',timeout=120000)
        for name,pos,target in views:
            await page.evaluate('v=>citygObservation.setView(v)',dict(mode='overview',kind='global',
                render_profile=profile,appearance='presentation',camera_position=pos,look_at=target,
                up=[0,0,1],fov_deg=46,show_grid=False,show_labels=False,show_outlines=False,
                auto_cutaway=False,sky_preset='clear'))
            status=await page.evaluate('()=>citygObservation.waitForAssets({timeout_ms:180000})')
            assert status['ready'] and not status.get('fallback') and not status.get('failed'),status
            data=await page.evaluate('citygObservation.captureFrame()')
            (output/f'{name}.png').write_bytes(base64.b64decode(data.split(',',1)[1]))
            result[name]=status;print(name,flush=True)
        (output/'render_check.json').write_text(json.dumps({'views':result,'errors':errors,'test_cpu_fast':cpu_fast,'profile':profile},indent=2))
        assert not errors,errors
        await browser.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('viewer',type=Path);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--resume',action='store_true')
    p.add_argument('--cpu-fast',action='store_true',help='Omit shadows, environment and transmission only in this CPU geometry check')
    p.add_argument('--profile',choices=['presentation','navigation'],default='presentation')
    a=p.parse_args()
    if a.resume:target=a.output/'viewer'
    else:
        a.output.mkdir(parents=True,exist_ok=False)
        target,_=fixture(a.viewer,a.output,building_ids=['building_004','building_008','building_061','building_070'],include_edges=True)
    city=json.loads((target/'scene/city.json').read_text())
    plan=city['metadata']['edge_landscape_extension']
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(SimpleHTTPRequestHandler,directory=str(target.resolve())))
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    try:asyncio.run(check(f'http://127.0.0.1:{server.server_port}',plan,a.output,a.cpu_fast,a.profile))
    finally:server.shutdown();server.server_close();thread.join(5)
