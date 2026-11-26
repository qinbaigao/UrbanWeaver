"""Authored-candidate offline checks; no LLM/VLM or production registry writes.

Only compact evidence is saved. No USD/GLB copies or portable Viewer exports.
"""
import argparse
import json
import time
from pathlib import Path

from cityg.assets import AssetRegistry, MaterialLibrary
from cityg.geometry import GeometryCompiler
from cityg.ccwp import build_world_program
from cityg.planning.prototypes import LayoutPrototypeLibrary
from cityg.planning.floor_prototypes import FloorPrototypeLibrary, circulation_raster
from cityg.planning.prototype_lab import make_lab, populate_reference, detached_registry, compiled_containment_checks
from cityg.planning.prototype_decor_assets import add_review_decorations
from cityg.validation.visual_grounding import room_facts
from cityg.serialization import save_json


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--library',type=Path,default=Path('configs/layout_prototypes/v1'))
    parser.add_argument('--prototypes',nargs='+',help='Check only these room IDs')
    parser.add_argument('--room-batch',default='rooms_reliability01.json',
                        help='Room definitions within configs/layout_prototypes/v1')
    parser.add_argument('--skip-floors',action='store_true')
    args=parser.parse_args()
    if args.output.exists(): parser.error('Use a new evidence filename')
    root=args.library
    library=LayoutPrototypeLibrary(root)
    registry=detached_registry(AssetRegistry('assets/asset_registry.json'))
    batch=root/args.room_batch
    if batch.resolve().parent != root.resolve():parser.error('room-batch must be a library filename')
    keys=args.prototypes or [r['id'] for r in json.loads(batch.read_text())['prototypes']]
    if len(keys)!=len(set(keys)) or any(k not in library.rooms for k in keys):
        parser.error('Select distinct room IDs present in this library')
    used={a for key in keys for a in library.materialize(key).asset_bindings.values()}
    for path in sorted(root.glob('reference_assets_*.json')):
        add_review_decorations(registry,path,project_root=Path.cwd(),asset_ids=used)
    report={'provenance':'assistant_authored_candidates_offline_not_model_success',
            'model_calls':0,'human_visual_approval':False,'rooms':[],'floors':[]}
    for key in keys:
        record=library.rooms[key]
        for case in [record['reference'],*record.get('adaptation_cases',[])]:
            t=time.monotonic()
            row={'prototype_id':key,'case':case,'ok':False}
            try:
                city,targets=make_lab(library,[key],{key:case})
                evidence=populate_reference(city,targets[0],library,registry)
                city.world_program=build_world_program(city,producer='offline_authored',seed=17)
                scene=GeometryCompiler(asset_registry=registry,
                    material_library=MaterialLibrary('assets/incoming/interior_materials/material_library.json')).compile(city)
                checks=compiled_containment_checks(scene,targets)
                room=targets[0][3]
                props=scene.metadata.get('room_surface_items',{}).get(room.id,{})
                expected=sum(p['count'] for p in library.materialize(key).design.surface_items)
                facts=room_facts(city,room.id)
                row.update(major_count=evidence['major_count'],compiled_containment=checks,
                           surface_items=props,expected_surface_items=expected,independent_facts=facts,
                           constraint_checks=evidence['constraint_checks'])
                row['ok']=(bool(checks) and all(c['ok'] for c in checks) and
                    props.get('placed',0)==props.get('requested',0)==expected and
                    facts['supported'] and not any(c['ok'] is False for c in facts['checks']))
            except Exception as error:
                row['error']=f'{type(error).__name__}: {error}'
            row['elapsed_s']=round(time.monotonic()-t,3)
            report['rooms'].append(row)
            print(key,case['width_m'],case['depth_m'],row['ok'],row.get('error',''),flush=True)
            save_json(report,args.output)
    floors=FloorPrototypeLibrary(root)
    for r in ([] if args.skip_floors else json.loads((root/'floors_reliability01.json').read_text())['prototypes']):
        row={'prototype_id':r['id'],'layout':floors.validate(r),'circulation':circulation_raster(r)}
        row['ok']=row['layout']['ok'] and row['circulation']['ok']
        report['floors'].append(row)
    report['ok']=all(r['ok'] for r in [*report['rooms'],*report['floors']])
    save_json(report,args.output)
    return 0 if report['ok'] else 1


if __name__=='__main__': raise SystemExit(main())
