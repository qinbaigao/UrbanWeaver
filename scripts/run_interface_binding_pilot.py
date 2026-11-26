"""Equal-fact contract representation diagnostic on actual adjacent-room edits.

Both model arms see identical dependencies, dimensions, locks and candidates.
One receives prose, the other typed records. A deterministic finite solver is a
strong baseline. This is bounded selection, NOT open-ended floor synthesis.
"""
import argparse
from copy import deepcopy
from dataclasses import asdict, replace
import json
from pathlib import Path
import random

from cityg.ccwp import build_world_program, entity_index
from cityg.geometry import GeometryCompiler
from cityg.planning.floor_prototype_lab import make_floor_lab
from cityg.planning.floor_prototypes import FloorPrototypeLibrary
from cityg.planning.floor_repartition import _compiled_locks, _check_compiled_access
from cityg.planning.negotiation import negotiate
from cityg.planning.scope_requirements import ScopeRequirements
from cityg.run_provenance import source_snapshot
from cityg.schemas import Bounds2D, Door, Point2D, Room
from cityg.serialization import save_json
from cityg.services.interfaces import ChatMessage, ModelEndpoint
from cityg.services.openai_compatible import OpenAICompatibleService
from cityg.transactions import fingerprint, refresh_local_overlay
from cityg.validation import CityValidator
from run_edit_method_pilot import RecordedService

SCENARIOS=('left_capacity','right_capacity','door_limited','donor_capacity','locked_donor','shift_budget')
METHODS=('prose_dependencies','typed_contracts','finite_solver','checked_candidates')


def fixture(scenario,seed):
    library=FloorPrototypeLibrary('configs/layout_prototypes/v1')
    city,_=make_floor_lab(library,['office_mixed_v1'])
    b=next(city.iter_buildings());f=b.floors[0]
    x,y=b.footprint.min_x,b.footprint.min_y
    total=7.2 if scenario=='donor_capacity' else 9.0
    edge=5.4 if scenario=='right_capacity' else 3.6
    right_door=4.65 if scenario=='door_limited' else (edge+total)/2
    f.objects=[];f.metadata={}
    f.rooms=[Room(f.id+'_hall','Hall','corridor',Bounds2D(x,y+4.5,x+36,y+24)),
        Room(f.id+'_a','Office A','office',Bounds2D(x,y,x+edge,y+4.5)),
        Room(f.id+'_b','Office B','office',Bounds2D(x+edge,y,x+total,y+4.5)),
        Room(f.id+'_rest','Storage','storage',Bounds2D(x+total,y,x+36,y+4.5))]
    f.doors=[Door(f.id+'_da',f.rooms[1].id,f.rooms[0].id,Point2D(x+edge/2,y+4.5)),
        Door(f.id+'_db',f.rooms[2].id,f.rooms[0].id,Point2D(x+right_door,y+4.5)),
        Door(f.id+'_dr',f.rooms[3].id,f.rooms[0].id,Point2D(x+20,y+4.5)),
        Door(f.id+'_de',f.rooms[0].id,None,b.entrance,1.8,'exterior')]
    city.world_program=build_world_program(city,producer='interface_probe',seed=seed)
    rooms=f.rooms[1:3]
    contract={'floor_id':f.id,'coordinate_frame':'canonical_building_xy_metres',
        'rooms':[{'id':r.id,'bounds':asdict(r.bounds),'required_min_width_m':4.0,
                  'geometry_locked':scenario=='locked_donor' and i==1} for i,r in enumerate(rooms)],
        'doors':[{'room_id':r.id,'x':d.position.x,'width_m':d.width_m} for r,d in zip(rooms,f.doors[:2])],
        'door_corner_margin_m':.15,'door_x_semantics':'opening center; edges are x minus/plus width_m/2',
        'boundary_axis':'x','shared_boundary_before':x+edge,
        'maximum_boundary_displacement_m':.25 if scenario=='shift_budget' else .8,
        'immutable':['all doors','outer rectangle of the pair','other rooms','building shell','vertical cores'],
        'authorized_root':f.id}
    edges=sorted({edge,4.0,total-4.0,total/2,edge-.72,edge+.72})
    rng=random.Random(seed+SCENARIOS.index(scenario));rng.shuffle(edges)
    candidates=[{'id':f'choice_{i}','shared_boundary_x':round(x+e,6)} for i,e in enumerate(edges)]
    return city,b,f,contract,candidates


def violations(contract,edge):
    """Geometric arithmetic oracle: no model labels or scenario name used."""
    a,b=contract['rooms'];errors=[];eps=1e-6
    if edge-a['bounds']['min_x']<a['required_min_width_m']-eps:errors.append('left_capacity')
    if b['bounds']['max_x']-edge<b['required_min_width_m']-eps:errors.append('right_capacity')
    delta=abs(edge-contract['shared_boundary_before'])
    if delta>contract['maximum_boundary_displacement_m']+eps:errors.append('shift_budget')
    if delta>eps and any(r['geometry_locked'] for r in (a,b)):errors.append('locked_geometry')
    for i,d in enumerate(contract['doors']):
        lo=a['bounds']['min_x'] if i==0 else edge
        hi=edge if i==0 else b['bounds']['max_x']
        clearance=d['width_m']/2+contract['door_corner_margin_m']
        if min(d['x']-lo,hi-d['x'])<clearance-eps:errors.append('door_corner')
    return errors


