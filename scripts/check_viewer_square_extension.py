"""Full-city navigation smoke and focused, real-facade extension screenshots."""
import argparse
import asyncio
import base64
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from threading import Thread

from check_viewer_facade_stability import fixture


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass


async def capture(url,output,buildings=None):
    from playwright.async_api import async_playwright
    errors=[];results={}
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True,args=['--disable-dev-shm-usage',
            '--use-angle=swiftshader','--enable-unsafe-swiftshader'])
        page=await browser.new_page(viewport={'width':1000,'height':800})
        page.on('pageerror',lambda e:errors.append(str(e)))
        await page.add_init_script("window.__CITYG_RENDER_PROFILE__='navigation'")
        await page.goto(url,wait_until='commit')
        await page.wait_for_function('window.citygObservation?.ready',timeout=120000)
        print('Viewer ready',flush=True)
        if buildings is None:
            views=[('square_city_navigation',[2350,-1750,2400],[640,500,0],'navigation')]
        else:
            views=[]
            for b in buildings:
                f=b['footprint'];x=(f['min_x']+f['max_x'])/2;y=(f['min_y']+f['max_y'])/2
                span=max(f['max_x']-f['min_x'],f['max_y']-f['min_y'])
                views.append((b['id'],[x+span*1.4,y-span*1.9,span*1.3+40],[x,y,15],'paper_capture'))
        for name,position,target,profile in views:
            result=await page.evaluate('v=>citygObservation.setView(v)',dict(mode='overview',kind='global',
                render_profile=profile,appearance='presentation',camera_position=position,look_at=target,
                up=[0,0,1],fov_deg=48,show_grid=False,show_labels=False,show_outlines=False,
                auto_cutaway=False,sky_preset='none'))
            print(name+' camera set: '+json.dumps({k:result[k] for k in
                ('ready','render_profile','visible_primitive_count')}),flush=True)
            status=await page.evaluate('()=>citygObservation.waitForAssets({timeout_ms:90000})')
            assert status['ready'] and not status.get('failed') and not status.get('fallback'),status
            data=await page.evaluate('citygObservation.captureFrame()')
            (output/(name+'.png')).write_bytes(base64.b64decode(data.split(',',1)[1]))
            results[name]=status;print('Captured '+name,flush=True)
        assert not errors,errors
        await browser.close()
    return {'views':results,'errors':errors}


def serve_capture(viewer,output,buildings=None):
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=str(viewer.resolve())))
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    try:return asyncio.run(asyncio.wait_for(capture(f'http://127.0.0.1:{server.server_port}',output,buildings),240))
    finally:server.shutdown();server.server_close();thread.join(5)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('viewer',type=Path);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--resume',action='store_true')
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=a.resume)
    report={'overview':serve_capture(a.viewer,a.output)}
    city=json.loads((a.viewer/'scene/city.json').read_text())
    ids=city['metadata']['north_south_extension']['added_buildings']
    target,buildings=fixture(a.viewer,a.output,building_ids=[ids[0],ids[7],ids[24],ids[31]])
    report['focused_facades']=serve_capture(target,a.output,buildings)
    (a.output/'render_check.json').write_text(json.dumps(report,indent=2))
