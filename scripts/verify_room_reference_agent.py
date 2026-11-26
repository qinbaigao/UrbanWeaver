"""Real Room Reference Agent and compiled placement check, without full export.

Default fixture covers residential, office, retail and public reception rooms.
--source accepts an unfurnished city checkpoint for a separate integration replay.
"""
import argparse
import json
from dataclasses import asdict
from pathlib import Path

from cityg.agents.room_reference import RoomReferenceAgent
from cityg.agents.requirement import AgentGenerationError
from cityg.assets import AssetRegistry
from cityg.ccwp import build_world_program
from cityg.geometry import GeometryCompiler
from cityg.planning.city_prototype_adapter import adapt_city_rooms
from cityg.planning.generation_prototypes import GenerationPrototypes, load_options
from cityg.planning.prototype_lab import make_lab
from cityg.run_provenance import record_stage_start
from cityg.serialization import load_city, save_json
from cityg.services.interfaces import ModelEndpoint
from cityg.services.openai_compatible import OpenAICompatibleService
from cityg.transactions import fingerprint


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--source',type=Path)
    parser.add_argument('--design-variation',action='store_true',
                        help='Exercise quoted shared goals and bounded semantic reference adjustments')
    parser.add_argument('--instruction',help='Override fixture requirement without changing target budgets')
    parser.add_argument('--fixture-cases',type=Path,
                        help='Optional reference-compatible dimensions for the laboratory rooms')
    args=parser.parse_args()
    if args.output.exists(): parser.error('Use a new output directory')
    if args.source and args.fixture_cases: parser.error('Fixture dimensions cannot alter a source city')
    runtime=GenerationPrototypes(load_options('configs/generation_prototypes.json'))
    if args.source:
        city=load_city(args.source)
        options=runtime.options['adaptation']
        targets=runtime.select_scope(city)['building_levels']
        requirement='保留现有建筑和楼层，在授权范围精细设计10个房间，尽量覆盖住宅、办公、商业与公共服务功能。'
    else:
        city,targets=make_lab(runtime.floors.room_library,
            ['living_media_v1','office_private_v1','retail_books_v1','reception_waiting_v1'],
            json.loads(args.fixture_cases.read_text()) if args.fixture_cases else None)
        for b,fn in zip(city.iter_buildings(),['residential','commercial','commercial','public_service']):
            b.function=fn
        targets={b.id:[0] for b in city.iter_buildings()}
        options={'max_buildings':4,'max_floors_per_building':1,'max_rooms':4,'max_attempts':16,'variation_limit':.2}
        requirement='分别精细陈设客厅、独立办公室、书店、公共服务接待室，共4个房间。保持必需家具完整，适当增加座椅周围间距。'
    if args.instruction: requirement=args.instruction
    if args.design_variation:
        options={**options,'design_variation':runtime.options['adaptation']['design_variation']}
    if any(city.iter_objects()): parser.error('Source must be unfurnished; existing inventory is never cleared')
    city.world_program=build_world_program(city,producer='room_reference_acceptance',seed=17)
    record_stage_start(args.output)
    compiler=GeometryCompiler(asset_registry=AssetRegistry('assets/asset_registry.json'))
    registry=runtime.prepare_resources(compiler.asset_registry,compiler)
    service=OpenAICompatibleService(ModelEndpoint(
        'http://127.0.0.1:8000/v1','cityg-llm',max_tokens=6144,timeout_s=180,seed=17))
    if args.design_variation:
        from cityg.design_goals import extract_goals
        goals,_=extract_goals(service,requirement)
        city.metadata['design_goals']=goals['goals']
        save_json(goals,args.output/'design_goals.json')
    before=fingerprint(city)
    agent=RoomReferenceAgent(service)
    def selector(candidate,candidates,library,opt):
        try:
            report,_=agent.plan(candidate,candidates,library,requirement,opt)
        except AgentGenerationError as error:
            save_json({'status':'failed','error':str(error),
                       'attempts':[asdict(a) for a in error.attempts]},
                      args.output/'room_reference_selection.json')
            raise
        save_json(report,args.output/'room_reference_selection.json')
        return report
    result,report=adapt_city_rooms(city,runtime.floors,registry,compiler,options,
        reference_selector=selector,target_levels=targets,progress=lambda *a:print(a,flush=True))
    save_json(result,args.output/'city.json')
    save_json(report,args.output/'prototype_report.json')
    groups=report['summary']['functional_coverage']
    audit={'source_unchanged':before==fingerprint(city),'room_count':report['summary']['accepted_rooms'],
        'target':options['max_rooms'],'coverage':groups,
        'compiled_rooms_verified':all(r['compiled_verified'] for r in report['rooms']),
        'agent_choices_applied':sum(r['selection_source'].startswith('agent_') for r in report['rooms']),
        'personalized_rooms':sum(r.get('design_changed',False) for r in report['rooms']),
        'spacing_adjusted_rooms':sum(any(p['gap_scale']!=1 for p in r['spacing_adjustments']) for r in report['rooms']),
        'design_adjustments_applied':sum(r.get('design_changed',False) and any(r.get('design_adjustments',{}).values()) for r in report['rooms']),
        'goals_cited':sorted({g for r in report['rooms'] for g in r.get('goal_ids',[])}),
        'scope':'actual_llm_and_compiled_room_transactions_no_full_export',
        'fixture':not bool(args.source)}
    audit['ok']=(audit['source_unchanged'] and audit['room_count']==audit['target'] and
        audit['compiled_rooms_verified'] and audit['agent_choices_applied']==audit['target'] and
        (bool(args.source) or set(groups)=={'residential','office','commercial','public_service'}))
    save_json(audit,args.output/'audit.json'); print(audit,flush=True)
    return 0 if audit['ok'] else 3


if __name__=='__main__': raise SystemExit(main())
