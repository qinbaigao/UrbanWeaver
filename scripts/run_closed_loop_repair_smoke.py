#!/usr/bin/env python3
"""Run a controlled validator-guided repair through the complete Coordinator."""

from __future__ import annotations

import argparse
from pathlib import Path

from cityg.agents import HierarchicalPlanningAgent, RepairAgent, RequirementAgent
from cityg.assets import AssetRegistry, AssetResolver
from cityg.closed_loop import ClosedLoopBudget, ClosedLoopCoordinator
from cityg.evaluation import inject_error
from cityg.geometry import GeometryCompiler
from cityg.services import OpenAICompatibleService, OpenUSDBackend
from cityg.services.interfaces import ModelEndpoint
from cityg.validation import CityValidator


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Inject one named regression error and exercise closed-loop repair"
    )
    requirement = result.add_mutually_exclusive_group(required=True)
    requirement.add_argument("--requirement")
    requirement.add_argument("--requirement-file", type=Path)
    result.add_argument("--output", required=True, type=Path)
    result.add_argument("--case", default="disconnected_entrance")
    result.add_argument("--variant", type=int, default=0)
    result.add_argument("--base-url", default="http://127.0.0.1:8000/v1")
    result.add_argument("--model", default="cityg-llm")
    result.add_argument("--model-seed", type=int, default=0)
    result.add_argument("--max-tokens", type=int, default=1536)
    result.add_argument("--timeout", type=float, default=180.0)
    result.add_argument("--max-wall-time", type=float, default=1800.0)
    result.add_argument("--max-total-tokens", type=int, default=160_000)
    result.add_argument("--max-touched-entities", type=int, default=64)
    result.add_argument("--asset-registry", type=Path)
    result.add_argument("--no-viewer", action="store_true")
    return result


def main() -> int:
    args = parser().parse_args()
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
    registry = AssetRegistry(args.asset_registry) if args.asset_registry else None
    resolver = AssetResolver(registry, max_provider_calls=0) if registry else None
    coordinator = ClosedLoopCoordinator(
        RequirementAgent(service, model_id=args.model),
        HierarchicalPlanningAgent(service, model_id=args.model),
        RepairAgent(service, model_id=args.model, validator=validator),
        validator=validator,
        simulation_backend=OpenUSDBackend(
            geometry_compiler=GeometryCompiler(asset_registry=registry)
        ),
        budget=ClosedLoopBudget(
            max_repair_rounds=3,
            max_total_tokens=args.max_total_tokens,
            max_touched_entities=args.max_touched_entities,
            max_wall_time_s=args.max_wall_time,
        ),
        candidate_transform=lambda city: inject_error(city, args.case, args.variant),
        export_viewer=not args.no_viewer,
        asset_registry=registry,
        asset_resolver=resolver,
        run_metadata={
            "evaluation": "controlled_error_injection",
            "injected_error_case": args.case,
            "injected_error_variant": args.variant,
            "model_seed": args.model_seed,
            "max_completion_tokens_per_call": args.max_tokens,
            "asset_registry": str(args.asset_registry) if args.asset_registry else None,
        },
    )
    result = coordinator.run(requirement, args.output)
    print(
        f"Closed-loop repair smoke: {result.run.status}; "
        f"repairs={result.run.metrics.repair_rounds}; "
        f"calls={result.run.metrics.model_calls}; elapsed={result.run.elapsed_s:.2f}s"
    )
    print(f"Run record: {result.output_dir / 'run.json'}")
    return 0 if result.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
