"""Render actual placed metro entries and surrounding parcels without loading the full city."""
import argparse
import asyncio
import base64
from functools import partial
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
import json
import math
from pathlib import Path
from threading import Thread

from check_viewer_facade_stability import fixture


async def check(url,rows,output):
    from playwright.async_api import async_playwright
    errors=[];results={}
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True,args=['--disable-dev-shm-usage','--use-angle=swiftshader','--enable-unsafe-swiftshader'])
        page=await browser.new_page(viewport={'width':1500,'height':1000})
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('console',lambda m:errors.append(m.text) if m.type=='error' and 'Failed to load resource' not in m.text else None)
        await page.add_init_script("window.__CITYG_RENDER_PROFILE__='navigation'")
        await page.goto(url,wait_until='commit')
        await page.wait_for_function('window.citygObservation?.ready',timeout=120000)
        for row in rows:
            x,y=row['center_xy'];gx,gy=row['entrance_approach'];length=math.hypot(gx-x,gy-y)
            vx,vy=(gx-x)/length,(gy-y)/length
            for tag,distance,height in [('entrance',22,12),('parcel',50,45)]:
                view={'mode':'overview','kind':'global','render_profile':'presentation','appearance':'presentation',
                    'camera_position':[x+vx*distance-vy*distance*.5,y+vy*distance+vx*distance*.5,height],
                    'look_at':[x,y,1.6],'up':[0,0,1],'fov_deg':44,'show_grid':False,'show_labels':False,
                    'show_outlines':False,'auto_cutaway':False,'sky_preset':'clear'}
                await page.evaluate('v=>citygObservation.setView(v)',view)
                status=await page.evaluate('()=>citygObservation.waitForAssets({timeout_ms:120000})')
                assert status['ready'] and not status.get('fallback'),status
                data=await page.evaluate('citygObservation.captureFrame()')
                key=f'{row["id"]}_{tag}'
                (output/f'{key}.png').write_bytes(base64.b64decode(data.split(',',1)[1]))
                results[key]=status;print(key,flush=True)
        (output/'render_check.json').write_text(json.dumps({'results':results,'errors':errors},indent=2))
        assert not errors,errors
        await browser.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('viewer',type=Path);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    geometry=json.loads((args.viewer/'scene/geometry_manifest.json').read_text())
    report=geometry['metadata']['metro_entrances'];rows=[];seen=set()
    for row in report['entrances']:
        if row['asset_id'] not in seen:rows.append(row);seen.add(row['asset_id'])
    if not rows:raise ValueError('No metro entrances in source')
    city=json.loads((args.viewer/'scene/city.json').read_text())
    wanted={row['parcel_id'] for row in rows}
    bids=[b['id'] for d in city['districts'] for parcel in d['parcels'] if parcel['id'] in wanted for b in parcel['buildings']]
    target,_=fixture(args.viewer,args.output,building_ids=bids,include_sites=True)
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(SimpleHTTPRequestHandler,directory=str(target.resolve())))
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    try:asyncio.run(check(f'http://127.0.0.1:{server.server_port}',rows,args.output))
    finally:server.shutdown();server.server_close();thread.join(5)


if __name__=='__main__':main()
