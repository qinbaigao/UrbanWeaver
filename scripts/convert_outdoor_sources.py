#!/usr/bin/env python3
"""Verified offline conversions, review registry and explicit hash-bound promotion."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import html
import xml.etree.ElementTree as ET
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from cityg.assets import AssetRecord, AssetRegistry
from cityg.asset_curation import _read_gltf, _document_metrics
from cityg.facade_runtime import _selected_bounds
from scripts.download_review_sources import blob_hash
from scripts.prepare_exterior_assets import write_json

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / 'assets/prepared/outdoor_runtime_v3'


def source_groups(directory):
    manifest = json.loads((directory / 'acquisition_manifest.json').read_text())
    by_path = {f['relative']: f for f in manifest['files']}
    for group in manifest['groups']:
        for name in group['local_files']:
            if blob_hash(directory / name) != by_path[name]['sha']:
                raise ValueError(f'Source integrity check failed: {name}')
    return {g['id']: {**g, 'directory': str(directory)} for g in manifest['groups']}


def make_jobs(config):
    gazebo = source_groups(ROOT / 'assets/incoming/exterior_v3_gazebo')
    other = source_groups(ROOT / 'assets/incoming/exterior_v3_sources')
    jobs = []
    for kind, entries in (('sdf', config['gazebo']), ('person', config['people']), ('gltf', config.get('gltf',[]))):
        for entry in entries:
            group = (gazebo if kind == 'sdf' else other)[entry['id']]
            paths = [Path(group['directory']) / p for p in group['local_files']]
            source = next(p for p in paths if (p.name == 'model.sdf' if kind == 'sdf'
                                               else p.suffix == '.glb' if kind == 'gltf'
                                               else p.name == entry['id'] + '.fbx'))
            asset_id = 'converted_v3_' + entry['id'].lower() + ('_' + entry['state'] if kind == 'person' else '')
            job = {**entry, 'kind': kind, 'asset_id': asset_id, 'source': str(source),
                   'output': str(STAGE / 'converted' / f'{asset_id}.glb'),
                   'texture_limit': config['texture_limit'], 'triangle_budget': entry.get('triangle_budget',config['triangle_budget']),
                   'provenance': {k: group[k] for k in ('repo','revision','license_id','source_url')}}
            if kind == 'sdf':
                job.update(source_root=str(source.parent.parent), texture_root=str(source.parent.parent))
            elif kind == 'person':
                animations = [Path(other['street_actions']['directory']) / p for p in other['street_actions']['local_files']]
                name = ('f_idle_breathe_01.max.fbx' if entry['state'] == 'standing' else
                        ('f_walk_neutral.max.fbx' if 'Female' in entry['id'] else 'm_walk_neutral.max.fbx'))
                job.update(animation=str(next(p for p in animations if p.name == name)),
                           texture_root=str(source.parent.parent), category='person',
                           tags=['person','pedestrian',entry['state'],entry['id'].lower()])
            jobs.append(job)
    return jobs


def index(jobs):
    records, failures = [], []
    for job in jobs:
        source = Path(job['output'])
        if not source.is_file() or not source.with_suffix('.json').is_file():
            failures.append(job['asset_id'])
            continue
        audit = json.loads(source.with_suffix('.json').read_text())
        if audit['job'] != job:
            failures.append(job['asset_id'] + ': stale job')
            continue
        doc, _ = _read_gltf(source)
        low, high = _selected_bounds(doc, doc['scenes'][doc.get('scene',0)]['nodes'])
        if any(abs(low[i]+.5) > .002 or abs(high[i]-.5) > .002 for i in range(3)):
            raise ValueError(f'Noncanonical bounds: {job["asset_id"]} {low} {high}')
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        payload = STAGE / 'glb' / f'{job["asset_id"]}_{digest[:12]}.glb'
        payload.parent.mkdir(parents=True, exist_ok=True)
        if payload.exists() and hashlib.sha256(payload.read_bytes()).hexdigest() != digest:
            raise ValueError('Changed content-addressed payload')
        if not payload.exists():
            shutil.copy2(source, payload)
        metrics = _document_metrics(doc, {'min':low, 'max':high, 'extent':[1,1,1]})
        attribution = (['Microsoft Rocketbox contributors'] if job['kind']=='person' else [])
        model_config = Path(job['source']).parent/'model.config'
        if job['kind']=='sdf' and model_config.is_file():
            attribution = [n.text for n in ET.parse(model_config).findall('.//author/name') if n.text]
        records.append(AssetRecord(job['asset_id'], job['category'], tags=tuple(job['tags']),
            dimensions_m=tuple(audit['dimensions_m']), geometry_path=str(payload.relative_to(STAGE)),
            source=job['provenance']['repo'] + '_exterior_prepared', license_id=job['provenance']['license_id'],
            quality_score=.88, environment='outdoor', metadata={
                'outdoor_pack_status':'candidate', 'external_content':True, 'redistribution_policy':'download_required',
                'license_review_required': job['kind']=='sdf',
                'style':'textured_authored', 'preserve_physical_proportions':True,
                'placement_yaw_offset_deg':job.get('placement_yaw_offset_deg',0),
                'face_road':job['category']=='bus_shelter',
                'orientation':{'canonical_up_axis':'+Z','canonical_forward_axis':'+X','orientation_confidence':'unreviewed'},
                'output_sha256':digest, 'mesh_validation':metrics, 'conversion_audit':str(source.with_suffix('.json').relative_to(STAGE)),
                'static_pose':job.get('state'), 'source_url':job['provenance']['source_url'],
                'source_revision':job['provenance']['revision'], 'manual_only':job.get('manual_only',False),
                'source_authors':attribution,
                'license_note':('Upstream LICENSE CC BY 3.0; manifest CC BY 4.0. Local technical acceptance is not redistribution clearance.'
                                if job['kind']=='sdf' else 'Retain upstream attribution and license on distribution.'),
                'preparation':{'runtime_triangle_budget':job['triangle_budget'], 'texture_limit':job['texture_limit']},
                'placement_rules':{'allowed_contexts':(['sidewalk','plaza','park'] if job['kind']=='person' else
                                   ['road_lane','parking_lot'] if job['category']=='vehicle' else ['park','plaza','sidewalk'])}
            }).to_dict())
    write_json(STAGE / 'candidate_registry.json', {'schema_version':'cityg.assets.v1','assets':records})
    write_json(STAGE / 'conversion_summary.json', {'converted':len(records), 'not_converted':failures})
    print(f'Indexed {len(records)} candidates; {len(failures)} unconverted; no production changes')


def validate_approval(record, review, payload):
    if review.get('status') != 'accepted' or not review.get('note'):
        raise ValueError('Explicit acceptance with visual note required')
    digest = hashlib.sha256(payload.read_bytes()).hexdigest()
    if digest != record.metadata['output_sha256'] or digest != review.get('sha256'):
        raise ValueError('Approval does not match exact mesh payload')
    if record.metadata.get('manual_only'):
        raise ValueError('Placement adapter required')
    if record.metadata['mesh_validation']['triangle_count'] > record.metadata['preparation']['runtime_triangle_budget']:
        raise ValueError('Runtime triangle budget exceeded')
    if not all(review.get(key) is True for key in ('front_checked','scale_checked','materials_checked','pose_checked')):
        raise ValueError('Incomplete visual approval')


def promote(review_path):
    registry_path = ROOT / 'assets/asset_registry.json'
    registry = AssetRegistry(registry_path)
    candidates = AssetRegistry(STAGE / 'candidate_registry.json')
    preview = json.loads((STAGE / 'review/preview_manifest.json').read_text())
    rendered = {r['asset_id']:r for r in preview['assets'] if r['status']=='rendered'}
    records = []
    for asset_id, review in json.loads(review_path.read_text())['assets'].items():
        if review.get('status') != 'accepted':
            continue
        record = candidates.require(asset_id)
        payload = candidates.resolve_path(record.geometry_path)
        validate_approval(record, review, payload)
        if asset_id not in rendered:
            raise ValueError('Successful four-view load required')
        if (Path(rendered[asset_id]['resolved_geometry_path']).resolve() != payload.resolve()
                or list(record.dimensions_m) != rendered[asset_id]['dimensions_m']):
            raise ValueError('Preview is stale: rerender exact candidate payload and dimensions')
        metadata = {**record.metadata,'outdoor_pack_status':'ready','visual_review':review,
                    'orientation':{**record.metadata['orientation'],'orientation_confidence':'medium','visually_checked':True}}
        metadata['conversion_audit'] = os.path.relpath(STAGE / metadata['conversion_audit'], registry_path.parent)
        records.append(replace(record, geometry_path=os.path.relpath(payload, registry_path.parent),metadata=metadata))
    backup = STAGE / 'registry_backups' / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f') + '.json')
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(registry_path, backup)
    registry.manifest_path = None
    registry.register_many(records, overwrite=True)
    write_json(registry_path, {'schema_version':'cityg.assets.v1','assets':[r.to_dict() for r in registry.list_all()]})
    print(f'Promoted {len(records)} reviewed assets, previous registry backed up')


def gallery(review_path):
    registry=AssetRegistry(STAGE/'candidate_registry.json')
    reviews=json.loads(review_path.read_text())['assets']
    target=STAGE/'gallery'
    (target/'images').mkdir(parents=True,exist_ok=True)
    cards=[]
    for record in registry.list_all():
        review=reviews.get(record.asset_id, {'status':'pending','note':'Not reviewed'})
        image=STAGE/'review/previews'/f'{record.asset_id}.png'
        markup='<p>Preview unavailable</p>'
        if image.is_file():
            shutil.copy2(image,target/'images'/image.name)
            markup=f'<a href="images/{image.name}"><img src="images/{image.name}" loading="lazy"></a>'
        text=f'{record.asset_id} | {record.category} | {review["status"]}'
        cards.append(f'<article>{markup}<h3>{html.escape(text)}</h3><p>{html.escape(review["note"])}</p>'
                     f'<p>{html.escape(str(record.dimensions_m))} m | {record.metadata["mesh_validation"]["triangle_count"]} triangles</p>'
                     f'<p>{html.escape(record.license_id)} | {html.escape(", ".join(record.metadata["source_authors"]))}</p></article>')
    target.joinpath('index.html').write_text('''<!doctype html><meta charset="utf-8"><title>CityG 转换验收</title>
<style>body{font:15px system-ui;background:#e8eeeb;margin:24px}main{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:16px}article{background:white;padding:12px;overflow-wrap:anywhere}img{width:100%}input{padding:12px;width:90%}</style>
<h1>车辆、自然姿态人物与公共设施：转换验收</h1><p>accepted 为本地运行通过；held 为暂不接入。技术验收不等于再分发授权核对完成。</p>
<input id="filter" placeholder="person / vehicle / accepted / held"><main>'''+''.join(cards)+'''</main>
<script>document.querySelector('input').oninput=e=>document.querySelectorAll('article').forEach(a=>a.hidden=!a.textContent.toLowerCase().includes(e.target.value.toLowerCase()))</script>''',encoding='utf-8')
    print(target/'index.html')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['convert','index','promote','gallery'])
    p.add_argument('--config',type=Path,default=ROOT/'configs/outdoor_conversion_v3.json')
    p.add_argument('--blender',default='blender')
    p.add_argument('--id',action='append',default=[])
    p.add_argument('--reviews',type=Path,default=ROOT/'configs/outdoor_conversion_v3_reviews.json')
    args = p.parse_args()
    if args.action=='promote':
        promote(args.reviews)
        return
    if args.action=='gallery':
        gallery(args.reviews)
        return
    jobs = make_jobs(json.loads(args.config.read_text()))
    if args.action=='convert':
        for job in jobs:
            if args.id and job['id'] not in args.id:
                continue
            path = STAGE/'jobs'/f'{job["asset_id"]}.json'
            write_json(path, job)
            log = path.with_suffix('.log')
            with log.open('w') as stream:
                result = subprocess.run([args.blender,'--background','--factory-startup','--disable-autoexec',
                      '--threads','2','--python-exit-code','1','--python',str(ROOT/'scripts/blender_outdoor_convert.py'),
                      '--',str(path)],stdout=stream,stderr=subprocess.STDOUT,timeout=300)
            print(f'{job["asset_id"]}: {"converted" if result.returncode==0 else "FAILED: " + str(log)}',flush=True)
    index(jobs)


if __name__=='__main__':
    main()
