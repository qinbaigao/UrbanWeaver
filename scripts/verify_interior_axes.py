"""Replay frozen upstream planning through cardinal-entry interior agents.

No upstream LLM resampling: keep the failed urban/building/global-floor program,
reserve supported interiors and call the actual local Floor/Room agents. This
focused replay is not a replacement for a subsequent ordinary main-script run.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from cityg.agents.building_floor import BuildingFloorAgent
from cityg.agents.room_reference import RoomReferenceAgent
from cityg.assets import AssetRegistry
from cityg.geometry import GeometryCompiler, GeometryValidator
from cityg.planning.generation_prototypes import GenerationPrototypes,load_options,DeferredFurniture
from cityg.planning.interior_capability import reserve_interiors
from cityg.planning.interior_capacity_search import improve_reserved_capacity
from cityg.planning.programmed import ProgrammedCityPlanner
from cityg.planning.programs import HierarchicalProgram,UrbanProgram,BuildingProgram,FloorProgram,SkylineProgram
from cityg.run_provenance import record_stage_start
from cityg.schemas import CitySpec
from cityg.serialization import save_json
from cityg.services import OpenAICompatibleService
from cityg.services.interfaces import ModelEndpoint


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('run',type=Path);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    if args.output.exists(): p.error('Use a fresh output directory')
    paths=[args.run/'requirement/requested_spec.json',args.run/'programs/hierarchical_program.json']
    hashes={str(q):hashlib.sha256(q.read_bytes()).hexdigest() for q in paths}
    spec=CitySpec.from_dict(json.loads(paths[0].read_text()))
    raw=json.loads(paths[1].read_text())
    program=HierarchicalProgram(UrbanProgram.from_dict(raw['urban']),BuildingProgram.from_dict(raw['building']),
        FloorProgram.from_dict(raw['floor']),SkylineProgram.from_dict(raw['skyline']))
    runtime=GenerationPrototypes(load_options('configs/reliability_prototypes.json'))
    draft=ProgrammedCityPlanner(program,floor_detail_agent=DeferredFurniture()).plan(spec)
    targets,pins,reservation=reserve_interiors(draft,limit=2,room_library=runtime.floors.room_library,
        corridor_ratios={q.function:q.corridor_ratio for q in program.floor.profiles})
    targets,capacity=improve_reserved_capacity(program,spec,targets,pins,runtime.floors.room_library)
    reservation.update(target_buildings=targets,capacity_search=capacity)
    record_stage_start(args.output);save_json(reservation,args.output/'reservation.json')
    if len(targets)!=2: raise ValueError('Frozen test expects two supported buildings')
    def instantiate(overrides=None):
        city=ProgrammedCityPlanner(program,floor_detail_agent=DeferredFurniture(),interior_targets=targets,
            archetype_pins=pins,floor_program_overrides=overrides).plan(spec)
        city.metadata['interior_capability_reservation']=reservation
        runtime.select_scope(city,building_limit=2,floor_limit=2)
        return city
    rough=instantiate()
    service=OpenAICompatibleService(ModelEndpoint('http://127.0.0.1:8000/v1','cityg-llm',
        timeout_s=180,max_tokens=6144,seed=spec.seed))
    selection=json.loads((args.run/'programs/prototype_selection.json').read_text())
    planned=BuildingFloorAgent(service,max_calls=4).plan_city(rough,
        {p.function:p for p in program.floor.profiles},spec,prototype_context=runtime.floor_context(selection))
    save_json(planned.trace_dict(),args.output/'floor_trace.json')
    save_json(planned.program_dict(),args.output/'floor_programs.json')
    if set(planned.overrides)!=set(targets): raise ValueError('Local Floor Agent fell back; retain trace')
    city=instantiate(planned.overrides)
    before={b.id:deepcopy((b.footprint,b.entrance,b.vertical_connectors)) for b in rough.iter_buildings()}
    protected=all(before[b.id]==(b.footprint,b.entrance,b.vertical_connectors) for b in city.iter_buildings())
    save_json(city,args.output/'unfurnished_city.json')
    registry=AssetRegistry('assets/asset_registry.json');compiler=GeometryCompiler(asset_registry=registry)
    registry=runtime.prepare_resources(registry,compiler)
    requirement=json.loads((args.run/'run.json').read_text())['requirement']
    def selector(candidate,candidates,library,options):
        report,_=RoomReferenceAgent(service,max_calls=2).plan(candidate,candidates,library,requirement,options)
        save_json(report,args.output/'room_reference_trace.json')
        return report
    furnished,adaptation=runtime.populate(city,registry,compiler,building_limit=2,floor_limit=2,
        reference_selector=selector)
    save_json(adaptation,args.output/'prototype_adaptation.json')
    save_json(furnished,args.output/'city.json')
    validation=GeometryValidator().validate(furnished,compiler.compile(furnished))
    save_json(validation.to_dict(),args.output/'geometry_validation.json')
    unchanged=all(hashlib.sha256(Path(q).read_bytes()).hexdigest()==h for q,h in hashes.items())
    report={'ok':protected and unchanged and validation.ok and adaptation['summary']['accepted_rooms']==4,
        'source_hashes':hashes,'source_unchanged':unchanged,'protected_geometry_unchanged':protected,
        'floor_agent_calls':len(planned.attempts),'floor_agent_fallbacks':planned.failed_buildings,
        'targets':targets,'room_summary':adaptation['summary'],
        'full_main_script_tested':False,'renderer_tested':False}
    save_json(report,args.output/'report.json');print(json.dumps(report,ensure_ascii=False),flush=True)
    return 0 if report['ok'] else 3


if __name__=='__main__': raise SystemExit(main())
