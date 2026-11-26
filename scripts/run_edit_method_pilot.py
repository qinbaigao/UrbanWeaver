"""Real production editing acceptance, separate from automatic conflict repair."""
import argparse
from copy import deepcopy
from dataclasses import asdict, replace
import json
from pathlib import Path
import time

from cityg.editing import run_edit
from cityg.evaluation.method_pilot import room_count
from cityg.evaluation.model_repair_pilot import attempt_cost
from cityg.run_provenance import source_snapshot
from cityg.repair import PatchRejected
from cityg.serialization import load_city, save_json
from cityg.services.interfaces import ModelEndpoint
from cityg.services.openai_compatible import OpenAICompatibleService
from cityg.transactions import fingerprint
from cityg.validation import CityValidator


class RecordedService:
    """Retain actual model calls even when planning fails before run_edit saves its plan."""
    def __init__(self, service, path):
        self.service, self.path, self.calls = service, path, []

    def complete_with_metadata(self, messages, response_schema=None):
        row = {'messages':[{'role':m.role,'content':m.content,'images':[str(p) for p in m.image_paths]} for m in messages],
               'schema':response_schema}
        started=time.perf_counter()
        try:
            result=self.service.complete_with_metadata(messages,response_schema)
            row['completion']=asdict(result)
            return result
        except Exception as exc:
            row['error']=f'{type(exc).__name__}: {exc}'
            raise
        finally:
            row['elapsed_s']=time.perf_counter()-started
            self.calls.append(row);save_json(self.calls,self.path)

    def complete(self,messages,response_schema=None):
        return self.complete_with_metadata(messages,response_schema).content


def run(config, fixtures, output, kinds=None):
    output.mkdir(parents=True, exist_ok=False)
    save_json(config, output/'config.json');save_json(source_snapshot(), output/'source_provenance.json')
    rows = []
    for seed in config['seeds']:
        original = load_city(fixtures/f'{seed}_clean.json')
        building = next(original.iter_buildings()); floors = building.floors[:2]
        target = 4 if any(room_count(f) != 4 for f in floors) else 6
        common = '保留建筑外轮廓、入口和核心筒。只修改明确指定的实体，不修改其它楼层或建筑。'
        cases = [
            ('rename', f'仅将 id={building.id} 的建筑显示名称改为“评测楼甲”。'+common),
            ('single_floor', f'将 id={floors[0].id} 的楼层重新分区为严格{target}个非走廊房间。'+common),
            ('two_floors', f'将 id={floors[0].id} 和 id={floors[1].id} 两个楼层分别重新分区，每层严格{target}个非走廊房间。'+common),
            ('ambiguous', '把这栋楼重新规划一下，让房间更多。'),
            ('unsupported', f'将 id={floors[0].id} 的楼层改为65个房间，不能减少数量。'+common),
            ('locked', f'将 id={floors[0].id} 的楼层重新分区为严格{target}个非走廊房间。'+common),
        ]
        for kind, instruction in cases:
            if kinds is not None and kind not in kinds: continue
            city = deepcopy(original)
            if kind == 'locked':
                next(n for n in city.world_program.nodes if n.entity_id == floors[0].id).locked = True
            source = output/f'fixtures/{seed}_{kind}/city.json';save_json(city, source)
            before = fingerprint(city);start = time.perf_counter();destination = output/f'runs/{seed}_{kind}'
            row = {'seed': seed, 'kind': kind, 'instruction': instruction, 'before_sha256': before,
                   'status': 'error', 'ok': False, 'cost': None}
            print('edit_start', seed, kind, flush=True)
            service=None
            try:
                endpoint = replace(ModelEndpoint(**config['endpoint']), seed=seed, max_tokens=4096)
                service=RecordedService(OpenAICompatibleService(endpoint),output/f'traces/{seed}_{kind}.json')
                result = run_edit(source, instruction, destination, service,
                    model_id=endpoint.model, backend='manifest', no_viewer=True, max_attempts=2)
                row.update(status=result.status, error=result.error, cost=attempt_cost(result.plan.attempts))
                candidate = load_city(result.output_city) if result.output_city else city
                b = next(b for b in candidate.iter_buildings() if b.id == building.id)
                row['outside_building_preserved'] = list(city.iter_buildings())[1] == list(candidate.iter_buildings())[1]
                row['interfaces_preserved'] = (b.footprint,b.entrance,b.vertical_connectors)==(building.footprint,building.entrance,building.vertical_connectors)
                row['structural_ok'] = CityValidator().validate(candidate).ok
                if kind == 'rename':
                    row['goal_met'] = b.name == '评测楼甲' and b.floors == building.floors
                elif kind in ('single_floor','two_floors'):
                    targets = b.floors[:1] if kind == 'single_floor' else b.floors[:2]
                    row['goal_met'] = all(room_count(f) == target for f in targets)
                    if kind == 'single_floor': row['goal_met'] &= b.floors[1:] == building.floors[1:]
                else:
                    row['goal_met'] = result.status != 'applied' and fingerprint(candidate) == before and not (destination/'final').exists()
                row['ok'] = all(row[k] for k in ('goal_met','outside_building_preserved','interfaces_preserved','structural_ok'))
                row['after_sha256'] = fingerprint(candidate)
            except PatchRejected as exc:
                row.update(status='rejected', error=f'{type(exc).__name__}: {exc}', rejection_code=exc.code)
                row['ok'] = kind == 'locked' and exc.code == 'locked_node' and not (destination/'final').exists()
            except Exception as exc:
                row['error'] = f'{type(exc).__name__}: {exc}'
                # Infrastructure errors never count as correct refusal.
                row['ok'] = False
            row['source_unchanged'] = fingerprint(load_city(source)) == before
            if service is not None:
                usage=[c.get('completion',{}).get('usage',{}) for c in service.calls]
                row['actual_model_calls']=len(service.calls)
                row['actual_usage']={k:sum(u[k] for u in usage) if all(k in u for u in usage) else None
                                     for k in ('prompt_tokens','completion_tokens')}
            row['ok'] &= row['source_unchanged'];row['elapsed_s'] = time.perf_counter()-start
            rows.append(row)
            save_json({'evidence_type':'real_model_production_edit_development',
                'automatic_M3_repair':False, 'scenarios_independent_not_multiturn':True,
                'asset_generation':False, 'rows':rows,
                'passed':sum(r['ok'] for r in rows),'completed':len(rows)}, output/'summary.json')
            print('edit_end', seed, kind, row['status'], row['ok'], row.get('error'), flush=True)
    return rows


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path,default=Path('configs/model_method_pilot.json'))
    p.add_argument('--fixtures',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--kinds',nargs='+',choices=['rename','single_floor','two_floors','ambiguous','unsupported','locked'])
    a=p.parse_args();run(json.loads(a.config.read_text()),a.fixtures,a.output,a.kinds)
