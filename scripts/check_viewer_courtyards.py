"""Render real courtyard geometry/assets without opening the user's browser.

Fixtures symlink asset resources, so they are diagnostics, not portable exports.
Use --profile presentation for shadows/PBR; paper_capture is a geometry audit.
"""
import argparse
import asyncio
import base64
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
from threading import Thread

from check_viewer_facade_stability import fixture


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass


def views_for(record,building,profile='presentation'):
    f=building['footprint'];bx=(f['min_x']+f['max_x'])/2;by=(f['min_y']+f['max_y'])/2
    nodes=record['nodes']
    chosen=next((n for n in nodes if n['kind'] in {'grove','pavilion','promenade'}),None)
    chosen=chosen or next((n for n in nodes if n['kind'] in {'terrace','garden','kiosk'}),nodes[0])
    x,y=chosen['center'];dx,dy=x-bx,y-by;length=max(math.hypot(dx,dy),1)
    dx/=length;dy/=length
    span=max(chosen.get('size_m',[16,10]))
    distance=max(25,span*1.5);side=max(11,span*.5);height=max(22,span*1.1)
    poses=[('detail',[x+dx*distance-dy*side,y+dy*distance+dx*side,height],[x,y,1]),
           ('parcel',[bx+dx*150-dy*30,by+dy*150+dx*30,150],[bx,by,6])]
    return [dict(view_id=f'courtyard_{record["parcel_id"]}_{name}',mode='overview',kind='global',
        render_profile=profile,appearance='presentation',camera_position=position,look_at=target,
        up=[0,0,1],fov_deg=48,show_grid=False,show_labels=False,show_outlines=False,
        auto_cutaway=False,sky_preset='clear' if profile=='presentation' else 'none',
        reset_visibility=True) for name,position,target in poses]


async def capture(url,output,record,building,profile):
    from playwright.async_api import async_playwright
    errors=[]
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True,args=['--disable-dev-shm-usage',
            '--use-angle=swiftshader','--enable-unsafe-swiftshader'])
        page=await browser.new_page(viewport={'width':1600,'height':1000},accept_downloads=True)
        page.on('pageerror',lambda e:errors.append(str(e)))
        await page.add_init_script("window.__CITYG_RENDER_PROFILE__='navigation'")
        await page.goto(url,wait_until='commit')
        await page.wait_for_function('window.citygObservation?.ready',timeout=120000)
        print(record['parcel_id']+' Viewer ready',flush=True)
        results={}
        for view in views_for(record,building,profile):
            name=view['view_id'].rsplit('_',1)[1]
            # Preload in explicit-frame mode; use the actual HQ PNG workflow
            # for one fully shaded frame instead of continuously redrawing a
            # stationary camera on the server's software rasterizer.
            await page.evaluate('v=>citygObservation.setView(v)',{**view,'render_profile':'paper_capture'})
            status=await page.evaluate('()=>citygObservation.waitForAssets({timeout_ms:180000})')
            if not status['ready'] or status.get('failed') or status.get('fallback'):
                raise AssertionError(status)
            if profile=='presentation':
                async with page.expect_download(timeout=240000) as pending:
                    snapshot=await page.evaluate('()=>citygObservation.saveHighQualityImage({longEdge:1200,download:true,timeoutMs:180000})')
                download=await pending.value
                await download.save_as(output/f'{name}.png')
                results[name]={'preload':status,'snapshot':snapshot}
            else:
                data=await page.evaluate('citygObservation.captureFrame()')
                (output/f'{name}.png').write_bytes(base64.b64decode(data.split(',',1)[1]))
                results[name]=status
            print(record['parcel_id']+' '+name+' captured',flush=True)
        await browser.close()
    if errors:raise AssertionError(errors)
    return {'views':results,'errors':errors,'profile':profile,'parcel_id':record['parcel_id']}


def run(source,report,output,profile,only=None,save_views=False):
    city=json.loads((source/'scene/city.json').read_text())
    parcels={p['id']:p for d in city['districts'] for p in d['parcels']}
    results=[]
    for record in report['parcels']:
        if only and record['parcel_id']!=only:continue
        target=output/record['parcel_id'];target.mkdir(parents=True,exist_ok=True)
        b=parcels[record['parcel_id']]['buildings'][0]
        viewer,_=fixture(source,target,include_planting=True,include_sites=True,building_ids=[b['id']],
                         include_parcel_context=True)
        server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=str(viewer.resolve())))
        thread=Thread(target=server.serve_forever,daemon=True);thread.start()
        try:result=asyncio.run(asyncio.wait_for(capture(f'http://127.0.0.1:{server.server_port}',target,record,b,profile),600))
        finally:server.shutdown();server.server_close();thread.join(5)
        (target/'render_check.json').write_text(json.dumps(result,indent=2))
        results.append(result)
    (output/'render_check.json').write_text(json.dumps(results,indent=2))
    if save_views:
        config_path=source/'viewer-config.json';config=json.loads(config_path.read_text())
        old=(source/config.get('paper_views','figure1_views.json')).resolve()
        if not old.is_relative_to(source.resolve()):raise ValueError('Saved-view path must be inside Viewer')
        plan=json.loads(old.read_text()) if old.exists() else {'selected_views':[]}
        plan['selected_views']=[v for v in plan['selected_views'] if not v['view_id'].startswith('courtyard_')]
        for record in report['parcels']:
            plan['selected_views'].extend(views_for(record,parcels[record['parcel_id']]['buildings'][0]))
        (source/'courtyard_review_views.json').write_text(json.dumps(plan,indent=2))
        config['paper_views']='./courtyard_review_views.json'
        config_path.write_text(json.dumps(config,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('viewer',type=Path)
    p.add_argument('--report',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--profile',choices=['paper_capture','presentation'],default='presentation')
    p.add_argument('--only')
    p.add_argument('--save-views',action='store_true',help='Append reviewed cameras to portable Viewer, retaining existing views')
    a=p.parse_args();run(a.viewer.resolve(),json.loads(a.report.read_text()),a.output.resolve(),a.profile,a.only,a.save_views)
