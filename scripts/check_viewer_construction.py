"""Small real-geometry worksite screenshots; no full-city or forest rendering."""
import argparse
import asyncio
import base64
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
from threading import Thread

from cityg.viewer import viewer_static_dir


def fixture(source, output):
    target=output/'viewer';shutil.copytree(viewer_static_dir(),target)
    (target/'scene').mkdir()
    config=json.loads((source/'viewer-config.json').read_text())
    city=json.loads((source/'scene/city.json').read_text())
    geom=json.loads((source/'scene/geometry_manifest.json').read_text())
    primitives=list(geom['primitives'])
    for chunk in geom.get('streaming',{}).get('chunks',[]):
        primitives.extend(json.loads((source/'scene'/chunk['file']).read_text())['primitives'])
    geom.pop('streaming',None)
    geom['primitives']=[p for p in primitives if p.get('metadata',{}).get('construction_system')]
    ids={p['metadata']['asset_id'] for p in geom['primitives'] if p.get('metadata',{}).get('resolved_asset')}
    used={p['material_id'] for p in geom['primitives']}
    geom['materials']=[m for m in geom['materials'] if m['id'] in used]
    config.update(paper_views=None,files=['city.json','geometry_manifest.json'],asset_lods={},
        asset_files={a:f for a,f in config['asset_files'].items() if a in ids},
        material_textures={a:v for a,v in config['material_textures'].items() if a in used})
    for folder,files in [('assets',set(config['asset_files'].values())),
        ('textures',{f for channels in config['material_textures'].values() for f in channels.values()})]:
        (target/folder).mkdir(exist_ok=True)
        for f in files:(target/folder/f).symlink_to((source/folder/f).resolve())
    for name,data in [('viewer-config.json',config),('scene/city.json',city),('scene/geometry_manifest.json',geom)]:
        (target/name).write_text(json.dumps(data))
    return target,city['metadata']['construction_sites']['sites']


async def check(url, records, output):
    from playwright.async_api import async_playwright
    errors=[];report={}
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True,args=['--disable-dev-shm-usage','--use-angle=swiftshader','--enable-unsafe-swiftshader'])
        page=await browser.new_page(viewport={'width':1200,'height':900})
        page.on('pageerror',lambda error:errors.append(str(error)))
        await page.add_init_script("window.__CITYG_RENDER_PROFILE__='paper_capture'")
        await page.goto(url,wait_until='commit')
        await page.wait_for_function('window.citygObservation?.ready',timeout=90000)
        print('Viewer ready',flush=True)
        for r in records:
            x0,y0,x1,y1=r['work_bounds'];x=(x0+x1)/2;y=(y0+y1)/2
            await page.evaluate('v=>citygObservation.setView(v)',dict(mode='overview',kind='global',
                render_profile='paper_capture',appearance='presentation',camera_position=[x-120,y-150,112],
                look_at=[x,y,12],up=[0,0,1],fov_deg=42,show_grid=False,show_labels=False,
                show_outlines=False,auto_cutaway=False,sky_preset='none'))
            print(r['id'],'camera set',flush=True)
            status=await page.evaluate('()=>citygObservation.waitForAssets({timeout_ms:60000})')
            assert status['ready'] and not status.get('failed') and not status.get('fallback'),status
            print(r['id'],'assets ready',flush=True)
            data=await page.evaluate('citygObservation.captureFrame()')
            (output/(r['id']+'.png')).write_bytes(base64.b64decode(data.split(',',1)[1]))
            report[r['id']]=status
            print(r['id'],'captured',flush=True)
        (output/'render_check.json').write_text(json.dumps(dict(views=report,errors=errors,profile='paper_capture'),indent=2))
        assert not errors,errors
        await browser.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('viewer',type=Path)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    target,records=fixture(a.viewer,a.output)
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(SimpleHTTPRequestHandler,directory=str(target.resolve())))
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    try:asyncio.run(asyncio.wait_for(check(f'http://127.0.0.1:{server.server_port}',records,a.output),timeout=240))
    finally:server.shutdown();server.server_close();thread.join(5)
