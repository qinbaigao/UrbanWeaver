"""Real facade + parcel regression across camera distances (no proxy buildings).

Test-only resource symlinks avoid duplicating the asset pack. This fixture is
not a portable deliverable. Original geometry/assets are never modified.
"""
import argparse
import asyncio
import base64
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import re
from pathlib import Path
import shutil
from threading import Thread
from cityg.viewer import viewer_static_dir


def fixture(source, output, include_planting=False, include_sites=False, building_ids=None, include_edges=False,
            include_parcel_context=False, include_water=False):
    viewer=output/'viewer';shutil.copytree(viewer_static_dir(),viewer,dirs_exist_ok=True)
    (viewer/'scene').mkdir(exist_ok=True)
    config=json.loads((source/'viewer-config.json').read_text())
    city=json.loads((source/'scene/city.json').read_text())
    core_bounds=city.get('metadata',{}).get('edge_landscape_extension',{}).get('original_bounds',city['bounds'])
    geom=json.loads((source/'scene/geometry_manifest.json').read_text())
    wanted=set(building_ids or ['building_000','building_004','building_051'])
    owners=set(wanted);parcel_ids=set();buildings=[];parcel_bounds=[]
    for d in city['districts']:
        d['parcels']=[p for p in d['parcels'] if any(b['id'] in wanted for b in p['buildings'])]
        for p in d['parcels']:
            parcel_ids.add(p['id'])
            parcel_bounds.append(p['bounds'])
            for b in p['buildings']:
                buildings.append(b);owners.update(f['id'] for f in b['floors'])
    primitives=list(geom.get('primitives',[]))
    for chunk in geom.get('streaming',{}).get('chunks',[]):
        primitives.extend(json.loads((source/'scene'/chunk['file']).read_text())['primitives'])
    primitives=[p for p in primitives if
        (include_water and p['semantic_class'].startswith(('river_', 'riparian_', 'bridge_')))
        or
        (p['owner_id'] in owners and (not p.get('metadata',{}).get('resolved_asset')
         or p['metadata'].get('asset_category')=='facade_module'
         or p['metadata'].get('roof_system')))
        or (p['owner_id'] in parcel_ids and (include_parcel_context or p['semantic_class'] in ('parcel_ground','parcel_surface_patch','parcel_edge')
            or (include_planting and p.get('metadata',{}).get('planting_system'))
            or (include_sites and (p.get('metadata',{}).get('site_system') or p.get('metadata',{}).get('metro_system')))))
        or (include_edges and (p.get('metadata',{}).get('edge_landscape_system')
            or p.get('metadata',{}).get('edge_greenery')
            or p['semantic_class']=='city_ground'
            or (p['semantic_class'] in {'road_surface','sidewalk','sidewalk_frontage_strip','sidewalk_furnishing_strip','curb'}
                and (p['center']['x']<core_bounds['min_x']+30 or p['center']['x']>core_bounds['max_x']-30))))
        or (include_sites and p['semantic_class']=='frontage_connector'
            and p.get('metadata',{}).get('building_id') in wanted)
        or (include_parcel_context and p['semantic_class'] in {'road_surface','sidewalk','curb','city_ground'}
            and any(p['center']['x']+max(p['size']['x'],p['size']['y'])/2>b['min_x']-12
                and p['center']['x']-max(p['size']['x'],p['size']['y'])/2<b['max_x']+12
                and p['center']['y']+max(p['size']['x'],p['size']['y'])/2>b['min_y']-12
                and p['center']['y']-max(p['size']['x'],p['size']['y'])/2<b['max_y']+12 for b in parcel_bounds))]
    geom.pop('streaming',None);geom['primitives']=primitives
    ids={p['metadata']['asset_id'] for p in primitives if p.get('metadata',{}).get('resolved_asset')}
    for aid in list(ids):ids.update(v['asset_id'] for v in config.get('asset_lods',{}).get(aid,[]))
    config.update(paper_views=None,files=['city.json','geometry_manifest.json'],
        asset_files={a:f for a,f in config['asset_files'].items() if a in ids},
        asset_lods={a:v for a,v in config.get('asset_lods',{}).items() if a in ids})
    used={p['material_id'] for p in primitives}|{'parcel_lawn','courtyard_paving'}
    config['material_textures']={k:v for k,v in config['material_textures'].items() if k in used}
    resources={'assets':set(config['asset_files'].values()),
        'textures':{f for channels in config['material_textures'].values() for f in channels.values()},
        'environment':{v['file'] for v in config.get('sky_presets',{}).values()}|{config.get('environment_file')}}
    for folder,files in resources.items():
        (viewer/folder).mkdir(exist_ok=True)
        for f in files:
            if f and not (viewer/folder/f).exists():(viewer/folder/f).symlink_to((source/folder/f).resolve())
    for f,d in [('viewer-config.json',config),('scene/city.json',city),('scene/geometry_manifest.json',geom)]:
        (viewer/f).write_text(json.dumps(d))
    return viewer,buildings


