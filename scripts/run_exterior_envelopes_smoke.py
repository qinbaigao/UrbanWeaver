"""Six exterior-envelope cases, portable Viewer, optional live agents and captures."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from cityg.agent_pipeline import HierarchicalAgenticGenerationPipeline
from cityg.agents import RequirementAgent, HierarchicalPlanningAgent
from cityg.assets import AssetRegistry, MaterialLibrary
from cityg.geometry import GeometryCompiler
from cityg.observation import AdaptiveObservationPlanner
from cityg.pipeline import GenerationPipeline
from cityg.schemas import CitySpec
from cityg.serialization import save_json
from cityg.services import OpenUSDBackend
from cityg.services.interfaces import ModelEndpoint
from cityg.viewer import export_portable_viewer
from run_architecture_smoke import TracedService, capture


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--online', action='store_true')
    parser.add_argument('--render', action='store_true')
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    output=args.output.resolve()
    if output.exists() and any(output.iterdir()):
        parser.error('Output must be absent or empty')
    output.mkdir(parents=True,exist_ok=True)
    registry,materials=AssetRegistry(),MaterialLibrary()
    registry.load(root/'assets/asset_registry.json')
    materials.load(root/'assets/material_library.json')
    backend=OpenUSDBackend(GeometryCompiler(asset_registry=registry,material_library=materials,include_interiors=False))
    source=json.loads((root/'examples/exterior_envelopes.json').read_text())
    if args.online:
        service=TracedService(ModelEndpoint(base_url='http://127.0.0.1:8000/v1',model='cityg-llm',
            max_tokens=5000,timeout_s=180,temperature=.25,seed=29),output)
        instruction=('仅生成室外外观，内部不在本次范围。构造六栋商业建筑的幕墙/非矩形/倾斜外壳对照场景。'
          '请保留下面参数、每个zone的envelope配置、每个zone一栋、全部六种类型，不要把新轮廓替换成矩形组合。'
          '楼层数在给定范围变化，rooms_per_floor=2且fixed只是占位。不要扩大建筑数量。配置：'+json.dumps(source,ensure_ascii=False))
        result=HierarchicalAgenticGenerationPipeline(RequirementAgent(service,model_id='cityg-llm'),
            HierarchicalPlanningAgent(service,model_id='cityg-llm',max_calls_per_agent=4),
            simulation_backend=backend).run(instruction,output/'scene').generation
    else:
        result=GenerationPipeline(simulation_backend=backend).run(CitySpec.from_dict(source),output/'scene')
    if not result.ok:
        raise RuntimeError(result.validation.to_dict())
    compiler_contracts=json.loads((output/'scene/geometry_manifest.json').read_text())['metadata']['exterior_envelopes']
    save_json(compiler_contracts,output/'floor_envelope_contracts.json')
    planner=AdaptiveObservationPlanner(include_room_views=False)
    views=list(planner._global_views(result.city)[:1])
    seen=set()
    for v in planner._building_views(result.city,[]):
        bid=v.target_entity_ids[0]
        if bid not in seen:
            views.append(v)
            seen.add(bid)
    plan={'scene_id':result.city.id,'selected_views':[v.to_dict() for v in views]}
    save_json(plan,output/'observation_plan.json')
    # Export before optional rendering so headless failures cannot hide a usable scene.
    export_portable_viewer(output/'scene',output/'viewer')
    if args.render:
        capture(output/'scene',plan,output/'observations')
    buildings=list(result.city.iter_buildings())
    expected_configs=[z['architecture']['envelope'] for z in source['zones']]
    actual_configs=[c['config'] for c in compiler_contracts.values()]
    defaults={'shape':'rectangle','profile':'straight','facade_system':'punched',
              'segments':32,'top_scale':.72,'lean_x':.10,'lean_y':0}
    missing_cases=[config for config in expected_configs if not any(
        all(actual.get(key,defaults.get(key))==value for key,value in config.items())
        for actual in actual_configs)]
    save_json({'online_planning':args.online,'building_count':len(buildings),
        'exterior_envelope_count':len(compiler_contracts),
        'requested_case_coverage_ok':not missing_cases,'missing_requested_cases':missing_cases,
        'interior_supported':False,'physics_runtime':'not_executed','vlm_review':'not_executed',
        'cases':{bid:c['config'] for bid,c in compiler_contracts.items()},
        'validation':result.validation.to_dict()},output/'exterior_smoke_report.json')
    if missing_cases:
        print(f'Warning: {len(missing_cases)} requested configurations not preserved by planning; see report.',flush=True)
    print(f"Portable Viewer: {output/'viewer'}",flush=True)


if __name__=='__main__':
    main()
