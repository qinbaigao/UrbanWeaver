"""Capture a few real facade colourways without rendering the entire city."""
import argparse
import asyncio
import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from check_viewer_facade_stability import check, fixture


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('viewer',type=Path)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--tag',default='colorway')
    p.add_argument('--building-ids',nargs='+',required=True)
    p.add_argument('--resume',action='store_true',help='Reuse an existing test fixture after interruption')
    a=p.parse_args()
    if a.resume:
        target=a.output/'viewer'
        city=json.loads((target/'scene/city.json').read_text())
        buildings=[b for d in city['districts'] for parcel in d['parcels']
                   for b in parcel['buildings'] if b['id'] in a.building_ids]
        if len(buildings)!=len(set(a.building_ids)):
            raise ValueError('Existing fixture does not contain all requested buildings')
    else:
        a.output.mkdir(parents=True,exist_ok=False)
        target,buildings=fixture(a.viewer,a.output,building_ids=a.building_ids)
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(SimpleHTTPRequestHandler,directory=str(target.resolve())))
    worker=Thread(target=server.serve_forever,daemon=True);worker.start()
    try:
        asyncio.run(check(f'http://127.0.0.1:{server.server_port}',buildings,a.output,a.tag,scales=[2]))
    finally:
        server.shutdown();server.server_close();worker.join(5)
