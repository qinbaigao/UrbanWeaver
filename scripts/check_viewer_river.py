"""Render the real curved river and adjacent buildings without opening a browser.

Only a small diagnostic fixture is written; source scene and assets are untouched.
The shader also runs in the HQ PNG path, with console/GLSL errors treated as failures.
"""
import argparse
import asyncio
from functools import partial
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
from threading import Thread

from check_viewer_courtyards import QuietHandler
from check_viewer_facade_stability import fixture
from check_viewer_roofs import capture


class RiverHandler(QuietHandler):
    def copyfile(self, source, outputfile):
        try:super().copyfile(source, outputfile)
        except (BrokenPipeError, ConnectionResetError):pass  # browser closed after capture


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    source=args.source.resolve();output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    city=json.loads((source/'scene/city.json').read_text())
    river=city['rivers'][0];point=river['centerline'][len(river['centerline'])//2]
    x,y,z=point['x'],point['y'],river.get('water_elevation_m',-3.5)
    buildings=[b for d in city['districts'] for p in d['parcels'] for b in p['buildings']]
    def distance(b):
        f=b['footprint']
        return ((f['min_x']+f['max_x'])/2-x)**2+((f['min_y']+f['max_y'])/2-y)**2
    chosen=[b['id'] for b in sorted(buildings,key=distance)[:2]]
    viewer,_=fixture(source,output,building_ids=chosen,include_parcel_context=True,include_water=True)
    common=dict(kind='global',mode='overview',appearance='presentation',render_profile='paper_capture',
        up=[0,0,1],fov_deg=48,show_grid=False,show_labels=False,show_outlines=False,
        auto_cutaway=False,sky_preset='clear',reset_visibility=True)
    views=[dict(common,view_id='river_aerial',camera_position=[x+180,y-150,z+190],look_at=[x,y,z]),
           dict(common,view_id='river_aerial_reverse',camera_position=[x-180,y+150,z+240],look_at=[x,y,z]),
           dict(common,view_id='river_near',camera_position=[x+32,y-45,z+23],look_at=[x,y+12,z])]
    (output/'river_views.json').write_text(json.dumps(views,indent=2))
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(RiverHandler,directory=str(viewer)))
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    try:asyncio.run(capture(f'http://127.0.0.1:{server.server_port}',output,views))
    finally:server.shutdown();server.server_close();thread.join(5)


if __name__=='__main__':main()
