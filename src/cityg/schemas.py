"""Canonical semantic data model for CityG.

The model intentionally avoids simulator-specific types. Backends compile this
representation into OpenUSD, OpenDRIVE, Blender scenes, or other formats.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


CCWP_SCHEMA_VERSION = "0.2.0"
NODE_STATUSES = frozenset({"draft", "valid", "compiled", "simulated"})


@dataclass(frozen=True)
class Point2D:
    x: float
    y: float


@dataclass(frozen=True)
class Bounds2D:
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    @property
    def width(self) -> float:
        return self.max_x - self.min_x

    @property
    def depth(self) -> float:
        return self.max_y - self.min_y

    @property
    def area(self) -> float:
        return self.width * self.depth

    @property
    def center(self) -> Point2D:
        return Point2D((self.min_x + self.max_x) / 2, (self.min_y + self.max_y) / 2)

    def inset(self, distance: float) -> "Bounds2D":
        return Bounds2D(
            self.min_x + distance,
            self.min_y + distance,
            self.max_x - distance,
            self.max_y - distance,
        )

    def contains_point(self, point: Point2D, tolerance: float = 1e-6) -> bool:
        return (
            self.min_x - tolerance <= point.x <= self.max_x + tolerance
            and self.min_y - tolerance <= point.y <= self.max_y + tolerance
        )

    def contains_bounds(self, other: "Bounds2D", tolerance: float = 1e-6) -> bool:
        return (
            self.min_x - tolerance <= other.min_x
            and self.min_y - tolerance <= other.min_y
            and self.max_x + tolerance >= other.max_x
            and self.max_y + tolerance >= other.max_y
        )

    def overlaps_area(self, other: "Bounds2D", tolerance: float = 1e-6) -> bool:
        overlap_x = min(self.max_x, other.max_x) - max(self.min_x, other.min_x)
        overlap_y = min(self.max_y, other.max_y) - max(self.min_y, other.min_y)
        return overlap_x > tolerance and overlap_y > tolerance


@dataclass(frozen=True)
class ZoneSpec:
    name: str
    function: str
    weight: float = 1.0
    architecture: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CitySpec:
    name: str = "cityg_demo"
    width_m: float = 600.0
    depth_m: float = 600.0
    building_count: int = 36
    min_floors: int = 2
    max_floors: int = 5
    rooms_per_floor: int = 6
    room_count_strategy: str = "adaptive"
    road_width_m: float = 12.0
    sidewalk_width_m: float = 2.5
    parcel_setback_m: float = 4.0
    layout_style: str = "organic_grid"
    open_space_ratio: float = 0.14
    layout_irregularity: float = 0.35
    road_pattern: str = "organic_hierarchy"
    buildings_per_block: int = 2
    branch_road_ratio: float = 0.65
    parcel_layout: str = "rectangular"
    river_mode: str = "none"
    river_width_m: float = 24.0
    river_bank_width_m: float = 5.0
    river_setback_m: float = 8.0
    morphology: dict[str, Any] = field(default_factory=dict)
    arterial_ratio: float = 0.08
    one_way_ratio: float = 0.08
    height_strategy: str = "zoned_skyline"
    highrise_ratio: float = 0.15
    landmark_count: int = 2
    skyline_strength: float = 0.75
    architecture: dict[str, Any] = field(default_factory=dict)
    interior_requirements: list[dict[str, Any]] = field(default_factory=list)
    urban_requirements: list[dict[str, Any]] = field(default_factory=list)
    seed: int = 0
    zones: tuple[ZoneSpec, ...] = (
        ZoneSpec("mixed_zone", "mixed_use", 1.0),
    )

    walking_requirements: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CitySpec":
        known = {field_name for field_name in cls.__dataclass_fields__}
        unknown = sorted(set(data) - known)
        if unknown:
            raise ValueError(f"Unknown CitySpec fields: {', '.join(unknown)}")

        raw_zones = data.get("zones")
        zones = (
            tuple(ZoneSpec(**zone) for zone in raw_zones)
            if raw_zones is not None
            else cls.__dataclass_fields__["zones"].default
        )
        values = {key: value for key, value in data.items() if key != "zones"}
        spec = cls(**values, zones=zones)
        spec.validate()
        return spec

    def validate(self) -> None:
        from cityg.architecture import validate_architecture
        from cityg.morphology import validate_morphology
        from cityg.interior_requirements import validate_requirements
        validate_requirements(self.interior_requirements)
        from cityg.urban_requirements import validate as validate_urban_requirements
        validate_urban_requirements(self.urban_requirements, spec=self)
        from cityg.walking_requirements import validate as validate_walks
        validate_walks(self.walking_requirements)
        if any(r['opposite_banks'] for r in self.walking_requirements) and self.river_mode == 'none':
            raise ValueError('An opposite-bank walking requirement needs river geometry (river_mode=meandering)')
        validate_morphology(self.morphology)
        if self.morphology and self.road_pattern != "landscape_adaptive":
            raise ValueError("morphology requires road_pattern=landscape_adaptive")
        validate_architecture(self.architecture)
        for zone in self.zones:
            validate_architecture(zone.architecture)
        if self.parcel_layout not in {"rectangular", "polygonal"}:
            raise ValueError("parcel_layout must be rectangular or polygonal")
        if self.river_mode not in {"none", "meandering"}:
            raise ValueError("river_mode must be none or meandering")
        if not all(math.isfinite(v) for v in (self.river_width_m, self.river_bank_width_m, self.river_setback_m)):
            raise ValueError("River dimensions must be finite")
        if self.river_width_m < 4 or self.river_bank_width_m < 2 or self.river_setback_m < 3:
            raise ValueError("River requires width >= 4 m, banks >= 2 m and setback >= 3 m")
        if not self.name.strip():
            raise ValueError("City name must not be empty")
        if self.width_m <= 0 or self.depth_m <= 0:
            raise ValueError("City dimensions must be positive")
        if self.building_count < 1:
            raise ValueError("building_count must be at least 1")
        if self.min_floors < 1 or self.max_floors < self.min_floors:
            raise ValueError("Floor range is invalid")
        if self.rooms_per_floor < 1:
            raise ValueError("rooms_per_floor must be at least 1")
        if self.room_count_strategy not in {"adaptive", "fixed"}:
            raise ValueError("room_count_strategy must be adaptive or fixed")
        if self.road_width_m <= 0 or self.sidewalk_width_m < 0:
            raise ValueError("Road width must be positive and sidewalk width non-negative")
        if self.parcel_setback_m < 0:
            raise ValueError("parcel_setback_m must be non-negative")
        if self.layout_style not in {"regular_grid", "organic_grid"}:
            raise ValueError("layout_style must be regular_grid or organic_grid")
        if not 0.0 <= self.open_space_ratio <= 0.35:
            raise ValueError("open_space_ratio must be within [0, 0.35]")
        if not 0.0 <= self.layout_irregularity <= 1.0:
            raise ValueError("layout_irregularity must be within [0, 1]")
        if self.road_pattern not in {"connected_grid", "organic_hierarchy", "curved_hierarchy", "landscape_adaptive"}:
            raise ValueError(
                "unsupported road_pattern"
            )
        if not 1 <= self.buildings_per_block <= 4:
            raise ValueError("buildings_per_block must be within [1, 4]")
        if not 0.0 <= self.branch_road_ratio <= 1.0:
            raise ValueError("branch_road_ratio must be within [0, 1]")
        if not 0.0 <= self.arterial_ratio <= 0.30:
            raise ValueError("arterial_ratio must be within [0, 0.30]")
        if not 0.0 <= self.one_way_ratio <= 0.50:
            raise ValueError("one_way_ratio must be within [0, 0.50]")
        if self.height_strategy not in {"uniform_random", "zoned_skyline"}:
            raise ValueError(
                "height_strategy must be uniform_random or zoned_skyline"
            )
        if not 0.0 <= self.highrise_ratio <= 0.5:
            raise ValueError("highrise_ratio must be within [0, 0.5]")
        if not 0 <= self.landmark_count <= 10:
            raise ValueError("landmark_count must be within [0, 10]")
        if not 0.0 <= self.skyline_strength <= 1.0:
            raise ValueError("skyline_strength must be within [0, 1]")
        if not self.zones:
            raise ValueError("At least one functional zone is required")
        if any(zone.weight <= 0 for zone in self.zones):
            raise ValueError("Zone weights must be positive")


@dataclass
class Junction:
    id: str
    position: Point2D


@dataclass
class RoadSegment:
    id: str
    start_junction_id: str
    end_junction_id: str
    centerline: tuple[Point2D, ...]  # sampled path; endpoints are semantic junctions
    road_class: str = "local"
    lane_count: int = 2
    width_m: float = 12.0
    sidewalk_width_m: float = 2.5
    speed_limit_kph: float = 30.0
    # Road semantics are optional so older city.json files remain loadable.
    directionality: str = "bidirectional"
    median_width_m: float = 0.0
    parking_allowed: bool = True
    bike_lane: bool = False
    bus_lane: bool = False
    turn_lane: bool = False
    intersection_control: str = "priority"


@dataclass
class RoadNetwork:
    junctions: list[Junction] = field(default_factory=list)
    segments: list[RoadSegment] = field(default_factory=list)


@dataclass
class River:
    id: str
    name: str
    centerline: tuple[Point2D, ...]
    width_m: float = 24.0
    bank_width_m: float = 5.0
    setback_m: float = 8.0
    water_elevation_m: float = -3.5
    bed_elevation_m: float = -5.0


@dataclass
class Bridge:
    id: str
    road_id: str
    river_id: str
    start_m: float
    end_m: float
    deck_elevation_m: float = 0.0
    structural_depth_m: float = 0.55
    min_clearance_m: float = 2.5


@dataclass
class Door:
    id: str
    room_a_id: str
    room_b_id: str | None
    position: Point2D
    width_m: float = 0.9
    door_type: str = "interior"
    interactive: bool = True


@dataclass
class Room:
    id: str
    name: str
    function: str
    bounds: Bounds2D
    height_m: float = 3.0
    object_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class InteriorObject:
    """Simulator-neutral indoor object placed by the floor detail planner."""

    id: str
    room_id: str
    category: str
    asset_id: str
    position: Point2D
    width_m: float
    depth_m: float
    height_m: float
    rotation_deg: float = 0.0
    interactive: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def function(self) -> str:
        return self.category

    @property
    def bounds(self) -> Bounds2D:
        angle = math.radians(self.rotation_deg)
        width = abs(math.cos(angle)) * self.width_m + abs(math.sin(angle)) * self.depth_m
        depth = abs(math.sin(angle)) * self.width_m + abs(math.cos(angle)) * self.depth_m
        return Bounds2D(
            self.position.x - width / 2,
            self.position.y - depth / 2,
            self.position.x + width / 2,
            self.position.y + depth / 2,
        )


@dataclass
class Floor:
    id: str
    level: int
    elevation_m: float
    height_m: float
    rooms: list[Room] = field(default_factory=list)
    doors: list[Door] = field(default_factory=list)
    objects: list[InteriorObject] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class VerticalConnector:
    id: str
    connector_type: str
    bounds: Bounds2D
    from_level: int
    to_level: int
    interactive: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Building:
    id: str
    name: str
    function: str
    footprint: Bounds2D
    entrance: Point2D
    floors: list[Floor] = field(default_factory=list)
    vertical_connectors: list[VerticalConnector] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Parcel:
    id: str
    bounds: Bounds2D
    buildings: list[Building] = field(default_factory=list)
    boundary: tuple[Point2D, ...] = ()
    holes: tuple[tuple[Point2D, ...], ...] = ()


@dataclass
class District:
    id: str
    name: str
    function: str
    bounds: Bounds2D
    parcels: list[Parcel] = field(default_factory=list)


@dataclass
class Intent:
    """Human- and machine-readable purpose attached to a CCWP entity."""

    description: str
    function: str
    tags: list[str] = field(default_factory=list)


@dataclass
class GeometryBudget:
    """Optional geometric limits inherited or checked across hierarchy levels."""

    coordinate_system: str = "right_handed_z_up_meters"
    max_width_m: float | None = None
    max_depth_m: float | None = None
    max_height_m: float | None = None
    max_area_m2: float | None = None


@dataclass
class InteractionState:
    """Simulator-neutral persistent state for an entity."""

    mobility: str = "static"
    state: str = "default"
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorldNode:
    """CCWP overlay for one canonical entity."""

    entity_id: str
    entity_type: str
    parent_id: str | None
    intent: Intent
    geometry: GeometryBudget = field(default_factory=GeometryBudget)
    contract_ids: list[str] = field(default_factory=list)
    relation_ids: list[str] = field(default_factory=list)
    artifact_ids: list[str] = field(default_factory=list)
    provenance_ids: list[str] = field(default_factory=list)
    state: InteractionState = field(default_factory=InteractionState)
    status: str = "draft"
    version: int = 1
    locked: bool = False


@dataclass
class Contract:
    """A deterministic constraint carried by one or more CCWP nodes."""

    id: str
    kind: str
    scope_id: str
    subject_ids: list[str]
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)
    inherited_from: str | None = None
    severity: str = "error"


@dataclass
class Relation:
    """Typed directed relation between canonical entities."""

    id: str
    relation_type: str
    source_id: str
    target_ids: list[str]
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class Artifact:
    """A generated or external compilation product owned by a CCWP node."""

    id: str
    owner_id: str
    artifact_type: str
    uri: str
    media_type: str = "application/octet-stream"
    checksum: str | None = None
    status: str = "planned"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProvenanceRecord:
    """Reproducibility record for generation or repair operations."""

    id: str
    entity_id: str
    producer: str
    operation: str
    seed: int | None = None
    model_id: str | None = None
    prompt_hash: str | None = None
    parent_record_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorldProgram:
    """Constraint-Carrying World Program registry embedded in a City manifest."""

    nodes: list[WorldNode] = field(default_factory=list)
    contracts: list[Contract] = field(default_factory=list)
    relations: list[Relation] = field(default_factory=list)
    artifacts: list[Artifact] = field(default_factory=list)
    provenance: list[ProvenanceRecord] = field(default_factory=list)


@dataclass
class City:
    id: str
    name: str
    bounds: Bounds2D
    road_network: RoadNetwork
    districts: list[District] = field(default_factory=list)
    coordinate_system: str = "right_handed_z_up_meters"
    schema_version: str = CCWP_SCHEMA_VERSION
    metadata: dict[str, Any] = field(default_factory=dict)
    world_program: WorldProgram = field(default_factory=WorldProgram)
    rivers: list[River] = field(default_factory=list)
    bridges: list[Bridge] = field(default_factory=list)

    def iter_parcels(self):
        for district in self.districts:
            yield from district.parcels

    def iter_buildings(self):
        for parcel in self.iter_parcels():
            yield from parcel.buildings

    def iter_floors(self):
        for building in self.iter_buildings():
            yield from building.floors

    def iter_rooms(self):
        for floor in self.iter_floors():
            yield from floor.rooms

    def iter_objects(self):
        for floor in self.iter_floors():
            yield from floor.objects

    def iter_entities(self):
        """Yield ``(entity, entity_type, parent_id)`` in stable hierarchy order."""

        yield self, "city", None
        for river in self.rivers:
            yield river, "river", self.id
        for bridge in self.bridges:
            yield bridge, "bridge", self.id
        for junction in self.road_network.junctions:
            yield junction, "junction", self.id
        for segment in self.road_network.segments:
            yield segment, "road_segment", self.id
        for district in self.districts:
            yield district, "district", self.id
            for parcel in district.parcels:
                yield parcel, "parcel", district.id
                for building in parcel.buildings:
                    yield building, "building", parcel.id
                    for connector in building.vertical_connectors:
                        yield connector, "vertical_connector", building.id
                    for floor in building.floors:
                        yield floor, "floor", building.id
                        for room in floor.rooms:
                            yield room, "room", floor.id
                            for obj in floor.objects:
                                if obj.room_id == room.id:
                                    yield obj, "interior_object", room.id
                        for door in floor.doors:
                            yield door, "door", floor.id
