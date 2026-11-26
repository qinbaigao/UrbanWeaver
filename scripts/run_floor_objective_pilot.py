"""Development intent/qualification probe, not end-to-end requirement extraction."""
import argparse
from dataclasses import asdict, replace
import json
from pathlib import Path

from cityg.agents import AgentGenerationError
from cityg.agents.building_floor import BuildingFloorAgent
from cityg.design_goals import validate_goals
from cityg.planning.floor_objectives import interpret_organization
from cityg.run_provenance import source_snapshot
from cityg.serialization import _building, save_json
from cityg.services.interfaces import ModelEndpoint
from cityg.services.openai_compatible import OpenAICompatibleService


CASES=[
    ('cn_private','每层以客厅作为各自居住单元的入口，卧室和卫生间只从各自客厅进入，尽量不直接接公共走廊。','private_groups'),
    ('cn_independent','办公室都应从公共走廊独立进入，不希望穿过另一间办公室才能到达。','independent'),
    ('cn_neutral','希望各层显得温馨明亮，颜色自然一些。','unspecified'),
    ('cn_qualified','只把三楼做成客厅带私有卧室的组团，其余楼层不要这样。','unspecified'),
    ('en_private','Use a shared living entry for each suite; bedrooms should be reached through that living entry, not directly from the public corridor.','private_groups'),
    ('en_independent','Avoid nested private suites. Give every enclosed room its own access from the common corridor.','independent'),
    ('en_conflict','Every room must have direct public corridor access, but every bedroom must only be entered through a private living room.','unspecified'),
    ('en_scope','Building B should use private suites. Do not change the organization of the other buildings.','unspecified'),
]
FIXTURE_INDICES={'cn_independent':2}  # Office-specific wording belongs to a commercial building.


def run(output,config):
    output.mkdir(parents=True,exist_ok=False)
    save_json(source_snapshot(),output/'source_provenance.json')
    fixtures=json.loads(Path('tests/fixtures/floor_brief_contracts.json').read_text())['cases']
    endpoint=replace(ModelEndpoint(**config['endpoint']),max_tokens=512,seed=101)
    save_json({'cases':CASES,'endpoint':asdict(endpoint),'fixture_indices':FIXTURE_INDICES,
               'buildings':[r['building'] for r in fixtures]},output/'protocol.json')
    rows=[]
    for key,quote,expected in CASES:
        building=_building(fixtures[FIXTURE_INDICES.get(key,0)]['building'])
        agent=BuildingFloorAgent(OpenAICompatibleService(endpoint),model_id=endpoint.model,max_calls=1)
        agent.design_goals=validate_goals({'goals':[{'source_quote':quote,'preference':quote,'levels':['floor']}]},quote)
        row={'id':key,'expected':expected,'correct':False}
        try:
            objective,attempts=interpret_organization(agent,building)
            row.update(objective=objective,correct=objective['organization']==expected)
        except AgentGenerationError as exc:attempts=exc.attempts;row['error']=str(exc)
        row['attempts']=[asdict(a) for a in attempts];rows.append(row)
        save_json(row,output/f'trials/{key}.json')
        save_json({'completed':len(rows),'expected_trials':len(CASES),
            'correct':sum(r['correct'] for r in rows),'rows':rows,
            'limitations':['Handwritten development preferences already placed in quoted floor goals.',
                'No full instruction extraction, geometric planning, edits or rendered privacy evaluation.',
                'Qualified preferences conservatively defer; no per-floor objective model in this path.']},output/'summary.json')
        print(key,row['correct'],row.get('objective'),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--config',type=Path,default=Path('configs/model_method_pilot.json'))
    a=p.parse_args();run(a.output,json.loads(a.config.read_text()))