def prose(contract):
    # A lossless alternative representation, not a weaker local-only baseline.
    lines=[f"Floor {contract['floor_id']}; coordinates {contract['coordinate_frame']}. "
        f"Authority is {contract['authorized_root']}. Shared boundary axis is {contract['boundary_axis']}. "
        f"Current shared boundary is {contract['shared_boundary_before']}. Maximum absolute displacement "
        f"is {contract['maximum_boundary_displacement_m']} metres."]
    for r in contract['rooms']:
        lines.append(f"Room {r['id']} has bounds {json.dumps(r['bounds'])}; required minimum width "
            f"{r['required_min_width_m']}; geometry locked={r['geometry_locked']}.")
    for d in contract['doors']:
        lines.append(f"Fixed door of {d['room_id']} has opening CENTER x={d['x']}, width={d['width_m']} "
            '(opening edges are x minus/plus width/2); '
            f"keep at least {contract['door_corner_margin_m']} metres from both opening edges to room corners.")
    lines.append('Immutable: '+', '.join(contract['immutable'])+'.')
    return '\n'.join(lines)


def execute(city,b,f,contract,choice):
    original=deepcopy(city);compiler=GeometryCompiler()
    locks=_compiled_locks(compiler.compile(deepcopy(city),building_ids={b.id}),b,f)
    def candidate(draft,scope,conflict):
        entities=entity_index(draft);a,c=(entities[r['id']] for r in contract['rooms'])
        a.bounds=replace(a.bounds,max_x=choice['shared_boundary_x'])
        c.bounds=replace(c.bounds,min_x=choice['shared_boundary_x'])
        return refresh_local_overlay(original,draft,[f.id])
    def gate(draft):
        if not CityValidator().validate(draft).ok:return {'ok':False}
        nb=entity_index(draft)[b.id];nf=entity_index(draft)[f.id]
        scene=compiler.compile(draft,building_ids={b.id})
        if _compiled_locks(scene,nb,nf)!=locks:raise ValueError('Compiled interface changed')
        _check_compiled_access(scene,nb,f,nf)
        return {'ok':True}
    def resolved(draft,conflict):
        entities=entity_index(draft);a,c=(entities[r['id']] for r in contract['rooms'])
        return abs(a.bounds.max_x-c.bounds.min_x)<1e-6 and not violations(contract,a.bounds.max_x)
    conflict={'conflict_id':'coupled_capacity','entity_id':contract['rooms'][0]['id'],
              'base_fingerprint':fingerprint(city)}
    return negotiate(city,conflict,authorized_roots=[f.id],strategies={'floor':candidate},
        compiled_gate=gate,resolution_gate=resolved,max_attempts=1,source='user_edit',
        scope_requirements=ScopeRequirements(tuple(r['id'] for r in contract['rooms']),('floor',)))


