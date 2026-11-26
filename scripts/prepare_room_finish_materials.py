"""Download checksum-verified CC0 room PBRs; does not edit production materials."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from scripts.download_polyhaven_ground_materials import request_json, download, pick_channel, CHANNELS
from cityg.serialization import save_json


def main():
    root = Path('assets/incoming/interior_materials')
    records, tasks, sources = [], [], []
    for asset, scale in [('wood_floor', 2.0), ('beige_wall_001', 2.0), ('floor_tiles_02', 2.0)]:
        files = request_json(f'https://api.polyhaven.com/files/{asset}')
        info = request_json(f'https://api.polyhaven.com/info/{asset}')
        paths, provenance = {}, {}
        for channel in CHANNELS:
            item = pick_channel(files, channel, '2k')
            name = f'{asset}/{channel}{Path(item["url"]).suffix}'
            paths[channel+'_path'] = name
            provenance[channel] = item
            tasks.append((item['url'],root/name,item['md5']))
        records.append({'material_id': 'room_pbr_'+asset, 'display_color':[1,1,1],
            'roughness': .8, 'metallic':0, 'texture_scale_m':scale,
            'source':'Poly Haven:'+asset,'license_id':'CC0-1.0',**paths})
        sources.append({'asset_id':asset,'source_page':f'https://polyhaven.com/a/{asset}',
                        'license_url':'https://polyhaven.com/license','info':info,'files':provenance})
    with ThreadPoolExecutor(max_workers=4) as pool:
        for path,status in pool.map(lambda t:download(*t),tasks):print(status,path,flush=True)
    save_json({'schema_version':'cityg.materials.v1','materials':records},root/'material_library.json')
    save_json({'sources':sources},root/'provenance.json')


if __name__ == '__main__':main()
