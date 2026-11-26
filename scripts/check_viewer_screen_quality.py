"""Small real-GLB/HDR regression: distant LOD, close-up original, export fidelity."""
import argparse
import asyncio
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
from threading import Thread
from cityg.viewer import viewer_static_dir


def make_fixture(source, base_fixture, output):
    config = json.loads((source/'viewer-config.json').read_text())
    aid = next(k for k in config['asset_lods'] if 'pine_sapling' in k)
    viewer = output/'viewer'
    shutil.copytree(viewer_static_dir(),viewer)
    scene = viewer/'scene'; scene.mkdir()
    city = json.loads((base_fixture/'scene/city.json').read_text())
    geometry = json.loads((base_fixture/'scene/geometry_manifest.json').read_text())
    geometry['primitives'] = []
    def primitive(pid, center, size, semantic='street_tree_canopy', asset=False):
        return {'id':pid,'owner_id':city['id'],'layer_id':'roads','primitive_type':'mesh' if asset else 'box',
                'center':dict(zip('xyz',center)),'size':dict(zip('xyz',size)),'rotation_z_deg':0,
                'semantic_class':semantic,'material_id':'city_ground',
                'metadata':{'resolved_asset':True,'asset_id':aid} if asset else {}}
    geometry['primitives'] = [primitive('tree_visible',[0,0,3],[4,4,6],asset=True),
                              primitive('tree_outside',[4000,0,3],[4,4,6],asset=True),
                              primitive('ground',[0,0,-.1],[100,100,.2],'city_ground'),
                              primitive('glass',[-6,0,2],[3,.2,4],'curtain_wall_glass')]
    (scene/'geometry_manifest.json').write_text(json.dumps(geometry))
    (scene/'city.json').write_text(json.dumps(city))
    asset_ids = [aid]+[v['asset_id'] for v in config['asset_lods'][aid]]
    (viewer/'assets').mkdir(exist_ok=True)
    for key in asset_ids:
        shutil.copyfile(source/config['asset_base']/config['asset_files'][key],viewer/'assets'/config['asset_files'][key])
    (viewer/'environment').mkdir()
    shutil.copyfile(source/config['environment_base']/config['environment_file'],viewer/'environment'/config['environment_file'])
    config.update(files=['city.json','geometry_manifest.json'],paper_views=None,
                  asset_files={k:config['asset_files'][k] for k in asset_ids},asset_lods={aid:config['asset_lods'][aid]},
                  material_textures={},texture_files={})
    (viewer/'viewer-config.json').write_text(json.dumps(config))
    return viewer


async def check(url, output):
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True,args=['--disable-dev-shm-usage','--use-angle=swiftshader','--enable-unsafe-swiftshader'])
        page = await browser.new_page(viewport={'width':1000,'height':800},accept_downloads=True)
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        await page.add_init_script("window.__CITYG_RENDER_PROFILE__='navigation'")
        await page.goto(url,wait_until='commit')
        await page.wait_for_function('window.citygObservation?.ready',timeout=120000)
        results={}
        for name,position in [('far',[0,-800,250]),('near',[0,-12,6])]:
            await page.evaluate('spec=>citygObservation.setView(spec)',{
                'mode':'overview','kind':'global','render_profile':'navigation','appearance':'presentation',
                'camera_position':position,'look_at':[0,0,3],'show_grid':False,'show_labels':False,'show_outlines':False})
            async with page.expect_download(timeout=180000) as download:
                result=await asyncio.wait_for(page.evaluate('()=>citygObservation.saveHighQualityImage({longEdge:640})'),180)
            await (await download.value).save_as(str(output/f'{name}.png'))
            s=result['assets']
            assert s['ready'] and not s['fallback'],s
            assert s['environment_state']=='ready' and all(s['shading'].values()),s
            assert s['expected']==1,s  # hidden second tree never loads/draws
            assert s['screen_lod']['reduced_assets' if name=='far' else 'original_assets']==1,s
            assert await page.evaluate("citygObservation.getViewState().render_profile==='navigation'")
            results[name]=result
        assert not errors,errors
        results['page_errors']=errors
        (output/'quality_check.json').write_text(json.dumps(results,indent=2))
        print(json.dumps({k:v['assets'] for k,v in results.items() if k!='page_errors'}),flush=True)
        await browser.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('base_fixture',type=Path)
    parser.add_argument('--output',required=True,type=Path)
    a=parser.parse_args()
    a.output.mkdir(exist_ok=False,parents=True)
    viewer=make_fixture(a.source,a.base_fixture,a.output)
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(SimpleHTTPRequestHandler,directory=str(viewer.resolve())))
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    try:asyncio.run(check(f'http://127.0.0.1:{server.server_port}',a.output))
    finally:server.shutdown();server.server_close();thread.join(5)


if __name__=='__main__': main()
