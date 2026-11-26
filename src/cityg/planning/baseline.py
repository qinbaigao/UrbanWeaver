"""Deterministic coarse-to-fine reference planner.

This planner exists to exercise the complete CityG contract before agentic and
constraint-solving planners are introduced. It favors valid hierarchy and stable
IDs while providing controlled, reproducible site-layout variation.
"""

from __future__ import annotations

import math
import random
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

from cityg.ccwp import build_world_program, point_segment_distance
from cityg.buildings import (
    BuildingSelection,
    BuildingSelectionContext,
    BuildingSelector,
)
from cityg.planning.highrise import (
    DEFAULT_HIGHRISE_MASSING_PALETTE,
    HighRisePolicy,
)
from cityg.planning.heights import HeightCandidate, HeightDecision, SkylinePlanner
from cityg.planning.interiors import FloorDetailAgent
from cityg.planning.orientation import StreetAlignmentPlanner
from cityg.schemas import (
    Bounds2D,
    Building,
    City,
    CitySpec,
    District,
    Door,
    Floor,
    Junction,
    Parcel,
    Point2D,
    RoadNetwork,
    RoadSegment,
    Room,
    ZoneSpec,
)


ROOM_FUNCTIONS = {
    "residential": (
        "reception",
        "living_room",
        "bedroom",
        "kitchen",
        "bathroom",
        "restroom",
        "study",
        "storage",
    ),
    "commercial": (
        "shop",
        "open_office",
        "office",
        "meeting_room",
        "reception",
        "restroom",
        "break_room",
        "storage",
        "service_room",
    ),
    "public_service": (
        "service_hall",
        "office",
        "waiting_room",
        "restroom",
        "equipment_room",
        "storage",
    ),
    "industrial": (
        "workshop",
        "storage",
        "control_room",
        "utility_room",
        "office",
        "restroom",
    ),
    "mixed_use": (
        "living_room",
        "shop",
        "open_office",
        "office",
        "meeting_room",
        "reception",
        "kitchen",
        "bedroom",
        "bathroom",
        "restroom",
        "break_room",
        "storage",
        "service_room",
    ),
}


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or "unnamed"


def _union_bounds(bounds: list[Bounds2D]) -> Bounds2D:
    return Bounds2D(
        min(item.min_x for item in bounds),
        min(item.min_y for item in bounds),
        max(item.max_x for item in bounds),
        max(item.max_y for item in bounds),
    )


@dataclass(frozen=True)
class _ParcelSite:
    bounds: Bounds2D
    urban_block_id: str
    cluster_size: int
    site_index: int
    frontage_sides: tuple[str, ...]


