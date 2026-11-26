"""Acquire public CC0 construction GLBs; stage canonical assets for visual review."""
import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import subprocess

from cityg.asset_curation import _read_gltf, _write_glb, _canonicalize_document, _document_metrics
from cityg.assets import AssetRecord, AssetRegistry
from cityg.facade_runtime import _selected_bounds

ROOT=Path(__file__).resolve().parents[1]
SPECS={
    'backhoe_loader':'backhoe-loader-excavator-e61bfbd8',
    'dump_truck':'dump-truck-8fbb9f8c',
    'concrete_mixer':'concrete-mixer-truck-af73974f',
    'site_cabin':'construction-site-cabin-6da41273',
    'mobile_scaffold':'mobile-scaffold-tower-235bde60',
    'site_toilet':'portable-site-toilet-3347fcc7',
    'tower_crane':'tower-crane-898f1b82',
}


def download():
    folder=ROOT/'assets/incoming/construction_innerscene';folder.mkdir(parents=True,exist_ok=True)
    for key,slug in SPECS.items():
        for suffix,url in [('html',f'https://www.innerscene.com/tools/library/3d-parts/{slug}'),
                           ('glb',f'https://www.innerscene.com/api/library/{slug}/download')]:
            path=folder/f'{key}.{suffix}'
            if path.exists():continue
            partial=path.with_suffix(path.suffix+'.part')
            subprocess.run(['curl','--fail','--silent','--show-error','--location','--proto','=https',
                '--proto-redir','=https','--max-time','120','--max-filesize','52428800',
                '--output',str(partial),url],check=True)
            if suffix=='glb' and partial.read_bytes()[:4]!=b'glTF':raise ValueError('Not a GLB download')
            partial.replace(path)
        print('downloaded',key,flush=True)


def prepare(promote=False):
    source=ROOT/'assets/incoming/construction_innerscene'
    folder=ROOT/'assets/prepared/construction_innerscene';folder.mkdir(parents=True,exist_ok=True)
    registry=AssetRegistry()
    for key,slug in SPECS.items():
        page=(source/f'{key}.html').read_text()
        if 'CC0' not in page or 'Innerscene' not in page:raise ValueError('Missing expected source/license')
        path=source/f'{key}.glb';doc,buffers=_read_gltf(path)
        low,high=_selected_bounds(doc,doc['scenes'][doc.get('scene',0)]['nodes'])
        extent=[high[i]-low[i] for i in range(3)];bounds={'min':low,'max':high,'extent':extent}
        aid='construction_innerscene_'+key
        normalized=_canonicalize_document(doc,bounds,asset_id=aid,source_up_axis='+Y',source_forward_axis='+X')
        # The legacy helper always maps source +Z to canonical +X. These
        # vehicles use source +X as their longitudinal axis instead.
        ex,ey,ez=extent;cx,cy,cz=[(a+b)/2 for a,b in zip(low,high)]
        for index in range(len(doc.get('nodes',[])),len(normalized['nodes'])):
            normalized['nodes'][index]['matrix']=[1/ex,0,0,0, 0,0,1/ey,0,
                0,-1/ez,0,0, -cx/ex,cz/ez,-cy/ey,1]
        payload=_write_glb(normalized,buffers,path.parent);digest=hashlib.sha256(payload).hexdigest()
        filename=aid+'_'+digest[:12]+'.glb';(folder/filename).write_bytes(payload)
        metrics=_document_metrics(doc,bounds)
        if metrics['skin_count'] or metrics['animation_count']:
            raise ValueError('This importer supports static equipment only')
        mast_fraction=None
        if key=='tower_crane':
            nodes=[i for i,n in enumerate(doc['nodes']) if 'mast' in n.get('name','').lower()]
            if not nodes:raise ValueError('Crane mast anchor cannot be identified')
            a,b=_selected_bounds(doc,nodes)
            mast_fraction=((a[0]+b[0])/2-cx)/ex
        record=AssetRecord(aid,'construction_equipment',tags=('outdoor','construction',key),
            environment='outdoor',dimensions_m=(extent[0],extent[2],extent[1]),geometry_path=filename,
            source='Innerscene',license_id='CC0-1.0',quality_score=.85,
            metadata={'outdoor_pack_status':'ready' if promote else 'candidate','external_content':True,
                'redistribution_policy':'download_required','manual_only':True,'preserve_physical_proportions':True,
                'source_url':f'https://www.innerscene.com/tools/library/3d-parts/{slug}',
                'download_url':f'https://www.innerscene.com/api/library/{slug}/download',
                'author':'Innerscene','license_url':'https://creativecommons.org/publicdomain/zero/1.0/',
                'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'output_sha256':digest,
                'mesh_validation':metrics,'source_bounds':bounds,'equipment_operable':False,
                'origin_x_fraction':-(low[0]+high[0])/2/extent[0],
                'mast_anchor_x_fraction':mast_fraction,
                'visual_review':{'status':'accepted' if promote else 'pending',
                    'note':'Four-view checked: complete static prop, proportions restored, +X front, +Z up; crane anchor measured from mast nodes.' if promote else '',
                    'sha256':digest},
                'orientation':{'canonical_up_axis':'+Z','canonical_forward_axis':'+X',
                    'visually_checked':promote,'orientation_confidence':'reviewed' if promote else 'unreviewed'},
                'placement_rules':{'allowed_contexts':['construction_site'],'indoor':False}})
        registry.register(record)
        print(aid,'dims',record.dimensions_m,'triangles',metrics.get('triangle_count'),'textures',len(doc.get('textures',[])),flush=True)
    registry.save(folder/'asset_registry.json')
    if promote:
        production=AssetRegistry(ROOT/'assets/asset_registry.json')
        for record in registry.list_all():
            production.register(replace(record,geometry_path=str((folder/record.geometry_path).relative_to(ROOT/'assets'))),overwrite=True)
        production.save()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--download',action='store_true')
    p.add_argument('--promote-reviewed',action='store_true');a=p.parse_args()
    if a.download:download()
    prepare(a.promote_reviewed)
