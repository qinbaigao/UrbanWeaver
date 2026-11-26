"""Additional wording/identity development checks, not held-out paper statistics."""
import argparse
from dataclasses import replace
import json
from pathlib import Path

from cityg.editing import run_edit
from cityg.evaluation.method_pilot import room_count
from cityg.naming import identity_registry
from cityg.run_provenance import source_snapshot
from cityg.serialization import load_city, save_json
from cityg.services.interfaces import ModelEndpoint
from cityg.services.openai_compatible import OpenAICompatibleService
from cityg.transactions import fingerprint
from cityg.validation import CityValidator
from run_edit_method_pilot import RecordedService


def run(source, output, config):
    output.mkdir(parents=True,exist_ok=False)
    save_json(source_snapshot(),output/'source_provenance.json')
    city=load_city(source);before=fingerprint(city)
    original_source=source
    source=save_json(city,output/'source/city.json')
    building=next(city.iter_buildings());a,b=building.floors[:2]
    identities=identity_registry(city)
    cases=[
        ('current_then_target',f'目前 id={a.id} 有6个房间，请重新分区，改为严格4个非走廊房间。',{a.id:4}),
        ('english',f'Repartition id={a.id} to contain exactly 5 non-corridor rooms.',{a.id:5}),
        ('uid_path',f"{identities[a.id]['uid']} 和 {identities[b.id]['path']} 每层严格4个房间。",{a.id:4,b.id:4}),
        ('distinct_counts',f'id={a.id} 改为4个非走廊房间；id={b.id} 改为5个非走廊房间。',{a.id:4,b.id:5}),
        ('ambiguous_total',f'id={a.id} 和 id={b.id} 重新分区，共4个房间。',{}),
        ('unsupported_second',f'id={a.id} 改为4个房间；id={b.id} 改为65个房间，不得减少数量。',{}),
    ]
    rows=[]
    endpoint=replace(ModelEndpoint(**config['endpoint']),seed=303,max_tokens=4096)
    save_json({'endpoint':config['endpoint'],'seed':303,'max_tokens':4096,'cases':cases},output/'config.json')
    for name,instruction,expected in cases:
        instruction+=' 保留建筑轮廓、入口和核心筒，不改变其它楼层或建筑。'
        service=RecordedService(OpenAICompatibleService(endpoint),output/f'traces/{name}.json')
        row={'case':name,'instruction':instruction,'expected':expected,'ok':False}
        try:
            result=run_edit(source,instruction,output/name,service,model_id=endpoint.model,
                            backend='manifest',no_viewer=True,max_attempts=2)
            row['status']=result.status
            after=load_city(result.output_city) if result.output_city else city
            floors={f.id:f for f in after.iter_floors()}
            row['actual']={key:room_count(floors[key]) for key in expected}
            if expected:
                row['ok']=(result.status=='applied' and row['actual']==expected and CityValidator().validate(after).ok
                    and all(floors[f.id]==f for f in city.iter_floors() if f.id not in expected))
                for old,new in zip(city.iter_buildings(),after.iter_buildings()):
                    row['ok'] &= (old.footprint,old.entrance,old.vertical_connectors)==(new.footprint,new.entrance,new.vertical_connectors)
            else:
                row['ok']=result.status=='needs_clarification' and fingerprint(after)==before and not (output/name/'final').exists()
        except Exception as exc:row['error']=f'{type(exc).__name__}: {exc}'
        row['model_calls']=len(service.calls)
        row['source_unchanged']=(fingerprint(load_city(source))==before and
                                 fingerprint(load_city(original_source))==before)
        row['ok'] &= row['source_unchanged'];rows.append(row)
        save_json({'evidence_type':'development_wording_regression','rows':rows,
                   'passed':sum(r['ok'] for r in rows)},output/'summary.json')
        print(name,row['ok'],row.get('status'),row.get('error'),flush=True)
    return rows


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--config',type=Path,default=Path('configs/model_method_pilot.json'))
    a=p.parse_args();rows=run(a.source,a.output,json.loads(a.config.read_text()))
    raise SystemExit(0 if all(r['ok'] for r in rows) else 3)
