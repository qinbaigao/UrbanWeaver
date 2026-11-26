"""Frozen semantic scene, different rendered asset payload: vision-only diagnostic.

The bad local package binds the chair ID to fern geometry. This simulates a
mislabelled/imported mesh: successful asset loading cannot establish semantics.
Only case-local registry records are changed; shared assets remain read-only.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path

from cityg.assets import AssetRegistry
from cityg.serialization import load_city,save_json
from run_easy_visual_defects import render, public_context
from run_visual_input_ablation import target


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,default=Path('analysis_results/easy_visual_defects_20261023/case_01'))
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    city=load_city(args.source/'scene/city.json');b,f,r=target(city)
    chair=next(o for o in f.objects if o.room_id==r.id and o.category=='office_chair')
    registry=AssetRegistry('assets/asset_registry.json')
    fern=registry.get('prepared_polyhaven_fern_02_a')
    source_registry=json.loads((args.source/'scene/assets/asset_registry.json').read_text())
    rows=[]
    for case,bad in [('case_01',False),('case_02',True)]:
        root=args.output/case
        for name in ('city.json','geometry_manifest.json','navigation.json','interactions.json','activation_manifest.json'):
            save_json(json.loads((args.source/'scene'/name).read_text()),root/'scene'/name)
        data=deepcopy(source_registry)
        if bad:
            items=data if isinstance(data,list) else data['assets']
            rec=next(x for x in items if x['asset_id']==chair.asset_id)
            rec['geometry_path']=str(registry.resolve_path(fern.geometry_path).resolve())
        save_json(data,root/'scene/assets/asset_registry.json')
        save_json(json.loads((args.source/'render_plan.json').read_text()),root/'render_plan.json')
        save_json(public_context(f,r),root/'public_context.json')
        save_json({'condition':'wrong_asset_payload' if bad else 'clean',
            'object_id':chair.id,'target_group_ids':['work'] if bad else [],
            'semantic_scene_identical':True,'fault':'local registry geometry payload only' if bad else None},root/'private_truth.json')
        rows.append({'case_id':case})
    save_json({'cases':rows,'scope':'render realization diagnostic; canonical metadata identical'},args.output/'protocol.json')
    render(args.output)


if __name__=='__main__':main()
