"""Small exterior-only architecture test; optional live planning + VLM review.

Uses existing local assets. Never starts a model/worker or opens a desktop browser.
"""
from __future__ import annotations

import argparse
import asyncio
import threading
from collections import Counter
from pathlib import Path

from cityg.adaptive_review import _render_plan, aggregate_visual_reviews
from cityg.agent_pipeline import HierarchicalAgenticGenerationPipeline
from cityg.agents import RequirementAgent, HierarchicalPlanningAgent
from cityg.architecture import DESIGN_LANGUAGES
from cityg.assets import AssetRegistry, MaterialLibrary
from cityg.geometry import GeometryCompiler
from cityg.observation import AdaptiveObservationPlanner
from cityg.pipeline import GenerationPipeline
from cityg.refinement.building import BuildingRefinementAgent, apply_building_refinement
from cityg.schemas import CitySpec, ZoneSpec
from cityg.serialization import save_json
from cityg.services import OpenUSDBackend, OpenAICompatibleService
from cityg.services.interfaces import ModelEndpoint
from cityg.viewer import create_viewer_server, export_portable_viewer
from cityg.visual_review import VisualReviewAgent


INSTRUCTION = """构造6栋建筑、约260米×240米的城市外观测试，不需要复杂室内。
两个住宅街区各3栋，都是3到5层；一个参考温带城市的旧砖石住宅街区，
强调成组开窗与实墙开窗；另一个是同一地区新建的现代住宅区，强调遮阳构件与框架网格。
请在architecture中保存地区、年代、气候与街区背景，在各zone中明确不同的
design_languages。不要将国家名称等同于固定风格。保持建筑形态和道路安全可实现。
每层2个房间，room_count_strategy=fixed。无高层、无地标、无河流。
使用connected_grid和buildings_per_block=1，让六栋楼各自位于独立街区而不是细长并排。
旧住宅区material_palette仅用brick，新住宅区material_palette为plaster与stone。
测试主要检查立面组织差异而非随机换色，建筑总数必须为6。"""


class TracedService(OpenAICompatibleService):
    def __init__(self, endpoint, output):
        super().__init__(endpoint)
        self.output, self.records = output, []

    def complete_with_metadata(self, messages, response_schema=None):
        print(f"Model call {len(self.records)+1}: sending", flush=True)
        try:
            result = super().complete_with_metadata(messages, response_schema)
        except Exception as error:
            self.records.append({"error": f"{type(error).__name__}: {error}"})
            save_json(self.records, self.output / "model_calls.json")
            raise
        self.records.append({"finish_reason": result.finish_reason, "usage": result.usage,
                             "content": result.content})
        save_json(self.records, self.output / "model_calls.json")
        print(f"Model call {len(self.records)}: {result.finish_reason}", flush=True)
        return result


def capture(scene_path, plan, destination):
    server, url, _ = create_viewer_server(scene_path, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        return asyncio.run(_render_plan(url, plan, destination, asset_timeout_ms=180_000))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--online", action="store_true")
    parser.add_argument("--render", action="store_true")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/v1")
    parser.add_argument("--model", default="cityg-llm")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        parser.error("Output must be absent or empty")
    output.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[1]
    registry, materials = AssetRegistry(), MaterialLibrary()
    registry.load(root / "assets/asset_registry.json")
    materials.load(root / "assets/material_library.json")
    compiler = GeometryCompiler(asset_registry=registry, material_library=materials,
        include_interiors=False,
        facade_asset_index_path=str(root / "assets/facades/asset_annotations_reviewed.json"))
    backend = OpenUSDBackend(geometry_compiler=compiler)
    initial = output / "initial"
    service = None
    if args.online:
        service = TracedService(ModelEndpoint(base_url=args.base_url, model=args.model,
            max_tokens=4096, timeout_s=180, temperature=.35, seed=17), output)
        result = HierarchicalAgenticGenerationPipeline(
            RequirementAgent(service, model_id=args.model),
            HierarchicalPlanningAgent(service, model_id=args.model, max_calls_per_agent=4),
            simulation_backend=backend).run(INSTRUCTION, initial).generation
    else:
        spec = CitySpec(name="six_facade_languages", width_m=260, depth_m=240,
            building_count=6, min_floors=3, max_floors=3, rooms_per_floor=2,
            zones=(ZoneSpec("appearance_gallery", "residential"),), seed=17,
            architecture={"design_languages": list(DESIGN_LANGUAGES)})
        result = GenerationPipeline(simulation_backend=backend).run(spec, initial)
    if not result.ok:
        raise RuntimeError(result.validation.to_dict())
    city = result.city
    print("Compiled initial scene", flush=True)
    planner = AdaptiveObservationPlanner(include_room_views=False)
    building_views = planner._building_views(city, [])
    # One explicit facade view per realized design language, plus an overview.
    selected, seen = list(planner._global_views(city)[:1]), set()
    for view in building_views:
        language = view.semantic_context["appearance_plan"]["language"]
        if language not in seen:
            selected.append(view)
            seen.add(language)
    plan = {"scene_id": city.id, "selected_views": [v.to_dict() for v in selected]}
    save_json(plan, output / "observation_plan.json")
    review, refinement = None, None
    final_scene = initial
    if args.render:
        capture(initial, plan, output / "observations")
        if service is not None:
            review = aggregate_visual_reviews(plan, output / "observations",
                VisualReviewAgent(service), scene_id=city.id, batch_size=2)
            save_json(review, output / "visual_review.json")
            # Exercise bounded feedback -> appearance refinement -> recompile.
            building = next(city.iter_buildings())
            agent = BuildingRefinementAgent(service, model_id=args.model)
            proposed, attempts = agent.propose(city, building.id, visual_feedback={
                "multiview_review": review,
                "instruction": "Only adjust design_language or facade_style_override if visible evidence warrants it; otherwise no change. Preserve massing, footprint, and accepted district palette."})
            # This exterior-only regression deliberately excludes massing changes.
            from dataclasses import replace
            proposed = replace(proposed, adjustments={k: v for k, v in proposed.adjustments.items()
                if k in {"design_language", "facade_style_override"}})
            if proposed.adjustments:
                refined = apply_building_refinement(city, proposed, attempts=attempts,
                                                    model_id=args.model)
                city = refined.city
                final_scene = output / "refined"
                backend.compile_incremental(city, final_scene, initial, [building.id])
                refinement = refined.trace_dict()
                save_json(refinement, output / "refinement.json")
                revised_views = [v for v in planner._building_views(city, [])
                                 if building.id in v.target_entity_ids][:1]
                recheck = {"scene_id": city.id, "selected_views": [v.to_dict() for v in revised_views]}
                capture(final_scene, recheck, output / "recheck")
                save_json(aggregate_visual_reviews(recheck, output / "recheck",
                    VisualReviewAgent(service), scene_id=city.id, batch_size=1), output / "recheck_review.json")
    export_portable_viewer(final_scene, output / "viewer")
    save_json({"online": args.online, "rendered": args.render,
        "interiors_compiled": False, "physics_runtime": "not_executed",
        "final_scene": str(final_scene), "building_count": len(list(city.iter_buildings())),
        "language_histogram": dict(Counter(b.metadata["appearance_plan"]["language"] for b in city.iter_buildings())),
        "validation": result.validation.to_dict(), "vlm_review_ran": review is not None,
        "refinement_applied": refinement is not None}, output / "architecture_smoke_report.json")
    print(f"Portable Viewer: {output / 'viewer'}", flush=True)


if __name__ == "__main__":
    main()
