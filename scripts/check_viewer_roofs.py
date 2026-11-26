"""Inspect actual rooftop geometry with shaded screenshots, without browser popups.

--preview-new adds the pending roof layer to a diagnostic fixture only. Compact
Viewer data is never promoted to a canonical city. Resources are symlinked.
"""
import argparse
import asyncio
from functools import partial
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
from threading import Thread

from check_viewer_facade_stability import fixture
from check_viewer_courtyards import QuietHandler
from cityg.assets import AssetRegistry, MaterialLibrary
from cityg.geometry import GeometryCompiler
from cityg.geometry.incremental import scene_from_manifest
from cityg.geometry.roofscape import compile_roofscape
from cityg.geometry.roof_surfaces import roof_surfaces
from cityg.schemas import City, RoadNetwork
from cityg.serialization import _bounds, _district, to_primitive, save_json
from cityg.viewer import _collect_material_textures


def prepare(source, output, selected, preview, preview_textures=False):
    viewer, buildings = fixture(source, output, building_ids=selected)
    config = json.loads((viewer/'viewer-config.json').read_text())
    scene = scene_from_manifest(json.loads((viewer/'scene/geometry_manifest.json').read_text()))
    if preview or preview_textures:
        data = json.loads((viewer/'scene/city.json').read_text())
        city = City(data['id'], data['name'], _bounds(data['bounds']), RoadNetwork(),
                    [_district(d) for d in data['districts']], metadata={'roofscape': {'enabled': True}})
        project = Path(__file__).resolve().parents[1]
        registry = AssetRegistry(project/'assets/asset_registry.json')
        compiler = GeometryCompiler(registry, MaterialLibrary(project/'assets/material_library.json'), include_interiors=False)
        if preview_textures:
            from cityg.geometry.roof_textures import apply_roof_textures
            city.metadata['roof_textures']={'enabled':True}
            report=apply_roof_textures(city,scene)
        else: report = compile_roofscape(compiler, city, scene)
        save_json(report, output/'roofscape_preview.json')
        payload = json.dumps(to_primitive(scene)).encode()
        base = Path(config['original_source'])
        textures, mapping, _ = _collect_material_textures(payload, base)
        for name, content in textures.items():
            target = viewer/'textures'/name
            if target.exists():
                if target.read_bytes() != content:
                    raise ValueError('Fixture would overwrite shared texture: '+name)
            else: target.write_bytes(content)
        config['material_textures'].update(mapping)
        for p in scene.primitives:
            if not p.metadata.get('resolved_asset'): continue
            aid = p.metadata['asset_id']
            if aid in config['asset_files']: continue
            record = registry.get(aid)
            path = registry.resolve_path(record.geometry_path)
            name = aid+path.suffix
            (viewer/'assets'/name).symlink_to(path.resolve())
            config['asset_files'][aid] = name
        (viewer/'scene/geometry_manifest.json').write_bytes(payload)
        save_json(config, viewer/'viewer-config.json')
    views = []
    for b in buildings:
        owners = {b['id']} | {f['id'] for f in b['floors']}
        surfaces = roof_surfaces([p for p in scene.primitives if p.owner_id in owners and not p.metadata.get('roof_system')])
        if not surfaces: continue
        roof = max(surfaces, key=lambda r:r['shape'].area)
        x0,y0,x1,y1 = roof['shape'].bounds
        x,y,z = (x0+x1)/2,(y0+y1)/2,roof['z']
        span = max(x1-x0,y1-y0,20)
        views.append(dict(view_id=b['id'], kind='building_exterior', mode='overview',
            render_profile='paper_capture', appearance='presentation',
            camera_position=[x+span*.75,y-span*.9,z+span*.95], look_at=[x,y,z],
            up=[0,0,1], fov_deg=48, show_grid=False, show_labels=False, show_outlines=False,
            auto_cutaway=False, sky_preset='clear', reset_visibility=True))
    save_json(views, output/'roof_views.json')
    return viewer,views


async def capture(url, output, views):
    from playwright.async_api import async_playwright
    results=[]; errors=[]
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True,args=['--disable-dev-shm-usage',
            '--use-angle=swiftshader','--enable-unsafe-swiftshader'])
        page=await browser.new_page(viewport={'width':1400,'height':1000},accept_downloads=True)
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('console',lambda m:errors.append(m.text) if m.type=='error' and 'Failed to load resource' not in m.text else None)
        await page.add_init_script("window.__CITYG_RENDER_PROFILE__='navigation'")
        await page.goto(url,wait_until='commit')
        await page.wait_for_function('window.citygObservation?.ready',timeout=120000)
        for view in views:
            await page.evaluate('v=>citygObservation.setView(v)',view)
            status=await page.evaluate('()=>citygObservation.waitForAssets({timeout_ms:180000})')
            assert status['ready'] and not status.get('failed') and not status.get('fallback'),status
            async with page.expect_download(timeout=240000) as pending:
                snapshot=await page.evaluate('()=>citygObservation.saveHighQualityImage({longEdge:1200,download:true,timeoutMs:180000})')
            await (await pending.value).save_as(output/(view['view_id']+'.png'))
            results.append({'building_id':view['view_id'],'preload':status,'snapshot':snapshot})
            print(view['view_id']+' captured',flush=True)
        await browser.close()
    assert not errors,errors
    save_json({'views':results,'errors':errors},output/'render_check.json')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('viewer',type=Path);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--building',action='append');p.add_argument('--preview-new',action='store_true')
    p.add_argument('--preview-textures',action='store_true',help='Preview material-only variety on existing roofs')
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    viewer,views=prepare(a.viewer.resolve(),a.output.resolve(),a.building or ['building_000','building_002','building_032'],a.preview_new,a.preview_textures)
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=str(viewer)))
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    try:asyncio.run(capture(f'http://127.0.0.1:{server.server_port}',a.output,views))
    finally:server.shutdown();server.server_close();thread.join(5)
