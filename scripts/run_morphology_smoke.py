"""Twelve-building exterior morphology test; optional live hierarchical planning.

Uses local assets only, never starts a worker or opens the desktop browser.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from cityg.agent_pipeline import HierarchicalAgenticGenerationPipeline
from cityg.agents import RequirementAgent, HierarchicalPlanningAgent
from cityg.assets import AssetRegistry, MaterialLibrary
from cityg.geometry import GeometryCompiler
from cityg.morphology import realization_report, contract_issues
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
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        parser.error('Output must be absent or empty')
    output.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[1]
    source = json.loads((root/'examples/morphology_showcase.json').read_text())
    registry, materials = AssetRegistry(), MaterialLibrary()
    registry.load(root/'assets/asset_registry.json')
    materials.load(root/'assets/material_library.json')
    backend = OpenUSDBackend(GeometryCompiler(asset_registry=registry,
        material_library=materials, include_interiors=False))
    save_json(source, output/'requested_spec.json')
    if args.online:
        service = TracedService(ModelEndpoint(base_url='http://127.0.0.1:8000/v1', model='cityg-llm',
            max_tokens=7000, timeout_s=180, temperature=.2, seed=29), output)
        instruction = ('仅生成城市室外。12栋建筑，河流独立蜿蜒，只有少量滨水道路弯曲，'
            '大部分道路保持直线，支路错位接入形成T字路口与斜向街块，不要整体扭曲城市。'
            '住宅保留普通体量，商业和公共建筑使用给定外壳组合。'
            '以下为必须保留的完整CitySpec参数，不要省略或改名。'
            'Urban Agent 保留 landscape_adaptive，Building Agent 可选择兼容原型，'
            '但不得替换显式外壳。配置：'+json.dumps(source, ensure_ascii=False))
        result = HierarchicalAgenticGenerationPipeline(
            RequirementAgent(service, model_id='cityg-llm'),
            HierarchicalPlanningAgent(service, model_id='cityg-llm', max_calls_per_agent=4),
            simulation_backend=backend).run(instruction, output/'scene').generation
    else:
        result = GenerationPipeline(simulation_backend=backend).run(CitySpec.from_dict(source), output/'scene')
    save_json({'online_planning': args.online, 'realized': realization_report(result.city),
               'intent_issues': contract_issues(result.city), 'validation': result.validation.to_dict(),
               'physics_runtime': 'not_executed', 'vlm_review': 'not_executed',
               'interiors_compiled': False}, output/'morphology_report.json')
    if not result.ok:
        raise RuntimeError(result.validation.to_dict())
    export_portable_viewer(output/'scene', output/'viewer')
    planner = AdaptiveObservationPlanner(include_room_views=False)
    views = list(planner._global_views(result.city)[:1])
    views.extend(planner._waterfront_views(result.city, [])[:2])
    seen = set()
    for view in planner._building_views(result.city, []):
        bid = view.target_entity_ids[0]
        b = next(b for b in result.city.iter_buildings() if b.id == bid)
        shape = b.metadata.get('appearance_plan', {}).get('envelope', {}).get('shape', 'legacy')
        if shape not in seen:
            views.append(view)
            seen.add(shape)
    plan = {'scene_id': result.city.id, 'selected_views': [v.to_dict() for v in views]}
    save_json(plan, output/'observation_plan.json')
    if args.render:
        capture(output/'scene', plan, output/'observations')
    print(f"Morphology Viewer: {output/'viewer'}", flush=True)


if __name__ == '__main__':
    main()
