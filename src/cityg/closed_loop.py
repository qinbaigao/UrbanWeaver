"""Bounded, auditable orchestration for CityG's agentic construction loop."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from cityg.agents import (
    AgentAttempt,
    AgentGenerationError,
    BuildingFloorAgent,
    HierarchicalPlanningAgent,
    HierarchicalPlanningResult,
    RepairAgent,
    RequirementAgent,
    StreetscapeAgent,
)
from cityg.assets import AssetRegistry, AssetResolver
from cityg.facade_assets import FacadeAssetIndex
from cityg.ccwp import build_world_program
from cityg.planning import HierarchicalProgram, ProgrammedCityPlanner
from cityg.planning.interiors import FloorDetailAgent
from cityg.planning.generation_prototypes import GenerationPrototypes, DeferredFurniture
from cityg.agents.prototype_selection import select_reference
from cityg.requirement_ledger import create_ledger, evaluate_ledger
from cityg.interior_requirements import InteriorRequirementConflict
from cityg.urban_requirements import UrbanPlanningConflict
from cityg.planning.appearance import appearance_program_for_city
from cityg.planning.streetscape import StreetProgramPlanner
from cityg.refinement import (
    BuildingRefinementAgent,
    RoomProgramAgent,
    apply_building_refinement,
    room_archetype_key,
    select_refinement_candidates,
)
from cityg.refinement.selection import mark_room_detail, select_hero_rooms
from cityg.memory import MemoryStore, MemoryRecord
from cityg.schemas import City
from cityg.serialization import save_json, to_primitive
from cityg.services import ManifestBackend, SimulationBackend
from cityg.services.interfaces import TextReasoningService
from cityg.validation import CityValidator, ValidationReport
from cityg.viewer import export_portable_viewer
from cityg.progress import progress, recorded_event, report_run, stage_started


TERMINAL_STATUSES = frozenset(
    {
        "success",
        "repaired_success",
        "partial_success",
        "budget_exhausted",
        "replan_required",
        "model_failure",
        "system_failure",
    }
)


@dataclass(frozen=True)
class ClosedLoopBudget:
    """Stage-boundary guards; zero disables only the optional token cap."""

    max_repair_rounds: int = 3
    max_total_model_calls: int = 32
    max_total_tokens: int = 0
    max_touched_entities: int = 32
    max_wall_time_s: float = 900.0
    repeated_issue_limit: int = 2

    def __post_init__(self) -> None:
        values = asdict(self)
        if values.pop("max_total_tokens") < 0:
            raise ValueError("max_total_tokens must be non-negative (0 means unlimited)")
        if any(value <= 0 for value in values.values()):
            raise ValueError("All non-token closed-loop budgets must be positive")


@dataclass
class RunMetrics:
    model_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model_elapsed_s: float = 0.0
    repair_rounds: int = 0
    touched_entity_count: int = 0
    distinct_touched_entity_ids: set[str] = field(default_factory=set)

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def consume(self, attempts: Iterable[AgentAttempt]) -> None:
        for attempt in attempts:
            self.model_calls += 1
            self.prompt_tokens += int(attempt.usage.get("prompt_tokens", 0))
            self.completion_tokens += int(attempt.usage.get("completion_tokens", 0))
            self.model_elapsed_s += attempt.elapsed_s

    def touch(self, entity_ids: Iterable[str]) -> None:
        values = tuple(entity_ids)
        self.touched_entity_count += len(values)
        self.distinct_touched_entity_ids.update(values)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_calls": self.model_calls,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "model_elapsed_s": round(self.model_elapsed_s, 6),
            "repair_rounds": self.repair_rounds,
            "touched_entity_count": self.touched_entity_count,
            "distinct_touched_entity_count": len(self.distinct_touched_entity_ids),
            "distinct_touched_entity_ids": sorted(self.distinct_touched_entity_ids),
        }


@dataclass(frozen=True)
class IssueRoute:
    action: str
    reason: str
    issue_signature: str
    error_codes: tuple[str, ...]
    scope_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class IssueRouter:
    """Map deterministic counterexamples to the narrowest safe next action."""

    def route(self, report: ValidationReport) -> IssueRoute:
        if report.ok:
            return IssueRoute("accept", "validation passed", "valid", ())
        errors = report.errors
        codes = tuple(sorted({issue.code for issue in errors}))
        scopes = {issue.allowed_patch_scope for issue in errors}
        signature_source = [
            {
                "code": issue.code,
                "entity_id": issue.entity_id,
                "scope": issue.allowed_patch_scope,
                "violating": sorted(issue.violating_entities),
            }
            for issue in errors
        ]
        signature = hashlib.sha256(
            json.dumps(signature_source, sort_keys=True).encode("utf-8")
        ).hexdigest()[:16]
        if None in scopes:
            return IssueRoute(
                "replan",
                "one or more errors have no validator-authorized local patch scope",
                signature,
                codes,
            )
        if len(scopes) != 1:
            return IssueRoute(
                "replan",
                "errors span multiple patch scopes and cannot be atomically committed",
                signature,
                codes,
            )
        scope_id = next(iter(scopes))
        return IssueRoute(
            "repair",
            "all errors share one validator-authorized patch scope",
            signature,
            codes,
            scope_id,
        )


@dataclass
class ClosedLoopRun:
    run_id: str
    requirement_fingerprint: str
    requirement: str
    model_id: str
    started_at: str
    budget: ClosedLoopBudget
    configuration: dict[str, Any] = field(default_factory=dict)
    status: str = "running"
    stage: str = "initializing"
    metrics: RunMetrics = field(default_factory=RunMetrics)
    issue_routes: list[dict[str, Any]] = field(default_factory=list)
    repair_history: list[dict[str, Any]] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    error: dict[str, Any] | None = None
    elapsed_s: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "protocol_version": "cityg.closed_loop.v1",
            "run_id": self.run_id,
            "requirement_fingerprint": self.requirement_fingerprint,
            "requirement": self.requirement,
            "model_id": self.model_id,
            "started_at": self.started_at,
            "status": self.status,
            "stage": self.stage,
            "budget": asdict(self.budget),
            "configuration": self.configuration,
            "metrics": self.metrics.to_dict(),
            "issue_routes": self.issue_routes,
            "repair_history": self.repair_history,
            "artifacts": self.artifacts,
            "error": self.error,
            "elapsed_s": round(self.elapsed_s, 6),
        }


@dataclass(frozen=True)
class ClosedLoopResult:
    run: ClosedLoopRun
    output_dir: Path
    city: City | None = None
    validation: ValidationReport | None = None

    @property
    def ok(self) -> bool:
        return self.run.status in {"success", "repaired_success"}


class _RunRecorder:
    def __init__(self, destination: Path, run: ClosedLoopRun) -> None:
        self.destination = destination
        self.run = run
        self.started = time.monotonic()
        self.sequence = 0
        self.events_path = destination / "events.jsonl"
        self._snapshot()

    def event(self, stage: str, event: str, **detail: Any) -> None:
        self.sequence += 1
        self.run.stage = stage
        self.run.elapsed_s = time.monotonic() - self.started
        payload = {
            "sequence": self.sequence,
            "elapsed_s": round(self.run.elapsed_s, 6),
            "stage": stage,
            "event": event,
            "detail": to_primitive(detail),
        }
        with self.events_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
        self._snapshot()
        recorded_event(stage, event, detail)

    def finish(self, status: str, stage: str, error: Exception | None = None) -> None:
        if status not in TERMINAL_STATUSES:
            raise ValueError(f"Unknown terminal status: {status}")
        self.run.status = status
        if error is not None:
            self.run.error = {"type": type(error).__name__, "message": str(error)}
        self.event(stage, "run_finished", status=status, error=self.run.error)

    def _snapshot(self) -> None:
        save_json(self.run.to_dict(), self.destination / "run.json")


class _BudgetExceeded(RuntimeError):
    pass


class ClosedLoopCoordinator:
    """Execute and persist one bounded requirement-to-simulation closed loop."""

    def __init__(
        self,
        requirement_agent: RequirementAgent,
        hierarchy_agent: HierarchicalPlanningAgent,
        repair_agent: RepairAgent,
        *,
        validator: CityValidator | None = None,
        simulation_backend: SimulationBackend | None = None,
        budget: ClosedLoopBudget | None = None,
        issue_router: IssueRouter | None = None,
        candidate_transform: Callable[[City], City] | None = None,
        export_viewer: bool = True,
        asset_registry: AssetRegistry | None = None,
        asset_resolver: AssetResolver | None = None,
        refinement_service: TextReasoningService | None = None,
        max_building_refinements: int = 0,
        max_room_refinements: int = 0,
        interior_building_limit: int = 0,
        interior_floor_limit: int = 2,
        enable_building_floor_agent: bool = False,
        max_building_floor_calls: int = 12,
        enable_streetscape_agent: bool = False,
        max_streetscape_calls: int = 3,
        memory_store: MemoryStore | None = None,
        facade_asset_index: FacadeAssetIndex | None = None,
        run_metadata: dict[str, Any] | None = None,
        prototype_options: dict[str, Any] | None = None,
    ) -> None:
        self.requirement_agent = requirement_agent
        self.hierarchy_agent = hierarchy_agent
        self.repair_agent = repair_agent
        self.validator = validator or CityValidator()
        self.simulation_backend = simulation_backend or ManifestBackend()
        self.budget = budget or ClosedLoopBudget()
        self.issue_router = issue_router or IssueRouter()
        self.candidate_transform = candidate_transform or (lambda city: city)
        self.export_viewer = export_viewer
        self.asset_registry = asset_registry
        self.asset_resolver = asset_resolver
        self.refinement_service = refinement_service
        self.max_building_refinements = max(0, max_building_refinements)
        self.max_room_refinements = max(0, max_room_refinements)
        self.interior_building_limit = max(0,interior_building_limit)
        self.interior_floor_limit = max(1,interior_floor_limit)
        self.enable_building_floor_agent = enable_building_floor_agent
        self.max_building_floor_calls = max(0, max_building_floor_calls)
        self.enable_streetscape_agent = enable_streetscape_agent
        self.max_streetscape_calls = max(1, max_streetscape_calls)
        self.memory_store = memory_store
        self.facade_asset_index = facade_asset_index
        self.run_metadata = dict(run_metadata or {})
        self.prototypes = GenerationPrototypes(prototype_options) if prototype_options else None
        if self.prototypes and self.max_building_refinements:
            raise ValueError("Prototype generation currently requires adaptive-building-refinements=0; "
                             "post-partition structural replanning is a separate transaction")

    @report_run('城市生成')
    def run(self, requirement: str, output_dir: str | Path) -> ClosedLoopResult:
        if not requirement.strip():
            raise ValueError("Requirement text must not be empty")
        destination = Path(output_dir).expanduser().resolve()
        if destination.exists() and any(destination.iterdir()):
            raise ValueError(f"Closed-loop output must be empty: {destination}")
        destination.mkdir(parents=True, exist_ok=True)
        from cityg.run_provenance import record_stage_start
        record_stage_start(destination)
        model_id = self.requirement_agent.model_id
        requirement_fingerprint = hashlib.sha256(
            f"{model_id}\0{requirement.strip()}".encode("utf-8")
        ).hexdigest()[:16]
        started_at = datetime.now(timezone.utc).isoformat()
        run_id = hashlib.sha256(
            f"{requirement_fingerprint}\0{started_at}\0{destination}".encode("utf-8")
        ).hexdigest()[:16]
        run = ClosedLoopRun(
            run_id=run_id,
            requirement_fingerprint=requirement_fingerprint,
            requirement=requirement.strip(),
            model_id=model_id,
            started_at=started_at,
            budget=self.budget,
            configuration={
                "backend": type(self.simulation_backend).__name__,
                "validator": type(self.validator).__name__,
                "planner": "ProgrammedCityPlanner",
                "portable_viewer": self.export_viewer,
                **self.run_metadata,
            },
        )
        policy = self.prototypes.options.get('coordination_policy','agent_feedback') if self.prototypes else 'agent_feedback'
        allow_cross_scale = policy in ('fixed_feedback', 'agent_feedback')
        run.configuration['coordination_policy'] = policy
        recorder = _RunRecorder(destination, run)
        city: City | None = None
        report: ValidationReport | None = None
        current_stage = "requirement"
        stage_started(current_stage)
        ledger = None
        prototype_report = None
        recorder.event(current_stage, "run_started", output_dir=str(destination))

        try:
            selection = None
            if self.prototypes:
                current_stage = "prototype_selection"
                stage_started(current_stage)
                selection, attempts = select_reference(self.requirement_agent, requirement,
                    self.prototypes.urban, max_attempts=self.prototypes.options['selection_attempts'])
                run.metrics.consume(attempts)
                save_json(selection, destination / "programs" / "prototype_selection.json")
                recorder.event(current_stage, "urban_reference_selected", prototype_id=selection['prototype_id'])
                self._check_budget(recorder)
                current_stage = "requirement"
                stage_started(current_stage)
                parsed = self.requirement_agent.parse(requirement, reference_context=self.prototypes.context(selection))
            else:
                parsed = self.requirement_agent.parse(requirement)
            run.metrics.consume(parsed.attempts)
            if self.prototypes and 'generation_seed' in self.prototypes.options:
                seed = self.prototypes.options['generation_seed']
                run.configuration['generation_seed'] = seed
                parsed = replace(parsed,spec=replace(parsed.spec,seed=seed))
            ledger = create_ledger(requirement, parsed.spec,
                prototype_options=self.prototypes.options if self.prototypes else None)
            design_goals=[]
            goal_options=self.prototypes.options.get('shared_goals',{}) if self.prototypes else {}
            if goal_options.get('enabled') and self.refinement_service is not None:
                from cityg.design_goals import extract_goals
                goal_report,goal_attempts=extract_goals(self.refinement_service,requirement,
                    max_calls=goal_options.get('max_calls',2))
                run.metrics.consume(goal_attempts)
                design_goals=goal_report['goals']
                save_json(goal_report,destination/'requirement'/'design_goals.json')
                self._check_budget(recorder)
            ledger['design_goals']=design_goals
            for name in ('urban_agent','skyline_agent','building_agent','floor_agent','appearance_agent'):
                agent=getattr(self.hierarchy_agent,name,None)
                if agent is not None: agent.design_goals=design_goals
            save_json(ledger, destination / "requirement" / "ledger.json")
            save_json(parsed.spec, destination / "requirement" / "requested_spec.json")
            save_json(parsed.trace_dict(), destination / "requirement" / "trace.json")
            recorder.event(
                current_stage,
                "requirement_accepted",
                attempts=len(parsed.attempts),
                building_count=parsed.spec.building_count,
                zone_count=len(parsed.spec.zones),
            )
            self._remember(
                MemoryRecord(
                    memory_id=f"{run_id}__requirement",
                    kind="requirement_spec",
                    scope_type="city",
                    scope_id=parsed.spec.name,
                    content=to_primitive(parsed.spec),
                    producer="requirement_agent",
                    validation_status="accepted",
                    confidence=1.0,
                    run_id=run_id,
                )
            )
            self._check_budget(recorder)

            current_stage = "hierarchy_urban"
            stage_started(current_stage)
            urban = self.hierarchy_agent.urban_agent.plan(parsed.spec)
            run.metrics.consume(urban.attempts)
            save_json(urban.program, destination / "programs" / "urban_program.json")
            save_json(urban.trace_dict(), destination / "programs" / "urban_trace.json")
            recorder.event(
                current_stage,
                "urban_program_accepted",
                model_calls=len(urban.attempts),
                disclosures=len(urban.disclosures),
            )
            self._check_budget(recorder)

            current_stage = "hierarchy_skyline"
            stage_started(current_stage)
            skyline = self.hierarchy_agent.skyline_agent.plan(
                parsed.spec, urban.program
            )
            run.metrics.consume(skyline.attempts)
            save_json(
                skyline.program, destination / "programs" / "skyline_program.json"
            )
            save_json(
                skyline.trace_dict(), destination / "programs" / "skyline_trace.json"
            )
            recorder.event(
                current_stage,
                "skyline_program_accepted",
                model_calls=len(skyline.attempts),
                disclosures=len(skyline.disclosures),
            )
            self._check_budget(recorder)

            current_stage = "hierarchy_building"
            stage_started(current_stage)
            building = self.hierarchy_agent.building_agent.plan(
                parsed.spec, urban.program, skyline.program,
                **({'prototype_context': {'instruction': 'Some buildings need detailed prototype interiors. '
                    'Prefer compatible bar/rectangular massing in archetype_palette unless user shape requirements '
                    'say otherwise. Nonrectangular clipped interiors may be rejected; do not invent supported geometry.',
                    'max_detailed_buildings': self.prototypes.options['adaptation']['max_buildings']}}
                   if self.prototypes and not self.requirement_agent.exterior_only else {}),
            )
            run.metrics.consume(building.attempts)
            save_json(
                building.program, destination / "programs" / "building_program.json"
            )
            save_json(
                building.trace_dict(), destination / "programs" / "building_trace.json"
            )
            recorder.event(
                current_stage,
                "building_program_accepted",
                model_calls=len(building.attempts),
                disclosures=len(building.disclosures),
            )
            self._check_budget(recorder)

            current_stage = "hierarchy_floor"
            stage_started(current_stage)
            floor = self.hierarchy_agent.floor_agent.plan(
                parsed.spec, building.program,
                **({'prototype_context': self.prototypes.floor_context(selection)} if self.prototypes else {}),
            )
            run.metrics.consume(floor.attempts)
            save_json(floor.program, destination / "programs" / "floor_program.json")
            save_json(floor.trace_dict(), destination / "programs" / "floor_trace.json")
            appearance = None
            if self.hierarchy_agent.enable_appearance_agent:
                current_stage = "hierarchy_appearance"
                stage_started(current_stage)
                appearance = self.hierarchy_agent.appearance_agent.plan(
                    parsed.spec, urban.program, building.program
                )
                run.metrics.consume(appearance.attempts)
                save_json(
                    appearance.program,
                    destination / "programs" / "appearance_program.json",
                )
                save_json(
                    appearance.trace_dict(),
                    destination / "programs" / "appearance_trace.json",
                )
                recorder.event(
                    current_stage,
                    "appearance_program_accepted",
                    model_calls=len(appearance.attempts),
                    disclosures=len(appearance.disclosures),
                )
                self._check_budget(recorder)
            program = HierarchicalProgram(
                urban.program, building.program, floor.program, skyline.program
            )
            program.validate(parsed.spec)
            hierarchy = HierarchicalPlanningResult(
                program, urban, skyline, building, floor, appearance
            )
            save_json(
                hierarchy.program, destination / "programs" / "hierarchical_program.json"
            )
            save_json(hierarchy.trace_dict(), destination / "programs" / "trace.json")
            recorder.event(
                current_stage,
                "hierarchy_accepted",
                model_calls=sum(
                    len(stage.attempts)
                    for stage in (urban, skyline, building, floor, appearance)
                    if stage is not None
                ),
                disclosures=sum(
                    len(stage.disclosures)
                    for stage in (urban, skyline, building, floor, appearance)
                    if stage is not None
                ),
            )
            self._check_budget(recorder)

            current_stage = "planning"
            stage_started(current_stage)
            floor_detail_agent = (
                FloorDetailAgent(
                    asset_resolver=(
                        self.asset_resolver
                        or AssetResolver(self.asset_registry)  # type: ignore[arg-type]
                    )
                )
                if self.asset_resolver is not None or self.asset_registry is not None
                else None
            )
            floor_overrides = {}
            floor_access_receipts = {}
            interior_targets = {}; archetype_pins = {}; interior_reservation = None
            interior_bindings = {}
            if parsed.spec.interior_requirements:
                from cityg.interior_requirements import bind_requirements
                requirement_draft = ProgrammedCityPlanner(hierarchy.program, floor_detail_agent=DeferredFurniture()).plan(parsed.spec)
                from cityg.planning.interior_capability import reserve_interiors
                eligible, _, eligibility = reserve_interiors(requirement_draft, limit=parsed.spec.building_count)
                save_json(eligibility, destination/'requirement'/'interior_binding_candidates.json')
                interior_bindings = bind_requirements(requirement_draft, parsed.spec.interior_requirements,
                                                      eligible_ids=set(eligible))
                ledger['bound_interior_requirements'] = [row for rows in interior_bindings.values() for row in rows]
                save_json(ledger, destination/'requirement'/'ledger.json')
            prototype_compiler = getattr(self.simulation_backend, 'geometry_compiler', None)
            if self.prototypes and prototype_compiler is not None and prototype_compiler.include_interiors:
                from cityg.planning.interior_capability import reserve_interiors
                draft = ProgrammedCityPlanner(hierarchy.program, floor_detail_agent=DeferredFurniture()).plan(parsed.spec)
                opt = self.prototypes.options['adaptation']
                interior_targets, archetype_pins, interior_reservation = reserve_interiors(
                    draft, limit=min(self.interior_building_limit or opt['max_buildings'], opt['max_buildings']),
                    explicit_ids=list(dict.fromkeys([*opt.get('floor_repartition', {}).get('target_building_ids', []), *interior_bindings])),
                    room_library=self.prototypes.floors.room_library if allow_cross_scale else None,
                    corridor_ratios={p.function: p.corridor_ratio for p in floor.program.profiles})
                if not interior_targets and opt['max_rooms'] > 0:
                    from cityg.planning.conflicts import planning_conflict
                    conflicts=[planning_conflict(draft,row['building_id'],
                        code='interior_capability_not_supported',reason=row['reason'],
                        stage='interior_capability') for row in interior_reservation['rejected']]
                    save_json(interior_reservation,destination/'programs'/'interior_capability_reservation.json')
                    save_json(conflicts,destination/'programs'/'planning_conflicts.json')
                    save_json(draft,destination/'checkpoints'/'interior_capability_draft.json')
                    run.configuration['prototype_status']='interior_capability_conflict'
                    recorder.finish('replan_required','interior_capability',ValueError(
                        'No building supports the requested detailed interiors; see '
                        'programs/interior_capability_reservation.json. Entrances, scope and '
                        'requested room budget were not changed; no final scene was published.'))
                    return ClosedLoopResult(run,destination,draft,None)
                from cityg.interior_requirements import constrain_reservations
                recorder.event(current_stage,'coordination_policy_entered',policy=policy)
                if allow_cross_scale:
                    from cityg.planning.generation_coordination import reserve_larger_sites
                    site_attempts = reserve_larger_sites(draft, interior_targets, interior_bindings)
                    save_json(site_attempts,destination/'programs'/'site_capacity_feedback.json')
                constrain_reservations(draft, interior_targets, interior_bindings)
                from cityg.planning.interior_capacity_search import improve_reserved_capacity
                capacity_options = self.prototypes.options.get('capacity_search', {})
                capacity_search = {'status':'disabled', 'buildings':[]}
                if allow_cross_scale and capacity_options.get('enabled', True):
                    interior_targets, capacity_search = improve_reserved_capacity(
                        hierarchy.program, parsed.spec, interior_targets, archetype_pins,
                        self.prototypes.floors.room_library,
                        max_floors=min(self.interior_floor_limit, opt['max_floors_per_building']),
                        target_levels=opt.get('floor_repartition', {}).get('levels', [0, 1]),
                        variation_limit=opt['variation_limit'],
                        max_candidates=capacity_options.get('max_candidates_per_building', 36))
                interior_reservation['target_buildings'] = interior_targets
                interior_reservation['capacity_search'] = capacity_search
                save_json(interior_reservation, destination / 'programs' / 'interior_capability_reservation.json')
                recorder.event(current_stage, 'interior_capability_reserved', targets=list(interior_targets))
            if interior_bindings and not interior_targets:
                from cityg.planning.interior_capability import reserve_interiors
                from cityg.interior_requirements import constrain_reservations
                interior_targets, archetype_pins, interior_reservation = reserve_interiors(
                    requirement_draft, limit=len(interior_bindings), explicit_ids=list(interior_bindings))
                constrain_reservations(requirement_draft, interior_targets, interior_bindings)
                save_json(interior_reservation, destination/'programs'/'interior_capability_reservation.json')
            if self.interior_building_limit:
                from cityg.planning.interior_scope import select_scope
                coordinator=self
                class ScopedDetail(FloorDetailAgent):
                    def populate(self, city, *, seed):
                        select_scope(city,coordinator.interior_building_limit,coordinator.interior_floor_limit)
                        return super().populate(city,seed=seed)
                floor_detail_agent=ScopedDetail(asset_resolver=self.asset_resolver or (
                    AssetResolver(self.asset_registry) if self.asset_registry else None))
            if self.enable_building_floor_agent:
                rough_city = ProgrammedCityPlanner(hierarchy.program,
                    interior_targets=interior_targets, archetype_pins=archetype_pins,
                    floor_detail_agent=DeferredFurniture() if self.prototypes else None).plan(parsed.spec)
                if interior_reservation is not None:
                    rough_city.metadata['interior_capability_reservation'] = interior_reservation
                if self.prototypes:
                    self.prototypes.select_scope(rough_city, building_limit=self.interior_building_limit,
                                                 floor_limit=self.interior_floor_limit)
                elif self.interior_building_limit:
                    select_scope(rough_city,self.interior_building_limit,self.interior_floor_limit)
                building_floor_agent = BuildingFloorAgent(
                    self.hierarchy_agent.floor_agent.service,
                    model_id=self.hierarchy_agent.floor_agent.model_id,
                    max_calls=self.hierarchy_agent.floor_agent.max_calls,
                )
                building_floor_agent.design_goals=design_goals
                if self.asset_registry is not None and policy != 'local_only':
                    building_floor_agent.inventory_asset_resolver=AssetResolver(
                        self.asset_registry, (), max_provider_calls=0)
                building_floor_batch = building_floor_agent.plan_city(
                    rough_city,
                    {
                        profile.function: profile
                        for profile in hierarchy.program.floor.profiles
                    },
                    parsed.spec,
                    max_unique_calls=self.max_building_floor_calls,
                    **({'prototype_context': self.prototypes.floor_context(selection)} if self.prototypes else {}),
                )
                run.metrics.consume(building_floor_batch.attempts)
                floor_overrides = building_floor_batch.overrides
                floor_access_receipts = building_floor_batch.program_dict()['decision_receipts']
                save_json(
                    building_floor_batch.program_dict(),
                    destination / "programs" / "building_floor_programs.json",
                )
                save_json(
                    building_floor_batch.trace_dict(),
                    destination / "programs" / "building_floor_trace.json",
                )
                from cityg.planning.conflicts import planning_conflict
                floor_conflicts = []
                for entity_id, reason in building_floor_batch.failed_buildings.items():
                    signature = building_floor_batch.signatures.get(entity_id)
                    attempts = building_floor_batch.trace_dict().get('failure_traces', {}).get(signature, [])
                    detail = attempts[-1].get('error') if attempts else None
                    conflict = planning_conflict(rough_city, entity_id,
                        code='building_floor_program_unrealizable', reason=detail or reason,
                        stage='building_specific_floor', fallback_used=True,
                        attempts_used=len(attempts), attempt_limit=len(attempts))
                    conflict['fallback'] = 'validated_global_floor_profile_not_building_specific_success'
                    floor_conflicts.append(conflict)
                save_json(floor_conflicts, destination/'programs'/'planning_conflicts.json')
                recorder.event(
                    current_stage,
                    "building_floor_programs_accepted",
                    model_calls=len(building_floor_batch.attempts),
                    planned_buildings=len(building_floor_batch.overrides),
                    cache_hits=sum(building_floor_batch.cache_hits.values()),
                    skipped_buildings=len(building_floor_batch.skipped_buildings),
                    failed_buildings=len(building_floor_batch.failed_buildings),
                )
                self._check_budget(recorder)

            city = ProgrammedCityPlanner(
                hierarchy.program,
                floor_detail_agent=DeferredFurniture() if self.prototypes else floor_detail_agent,
                appearance_program=(appearance.program if appearance is not None else None),
                floor_program_overrides=floor_overrides,
                interior_targets=interior_targets, archetype_pins=archetype_pins,
            ).plan(parsed.spec)
            save_json({
                'requirements': city.metadata.get('urban_requirements', []),
                'site_assignment': city.metadata.get('urban_spatial_assignment', {}),
                'geography_recovery': city.metadata.get('geography_recovery', {}),
            }, destination / 'programs' / 'urban_spatial.json')
            if interior_reservation is not None:
                city.metadata['interior_capability_reservation'] = interior_reservation
            city.metadata['design_goals']=design_goals
            from cityg.validation.floor_access_contracts import bind_floor_access_contracts
            bind_floor_access_contracts(city,floor_access_receipts)
            city = self.candidate_transform(city)
            if self.prototypes:
                current_stage = "prototype_adaptation"
                stage_started(current_stage)
                urban_report = self.prototypes.attach_urban(city, parsed.spec, selection)
                save_json(urban_report, destination / "programs" / "urban_reference.json")
                compiler = getattr(self.simulation_backend, 'geometry_compiler', None)
                if compiler is not None and compiler.include_interiors:
                    registry = self.prototypes.prepare_resources(self.asset_registry, compiler)
                    self.asset_registry = registry
                    if self.asset_resolver is not None:
                        self.asset_resolver.registry = registry
                    save_json(city, destination / "checkpoints" / "unfurnished_city.json")
                    def prototype_progress(*args):
                        recorder.event(current_stage, "prototype_step", detail=list(args))
                        self._check_budget(recorder)
                    reference_selector = None
                    room_selection = self.prototypes.options.get('room_selection', {})
                    if room_selection.get('enabled') and self.refinement_service is not None:
                        from cityg.agents.room_reference import RoomReferenceAgent
                        def reference_selector(candidate, candidates, library, options):
                            self._check_budget(recorder)
                            agent = RoomReferenceAgent(self.refinement_service,
                                max_calls=room_selection.get('max_calls',2))
                            try:
                                report, attempts = agent.plan(candidate,candidates,library,requirement,options)
                            except AgentGenerationError as exc:
                                attempts=exc.attempts
                                report={'status':'rejected_fallback_to_balanced_feasibility','choices':[],
                                    'error':str(exc),'attempts':[asdict(a) for a in attempts]}
                            run.metrics.consume(attempts)
                            save_json(report,destination/'programs'/'room_reference_selection.json')
                            self._check_budget(recorder)
                            return report
                    coordination_traces=[]
                    def floor_selector(candidate,offered):
                        from cityg.planning.floor_coordination import choose_proposal
                        self._check_budget(recorder)
                        try:
                            choice,attempts=choose_proposal(self.refinement_service,candidate,offered)
                        except AgentGenerationError as exc:
                            attempts=exc.attempts
                            choice={'proposal_id':'none','reason':'Coordination Agent unavailable: '+str(exc)}
                        run.metrics.consume(attempts)
                        coordination_traces.append({'selection':choice,'attempts':[asdict(a) for a in attempts]})
                        save_json(coordination_traces,destination/'programs'/'floor_coordination.json')
                        self._check_budget(recorder)
                        return choice
                    city, prototype_report = self.prototypes.populate(city, registry, compiler,
                        progress=prototype_progress, building_limit=self.interior_building_limit,
                        floor_limit=self.interior_floor_limit,
                        preserve_partition=parsed.spec.room_count_strategy == 'fixed',
                        memory_store=self.memory_store, reference_selector=reference_selector,
                        floor_selector=floor_selector if self.refinement_service is not None else None)
                    save_json(city, destination / "checkpoints" / "prototype_city.json")
                else:
                    city.metadata['interior_scope'] = {'building_levels': {}, 'policy': 'prototype_exterior_only'}
                    prototype_report = {'status': 'interiors_skipped', 'summary': {}, 'rooms': [],
                        'reason': 'Interior prototype verification requires an interior-enabled OpenUSD compiler'}
                save_json(prototype_report, destination / "programs" / "prototype_adaptation.json")
                self._remember(MemoryRecord(
                    memory_id=f"{run_id}__prototype_execution", kind="prototype_execution",
                    scope_type="city", scope_id=city.id,
                    content={'urban_reference': selection['prototype_id'],
                             'status': prototype_report['status'], 'summary': prototype_report['summary'],
                             'report': 'programs/prototype_adaptation.json'},
                    producer='generation_prototypes', validation_status='accepted', run_id=run_id))
                recorder.event(current_stage, "prototype_adaptation_completed", status=prototype_report['status'],
                               summary=prototype_report['summary'])
                run.configuration['prototype_options'] = self.prototypes.options
                run.configuration['prototype_status'] = prototype_report['status']
                self._check_budget(recorder)
            if (interior_bindings and self.refinement_service is not None and
                    self.asset_registry is not None and prototype_compiler is not None and
                    prototype_compiler.include_interiors):
                from cityg.refinement.functional_completion import complete_inventory
                current_stage = "functional_completion"
                stage_started(current_stage)
                def account_completion(attempts):
                    run.metrics.consume(attempts)
                    self._check_budget(recorder)
                city, completion_report = complete_inventory(city, self.refinement_service,
                    prototype_compiler, self.asset_registry, max_rooms=self.max_room_refinements,
                    seed=parsed.spec.seed, memory_store=self.memory_store, on_attempts=account_completion)
                run.metrics.touch(tuple(row['room_id'] for row in completion_report['attempts'] if row['status']=='accepted'))
                if prototype_report is not None:
                    prototype_report['functional_completion'] = {
                        'max_rooms':completion_report['max_rooms'],
                        'compiled_rooms':completion_report['compiled_rooms']}
                    save_json(prototype_report,destination/'programs'/'prototype_adaptation.json')
                save_json(completion_report, destination/'refinements'/'functional_completion.json')
                self._check_budget(recorder)
                recorder.event(current_stage, 'functional_completion_checked',
                               attempted_rooms=len(completion_report['attempts']))
            if (self.prototypes and self.refinement_service is not None and
                    self.asset_registry is not None and prototype_compiler is not None and
                    prototype_compiler.include_interiors and
                    self.prototypes.options.get('functional_configuration', {}).get('enabled')):
                from cityg.refinement.functional_configuration import improve_functional_configuration
                current_stage = 'functional_configuration'
                stage_started(current_stage)
                def account_configuration(attempts):
                    run.metrics.consume(attempts)
                    self._check_budget(recorder)
                city, configuration_report = improve_functional_configuration(
                    city, self.refinement_service, prototype_compiler, self.asset_registry,
                    config=self.prototypes.options['functional_configuration'], seed=parsed.spec.seed,
                    memory_store=self.memory_store, on_attempts=account_configuration)
                run.metrics.touch(tuple(r['room_id'] for r in configuration_report['attempts'] if r['status']=='accepted'))
                prototype_report['functional_configuration'] = {
                    'max_rooms': configuration_report['options']['max_rooms'],
                    'compiled_rooms': configuration_report['compiled_rooms']}
                save_json(prototype_report, destination/'programs'/'prototype_adaptation.json')
                save_json(configuration_report, destination/'refinements'/'functional_configuration.json')
                save_json(city, destination/'checkpoints'/'functional_configuration_city.json')
                recorder.event(current_stage, 'functional_configuration_checked',
                               attempted_rooms=len(configuration_report['attempts']),
                               accepted_rooms=len(configuration_report['compiled_rooms']))
                self._check_budget(recorder)
            save_json(city, destination / "checkpoints" / "before_room_refinement.json")
            progress('局部个性化', '检查建筑与精细房间的自适应规划')
            city, refinement_summary = self._apply_adaptive_refinements(
                city, parsed.spec.seed, destination, run_id, run
            )
            if refinement_summary:
                recorder.event(current_stage, "adaptive_refinements_applied", **refinement_summary)
            if self.enable_streetscape_agent:
                current_stage = "planning_streetscape"
                stage_started(current_stage)
                streetscape_agent = StreetscapeAgent(
                    self.hierarchy_agent.floor_agent.service,
                    model_id=self.hierarchy_agent.floor_agent.model_id,
                    max_calls=self.max_streetscape_calls,
                )
                streetscape_producer = "streetscape_agent"
                streetscape_confidence = 1.0
                try:
                    streetscape = streetscape_agent.plan(
                        city, appearance_program_for_city(city)
                    )
                    run.metrics.consume(streetscape.attempts)
                    if streetscape.diagnostics.get('fallback_road_ids'):
                        streetscape_producer = 'streetscape_agent_with_local_fallback'
                        streetscape_confidence = 0.85
                    city.metadata["street_network_program"] = streetscape.program.to_dict()
                    city.metadata['streetscape_planning_diagnostics'] = streetscape.diagnostics
                    save_json(
                        streetscape.program,
                        destination / "programs" / "streetscape_program.json",
                    )
                    save_json(
                        streetscape.trace_dict(),
                        destination / "programs" / "streetscape_trace.json",
                    )
                    recorder.event(
                        current_stage,
                        "streetscape_program_accepted",
                        model_calls=len(streetscape.attempts),
                        disclosures=len(streetscape.disclosures),
                        road_segments=len(streetscape.program.segments),
                        fallback_roads=len(streetscape.diagnostics.get('fallback_road_ids',[])),
                    )
                except AgentGenerationError as error:
                    streetscape_producer = "deterministic_street_program_planner"
                    streetscape_confidence = 0.85
                    run.metrics.consume(error.attempts)
                    fallback = StreetProgramPlanner().plan(
                        city, appearance_program_for_city(city)
                    )
                    city.metadata["street_network_program"] = fallback.to_dict()
                    save_json(
                        fallback,
                        destination / "programs" / "streetscape_program.json",
                    )
                    save_json(
                        {
                            "agent": "streetscape",
                            "model_id": self.hierarchy_agent.floor_agent.model_id,
                            "fallback": "deterministic_context",
                            "error": str(error),
                            "attempts": [asdict(item) for item in error.attempts],
                        },
                        destination / "programs" / "streetscape_trace.json",
                    )
                    recorder.event(
                        current_stage,
                        "streetscape_agent_fallback",
                        model_calls=len(error.attempts),
                        road_segments=len(fallback.segments),
                        reason=str(error),
                    )
                self._remember(
                    MemoryRecord(
                        memory_id=f"{run_id}__streetscape",
                        kind="street_network_program",
                        scope_type="city",
                        scope_id=city.id,
                        content=city.metadata["street_network_program"],
                        producer=streetscape_producer,
                        validation_status="accepted",
                        confidence=streetscape_confidence,
                        run_id=run_id,
                    )
                )
                self._check_budget(recorder)
            save_json(city, destination / "checkpoints" / "planned_city.json")
            recorder.event(
                current_stage,
                "city_planned",
                buildings=sum(1 for _ in city.iter_buildings()),
                floors=sum(1 for _ in city.iter_floors()),
                rooms=sum(1 for _ in city.iter_rooms()),
                asset_resolution=(
                    self.asset_resolver.stats()
                    if self.asset_resolver is not None
                    else None
                ),
            )

            current_stage = "validation"
            stage_started(current_stage)
            report = self.validator.validate(city)
            save_json(
                report.to_dict(),
                destination / "checkpoints" / "validation_round_00.json",
            )
            recorder.event(
                current_stage,
                "validation_completed",
                round=0,
                errors=len(report.errors),
                warnings=len(report.warnings),
            )

            seen_signatures: dict[str, int] = {}
            while not report.ok:
                route = self.issue_router.route(report)
                run.issue_routes.append(route.to_dict())
                seen_signatures[route.issue_signature] = (
                    seen_signatures.get(route.issue_signature, 0) + 1
                )
                recorder.event("routing", "issues_routed", **route.to_dict())
                if route.action != "repair":
                    recorder.finish("replan_required", "routing")
                    return ClosedLoopResult(run, destination, city, report)
                if (
                    seen_signatures[route.issue_signature]
                    > self.budget.repeated_issue_limit
                ):
                    raise _BudgetExceeded(
                        "repeated validation issue signature exceeded its limit"
                    )
                if run.metrics.repair_rounds >= self.budget.max_repair_rounds:
                    raise _BudgetExceeded("maximum repair rounds exhausted")

                current_stage = "repair"
                stage_started(current_stage)
                round_index = run.metrics.repair_rounds + 1
                repair = self.repair_agent.repair(city, report)
                run.metrics.repair_rounds = round_index
                run.metrics.consume(repair.attempts)
                run.metrics.touch(repair.touched_entity_ids)
                round_dir = destination / "repairs" / f"round_{round_index:02d}"
                save_json(repair.trace_dict(), round_dir / "trace.json")
                save_json(repair.patch, round_dir / "patch.json")
                save_json(repair.city, round_dir / "city.json")
                save_json(repair.validation.to_dict(), round_dir / "validation.json")
                history = {
                    "round": round_index,
                    "scope_id": repair.patch.scope_entity_id,
                    "patch_id": repair.patch.id,
                    "attempts": len(repair.attempts),
                    "touched_entity_ids": list(repair.touched_entity_ids),
                    "post_error_count": len(repair.validation.errors),
                }
                run.repair_history.append(history)
                city, report = repair.city, repair.validation
                recorder.event(current_stage, "repair_committed", **history)
                self._check_budget(recorder)

            current_stage = "compilation"
            stage_started(current_stage)
            evaluate_ledger(ledger, city, prototype_report)
            save_json(ledger, destination / "requirement" / "ledger.json")
            if ledger['status'] == 'violated':
                recorder.event("requirement", "requirement_checks_failed", summary=ledger['summary'])
                recorder.finish("replan_required", "requirement")
                return ClosedLoopResult(run, destination, city, report)
            final_dir = destination / "final"
            backend_directory = (
                "manifest"
                if isinstance(self.simulation_backend, ManifestBackend)
                else "openusd"
            )
            compile_dir = final_dir / backend_directory
            walks = ledger['parsed_spec'].get('walking_requirements', [])
            if walks:
                city.metadata['walking_contract'] = {'requirements':walks, 'bindings':[
                    {'label':r['label'], 'building_id':r['building_id']}
                    for r in ledger.get('bound_interior_requirements', [])]}
            from cityg.services.openusd import OpenUSDBackend
            verify_furnishings = self.prototypes and (prototype_report.get('options') or prototype_report.get('rooms')
                    or prototype_report.get('functional_completion', {}).get('compiled_rooms')
                    or prototype_report.get('functional_configuration', {}).get('compiled_rooms'))
            if walks and allow_cross_scale and isinstance(self.simulation_backend, OpenUSDBackend) and run.metrics.repair_rounds < self.budget.max_repair_rounds:
                from copy import deepcopy
                from cityg.planning.floor_access_repair import compile_with_access_replanning
                def choose_access(row, choices):
                    progress("Floor Agent", "根据实际楼板断点选择修复候选", room=row["room_id"], candidates=len(choices))
                    def account(attempts):
                        run.metrics.consume(attempts)
                        self._check_budget(recorder)
                    return self.hierarchy_agent.floor_agent.rank_access_repair(row, choices, on_attempts=account)
                def protect(draft, original_manifest, revised_manifest):
                    check = evaluate_ledger(deepcopy(ledger), draft, prototype_report)
                    prior = {r["id"] for r in ledger["requirements"] if r["status"]=="satisfied"}
                    if check["status"]=="violated" or not prior <= {r["id"] for r in check["requirements"] if r["status"]=="satisfied"}:
                        raise ValueError("Floor revision conflicts with existing requirements")
                    if verify_furnishings:
                        def served(c,m):
                            result=self.prototypes.verify_final(c,m,prototype_report)
                            return set((result.get("furnishing_coverage") or {}).get("verified_room_ids",[]))
                        if not served(city,original_manifest)<=served(draft,revised_manifest):
                            raise ValueError("Floor revision loses verified room service")
                city, artifacts, floor_repairs = compile_with_access_replanning(city,self.simulation_backend,
                    compile_dir,select=choose_access if policy=='agent_feedback' else None,preserve_requirements=protect)
                save_json(floor_repairs, final_dir/"reports"/"floor_access_replanning.json")
                accepted = [r for r in floor_repairs if r["status"]=="accepted"]
                if accepted:
                    run.metrics.repair_rounds += 1
                    run.metrics.touch({key for r in accepted for key in r["changed_ids"]})
                recorder.event(current_stage,"floor_access_replanning",breakpoints=len(floor_repairs), accepted=len(accepted))
            else:
                artifacts = self.simulation_backend.compile(city, compile_dir)
            furnishing_coverage = None
            if verify_furnishings:
                checks = self.prototypes.verify_final(city, compile_dir / 'geometry_manifest.json', prototype_report)
                furnishing_coverage = checks['furnishing_coverage']
                run.configuration['furnishing_coverage'] = furnishing_coverage
                ledger['furnishing_coverage'] = furnishing_coverage
                save_json(checks, final_dir / 'reports' / 'prototype_compiled_acceptance.json')
                if furnishing_coverage is not None:
                    progress('精装验收', '已核对最终家具组合与使用通路',
                             verified=furnishing_coverage['verified_rooms'], target=furnishing_coverage['target_rooms'],
                             prototype_rooms=furnishing_coverage['prototype_rooms'])
            report = self.validator.validate(city)
            save_json(report.to_dict(), final_dir / "reports" / "semantic_validation.json")
            if not report.ok:
                raise RuntimeError("simulation compilation broke canonical validation")
            save_json(city, final_dir / "city.json")
            compiled_manifest = None
            if ledger['parsed_spec'].get('walking_requirements'):
                import json as manifest_json
                manifest_path = compile_dir / 'geometry_manifest.json'
                if manifest_path.is_file():
                    compiled_manifest = manifest_json.loads(manifest_path.read_bytes())
            evaluate_ledger(ledger, city, prototype_report, compiled_manifest=compiled_manifest, final=True)
            save_json(ledger, final_dir / "reports" / "requirement_acceptance.json")
            save_json(ledger, destination / "requirement" / "ledger.json")
            if ledger['status'] == 'required_route_unverified':
                recorder.event("requirement", "walking_evidence_incomplete", summary=ledger['summary'])
                recorder.finish("replan_required", "requirement")
                return ClosedLoopResult(run, destination, city, report)
            self._remember(
                MemoryRecord(
                    memory_id=f"{run_id}__outcome",
                    kind="run_outcome",
                    scope_type="city",
                    scope_id=city.id,
                    content={
                        "status": "valid",
                        "building_count": sum(1 for _ in city.iter_buildings()),
                        "floor_count": sum(1 for _ in city.iter_floors()),
                        "room_count": sum(1 for _ in city.iter_rooms()),
                    },
                    producer="closed_loop",
                    validation_status="accepted",
                    confidence=1.0,
                    run_id=run_id,
                )
            )
            run.artifacts = [
                str(path.resolve().relative_to(destination)) for path in artifacts
            ]
            recorder.event(
                current_stage,
                "simulation_compiled",
                artifact_count=len(artifacts),
                output=str(compile_dir.relative_to(destination)),
            )
            self._check_budget(recorder)

            if self.export_viewer:
                current_stage = "viewer"
                stage_started(current_stage)
                viewer_input = compile_dir if (compile_dir / "city.json").is_file() else final_dir / "city.json"
                viewer_dir = export_portable_viewer(viewer_input, destination / "viewer")
                run.artifacts.append(str(viewer_dir.relative_to(destination)))
                recorder.event(
                    current_stage,
                    "viewer_exported",
                    output=str(viewer_dir.relative_to(destination)),
                )
                self._check_budget(recorder)

            status = "repaired_success" if run.metrics.repair_rounds else "success"
            if furnishing_coverage is not None and not furnishing_coverage['target_met']:
                status = 'partial_success'
            elif furnishing_coverage is None and prototype_report and prototype_report['status'] in {'partial_reuse', 'no_compatible_rooms'}:
                status = 'partial_success'
            recorder.finish(status, "complete")
            return ClosedLoopResult(run, destination, city, report)
        except AgentGenerationError as error:
            run.metrics.consume(error.attempts)
            save_json(
                {
                    "stage": current_stage,
                    "error": str(error),
                    "attempts": [asdict(attempt) for attempt in error.attempts],
                },
                destination / "failures" / f"{current_stage}.json",
            )
            recorder.finish("model_failure", current_stage, error)
            return ClosedLoopResult(run, destination, city, report)
        except (InteriorRequirementConflict, UrbanPlanningConflict) as error:
            if isinstance(error, UrbanPlanningConflict):
                save_json({'stage': current_stage, 'reason': str(error),
                           'kind': 'urban_planning_conflict', **error.report},
                          destination/'failures'/'urban_planning.json')
            else:
                save_json({'stage':current_stage,'reason':str(error),'kind':'interior_requirement_conflict'},
                          destination/'failures'/'interior_requirements.json')
            recorder.finish('replan_required',current_stage,error)
            return ClosedLoopResult(run,destination,city,report)
        except _BudgetExceeded as error:
            recorder.finish("budget_exhausted", current_stage, error)
            return ClosedLoopResult(run, destination, city, report)
        except Exception as error:  # persist unexpected runtime/backend failures
            recorder.finish("system_failure", current_stage, error)
            return ClosedLoopResult(run, destination, city, report)

    def _check_budget(self, recorder: _RunRecorder) -> None:
        metrics = recorder.run.metrics
        budget = self.budget
        elapsed = time.monotonic() - recorder.started
        if metrics.model_calls > budget.max_total_model_calls:
            raise _BudgetExceeded("maximum total model calls exceeded")
        if budget.max_total_tokens > 0 and metrics.total_tokens > budget.max_total_tokens:
            raise _BudgetExceeded("maximum total model tokens exceeded")
        if metrics.touched_entity_count > budget.max_touched_entities:
            raise _BudgetExceeded("maximum touched entities exceeded")
        if elapsed > budget.max_wall_time_s:
            raise _BudgetExceeded("maximum wall time exceeded")

    def _remember(self, record: MemoryRecord) -> None:
        if self.memory_store is not None:
            self.memory_store.put(record)

    def _apply_adaptive_refinements(
        self,
        city: City,
        seed: int,
        destination: Path,
        run_id: str,
        run: ClosedLoopRun,
    ) -> tuple[City, dict[str, Any]]:
        """Run selective post-planning agents behind an explicit call budget."""
        if self.refinement_service is None:
            return city, {}
        if self.prototypes:
            # Prototype inventories have compiled complete-inventory evidence.
            # Replacing them via the legacy refinement path would invalidate
            # that evidence. Shared transactional refinements follow in round 2.
            return city, {"deferred_room_refinements": self.max_room_refinements,
                          "reason": "prototype_inventory_preserved_until_shared_refinement_gate"}
        summary: dict[str, Any] = {"building_refinements": 0, "room_refinements": 0}
        if self.max_building_refinements > 0:
            agent = BuildingRefinementAgent(
                self.refinement_service, model_id=self.requirement_agent.model_id,
                validator=self.validator, max_attempts=2, memory_store=self.memory_store,
                facade_asset_index=self.facade_asset_index,
            )
            candidates = select_refinement_candidates(
                city, max_candidates=self.max_building_refinements
            )
            for building_id in candidates:
                plan, attempts = agent.propose(city, building_id)
                run.metrics.consume(attempts)
                result = apply_building_refinement(
                    city, plan, validator=self.validator, attempts=attempts,
                    model_id=self.requirement_agent.model_id,
                )
                run.metrics.touch((building_id,))
                city = result.city
                summary["building_refinements"] += 1
                save_json(result.trace_dict(), destination / "refinements" / f"building_{building_id}.json")
                self._remember(MemoryRecord(
                    memory_id=f"{run_id}__building_refine__{building_id}",
                    kind="building_refinement",
                    scope_type="building",
                    scope_id=building_id,
                    content=asdict(plan),
                    world_version=_node_version(city, building_id),
                    producer="building_refinement_agent",
                    validation_status="accepted",
                    confidence=plan.confidence,
                    run_id=run_id,
                ))
        if self.max_room_refinements > 0:
            agent = RoomProgramAgent(
                self.refinement_service, model_id=self.requirement_agent.model_id,
                memory_store=self.memory_store,
                asset_resolver=self.asset_resolver,
                max_attempts=4,
                placement_seed=seed+101,
            )
            overrides = {}
            eligible = None
            if city.metadata.get("interior_scope"):
                from cityg.geometry import GeometryCompiler
                from cityg.observation import _RealizedRoomIndex
                preview = GeometryCompiler(asset_registry=(self.asset_resolver.registry
                    if self.asset_resolver else self.asset_registry)).compile(city)
                index = _RealizedRoomIndex(city, preview)
                from cityg.planning.room_envelope import metric_envelope, envelope_context
                eligible = set()
                rejected_envelopes = {}
                for b in city.iter_buildings():
                    for f in b.floors:
                        for r in f.rooms:
                            if index.frame(b,f,r) is None: continue
                            envelope=metric_envelope(b,f,r)
                            if envelope['status']=='supported': eligible.add(r.id)
                            else: rejected_envelopes[r.id]=envelope_context(envelope)
                save_json({"policy":"compiled_frame_and_metric_envelope_v2","eligible_room_ids":sorted(eligible),
                           "floor_replanning_feedback":rejected_envelopes},
                          destination / "refinements" / "room_eligibility.json")
                del preview,index
            selection = select_hero_rooms(city, max_rooms=self.max_room_refinements,
                                          eligible_room_ids=eligible)
            selected_ids = set(selection.room_ids)
            save_json(selection.to_dict(), destination / "refinements" / "room_selection.json")
            mark_room_detail(city, selected_ids, status="selected", selection=selection)
            room_index = {
                room.id: (building, floor, room)
                for building in city.iter_buildings()
                for floor in building.floors
                for room in floor.rooms
            }
            for room_id in selection.room_ids:
                target = room_index.get(room_id)
                if target is None:
                    continue
                building, floor, room = target
                try:
                    result = agent.propose(city, building, floor, room)
                    overrides[room.id] = result.program
                    mark_room_detail(city, {room.id}, status="accepted", selection=selection)
                    run.metrics.consume(result.attempts)
                    run.metrics.touch((room.id,))
                    save_json(result.raw, destination / "refinements" / f"room_{room.id}.json")
                except Exception as error:
                    run.metrics.consume(getattr(error,"attempts",()))
                    mark_room_detail(city, {room.id}, status="fallback", selection=selection)
                    save_json(
                        {"room_id": room.id, "error": f"{type(error).__name__}: {error}",
                         "attempts": [asdict(a) for a in getattr(error,"attempts",())]},
                        destination / "refinements" / f"room_{room.id}_error.json",
                    )
            if overrides:
                resolver = self.asset_resolver
                detail = FloorDetailAgent(
                    asset_resolver=resolver,
                    program_overrides=overrides,
                )
                # Hero designs are transactions over selected rooms, never a
                # reason to repopulate every other room in the city.
                detail.populate_rooms(city, set(overrides), seed=seed + 101)
                for room_id in overrides:
                    room = room_index[room_id][2]
                    status = ("gate_rejected" if room.metadata.get("room_design_rejected")
                              else room.metadata.get("room_design", {}).get("status", "accepted"))
                    mark_room_detail(city, {room_id}, status=status, selection=selection)
                # Room refinement mutates canonical InteriorObject entities.
                # Rebuild the CCWP overlay so every accepted object has a node
                # and contains relation before validation/compilation.
                city.world_program = build_world_program(
                    city,
                    producer="closed_loop_room_refinement",
                    seed=seed + 101,
                )
                summary["room_refinements"] = sum(
                    room_index[rid][2].metadata.get("refinement_status") == "accepted" for rid in overrides)
            summary["selected_room_count"] = len(selected_ids)
            summary["room_refinement_fallbacks"] = len(selected_ids) - summary.get("room_refinements", 0)
        return city, summary


def _node_version(city: City, entity_id: str) -> int:
    for node in city.world_program.nodes:
        if node.entity_id == entity_id:
            return node.version
    raise KeyError(entity_id)
