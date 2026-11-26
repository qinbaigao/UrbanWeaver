"""Command line entry point."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from cityg.asset_providers import (
    AssetProviderError,
    HunyuanAssetEndpoint,
    HunyuanAssetProvider,
)
from cityg.assets import AssetRegistry, AssetResolver, MaterialLibrary
from cityg.agent_pipeline import (
    AgenticGenerationPipeline,
    HierarchicalAgenticGenerationPipeline,
)
from cityg.agents import (
    AgentGenerationError,
    HierarchicalPlanningAgent,
    RepairAgent,
    RequirementAgent,
)
from cityg.closed_loop import ClosedLoopBudget, ClosedLoopCoordinator
from cityg.pipeline import GenerationPipeline
from cityg.geometry import GeometryCompiler
from cityg.planning import BaselineCityPlanner
from cityg.planning.interiors import FloorDetailAgent
from cityg.repair import PatchEngine, PatchRejected, WorldPatch
from cityg.schemas import CitySpec
from cityg.serialization import load_city, save_json
from cityg.services import OpenAICompatibleService, OpenUSDBackend
from cityg.services.interfaces import ModelEndpoint
from cityg.validation import CityValidator
from cityg.viewer import export_portable_viewer, serve_viewer
from cityg.memory import MemoryStore
from cityg.visual_review import VisualReviewAgent
from cityg.observation import AdaptiveObservationPlanner
from cityg.adaptive_review import run_adaptive_review
from cityg.editing import rollback_scene, run_batch_edit, run_edit
from cityg.outdoor_assets import (
    OutdoorAssetPackBuilder,
    default_outdoor_slots,
    import_outdoor_asset,
)
from cityg.asset_curation import ExternalAssetSourceCatalog, IncomingAssetCurator
from cityg.facade_assets import FacadeAssetIndex


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cityg", description="Generate and validate hierarchical city environments"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate", help="Generate a city from a JSON spec")
    generate.add_argument("--spec", required=True, type=Path, help="Path to CitySpec JSON")
    generate.add_argument("--output", required=True, type=Path, help="Output directory")
    generate.add_argument(
        "--backend",
        choices=("manifest", "openusd"),
        default="manifest",
        help="Compilation backend (default: manifest)",
    )
    generate.add_argument(
        "--asset-registry",
        type=Path,
        help="Optional local asset registry used for indoor objects",
    )
    generate.add_argument(
        "--material-library",
        type=Path,
        help="Optional PBR material library (defaults to assets/material_library.json when present)",
    )
    generate.add_argument(
        "--facade-asset-index",
        type=Path,
        help="Optional reviewed facade-module annotation index",
    )
    generate.add_argument(
        "--no-viewer",
        action="store_true",
        help="Skip portable Web Viewer export",
    )

    asset_generate = subparsers.add_parser(
        "asset-generate", help="Generate or reuse one asset through a local Hunyuan worker"
    )
    asset_generate.add_argument("--query", required=True)
    asset_generate.add_argument("--category", required=True)
    asset_generate.add_argument(
        "--dimensions",
        type=float,
        nargs=3,
        metavar=("WIDTH", "DEPTH", "HEIGHT"),
        required=True,
        help="Target dimensions in meters",
    )
    asset_generate.add_argument(
        "--registry", required=True, type=Path, help="Asset registry JSON to update"
    )
    asset_generate.add_argument(
        "--asset-url", default="http://127.0.0.1:8091"
    )
    asset_generate.add_argument("--timeout", type=float, default=1800.0)
    asset_generate.add_argument(
        "--no-texture", action="store_true", help="Request geometry only"
    )

    outdoor_assets = subparsers.add_parser(
        "outdoor-assets",
        help="Build or audit the semantic CityG outdoor asset pack",
    )
    outdoor_assets.add_argument(
        "--registry", required=True, type=Path, help="Asset registry JSON to update"
    )
    outdoor_assets.add_argument(
        "--output", required=True, type=Path, help="Outdoor pack manifest JSON"
    )
    outdoor_assets.add_argument(
        "--generate",
        action="store_true",
        help="Fill generation-safe missing slots with the configured local worker",
    )
    outdoor_assets.add_argument(
        "--experimental-generate-curated",
        action="store_true",
        help="Generate candidate vehicle/person/vegetation assets for review; never auto-use them",
    )
    outdoor_assets.add_argument(
        "--max-generated-assets", type=int, default=4,
        help="Maximum provider calls during this invocation (default: 4)",
    )
    outdoor_assets.add_argument("--asset-url", default="http://127.0.0.1:8091")
    outdoor_assets.add_argument("--timeout", type=float, default=1800.0)
    outdoor_assets.add_argument(
        "--no-texture", action="store_true", help="Request geometry-only candidates"
    )
    outdoor_assets.add_argument(
        "--slot", action="append", default=[],
        help="Build only this slot id; repeat to select multiple slots",
    )

    outdoor_import = subparsers.add_parser(
        "outdoor-import",
        help="Copy and register one licensed GLB/USD asset into an outdoor slot",
    )
    outdoor_import.add_argument("--slot", required=True)
    outdoor_import.add_argument("--geometry", required=True, type=Path)
    outdoor_import.add_argument("--registry", required=True, type=Path)
    outdoor_import.add_argument("--asset-root", required=True, type=Path)
    outdoor_import.add_argument("--source", required=True)
    outdoor_import.add_argument("--license", required=True, dest="license_id")
    outdoor_import.add_argument("--preview", type=Path)
    outdoor_import.add_argument("--quality", type=float, default=.8)

    outdoor_review = subparsers.add_parser(
        "outdoor-review",
        help="Accept or reject a registered outdoor asset after visual inspection",
    )
    outdoor_review.add_argument("--slot", required=True)
    outdoor_review.add_argument("--status", choices=("accepted", "rejected"), required=True)
    outdoor_review.add_argument("--reason", default="manual visual review")
    outdoor_review.add_argument("--registry", required=True, type=Path)
    outdoor_review.add_argument("--pack", required=True, type=Path)

    asset_curate = subparsers.add_parser(
        "asset-curate",
        help="Canonicalize and tag supported packs under assets/incoming",
    )
    asset_curate.add_argument("--incoming", required=True, type=Path)
    asset_curate.add_argument("--cache", required=True, type=Path)
    asset_curate.add_argument("--registry", required=True, type=Path)
    asset_curate.add_argument("--manifest", required=True, type=Path)
    asset_curate.add_argument(
        "--source-catalog",
        type=Path,
        help="Optional JSON path for the persistent external source catalog",
    )
    asset_curate.add_argument(
        "--limit", type=int, help="Optional deterministic asset limit for smoke tests"
    )

    source_search = subparsers.add_parser(
        "asset-source-search",
        help="Create a demand-driven search plan for external high-quality assets",
    )
    source_search.add_argument("--query", required=True)
    source_search.add_argument("--category")
    source_search.add_argument("--output", type=Path)

    agent_generate = subparsers.add_parser(
        "agent-generate", help="Generate a city from a natural-language requirement"
    )
    requirement_source = agent_generate.add_mutually_exclusive_group(required=True)
    requirement_source.add_argument("--requirement", help="Natural-language requirement")
    requirement_source.add_argument(
        "--requirement-file", type=Path, help="UTF-8 text file containing the requirement"
    )
    agent_generate.add_argument("--output", required=True, type=Path)
    agent_generate.add_argument(
        "--base-url", default="http://127.0.0.1:8000/v1"
    )
    agent_generate.add_argument("--model", default="cityg-llm")
    agent_generate.add_argument("--timeout", type=float, default=180.0)
    agent_generate.add_argument("--max-tokens", type=int, default=1536)
    agent_generate.add_argument("--max-attempts", type=int, default=3)
    agent_generate.add_argument(
        "--hierarchical",
        action="store_true",
        help="Run Urban, Building and Floor agents after requirement parsing",
    )
    agent_generate.add_argument("--max-calls-per-agent", type=int, default=4,
        help="Proposal/invalid-action attempts per agent; successful context disclosure has a separate bounded budget")
    agent_generate.add_argument(
        "--disable-building-floor-agent",
        action="store_true",
        help="Skip the post-footprint Building-specific Floor Agent",
    )
    agent_generate.add_argument(
        "--max-building-floor-calls",
        type=int,
        default=12,
        help="Maximum distinct footprint signatures sent to Building-specific Floor Agent",
    )
    agent_generate.add_argument(
        "--backend", choices=("manifest", "openusd"), default="manifest"
    )
    agent_generate.add_argument(
        "--material-library",
        type=Path,
        help="Optional PBR material library (defaults to assets/material_library.json when present)",
    )
    agent_generate.add_argument(
        "--no-viewer", action="store_true", help="Skip portable Web Viewer export"
    )

    validate = subparsers.add_parser("validate", help="Validate a generated city.json")
    validate.add_argument("manifest", type=Path, help="Path to city.json")
    validate.add_argument("--report", type=Path, help="Optional path for the report JSON")

    patch = subparsers.add_parser("patch", help="Apply an atomic, scope-limited CCWP patch")
    patch.add_argument("manifest", type=Path, help="Input city.json, which may be invalid")
    patch.add_argument("--patch", required=True, type=Path, dest="patch_path")
    patch.add_argument("--output", required=True, type=Path, help="Output repaired city.json")
    patch.add_argument("--report", type=Path, help="Optional post-validation report JSON")

    agent_repair = subparsers.add_parser(
        "agent-repair", help="Repair one validator-localized CCWP subtree with an LLM"
    )
    agent_repair.add_argument("manifest", type=Path, help="Invalid input city.json")
    agent_repair.add_argument("--output", required=True, type=Path)
    agent_repair.add_argument("--trace", required=True, type=Path)
    agent_repair.add_argument(
        "--base-url", default="http://127.0.0.1:8000/v1"
    )
    agent_repair.add_argument("--model", default="cityg-llm")
    agent_repair.add_argument("--timeout", type=float, default=180.0)
    agent_repair.add_argument("--max-tokens", type=int, default=2048)
    agent_repair.add_argument("--max-attempts", type=int, default=3)

    agent_edit = subparsers.add_parser(
        "agent-edit",
        help="Edit an existing CityG scene from a natural-language instruction",
    )
    agent_edit.add_argument(
        "--scene", required=True, type=Path,
        help="Existing run directory, compiled scene directory, or city.json",
    )
    edit_instruction = agent_edit.add_mutually_exclusive_group(required=True)
    edit_instruction.add_argument("--instruction", help="Natural-language edit instruction")
    edit_instruction.add_argument(
        "--instruction-file", type=Path, help="UTF-8 text file containing the edit instruction"
    )
    agent_edit.add_argument("--output", required=True, type=Path)
    agent_edit.add_argument("--base-url", default="http://127.0.0.1:8000/v1")
    agent_edit.add_argument("--model", default="cityg-llm")
    agent_edit.add_argument("--timeout", type=float, default=180.0)
    agent_edit.add_argument("--max-tokens", type=int, default=2048)
    agent_edit.add_argument("--max-attempts", type=int, default=3)
    agent_edit.add_argument("--backend", choices=("manifest", "openusd"), default="openusd")
    agent_edit.add_argument("--asset-registry", type=Path)
    agent_edit.add_argument("--generate-missing-assets", action="store_true")
    agent_edit.add_argument("--asset-url", default="http://127.0.0.1:8091")
    agent_edit.add_argument("--asset-timeout", type=float, default=1800.0)
    agent_edit.add_argument("--max-generated-assets", type=int, default=4)
    agent_edit.add_argument("--no-asset-texture", action="store_true")
    agent_edit.add_argument(
        "--visual-review", action="store_true",
        help="Run adaptive VLM review after the edit",
    )
    agent_edit.add_argument(
        "--auto-vlm-refine", action="store_true",
        help="Allow bounded VLM review refinements to be promoted into the edited version",
    )
    agent_edit.add_argument("--review-base-url", help="Optional separate VLM endpoint")
    agent_edit.add_argument("--review-model", help="Optional separate VLM model")
    agent_edit.add_argument("--review-max-views", type=int, default=6)

    batch_edit = subparsers.add_parser(
        "batch-edit", help="Apply several natural-language edits as versioned steps"
    )
    batch_edit.add_argument("--scene", required=True, type=Path)
    batch_edit.add_argument(
        "--instructions-file", required=True, type=Path,
        help="JSON array or UTF-8 file with one instruction per non-empty line",
    )
    batch_edit.add_argument("--output", required=True, type=Path)
    batch_edit.add_argument("--base-url", default="http://127.0.0.1:8000/v1")
    batch_edit.add_argument("--model", default="cityg-llm")
    batch_edit.add_argument("--timeout", type=float, default=180.0)
    batch_edit.add_argument("--max-tokens", type=int, default=2048)
    batch_edit.add_argument("--max-attempts", type=int, default=3)
    batch_edit.add_argument("--backend", choices=("manifest", "openusd"), default="openusd")
    batch_edit.add_argument("--no-viewer", action="store_true")
    batch_edit.add_argument("--asset-registry", type=Path)
    batch_edit.add_argument("--generate-missing-assets", action="store_true")
    batch_edit.add_argument("--asset-url", default="http://127.0.0.1:8091")
    batch_edit.add_argument("--asset-timeout", type=float, default=1800.0)
    batch_edit.add_argument("--max-generated-assets", type=int, default=4)
    batch_edit.add_argument("--no-asset-texture", action="store_true")

    rollback = subparsers.add_parser(
        "rollback", help="Create a new scene version from an earlier scene"
    )
    rollback.add_argument("--scene", required=True, type=Path, help="Edited scene to roll back from")
    rollback.add_argument("--to", type=Path, help="Explicit target scene; otherwise use base_scene_ref.json")
    rollback.add_argument("--output", required=True, type=Path)
    rollback.add_argument("--backend", choices=("manifest", "openusd"), default="openusd")
    rollback.add_argument("--no-viewer", action="store_true")
    agent_edit.add_argument(
        "--no-viewer", action="store_true", help="Skip portable Viewer export"
    )

    agent_build = subparsers.add_parser(
        "agent-build",
        help="Run the bounded requirement-to-simulation closed loop",
    )
    build_requirement = agent_build.add_mutually_exclusive_group(required=True)
    build_requirement.add_argument("--requirement", help="Natural-language requirement")
    build_requirement.add_argument(
        "--requirement-file", type=Path, help="UTF-8 requirement text file"
    )
    agent_build.add_argument("--output", required=True, type=Path)
    agent_build.add_argument("--prototype-config", type=Path,
                             help="Enable bounded prototype-driven generation from a JSON config")
    agent_build.add_argument("--base-url", default="http://127.0.0.1:8000/v1")
    agent_build.add_argument("--model", default="cityg-llm")
    agent_build.add_argument("--timeout", type=float, default=180.0)
    agent_build.add_argument("--max-tokens", type=int, default=6144)
    agent_build.add_argument(
        "--model-seed", type=int, default=0, help="Sampling seed sent to vLLM"
    )
    agent_build.add_argument("--max-attempts", type=int, default=3)
    agent_build.add_argument("--max-calls-per-agent", type=int, default=4,
        help="Proposal/invalid-action attempts per agent; successful context disclosure has a separate bounded budget")
    agent_build.add_argument(
        "--disable-building-floor-agent",
        action="store_true",
        help="Skip the post-footprint Building-specific Floor Agent",
    )
    agent_build.add_argument(
        "--max-building-floor-calls",
        type=int,
        default=12,
        help="Maximum distinct footprint signatures sent to Building-specific Floor Agent",
    )
    agent_build.add_argument(
        "--disable-streetscape-agent",
        action="store_true",
        help="Skip post-layout semantic personalization of realized road segments",
    )
    agent_build.add_argument(
        "--max-streetscape-calls",
        type=int,
        default=3,
        help="Maximum proposal/invalid-action attempts per streetscape batch (successful disclosure has a separate bounded budget)",
    )
    agent_build.add_argument("--max-repair-rounds", type=int, default=3)
    agent_build.add_argument("--max-total-model-calls", type=int, default=32)
    agent_build.add_argument(
        "--max-total-tokens", type=int, default=0,
        help="Optional cumulative input + output token cap; 0 (default) means unlimited",
    )
    agent_build.add_argument("--max-touched-entities", type=int, default=32)
    agent_build.add_argument("--max-wall-time", type=float, default=900.0)
    agent_build.add_argument(
        "--backend", choices=("manifest", "openusd"), default="openusd"
    )
    agent_build.add_argument(
        "--asset-registry",
        type=Path,
        help="Optional local asset registry used for indoor visual assets",
    )
    agent_build.add_argument(
        "--material-library",
        type=Path,
        help="Optional PBR material library (defaults to assets/material_library.json when present)",
    )
    agent_build.add_argument(
        "--facade-asset-index",
        type=Path,
        help="Reviewed facade-module index used by Building Agent and geometry compilation",
    )
    agent_build.add_argument(
        "--generate-missing-assets",
        action="store_true",
        help="Generate missing indoor GLB assets through a local Hunyuan worker",
    )
    agent_build.add_argument(
        "--asset-url", default="http://127.0.0.1:8091"
    )
    agent_build.add_argument("--asset-timeout", type=float, default=1800.0)
    agent_build.add_argument(
        "--max-generated-assets",
        type=int,
        default=8,
        help="Maximum provider calls in one build (default: 8)",
    )
    agent_build.add_argument(
        "--no-asset-texture",
        action="store_true",
        help="Request geometry-only assets from the Hunyuan worker",
    )
    agent_build.add_argument(
        "--no-viewer", action="store_true", help="Skip portable Web Viewer export"
    )
    agent_build.add_argument(
        "--no-interiors", action="store_true",
        help="Compile city-scale shells/streetscape only; keep canonical rooms in city.json",
    )
    agent_build.add_argument(
        "--adaptive-building-refinements", type=int, default=0,
        help="Selective LLM building personalization calls after deterministic planning",
    )
    agent_build.add_argument(
        "--adaptive-room-refinements", type=int, default=0,
        help="Number of representative hero rooms for selective/cached LLM furnishing programs",
    )
    agent_build.add_argument("--interior-building-limit",type=int,default=0,
                             help="Compile interiors only in this many representative buildings; 0 means all")
    agent_build.add_argument("--interior-floor-limit",type=int,default=2,
                             help="First N floors in each selected interior building")
    agent_build.add_argument(
        "--memory-store", type=Path,
        help="Optional SQLite cross-agent memory database",
    )

    view = subparsers.add_parser(
        "view", help="Inspect a CityG city or compiled scene in the Web Viewer"
    )
    view.add_argument("scene", type=Path, help="city.json or compiled output directory")
    view.add_argument("--host", default="127.0.0.1")
    view.add_argument("--port", type=int, default=5173)
    view.add_argument("--no-browser", action="store_true")

    view_export = subparsers.add_parser(
        "view-export", help="Export a portable Viewer folder for macOS or another machine"
    )
    view_export.add_argument("scene", type=Path, help="city.json or compiled output directory")
    view_export.add_argument("--output", required=True, type=Path)

    visual_review = subparsers.add_parser(
        "visual-review", help="Run the optional VLM visual review gate on local images"
    )
    visual_review.add_argument("images", nargs="+", type=Path)
    visual_review.add_argument("--output", required=True, type=Path)
    visual_review.add_argument("--base-url", default="http://127.0.0.1:8000/v1")
    visual_review.add_argument("--model", default="cityg-llm")
    visual_review.add_argument("--timeout", type=float, default=180.0)
    visual_review.add_argument("--max-tokens", type=int, default=2048)

    observation_plan = subparsers.add_parser(
        "observation-plan",
        help="Generate an adaptive, auditable set of scene observation viewpoints",
    )
    observation_plan.add_argument(
        "scene", type=Path, help="city.json or compiled OpenUSD/Viewer scene directory"
    )
    observation_plan.add_argument("--output", required=True, type=Path)
    observation_plan.add_argument("--max-views", type=int, default=12)
    observation_plan.add_argument(
        "--no-room-views", action="store_true", help="Skip room interior candidates"
    )

    adaptive_review = subparsers.add_parser(
        "adaptive-review",
        help="Batch-render adaptive views, run multi-view VLM review, refine locally, and re-render",
    )
    adaptive_review.add_argument("scene", type=Path, help="Compiled scene directory or city.json")
    adaptive_review.add_argument("--output", required=True, type=Path)
    adaptive_review.add_argument("--memory-store", type=Path)
    adaptive_review.add_argument("--base-url", default="http://127.0.0.1:8000/v1")
    adaptive_review.add_argument("--model", default="cityg-llm")
    adaptive_review.add_argument("--timeout", type=float, default=180.0)
    adaptive_review.add_argument("--max-tokens", type=int, default=1536)
    adaptive_review.add_argument("--viewer-port", type=int, default=5210)
    adaptive_review.add_argument(
        "--asset-load-timeout",
        type=float,
        default=180.0,
        help="Seconds allowed for generation-scoped Viewer assets per observation",
    )
    adaptive_review.add_argument("--max-views", type=int, default=10)
    adaptive_review.add_argument("--max-building-refinements", type=int, default=2)
    adaptive_review.add_argument("--max-room-refinements", type=int, default=2)
    adaptive_review.add_argument(
        "--max-room-layout-refinements",
        type=int,
        default=1,
        help="Post-VLM rooms eligible for transactional furniture rearrangement",
    )
    adaptive_review.add_argument(
        "--max-streetscape-refinements",
        type=int,
        default=2,
        help="Exact road segments eligible for bounded semantic streetscape repair",
    )
    adaptive_review.add_argument(
        "--max-archetype-candidates",
        type=int,
        default=4,
        help="Compatible building candidates rendered per contact sheet (1-4)",
    )
    adaptive_review.add_argument(
        "--no-archetype-contact-sheets",
        action="store_true",
        help="Skip candidate building rendering and VLM visual comparison",
    )
    adaptive_review.add_argument("--batch-size", type=int, default=4)
    adaptive_review.add_argument("--seed", type=int, default=17)
    adaptive_review.add_argument("--facade-asset-index", type=Path,
        help="Preserve the source generation's facade module catalog during recompilation")
    adaptive_review.add_argument(
        "--asset-registry", type=Path,
        help="Asset registry used by local room re-planning (defaults to scene assets/asset_registry.json)",
    )
    adaptive_review.add_argument(
        "--generate-missing-assets", action="store_true",
        help="Generate missing room GLBs through the local Hunyuan worker during re-planning",
    )
    adaptive_review.add_argument("--asset-url", default="http://127.0.0.1:8091")
    adaptive_review.add_argument("--asset-timeout", type=float, default=1800.0)
    adaptive_review.add_argument("--max-generated-assets", type=int, default=4)
    adaptive_review.add_argument(
        "--no-asset-texture", action="store_true",
        help="Request geometry-only room assets from the Hunyuan worker",
    )

    return parser


def _load_material_library(path: Path | None) -> MaterialLibrary | None:
    """Load the explicit library, or the project default when available."""
    candidate = path or Path("assets/material_library.json")
    if path is not None and not candidate.is_file():
        raise ValueError(f"Material library does not exist: {candidate}")
    return MaterialLibrary(candidate) if candidate.is_file() else None


def _generate(
    spec_path: Path,
    output: Path,
    backend: str = "manifest",
    asset_registry_path: Path | None = None,
    material_library_path: Path | None = None,
    facade_asset_index_path: Path | None = None,
    export_viewer: bool = True,
) -> int:
    data = json.loads(spec_path.read_text(encoding="utf-8"))
    spec = CitySpec.from_dict(data)
    registry = AssetRegistry(asset_registry_path) if asset_registry_path else None
    materials = _load_material_library(material_library_path)
    detail_agent = (
        FloorDetailAgent(asset_resolver=AssetResolver(registry))
        if registry is not None
        else None
    )
    simulation_backend = (
        OpenUSDBackend(
            geometry_compiler=GeometryCompiler(
                asset_registry=registry,
                material_library=materials,
                facade_asset_index_path=(
                    str(facade_asset_index_path)
                    if facade_asset_index_path is not None
                    else None
                ),
            )
        )
        if backend == "openusd"
        else None
    )
    result = GenerationPipeline(
        planner=BaselineCityPlanner(floor_detail_agent=detail_agent),
        simulation_backend=simulation_backend,
    ).run(spec, output)
    summary_path = output / "summary.json"
    if result.ok:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        print(
            "Generated "
            f"{summary['building_count']} buildings, {summary['floor_count']} floors, "
            f"and {summary['room_count_including_corridors']} rooms."
        )
        print(f"Manifest: {output / 'city.json'}")
        if export_viewer:
            viewer_dir = export_portable_viewer(output, output / "viewer")
            print(f"Portable Viewer: {viewer_dir}")
        return 0

    print(
        f"Generation failed validation with {len(result.validation.errors)} error(s).",
        file=sys.stderr,
    )
    return 2


def _asset_generate(args: argparse.Namespace) -> int:
    registry = AssetRegistry(args.registry)
    provider = HunyuanAssetProvider(
        HunyuanAssetEndpoint(
            base_url=args.asset_url,
            timeout_s=args.timeout,
            request_texture=not args.no_texture,
        )
    )
    health = provider.health()
    resolver = AssetResolver(registry, providers=(provider,))
    record = resolver.resolve(
        args.query,
        category=args.category,
        dimensions_m=tuple(args.dimensions),
    )
    if record is None:
        raise AssetProviderError("No asset provider could satisfy the request")
    texture_status = record.metadata.get("texture_status", "unknown")
    print(
        f"Asset ready: {record.asset_id} ({record.source}, texture={texture_status})"
    )
    print(f"Geometry: {record.geometry_path}")
    print(f"Registry: {args.registry}")
    if not health.get("texture_available", False) and not args.no_texture:
        print("Warning: worker has no texture checkpoint and generated geometry only.")
    return 0


def _outdoor_assets(args: argparse.Namespace) -> int:
    registry = AssetRegistry(args.registry)
    slots = default_outdoor_slots()
    if args.slot:
        requested = set(args.slot)
        known = {slot.slot_id for slot in slots}
        unknown = sorted(requested - known)
        if unknown:
            raise ValueError("Unknown outdoor asset slot(s): " + ", ".join(unknown))
        slots = tuple(slot for slot in slots if slot.slot_id in requested)
    providers = ()
    if args.generate:
        providers = (
            HunyuanAssetProvider(
                HunyuanAssetEndpoint(
                    base_url=args.asset_url,
                    timeout_s=args.timeout,
                    request_texture=not args.no_texture,
                )
            ),
        )
    builder = OutdoorAssetPackBuilder(
        registry,
        providers=providers,
        max_generated_assets=(args.max_generated_assets if args.generate else 0),
    )
    payload = builder.build(
        args.output,
        slots=slots,
        generate=args.generate or args.experimental_generate_curated,
        force_generation=args.experimental_generate_curated,
    )
    summary = payload["summary"]
    print(
        "Outdoor asset pack: "
        f"{summary['ready_count']}/{summary['slot_count']} ready, "
        f"{summary.get('candidate_count', 0)} candidates, "
        f"{summary['missing_count']} missing, {summary['rejected_count']} rejected."
    )
    print(f"Manifest: {args.output}")
    print(f"Registry: {args.registry}")
    return 0


def _outdoor_import(args: argparse.Namespace) -> int:
    registry = AssetRegistry(args.registry)
    record = import_outdoor_asset(
        registry,
        slot_id=args.slot,
        geometry=args.geometry,
        asset_root=args.asset_root,
        source=args.source,
        license_id=args.license_id,
        preview=args.preview,
        quality_score=args.quality,
    )
    print(f"Outdoor asset imported: {record.asset_id} -> {args.slot}")
    print(f"Geometry: {record.geometry_path}")
    print(f"Registry: {args.registry}")
    return 0


def _outdoor_review(args: argparse.Namespace) -> int:
    registry = AssetRegistry(args.registry)
    slots = {item.slot_id: item for item in default_outdoor_slots()}
    if args.slot not in slots:
        raise ValueError(f"Unknown outdoor asset slot: {args.slot}")
    candidates = [
        item for item in registry.list_all()
        if item.metadata.get("outdoor_slot") == args.slot
        and item.geometry_path
    ]
    if not candidates:
        raise ValueError(f"No registered geometry for outdoor slot: {args.slot}")
    record = sorted(candidates, key=lambda item: item.asset_id)[0]
    from dataclasses import replace
    registry.register(
        replace(
            record,
            metadata={
                **record.metadata,
                "manual_review_status": args.status,
                "manual_review_reason": args.reason,
            },
        ),
        overwrite=True,
    )
    payload = OutdoorAssetPackBuilder(registry).build(args.pack)
    print(f"Outdoor review: {args.slot} -> {args.status}")
    print(f"Pack: {args.pack} ({payload['summary']['ready_count']} ready)")
    return 0


def _asset_curate(args: argparse.Namespace) -> int:
    registry = AssetRegistry(args.registry)
    catalog = ExternalAssetSourceCatalog()
    if args.source_catalog:
        catalog.save(args.source_catalog)
    payload = IncomingAssetCurator(
        registry,
        incoming_root=args.incoming,
        cache_root=args.cache,
        source_catalog=catalog,
    ).curate(args.manifest, limit=args.limit)
    print(
        f"Curated {payload['asset_count']} assets from "
        f"{sum(item['status'] == 'processed' for item in payload['packages'])} pack(s)."
    )
    print(f"Canonical GLB cache: {args.cache}")
    print(f"Registry: {args.registry}")
    print(f"Manifest: {args.manifest}")
    return 0


def _asset_source_search(args: argparse.Namespace) -> int:
    payload = ExternalAssetSourceCatalog().search_plan(
        args.query, category=args.category
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"External asset search plan: {args.output}")
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def _agent_generate(args: argparse.Namespace) -> int:
    requirement = (
        args.requirement_file.read_text(encoding="utf-8")
        if args.requirement_file is not None
        else args.requirement
    )
    endpoint = ModelEndpoint(
        base_url=args.base_url,
        model=args.model,
        timeout_s=args.timeout,
        max_tokens=args.max_tokens,
        enable_thinking=False,
    )
    service = OpenAICompatibleService(endpoint)
    agent = RequirementAgent(
        service,
        model_id=args.model,
        max_attempts=args.max_attempts,
    )
    materials = _load_material_library(args.material_library)
    backend = (
        OpenUSDBackend(geometry_compiler=GeometryCompiler(material_library=materials))
        if args.backend == "openusd"
        else None
    )
    if args.hierarchical:
        pipeline = HierarchicalAgenticGenerationPipeline(
            agent,
            HierarchicalPlanningAgent(
                service,
                model_id=args.model,
                max_calls_per_agent=args.max_calls_per_agent,
                enable_appearance_agent=True,
            ),
            enable_building_floor_agent=not args.disable_building_floor_agent,
            max_building_floor_calls=args.max_building_floor_calls,
            simulation_backend=backend,
        )
    else:
        pipeline = AgenticGenerationPipeline(
            agent,
            GenerationPipeline(simulation_backend=backend),
        )
    try:
        result = pipeline.run(requirement, args.output)
    except AgentGenerationError as error:
        save_json(
            {
                "agent": "requirement",
                "model_id": args.model,
                "error": str(error),
                "attempts": [
                    {
                        "index": attempt.index,
                        "prompt_hash": attempt.prompt_hash,
                        "messages": attempt.messages,
                        "raw_output": attempt.raw_output,
                        "elapsed_s": attempt.elapsed_s,
                        "error": attempt.error,
                        "finish_reason": attempt.finish_reason,
                        "usage": attempt.usage,
                    }
                    for attempt in error.attempts
                ],
            },
            args.output / "agent_failure_trace.json",
        )
        print(f"Requirement agent failed: {error}", file=sys.stderr)
        return 2
    spec = result.requirement.spec
    print(
        f"Requirement accepted in {len(result.requirement.attempts)} attempt(s): "
        f"{spec.building_count} buildings, {len(spec.zones)} zone(s)."
    )
    print(f"Trace: {args.output / 'requirement_trace.json'}")
    if args.hierarchical:
        print(f"Hierarchy: {args.output / 'hierarchical_program.json'}")
        print(f"Hierarchy trace: {args.output / 'hierarchy_trace.json'}")
    print(f"Manifest: {args.output / 'city.json'}")
    if result.ok and not args.no_viewer:
        viewer_dir = export_portable_viewer(args.output, args.output / "viewer")
        print(f"Portable Viewer: {viewer_dir}")
    return 0 if result.ok else 2


def _validate(manifest: Path, report_path: Path | None) -> int:
    city = load_city(manifest)
    report = CityValidator().validate(city)
    if report_path:
        save_json(report.to_dict(), report_path)
    print(
        f"Validation: {'OK' if report.ok else 'FAILED'} "
        f"({len(report.errors)} errors, {len(report.warnings)} warnings)"
    )
    for issue in report.issues:
        target = f" [{issue.entity_id}]" if issue.entity_id else ""
        print(f"- {issue.severity.upper()} {issue.code}{target}: {issue.message}")
    return 0 if report.ok else 2


def _apply_patch(
    manifest: Path, patch_path: Path, output: Path, report_path: Path | None
) -> int:
    city = load_city(manifest)
    patch = WorldPatch.from_dict(
        json.loads(patch_path.read_text(encoding="utf-8"))
    )
    try:
        result = PatchEngine().apply(city, patch)
    except PatchRejected as error:
        if report_path and error.validation is not None:
            save_json(error.validation.to_dict(), report_path)
        print(f"Patch rejected [{error.code}]: {error}", file=sys.stderr)
        return 2
    save_json(result.city, output)
    if report_path:
        save_json(result.validation.to_dict(), report_path)
    print(
        f"Patch applied: {patch.id}; touched {len(result.touched_entity_ids)} entity(s)."
    )
    return 0


def _agent_repair(args: argparse.Namespace) -> int:
    city = load_city(args.manifest)
    validator = CityValidator()
    before = validator.validate(city)
    endpoint = ModelEndpoint(
        base_url=args.base_url,
        model=args.model,
        timeout_s=args.timeout,
        max_tokens=args.max_tokens,
        enable_thinking=False,
    )
    agent = RepairAgent(
        OpenAICompatibleService(endpoint),
        model_id=args.model,
        validator=validator,
        max_attempts=args.max_attempts,
    )
    try:
        result = agent.repair(city, before)
    except AgentGenerationError as error:
        save_json(
            {
                "agent": "repair",
                "model_id": args.model,
                "error": str(error),
                "pre_validation": before.to_dict(),
                "attempts": [
                    {
                        "index": attempt.index,
                        "prompt_hash": attempt.prompt_hash,
                        "messages": attempt.messages,
                        "raw_output": attempt.raw_output,
                        "elapsed_s": attempt.elapsed_s,
                        "error": attempt.error,
                        "finish_reason": attempt.finish_reason,
                        "usage": attempt.usage,
                    }
                    for attempt in error.attempts
                ],
            },
            args.trace,
        )
        print(f"Repair agent failed: {error}", file=sys.stderr)
        return 2
    save_json(result.city, args.output)
    save_json(
        {"pre_validation": before.to_dict(), **result.trace_dict()}, args.trace
    )
    print(
        f"Repair accepted in {len(result.attempts)} attempt(s); "
        f"touched {len(result.touched_entity_ids)} entity(s)."
    )
    print(f"Manifest: {args.output}")
    print(f"Trace: {args.trace}")
    return 0


def _agent_edit(args: argparse.Namespace) -> int:
    instruction = (
        args.instruction_file.read_text(encoding="utf-8")
        if args.instruction_file is not None
        else args.instruction
    )
    endpoint = ModelEndpoint(
        base_url=args.base_url,
        model=args.model,
        timeout_s=args.timeout,
        max_tokens=args.max_tokens,
        enable_thinking=False,
    )
    asset_resolver = _edit_asset_resolver(args)
    try:
        result = run_edit(
            args.scene,
            instruction,
            args.output,
            OpenAICompatibleService(endpoint),
            model_id=args.model,
            backend=args.backend,
            timeout_s=args.timeout,
            no_viewer=args.no_viewer,
            max_attempts=args.max_attempts,
            asset_resolver=asset_resolver,
            visual_review=args.visual_review,
            auto_vlm_refine=args.auto_vlm_refine,
            review_base_url=args.review_base_url or args.base_url,
            review_model=args.review_model or args.model,
            review_max_views=args.review_max_views,
        )
    except AgentGenerationError as error:
        print(f"Edit agent failed: {error}", file=sys.stderr)
        return 2
    except PatchRejected as error:
        print(f"Edit rejected [{error.code}]: {error}", file=sys.stderr)
        return 2
    if result.status == "needs_clarification":
        print(f"Edit not applied: {result.error or result.plan.clarification}", file=sys.stderr)
        print(f"Clarification report: {args.output / 'edit_result.json'}")
        return 3
    if result.status == "replan_required":
        print(f"Edit requires structural replanning: {result.error or result.plan.reason}", file=sys.stderr)
        print(f"Edit plan: {args.output / 'edit_plan.json'}")
        return 4
    print(
        f"Edit applied: touched {len(result.touched_entity_ids)} entity(s): "
        f"{', '.join(result.touched_entity_ids)}"
    )
    print(f"Output city: {result.output_city}")
    if result.output_compiled:
        print(f"Compiled scene: {result.output_compiled}")
    print(f"Edit result: {args.output / 'edit_result.json'}")
    return 0


def _edit_asset_resolver(args: argparse.Namespace):
    if args.generate_missing_assets and args.asset_registry is None:
        raise ValueError("--generate-missing-assets requires --asset-registry")
    if args.max_generated_assets < 0:
        raise ValueError("--max-generated-assets must be non-negative")
    registry = AssetRegistry(args.asset_registry) if args.asset_registry else None
    if registry is None:
        return None
    providers = ()
    if args.generate_missing_assets:
        providers = (
            HunyuanAssetProvider(
                HunyuanAssetEndpoint(
                    base_url=args.asset_url,
                    timeout_s=args.asset_timeout,
                    request_texture=not args.no_asset_texture,
                )
            ),
        )
    return AssetResolver(
        registry,
        providers,
        max_provider_calls=(args.max_generated_assets if args.generate_missing_assets else 0),
        strict_provider_errors=False,
    )


def _batch_edit(args: argparse.Namespace) -> int:
    source = args.instructions_file.read_text(encoding="utf-8")
    try:
        parsed = json.loads(source)
        instructions = parsed if isinstance(parsed, list) else [source]
    except json.JSONDecodeError:
        instructions = [line.strip() for line in source.splitlines() if line.strip()]
    endpoint = ModelEndpoint(
        base_url=args.base_url,
        model=args.model,
        timeout_s=args.timeout,
        max_tokens=args.max_tokens,
        enable_thinking=False,
    )
    try:
        asset_resolver = _edit_asset_resolver(args)
        result = run_batch_edit(
            args.scene,
            instructions,
            args.output,
            OpenAICompatibleService(endpoint),
            model_id=args.model,
            backend=args.backend,
            timeout_s=args.timeout,
            no_viewer=args.no_viewer,
            max_attempts=args.max_attempts,
            asset_resolver=asset_resolver,
        )
    except (AgentGenerationError, PatchRejected, ValueError) as error:
        print(f"Batch edit failed: {error}", file=sys.stderr)
        return 2
    if result.status != "applied":
        print(f"Batch edit paused: {result.error or 'clarification required'}", file=sys.stderr)
        print(f"Batch report: {args.output / 'batch_result.json'}")
        return 3
    print(f"Batch edit applied: {len(result.steps)} step(s)")
    print(f"Batch report: {args.output / 'batch_result.json'}")
    return 0


def _rollback(args: argparse.Namespace) -> int:
    try:
        output = rollback_scene(
            args.scene,
            args.output,
            target_scene=args.to,
            backend=args.backend,
            no_viewer=args.no_viewer,
        )
    except (OSError, ValueError, KeyError) as error:
        print(f"Rollback failed: {error}", file=sys.stderr)
        return 2
    print(f"Rollback created: {output}")
    return 0


def _agent_build(args: argparse.Namespace) -> int:
    requirement = (
        args.requirement_file.read_text(encoding="utf-8")
        if args.requirement_file is not None
        else args.requirement
    )
    endpoint = ModelEndpoint(
        base_url=args.base_url,
        model=args.model,
        timeout_s=args.timeout,
        max_tokens=args.max_tokens,
        seed=args.model_seed,
        enable_thinking=False,
    )
    service = OpenAICompatibleService(endpoint)
    validator = CityValidator()
    if args.generate_missing_assets and args.asset_registry is None:
        raise ValueError("--generate-missing-assets requires --asset-registry")
    if args.max_generated_assets < 0:
        raise ValueError("--max-generated-assets must be non-negative")
    registry = AssetRegistry(args.asset_registry) if args.asset_registry else None
    materials = _load_material_library(args.material_library)
    facade_asset_index = None
    if args.facade_asset_index is not None:
        if not args.facade_asset_index.is_file():
            raise ValueError(f"Facade asset index does not exist: {args.facade_asset_index}")
        facade_asset_index = FacadeAssetIndex.load(args.facade_asset_index)
    asset_resolver = None
    if registry is not None:
        providers = ()
        if args.generate_missing_assets:
            providers = (
                HunyuanAssetProvider(
                    HunyuanAssetEndpoint(
                        base_url=args.asset_url,
                        timeout_s=args.asset_timeout,
                        request_texture=not args.no_asset_texture,
                    )
                ),
            )
        asset_resolver = AssetResolver(
            registry,
            providers,
            max_provider_calls=(
                args.max_generated_assets if args.generate_missing_assets else 0
            ),
            strict_provider_errors=False,
        )
    memory_store = MemoryStore(args.memory_store) if args.memory_store else None
    from cityg.planning.generation_prototypes import load_options
    prototype_options = load_options(args.prototype_config) if args.prototype_config else None
    coordinator = ClosedLoopCoordinator(
        RequirementAgent(
            service, model_id=args.model, max_attempts=args.max_attempts,
            exterior_only=args.no_interiors,
            separate_interiors=not args.no_interiors,
        ),
        HierarchicalPlanningAgent(
            service,
            model_id=args.model,
            max_calls_per_agent=args.max_calls_per_agent,
            enable_appearance_agent=True,
        ),
        RepairAgent(
            service,
            model_id=args.model,
            validator=validator,
            max_attempts=args.max_attempts,
        ),
        validator=validator,
        simulation_backend=(
            OpenUSDBackend(
                geometry_compiler=GeometryCompiler(
                    asset_registry=registry,
                    material_library=materials,
                    include_interiors=not args.no_interiors,
                    facade_asset_index_path=(
                        str(args.facade_asset_index)
                        if args.facade_asset_index is not None
                        else None
                    ),
                )
            )
            if args.backend == "openusd"
            else None
        ),
        budget=ClosedLoopBudget(
            max_repair_rounds=args.max_repair_rounds,
            max_total_model_calls=args.max_total_model_calls,
            max_total_tokens=args.max_total_tokens,
            max_touched_entities=args.max_touched_entities,
            max_wall_time_s=args.max_wall_time,
        ),
        export_viewer=not args.no_viewer,
        asset_registry=registry,
        asset_resolver=asset_resolver,
        refinement_service=service,
        max_building_refinements=args.adaptive_building_refinements,
        max_room_refinements=args.adaptive_room_refinements,
        interior_building_limit=args.interior_building_limit,
        interior_floor_limit=args.interior_floor_limit,
        prototype_options=prototype_options,
        enable_building_floor_agent=not args.disable_building_floor_agent,
        max_building_floor_calls=args.max_building_floor_calls,
        enable_streetscape_agent=not args.disable_streetscape_agent,
        max_streetscape_calls=args.max_streetscape_calls,
        memory_store=memory_store,
        facade_asset_index=facade_asset_index,
        run_metadata={
            "base_url": args.base_url,
            "model_seed": args.model_seed,
            "max_completion_tokens_per_call": args.max_tokens,
            "max_attempts_per_agent_action": args.max_attempts,
            "max_calls_per_hierarchy_agent": args.max_calls_per_agent,
            "asset_registry": str(args.asset_registry) if args.asset_registry else None,
            "generate_missing_assets": args.generate_missing_assets,
            "asset_url": args.asset_url if args.generate_missing_assets else None,
            "max_generated_assets": (
                args.max_generated_assets if args.generate_missing_assets else 0
            ),
            "request_asset_textures": (
                not args.no_asset_texture if args.generate_missing_assets else False
            ),
            "adaptive_building_refinements": args.adaptive_building_refinements,
            "adaptive_room_refinements": args.adaptive_room_refinements,
            "building_floor_agent": not args.disable_building_floor_agent,
            "max_building_floor_calls": args.max_building_floor_calls,
            "streetscape_agent": not args.disable_streetscape_agent,
            "max_streetscape_calls": args.max_streetscape_calls,
            "memory_store": str(args.memory_store) if args.memory_store else None,
            "facade_asset_index": (
                str(args.facade_asset_index) if args.facade_asset_index else None
            ),
            "interiors_compiled": not args.no_interiors,
        },
    )
    try:
        result = coordinator.run(requirement, args.output)
    finally:
        if memory_store is not None:
            memory_store.close()
    metrics = result.run.metrics.to_dict()
    print(
        f"Closed loop: {result.run.status}; "
        f"{metrics['model_calls']} model call(s), "
        f"{metrics['repair_rounds']} repair round(s), "
        f"{result.run.elapsed_s:.2f}s."
    )
    print(f"Run record: {result.output_dir / 'run.json'}")
    if result.ok or result.run.status == 'partial_success':
        print(f"Final scene: {result.output_dir / 'final'}")
        if not args.no_viewer:
            print(f"Portable Viewer: {result.output_dir / 'viewer'}")
        if result.run.status == 'partial_success':
            print("Furnishing target not fully met; inspect run.json and final/reports/prototype_compiled_acceptance.json when available", file=sys.stderr)
            return 3
        return 0
    if result.run.error:
        print(
            f"Failure: {result.run.error['type']}: {result.run.error['message']}",
            file=sys.stderr,
        )
    return 2


def _visual_review(args: argparse.Namespace) -> int:
    service = OpenAICompatibleService(
        ModelEndpoint(
            base_url=args.base_url,
            model=args.model,
            timeout_s=args.timeout,
            max_tokens=args.max_tokens,
            enable_thinking=False,
        )
    )
    result = VisualReviewAgent(service).review(
        "Review this CityG scene from the supplied views. Focus on layout readability, "
        "building diversity, facade continuity, roads, and visible empty-space problems.",
        args.images,
    )
    save_json(result.to_dict(), args.output)
    print(f"Visual review: {'available' if result.available else 'unavailable'}")
    if result.error:
        print(f"Reason: {result.error}", file=sys.stderr)
    print(f"Report: {args.output}")
    return 0 if result.available else 2


def _observation_plan(args: argparse.Namespace) -> int:
    scene = args.scene.expanduser().resolve()
    city_path = scene if scene.is_file() else scene / "city.json"
    if not city_path.is_file() and scene.is_dir() and (scene / "openusd" / "city.json").is_file():
        city_path = scene / "openusd" / "city.json"
    if not city_path.is_file():
        raise ValueError(f"Observation scene must contain city.json: {scene}")
    city = load_city(city_path)
    risk_ids: set[str] = set()
    report_root = city_path.parent
    for filename in (
        "validation_report.json",
        "geometry_validation_report.json",
        "usd_validation_report.json",
    ):
        report_path = report_root / filename
        if not report_path.is_file():
            continue
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for issue in report.get("issues", []):
            entity_id = issue.get("entity_id")
            if entity_id:
                risk_ids.update(
                    item.strip() for item in str(entity_id).split(",") if item.strip()
                )
    planner = AdaptiveObservationPlanner(
        max_views=args.max_views,
        include_room_views=not args.no_room_views,
    )
    geometry_manifest = None
    geometry_path = city_path.parent / "geometry_manifest.json"
    if geometry_path.is_file():
        try:
            geometry_manifest = json.loads(geometry_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError(
                f"Invalid geometry manifest for observation planning: {geometry_path}"
            ) from error
    plan = planner.plan(
        city,
        risk_entity_ids=risk_ids,
        geometry_manifest=geometry_manifest,
    )
    save_json(plan.to_dict(), args.output)
    print(
        f"Observation plan: {len(plan.selected_views)} selected / "
        f"{plan.candidate_count} candidates; "
        f"{len(plan.covered_entity_ids)} entities covered."
    )
    if plan.uncovered_risk_entity_ids:
        print(
            "Uncovered risk entities: "
            + ", ".join(plan.uncovered_risk_entity_ids),
            file=sys.stderr,
        )
    print(f"Plan: {args.output}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "generate":
            return _generate(
                args.spec,
                args.output,
                args.backend,
                args.asset_registry,
                args.material_library,
                args.facade_asset_index,
                not args.no_viewer,
            )
        if args.command == "asset-generate":
            return _asset_generate(args)
        if args.command == "outdoor-assets":
            return _outdoor_assets(args)
        if args.command == "outdoor-import":
            return _outdoor_import(args)
        if args.command == "outdoor-review":
            return _outdoor_review(args)
        if args.command == "asset-curate":
            return _asset_curate(args)
        if args.command == "asset-source-search":
            return _asset_source_search(args)
        if args.command == "agent-generate":
            return _agent_generate(args)
        if args.command == "validate":
            return _validate(args.manifest, args.report)
        if args.command == "patch":
            return _apply_patch(
                args.manifest, args.patch_path, args.output, args.report
            )
        if args.command == "agent-repair":
            return _agent_repair(args)
        if args.command == "agent-edit":
            return _agent_edit(args)
        if args.command == "batch-edit":
            return _batch_edit(args)
        if args.command == "rollback":
            return _rollback(args)
        if args.command == "agent-build":
            return _agent_build(args)
        if args.command == "view":
            serve_viewer(
                args.scene,
                host=args.host,
                port=args.port,
                open_browser=not args.no_browser,
            )
            return 0
        if args.command == "view-export":
            output = export_portable_viewer(args.scene, args.output)
            print(f"Portable CityG Viewer: {output}")
            print("Copy it to macOS and run: python3 serve.py")
            return 0
        if args.command == "visual-review":
            return _visual_review(args)
        if args.command == "observation-plan":
            return _observation_plan(args)
        if args.command == "adaptive-review":
            report = run_adaptive_review(
                args.scene,
                args.output,
                memory_store_path=args.memory_store,
                base_url=args.base_url,
                model=args.model,
                timeout=args.timeout,
                max_tokens=args.max_tokens,
                viewer_port=args.viewer_port,
                asset_load_timeout=args.asset_load_timeout,
                max_views=args.max_views,
                max_building_refinements=args.max_building_refinements,
                max_room_refinements=args.max_room_refinements,
                max_room_layout_refinements=args.max_room_layout_refinements,
                max_streetscape_refinements=args.max_streetscape_refinements,
                enable_archetype_contact_sheets=not args.no_archetype_contact_sheets,
                max_archetype_candidates=args.max_archetype_candidates,
                batch_size=args.batch_size,
                seed=args.seed,
                asset_registry=args.asset_registry,
                facade_asset_index=args.facade_asset_index,
                generate_missing_assets=args.generate_missing_assets,
                asset_url=args.asset_url,
                asset_timeout=args.asset_timeout,
                max_generated_assets=args.max_generated_assets,
                asset_texture=not args.no_asset_texture,
            )
            reviews = [report['review'], report['review_after']]
            complete = all(r['batch_count'] > 0 and r['available_batches'] == r['batch_count'] for r in reviews)
            print(
                f"Adaptive review {'complete' if complete else 'INCOMPLETE (unavailable VLM batches)'}: "
                f"{len(report['review']['aggregated_issues'])} aggregated issue(s), "
                f"{len(report['touched_entity_ids'])} entity/entities refined."
            )
            print(f"Before images: {report['before_images'][0] if report['before_images'] else 'none'}")
            print(f"After images: {report['after_images'][0] if report['after_images'] else 'none'}")
            print(f"Report: {args.output / 'adaptive_review_report.json'}")
            return 0 if complete else 2
    except (
        OSError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
        AssetProviderError,
    ) as error:
        print(f"cityg: {error}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
