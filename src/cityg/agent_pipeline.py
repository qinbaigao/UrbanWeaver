"""First Phase 3 loop: requirement agent followed by deterministic generation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cityg.agents import (
    BuildingFloorAgent,
    HierarchicalPlanningAgent,
    HierarchicalPlanningResult,
    RequirementAgent,
    RequirementResult,
)
from cityg.pipeline import GenerationPipeline, GenerationResult
from cityg.planning import ProgrammedCityPlanner
from cityg.serialization import save_json


@dataclass(frozen=True)
class AgenticGenerationResult:
    requirement: RequirementResult
    generation: GenerationResult

    @property
    def ok(self) -> bool:
        return self.generation.ok


class AgenticGenerationPipeline:
    """Keep probabilistic interpretation outside deterministic city construction."""

    def __init__(
        self,
        requirement_agent: RequirementAgent,
        generation_pipeline: GenerationPipeline | None = None,
    ) -> None:
        self.requirement_agent = requirement_agent
        self.generation_pipeline = generation_pipeline or GenerationPipeline()

    def run(self, requirement: str, output_dir: str | Path) -> AgenticGenerationResult:
        destination = Path(output_dir)
        destination.mkdir(parents=True, exist_ok=True)
        parsed = self.requirement_agent.parse(requirement)
        save_json(parsed.spec, destination / "requested_spec.json")
        save_json(parsed.trace_dict(), destination / "requirement_trace.json")
        generated = self.generation_pipeline.run(parsed.spec, destination)
        return AgenticGenerationResult(parsed, generated)


@dataclass(frozen=True)
class HierarchicalGenerationResult:
    requirement: RequirementResult
    hierarchy: HierarchicalPlanningResult
    generation: GenerationResult

    @property
    def ok(self) -> bool:
        return self.generation.ok


class HierarchicalAgenticGenerationPipeline:
    """Natural language -> disclosed hierarchy programs -> deterministic CCWP."""

    def __init__(
        self,
        requirement_agent: RequirementAgent,
        hierarchy_agent: HierarchicalPlanningAgent,
        *,
        validator=None,
        simulation_backend=None,
        enable_building_floor_agent: bool = False,
        max_building_floor_calls: int = 12,
    ) -> None:
        self.requirement_agent = requirement_agent
        self.hierarchy_agent = hierarchy_agent
        self.validator = validator
        self.simulation_backend = simulation_backend
        self.enable_building_floor_agent = enable_building_floor_agent
        self.max_building_floor_calls = max(0, max_building_floor_calls)

    def run(
        self, requirement: str, output_dir: str | Path
    ) -> HierarchicalGenerationResult:
        destination = Path(output_dir)
        destination.mkdir(parents=True, exist_ok=True)
        parsed = self.requirement_agent.parse(requirement)
        save_json(parsed.spec, destination / "requested_spec.json")
        save_json(parsed.trace_dict(), destination / "requirement_trace.json")
        hierarchy = self.hierarchy_agent.plan(parsed.spec)
        save_json(hierarchy.program, destination / "hierarchical_program.json")
        save_json(hierarchy.trace_dict(), destination / "hierarchy_trace.json")
        floor_overrides = {}
        if self.enable_building_floor_agent:
            rough_city = ProgrammedCityPlanner(hierarchy.program).plan(parsed.spec)
            building_floor = BuildingFloorAgent(
                self.hierarchy_agent.floor_agent.service,
                model_id=self.hierarchy_agent.floor_agent.model_id,
                max_calls=min(3, self.hierarchy_agent.floor_agent.max_calls),
            )
            batch = building_floor.plan_city(
                rough_city,
                {
                    profile.function: profile
                    for profile in hierarchy.program.floor.profiles
                },
                parsed.spec,
                max_unique_calls=self.max_building_floor_calls,
            )
            floor_overrides = batch.overrides
            save_json(batch.program_dict(), destination / "building_floor_programs.json")
            save_json(batch.trace_dict(), destination / "building_floor_trace.json")

        pipeline = GenerationPipeline(
            planner=ProgrammedCityPlanner(
                hierarchy.program,
                appearance_program=(
                    hierarchy.appearance.program if hierarchy.appearance is not None else None
                ),
                floor_program_overrides=floor_overrides,
            ),
            validator=self.validator,
            simulation_backend=self.simulation_backend,
        )
        generated = pipeline.run(parsed.spec, destination)
        return HierarchicalGenerationResult(parsed, hierarchy, generated)
