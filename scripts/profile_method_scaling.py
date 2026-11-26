"""Development compiler/context scaling, without models, assets or rendering."""
import argparse
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import statistics
import time

from cityg.agents import RepairAgent
from cityg.evaluation.error_injection import inject_error
from cityg.geometry import GeometryCompiler
from cityg.geometry.incremental import merge_building_scene
from cityg.planning.baseline import BaselineCityPlanner
from cityg.planning.generation_prototypes import DeferredFurniture
from cityg.run_provenance import source_snapshot
from cityg.schemas import CitySpec
from cityg.serialization import save_json, to_primitive
from cityg.subtree_transactions import FloorSubtreePlanner
from cityg.validation import CityValidator


def digest(value):
    return hashlib.sha256(json.dumps(to_primitive(value),sort_keys=True,separators=(',',':')).encode()).hexdigest()


def equivalent(a,b):
    # Runtime metrics and compile-scope metadata intentionally differ.
    fields = ('primitives','materials','state_machines','layers','activation_tiers')
    result = {}
    for field in fields:
        aa,bb=getattr(a,field),getattr(b,field)
        key='name' if field=='activation_tiers' else 'id'
        left={getattr(x,key):digest(x) for x in aa};right={getattr(x,key):digest(x) for x in bb}
        result[field]=left==right and len(left)==len(aa) and len(right)==len(bb)
    for field in ('nodes','edges'):
        aa,bb=getattr(a.navigation,field),getattr(b.navigation,field)
        left={x.id:digest(x) for x in aa};right={x.id:digest(x) for x in bb}
        result['navigation_'+field]=left==right and len(left)==len(aa) and len(right)==len(bb)
    result['building_prototypes']=a.building_prototypes==b.building_prototypes
    result['coordinate_system']=a.coordinate_system==b.coordinate_system
    return result


def run(output,sizes,repeats):
    output.mkdir(parents=True,exist_ok=False)
    save_json(source_snapshot(),output/'source_provenance.json')
    rows=[]
    def publish():
        save_json({'evidence_type':'offline_development_profile','model_calls':0,
            'configured_sizes':sizes,'repeats':repeats,
            'limitations':['One seed, two floors/building, unfurnished procedural geometry; not full city quality.',
                'Inputs copied outside timer; incremental timer includes subset compilation and merge.',
                'No disk IO, USD writing, binary assets, render or model latency in measured compile time.',
                'No total-scene metadata equivalence claim; rendering/navigation fields compared explicitly.',
                'City width changes with building count, so not a strict fixed-local-geometry distractor experiment.'],
            'rows':rows},output/'summary.json')
    publish()
    for n in sizes:
        print('size_start',n,flush=True)
        width=max(180,60*math.sqrt(n))
        spec=CitySpec(building_count=n,min_floors=2,max_floors=2,width_m=width,depth_m=width,seed=101)
        try:
            city=BaselineCityPlanner(floor_detail_agent=DeferredFurniture()).plan(spec)
            if not CityValidator().validate(city).ok:raise ValueError('Invalid fixture')
        except Exception as exc:
            rows.append({'buildings':n,'spec':to_primitive(spec),'status':'fixture_failed',
                         'error':f'{type(exc).__name__}: {exc}','speedup_if_equivalent':None})
            publish()
            print('size_end',n,'fixture_failed',rows[-1]['error'],flush=True)
            continue
        building=next(city.iter_buildings());floor=building.floors[0]
        broken=inject_error(city,'disconnected_entrance')
        context=RepairAgent(None)._context(broken,CityValidator().validate(broken),building.id)
        baseline=GeometryCompiler().compile(deepcopy(city))
        changed=FloorSubtreePlanner().replace(city,floor.id,{'room_count':4}).city
        timings={'full':[],'incremental':[]};checks=[];last_stats=None
        for repeat in range(repeats):
            results={}
            for mode in (('full','incremental') if repeat%2==0 else ('incremental','full')):
                draft=deepcopy(changed);compiler=GeometryCompiler();start=time.perf_counter()
                if mode=='full':result=compiler.compile(draft)
                else:
                    subset=compiler.compile(draft,building_ids={building.id})
                    result,last_stats=merge_building_scene(draft,baseline,subset,{building.id},previous_city=city)
                timings[mode].append(time.perf_counter()-start);results[mode]=result
            checks.append(equivalent(results['full'],results['incremental']))
        exact=all(all(c.values()) for c in checks)
        rows.append({'buildings':n,'status':'measured','floors':sum(1 for _ in city.iter_floors()),
            'rooms':sum(len(f.rooms) for f in city.iter_floors()),'objects':sum(len(f.objects) for f in city.iter_floors()),
            'spec':to_primitive(spec),'city_sha256':digest(city),'original_primitives':len(baseline.primitives),
            'full_scene_json_bytes':len(json.dumps(to_primitive(city),ensure_ascii=False).encode()),
            'entrance_repair_context_bytes':len(json.dumps(context,ensure_ascii=False).encode()),
            'context_measurement':'UTF-8 bytes, not tokenizer tokens or model effectiveness',
            'timings_s':timings,'median_s':{k:statistics.median(v) for k,v in timings.items()},
            'equivalence_checks':checks,'equivalent':exact,'incremental_stats':last_stats,
            'speedup_if_equivalent':statistics.median(timings['full'])/statistics.median(timings['incremental']) if exact else None})
        publish()
        print('size_end',n,'equivalent',exact,'median',rows[-1]['median_s'],flush=True)
    return rows


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--sizes',nargs='+',type=int,default=[10,30,60,100]);p.add_argument('--repeats',type=int,default=3)
    a=p.parse_args()
    if a.repeats<1 or any(n<2 for n in a.sizes):p.error('Positive repeats and at least two buildings required')
    rows=run(a.output,a.sizes,a.repeats)
    raise SystemExit(0 if all(r.get('equivalent') for r in rows) else 3)
