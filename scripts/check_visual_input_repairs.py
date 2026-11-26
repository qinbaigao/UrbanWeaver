"""Execute supported proposals from the input experiment with narrow attribution.

This diagnostic gate handles rectangular, floor-standing fixture objects only.
It is not registered as a general production mesh collision checker. It never
reads the injected truth. Detected affected groups != authorized changed groups.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path

from cityg.assets import AssetResolver, MaterialLibrary
from cityg.geometry import GeometryCompiler
from cityg.planning.prototypes import reference_registry
from cityg.planning.room_envelope import metric_envelope
from cityg.planning.room_metric_frame import restore_metric_object
from cityg.refinement.room import RoomProgramAgent
from cityg.refinement.room_preflight import prepare_preflight
from cityg.refinement.room_commit import commit_room_program
from cityg.schemas import Bounds2D
from cityg.serialization import load_city, save_json, to_primitive
from cityg.services.interfaces import ModelEndpoint
from cityg.services.openai_compatible import OpenAICompatibleService
from cityg.transactions import fingerprint
from cityg.validation.visual_grounding import room_facts, ground_review, resolution_proofs
from run_easy_visual_defects import resources, export_fixture, PROTOTYPE
from run_edit_method_pilot import RecordedService
from run_visual_input_ablation import target


def overlap_area(a,b):
    return max(0,min(a.max_x,b.max_x)-max(a.min_x,b.min_x))*max(0,min(a.max_y,b.max_y)-max(a.min_y,b.min_y))


def attribute(city,issue):
    b,f,r=target(city);env=metric_envelope(b,f,r);bb=env['bounds']
    objects={o.id:restore_metric_object(o,b,f,r,env) for o in f.objects if o.room_id==r.id}
    wanted=issue.get('object_ids',[])
    if not wanted or not set(wanted)<=objects.keys():return {'status':'unverified','reason':'missing_object_binding'}
    selected=[objects[k] for k in wanted];gids={o.metadata['group_key'] for o in selected}
    if not set(issue['group_ids'])<=gids:return {'status':'unverified','reason':'group_object_mismatch'}
    kind=issue['kind'];bad=[];evidence=[]
    if kind=='outside':
        bad=[o.metadata['group_key'] for o in selected if not bb.contains_bounds(o.bounds,tolerance=1e-5)]
    elif kind=='door_blocked':
        for door in env['floor'].doors:
            if r.id not in (door.room_a_id,door.room_b_id):continue
            # Scope deliberately restricted to south entries used in this lab.
            if abs(door.position.y-bb.min_y)>.01:continue
            approach=Bounds2D(door.position.x-door.width_m/2,bb.min_y,
                              door.position.x+door.width_m/2,bb.min_y+.8)
            for o in selected:
                area=overlap_area(o.bounds,approach)
                if area>.05:
                    bad.append(o.metadata['group_key']);evidence.append({'object_id':o.id,'door_id':door.id,'intersection_m2':area})
    elif kind=='overlap':
        for i,a in enumerate(selected):
            for other in selected[i+1:]:
                # Cabinet versus desk is a tall, floor-standing pair in these
                # fixtures. Do not generalize to chairs, supported clutter, etc.
                if {a.category,other.category}!={'bookcase','desk'}:continue
                area=overlap_area(a.bounds,other.bounds)
                if area>.15:
                    bad.extend([a.metadata['group_key'],other.metadata['group_key']])
                    evidence.append({'object_ids':[a.id,other.id],'intersection_m2':area})
    else:return {'status':'unverified','reason':'unsupported_diagnostic_kind'}
    if not bad or not set(issue['group_ids'])<=set(bad):
        return {'status':'not_supported','reason':'named_objects_do_not_cause_claimed_defect','evidence':evidence}
    facts=room_facts(city,r.id)
    failed_wall={c['group_id'] for c in facts['checks'] if c['kind']=='alignment' and c['ok'] is False}
    # Restrict editable groups to implicated groups with a violated accepted
    # wall contract. A correct desk participating in a collision stays frozen.
    editable=set(bad)&failed_wall
    return {'status':'confirmed','affected_groups':sorted(set(bad)),
            'editable_groups':sorted(editable),'evidence':evidence,
            'gate_scope':'fixture_rectangles_not_general_mesh_intersection'}


def run(source,results,output,case,seed,base_url,preserve_contract=False):
    root=output/case;root.mkdir(parents=True,exist_ok=False)
    city=load_city(source/case/'scene/city.json');b,f,r=target(city)
    original=fingerprint(city)
    diagnosis=json.loads((results/case/f'seed_{seed}'/'result.json').read_text())
    report={'case':case,'model_diagnosis':diagnosis,'source_unchanged':True,'ok':False}
    candidates=[(i,attribute(city,i)) for i in diagnosis.get('issues',[])]
    report['attribution']=[{'issue':i,'check':g} for i,g in candidates]
    eligible=[(i,g) for i,g in candidates if g['status']=='confirmed' and g.get('editable_groups')]
    if not eligible:
        report['status']='no_verified_edit_candidate';save_json(report,root/'result.json');return report
    issue,gateproof=eligible[0]
    changed=gateproof['editable_groups']
    # Retain VLM wording; route the independently confirmed accepted-wall
    # violation via the existing production-compatible issue contract.
    feedback={'entity_id':r.id,'category':'room','issue_code':'room_group_misaligned',
        'description':issue['description'],'suggested_action':issue['suggested_action'],
        'target_group_ids':changed,'confidence':issue['confidence'],'binding_confidence':1.,
        'binding_basis':'view_context','diagnostic_original_kind':issue['kind'],
        'object_attribution':gateproof}
    if preserve_contract:
        feedback['immutable_placement_requirements']={g['id']:g.get('placement',{})
            for g in r.metadata['room_design']['groups']}
        feedback['repair_policy']=('Correct the current realized pose, not the accepted design. '
            'Preserve each original required wall, contact side and maximum gap. Do not switch '
            'east to west even if the new location is otherwise traversable. Other groups are frozen.')
    grounded=ground_review(city,{'aggregated_issues':[feedback]})
    if not grounded['aggregated_issues'][0].get('automatic_repair_allowed'):raise ValueError('Alignment gate rejected')
    library,registry=resources();pinned=reference_registry(registry,library.materialize(PROTOTYPE))
    resolver=AssetResolver(pinned,(),max_provider_calls=0)
    compiler=GeometryCompiler(asset_registry=registry,material_library=MaterialLibrary(
        'assets/incoming/interior_materials/material_library.json'))
    service=RecordedService(OpenAICompatibleService(ModelEndpoint(base_url=base_url,model='cityg-llm',
        timeout_s=180,max_tokens=4096,seed=seed,enable_thinking=False)),root/'calls.json')
    try:
        support,preflight,gate=prepare_preflight(city,r.id,compiler,pinned,seed=17)
        if preserve_contract:
            original_preflight=preflight
            def preflight(program):
                from cityg.planning.room_constraints import placement_policy
                new={g['id']:g for g in to_primitive(program.design)['groups']}
                for old in r.metadata['room_design']['groups']:
                    a=placement_policy(old);v=placement_policy(new[old['id']])
                    if any(v.get(k)!=a.get(k) for k in ('mode','wall','contact')) or v['max_gap_m']>a['max_gap_m']+1e-6:
                        raise ValueError('Repair must preserve original placement contract for '+old['id']+': '+str(a))
                return original_preflight(program)
        proposal=RoomProgramAgent(service,asset_resolver=resolver,max_attempts=3,
            review_sufficiency=False).propose(city,b,f,r,use_cache=False,
                visual_feedback={**feedback,'compiled_support_context':support},compiled_preflight=preflight)
        save_json(proposal.program,root/'proposal.json')
        committed,stats=commit_room_program(city,r.id,proposal.program,asset_resolver=resolver,
            seed=17,compiled_gate=gate,source='visual_repair')
        proof=resolution_proofs(city,committed.city,grounded)
        facts=room_facts(committed.city,r.id,reference=room_facts(city,r.id))
        untouched=lambda c:[o for bb in c.iter_buildings() for ff in bb.floors for o in ff.objects
            if o.room_id==r.id and o.metadata.get('group_key') not in changed]
        after_attribute=attribute(committed.city,issue)
        report.update(status=committed.report['status'],transaction=committed.report,
            original_defect_after=after_attribute,proofs=proof,after_facts=facts,
            editable_groups=changed,unedited_groups_unchanged=untouched(city)==untouched(committed.city),
            source_unchanged=original==fingerprint(city))
        report['ok']=(report['status']=='accepted' and bool(proof) and all(p['ok'] for p in proof.values())
            and after_attribute['status']=='not_supported' and report['source_unchanged']
            and report['unedited_groups_unchanged'] and not any(c['ok'] is False for c in facts['checks']))
        export_fixture(committed.city,compiler,root/'scene')
        save_json(json.loads((source/case/'render_plan.json').read_text()),root/'render_plan.json')
    except Exception as error:report['error']=f'{type(error).__name__}: {error}'
    report['model_calls']=len(service.calls)
    report['tokens']=sum(c.get('completion',{}).get('usage',{}).get('total_tokens',0) for c in service.calls)
    report['preserve_contract']=preserve_contract
    report['publish_allowed']=report['ok']
    save_json(report,root/'result.json');print(case,'repair',report['ok'],report.get('error',''),flush=True)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,default=Path('analysis_results/easy_visual_defects_20261023'))
    p.add_argument('--results',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--seed',type=int,default=7321)
    p.add_argument('--base-url',default='http://127.0.0.1:8000/v1')
    p.add_argument('--preserve-contract',action='store_true')
    args=p.parse_args()
    cases=[r['case_id'] for r in json.loads((args.source/'protocol.json').read_text())['cases']]
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs=[pool.submit(run,args.source,args.results,args.output,case,args.seed,args.base_url,args.preserve_contract) for case in cases]
        results=[j.result() for j in jobs]
    save_json(results,args.output/'results.json')


if __name__=='__main__':main()
