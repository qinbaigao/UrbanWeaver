"""Inspect actual added roadside trees, not arbitrary unchanged street views."""
import argparse
import asyncio
from collections import defaultdict
from functools import partial
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
from threading import Thread

from check_viewer_facade_stability import fixture
from check_viewer_residential_groups import ReviewHandler
from check_viewer_roofs import capture
from cityg.geometry.street_tree_infill import KEY, VERSION
from cityg.paths import PlanarPath2D
from cityg.schemas import Point2D
from cityg.serialization import save_json


def run(source, output):
    city=json.loads((source/'scene/city.json').read_text())
    parcels={p['id']:p for d in city['districts'] for p in d['parcels']}
    roads={r['id']:r for r in city['road_network']['segments']}
    header=json.loads((source/'scene/geometry_manifest.json').read_text())
    by_parcel=defaultdict(list)

    def collect(primitives):
        for p in primitives:
            if p.get('metadata',{}).get(KEY)==VERSION:
                by_parcel[p['owner_id']].append(p)
    collect(header.get('primitives',[]))
    for chunk in header.get('streaming',{}).get('chunks',[]):
        collect(json.loads((source/'scene'/chunk['file']).read_text())['primitives'])
    ranked=sorted(by_parcel,key=lambda pid:(-len(by_parcel[pid]),pid))
    if not ranked:raise ValueError('No new roadside trees in this Viewer')
    selected=ranked[:2]
    for pid in selected:
        parcel=parcels[pid];trees=by_parcel[pid]
        by_road=defaultdict(list)
        for p in trees:by_road[p['metadata']['road_id']].append(p)
        rid=max(by_road,key=lambda rid:len(by_road[rid]))
        group=sorted(by_road[rid],key=lambda p:p['metadata']['road_station_m'])
        p=group[len(group)//2];road=roads[rid]
        path=PlanarPath2D(Point2D(v['x'],v['y']) for v in road['centerline'])
        station=p['metadata']['road_station_m']
        camera=path.point(max(5,station-20))
        target=output/pid;target.mkdir(parents=True,exist_ok=True)
        preview,_=fixture(source,target,building_ids=[b['id'] for b in parcel['buildings']],
            include_parcel_context=True,include_planting=True,include_sites=True)
        view=dict(view_id='roadside_'+pid,kind='global',mode='overview',
            render_profile='paper_capture',appearance='presentation',
            camera_position=[camera.x,camera.y,4.2],look_at=[p['center']['x'],p['center']['y'],4.5],
            up=[0,0,1],fov_deg=62,show_grid=False,show_labels=False,show_outlines=False,
            auto_cutaway=False,sky_preset='clear',reset_visibility=True)
        save_json({'view':view,'new_trees':trees},target/'review_targets.json')
        server=ThreadingHTTPServer(('127.0.0.1',0),partial(ReviewHandler,directory=str(preview)))
        thread=Thread(target=server.serve_forever,daemon=True);thread.start()
        try:asyncio.run(capture(f'http://127.0.0.1:{server.server_port}',target,[view]))
        finally:server.shutdown();server.server_close();thread.join(5)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('viewer',type=Path);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run(a.viewer.resolve(),a.output.resolve())
