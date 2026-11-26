"""Deterministic compiler for validated hierarchical agent programs."""

from __future__ import annotations

import math
import random
from collections import Counter
from dataclasses import asdict, replace

from cityg.buildings import BuildingSelector
from cityg.planning.baseline import BaselineCityPlanner
from cityg.planning.highrise import HighRisePolicy
from cityg.planning.heights import HeightDecision, SkylinePlanner
from cityg.planning.interiors import FloorDetailAgent
from cityg.planning.orientation import StreetAlignmentPlanner
from cityg.planning.programs import FloorArchetype, FloorProfile, HierarchicalProgram
from cityg.planning.appearance import UrbanAppearanceProgram
from cityg.planning.spatial_layout import solve_spatial_floor, SpatialLayoutInfeasible
from cityg.planning.interior_frame import InteriorFrame
from cityg.schemas import (
    Bounds2D,
    Building,
    City,
    CitySpec,
    Door,
    Floor,
    Point2D,
    Room,
)


class ProgrammedCityPlanner(BaselineCityPlanner):
    """Compile small agent choices without delegating coordinates or topology."""

    def __init__(
        self,
        program: HierarchicalProgram,
        floor_detail_agent: FloorDetailAgent | None = None,
        appearance_program: UrbanAppearanceProgram | None = None,
        floor_program_overrides: dict[str, FloorProfile] | None = None,
        building_selector: BuildingSelector | None = None,
        interior_targets: dict | None = None,
        archetype_pins: dict | None = None,
    ) -> None:
        super().__init__(
            floor_detail_agent=floor_detail_agent,
            building_selector=building_selector,
        )
        self.program = program
        self.appearance_program = appearance_program
        self.floor_program_overrides = dict(floor_program_overrides or {})
        self.interior_targets = dict(interior_targets or {})
        self.archetype_pins = dict(archetype_pins or {})

    def plan(self, spec: CitySpec) -> City:
        self.program.validate(spec)
        if spec.road_pattern == 'landscape_adaptive' and self.program.urban.road_pattern != spec.road_pattern:
            raise ValueError('Urban Agent must preserve landscape_adaptive morphology intent')
        zone_map = {
            f"zone_{index:02d}": zone for index, zone in enumerate(spec.zones)
        }
        ordered_spec = replace(
            spec,
            zones=tuple(zone_map[key] for key in self.program.urban.district_order),
            road_pattern=self.program.urban.road_pattern,
        )
        city = super().plan(ordered_spec)
        adaptive_floor_program = any(
            profile.space_archetypes for profile in self.program.floor.profiles
        )
        city.metadata.update(
            {
                "planner": (
                    "hierarchical_program_v2"
                    if adaptive_floor_program
                    else "hierarchical_program_v1"
                ),
                "hierarchical_program": asdict(self.program),
                "building_floor_program_overrides": {
                    building_id: asdict(profile)
                    for building_id, profile in sorted(
                        self.floor_program_overrides.items()
                    )
                },
            }
        )
        if self.appearance_program is not None:
            city.metadata["urban_appearance_program"] = self.appearance_program.to_dict()
            city.metadata["appearance_planner"] = "llm_appearance_program_v1"
        spatial_reports = [f.metadata["spatial_layout"] for b in city.iter_buildings()
                           for f in b.floors if "spatial_layout" in f.metadata]
        if spatial_reports:
            city.metadata["spatial_layout_summary"] = {
                "requested_floors": len(spatial_reports),
                "accepted_floors": sum(r["status"] == "accepted" for r in spatial_reports),
                "fallback_floors": sum(r["status"] == "fallback" for r in spatial_reports),
                "accepted_families": dict(Counter(r["family"] for r in spatial_reports if r["status"] == "accepted")),
                "fallback_reasons": dict(Counter(r["reason"] for r in spatial_reports if r["status"] == "fallback")),
            }
        return city

    def _make_blocks(
        self, spec: CitySpec, x_roads: list[float], y_roads: list[float]
    ) -> list[Bounds2D]:
        blocks = super()._make_blocks(spec, x_roads, y_roads)
        if self.program.urban.block_traversal == "column_major":
            return sorted(blocks, key=lambda item: (item.center.x, item.center.y))
        return blocks

    def _preferred_entrance_side(self, function: str) -> str | None:
        return self.program.building.for_function(function).entrance_side

    def _skyline_program(self, spec: CitySpec):
        return self.program.skyline

    def _make_building(
        self,
        spec: CitySpec,
        rng: random.Random,
        index: int,
        function: str,
        parcel_bounds: Bounds2D,
        frontage_sides: tuple[str, ...] = ("west", "east", "north", "south"),
        urban_block_id: str = "urban_block_000",
        cluster_size: int = 1,
        site_index: int = 0,
        height_decision: HeightDecision | None = None,
    ) -> Building:
        profile = self.program.building.for_function(function)
        floor_profile = self.floor_program_overrides.get(
            f"building_{index:03d}"
        ) or self.program.floor.for_function(function)
        entrance_side = (
            profile.entrance_side
            if profile.entrance_side in frontage_sides
            else frontage_sides[(index + spec.seed) % len(frontage_sides)]
        )
        footprint = self._layout_footprint(
            spec,
            rng,
            index,
            function,
            parcel_bounds,
            entrance_side,
        )
        building_id = f"building_{index:03d}"
        from cityg.planning.urban_spatial import fit_building
        footprint = fit_building(spec, index, function, getattr(self, '_active_zone_name', ''),
                                 parcel_bounds, entrance_side, footprint)
        interior_target = self.interior_targets.get(building_id)
        interior_frame=InteriorFrame((interior_target or {}).get('circulation_axis','x'))
        if interior_target:
            # Select the entry before constructing any rooms/doors. The site
            # footprint above uses the original policy, preserving parcel/RNG
            # decisions and every other building's footprint.
            entrance_side = interior_target['entrance_side']
            if entrance_side not in frontage_sides:
                raise ValueError('Reserved interior entry has no street frontage')
            if interior_target.get('footprint'):
                proposed = Bounds2D(**interior_target['footprint'])
                permitted = footprint
                growth = interior_target.get('verified_site_growth')
                if growth:
                    if footprint != Bounds2D(**growth['original']):
                        raise ValueError('Site changed since capacity verification')
                    permitted = Bounds2D(**growth['bounds'])
                    if not parcel_bounds.inset(spec.parcel_setback_m).contains_bounds(permitted,tolerance=1e-5):
                        raise ValueError('Expanded site no longer inside buildable parcel')
                if not permitted.contains_bounds(proposed, tolerance=1e-5):
                    raise ValueError('Reserved interior plate exceeds its buildable site')
                footprint = proposed
        floor_count = self._floor_count(
            profile.floor_policy, spec, rng, index, height_decision
        )
        highrise = HighRisePolicy.is_highrise(floor_count)
        landmark = (
            bool(height_decision.landmark)
            if height_decision is not None
            else False
        )
        selection = self._select_building_archetype(
            building_id=building_id,
            function=function,
            footprint=footprint,
            floor_count=floor_count,
            highrise=highrise,
            landmark=landmark,
            prototype_id=profile.prototype_id,
            preferred_ids=((self.archetype_pins[building_id],) if building_id in self.archetype_pins
                           else profile.archetype_palette),
        )
        if building_id in self.archetype_pins and selection.archetype.archetype_id != self.archetype_pins[building_id]:
            raise ValueError('Pinned archetype no longer satisfies the realized building')
        highrise_palette = profile.highrise_massing_palette
        highrise_variant = HighRisePolicy.massing_variant(
            building_id=building_id,
            floor_count=floor_count,
            function=function,
            landmark=landmark,
            seed=spec.seed,
            palette=highrise_palette,
        )
        if selection.archetype.massing_variant and highrise:
            # The selected archetype is part of the floor-plate contract.  It
            # must be applied before Building-specific Floor Agent planning.
            highrise_variant = selection.archetype.massing_variant
        orientation = StreetAlignmentPlanner.plan(
            entrance_side=entrance_side,
            function=function,
            centrality=(
                height_decision.centrality
                if height_decision is not None
                else SkylinePlanner._centrality(spec, parcel_bounds.center)
            ),
            cluster_size=cluster_size,
            highrise=highrise,
            landmark=landmark,
            layout_style=spec.layout_style,
            building_index=index,
            seed=spec.seed,
        )
        podium_floors = HighRisePolicy.podium_floors(floor_count)
        floor_footprints = [
            HighRisePolicy.floor_plate_bounds(
                footprint,
                floor_count,
                level,
                highrise_variant,
                orientation_deg=orientation.orientation_deg,
            )
            for level in range(floor_count)
        ]
        # Vertical circulation is a shared geometric invariant, so derive it
        # from the intersection of every realized floor plate instead of the
        # larger parcel-level building footprint. Offset/setback towers remain
        # free to change silhouette while stairs and elevators stay inside the
        # central corridor on every served level.
        connector_footprint = Bounds2D(
            max(item.min_x for item in floor_footprints),
            max(item.min_y for item in floor_footprints),
            min(item.max_x for item in floor_footprints),
            min(item.max_y for item in floor_footprints),
        )
        corridor_depth = min(
            self._corridor_depth(interior_frame.bounds(item).depth, floor_profile.corridor_ratio)
            for item in floor_footprints
        )
        # Keep the public entrance on the street-facing boundary of the
        # building footprint. The podium shell may be inset, but access and
        # frontage contracts are expressed against this urban footprint.
        entrance = self._entrance(footprint, entrance_side)
        connectors = HighRisePolicy.connectors(
            building_id, floor_count, interior_frame.bounds(connector_footprint), corridor_depth
        )
        core_bounds = self._connector_core_bounds(
            interior_frame.bounds(connector_footprint), connectors, corridor_depth
        )
        core_bounds=interior_frame.bounds(core_bounds)
        if interior_frame.axis=='y':
            for connector in connectors:
                connector.bounds=interior_frame.bounds(connector.bounds)
                connector.metadata['stair_run_axis']='x'
        floors: list[Floor] = []
        for level in range(floor_count):
            floor_footprint = floor_footprints[level]
            vertical_zone = floor_profile.zone_for_level(level)
            role = (
                vertical_zone.role
                if vertical_zone is not None
                else self._floor_program_role(level, floor_count, podium_floors)
            )
            archetype = (
                vertical_zone.archetype
                if vertical_zone is not None
                else floor_profile.for_role(role)
            )
            if archetype is None or spec.room_count_strategy == "fixed":
                room_count = spec.rooms_per_floor
                functions = (
                    archetype.room_function_cycle
                    if archetype is not None
                    else floor_profile.room_function_cycle
                )
                unit_group_size = (
                    archetype.unit_group_size if archetype is not None else 1
                )
                space_contract = (
                    {
                        "source": "fixed_rooms_per_floor",
                        "role": role,
                        "realized_room_count": room_count,
                        "unit_group_size": unit_group_size,
                        "max_room_depth_m": archetype.max_room_depth_m if archetype else None,
                        "max_room_aspect_ratio": archetype.max_room_aspect_ratio if archetype else None,
                        "room_function_cycle": list(functions),
                    }
                    if archetype is not None
                    else None
                )
            else:
                room_count, space_contract = self._resolve_room_count(
                    interior_frame.bounds(floor_footprint),
                    floor_profile.corridor_ratio,
                    archetype,
                )
                functions = archetype.room_function_cycle
                unit_group_size = archetype.unit_group_size
            if highrise and floor_footprint.area < footprint.area * 0.92:
                capacity_archetype = archetype or FloorArchetype(
                    role=role,
                    preferred_room_count=max(1, room_count),
                    min_room_count=1,
                    max_room_count=max(1, room_count),
                    target_room_area_m2=36.0,
                    min_room_width_m=3.0,
                    room_function_cycle=functions,
                    layout_template="tower_core",
                )
                plate_plan = self._room_band_plan(
                    floor_footprint,
                    floor_profile.corridor_ratio,
                    capacity_archetype,
                    target_room_count=room_count,
                )
                capacity = max(1, int(plate_plan["geometric_capacity"]))
                if room_count > capacity:
                    room_count = capacity
                    space_contract = dict(space_contract or {})
                    space_contract.update(
                        {
                            "source": "highrise_massing_capacity_v1",
                            "capacity_limited": True,
                            "realized_room_count": room_count,
                            "massing_variant": highrise_variant,
                            "realized_plate_area_m2": round(floor_footprint.area, 3),
                            "realized_plate_bounds": asdict(floor_footprint),
                            "geometric_capacity": capacity,
                        }
                    )
            floors.append(
                self._make_programmed_floor(
                    building_id,
                    level,
                    floor_footprint,
                    floor_profile.corridor_ratio,
                    functions,
                    room_count,
                    entrance,
                    building_function=function,
                    program_role=role,
                    unit_group_size=unit_group_size,
                    space_contract=space_contract,
                    archetype=archetype,
                    core_bounds=core_bounds,
                    circulation_axis=interior_frame.axis,
                    vertical_zone=(
                        {
                            "zone_id": vertical_zone.zone_id,
                            "start_level": vertical_zone.start_level,
                            "end_level": vertical_zone.end_level,
                            "role": vertical_zone.role,
                            "use_type": vertical_zone.use_type,
                        }
                        if vertical_zone is not None
                        else None
                    ),
                    floor_plate_contract={
                        "spatial_footprint_supported": highrise or selection.archetype.massing_style == "bar",
                        "fixed_room_count": spec.rooms_per_floor if spec.room_count_strategy == "fixed" else None,
                        "source": "highrise_massing_outline_v1" if highrise else "full_building_footprint",
                        "massing_variant": highrise_variant,
                        "bounds": asdict(floor_footprint),
                        "area_m2": round(floor_footprint.area, 3),
                    },
                )
            )

        reuse_groups = HighRisePolicy.annotate_typical_floors(
            building_id, floors, podium_floors
        )
        building = Building(
            id=building_id,
            name=f"{function.replace('_', ' ').title()} {index + 1}",
            function=function,
            footprint=footprint,
            entrance=entrance,
            floors=floors,
            vertical_connectors=connectors,
            metadata={
                "lod_policy": "shell_then_active_floor",
                "generated": True,
                "prototype_id": profile.prototype_id,
                "floor_policy": profile.floor_policy,
                "entrance_side": entrance_side,
                "requested_entrance_side": profile.entrance_side,
                "available_frontages": list(frontage_sides),
                "urban_block_id": urban_block_id,
                "cluster_size": cluster_size,
                "cluster_site_index": site_index,
                "massing_style": selection.archetype.massing_style,
                "orientation_deg": orientation.orientation_deg,
                "orientation_contract": orientation.to_metadata(),
                "interior_core_policy": (
                    "fire_separated_tower_core"
                    if highrise
                    else "rectangular_navigation_core"
                ),
                "highrise": HighRisePolicy.metadata(
                    floor_count,
                    reuse_groups,
                    massing_variant=highrise_variant,
                    massing_palette=highrise_palette,
                ),
                "floor_plate_contract": HighRisePolicy.floor_plate_contract(
                    footprint,
                    floor_count,
                    highrise_variant,
                    orientation_deg=orientation.orientation_deg,
                ),
                "floor_layout": floor_profile.layout,
                "corridor_ratio": floor_profile.corridor_ratio,
                "vertical_zoning": {
                    "source": (
                        "building_specific_floor_agent_v1"
                        if floor_profile.vertical_zones
                        else "legacy_highrise_role_policy"
                    ),
                    "zones": [asdict(zone) for zone in floor_profile.vertical_zones],
                },
                "height_contract": {
                    **(
                        height_decision.to_metadata()
                        if height_decision is not None
                        else {
                            "height_zone": "unconstrained",
                            "height_role": SkylinePlanner._height_role(
                                floor_count, False
                            ),
                            "min_floors": spec.min_floors,
                            "max_floors": spec.max_floors,
                            "recommended_floors": floor_count,
                            "centrality": 0.0,
                            "highrise": False,
                            "landmark": False,
                        }
                    ),
                    "planner": (
                        "llm_skyline_program_v1"
                        if height_decision is not None
                        and height_decision.source == "llm_skyline_program"
                        else (
                            "zoned_skyline_v1"
                            if spec.height_strategy == "zoned_skyline"
                            else "uniform_random_v1"
                        )
                    ),
                    "realized_floors": floor_count,
                },
            },
        )
        building.metadata.update(selection.to_metadata())
        if interior_target:
            if highrise or selection.archetype.massing_style != 'bar' or abs(orientation.orientation_deg) > 1e-6:
                raise ValueError('Reserved interior building lost its rectangular capability')
            building.metadata['interior_layout_contract'] = dict(interior_target)
            building.metadata['massing_signature'] += '|full_plate_interior'
        building.metadata["semantic_archetype_palette"] = list(
            profile.archetype_palette
        )
        building.metadata["semantic_design_language_palette"] = list(profile.design_language_palette)
        building.metadata["semantic_envelope_preference"] = dict(profile.envelope_preference)
        if profile.roof_profile_palette:
            from cityg.geometry.roof_programs import roof_seed
            building.metadata['roof_program']={
                'profile':profile.roof_profile_palette[roof_seed(building.id)%len(profile.roof_profile_palette)],
                'source':'building_agent_profile_palette'}
        return building

    @staticmethod
    def _floor_count(
        policy: str,
        spec: CitySpec,
        rng: random.Random,
        index: int,
        decision: HeightDecision | None = None,
    ) -> int:
        if decision is not None:
            if decision.landmark:
                return decision.recommended_floors
            minimum = decision.min_floors
            maximum = decision.max_floors
            recommended = decision.recommended_floors
            # The skyline planner owns the vertical composition. A building
            # profile may express a modest preference, but must not collapse an
            # entire functional zone onto one edge of its permitted range.
            span = maximum - minimum
            nudge = max(1, round(span * 0.12)) if span else 0
            if policy == "minimum":
                realized = recommended - nudge
            elif policy == "maximum":
                realized = recommended + nudge
            elif policy == "midpoint":
                midpoint = (minimum + maximum) / 2
                realized = round(0.75 * recommended + 0.25 * midpoint)
            elif policy == "alternating":
                realized = recommended + (-nudge if index % 2 == 0 else nudge)
            else:
                realized = recommended
            return min(maximum, max(minimum, realized))
        else:
            minimum = spec.min_floors
            maximum = spec.max_floors
            recommended = rng.randint(minimum, maximum)
        if policy == "minimum":
            return minimum
        if policy == "midpoint":
            return (minimum + maximum) // 2
        if policy == "maximum":
            return maximum
        if policy == "alternating":
            return minimum if index % 2 == 0 else maximum
        return recommended

    @staticmethod
    def _entrance(footprint: Bounds2D, side: str) -> Point2D:
        if side == "east":
            return Point2D(footprint.max_x, footprint.center.y)
        if side == "north":
            return Point2D(footprint.center.x, footprint.max_y)
        if side == "south":
            return Point2D(footprint.center.x, footprint.min_y)
        return Point2D(footprint.min_x, footprint.center.y)

    @staticmethod
    def _corridor_depth(footprint_depth: float, corridor_ratio: float) -> float:
        """Keep circulation realistic instead of consuming most of a deep plate."""

        return min(
            max(2.4, footprint_depth * corridor_ratio),
            5.0,
            footprint_depth * 0.25,
        )

    @staticmethod
    def _connector_core_bounds(
        footprint: Bounds2D, connectors: list, corridor_depth: float
    ) -> Bounds2D:
        """Return one stable core envelope shared by every building floor."""

        if connectors:
            return Bounds2D(
                min(item.bounds.min_x for item in connectors),
                min(item.bounds.min_y for item in connectors),
                max(item.bounds.max_x for item in connectors),
                max(item.bounds.max_y for item in connectors),
            )
        width = min(max(3.0, footprint.width * 0.16), 8.0)
        depth = min(max(2.4, corridor_depth * 0.75), corridor_depth)
        return Bounds2D(
            footprint.center.x - width / 2,
            footprint.center.y - depth / 2,
            footprint.center.x + width / 2,
            footprint.center.y + depth / 2,
        )

    @staticmethod
    def _layout_template(
        building_function: str,
        program_role: str,
        archetype: FloorArchetype | None,
    ) -> str:
        requested = archetype.layout_template if archetype is not None else "auto"
        if requested != "auto":
            return requested
        if program_role == "podium":
            return "podium_core"
        if building_function == "residential":
            return "residential_units"
        if building_function == "commercial":
            return "commercial_retail" if program_role == "ground" else "office_core"
        if building_function == "mixed_use":
            return (
                "commercial_retail"
                if program_role in {"ground", "podium"}
                else "tower_core"
            )
        if building_function == "industrial":
            return "open_plan"
        return "tower_core" if program_role in {"typical", "top"} else "podium_core"

    @staticmethod
    def _core_policy(layout_template: str, program_role: str) -> str:
        if layout_template in {"tower_core", "office_core", "residential_units"}:
            return "compact_shared_vertical_core"
        if layout_template in {"podium_core", "commercial_retail"}:
            return "public_lobby_with_service_core"
        if layout_template == "open_plan":
            return "central_service_core"
        return "aligned_circulation_core"

    @staticmethod
    def _space_kind(function: str, layout_template: str) -> str:
        if function == "open_office" or layout_template == "open_plan":
            return "open_plan"
        if function in {"reception", "service_hall", "waiting_room"}:
            return "shared_open_space"
        if function == "shop":
            return "retail_bay"
        if layout_template == "residential_units":
            return "dwelling_room"
        if function in {"storage", "restroom", "bathroom", "service_room", "equipment_room"}:
            return "support_space"
        return "enclosed_room"

    @staticmethod
    def _semantic_cycle(
        functions: tuple[str, ...], layout_template: str
    ) -> tuple[str, ...]:
        """Put template-defining uses first without discarding the agent's catalog."""

        priorities = {
            "residential_units": (
                "living_room", "bedroom", "kitchen", "bathroom", "study", "storage"
            ),
            "office_core": (
                "open_office", "office", "meeting_room", "break_room", "restroom", "storage"
            ),
            "commercial_retail": (
                "shop", "shop", "service_room", "storage", "restroom", "reception"
            ),
            "podium_core": (
                "reception", "shop", "service_hall", "waiting_room", "restroom", "storage"
            ),
            "open_plan": (
                "open_office", "workshop", "service_hall", "office", "storage", "restroom"
            ),
        }
        source = tuple(functions)
        ordered = [item for item in priorities.get(layout_template, ()) if item in source]
        ordered.extend(item for item in source if item not in ordered)
        return tuple(ordered or source)

    @classmethod
    def _room_band_plan(
        cls,
        footprint: Bounds2D,
        corridor_ratio: float,
        archetype: FloorArchetype,
        target_room_count: int | None = None,
    ) -> dict:
        """Choose the number/depth of room bands on each side of a corridor.

        A deep plate is split into alternating room and secondary-corridor
        bands.  This keeps daylight-facing rooms within the LLM's depth/aspect
        contract without globally enlarging the building footprint.
        """

        central_depth = cls._corridor_depth(footprint.depth, corridor_ratio)
        side_depth = max(0.0, (footprint.depth - central_depth) / 2.0)
        secondary_depth = min(3.5, max(2.4, central_depth * 0.7))
        max_depth = max(4.0, archetype.max_room_depth_m)
        min_width = max(
            archetype.min_room_width_m,
            max_depth * 0.0,
        )
        aspect = max(1.4, archetype.max_room_aspect_ratio)
        minimum_bands = max(
            1,
            math.ceil((side_depth + secondary_depth) / (max_depth + secondary_depth)),
        )
        minimum_bands = min(4, minimum_bands)
        selected = min(4, minimum_bands)
        capacity = 0
        room_depth = side_depth
        for bands in range(minimum_bands, 5):
            room_depth = (
                side_depth - secondary_depth * (bands - 1)
            ) / max(1, bands)
            required_width = max(min_width, room_depth / aspect)
            per_band_capacity = max(1, math.floor(footprint.width / required_width))
            capacity = per_band_capacity * bands * 2
            selected = bands
            if target_room_count is None or capacity >= target_room_count:
                break
        room_depth = max(1.8, room_depth)
        required_width = max(min_width, room_depth / aspect)
        per_band_capacity = max(1, math.floor(footprint.width / required_width))
        capacity = per_band_capacity * selected * 2
        return {
            "central_depth": central_depth,
            "secondary_depth": secondary_depth,
            "side_depth": side_depth,
            "bands_per_side": selected,
            "room_depth": room_depth,
            "per_band_capacity": per_band_capacity,
            "geometric_capacity": capacity,
            "required_room_width": required_width,
            "max_room_depth_m": archetype.max_room_depth_m,
            "max_room_aspect_ratio": archetype.max_room_aspect_ratio,
        }

    @staticmethod
    def _distribute_count(total: int, buckets: int) -> list[int]:
        base, remainder = divmod(max(0, total), max(1, buckets))
        return [base + (index < remainder) for index in range(max(1, buckets))]

    def _make_programmed_floor(
        self,
        building_id: str,
        level: int,
        footprint: Bounds2D,
        corridor_ratio: float,
        functions: tuple[str, ...],
        room_count: int,
        entrance: Point2D,
        *,
        building_function: str,
        program_role: str,
        unit_group_size: int = 1,
        space_contract: dict | None = None,
        archetype: FloorArchetype | None = None,
        core_bounds: Bounds2D | None = None,
        vertical_zone: dict | None = None,
        floor_plate_contract: dict | None = None,
        circulation_axis: str = 'x',
    ) -> Floor:
        frame=InteriorFrame(circulation_axis)
        if frame.axis=='y':
            return frame.floor(self._make_programmed_floor(
                building_id,level,frame.bounds(footprint),corridor_ratio,functions,room_count,
                frame.point(entrance),building_function=building_function,program_role=program_role,
                unit_group_size=unit_group_size,space_contract=frame.metadata(space_contract),
                archetype=archetype,core_bounds=frame.bounds(core_bounds) if core_bounds else None,
                vertical_zone=vertical_zone,floor_plate_contract=frame.metadata(floor_plate_contract)))
        floor_id = f"{building_id}_floor_{level:02d}"
        spatial_failure = None
        if archetype is not None and archetype.spatial_program is not None:
            try:
                if (floor_plate_contract or {}).get("spatial_footprint_supported") is False:
                    raise SpatialLayoutInfeasible("irregular low-rise massing requires a polygon/wing connectivity solver; legacy layout retained")
                spatial = solve_spatial_floor(
                    archetype.spatial_program, floor_id=floor_id, level=level,
                    height=self.floor_height_m, footprint=footprint,
                    corridor_depth=self._corridor_depth(footprint.depth, corridor_ratio),
                    core_bounds=core_bounds, entrance=entrance,
                    min_width=archetype.min_room_width_m,
                    max_aspect=archetype.max_room_aspect_ratio,
                    max_depth=archetype.max_room_depth_m,
                )
                count = len(spatial.rooms) - 1
                if not archetype.min_room_count <= count <= archetype.max_room_count:
                    raise SpatialLayoutInfeasible("realized spatial count violates archetype count range")
                if (space_contract or {}).get("source") == "fixed_rooms_per_floor" and count != room_count:
                    raise SpatialLayoutInfeasible("spatial count violates fixed rooms_per_floor")
                fixed = (floor_plate_contract or {}).get("fixed_room_count")
                if fixed is not None and count != fixed:
                    raise SpatialLayoutInfeasible("spatial count violates fixed rooms_per_floor")
                spatial.metadata.update({
                    "program_role": program_role, "vertical_role": program_role,
                    "vertical_zone": vertical_zone,
                    "vertical_zone_id": (vertical_zone or {}).get("zone_id"),
                    "vertical_use_type": (vertical_zone or {}).get("use_type"),
                    "space_program": {**(space_contract or {}), "source": "spatial_requirements_v1", "realized_room_count": count},
                    "realized_floor_plate": floor_plate_contract,
                    "floor_plate_zone": "podium" if program_role in {"ground", "podium"} else "tower",
                    "core_bounds": asdict(core_bounds) if core_bounds else None,
                    "core_policy": self._core_policy(self._layout_template(building_function, program_role, archetype), program_role),
                    "corridor_count": 1,
                })
                for room in spatial.rooms:
                    room.metadata.update(floor_program_role=program_role,
                                         vertical_zone_id=(vertical_zone or {}).get("zone_id"))
                return spatial
            except SpatialLayoutInfeasible as exc:
                spatial_failure = {"status": "fallback", "version": 1,
                                   "family": archetype.spatial_program.family,
                                   "reason": str(exc), "requirements": asdict(archetype.spatial_program),
                                   "requirements_satisfied": False}
        # Use a bounded central corridor and add parallel corridors only when
        # the plate is too deep for the room archetype.
        plan = self._room_band_plan(
            footprint,
            corridor_ratio,
            archetype or FloorArchetype(
                role=program_role if program_role in {"ground", "podium", "typical", "top"} else "typical",
                preferred_room_count=max(1, room_count),
                min_room_count=1,
                max_room_count=max(1, room_count),
                target_room_area_m2=24.0,
                min_room_width_m=2.8,
                room_function_cycle=functions,
            ),
            target_room_count=room_count,
        )
        layout_template = self._layout_template(
            building_function, program_role, archetype
        )
        functions = self._semantic_cycle(functions, layout_template)
        core_policy = self._core_policy(layout_template, program_role)
        corridor_depth = plan["central_depth"]
        # Keep the central circulation band aligned with the stable vertical
        # core.  A rotated/offset tower plate can have a different AABB center
        # from the original building footprint; using ``footprint.center`` in
        # that case leaves stairs/elevators just outside the corridor on every
        # floor even though they are inside the realized tower envelope.
        corridor_center_y = footprint.center.y
        if core_bounds is not None:
            candidate_y = core_bounds.center.y
            if footprint.min_y <= candidate_y <= footprint.max_y:
                corridor_center_y = candidate_y
                # A podium and its tower plate may have different centers.
                # Keep the corridor aligned with the stable vertical core,
                # while shrinking the symmetric room bands to the smaller
                # side of this realized floor plate.
                available_side_depth = min(
                    corridor_center_y
                    - footprint.min_y
                    - corridor_depth / 2,
                    footprint.max_y
                    - corridor_center_y
                    - corridor_depth / 2,
                )
                if available_side_depth > 0:
                    plan["side_depth"] = min(
                        plan["side_depth"], available_side_depth
                    )
        corridor = Bounds2D(
            footprint.min_x,
            corridor_center_y - corridor_depth / 2,
            footprint.max_x,
            corridor_center_y + corridor_depth / 2,
        )
        corridor_id = f"{floor_id}_corridor"
        rooms = [
            Room(
                corridor_id,
                "Main corridor",
                "corridor",
                corridor,
                metadata={
                    "floor_program_role": program_role,
                    "space_kind": "circulation",
                    "corridor_role": "central",
                    "core_policy": core_policy,
                    "core_bounds": asdict(core_bounds) if core_bounds else None,
                },
            )
        ]
        doors: list[Door] = []
        side_bands: dict[str, list[tuple[str, float, float]]] = {"north": [], "south": []}
        north_count = math.ceil(room_count / 2)
        south_count = room_count - north_count
        requested_bands = plan["bands_per_side"]
        side_band_counts = {
            "north": min(requested_bands, max(1, north_count)),
            "south": min(requested_bands, max(1, south_count)),
        }
        secondary_depth = plan["secondary_depth"]
        for side in ("north", "south"):
            bands = side_band_counts[side]
            room_depth = (
                plan["side_depth"] - secondary_depth * (bands - 1)
            ) / max(1, bands)
            cursor = corridor.max_y if side == "north" else corridor.min_y
            for band_index in range(bands):
                if side == "north":
                    min_y, max_y = cursor, cursor + room_depth
                    cursor = max_y
                else:
                    min_y, max_y = cursor - room_depth, cursor
                    cursor = min_y
                band_corridor_id = (
                    corridor_id
                    if band_index == 0
                    else f"{floor_id}_corridor_{side}_{band_index:02d}"
                )
                side_bands[side].append((band_corridor_id, min_y, max_y))
                if band_index < bands - 1:
                    if side == "north":
                        min_y, max_y = cursor, cursor + secondary_depth
                        cursor = max_y
                    else:
                        min_y, max_y = cursor - secondary_depth, cursor
                        cursor = min_y
                    secondary_id = f"{floor_id}_corridor_{side}_{band_index + 1:02d}"
                    rooms.append(
                        Room(
                            secondary_id,
                            f"{side.title()} secondary corridor {band_index + 1}",
                            "corridor",
                            Bounds2D(footprint.min_x, min_y, footprint.max_x, max_y),
                            metadata={
                                "floor_program_role": program_role,
                                "space_kind": "circulation",
                                "corridor_role": "secondary",
                                "corridor_side": side,
                                "corridor_band_index": band_index + 1,
                            },
                        )
                    )
        room_index = 0
        for side, count in (("north", north_count), ("south", south_count)):
            band_counts = self._distribute_count(count, len(side_bands[side]))
            previous_band_rooms: list[Room] = []
            for band_index, band_count in enumerate(band_counts):
                corridor_for_band, min_y, max_y = side_bands[side][band_index]
                room_width = footprint.width / max(1, band_count)
                current_band_rooms: list[Room] = []
                for side_index in range(band_count):
                    bounds = Bounds2D(
                        footprint.min_x + side_index * room_width,
                        min_y,
                        footprint.min_x + (side_index + 1) * room_width,
                        max_y,
                    )
                    room_id = f"{floor_id}_room_{room_index:02d}"
                    function_offset = room_index + (0 if space_contract else level)
                    function = functions[function_offset % len(functions)]
                    group_index = room_index // max(1, unit_group_size)
                    group_id = f"{floor_id}_group_{group_index:02d}"
                    room = Room(
                        room_id,
                        function.replace("_", " ").title(),
                        function,
                        bounds,
                        metadata={
                            "floor_program_role": program_role,
                            "vertical_zone_id": (
                                vertical_zone.get("zone_id") if vertical_zone else None
                            ),
                            "space_group_id": group_id,
                            "unit_id": (
                                group_id if building_function == "residential" else None
                            ),
                            "tenant_id": (
                                group_id
                                if building_function in {"commercial", "mixed_use"}
                                else None
                            ),
                            "space_group_type": (
                                "dwelling_unit"
                                if building_function == "residential"
                                and unit_group_size > 1
                                else (
                                    "tenant_or_department"
                                    if unit_group_size > 1
                                    else "individual_space"
                                )
                            ),
                            "space_group_size": unit_group_size,
                            "programmed_room_index": room_index,
                            "layout_template": layout_template,
                            "space_kind": self._space_kind(function, layout_template),
                            "open_plan": self._space_kind(function, layout_template)
                            in {"open_plan", "shared_open_space"},
                            "requires_facade": True,
                            "room_geometry_contract": {
                                "max_room_depth_m": plan["max_room_depth_m"],
                                "max_room_aspect_ratio": plan["max_room_aspect_ratio"],
                            },
                        },
                    )
                    rooms.append(room)
                    door_y = bounds.min_y if side == "north" else bounds.max_y
                    doors.append(
                        Door(
                            id=f"{room_id}_door",
                            room_a_id=room_id,
                            room_b_id=corridor_for_band,
                            position=Point2D(bounds.center.x, door_y),
                        )
                    )
                    current_band_rooms.append(room)
                    room_index += 1
                # Secondary corridors are connected through the room band they
                # border. This preserves a connected navigation graph without
                # inventing coordinates outside the floor plate.
                if band_index > 0 and previous_band_rooms:
                    bridge = previous_band_rooms[0]
                    bridge_y = (
                        bridge.bounds.max_y
                        if side == "north"
                        else bridge.bounds.min_y
                    )
                    doors.append(
                        Door(
                            id=f"{floor_id}_{side}_secondary_{band_index}_bridge",
                            room_a_id=bridge.id,
                            room_b_id=corridor_for_band,
                            position=Point2D(bridge.bounds.center.x, bridge_y),
                        )
                    )
                previous_band_rooms = current_band_rooms
        if level == 0:
            doors.append(
                Door(
                    id=f"{floor_id}_entrance",
                    room_a_id=corridor_id,
                    room_b_id=None,
                    position=entrance,
                    width_m=1.6,
                    door_type="exterior",
                )
            )
        rooms, doors, split_stats = self._split_oversized_rooms(
            floor_id,
            rooms,
            doors,
            archetype,
        )
        return Floor(
            id=floor_id,
            level=level,
            elevation_m=level * self.floor_height_m,
            height_m=self.floor_height_m,
            rooms=rooms,
            doors=doors,
            metadata={
                "program_role": program_role,
                "vertical_role": program_role,
                "vertical_zone": vertical_zone,
                "vertical_zone_id": (
                    vertical_zone.get("zone_id") if vertical_zone else None
                ),
                "vertical_use_type": (
                    vertical_zone.get("use_type") if vertical_zone else None
                ),
                "space_program": space_contract
                or {
                    "source": "legacy_rooms_per_floor",
                    "realized_room_count": room_count,
                },
                "layout_topology": (
                    "multi_corridor_bands"
                    if any(len(items) > 1 for items in side_bands.values())
                    else "double_loaded_corridor"
                ),
                "corridor_count": 1 + sum(max(0, len(items) - 1) for items in side_bands.values()),
                "room_band_plan": plan,
                "layout_template": layout_template,
                "floor_plate_zone": (
                    "podium" if program_role in {"ground", "podium"} else "tower"
                ),
                "realized_floor_plate": floor_plate_contract,
                "core_policy": core_policy,
                "core_bounds": asdict(core_bounds) if core_bounds else None,
                "large_space_postprocess": split_stats,
                **({"spatial_layout": spatial_failure} if spatial_failure else {}),
            },
        )

    @staticmethod
    def _split_oversized_rooms(
        floor_id: str,
        rooms: list[Room],
        doors: list[Door],
        archetype: FloorArchetype | None,
    ) -> tuple[list[Room], list[Door], dict]:
        """Split oversized enclosed bays while preserving intentional open plans.

        The band planner already controls room depth. This pass handles the
        remaining orthogonal case: a low-count program can produce one very
        wide enclosed room. Open offices and public halls are retained and
        explicitly marked instead of being fragmented into arbitrary cells.
        """

        if archetype is None:
            return rooms, doors, {
                "policy": "disabled_without_archetype",
                "split_source_room_count": 0,
                "created_room_count": 0,
                "preserved_open_space_count": 0,
            }
        max_aspect = archetype.max_room_aspect_ratio
        min_width = archetype.min_room_width_m
        # A target area is a semantic average, not a hard maximum.  Use a
        # generous upper bound so a normal lobby/office bay is not fragmented
        # merely because the realized plate is larger than the estimate.
        max_enclosed_area = max(120.0, archetype.target_room_area_m2 * 5.0)
        replacements: dict[str, list[Room]] = {}
        preserved_open = 0
        output: list[Room] = []
        for room in rooms:
            if room.function == "corridor":
                output.append(room)
                continue
            metadata = dict(room.metadata)
            space_kind = metadata.get("space_kind", "enclosed_room")
            width = room.bounds.width
            depth = room.bounds.depth
            aspect = max(width, depth) / max(min(width, depth), 1e-6)
            preserve_open = (
                space_kind in {"open_plan", "shared_open_space"}
                and aspect <= max_aspect * 2.0
            )
            if preserve_open:
                if room.bounds.area > max_enclosed_area:
                    metadata.update(
                        {
                            "large_space_policy": "preserve_as_open_plan",
                            "open_plan": True,
                            "nominal_capacity_zones": max(
                                1, round(room.bounds.area / archetype.target_room_area_m2)
                            ),
                        }
                    )
                    room.metadata = metadata
                    preserved_open += 1
                output.append(room)
                continue
            aspect_segments = math.ceil(width / max(depth * max_aspect, 1e-6))
            area_segments = math.ceil(room.bounds.area / max(max_enclosed_area * 1.5, 1.0))
            requested_segments = max(1, aspect_segments, area_segments)
            capacity = max(1, math.floor(width / min_width))
            segments = min(requested_segments, capacity, 6)
            if segments <= 1:
                metadata["large_space_policy"] = (
                    "geometry_limited" if requested_segments > 1 else "within_contract"
                )
                room.metadata = metadata
                output.append(room)
                continue
            parts: list[Room] = []
            part_width = width / segments
            for index in range(segments):
                bounds = Bounds2D(
                    room.bounds.min_x + index * part_width,
                    room.bounds.min_y,
                    room.bounds.min_x + (index + 1) * part_width,
                    room.bounds.max_y,
                )
                part_metadata = {
                    **metadata,
                    "large_space_policy": "split_enclosed_space",
                    "split_from_room_id": room.id,
                    "split_index": index,
                    "split_count": segments,
                }
                parts.append(
                    Room(
                        id=f"{room.id}_part_{index + 1:02d}",
                        name=f"{room.name} {index + 1}",
                        function=room.function,
                        bounds=bounds,
                        height_m=room.height_m,
                        metadata=part_metadata,
                    )
                )
            replacements[room.id] = parts
            output.extend(parts)

        if not replacements:
            return output, doors, {
                "policy": "semantic_split_or_open_plan_v1",
                "split_source_room_count": 0,
                "created_room_count": 0,
                "preserved_open_space_count": preserved_open,
            }

        rebuilt_doors: list[Door] = []
        corridor_targets: dict[str, tuple[str | None, float]] = {}
        connected_parts: set[str] = set()
        for door in doors:
            room_id = door.room_a_id if door.room_a_id in replacements else (
                door.room_b_id if door.room_b_id in replacements else None
            )
            if room_id is None:
                rebuilt_doors.append(door)
                continue
            parts = replacements[room_id]
            selected = next(
                (
                    part for part in parts
                    if part.bounds.min_x - 1e-6 <= door.position.x <= part.bounds.max_x + 1e-6
                ),
                parts[0],
            )
            # The inherited door can lie exactly on a new split boundary.
            # Keep the opening on the selected part's corridor-facing wall
            # and reserve a short wall pier at both corners; otherwise the
            # half-width opening is also subtracted from the neighbouring
            # room and leaves a visible corner crack.
            inset = door.width_m / 2 + 0.18
            if selected.bounds.width > 2 * inset:
                door_x = min(
                    max(door.position.x, selected.bounds.min_x + inset),
                    selected.bounds.max_x - inset,
                )
            else:
                door_x = selected.bounds.center.x
            inherited_position = Point2D(door_x, door.position.y)
            room_is_a = door.room_a_id == room_id
            other_id = door.room_b_id if room_is_a else door.room_a_id
            corridor_targets.setdefault(room_id, (other_id, door.position.y))
            rebuilt_doors.append(
                Door(
                    id=door.id,
                    room_a_id=selected.id if room_is_a else door.room_a_id,
                    room_b_id=door.room_b_id if room_is_a else selected.id,
                    position=inherited_position,
                    width_m=door.width_m,
                    door_type=door.door_type,
                    interactive=door.interactive,
                )
            )
            connected_parts.add(selected.id)
        for source_id, parts in replacements.items():
            target_id, door_y = corridor_targets.get(source_id, (None, parts[0].bounds.min_y))
            if target_id is None:
                continue
            for part in parts:
                if part.id in connected_parts:
                    continue
                rebuilt_doors.append(
                    Door(
                        id=f"{part.id}_door",
                        room_a_id=part.id,
                        room_b_id=target_id,
                        position=Point2D(part.bounds.center.x, door_y),
                    )
                )
        return output, rebuilt_doors, {
            "policy": "semantic_split_or_open_plan_v1",
            "split_source_room_count": len(replacements),
            "created_room_count": sum(len(items) for items in replacements.values()),
            "preserved_open_space_count": preserved_open,
        }

    @staticmethod
    def _floor_program_role(
        level: int, floor_count: int, podium_floors: int
    ) -> str:
        if level == 0:
            return "ground"
        if floor_count > 1 and level == floor_count - 1:
            return "top"
        if podium_floors and level < podium_floors:
            return "podium"
        return "typical"

    @staticmethod
    def _resolve_room_count(
        footprint: Bounds2D,
        corridor_ratio: float,
        archetype: FloorArchetype,
    ) -> tuple[int, dict]:
        """Adapt an LLM space budget to the realized, compiler-owned floor plate."""

        usable_area = footprint.area * (1.0 - min(corridor_ratio, 0.25))
        area_count = max(1, round(usable_area / archetype.target_room_area_m2))
        blended = round((archetype.preferred_room_count + area_count) / 2)
        bounded = min(
            archetype.max_room_count,
            max(archetype.min_room_count, blended),
        )
        band_plan = ProgrammedCityPlanner._room_band_plan(
            footprint,
            corridor_ratio,
            archetype,
            target_room_count=bounded,
        )
        geometric_capacity = max(1, int(band_plan["geometric_capacity"]))
        realized = max(1, min(bounded, geometric_capacity))
        return realized, {
            "source": "llm_floor_space_program_v1",
            "role": archetype.role,
            "preferred_room_count": archetype.preferred_room_count,
            "min_room_count": archetype.min_room_count,
            "max_room_count": archetype.max_room_count,
            "target_room_area_m2": archetype.target_room_area_m2,
            "min_room_width_m": archetype.min_room_width_m,
            "max_room_depth_m": archetype.max_room_depth_m,
            "max_room_aspect_ratio": archetype.max_room_aspect_ratio,
            "usable_floor_area_m2": round(usable_area, 3),
            "area_based_room_count": area_count,
            "pre_geometry_room_count": bounded,
            "geometric_capacity": geometric_capacity,
            "realized_room_count": realized,
            "capacity_limited": realized < bounded,
            "layout_topology": (
                "multi_corridor_bands"
                if band_plan["bands_per_side"] > 1
                else "double_loaded_corridor"
            ),
            "room_bands_per_side": band_plan["bands_per_side"],
            "room_depth_m": round(band_plan["room_depth"], 3),
            "required_room_width_m": round(band_plan["required_room_width"], 3),
            "unit_group_size": archetype.unit_group_size,
            "room_function_cycle": list(archetype.room_function_cycle),
        }
