"""Review two real residential groups; no asset duplication or desktop popup."""
import argparse
import asyncio
from functools import partial
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
from threading import Thread

from check_viewer_facade_stability import fixture
from check_viewer_courtyards import QuietHandler
from check_viewer_roofs import capture
from cityg.serialization import save_json


class ReviewHandler(QuietHandler):
    def copyfile(self, source, outputfile):
        try:
            super().copyfile(source, outputfile)
        except (BrokenPipeError, ConnectionResetError):
            # Chromium cancels background prefetches when the checked page closes.
            pass


def group_view(parcel, kind):
    f = parcel['bounds']; x=(f['min_x']+f['max_x'])/2; y=(f['min_y']+f['max_y'])/2
    span = max(f['max_x']-f['min_x'],f['max_y']-f['min_y'])
    return dict(view_id='residential_group_'+parcel['id'],kind='global',mode='overview',
        render_profile='paper_capture',appearance='presentation',
        camera_position=[x+span*.55,y-span*.92,span*.86],look_at=[x,y,8 if kind=='apartments' else 3],
        up=[0,0,1],fov_deg=48,show_grid=False,show_labels=False,show_outlines=False,
        auto_cutaway=False,sky_preset='clear',reset_visibility=True)


def save_views(source, report):
    city=json.loads((source/'scene/city.json').read_text())
    parcels={p['id']:p for d in city['districts'] for p in d['parcels']}
    cfg=json.loads((source/'viewer-config.json').read_text())
    path=(source/cfg.get('paper_views','figure1_views.json')).resolve()
    if not path.is_relative_to(source.resolve()): raise ValueError('Views must be inside the portable Viewer')
    data=json.loads(path.read_text()) if path.exists() else {'selected_views':[]}
    data['selected_views']=[v for v in data['selected_views'] if not v['view_id'].startswith('residential_group_')]
    for r in report['parcels']:
        view=group_view(parcels[r['parcel_id']],r['kind']);view['render_profile']='presentation'
        data['selected_views'].append(view)
    save_json(data,path)


def street_view(city, preview, parcel):
    """Inspect an actual new street bed from the nearest real road centreline."""
    from cityg.polygons import geos
    s=geos()
    data=json.loads((preview/'scene/geometry_manifest.json').read_text())
    beds=[p for p in data['primitives'] if p['owner_id']==parcel['id']
          and p['semantic_class']=='parcel_planting_bed'
          and p.get('metadata',{}).get('planting_context')=='street_border']
    if not beds:return None
    bed=max(beds,key=lambda p:p['size']['x']*p['size']['y'])
    point=s.Point(bed['center']['x'],bed['center']['y'])
    roads=[s.LineString([(p['x'],p['y']) for p in r['centerline']])
           for r in city['road_network']['segments']]
    if not roads:return None
    road=min(roads,key=lambda r:r.distance(point))
    along=road.project(point);camera=road.interpolate(max(0,min(road.length,along-5)))
    return dict(view_id='street_border_'+parcel['id'],kind='global',mode='overview',
        render_profile='paper_capture',appearance='presentation',
        camera_position=[camera.x,camera.y,2.8],look_at=[point.x,point.y,1.8],
        up=[0,0,1],fov_deg=62,show_grid=False,show_labels=False,show_outlines=False,
        auto_cutaway=False,sky_preset='clear',reset_visibility=True)


def preview_greenbelts(viewer,output):
    """Diagnostic only: replace planting in a clipped fixture, never canonical data."""
    from cityg.assets import AssetRegistry
    from cityg.geometry import GeometryCompiler
    from cityg.geometry.incremental import scene_from_manifest
    from cityg.geometry.urban_greenbelts import compile_urban_greenbelts, KEY, VERSION
    from cityg.serialization import city_from_dict
    data=json.loads((viewer/'scene/city.json').read_text())
    # Portable data omits CCWP. This empty program belongs only to a clipped
    # render fixture and must never be saved as an authoritative city package.
    data.setdefault('world_program',{})
    city=city_from_dict(data)
    city.metadata[KEY]={'enabled':True,'version':VERSION,'density':1.,'seed':20261017}
    scene=scene_from_manifest(json.loads((viewer/'scene/geometry_manifest.json').read_text()))
    registry=AssetRegistry(Path(__file__).resolve().parents[1]/'assets/asset_registry.json')
    report=compile_urban_greenbelts(GeometryCompiler(registry,include_interiors=False),city,scene)
    config=json.loads((viewer/'viewer-config.json').read_text())
    for p in scene.primitives:
        aid=p.metadata.get('asset_id')
        if not p.metadata.get('resolved_asset') or aid in config['asset_files']:continue
        record=registry.get(aid);source=registry.resolve_path(record.geometry_path).resolve()
        filename=aid+source.suffix;target=viewer/'assets'/filename
        if not target.exists():target.symlink_to(source)
        config['asset_files'][aid]=filename
    save_json(scene,viewer/'scene/geometry_manifest.json')
    save_json(config,viewer/'viewer-config.json')
    save_json(report,output/'preview_greenbelts.json')


def run(source,report,output,street=False,preview=False,kinds=None):
    city=json.loads((source/'scene/city.json').read_text())
    parcels={p['id']:p for d in city['districts'] for p in d['parcels']}
    # Include every unit explicitly: roofs are owned by buildings, windows by floors.
    for kind in (kinds or ('apartments','townhouses')):
        r=next(r for r in report['parcels'] if r['kind']==kind)
        target=output/kind;target.mkdir(parents=True,exist_ok=True)
        viewer,_=fixture(source,target,building_ids=r['building_ids'],include_parcel_context=True,
                         include_planting=True,include_sites=True)
        if preview:preview_greenbelts(viewer,target)
        server=ThreadingHTTPServer(('127.0.0.1',0),partial(ReviewHandler,directory=str(viewer)))
        thread=Thread(target=server.serve_forever,daemon=True);thread.start()
        views=[group_view(parcels[r['parcel_id']],kind)]
        if street:
            extra=street_view(city,viewer,parcels[r['parcel_id']])
            if extra:views.append(extra)
        try:
            asyncio.run(capture(f'http://127.0.0.1:{server.server_port}',target,
                                views))
        finally: server.shutdown();server.server_close();thread.join(5)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('viewer',type=Path);p.add_argument('--report',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--save-views',action='store_true')
    p.add_argument('--street',action='store_true',help='Also inspect a planted road border at pedestrian height')
    p.add_argument('--preview-greenbelts',action='store_true',help='Preview pending planting code in a fixture only')
    p.add_argument('--kind',choices=['apartments','townhouses'],action='append')
    a=p.parse_args();report=json.loads(a.report.read_text())
    if a.save_views:save_views(a.viewer.resolve(),report)
    run(a.viewer.resolve(),report,a.output.resolve(),a.street,a.preview_greenbelts,a.kind)
