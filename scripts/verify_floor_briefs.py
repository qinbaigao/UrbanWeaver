"""Read-only replay of actual failed buildings through the semantic Floor Agent."""
import argparse
import hashlib
import json
from pathlib import Path
from copy import deepcopy
from dataclasses import asdict

from cityg.agents.building_floor import BuildingFloorAgent
from cityg.agents.requirement import AgentGenerationError
from cityg.planning.floor_brief import geometry_summary, interior_capability
from cityg.planning.generation_prototypes import GenerationPrototypes, load_options
from cityg.planning.programs import FloorProfile
from cityg.run_provenance import record_stage_start
from cityg.schemas import CitySpec
from cityg.serialization import load_city, save_json
from cityg.services.interfaces import ModelEndpoint
from cityg.services.openai_compatible import OpenAICompatibleService


def realize_profile(city, building_id, profile, spec):
    """Exercise the production floor builder and geometry compiler, without export.

    Work on a detached scene; this is not a substitute for main-script acceptance.
    """
    from cityg.planning.programmed import ProgrammedCityPlanner
    from cityg.planning.programs import HierarchicalProgram, UrbanProgram, BuildingProgram, FloorProgram, SkylineProgram
    from cityg.schemas import Bounds2D
    from cityg.ccwp import build_world_program
    candidate = deepcopy(city)
    building = next(b for b in candidate.iter_buildings() if b.id == building_id)
    protected = deepcopy((building.footprint, building.entrance, building.vertical_connectors))
    geometry = geometry_summary(building, profile)
    raw = city.metadata['hierarchical_program']
    planner = ProgrammedCityPlanner(HierarchicalProgram(
        UrbanProgram.from_dict(raw['urban']), BuildingProgram.from_dict(raw['building']),
        FloorProgram.from_dict(raw['floor']), SkylineProgram.from_dict(raw['skyline']) if raw.get('skyline') else None))
    realized = []
    for floor in building.floors:
        zone = profile.zone_for_level(floor.level)
        archetype = zone.archetype
        new = planner._make_programmed_floor(building.id, floor.level, building.footprint,
            profile.corridor_ratio, archetype.room_function_cycle, archetype.preferred_room_count,
            building.entrance, building_function=building.function, program_role=zone.role,
            archetype=archetype, core_bounds=Bounds2D(**geometry['core']),
            circulation_axis=geometry.get('circulation_axis','x'),
            vertical_zone={k:asdict(zone)[k] for k in ('zone_id','start_level','end_level','role','use_type')},
            floor_plate_contract={'spatial_footprint_supported':True,
                'fixed_room_count':spec.rooms_per_floor if spec.room_count_strategy=='fixed' else None,
                'bounds':asdict(building.footprint)})
        if new.metadata.get('spatial_layout', {}).get('status') != 'accepted':
            raise ValueError(f'Production floor builder fell back at {floor.id}')
        realized.append(new)
    building.floors = realized
    candidate.world_program = build_world_program(candidate, producer='floor_brief_acceptance', seed=spec.seed)
    if protected != (building.footprint, building.entrance, building.vertical_connectors):
        raise ValueError('Protected building geometry changed')
    return candidate


def audit_realization(city, building_id, profile, spec):
    from cityg.geometry.compiler import GeometryCompiler
    candidate = realize_profile(city, building_id, profile, spec)
    building = next(b for b in candidate.iter_buildings() if b.id == building_id)
    realized = building.floors
    scene = GeometryCompiler().compile(candidate, building_ids={building_id})
    return {'production_floor_builder_passed':True, 'geometry_compiled':True,
        'protected_geometry_unchanged':True, 'floor_count':len(realized),
        'room_counts':[sum(r.function != 'corridor' for r in f.rooms) for f in realized],
        'primitive_count':len(scene.primitives), 'full_export_tested':False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('run', type=Path); p.add_argument('--output', type=Path, required=True)
    p.add_argument('--base-url', default='http://127.0.0.1:8000/v1')
    p.add_argument('--model', default='cityg-llm'); p.add_argument('--max-calls', type=int, default=4)
    p.add_argument('--prototype-config',type=Path,default=Path('configs/generation_prototypes.json'))
    args = p.parse_args()
    if args.output.exists(): p.error('Output must be new')
    source = args.run/'checkpoints/unfurnished_city.json'
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    city = load_city(source)
    ledger = json.loads((args.run/'final/reports/requirement_acceptance.json').read_text())
    spec = CitySpec.from_dict(ledger['parsed_spec'])
    profiles = {r['function']:FloorProfile.from_dict(r) for r in
        json.loads((args.run/'programs/floor_program.json').read_text())['profiles']}
    conflicts = json.loads((args.run/'programs/planning_conflicts.json').read_text())
    targets = {row['entity_id'] for row in conflicts if row['stage']=='building_specific_floor'}
    old_trace = json.loads((args.run/'programs/building_floor_trace.json').read_text())
    record_stage_start(args.output)
    service = OpenAICompatibleService(ModelEndpoint(args.base_url, args.model,
        timeout_s=180, max_tokens=6144, seed=17))
    agent = BuildingFloorAgent(service, model_id=args.model, max_calls=args.max_calls)
    runtime = GenerationPrototypes(load_options(args.prototype_config))
    selection = json.loads((args.run/'programs/prototype_selection.json').read_text())
    # Selection files can include the selected record beside its attempts.
    if 'prototype_id' not in selection: selection = selection.get('selection', selection)
    rows = []
    for building in city.iter_buildings():
        if building.id not in targets: continue
        base = profiles[building.function]
        save_json({'building':building, 'base_profile':base, 'spec':spec,
                   'geometry':geometry_summary(building, base),
                   'capability':interior_capability(building),
                   'previous_conflicts':[r for r in conflicts if r['entity_id']==building.id],
                   'previous_trace':old_trace}, args.output/'fixtures'/f'{building.id}.json')
        try:
            result = agent.plan(building, base, spec, prototype_context=runtime.floor_context(selection))
            save_json(result.trace_dict(), args.output/f'{building.id}_trace.json')
            realization = audit_realization(city, building.id, result.program.profile, spec)
            rows.append({'building_id':building.id,'accepted':True,'fallback_used':False,
                'calls':len(result.attempts),'first_attempt_pass':len(result.attempts)==1,
                'corridor_ratio_preserved':result.program.profile.corridor_ratio==base.corridor_ratio,
                'realization':realization})
        except AgentGenerationError as error:
            save_json({'error':str(error),'attempts':error.attempts},args.output/f'{building.id}_trace.json')
            rows.append({'building_id':building.id,'accepted':False,'calls':len(error.attempts),
                'error':error.attempts[-1].error if error.attempts else str(error)})
        print(rows[-1], flush=True)
        save_json({'targets':sorted(targets),'results':rows,'complete':len(rows)==len(targets),
            'ok':len(rows)==len(targets) and all(r['accepted'] for r in rows),
            'source_unchanged':hashlib.sha256(source.read_bytes()).hexdigest()==digest,
            'source_sha256':digest,'scope':'real_llm_floor_planning_no_full_export'},args.output/'report.json')
    return 0 if rows and all(r['accepted'] for r in rows) else 3


if __name__ == '__main__': raise SystemExit(main())
