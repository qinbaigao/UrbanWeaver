"""Replay one bound VLM room complaint through real Room Agent and compiled gates.

Source scene is immutable. This is a local proposal test, not a new city run or
proof that a visual complaint is true/resolved. No asset generation or rendering.
"""
import argparse
from dataclasses import asdict
import json
from pathlib import Path

from cityg.adaptive_review import _review_asset_registry
from cityg.assets import AssetResolver, MaterialLibrary
from cityg.geometry import GeometryCompiler
from cityg.refinement.room import RoomProgramAgent
from cityg.refinement.room_commit import commit_room_program, negotiate_room_program
from cityg.run_provenance import record_stage_start
from cityg.serialization import load_city, save_json
from cityg.services.interfaces import ModelEndpoint
from cityg.services.openai_compatible import OpenAICompatibleService
from cityg.transactions import fingerprint
from cityg.validation.local_room import room_compilation_gate


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('run',type=Path);p.add_argument('--room-id',required=True)
    p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    if args.output.exists(): p.error('Use a fresh output directory')
    root=args.run/'visual_review';review=json.loads((root/'adaptive_review_report.json').read_text())
    city=load_city(review['city_refined']);source_hash=fingerprint(city)
    package=Path(review['openusd_after']);registry=_review_asset_registry(package)
    resolver=AssetResolver(registry,(),max_provider_calls=0)
    compiler=GeometryCompiler(asset_registry=registry,
        material_library=MaterialLibrary(package/'assets/material_library.json'))
    b,f,r=next((b,f,r) for b in city.iter_buildings() for f in b.floors for r in f.rooms if r.id==args.room_id)
    issues=[i for i in review['review']['aggregated_issues'] if i.get('entity_id')==r.id]
    if not issues: p.error('No original VLM complaint for this room')
    feedback={'issues':issues}
    if all(i.get('target_group_ids') for i in issues):
        feedback['target_group_ids']=sorted({g for i in issues for g in i['target_group_ids']})
    record_stage_start(args.output)
    service=OpenAICompatibleService(ModelEndpoint('http://127.0.0.1:8000/v1','cityg-llm',
        timeout_s=180,max_tokens=6144,seed=17))
    agent=RoomProgramAgent(service,max_attempts=2,asset_resolver=resolver,placement_seed=17)
    report={'mode':'real_room_feedback_local_replay','room_id':r.id,'visual_feedback':feedback,
            'visual_issue_resolution_proven':False,'ok':False,'source_fingerprint':source_hash}
    try:
        proposal=agent.propose(city,b,f,r,use_cache=False,visual_feedback=feedback)
        report['initial_proposal']=proposal.raw;report['attempts']=[asdict(a) for a in proposal.attempts]
        try:
            accepted,stats=commit_room_program(city,r.id,proposal.program,asset_resolver=resolver,
                compiled_gate=room_compilation_gate(city,r.id,compiler))
            report.update(status=accepted.report['status'],transaction=accepted.report,stats=stats,ok=True)
            save_json(accepted.city,args.output/'candidate_city.json')
        except (ValueError,RuntimeError) as error:
            report['initial_compile_error']=str(error)
            def revised(draft,conflict):
                retry=RoomProgramAgent(service,max_attempts=1,asset_resolver=resolver)
                result=retry.propose(draft,b,f,r,use_cache=False,
                    visual_feedback={**feedback,'compiled_conflict':conflict})
                report['retry_attempts']=[asdict(a) for a in result.attempts]
                return result.program
            candidate,negotiation,stats=negotiate_room_program(city,r.id,revised,
                failure=str(error),asset_resolver=resolver,compiled_gate=room_compilation_gate(city,r.id,compiler))
            report.update(negotiation=negotiation,stats=stats,status=negotiation['status'],
                          ok=negotiation['status']=='resolved')
            save_json(candidate,args.output/'candidate_city.json')
    except Exception as error:
        report.update(status='rejected',error=f'{type(error).__name__}: {error}',
                      failed_attempts=[asdict(a) for a in getattr(error,'attempts',())])
    report['source_unchanged']=source_hash==fingerprint(city)
    report['ok'] &= report['source_unchanged']
    save_json(report,args.output/'report.json')
    print({k:report.get(k) for k in ('ok','status','source_unchanged','error')},flush=True)
    return 0 if report['ok'] else 3


if __name__=='__main__': raise SystemExit(main())