class BaselineCityPlanner:
    """Generate a connected, irregularized grid city with building interiors."""

    floor_height_m = 3.2

    @staticmethod
    def _primary_road_envelope(spec: CitySpec) -> tuple[float, float]:
        """Return the conservative envelope reserved for grid roads.

        Grid axes are shared by collector and local segments.  We reserve the
        largest plausible collector cross-section before assigning individual
        segment profiles, so a wider collector never overlaps a parcel or a
        neighboring sidewalk after widths diversify.
        """

        base_width = float(spec.road_width_m)
        base_sidewalk = float(spec.sidewalk_width_m)
        arterial = BaselineCityPlanner._arterials_enabled(spec)
        width_factor = 1.46 if arterial else 1.24
        sidewalk_factor = 1.38 if arterial else 1.28
        return max(base_width, base_width * width_factor), max(
            base_sidewalk, base_sidewalk * sidewalk_factor
        )

    @staticmethod
    def _arterials_enabled(spec: CitySpec) -> bool:
        """Enable a small arterial hierarchy only for city-scale layouts."""

        return bool(
            spec.arterial_ratio > 0.0
            and spec.building_count >= 12
            and max(spec.width_m, spec.depth_m) >= 300.0
        )

    @staticmethod
    def _road_cross_section(
        spec: CitySpec,
        road_class: str,
        index: int,
        orientation: str,
    ) -> tuple[int, float, float]:
        """Derive a stable, hierarchical cross-section for one segment.

        The input ``road_width_m`` remains the user-facing baseline. Small
        deterministic variation avoids a city-wide repeated stencil while
        retaining clear class-level ranges and enough width for the compiler's
        lane/sidewalk constraints.
        """

        base = float(spec.road_width_m)
        sidewalk = float(spec.sidewalk_width_m)
        noise = random.Random(f"{spec.seed}:cross_section:{orientation}:{index}")
        if road_class == "collector":
            width = base * (1.16 + noise.uniform(-0.045, 0.075))
            lanes = 3 if width >= max(13.0, base * 1.08) else 2
            sidewalk_width = sidewalk * (1.18 + noise.uniform(-0.05, 0.12))
        elif road_class == "arterial":
            # A four-lane boulevard is intentionally uncommon; its median and
            # reserved transit/cycle space are represented separately in the
            # road semantics below.
            width = base * (1.42 + noise.uniform(-0.045, 0.075))
            lanes = 4
            sidewalk_width = sidewalk * (1.32 + noise.uniform(-0.04, 0.10))
        elif road_class == "local":
            width = base * (0.80 + noise.uniform(-0.055, 0.075))
            width = max(7.2, width)
            lanes = 2
            sidewalk_width = sidewalk * (0.88 + noise.uniform(-0.06, 0.08))
        elif road_class == "service":
            width = max(4.5, base * (0.50 + noise.uniform(-0.025, 0.045)))
            lanes = 1
            sidewalk_width = max(1.2, sidewalk * 0.65)
        elif road_class == "shared_space":
            width = max(5.0, base * (0.58 + noise.uniform(-0.035, 0.055)))
            lanes = 1
            sidewalk_width = max(1.35, sidewalk * 0.72)
        else:
            width = base
            lanes = 2
            sidewalk_width = sidewalk
        return lanes, round(width, 3), round(sidewalk_width, 3)

    @staticmethod
    def _road_semantics(
        spec: CitySpec,
        road_class: str,
        index: int,
        orientation: str,
        *,
        branch: bool = False,
    ) -> dict[str, Any]:
        """Return stable lane-use semantics consumed by geometry and agents."""

        if road_class == "arterial":
            return {
                "directionality": "bidirectional",
                "median_width_m": round(max(1.2, spec.road_width_m * 0.12), 2),
                "parking_allowed": False,
                "bike_lane": True,
                "bus_lane": True,
                "turn_lane": True,
                "intersection_control": "signalized",
            }
        if road_class == "collector":
            # Keep curb parking off the major edge/central corridors; one in
            # three collectors retain it where frontage is less intensive.
            seed = random.Random(f"{spec.seed}:collector:{orientation}:{index}")
            parking = seed.random() > 0.68
            return {
                "directionality": "bidirectional",
                "median_width_m": 0.0,
                "parking_allowed": parking,
                "bike_lane": True,
                "bus_lane": False,
                "turn_lane": bool(index % 3 == 0),
                "intersection_control": "priority",
            }
        if road_class == "service":
            return {
                "directionality": "one_way" if spec.one_way_ratio > 0.0 else "bidirectional",
                "median_width_m": 0.0,
                "parking_allowed": False,
                "bike_lane": False,
                "bus_lane": False,
                "turn_lane": False,
                "intersection_control": "yield",
            }
        if road_class == "shared_space":
            return {
                "directionality": "bidirectional",
                "median_width_m": 0.0,
                "parking_allowed": False,
                "bike_lane": True,
                "bus_lane": False,
                "turn_lane": False,
                "intersection_control": "priority",
            }
        return {
            "directionality": "bidirectional",
            "median_width_m": 0.0,
            "parking_allowed": True,
            "bike_lane": False,
            "bus_lane": False,
            "turn_lane": False,
            "intersection_control": "priority",
        }

    def __init__(
        self,
        floor_detail_agent: FloorDetailAgent | None = None,
        building_selector: BuildingSelector | None = None,
    ) -> None:
        self.floor_detail_agent = floor_detail_agent or FloorDetailAgent()
        self.building_selector = building_selector or BuildingSelector()
        self._used_archetype_ids: set[str] = set()
        self._used_massing_signatures: set[str] = set()

    def plan(self, spec: CitySpec) -> City:
        spec.validate()
        # Selection is deterministic per plan, but the diversity budget must
        # not leak from one independent city generation into the next.
        self._used_archetype_ids = set()
        self._used_massing_signatures = set()
        rng = random.Random(spec.seed)
        cols, rows = self._grid_shape(spec)
        irregularity = (
            spec.layout_irregularity if spec.layout_style == "organic_grid" else 0.0
        )
        x_roads = self._road_axes(
            spec,
            spec.width_m,
            cols,
            random.Random(f"{spec.seed}:road:x"),
            irregularity,
        )
        y_roads = self._road_axes(
            spec,
            spec.depth_m,
            rows,
            random.Random(f"{spec.seed}:road:y"),
            irregularity,
        )

        blocks = self._make_blocks(spec, x_roads, y_roads)
        occupied_block_count = self._occupied_block_count(spec)
        if len(blocks) < occupied_block_count:
            raise RuntimeError("Internal planner error: insufficient blocks")
        selected_blocks = self._select_blocks(
            blocks,
            occupied_block_count,
            random.Random(f"{spec.seed}:occupancy"),
        )
        vacant_blocks = [block for block in blocks if block not in selected_blocks]
        network = self._make_road_network(
            spec,
            x_roads,
            y_roads,
            secondary_blocks=vacant_blocks,
            rng=random.Random(f"{spec.seed}:secondary_roads"),
        )
        parcel_sites = self._make_parcel_sites(
            spec,
            selected_blocks,
            random.Random(f"{spec.seed}:clusters"),
        )
        geography = None
        if spec.parcel_layout == "polygonal" or spec.river_mode != "none" or spec.road_pattern == "landscape_adaptive":
            from cityg.planning.geography import plan_geography
            geography = plan_geography(spec, network)
            network, parcel_sites = geography.network, geography.sites
        if len(parcel_sites) != spec.building_count:
            raise RuntimeError("Internal planner error: parcel allocation mismatch")

        allocation = self._allocate_zones(spec.zones, spec.building_count)
        from cityg.planning.urban_spatial import assign_sites
        site_order, spatial_assignment = assign_sites(spec, parcel_sites, allocation, network,
                                                     geography.rivers if geography else [])
        parcel_sites = [parcel_sites[i] for i in site_order]
        if geography is not None:
            geography.plots = [geography.plots[i] for i in site_order]
        function_sequence = [
            zone.function for zone, count in allocation for _ in range(count)
        ]
        skyline_program = self._skyline_program(spec)
        height_decisions = SkylinePlanner().plan(
            spec,
            [
                HeightCandidate(index, function, site.bounds.center)
                for index, (function, site) in enumerate(
                    zip(function_sequence, parcel_sites)
                )
            ],
            skyline_program,
        )
        height_by_index = {
            item.building_index: item for item in height_decisions
        }
        districts: list[District] = []
        block_index = 0
        building_index = 0

        for district_index, (zone, count) in enumerate(allocation):
            parcels: list[Parcel] = []
            for district_ordinal in range(count):
                site = parcel_sites[block_index]
                block_index += 1
                parcel_id = f"parcel_{building_index:03d}"
                self._active_zone_name = zone.name
                building = self._make_building(
                    spec=spec,
                    rng=rng,
                    index=building_index,
                    function=zone.function,
                    parcel_bounds=site.bounds,
                    frontage_sides=site.frontage_sides,
                    urban_block_id=site.urban_block_id,
                    cluster_size=site.cluster_size,
                    site_index=site.site_index,
                    height_decision=height_by_index[building_index],
                )
                from cityg.architecture import make_appearance_plan, merge_architecture
                architectural_context = merge_architecture(spec.architecture, zone.architecture)
                architectural_context.setdefault("district_character", zone.name)
                building.metadata["appearance_plan"] = make_appearance_plan(
                    building, architectural_context, seed=spec.seed, ordinal=district_ordinal,
                    form_ordinal=district_ordinal if 'expressive_ratio' in zone.architecture else building_index)
                parcel = Parcel(id=parcel_id, bounds=site.bounds, buildings=[building])
                if geography is not None:
                    from cityg.polygons import rings
                    polygon = geography.plots[building_index]
                    parcel.bounds = Bounds2D(*polygon.bounds)
                    parcel.boundary, parcel.holes = rings(polygon)
                parcels.append(parcel)
                building_index += 1

            district_bounds = _union_bounds([parcel.bounds for parcel in parcels])
            districts.append(
                District(
                    id=f"district_{district_index:02d}_{_slug(zone.name)}",
                    name=zone.name,
                    function=zone.function,
                    bounds=district_bounds,
                    parcels=parcels,
                )
            )

        city = City(
            id=f"city_{_slug(spec.name)}",
            name=spec.name,
            bounds=Bounds2D(0.0, 0.0, spec.width_m, spec.depth_m),
            road_network=network,
            districts=districts,
            metadata={
                "planner": "baseline_site_layout_v2",
                "seed": spec.seed,
                "requested_buildings": spec.building_count,
                "parcel_setback_m": spec.parcel_setback_m,
                "urban_requirements": list(spec.urban_requirements),
                "urban_spatial_assignment": spatial_assignment,
                "geography_recovery": getattr(geography, 'recovery', None),
                "grid": {"columns": cols, "rows": rows},
                "site_layout": {
                    "style": spec.layout_style,
                    "irregularity": spec.layout_irregularity,
                    "candidate_block_count": len(blocks),
                    "occupied_block_count": len(selected_blocks),
                    "open_block_count": len(blocks) - len(selected_blocks),
                    "buildings_per_occupied_block": round(
                        spec.building_count / len(selected_blocks), 6
                    ),
                    "cluster_size_histogram": {
                        str(size): sum(
                            1
                            for site in parcel_sites
                            if site.site_index == 0 and site.cluster_size == size
                        )
                        for size in sorted({site.cluster_size for site in parcel_sites})
                    },
                    "secondary_road_count": sum(
                        segment.road_class in {"service", "shared_space"}
                        for segment in network.segments
                    ),
                    "landscape_site_count": len(vacant_blocks),
                    "realized_open_space_ratio": round(
                        (len(blocks) - len(selected_blocks)) / len(blocks), 6
                    ),
                },
                "landscape_sites": [
                    {
                        "id": f"landscape_{index:03d}",
                        "style": ("park", "plaza", "garden")[
                            (index + spec.seed) % 3
                        ],
                        # Public green areas receive a fuller planting tier;
                        # plazas stay more open for circulation and sightlines.
                        "density_tier": {
                            "park": "lush",
                            "garden": "lush",
                            "plaza": "standard",
                        }[("park", "plaza", "garden")[(index + spec.seed) % 3]],
                        "bounds": {
                            "min_x": block.min_x,
                            "min_y": block.min_y,
                            "max_x": block.max_x,
                            "max_y": block.max_y,
                        },
                    }
                    for index, block in enumerate(vacant_blocks)
                ],
            },
        )
        city.metadata["architecture"] = dict(spec.architecture)
        if geography is not None:
            city.rivers, city.bridges = geography.rivers, geography.bridges
            city.metadata["landscape_sites"] = geography.landscape_sites
            city.metadata["geography"] = {"planner": "polygonal_land_first_v1",
                "river_mode": spec.river_mode, "parcel_layout": "polygonal",
                "river_count": len(city.rivers), "bridge_count": len(city.bridges),
                "polygon_parcel_count": len(geography.plots), "bank_promenade_width_m": 3.0}
            city.metadata["site_layout"].update({"style": "polygonal", "occupied_block_count": len(geography.plots),
                "landscape_site_count": len(geography.landscape_sites),
                "open_block_count": len(geography.landscape_sites)})
        envelope_width, envelope_sidewalk = self._primary_road_envelope(spec)
        city.metadata["road_cross_section_plan"] = {
            "planner": "hierarchical_cross_sections_v1",
            "base_width_m": spec.road_width_m,
            "base_sidewalk_width_m": spec.sidewalk_width_m,
            "reserved_primary_envelope": {
                "width_m": round(envelope_width, 3),
                "sidewalk_width_m": round(envelope_sidewalk, 3),
            },
            "segments": [
                {
                    "road_id": road.id,
                    "road_class": road.road_class,
                    "lane_count": road.lane_count,
                    "width_m": road.width_m,
                    "sidewalk_width_m": road.sidewalk_width_m,
                    "directionality": road.directionality,
                    "median_width_m": road.median_width_m,
                    "parking_allowed": road.parking_allowed,
                    "bike_lane": road.bike_lane,
                    "bus_lane": road.bus_lane,
                    "turn_lane": road.turn_lane,
                    "intersection_control": road.intersection_control,
                }
                for road in network.segments
            ],
        }
        city.metadata["height_plan"] = SkylinePlanner.summarize(
            spec,
            height_decisions,
            {
                index: len(building.floors)
                for index, building in enumerate(city.iter_buildings())
            },
            skyline_program,
        )
        morphology_buildings = list(city.iter_buildings())
        centralities = [
            float(item.metadata.get("height_contract", {}).get("centrality", 0.0))
            for item in morphology_buildings
        ]
        city.metadata["urban_morphology"] = {
            "planner": "macro_morphology_v1",
            "core_radius_ratio": 0.42,
            "transition_radius_ratio": 0.72,
            "hierarchy": ["core", "transition", "edge"],
            "landmark_ids": [
                item.id for item in morphology_buildings
                if item.metadata.get("urban_morphology_role") == "landmark"
            ],
            "core_building_ids": [
                item.id for item in morphology_buildings
                if float(item.metadata.get("height_contract", {}).get("centrality", 0.0)) >= 0.55
            ],
            "edge_building_ids": [
                item.id for item in morphology_buildings
                if float(item.metadata.get("height_contract", {}).get("centrality", 0.0)) < 0.30
            ],
            "centrality_range": [
                round(min(centralities), 6), round(max(centralities), 6)
            ] if centralities else [0.0, 0.0],
        }
        city.metadata["building_archetype_catalog"] = {
            "version": "building_archetype.v1",
            "entry_count": len(self.building_selector.catalog),
            "massing_signature_count": len({
                item.massing_signature for item in self.building_selector.catalog
            }),
            "selector": "deterministic_catalog_v1",
        }
        self._resolve_street_orientations(city, spec)
        orientation_contracts = [
            building.metadata["orientation_contract"]
            for building in city.iter_buildings()
        ]
        city.metadata["orientation_plan"] = {
            "planner": "street_alignment_v1",
            "strict_street_aligned_count": sum(
                item["strict_alignment"] for item in orientation_contracts
            ),
            "contextual_rotation_count": sum(
                abs(float(item["offset_deg"])) > 1e-9
                for item in orientation_contracts
            ),
            "alignment_mode_histogram": dict(
                sorted(
                    Counter(
                        item["alignment_mode"] for item in orientation_contracts
                    ).items()
                )
            ),
        }
        city.metadata["interior_detail"] = self.floor_detail_agent.populate(
            city, seed=spec.seed
        )
        from cityg.morphology import realization_report
        explicit_envelopes = {
            b.id: dict(b.metadata['appearance_plan']['envelope'])
            for b in city.iter_buildings()
            if (b.metadata['appearance_plan']['context'].get('envelope') or
                b.metadata['appearance_plan']['context'].get('envelope_palette'))
        }
        adaptive = spec.road_pattern == 'landscape_adaptive'
        if adaptive or explicit_envelopes:
            city.metadata['morphology_contract'] = {
                'version': 'cityg.morphology.v2', 'adaptive_roads': adaptive,
                'river_min_deviation_m': spec.width_m * .025 if adaptive and city.rivers else 0,
                'intent': dict(spec.morphology), 'building_envelopes': explicit_envelopes,
                'topology': 'staggered_streets_local_waterfront' if adaptive else 'legacy',
            }
            city.metadata['morphology_report'] = realization_report(city)
        city.world_program = build_world_program(
            city, producer=self.__class__.__name__, seed=spec.seed
        )
        return city

    @staticmethod
    def _resolve_street_orientations(city: City, spec: CitySpec) -> None:
        """Bind provisional frontage intent to the actual nearest road bearing."""

        for index, building in enumerate(city.iter_buildings()):
            road = min(
                city.road_network.segments,
                key=lambda item: point_segment_distance(
                    building.entrance, item.centerline
                ),
            )
            from cityg.paths import PlanarPath2D
            path = PlanarPath2D(road.centerline)
            street_axis = path.heading(path.project(building.entrance).distance) % 180.0
            height = building.metadata.get("height_contract", {})
            decision = StreetAlignmentPlanner.plan(
                entrance_side=str(building.metadata.get("entrance_side", "west")),
                function=building.function,
                centrality=float(height.get("centrality", 0.0)),
                cluster_size=int(building.metadata.get("cluster_size", 1)),
                highrise=bool(
                    building.metadata.get("highrise", {}).get("enabled")
                ),
                landmark=bool(height.get("landmark")),
                layout_style=spec.layout_style,
                building_index=index,
                seed=spec.seed,
                street_axis_deg=street_axis,
                frontage_road_id=road.id,
            )
            building.metadata["orientation_deg"] = decision.orientation_deg
            building.metadata["orientation_contract"] = decision.to_metadata()

    def _skyline_program(self, spec: CitySpec):
        """Return an optional agent-authored program; baseline uses the fallback."""

        return None

    @staticmethod
    def _grid_shape(spec: CitySpec) -> tuple[int, int]:
        occupied_blocks = BaselineCityPlanner._occupied_block_count(spec)
        occupancy = (
            1.0 - spec.open_space_ratio
            if spec.layout_style == "organic_grid" and occupied_blocks >= 3
            else 1.0
        )
        target_blocks = max(
            occupied_blocks, math.ceil(occupied_blocks / occupancy)
        )
        aspect = spec.width_m / spec.depth_m
        candidates: list[tuple[float, int, int]] = []
        for cols in range(1, target_blocks + 1):
            rows = math.ceil(target_blocks / cols)
            unused = cols * rows - target_blocks
            shape_error = abs(math.log((cols / rows) / aspect))
            score = shape_error + 0.35 * unused / target_blocks
            candidates.append((score, cols, rows))
        _, cols, rows = min(candidates)
        return cols, rows

    @staticmethod
    def _occupied_block_count(spec: CitySpec) -> int:
        if spec.building_count < 6:
            return spec.building_count
        allocation = BaselineCityPlanner._allocate_zones(
            spec.zones, spec.building_count
        )
        return sum(
            math.ceil(count / spec.buildings_per_block)
            for _, count in allocation
        )

    @staticmethod
    def _road_axes(
        spec: CitySpec,
        extent: float,
        cell_count: int,
        rng: random.Random,
        irregularity: float,
    ) -> list[float]:
        road_width, sidewalk_width = BaselineCityPlanner._primary_road_envelope(spec)
        if cell_count == 1:
            return [road_width / 2, extent - road_width / 2]
        start = road_width / 2
        end = extent - road_width / 2
        spacing = (end - start) / cell_count
        clearance = road_width / 2 + sidewalk_width
        minimum_spacing = 2 * clearance + 2 * spec.parcel_setback_m + 6.0
        jitter_limit = min(
            spacing * 0.24 * irregularity,
            max(0.0, (spacing - minimum_spacing) * 0.35),
        )
        axes = [start]
        for index in range(1, cell_count):
            axes.append(start + spacing * index + rng.uniform(-jitter_limit, jitter_limit))
        axes.append(end)
        return axes

    @staticmethod
    def _select_blocks(
        blocks: list[Bounds2D], count: int, rng: random.Random
    ) -> list[Bounds2D]:
        """Distribute vacant blocks while retaining the planner traversal order."""

        if count == len(blocks):
            return blocks
        ranked = list(enumerate(blocks))
        rng.shuffle(ranked)
        occupied_indices = {index for index, _ in ranked[:count]}
        return [block for index, block in enumerate(blocks) if index in occupied_indices]

    @staticmethod
    def _cluster_capacities(
        building_count: int, block_count: int, rng: random.Random
    ) -> list[int]:
        """Allocate 1--3 buildings per block while preserving the exact total."""

        base, remainder = divmod(building_count, block_count)
        capacities = [base + (index < remainder) for index in range(block_count)]
        indices = list(range(block_count))
        rng.shuffle(indices)
        pair_count = min(block_count // 4, len(indices) // 2)
        for pair_index in range(pair_count):
            donor = indices[pair_index * 2]
            receiver = indices[pair_index * 2 + 1]
            if capacities[donor] > 1 and capacities[receiver] < 4:
                capacities[donor] -= 1
                capacities[receiver] += 1
        return capacities

    def _make_parcel_sites(
        self,
        spec: CitySpec,
        blocks: list[Bounds2D],
        rng: random.Random,
    ) -> list[_ParcelSite]:
        sites: list[_ParcelSite] = []
        block_cursor = 0
        global_block_index = 0
        for zone, building_count in self._allocate_zones(
            spec.zones, spec.building_count
        ):
            zone_block_count = (
                building_count
                if spec.building_count < 6
                else math.ceil(building_count / spec.buildings_per_block)
            )
            zone_blocks = blocks[block_cursor : block_cursor + zone_block_count]
            block_cursor += zone_block_count
            capacities = self._cluster_capacities(
                building_count, zone_block_count, rng
            )
            preferred_side = self._preferred_entrance_side(zone.function)
            for block, capacity in zip(zone_blocks, capacities):
                block_id = f"urban_block_{global_block_index:03d}"
                sites.extend(
                    self._subdivide_block(
                        block,
                        block_id,
                        capacity,
                        rng,
                        preferred_side=preferred_side,
                        minimum_site_span=2 * spec.parcel_setback_m + 8.0,
                    )
                )
                global_block_index += 1
        return sites

    def _preferred_entrance_side(self, function: str) -> str | None:
        return None

    @staticmethod
    def _massing_style(function: str, index: int, seed: int) -> str:
        styles = {
            "residential": ("bar", "l_shape", "u_shape"),
            "commercial": ("bar", "t_shape", "l_shape"),
            "public_service": ("u_shape", "t_shape", "l_shape"),
            "industrial": ("bar", "l_shape", "t_shape"),
            "mixed_use": ("l_shape", "u_shape", "t_shape", "bar"),
        }.get(function, ("bar", "l_shape", "t_shape"))
        return styles[(index + seed) % len(styles)]

    @staticmethod
    def _subdivide_block(
        block: Bounds2D,
        block_id: str,
        capacity: int,
        rng: random.Random,
        preferred_side: str | None = None,
        minimum_site_span: float = 0.0,
    ) -> list[_ParcelSite]:
        if capacity == 1:
            return [
                _ParcelSite(
                    block,
                    block_id,
                    1,
                    0,
                    ("west", "east", "north", "south"),
                )
            ]

        if preferred_side in {"north", "south"}:
            split_axis = "x"
        elif preferred_side in {"west", "east"}:
            split_axis = "y"
        elif block.width > block.depth * 1.2:
            split_axis = "x"
        elif block.depth > block.width * 1.2:
            split_axis = "y"
        else:
            split_axis = "x" if rng.random() < 0.5 else "y"

        # A preferred street frontage is soft; buildable width after setbacks
        # is not. A narrow strip cannot be repaired by choosing a prettier mesh.
        lengths = {'x': block.width, 'y': block.depth}
        other = 'y' if split_axis == 'x' else 'x'
        if lengths[split_axis] / capacity < minimum_site_span:
            if lengths[other] / capacity >= minimum_site_span:
                split_axis = other
            elif capacity in (3, 4) and min(block.width, block.depth) / 2 >= minimum_site_span:
                # Two boundary rows retain an actual outer street frontage for
                # each parcel; no invented internal road or landlocked parcel.
                sites = []
                for row, count in enumerate((2, capacity - 2)):
                    for col in range(count):
                        bounds = Bounds2D(block.min_x + block.width * col / count,
                                          block.min_y + block.depth * row / 2,
                                          block.min_x + block.width * (col + 1) / count,
                                          block.min_y + block.depth * (row + 1) / 2)
                        fronts = ['south' if row == 0 else 'north']
                        if col == 0: fronts.append('west')
                        if col == count - 1: fronts.append('east')
                        sites.append(_ParcelSite(bounds, block_id, capacity, len(sites), tuple(fronts)))
                return sites
            else:
                raise ValueError(f'{block_id}: block cannot fit {capacity} street-accessible parcels '
                                 f'with minimum span {minimum_site_span:.2f} m; revise urban density or setbacks')

        weights = [rng.uniform(0.86, 1.14) for _ in range(capacity)]
        total = sum(weights)
        shares = [weight / total for weight in weights]
        length = lengths[split_axis]
        if minimum_site_span and min(shares) * length < minimum_site_span:
            slack = length - capacity * minimum_site_span
            shares = [(minimum_site_span + slack * share) / length for share in shares]
        sites: list[_ParcelSite] = []
        cursor = block.min_x if split_axis == "x" else block.min_y
        for site_index, share in enumerate(shares):
            is_last = site_index == capacity - 1
            if split_axis == "x":
                next_cursor = (
                    block.max_x
                    if is_last
                    else cursor + block.width * share
                )
                bounds = Bounds2D(cursor, block.min_y, next_cursor, block.max_y)
                frontages = ("north", "south")
            else:
                next_cursor = (
                    block.max_y
                    if is_last
                    else cursor + block.depth * share
                )
                bounds = Bounds2D(block.min_x, cursor, block.max_x, next_cursor)
                frontages = ("west", "east")
            sites.append(
                _ParcelSite(
                    bounds,
                    block_id,
                    capacity,
                    site_index,
                    frontages,
                )
            )
            cursor = next_cursor
        return sites

    @staticmethod
    def _layout_footprint(
        spec: CitySpec,
        rng: random.Random,
        index: int,
        function: str,
        parcel_bounds: Bounds2D,
        entrance_side: str,
    ) -> Bounds2D:
        """Place a varied rectangular mass inside a parcel without breaking access."""

        inner = parcel_bounds.inset(spec.parcel_setback_m)
        if spec.layout_style == "regular_grid":
            return inner

        density = {
            "commercial": (0.72, 0.94),
            "mixed_use": (0.68, 0.92),
            "public_service": (0.58, 0.86),
            "residential": (0.55, 0.84),
            "industrial": (0.66, 0.92),
        }.get(function, (0.62, 0.88))
        strength = spec.layout_irregularity
        minimum_scale, maximum_scale = density
        scale_x = 1.0 - strength * (1.0 - rng.uniform(minimum_scale, maximum_scale))
        scale_y = 1.0 - strength * (1.0 - rng.uniform(minimum_scale, maximum_scale))
        if index % 3 == 1:
            scale_x = max(0.55, scale_x - 0.04 * strength)
        elif index % 3 == 2:
            scale_y = max(0.55, scale_y - 0.04 * strength)
        if function == "industrial":
            scale_x = min(1.0, scale_x + 0.06 * strength)
            scale_y = max(0.55, scale_y - 0.05 * strength)

        width = max(6.0, inner.width * scale_x)
        depth = max(6.0, inner.depth * scale_y)
        width = min(width, inner.width)
        depth = min(depth, inner.depth)
        slack_x = inner.width - width
        slack_y = inner.depth - depth
        offset_x = rng.random() * slack_x
        offset_y = rng.random() * slack_y

        # Bias the mass toward its entrance frontage. The remaining small offset
        # creates staggered street walls while preserving the nearest-road contract.
        # Curved polygonal frontages already include geometric setback from
        # their inscribed rectangle. Do not add randomized frontage slack.
        frontage_bias = 0.0 if spec.road_pattern == 'landscape_adaptive' else 0.28
        frontage_budget = max(
            0.0,
            24.5
            - (
                BaselineCityPlanner._primary_road_envelope(spec)[0] / 2
                + BaselineCityPlanner._primary_road_envelope(spec)[1]
                + spec.parcel_setback_m
            ),
        )
        if entrance_side == "west":
            offset_x = min(offset_x * frontage_bias, frontage_budget)
        elif entrance_side == "east":
            offset_x = slack_x - min(offset_x * frontage_bias, frontage_budget)
        elif entrance_side == "south":
            offset_y = min(offset_y * frontage_bias, frontage_budget)
        elif entrance_side == "north":
            offset_y = slack_y - min(offset_y * frontage_bias, frontage_budget)

        return Bounds2D(
            inner.min_x + offset_x,
            inner.min_y + offset_y,
            inner.min_x + offset_x + width,
            inner.min_y + offset_y + depth,
        )

    def _make_road_network(
        self,
        spec: CitySpec,
        x_roads: list[float],
        y_roads: list[float],
        secondary_blocks: list[Bounds2D] | None = None,
        rng: random.Random | None = None,
    ) -> RoadNetwork:
        junctions: list[Junction] = []
        junction_ids: dict[tuple[int, int], str] = {}
        for x_index, x in enumerate(x_roads):
            for y_index, y in enumerate(y_roads):
                junction_id = f"junction_{x_index:02d}_{y_index:02d}"
                junction_ids[(x_index, y_index)] = junction_id
                junctions.append(Junction(junction_id, Point2D(x, y)))

        segments: list[RoadSegment] = []
        arterial_enabled = self._arterials_enabled(spec)
        # One central axis is enough for a compact district; larger scenes use
        # a cross-shaped pair, yielding roughly the configured 5–10% share.
        central_x = len(x_roads) // 2
        central_y = len(y_roads) // 2
        # Keep the arterial share near 5–10%: compact districts use one spine;
        # only genuinely large cities gain a perpendicular boulevard.
        use_horizontal_arterial = arterial_enabled and spec.building_count >= 100 and spec.arterial_ratio >= 0.06
        for x_index, x in enumerate(x_roads):
            for y_index in range(len(y_roads) - 1):
                start = Point2D(x, y_roads[y_index])
                end = Point2D(x, y_roads[y_index + 1])
                is_arterial = arterial_enabled and (
                    x_index == central_x
                )
                road_class = "arterial" if is_arterial else ("collector" if x_index in (0, len(x_roads) - 1) else "local")
                lanes, road_width, sidewalk_width = self._road_cross_section(
                    spec, road_class,
                    y_index,
                    "vertical",
                )
                semantics = self._road_semantics(spec, road_class, y_index, "vertical")
                segments.append(
                    RoadSegment(
                        id=f"road_vertical_{x_index:02d}_{y_index:02d}",
                        start_junction_id=junction_ids[(x_index, y_index)],
                        end_junction_id=junction_ids[(x_index, y_index + 1)],
                        centerline=(start, end),
                        road_class=road_class,
                        lane_count=lanes,
                        width_m=road_width,
                        sidewalk_width_m=sidewalk_width,
                        **semantics,
                    )
                )

        for y_index, y in enumerate(y_roads):
            for x_index in range(len(x_roads) - 1):
                start = Point2D(x_roads[x_index], y)
                end = Point2D(x_roads[x_index + 1], y)
                is_arterial = use_horizontal_arterial and y_index == central_y
                road_class = "arterial" if is_arterial else ("collector" if y_index in (0, len(y_roads) - 1) else "local")
                lanes, road_width, sidewalk_width = self._road_cross_section(
                    spec, road_class,
                    x_index,
                    "horizontal",
                )
                semantics = self._road_semantics(spec, road_class, x_index, "horizontal")
                segments.append(
                    RoadSegment(
                        id=f"road_horizontal_{y_index:02d}_{x_index:02d}",
                        start_junction_id=junction_ids[(x_index, y_index)],
                        end_junction_id=junction_ids[(x_index + 1, y_index)],
                        centerline=(start, end),
                        road_class=road_class,
                        lane_count=lanes,
                        width_m=road_width,
                        sidewalk_width_m=sidewalk_width,
                        **semantics,
                    )
                )
        if spec.road_pattern in {"organic_hierarchy", "curved_hierarchy", "landscape_adaptive"} and secondary_blocks:
            secondary_rng = rng or random.Random(spec.seed)
            envelope_width, envelope_sidewalk = self._primary_road_envelope(spec)
            clearance = envelope_width / 2 + envelope_sidewalk
            for branch_index, block in enumerate(secondary_blocks):
                if secondary_rng.random() > spec.branch_road_ratio:
                    continue
                left = min(
                    range(len(x_roads)),
                    key=lambda index: abs(x_roads[index] - (block.min_x - clearance)),
                )
                right = min(
                    range(len(x_roads)),
                    key=lambda index: abs(x_roads[index] - (block.max_x + clearance)),
                )
                bottom = min(
                    range(len(y_roads)),
                    key=lambda index: abs(y_roads[index] - (block.min_y - clearance)),
                )
                top = min(
                    range(len(y_roads)),
                    key=lambda index: abs(y_roads[index] - (block.max_y + clearance)),
                )
                corners = (
                    (left, bottom),
                    (right, bottom),
                    (right, top),
                    (left, top),
                )
                start_key = corners[branch_index % len(corners)]
                start_id = junction_ids[start_key]
                start = next(
                    item.position for item in junctions if item.id == start_id
                )
                road_class = "shared_space" if branch_index % 2 == 0 else "service"
                lane_count, road_width, sidewalk_width = self._road_cross_section(
                    spec, road_class, branch_index, "branch"
                )

                if branch_index % 2 == 0:
                    end_key = corners[(branch_index + 2) % len(corners)]
                    end_id = junction_ids[end_key]
                    end = next(
                        item.position for item in junctions if item.id == end_id
                    )
                    road_id = f"road_diagonal_{branch_index:03d}"
                else:
                    end_id = f"junction_branch_terminal_{branch_index:03d}"
                    end = block.center
                    junctions.append(Junction(end_id, end))
                    road_id = f"road_branch_{branch_index:03d}"

                centerline = (start, end)
                if spec.road_pattern in {"curved_hierarchy", "landscape_adaptive"}:
                    from cityg.paths import sample_cubic_bezier
                    # Both controls stay inside this unbuilt block. The Bezier
                    # convex-hull property keeps the path out of occupied blocks;
                    # main grid corridors and all semantic junction IDs are kept.
                    dx, dy = end.x - start.x, end.y - start.y
                    length = math.hypot(dx, dy)
                    bend = min(block.width, block.depth) * 0.12
                    controls = []
                    for t, sign in ((1/3, 1), (2/3, -1)):
                        controls.append(Point2D(
                            max(block.min_x, min(block.max_x, start.x + dx*t - dy/length*bend*sign)),
                            max(block.min_y, min(block.max_y, start.y + dy*t + dx/length*bend*sign)),
                        ))
                    centerline = sample_cubic_bezier(start, *controls, end)
                segments.append(
                    RoadSegment(
                        id=road_id,
                        start_junction_id=start_id,
                        end_junction_id=end_id,
                        centerline=centerline,
                        road_class=road_class,
                        lane_count=1,
                        width_m=road_width,
                        sidewalk_width_m=sidewalk_width,
                        speed_limit_kph=15.0,
                        **self._road_semantics(spec, road_class, branch_index, "branch", branch=True),
                    )
                )
        return RoadNetwork(junctions=junctions, segments=segments)

    @staticmethod
    def _make_blocks(
        spec: CitySpec, x_roads: list[float], y_roads: list[float]
    ) -> list[Bounds2D]:
        envelope_width, envelope_sidewalk = BaselineCityPlanner._primary_road_envelope(spec)
        clearance = envelope_width / 2 + envelope_sidewalk
        blocks: list[Bounds2D] = []
        for y_index in range(len(y_roads) - 1):
            for x_index in range(len(x_roads) - 1):
                block = Bounds2D(
                    x_roads[x_index] + clearance,
                    y_roads[y_index] + clearance,
                    x_roads[x_index + 1] - clearance,
                    y_roads[y_index + 1] - clearance,
                )
                minimum = 2 * spec.parcel_setback_m + 6.0
                if block.width <= minimum or block.depth <= minimum:
                    raise ValueError(
                        "City is too small for the requested building/road/setback configuration"
                    )
                blocks.append(block)
        return blocks

    @staticmethod
    def _allocate_zones(
        zones: tuple[ZoneSpec, ...], building_count: int
    ) -> list[tuple[ZoneSpec, int]]:
        total_weight = sum(zone.weight for zone in zones)
        exact = [building_count * zone.weight / total_weight for zone in zones]
        counts = [math.floor(value) for value in exact]

        if building_count >= len(zones):
            for index, count in enumerate(counts):
                if count == 0:
                    counts[index] = 1

        while sum(counts) > building_count:
            candidates = [i for i, count in enumerate(counts) if count > 1]
            index = min(candidates, key=lambda i: exact[i] - counts[i])
            counts[index] -= 1
        while sum(counts) < building_count:
            index = max(range(len(zones)), key=lambda i: exact[i] - counts[i])
            counts[index] += 1

        return [(zone, count) for zone, count in zip(zones, counts) if count]

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
        entrance_side = frontage_sides[(index + spec.seed) % len(frontage_sides)]
        footprint = self._layout_footprint(
            spec, rng, index, function, parcel_bounds, entrance_side
        )
        from cityg.planning.urban_spatial import fit_building
        footprint = fit_building(spec, index, function, getattr(self, '_active_zone_name', ''),
                                 parcel_bounds, entrance_side, footprint)
        building_id = f"building_{index:03d}"
        floor_count = (
            height_decision.recommended_floors
            if height_decision is not None
            else rng.randint(spec.min_floors, spec.max_floors)
        )
        entrance = self._entrance_for_side(footprint, entrance_side)
        floors = [
            self._make_floor(
                building_id,
                level,
                footprint,
                function,
                spec.rooms_per_floor,
                entrance,
            )
            for level in range(floor_count)
        ]

        corridor_depth = min(max(1.8, footprint.depth * 0.18), footprint.depth * 0.35)
        podium_floors = HighRisePolicy.podium_floors(floor_count)
        reuse_groups = HighRisePolicy.annotate_typical_floors(
            building_id, floors, podium_floors
        )
        connectors = HighRisePolicy.connectors(
            building_id, floor_count, footprint, corridor_depth
        )
        highrise = HighRisePolicy.is_highrise(floor_count)
        landmark = (
            bool(height_decision.landmark)
            if height_decision is not None
            else False
        )
        highrise_palette = DEFAULT_HIGHRISE_MASSING_PALETTE
        highrise_variant = HighRisePolicy.massing_variant(
            building_id=building_id,
            floor_count=floor_count,
            function=function,
            landmark=landmark,
            seed=spec.seed,
            palette=highrise_palette,
        )
        selection = self._select_building_archetype(
            building_id=building_id,
            function=function,
            footprint=footprint,
            floor_count=floor_count,
            highrise=highrise,
            landmark=landmark,
            prototype_id=None,
        )
        if selection.archetype.massing_variant and highrise:
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
                "entrance_side": entrance_side,
                "site_coverage_ratio": round(footprint.area / parcel_bounds.area, 6),
                "layout_variant": index % 8,
                "urban_block_id": urban_block_id,
                "cluster_size": cluster_size,
                "cluster_site_index": site_index,
                "available_frontages": list(frontage_sides),
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
                "urban_morphology_role": (
                    "landmark" if landmark
                    else "core_highrise" if highrise and height_decision and height_decision.centrality >= 0.55
                    else "core_midrise" if height_decision and height_decision.centrality >= 0.55
                    else "edge_lowrise"
                ),
                "frontage_character": (
                    "active_retail" if function in {"commercial", "mixed_use"}
                    else "civic_forecourt" if function == "public_service"
                    else "residential_setback" if function == "residential"
                    else "service_yard"
                ),
            },
        )
        building.metadata.update(selection.to_metadata())
        if selection.archetype.prototype_ids:
            building.metadata["prototype_id"] = selection.archetype.prototype_ids[0]
        return building

    def _select_building_archetype(
        self,
        *,
        building_id: str,
        function: str,
        footprint: Bounds2D,
        floor_count: int,
        highrise: bool,
        landmark: bool,
        prototype_id: str | None,
        preferred_ids: tuple[str, ...] = (),
    ) -> BuildingSelection:
        selection = self.building_selector.select(
            BuildingSelectionContext(
                building_id=building_id,
                function=function,
                floor_count=floor_count,
                width_m=footprint.width,
                depth_m=footprint.depth,
                highrise=highrise,
                landmark=landmark,
                prototype_id=prototype_id,
            ),
            used_archetype_ids=self._used_archetype_ids,
            used_massing_signatures=self._used_massing_signatures,
            preferred_ids=preferred_ids,
        )
        self._used_archetype_ids.add(selection.archetype.archetype_id)
        self._used_massing_signatures.add(selection.archetype.massing_signature)
        return selection

    @staticmethod
    def _entrance_for_side(footprint: Bounds2D, side: str) -> Point2D:
        if side == "east":
            return Point2D(footprint.max_x, footprint.center.y)
        if side == "north":
            return Point2D(footprint.center.x, footprint.max_y)
        if side == "south":
            return Point2D(footprint.center.x, footprint.min_y)
        return Point2D(footprint.min_x, footprint.center.y)

    def _make_floor(
        self,
        building_id: str,
        level: int,
        footprint: Bounds2D,
        building_function: str,
        room_count: int,
        entrance: Point2D,
    ) -> Floor:
        floor_id = f"{building_id}_floor_{level:02d}"
        corridor_depth = min(max(1.8, footprint.depth * 0.18), footprint.depth * 0.35)
        corridor = Bounds2D(
            footprint.min_x,
            footprint.center.y - corridor_depth / 2,
            footprint.max_x,
            footprint.center.y + corridor_depth / 2,
        )
        corridor_id = f"{floor_id}_corridor"
        rooms = [Room(corridor_id, "Main corridor", "corridor", corridor)]
        doors: list[Door] = []
        functions = ROOM_FUNCTIONS.get(building_function, ROOM_FUNCTIONS["mixed_use"])

        north_count = math.ceil(room_count / 2)
        south_count = room_count - north_count
        room_index = 0

        for side, count, min_y, max_y in (
            ("north", north_count, corridor.max_y, footprint.max_y),
            ("south", south_count, footprint.min_y, corridor.min_y),
        ):
            if count == 0:
                continue
            room_width = footprint.width / count
            for side_index in range(count):
                bounds = Bounds2D(
                    footprint.min_x + side_index * room_width,
                    min_y,
                    footprint.min_x + (side_index + 1) * room_width,
                    max_y,
                )
                room_id = f"{floor_id}_room_{room_index:02d}"
                function = functions[(room_index + level) % len(functions)]
                rooms.append(Room(room_id, function.replace("_", " ").title(), function, bounds))
                door_y = corridor.max_y if side == "north" else corridor.min_y
                doors.append(
                    Door(
                        id=f"{room_id}_door",
                        room_a_id=room_id,
                        room_b_id=corridor_id,
                        position=Point2D(bounds.center.x, door_y),
                    )
                )
                room_index += 1

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

        return Floor(
            id=floor_id,
            level=level,
            elevation_m=level * self.floor_height_m,
            height_m=self.floor_height_m,
            rooms=rooms,
            doors=doors,
        )
