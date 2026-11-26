"""Small live acceptance of production review -> grounding -> guarded commit.

Reuses frozen renders and shared assets; never publishes into source scenes.
Private injection labels are not supplied to any model or production gate.
"""
import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path

from cityg.adaptive_review import aggregate_visual_reviews, _render_plan, _start_server
from cityg.assets import AssetResolver, MaterialLibrary
from cityg.geometry import GeometryCompiler
from cityg.planning.prototypes import reference_registry
from cityg.refinement.room import RoomProgramAgent
from cityg.refinement.room_commit import commit_room_program
from cityg.refinement.room_preflight import prepare_preflight
from cityg.refinement.room_repair_guard import RoomRepairGuard
from cityg.serialization import load_city, save_json
from cityg.services.interfaces import ModelEndpoint
from cityg.services.openai_compatible import OpenAICompatibleService
from cityg.transactions import fingerprint
from cityg.validation.visual_grounding import ground_review, resolution_proofs
from cityg.visual_review import VisualReviewAgent
from run_edit_method_pilot import RecordedService
from run_easy_visual_defects import resources, export_fixture, PROTOTYPE
from run_visual_input_ablation import target, production_plan


def run_case(source, output, case, base_url):
    root=output/case;root.mkdir(parents=True,exist_ok=False)
    fixture=source/case
    city=load_city(fixture/'scene/city.json');original=fingerprint(city)
    b,f,r=target(city)
    service=RecordedService(OpenAICompatibleService(ModelEndpoint(base_url=base_url,
        model='cityg-llm',timeout_s=180,max_tokens=4096,seed=7321,enable_thinking=False)),root/'calls.json')
    report={'case':case,'status':'failed','source_unchanged':False,'published':False}
    try:
        before=aggregate_visual_reviews(production_plan(city,fixture),fixture/'images',
            VisualReviewAgent(service,max_images=2,max_attempts=2),scene_id=city.id,batch_size=2)
        grounded=ground_review(city,before)
        save_json(grounded,root/'review_before.json')
        issues=[i for i in grounded['aggregated_issues'] if i.get('automatic_repair_allowed')]
        report.update(reported_issues=len(grounded['aggregated_issues']),verified_issues=len(issues),
                      rejected_suggestions=len(grounded['aggregated_issues'])-len(issues))
        if before.get('available_batches')!=before.get('batch_count'):
            raise ValueError('Review unavailable; cannot treat it as a clean result')
        if not issues:
            report['status']='no_verified_edit'
        else:
            guard=RoomRepairGuard(city,r.id,issues)
            library,registry=resources()
            pinned=reference_registry(registry,library.materialize(PROTOTYPE))
            compiler=GeometryCompiler(asset_registry=pinned,material_library=MaterialLibrary(
                'assets/incoming/interior_materials/material_library.json'))
            resolver=AssetResolver(pinned,(),max_provider_calls=0)
            support,preflight,gate=prepare_preflight(city,r.id,compiler,pinned,repair_guard=guard)
            proposal=RoomProgramAgent(service,model_id='cityg-llm',max_attempts=2,
                asset_resolver=resolver,placement_seed=17).propose(city,b,f,r,use_cache=False,
                visual_feedback={'issues':issues,**guard.feedback(),'compiled_support_context':support},
                compiled_preflight=preflight)
            save_json(proposal.program,root/'proposal.json')
            committed,stats=commit_room_program(city,r.id,proposal.program,
                asset_resolver=resolver,compiled_gate=gate,seed=17)
            report.update(transaction=committed.report,stats=stats,guard=guard(committed.city),
                          proofs=resolution_proofs(city,committed.city,grounded))
            if committed.report['status']!='accepted' or not report['guard']['ok']:
                raise ValueError('Candidate retained as rejected; source untouched')
            # Export only after real production gates accept the detached result.
            export_fixture(committed.city,compiler,root/'scene')
            save_json(json.loads((fixture/'render_plan.json').read_text()),root/'render_plan.json')
            plan=production_plan(committed.city,root)
            server,thread,url=_start_server(root/'scene',0)
            try:asyncio.run(_render_plan(url,plan,root/'images',asset_timeout_ms=180000))
            finally:server.shutdown();server.server_close();thread.join(timeout=5)
            after=aggregate_visual_reviews(plan,root/'images',VisualReviewAgent(service,max_images=2),
                                          scene_id=city.id,batch_size=2)
            save_json(ground_review(committed.city,after),root/'review_after.json')
            report.update(status='accepted_and_rechecked',published=True,
                after_available=after.get('available_batches')==after.get('batch_count'),
                after_reported_issues=len(after.get('aggregated_issues',[])))
    except Exception as error:
        report['error']=f'{type(error).__name__}: {error}'
    report.update(source_unchanged=fingerprint(city)==original,model_calls=len(service.calls),
        tokens=sum(c.get('completion',{}).get('usage',{}).get('total_tokens',0) for c in service.calls))
    save_json(report,root/'result.json')
    print(case,report['status'],report.get('error',''),flush=True)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,default=Path('analysis_results/easy_visual_defects_20261023'))
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--base-url',default='http://127.0.0.1:8000/v1')
    p.add_argument('--cases',nargs='+',default=['case_01','case_02','case_03','case_04'])
    p.add_argument('--full-workflow',action='store_true',help='Exercise adaptive-review orchestration on case_02')
    args=p.parse_args()
    if args.full_workflow:
        from cityg.adaptive_review import run_adaptive_review
        city=load_city(args.source/'case_02/scene/city.json')
        library,registry=resources()
        pinned=reference_registry(registry,library.materialize(PROTOTYPE))
        compiler=GeometryCompiler(asset_registry=pinned,material_library=MaterialLibrary(
            'assets/incoming/interior_materials/material_library.json'))
        package=args.output/'input'
        if args.output.exists():raise ValueError('Use a new output directory')
        export_fixture(city,compiler,package)
        report=run_adaptive_review(package,args.output/'review',base_url=args.base_url,
            model='cityg-llm',max_tokens=4096,max_views=8,max_room_refinements=1,
            max_room_layout_refinements=1,max_building_refinements=0,max_streetscape_refinements=0,
            viewer_port=0)
        print('Full workflow:',report.get('status',report.get('bounded_outcome')),flush=True)
        return
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs=[pool.submit(run_case,args.source.resolve(),args.output.resolve(),c,args.base_url) for c in args.cases]
        results=[job.result() for job in jobs]
    save_json(results,args.output/'results.json')


if __name__=='__main__':main()