async def check(url,buildings,output,tag,no_shadows=False,only=None,scales=None,north=False):
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True,args=['--disable-dev-shm-usage','--use-angle=swiftshader','--enable-unsafe-swiftshader'])
        page=await browser.new_page(viewport={'width':1400,'height':1000},accept_downloads=True)
        if no_shadows:
            async def without_shadows(route):
                response=await route.fetch();body=await response.text()
                body,count=re.subn(r'(\.shadowMap\.enabled=)[^,;]+',r'\1false',body)
                assert count>=1,'Expected renderer shadow switch in test bundle'
                await route.fulfill(response=response,body=body)
            await page.route('**/assets/index-*.js',without_shadows)
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('console',lambda m:errors.append(m.text) if m.type=='error' and 'Failed to load resource' not in m.text else None)
        await page.add_init_script("window.__CITYG_RENDER_PROFILE__='navigation'")
        await page.goto(url,wait_until='commit');await page.wait_for_function('window.citygObservation?.ready',timeout=120000)
        results={};first_views={};roundtrips={}
        for b in buildings:
            if only and b['id']!=only:continue
            f=b['footprint'];x=(f['min_x']+f['max_x'])/2;y=(f['min_y']+f['max_y'])/2
            span=max(f['max_x']-f['min_x'],f['max_y']-f['min_y'])
            for scale in scales or [8,4,2,4]:
                key=f'{b["id"]}_{len(results):02d}_{scale}'
                d=span*scale
                await page.evaluate('v=>citygObservation.setView(v)',dict(kind='building_exterior',mode='overview',
                    appearance='presentation',render_profile='prototype_capture',near_clip_m=1.0,
                    camera_position=[x+d*.72,y+d*.8*(1 if north else -1),20+d*.6],look_at=[x,y,20],
                    show_grid=False,show_labels=False,show_outlines=False,sky_preset='clear'))
                # Simulate the small near plane retained by interactive city
                # orbit/zoom, which the scripted-camera path used to conceal.
                await page.evaluate('()=>citygObservation.setView({render_profile:"presentation"})')
                status=await page.evaluate('()=>citygObservation.waitForAssets({timeout_ms:120000})')
                assert status['ready'] and not status.get('fallback'),status
                # Exercise the interactive camera path, not only HQ export.
                image_path=output/f'{tag}_{key}.png'
                # Read the rendered canvas directly after the asset barrier;
                # avoid Playwright's scroll/stability wait on a continuously
                # animated WebGL canvas (particularly slow on CPU renderers).
                data=await page.evaluate('citygObservation.captureFrame()')
                image_path.write_bytes(base64.b64decode(data.split(',',1)[1]))
                pose=(b['id'],scale)
                if pose in first_views:
                    from PIL import Image, ImageChops, ImageStat
                    a=Image.open(first_views[pose]).convert('RGB');current=Image.open(image_path).convert('RGB')
                    crop=(0,80,a.width,a.height-50)  # exclude buttons/status text
                    difference=ImageChops.difference(a.crop(crop),current.crop(crop))
                    error=max(ImageStat.Stat(difference).mean)
                    roundtrips[key]={'max_channel_mean_error_255':error,'changed_bbox':difference.getbbox()}
                    assert error<=0.05,('same camera changed after zoom round trip',roundtrips[key])
                else:first_views[pose]=image_path
                results[key]={'status':status,'view':await page.evaluate('citygObservation.getViewState()')}
                print(tag,key,flush=True)
        assert not errors,errors
        (output/f'{tag}_report.json').write_text(json.dumps({'results':results,'errors':errors,'roundtrips':roundtrips},indent=2))
        await browser.close()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--tag',default='check')
    p.add_argument('--no-shadows',action='store_true');p.add_argument('--only')
    p.add_argument('--scales',nargs='+',type=float)
    p.add_argument('--include-planting',action='store_true',help='Include asset-backed parcel mixed borders')
    p.add_argument('--north',action='store_true',help='Inspect the north side instead of the south side')
    p.add_argument('--include-sites',action='store_true',help='Include new parcel amenity nodes and entrance paths')
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    viewer,buildings=fixture(a.source,a.output,a.include_planting,a.include_sites,[a.only] if a.only else None)
    s=ThreadingHTTPServer(('127.0.0.1',0),partial(SimpleHTTPRequestHandler,directory=str(viewer.resolve())))
    t=Thread(target=s.serve_forever,daemon=True);t.start()
    try:asyncio.run(check(f'http://127.0.0.1:{s.server_port}',buildings,a.output,a.tag,a.no_shadows,a.only,a.scales,a.north))
    finally:s.shutdown();s.server_close();t.join(5)


if __name__=='__main__':main()
