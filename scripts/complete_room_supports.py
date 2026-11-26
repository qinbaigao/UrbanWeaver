"""Probe missing support annotations on furniture used by selected Hero rooms.

Static, normalized GLBs only; never trust an AABB top or change asset dimensions.
Shelf fronts require an existing reviewed orientation. Writes a candidate
registry/report by default; --apply explicitly promotes geometry-checked patches.
"""
import argparse
from collections import defaultdict
from dataclasses import replace
import hashlib
from pathlib import Path

from cityg.assets import AssetRegistry
from cityg.serialization import load_city, save_json
from scripts.annotate_interior_assets import triangles
from scripts.annotate_hssd_assets import discover_supports

TOP_CATEGORIES={'desk','bedside_table','dining_table','meeting_table','coffee_table',
                'kitchen_counter','reception_desk','checkout_counter','cabinet','tv_console','workbench'}
SHELF_CATEGORIES={'bookcase','storage_rack','display_shelf'}


def complete(scene, registry_path, output, apply=False):
    if output.exists() and any(output.iterdir()):
        raise ValueError('Use a fresh annotation output directory')
    output.mkdir(parents=True,exist_ok=True)
    source=AssetRegistry(registry_path)
    registry=AssetRegistry()
    registry.register_many(source.list_all())
    city=load_city(scene/'city.json' if scene.is_dir() else scene)
    needed=defaultdict(set)
    for b in city.iter_buildings():
        for f in b.floors:
            for r in f.rooms:
                if r.metadata.get('detail_tier')!='hero': continue
                objects={o.metadata.get('design_member_id'):o for o in f.objects if o.room_id==r.id}
                for request in r.metadata.get('room_design',{}).get('surface_items',[]):
                    obj=objects.get(request['support_member_id'])
                    if obj: needed[obj.asset_id].add(request['surface'])
    report=[]
    for asset_id,kinds in sorted(needed.items()):
        record=registry.get(asset_id)
        if record is None or not record.geometry_path: continue
        existing=list(record.metadata.get('room_support_surfaces',[]))
        missing=kinds-{s['kind'] for s in existing if s.get('verified')}
        if not missing: continue
        item={'asset_id':asset_id,'requested_kinds':sorted(missing),'added':[],'diagnostics':[]}
        report.append(item)
        try:
            path=source.resolve_path(record.geometry_path)
            digest=hashlib.sha256(path.read_bytes()).hexdigest()
            mesh=triangles(path)
            for kind in sorted(missing):
                if record.category not in (TOP_CATEGORIES if kind=='top' else SHELF_CATEGORIES):
                    item['diagnostics'].append('unsupported_semantic_support_category:'+kind);continue
                orientation=record.metadata.get('orientation',{})
                front=orientation.get('canonical_forward_axis')
                if kind=='shelves' and (orientation.get('orientation_confidence')!='reviewed' or front not in {'+X','-X','+Y','-Y'}):
                    item['diagnostics'].append('shelves_require_reviewed_front');continue
                patches,failures=discover_supports(mesh,record.dimensions_m,kind,front or '+Y')
                for patch in patches:
                    patch['id']='supplement_'+patch['id']
                    patch['evidence']={'geometry_sha256':digest,'semantic_category':record.category,
                                       'verification':'triangle_contact_and_clearance_not_load_bearing'}
                existing.extend(patches)
                item['added'].extend(patches)
                item['diagnostics'].extend(failures[:4])
            if item['added']:
                registry.register(replace(record,metadata={**record.metadata,'room_support_surfaces':existing}),overwrite=True)
        except (ValueError,KeyError,OSError) as exc:
            item['diagnostics'].append(str(exc))
        save_json({'assets':report,'production_updated':False},output/'support_report.json')
    # Preserve a portable candidate registry: relative geometry paths must
    # remain relative to the original asset registry, not this report folder.
    candidate=AssetRegistry()
    candidate.register_many(replace(r,geometry_path=str(source.resolve_path(r.geometry_path).resolve()))
                            if r.geometry_path else r for r in registry.list_all())
    candidate.save(output/'candidate_registry.json')
    if apply:
        save_json({'source':str(registry_path.resolve()),'records':[
            source.require(i['asset_id']).to_dict() for i in report if i['added']]},
            output/'previous_annotations.json')
        registry.save(registry_path)
    save_json({'assets':report,'production_updated':apply,
               'candidate_geometry_base':'absolute_paths'},output/'support_report.json')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('scene',type=Path)
    parser.add_argument('--registry',type=Path,default=Path('assets/asset_registry.json'))
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    result=complete(args.scene,args.registry,args.output,args.apply)
    print('assets with added supports:',sum(bool(i['added']) for i in result))
