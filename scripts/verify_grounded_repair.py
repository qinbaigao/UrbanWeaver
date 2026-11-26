"""Real Room Agent on a controlled orientation defect; original scene immutable.

This is not a VLM detection benchmark: the injected defect is explicitly bound.
It tests geometry confirmation, compiled preflight, transaction and independent
before/after proof without downloading assets or copying a full Viewer.
"""
import argparse
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path

from cityg.adaptive_review import _review_asset_registry
from cityg.assets import AssetResolver,MaterialLibrary
from cityg.geometry import GeometryCompiler
from cityg.refinement.room import RoomProgramAgent
from cityg.refinement.room_commit import commit_room_program
from cityg.refinement.room_preflight import prepare_preflight
from cityg.validation.visual_grounding import ground_review,resolution_proofs,room_facts
from cityg.run_provenance import record_stage_start
from cityg.serialization import load_city,save_json
from cityg.services import OpenAICompatibleService
from cityg.services.interfaces import ModelEndpoint
from cityg.transactions import fingerprint


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run',type=Path);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists(): parser.error('Use a fresh directory; preserve failed evidence')
    root=args.run/'visual_review'
    original=json.loads((root/'adaptive_review_report.json').read_text())
    source=load_city(original['city_refined']);source_hash=fingerprint(source)
    city=deepcopy(source)
    room=next(r for r in city.iter_rooms() if r.function=='bedroom' and r.metadata.get('room_design'))
    b,f,r=next((b,f,r) for b in city.iter_buildings() for f in b.floors for r in f.rooms if r.id==room.id)
    obj=next(o for o in f.objects if o.room_id==r.id and o.metadata.get('group_key')=='storage'
             and o.id==o.metadata.get('group_anchor_id'))
    if not room_facts(source,r.id)['supported']: parser.error('Unsupported source fixture')
    obj.rotation_deg=(obj.rotation_deg+180)%360
    # Controlled *compiled* pose defect, not a stale pose-binding corruption.
    # Only this detached fixture is rebased; production guards remain intact.
    binding=obj.metadata.get('metric_room_placement',{}).get('canonical_binding')
    if binding is not None: binding[5]=obj.rotation_deg
    issue={'issue_id':'controlled_wrong_facing','entity_id':r.id,'entity_type':'room',
        'category':'room','issue_code':'room_group_misaligned','target_group_ids':['storage'],
        'description':'Controlled defect: storage anchor was rotated 180 degrees away from its accepted wall binding.',
        'suggested_action':'Restore the storage group accepted wall/back contact, retaining all other groups and surface items.',
        'confidence':1.,'binding_confidence':1.,'automatic_repair_allowed':True}
    review=ground_review(city,{'aggregated_issues':[issue]})
    record_stage_start(args.output);save_json(city,args.output/'defective_city.json')
    save_json(review,args.output/'grounding_before.json')
    report={'mode':'controlled_defect_real_room_agent','vlm_detection_tested':False,
        'original_source_hash':source_hash,'ok':False}
    try:
        if not review['aggregated_issues'][0]['automatic_repair_allowed']:
            raise ValueError('Controlled defect not independently confirmed')
        package=Path(original['openusd_after']);registry=_review_asset_registry(package)
        compiler=GeometryCompiler(asset_registry=registry,
            material_library=MaterialLibrary(package/'assets/material_library.json'),
            facade_asset_index_path=original.get('facade_asset_index'))
        context,preflight,gate=prepare_preflight(city,r.id,compiler,registry)
        service=OpenAICompatibleService(ModelEndpoint('http://127.0.0.1:8000/v1','cityg-llm',
            timeout_s=180,max_tokens=8192,seed=202))
        resolver=AssetResolver(registry,(),max_provider_calls=0)
        agent=RoomProgramAgent(service,max_attempts=3,asset_resolver=resolver,placement_seed=202)
        proposal=agent.propose(city,b,f,r,use_cache=False,compiled_preflight=preflight,
            visual_feedback={'issues':review['aggregated_issues'],'target_group_ids':['storage'],
                             'compiled_support_context':context})
        save_json([asdict(a) for a in proposal.attempts],args.output/'agent_attempts.json')
        accepted,stats=commit_room_program(city,r.id,proposal.program,asset_resolver=resolver,
            seed=202,compiled_gate=gate)
        proofs=resolution_proofs(city,accepted.city,review)
        save_json(accepted.city,args.output/'candidate_city.json')
        report.update(transaction=accepted.report,stats=stats,proofs=proofs,
            model_calls=len(proposal.attempts),asset_stats=resolver.stats(),
            ok=bool(proofs) and all(p['ok'] for p in proofs.values()))
    except Exception as error:
        report.update(error=f'{type(error).__name__}: {error}',
                      attempts=[asdict(a) for a in getattr(error,'attempts',())])
    report['source_unchanged']=source_hash==fingerprint(source)
    report['ok'] &= report['source_unchanged']
    save_json(report,args.output/'report.json')
    print({k:report.get(k) for k in ('ok','model_calls','source_unchanged','error')},flush=True)
    return 0 if report['ok'] else 3


if __name__=='__main__': raise SystemExit(main())
