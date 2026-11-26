"""HQ apartment, townhouse and park checks without opening a desktop browser."""
import argparse
import asyncio
from functools import partial
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
from threading import Thread

from check_viewer_facade_stability import fixture
from check_viewer_residential_groups import run as groups, ReviewHandler
from check_viewer_roofs import capture


def run(viewer, group_report, output, only=None):
    if only != 'park':
        groups(viewer,group_report,output)
    if only == 'groups':
        return
    target=output/'park';target.mkdir(parents=True,exist_ok=True)
    preview,_=fixture(viewer,target,building_ids=['no_building_selected'],include_edges=True)
    city=json.loads((viewer/'scene/city.json').read_text())
    b=city['metadata']['edge_landscape_extension']['park_bounds']
    x=(b['min_x']+b['max_x'])/2;y=(b['min_y']+b['max_y'])/2
    view=dict(view_id='dense_park',kind='global',mode='overview',render_profile='paper_capture',
        appearance='presentation',camera_position=[x-190,y-250,240],look_at=[x,y,2],
        up=[0,0,1],fov_deg=50,show_grid=False,show_labels=False,show_outlines=False,
        auto_cutaway=False,sky_preset='clear',reset_visibility=True)
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(ReviewHandler,directory=str(preview)))
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    try:asyncio.run(capture(f'http://127.0.0.1:{server.server_port}',target,[view]))
    finally:server.shutdown();server.server_close();thread.join(5)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('viewer',type=Path);p.add_argument('--group-report',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--only',choices=['groups','park'])
    a=p.parse_args();run(a.viewer.resolve(),json.loads(a.group_report.read_text()),a.output.resolve(),a.only)
