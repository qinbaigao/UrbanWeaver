"""Render a small A/B ground-material fixture derived from a real portable city.

Keeps actual clipped parcel/road geometry; simple building proxies intentionally
isolate the surface test from facade/GLB cost. Does not modify the source city.
"""
import argparse
import asyncio
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
from threading import Thread

from cityg.viewer import viewer_static_dir


def fixture(source, output):
    target = output / 'viewer'
    shutil.copytree(viewer_static_dir(), target)
    (target / 'scene').mkdir()
    config = json.loads((source / 'viewer-config.json').read_text())
    city = json.loads((source / 'scene/city.json').read_text())
    manifest = json.loads((source / 'scene/geometry_manifest.json').read_text())
    keep = {'parcel_ground', 'parcel_surface_patch', 'parcel_edge', 'road_surface',
            'sidewalk', 'river_water', 'city_ground', 'building_access_path'}
    primitives = list(manifest.get('primitives', []))
    for chunk in manifest.get('streaming', {}).get('chunks', []):
        primitives.extend(json.loads((source / 'scene' / chunk['file']).read_text())['primitives'])
    primitives = [p for p in primitives if p['semantic_class'] in keep or p.get('metadata', {}).get('ground_plane')]
    parcels = [p for d in city['districts'] for p in d['parcels']]
    for parcel in parcels:
        for building in parcel['buildings']:
            b = building['footprint']
            primitives.append(dict(id=building['id']+'_test_proxy',owner_id=building['id'],layer_id='roads',
                primitive_type='box',semantic_class='exterior_wall',material_id='ground_test_proxy',
                center=dict(x=(b['min_x']+b['max_x'])/2,y=(b['min_y']+b['max_y'])/2,z=8),
                size=dict(x=b['max_x']-b['min_x'],y=b['max_y']-b['min_y'],z=16),
                rotation_z_deg=building.get('metadata',{}).get('orientation_deg',0),metadata={}))
    manifest.pop('streaming', None)
    manifest['primitives'] = primitives
    manifest['materials'].append(dict(id='ground_test_proxy',display_color=[0.65,0.65,0.60],roughness=0.85))
    used = {p['material_id'] for p in primitives} | {'parcel_lawn', 'courtyard_paving'}
    textures = {k:v for k,v in config.get('material_textures',{}).items() if k in used}
    (target/'textures').mkdir()
    for filename in {f for channels in textures.values() for f in channels.values()}:
        shutil.copyfile(source/config['texture_base']/filename,target/'textures'/filename)
    # Use the same clear-sky illumination, but no full asset pack is needed.
    preset = config.get('sky_presets',{}).get('clear')
    if preset:
        (target/'environment').mkdir()
        shutil.copyfile(source/config['environment_base']/preset['file'],target/'environment'/preset['file'])
    config.update(files=['city.json','geometry_manifest.json'],paper_views=None,
        asset_files={},asset_lods={},material_textures=textures,texture_files={},
        sky_presets={'clear':preset} if preset else {},environment_file=preset['file'] if preset else None)
    for filename,value in [('scene/city.json',city),('scene/geometry_manifest.json',manifest),('viewer-config.json',config)]:
        (target/filename).write_text(json.dumps(value))
    return target,parcels,len(primitives)


async def check(url, target, parcels, output):
    from playwright.async_api import async_playwright
    config_path=target/'viewer-config.json'
    config=json.loads(config_path.read_text())
    errors=[];results={}
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True,args=['--disable-dev-shm-usage','--use-angle=swiftshader','--enable-unsafe-swiftshader'])
        page=await browser.new_page(viewport={'width':1200,'height':900},accept_downloads=True)
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('console',lambda m:errors.append(m.text) if m.type=='error' and 'Failed to load resource' not in m.text else None)
        await page.add_init_script("window.__CITYG_RENDER_PROFILE__='navigation'")
        xmin=min(q['bounds']['min_x'] for q in parcels);xmax=max(q['bounds']['max_x'] for q in parcels)
        ymin=min(q['bounds']['min_y'] for q in parcels);ymax=max(q['bounds']['max_y'] for q in parcels)
        cx=(xmin+xmax)/2;cy=(ymin+ymax)/2;extent=max(xmax-xmin,ymax-ymin)
        selected=[parcels[0],next((q for q in parcels if q['buildings'][0]['function'] in ('office','commercial','retail','mixed_use')),parcels[-1])]
        views={'aerial':([cx,cy-extent*.4,extent*1.5],[cx,cy,0])}
        for i,q in enumerate(selected):
            b=q['bounds'];x=(b['min_x']+b['max_x'])/2;y=(b['min_y']+b['max_y'])/2
            span=max(b['max_x']-b['min_x'],b['max_y']-b['min_y'])
            views[f'parcel_{i}']=([x,y-span*.5,span*1.6],[x,y,0])
        for enabled in [False,True]:
            config['ground_surface']={'enabled':enabled}
            config_path.write_text(json.dumps(config))
            await page.goto(url,wait_until='commit')
            await page.wait_for_function('window.citygObservation?.ready',timeout=120000)
            for name,(camera,target_point) in views.items():
                key=f'{name}_{"after" if enabled else "before"}'
                await page.evaluate('v=>citygObservation.setView(v)',dict(mode='overview',kind='global',
                    render_profile='navigation',appearance='presentation',camera_position=camera,look_at=target_point,
                    show_grid=False,show_labels=False,show_outlines=False))
                async with page.expect_download(timeout=180000) as pending:
                    result=await asyncio.wait_for(page.evaluate('()=>citygObservation.saveHighQualityImage({longEdge:1200})'),180)
                await (await pending.value).save_as(str(output/f'{key}.png'))
                assert result['assets']['ready'],result
                results[key]=result
                print(key,flush=True)
        assert not errors,errors
        results['page_errors']=errors
        (output/'ground_check.json').write_text(json.dumps(results,indent=2))
        await browser.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    target,parcels,count=fixture(args.source,args.output)
    print(f'Ground-only regression: {len(parcels)} parcels, {count} primitives',flush=True)
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(SimpleHTTPRequestHandler,directory=str(target.resolve())))
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    try:asyncio.run(check(f'http://127.0.0.1:{server.server_port}',target,parcels,args.output))
    finally:server.shutdown();server.server_close();thread.join(5)


if __name__=='__main__':main()
