"""Prepare locally downloaded CC-BY metro entrances; review before promotion.

Source GLBs are distributed by allenai/objaverse; original Sketchfab metadata
must accompany them. This script never logs in or downloads gated content.
"""
import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import subprocess

from cityg.asset_curation import _read_gltf, _write_glb, _canonicalize_document, _document_metrics
from cityg.assets import AssetRecord, AssetRegistry
from cityg.facade_runtime import _selected_bounds

ROOT = Path(__file__).resolve().parents[1]
SPECS = {
    'antake': {'uid':'cccece3f5a7248a891a300735841a41e', 'shard':'000-088', 'height':5.0, 'remove':[],
        'ground_y':-.91536, 'front_axis':'+Y', 'pit_source_xz':None,
        'palette':{'Krusha':[.09,.13,.15,1], 'NutrKrusha':[.12,.16,.17,1],
                   'Descent':[.24,.25,.23,1]}},
    # Source Floor is an untextured above-ground rear cover, not the lower
    # landing (Floor_Underground). CityG terrain supplies that cover instead.
    # Only expose the descending steps beneath the canopy, not the entire shaft.
    'alt': {'uid':'35c02eee93ea4a2f80af8acb84351d8c', 'shard':'000-067', 'height':8.0, 'remove':['Ground','Floor'],
        'ground_y':0, 'front_axis':'+X', 'pit_source_xz':[-2.18,-2.20,2.18,1.93],
        'palette':{}},
}


def download():
    directory=ROOT/'assets/incoming/metro_entrances'
    directory.mkdir(parents=True,exist_ok=True)
    for key,spec in SPECS.items():
        uid=spec['uid']
        files={f'{key}_metadata.json':f'https://api.sketchfab.com/v3/models/{uid}',
               f'{key}_metro.glb':f'https://huggingface.co/datasets/allenai/objaverse/resolve/main/glbs/{spec["shard"]}/{uid}.glb'}
        for filename,url in files.items():
            target=directory/filename
            if target.exists():continue
            partial=target.with_suffix(target.suffix+'.part')
            subprocess.run(['curl','--fail','--location','--silent','--show-error',
                '--proto','=https','--proto-redir','=https','--max-time','180',
                '--max-filesize','104857600','--output',str(partial),url],check=True)
            partial.replace(target)


def prepare(promote=False):
    source = ROOT/'assets/incoming/metro_entrances'
    output = ROOT/'assets/prepared/metro_entrances'
    output.mkdir(parents=True, exist_ok=True)
    registry = AssetRegistry()
    for key, spec in SPECS.items():
        info = json.loads((source/f'{key}_metadata.json').read_text())
        if info['uid'] != spec['uid'] or info['license']['slug'] != 'by':
            raise ValueError('Unexpected source or license')
        path = source/f'{key}_metro.glb'
        doc, buffers = _read_gltf(path)
        remove = {i for i,n in enumerate(doc['nodes']) if n.get('name') in spec['remove']}
        for node in doc['nodes']:
            if 'children' in node: node['children'] = [i for i in node['children'] if i not in remove]
        for material in doc.get('materials',[]):
            color=spec['palette'].get(material.get('name'))
            if color:material.setdefault('pbrMetallicRoughness',{})['baseColorFactor']=color
        roots = doc['scenes'][doc.get('scene',0)]['nodes']
        low, high = _selected_bounds(doc, roots)
        extent = [high[i]-low[i] for i in range(3)]
        bounds = {'min':low, 'max':high, 'extent':extent}
        aid = f'metro_{key}_entrance'
        normalized = _canonicalize_document(doc, bounds, asset_id=aid,
            source_up_axis='+Y', source_forward_axis='+Z')
        payload = _write_glb(normalized, buffers, path.parent)
        digest = hashlib.sha256(payload).hexdigest()
        filename = f'{aid}_{digest[:12]}.glb'
        (output/filename).write_bytes(payload)
        scale = spec['height']/extent[1]
        center=[(a+b)/2 for a,b in zip(low,high)]
        pit=spec['pit_source_xz']
        # Reviewed opening: source X/Z -> canonical Y/X, in unit-box coordinates.
        hole=None if pit is None else [(pit[1]-center[2])/extent[2],(pit[0]-center[0])/extent[0],
                                      (pit[3]-center[2])/extent[2],(pit[2]-center[0])/extent[0]]
        record = AssetRecord(aid, 'metro_entrance', tags=('metro','entrance','outdoor'),
            environment='outdoor', dimensions_m=tuple(extent[i]*scale for i in [2,0,1]),
            geometry_path=filename, source='Objaverse / Sketchfab', license_id='CC-BY-4.0',
            metadata={'outdoor_pack_status':'ready' if promote else 'candidate', 'external_content':True,
                'redistribution_policy':'download_required', 'preserve_physical_proportions':True,
                'source_url':info['viewerUrl'], 'author':info['user']['displayName'],
                'download_url':f'https://huggingface.co/datasets/allenai/objaverse/resolve/main/glbs/{spec["shard"]}/{spec["uid"]}.glb',
                'license_url':info['license']['url'], 'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                'output_sha256':digest, 'removed_nodes':spec['remove'], 'source_bounds':bounds,
                'palette_changes':spec['palette'],
                'ground_anchor_fraction':(spec['ground_y']-low[1])/extent[1],
                'metro_placement':{'reviewed':promote, 'front_axis':spec['front_axis'],
                    'opening_unit_bounds':hole, 'exterior_only':True, 'underground_navigation':False},
                'mesh_validation':_document_metrics(doc,bounds),
                'style':'textured_authored' if doc.get('textures') else 'authored_untextured',
                'orientation':{'canonical_up_axis':'+Z','canonical_forward_axis':spec['front_axis'],
                    'visually_checked':promote,'orientation_confidence':'reviewed' if promote else 'unreviewed'}})
        registry.register(record)
        print(aid, record.dimensions_m, digest[:12], flush=True)
    registry.save(output/'asset_registry.json')
    if promote:
        production=AssetRegistry(ROOT/'assets/asset_registry.json')
        for record in registry.list_all():
            production.register(replace(record,geometry_path=str((output/record.geometry_path).relative_to(ROOT/'assets'))),overwrite=True)
        production.save()


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download',action='store_true',help='Acquire the two public, licensed GLBs and source metadata')
    parser.add_argument('--promote-reviewed',action='store_true')
    args=parser.parse_args()
    if args.download:download()
    prepare(args.promote_reviewed)