def run(output,seeds,config,compact=False,methods=None):
    selected_methods=methods or METHODS[:3]
    output.mkdir(parents=True,exist_ok=False)
    save_json(source_snapshot(),output/'source_provenance.json')
    save_json({'seeds':seeds,'methods':selected_methods,'scenarios':SCENARIOS,'config':config,
               'calls_per_trial':1,'max_completion_tokens':1024,
               'compact_decisions':compact},output/'protocol.json')
    rows=[]
    for seed in seeds:
        for scenario in SCENARIOS:
            city,b,f,contract,candidates=fixture(scenario,seed)
            feasible=[c for c in candidates if not violations(contract,c['shared_boundary_x'])]
            best=min((abs(c['shared_boundary_x']-contract['shared_boundary_before']) for c in feasible),default=None)
            save_json({'contract':contract,'candidates':candidates,
                       'evaluation_only':{'feasible_ids':[c['id'] for c in feasible]}},output/f'fixtures/{seed}_{scenario}.json')
            order=list(selected_methods);random.Random(f'{seed}:{scenario}').shuffle(order)
            for method in order:
                key=f'{seed}_{scenario}_{method}';print('interface_start',key,flush=True)
                row={'id':key,'method':method,'scenario':scenario,'seed':seed,'feasible_task':bool(feasible),
                     'selection_correct':False,'compiled_success':False,'minimum_change':False}
                service=None;before=fingerprint(city)
                try:
                    if method=='finite_solver' or (method=='checked_candidates' and not feasible):
                        choice=min(feasible,key=lambda c:abs(c['shared_boundary_x']-contract['shared_boundary_before'])) if feasible else None
                        answer={'choice_id':choice['id'] if choice else 'none','reason':'finite constraint search'}
                    else:
                        service=RecordedService(OpenAICompatibleService(replace(ModelEndpoint(**config['endpoint']),
                            seed=seed,max_tokens=1024)),output/f'traces/{key}.json')
                        offered=feasible if method=='checked_candidates' else candidates
                        schema={'type':'object','additionalProperties':False,'properties':{
                            'choice_id':{'type':'string','enum':['none']+[c['id'] for c in offered]},
                            'reason':{'type':'string'}},'required':['choice_id','reason']}
                        if compact:
                            schema['properties']={'reason':{'type':'string','maxLength':240},
                                'choice_id':schema['properties']['choice_id']}
                        payload={'candidate_edits':offered,
                            'interface_contract' if method!='prose_dependencies' else 'complete_dependency_notes':
                                contract if method!='prose_dependencies' else prose(contract)}
                        if method=='checked_candidates':
                            payload['candidate_filter']={'stage':'trusted geometric contract evaluator',
                                'all_offered_candidates_feasible':True,
                                'absolute_displacements':{c['id']:round(abs(c['shared_boundary_x']-
                                    contract['shared_boundary_before']),6) for c in offered}}
                        response=service.complete_with_metadata([ChatMessage(role='system',content=
                            'Choose one shared-wall edit satisfying ALL room capacities, fixed doors, locks and '
                            'displacement limits. Two adjacent rooms must share one boundary. Among feasible edits '
                            'minimize absolute displacement. Select none ONLY when no offered edit can satisfy all '
                            'requirements. Do not assume authority permits changing locked geometry. '
                            +('Give a concise final reason in at most 240 characters, then the consistent choice_id. '
                              'Do not enumerate candidates or put lengthy deliberation in the JSON.' if compact else
                              'Return the choice and reason.')),
                            ChatMessage(role='user',content=json.dumps(payload))],schema)
                        if response.finish_reason=='length':raise ValueError('Truncated response')
                        answer=json.loads(response.content)
                        choice=next((c for c in candidates if c['id']==answer['choice_id']),None)
                        if choice is None and answer['choice_id']!='none':raise ValueError('Unknown choice')
                    row['answer']=answer
                    row['selection_correct']=(choice in feasible if choice else not feasible)
                    row['minimum_change']=(abs(abs(choice['shared_boundary_x']-contract['shared_boundary_before'])-best)<1e-6
                        if choice and row['selection_correct'] else not feasible and choice is None)
                    if choice:
                        candidate,receipt=execute(city,b,f,contract,choice)
                        row['compiled_success']=receipt['status']=='resolved' and row['selection_correct']
                        save_json(receipt,output/f'receipts/{key}.json')
                    else:row['correct_refusal']=not feasible
                except Exception as exc:row['error']=f'{type(exc).__name__}: {exc}'
                row['source_unchanged']=fingerprint(city)==before
                row['model_calls']=len(service.calls) if service else 0
                usage=[c.get('completion',{}).get('usage',{}) for c in service.calls] if service else []
                row['prompt_tokens']=sum(u.get('prompt_tokens',0) for u in usage)
                rows.append(row)
                totals={m:{'trials':len(g:=[r for r in rows if r['method']==m]),
                    'selection_correct':sum(r['selection_correct'] for r in g),
                    'minimum_change':sum(r['minimum_change'] for r in g),
                    'feasible_tasks':sum(r['feasible_task'] for r in g),
                    'compiled_success':sum(r['compiled_success'] for r in g),
                    'correct_refusals':sum(r.get('correct_refusal',False) for r in g),
                    'model_calls':sum(r['model_calls'] for r in g),
                    'prompt_tokens':sum(r['prompt_tokens'] for r in g)} for m in selected_methods}
                save_json({'rows':rows,'summary':totals,'evidence_type':'equal_fact_interface_representation_development',
                    'limitations':['Finite supplied edits, not open-ended hierarchical synthesis.',
                        'Prose and typed arms both include all constraints; same external gates.',
                        'checked_candidates adds geometric prefiltering and measured costs; it is not an equal-evidence representation ablation.',
                        'Finite solver and prefilter share arithmetic predicates; compilation/protection remain separately checked.',
                        'Model seeds/candidate orders repeat six geometry families, not independent cities.',
                        'No aesthetics or learned embodied policy evaluation.']},output/'summary.json')
                print('interface_end',key,row['selection_correct'],row['compiled_success'],row.get('error'),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',required=True,type=Path)
    p.add_argument('--seeds',nargs='+',type=int,default=[101,202])
    p.add_argument('--config',type=Path,default=Path('configs/model_method_pilot.json'))
    p.add_argument('--compact-decisions',action='store_true')
    p.add_argument('--methods',nargs='+',choices=METHODS,default=list(METHODS[:3]))
    a=p.parse_args();run(a.output,a.seeds,json.loads(a.config.read_text()),a.compact_decisions,a.methods)
