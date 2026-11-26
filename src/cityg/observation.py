"""Deterministic adaptive observation planning for CityG scenes.

The observation layer deliberately sits between compilation and VLM review.  It
does not ask a model to invent camera coordinates.  Instead it extracts a
bounded set of semantically meaningful candidate views from the canonical City
and greedily selects views that maximize coverage, risk exposure, and visual
novelty.  The resulting plan is an auditable input to a renderer such as the
portable Web Viewer or a headless browser.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from cityg.planning.appearance import appearance_program_for_city
from cityg.planning.streetscape import StreetProgramPlanner
from cityg.schemas import Building, City, RoadSegment, Room
from cityg.serialization import to_primitive
from cityg.visual_evidence import room_visual_contract


VIEW_KINDS = frozenset(
    {"global", "road", "landscape", "building_exterior", "room_interior"}
)


@dataclass(frozen=True)
class _RealizedPrimitive:
    owner_id: str
    semantic_class: str
    center: tuple[float, float, float]
    size: tuple[float, float, float]
    rotation_z_deg: float
    metadata: Mapping[str, Any]


@dataclass(frozen=True)
class _Footprint:
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    @property
    def center(self) -> tuple[float, float]:
        return ((self.min_x + self.max_x) / 2, (self.min_y + self.max_y) / 2)


@dataclass(frozen=True)
class _RealizedRoomFrame:
    center_x: float
    center_y: float
    width: float
    depth: float
    rotation_rad: float
    elevation: float
    wall_count: int
    furniture_count: int
    local_wall_bounds: _Footprint
    local_audit_bounds: _Footprint
    furniture_footprints: tuple[_Footprint, ...]
    door_points: tuple[tuple[float, float], ...]

    def local_to_world(self, x: float, y: float) -> tuple[float, float]:
        cos = math.cos(self.rotation_rad)
        sin = math.sin(self.rotation_rad)
        return (
            self.center_x + x * cos - y * sin,
            self.center_y + x * sin + y * cos,
        )


def _field(value: object, name: str, default: object = None) -> object:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _xyz(value: object) -> tuple[float, float, float]:
    return (
        float(_field(value, "x", 0.0)),
        float(_field(value, "y", 0.0)),
        float(_field(value, "z", 0.0)),
    )


def _normalized_primitives(geometry_manifest: object | None) -> list[_RealizedPrimitive]:
    if geometry_manifest is None:
        return []
    raw_primitives = _field(geometry_manifest, "primitives", ()) or ()
    result: list[_RealizedPrimitive] = []
    for primitive in raw_primitives:
        result.append(
            _RealizedPrimitive(
                owner_id=str(_field(primitive, "owner_id", "")),
                semantic_class=str(_field(primitive, "semantic_class", "")),
                center=_xyz(_field(primitive, "center", {})),
                size=_xyz(_field(primitive, "size", {})),
                rotation_z_deg=float(_field(primitive, "rotation_z_deg", 0.0) or 0.0),
                metadata=_field(primitive, "metadata", {}) or {},
            )
        )
    return result


def _primitive_corners_local(
    primitive: _RealizedPrimitive,
    *,
    frame_rotation_rad: float,
) -> tuple[tuple[float, float], ...]:
    primitive_rotation = math.radians(primitive.rotation_z_deg)
    primitive_cos = math.cos(primitive_rotation)
    primitive_sin = math.sin(primitive_rotation)
    frame_cos = math.cos(frame_rotation_rad)
    frame_sin = math.sin(frame_rotation_rad)
    points: list[tuple[float, float]] = []
    for sx in (-0.5, 0.5):
        for sy in (-0.5, 0.5):
            world_x = (
                primitive.center[0]
                + primitive_cos * sx * primitive.size[0]
                - primitive_sin * sy * primitive.size[1]
            )
            world_y = (
                primitive.center[1]
                + primitive_sin * sx * primitive.size[0]
                + primitive_cos * sy * primitive.size[1]
            )
            points.append(
                (
                    world_x * frame_cos + world_y * frame_sin,
                    -world_x * frame_sin + world_y * frame_cos,
                )
            )
    return tuple(points)


def _bounds_of(points: Iterable[tuple[float, float]]) -> _Footprint | None:
    values = tuple(points)
    if not values:
        return None
    return _Footprint(
        min(item[0] for item in values),
        min(item[1] for item in values),
        max(item[0] for item in values),
        max(item[1] for item in values),
    )


def _union_bounds(bounds: Iterable[_Footprint]) -> _Footprint | None:
    values = tuple(bounds)
    if not values:
        return None
    return _Footprint(
        min(item.min_x for item in values),
        min(item.min_y for item in values),
        max(item.max_x for item in values),
        max(item.max_y for item in values),
    )


class _RealizedRoomIndex:
    """Bind canonical rooms to compiled wall, door, and furniture geometry."""

    def __init__(self, city: City, geometry_manifest: object) -> None:
        self._primitives = _normalized_primitives(geometry_manifest)
        self.surface_reports = (_field(geometry_manifest, "metadata", {}) or {}).get("room_surface_items", {})
        self.sufficiency_reports = (_field(geometry_manifest, "metadata", {}) or {}).get("room_furnishing_sufficiency", {})
        self._room_ids = {room.id for room in city.iter_rooms()}
        self._object_rooms = {
            item.id: item.room_id
            for floor in city.iter_floors()
            for item in floor.objects
        }
        self._door_rooms = {
            door.id: tuple(
                room_id
                for room_id in (door.room_a_id, door.room_b_id)
                if room_id in self._room_ids
            )
            for floor in city.iter_floors()
            for door in floor.doors
        }
        self._walls: dict[str, list[_RealizedPrimitive]] = defaultdict(list)
        self._furniture: dict[str, list[_RealizedPrimitive]] = defaultdict(list)
        self._doors: dict[str, list[_RealizedPrimitive]] = defaultdict(list)
        for primitive in self._primitives:
            metadata_rooms = tuple(
                str(item)
                for item in primitive.metadata.get("room_ids", ())
                if str(item) in self._room_ids
            )
            if primitive.semantic_class == "interior_wall":
                room_ids = metadata_rooms or (
                    (primitive.owner_id,) if primitive.owner_id in self._room_ids else ()
                )
                for room_id in room_ids:
                    self._walls[room_id].append(primitive)
            elif primitive.semantic_class.startswith("furniture_"):
                room_id = self._object_rooms.get(primitive.owner_id)
                if room_id:
                    self._furniture[room_id].append(primitive)
            elif primitive.semantic_class == "door":
                room_ids = metadata_rooms or self._door_rooms.get(primitive.owner_id, ())
                for room_id in room_ids:
                    self._doors[room_id].append(primitive)

    def compiled_object_ids(self, room_id: str) -> list[str]:
        return sorted({primitive.owner_id for primitive in self._furniture.get(room_id, ())})

    def frame(self, building: Building, floor: object, room: Room) -> _RealizedRoomFrame | None:
        walls = self._walls.get(room.id, ())
        if not walls:
            return None
        rotation_deg = float(
            building.metadata.get("orientation_contract", {}).get(
                "orientation_deg", building.metadata.get("orientation_deg", 0.0)
            )
        )
        rotation_rad = math.radians(rotation_deg)
        wall_points = tuple(
            point
            for primitive in walls
            for point in _primitive_corners_local(
                primitive, frame_rotation_rad=rotation_rad
            )
        )
        wall_bounds = _bounds_of(wall_points)
        if (
            wall_bounds is None
            or wall_bounds.max_x - wall_bounds.min_x <= 0.5
            or wall_bounds.max_y - wall_bounds.min_y <= 0.5
        ):
            return None

        open_plan = (
            room.function == "corridor"
            or room.metadata.get("open_plan") is True
            or room.metadata.get("space_kind") == "open_plan"
        )
        if not open_plan and not self._has_all_canonical_boundaries(room, walls):
            return None

        furniture_bounds = tuple(
            bound
            for primitive in self._furniture.get(room.id, ())
            if (
                bound := _bounds_of(
                    _primitive_corners_local(
                        primitive, frame_rotation_rad=rotation_rad
                    )
                )
            ) is not None
        )
        audit_bounds = _union_bounds((wall_bounds, *furniture_bounds)) or wall_bounds
        local_center_x, local_center_y = wall_bounds.center
        frame_cos = math.cos(rotation_rad)
        frame_sin = math.sin(rotation_rad)
        center_x = local_center_x * frame_cos - local_center_y * frame_sin
        center_y = local_center_x * frame_sin + local_center_y * frame_cos
        door_points = tuple(
            (
                primitive.center[0] * frame_cos + primitive.center[1] * frame_sin
                - local_center_x,
                -primitive.center[0] * frame_sin + primitive.center[1] * frame_cos
                - local_center_y,
            )
            for primitive in self._doors.get(room.id, ())
        )
        relative_furniture = tuple(
            _Footprint(
                item.min_x - local_center_x,
                item.min_y - local_center_y,
                item.max_x - local_center_x,
                item.max_y - local_center_y,
            )
            for item in furniture_bounds
        )
        return _RealizedRoomFrame(
            center_x=center_x,
            center_y=center_y,
            width=wall_bounds.max_x - wall_bounds.min_x,
            depth=wall_bounds.max_y - wall_bounds.min_y,
            rotation_rad=rotation_rad,
            elevation=float(_field(floor, "elevation_m", 0.0)),
            wall_count=len(walls),
            furniture_count=len(furniture_bounds),
            local_wall_bounds=_Footprint(
                wall_bounds.min_x - local_center_x,
                wall_bounds.min_y - local_center_y,
                wall_bounds.max_x - local_center_x,
                wall_bounds.max_y - local_center_y,
            ),
            local_audit_bounds=_Footprint(
                audit_bounds.min_x - local_center_x,
                audit_bounds.min_y - local_center_y,
                audit_bounds.max_x - local_center_x,
                audit_bounds.max_y - local_center_y,
            ),
            furniture_footprints=relative_furniture,
            door_points=door_points,
        )

    @staticmethod
    def _has_all_canonical_boundaries(
        room: Room, walls: Sequence[_RealizedPrimitive]
    ) -> bool:
        tolerance = 1e-3

        def has_boundary(value: float, horizontal: bool, side: str) -> bool:
            for wall in walls:
                # Irregular-massing room isolation closes the *realized*
                # footprint, whose edge need not equal the template boundary.
                if (wall.metadata.get("wall_role") == "room_view_cap"
                        and wall.metadata.get("room_isolation_cap") is True
                        and wall.metadata.get("wall_side") == side):
                    return True
                boundary = wall.metadata.get("canonical_boundary")
                if boundary is None or abs(float(boundary) - value) > tolerance:
                    continue
                if horizontal and wall.size[0] >= wall.size[1]:
                    return True
                if not horizontal and wall.size[1] >= wall.size[0]:
                    return True
            return False

        return all(
            (
                has_boundary(room.bounds.min_y, True, "south"),
                has_boundary(room.bounds.max_y, True, "north"),
                has_boundary(room.bounds.min_x, False, "west"),
                has_boundary(room.bounds.max_x, False, "east"),
            )
        )


def _canonical_room_frame(floor: object, room: Room) -> _RealizedRoomFrame:
    """Compatibility frame for planning stages that have not compiled geometry."""
    center = room.bounds.center
    furniture: list[_Footprint] = []
    for item in _field(floor, "objects", ()) or ():
        if _field(item, "room_id") != room.id:
            continue
        position = _field(item, "position", {})
        local_x = float(_field(position, "x", center.x)) - center.x
        local_y = float(_field(position, "y", center.y)) - center.y
        half_width = float(_field(item, "width_m", 0.5)) / 2
        half_depth = float(_field(item, "depth_m", 0.5)) / 2
        furniture.append(
            _Footprint(
                local_x - half_width,
                local_y - half_depth,
                local_x + half_width,
                local_y + half_depth,
            )
        )
    wall_bounds = _Footprint(
        -room.bounds.width / 2,
        -room.bounds.depth / 2,
        room.bounds.width / 2,
        room.bounds.depth / 2,
    )
    audit_bounds = _union_bounds((wall_bounds, *furniture)) or wall_bounds
    door_points = tuple(
        (
            float(_field(_field(door, "position", {}), "x", center.x)) - center.x,
            float(_field(_field(door, "position", {}), "y", center.y)) - center.y,
        )
        for door in (_field(floor, "doors", ()) or ())
        if room.id
        in {
            _field(door, "room_a_id"),
            _field(door, "room_b_id"),
        }
    )
    return _RealizedRoomFrame(
        center_x=center.x,
        center_y=center.y,
        width=room.bounds.width,
        depth=room.bounds.depth,
        rotation_rad=0.0,
        elevation=float(_field(floor, "elevation_m", 0.0)),
        wall_count=4,
        furniture_count=len(furniture),
        local_wall_bounds=wall_bounds,
        local_audit_bounds=audit_bounds,
        furniture_footprints=tuple(furniture),
        door_points=door_points,
    )


def _distance_to_footprint(point: tuple[float, float], bounds: _Footprint) -> float:
    dx = max(bounds.min_x - point[0], 0.0, point[0] - bounds.max_x)
    dy = max(bounds.min_y - point[1], 0.0, point[1] - bounds.max_y)
    return math.hypot(dx, dy)


@dataclass(frozen=True)
class ViewSpec:
    """One renderer-independent camera request."""

    view_id: str
    kind: str
    purpose: str
    target_entity_ids: tuple[str, ...]
    camera_position: tuple[float, float, float]
    look_at: tuple[float, float, float]
    coverage_entity_ids: tuple[str, ...] = ()
    up: tuple[float, float, float] = (0.0, 0.0, 1.0)
    fov_deg: float = 46.0
    mode: str = "full"
    appearance: str = "presentation"
    auto_cutaway: bool = False
    risk_score: float = 0.0
    novelty_key: str = ""
    semantic_context: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.kind not in VIEW_KINDS:
            raise ValueError(f"unsupported observation view kind: {self.kind}")
        if not self.view_id.strip():
            raise ValueError("view_id must not be empty")
        if not self.target_entity_ids:
            raise ValueError("observation view must target at least one entity")
        if self.fov_deg <= 0 or self.fov_deg >= 180:
            raise ValueError("fov_deg must be within (0, 180)")

    @property
    def covered_entities(self) -> tuple[str, ...]:
        """Entities this view claims to inspect for greedy selection.

        A global view can contain the whole city visually, but it must not be
        treated as having inspected every room or facade in the coverage
        objective.  Fine-grained views therefore carry their own coverage set.
        """
        return self.coverage_entity_ids or self.target_entity_ids

    def to_dict(self) -> dict[str, object]:
        return to_primitive(self)


def fit_capture_view(view: dict, *, width: float, height: float) -> dict:
    """Fit a top-down room audit to the actual canvas, not the browser window.

    The sidebar/inspector can make a nominal landscape page's canvas portrait.
    Preserve the planned horizontal pose/FOV and only raise the top-down camera.
    Capture records this effective view so evidence remains reproducible.
    """
    bounds = view.get('semantic_context', {}).get('top_down_audit_bounds_world')
    if not bounds:
        return view
    if width <= 0 or height <= 0:
        raise ValueError('capture canvas dimensions must be positive')
    position, target = view['camera_position'], view['look_at']
    if (view.get('kind') != 'room_interior'
            or abs(position[0]-target[0]) > 1e-6 or abs(position[1]-target[1]) > 1e-6
            or tuple(view.get('up', ())) != (0.0, 1.0, 0.0)):
        return view
    aspect = width/height
    half_span = max((bounds[3]-bounds[0])/aspect, bounds[4]-bounds[1])/2
    distance = 1.08*half_span/math.tan(math.radians(view.get('fov_deg',50.0))/2)
    return {**view, 'camera_position':[position[0], position[1], max(position[2],bounds[5]+distance)]}


@dataclass(frozen=True)
class ObservationPlan:
    """Selected views plus candidate and coverage metadata."""

    scene_id: str
    max_views: int
    risk_entity_ids: tuple[str, ...]
    candidate_count: int
    selected_views: tuple[ViewSpec, ...]
    covered_entity_ids: tuple[str, ...]
    uncovered_risk_entity_ids: tuple[str, ...]
    selection_policy: str = "coverage_risk_novelty_greedy_v1"
    candidates: tuple[ViewSpec, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, object]:
        return {
            "scene_id": self.scene_id,
            "max_views": self.max_views,
            "risk_entity_ids": list(self.risk_entity_ids),
            "candidate_count": self.candidate_count,
            "selected_views": [view.to_dict() for view in self.selected_views],
            "covered_entity_ids": list(self.covered_entity_ids),
            "uncovered_risk_entity_ids": list(self.uncovered_risk_entity_ids),
            "selection_policy": self.selection_policy,
            "candidates": [view.to_dict() for view in self.candidates],
        }


class AdaptiveObservationPlanner:
    """Create and select camera views without model-generated coordinates."""

    def __init__(
        self,
        *,
        max_views: int = 12,
        min_global_views: int = 2,
        include_room_views: bool = True,
    ) -> None:
        if max_views < 1:
            raise ValueError("max_views must be positive")
        if min_global_views < 1:
            raise ValueError("min_global_views must be positive")
        self.max_views = max_views
        self.min_global_views = min_global_views
        self.include_room_views = include_room_views
        self.minimum_diversity_views = {
            "road": 2,
            "building_exterior": 2,
            "landscape": 1,
            "room_interior": 2 if include_room_views else 0,
        }

    def plan(
        self,
        city: City,
        *,
        risk_entity_ids: Iterable[str] = (),
        max_views: int | None = None,
        geometry_manifest: object | None = None,
    ) -> ObservationPlan:
        budget = self.max_views if max_views is None else max_views
        if budget < 1:
            raise ValueError("max_views must be positive")
        risks = tuple(sorted({str(item) for item in risk_entity_ids if str(item)}))
        realized_rooms = (
            _RealizedRoomIndex(city, geometry_manifest)
            if geometry_manifest is not None
            else None
        )
        candidates = self._deduplicate(
            [
                *self._global_views(city),
                *self._road_views(city, risks),
                *self._intersection_views(city, risks),
                *self._waterfront_views(city, risks),
                *self._landscape_views(city, risks),
                *self._building_views(city, risks),
                *(
                    self._room_views(city, risks, realized_rooms)
                    if self.include_room_views
                    else []
                ),
            ]
        )
        selected = self._select(candidates, budget, risks)
        covered = tuple(
            sorted({entity for view in selected for entity in view.covered_entities})
        )
        uncovered_risks = tuple(sorted(set(risks) - set(covered)))
        return ObservationPlan(
            scene_id=city.id,
            max_views=budget,
            risk_entity_ids=risks,
            candidate_count=len(candidates),
            selected_views=tuple(selected),
            covered_entity_ids=covered,
            uncovered_risk_entity_ids=uncovered_risks,
            selection_policy=(
                "coverage_risk_novelty_realized_geometry_v2"
                if geometry_manifest is not None
                else "coverage_risk_novelty_greedy_v1"
            ),
            candidates=tuple(candidates),
        )

    def _global_views(self, city: City) -> list[ViewSpec]:
        center = city.bounds.center
        extent = max(city.bounds.width, city.bounds.depth, 1.0)
        max_height = max(
            (floor.elevation_m + floor.height_m for floor in city.iter_floors()),
            default=6.0,
        )
        distance = max(80.0, extent * 1.35)
        targets = tuple(
            [city.id]
            + [segment.id for segment in city.road_network.segments]
            + [building.id for building in city.iter_buildings()]
        )
        views: list[ViewSpec] = []
        for index, azimuth in enumerate((45.0, 135.0, 225.0, 315.0)):
            angle = math.radians(azimuth)
            views.append(
                ViewSpec(
                    view_id=f"global_iso_{index:02d}",
                    kind="global",
                    purpose="检查城市总体布局、道路网络和天际线",
                    target_entity_ids=targets,
                    coverage_entity_ids=(city.id,),
                    camera_position=(
                        center.x + math.cos(angle) * distance,
                        center.y + math.sin(angle) * distance,
                        max(30.0, max_height * 0.65, distance * 0.68),
                    ),
                    look_at=(center.x, center.y, max_height * 0.28),
                    mode="overview",
                    novelty_key=f"global_azimuth_{int(azimuth)}",
                )
            )
        views.append(
            ViewSpec(
                view_id="global_top_00",
                kind="global",
                purpose="检查街区覆盖率、空地和道路拓扑",
                target_entity_ids=targets,
                camera_position=(center.x, center.y, max(100.0, distance * 1.25)),
                look_at=(center.x, center.y, 0.0),
                coverage_entity_ids=(city.id,),
                up=(0.0, 1.0, 0.0),
                mode="overview",
                novelty_key="global_top",
            )
        )
        return views

    def _road_views(self, city: City, risks: Sequence[str]) -> list[ViewSpec]:
        views: list[ViewSpec] = []
        street_program = StreetProgramPlanner().plan(
            city, appearance_program_for_city(city)
        )
        programs = {item.road_id: item for item in street_program.segments}
        for segment in city.road_network.segments:
            program = programs[segment.id]
            from cityg.paths import PlanarPath2D
            path = PlanarPath2D(segment.centerline)
            length = path.length
            risk = 1.0 if segment.id in risks else 0.0
            for side in (1, -1) if risk else (1,):
                along = min(max(7.0, length * 0.22), max(7.0, length - 8.0))
                if side < 0:
                    along = length - along
                direction = side
                lane_offset = segment.width_m * 0.22 * side
                position = path.point(along, lane_offset)
                camera_x, camera_y = position.x, position.y
                look_distance = min(24.0, max(8.0, length * 0.32))
                target = path.point(along + look_distance * direction, lane_offset)
                views.append(
                    ViewSpec(
                        view_id=f"{segment.id}_road_{'a' if side == 1 else 'b'}",
                        kind="road",
                        purpose="以道路第一视角检查车道、行道树、车辆、行人和首层街道界面",
                        target_entity_ids=(
                            segment.id,
                            segment.start_junction_id,
                            segment.end_junction_id,
                            *program.adjacent_building_ids,
                        ),
                        coverage_entity_ids=(segment.id, *program.adjacent_building_ids),
                        camera_position=(
                            camera_x,
                            camera_y,
                            1.70,
                        ),
                        look_at=(
                            target.x,
                            target.y,
                            1.58,
                        ),
                        mode="overview",
                        fov_deg=62.0,
                        risk_score=risk + (0.28 if program.activity_level == "high" else 0.12 if program.activity_level == "medium" else 0.0),
                        novelty_key=f"street_archetype_{program.archetype}",
                        semantic_context={
                            "road_id": segment.id,
                            "adjacent_appearance_plans": {
                                b.id: b.metadata.get("appearance_plan", {})
                                for b in city.iter_buildings()
                                if b.id in program.adjacent_building_ids
                            },
                            "street_archetype": program.archetype,
                            "dominant_function": program.dominant_function,
                            "activity_level": program.activity_level,
                            "frontage_treatment": program.frontage_treatment,
                            "parking_sides": list(program.parking_sides),
                            "bicycle_lane_sides": list(program.bicycle_lane_sides),
                            "amenity_types": list(program.amenity_types),
                        },
                    )
                )
        return views

    def _intersection_views(self, city: City, risks: Sequence[str]) -> list[ViewSpec]:
        incidents: dict[str, list[RoadSegment]] = {
            junction.id: [] for junction in city.road_network.junctions
        }
        for segment in city.road_network.segments:
            incidents.setdefault(segment.start_junction_id, []).append(segment)
            incidents.setdefault(segment.end_junction_id, []).append(segment)
        junctions = {item.id: item for item in city.road_network.junctions}
        views: list[ViewSpec] = []
        for junction_id, roads in sorted(incidents.items()):
            if len(roads) < 3:
                continue
            junction = junctions[junction_id]
            primary = max(roads, key=lambda item: (item.width_m, item.id))
            from cityg.paths import PlanarPath2D
            path = PlanarPath2D(primary.centerline)
            length = path.length
            distance = min(16.0, max(9.0, length * 0.25))
            position = path.point(distance if primary.start_junction_id == junction_id else length - distance)
            risk = 1.0 if junction_id in risks or any(r.id in risks for r in roads) else 0.0
            views.append(
                ViewSpec(
                    view_id=f"{junction_id}_street_intersection",
                    kind="road",
                    purpose="以行人高度检查路口标线、斑马线、视距和街道设施冲突",
                    target_entity_ids=(junction_id, *(road.id for road in roads)),
                    coverage_entity_ids=(junction_id, *(road.id for road in roads)),
                    camera_position=(
                        position.x,
                        position.y,
                        1.72,
                    ),
                    look_at=(junction.position.x, junction.position.y, 1.35),
                    mode="overview",
                    fov_deg=66.0,
                    risk_score=risk + 0.25,
                    novelty_key=f"intersection_degree_{len(roads)}",
                )
            )
        return views

    def _waterfront_views(self, city: City, risks: Sequence[str]) -> list[ViewSpec]:
        from cityg.paths import PlanarPath2D
        views = []
        for river in city.rivers:
            path = PlanarPath2D(river.centerline)
            center = path.point(path.length/2)
            camera = path.point(path.length*.35, river.width_m/2+river.bank_width_m+18)
            views.append(ViewSpec(view_id=f"{river.id}_waterfront", kind="landscape",
                purpose="检查河道连续性、岸坡、滨水步道以及河岸地块退让",
                target_entity_ids=(river.id,), coverage_entity_ids=(river.id,),
                camera_position=(camera.x, camera.y, 28), look_at=(center.x, center.y, -1),
                mode="overview", risk_score=.5 + float(river.id in risks), novelty_key="waterfront"))
        roads = {r.id: r for r in city.road_network.segments}
        for bridge in city.bridges:
            path = PlanarPath2D(roads[bridge.road_id].centerline)
            mid = (bridge.start_m+bridge.end_m)/2
            target, camera = path.point(mid), path.point(mid, roads[bridge.road_id].width_m+18)
            views.append(ViewSpec(view_id=f"{bridge.id}_side", kind="road",
                purpose="检查桥面与道路衔接、跨河覆盖、护栏和桥下净空",
                target_entity_ids=(bridge.id,bridge.road_id,bridge.river_id),
                coverage_entity_ids=(bridge.id,bridge.road_id,bridge.river_id),
                camera_position=(camera.x,camera.y,7), look_at=(target.x,target.y,-.5),
                mode="overview", risk_score=.65 + float(bridge.id in risks), novelty_key=f"bridge_{bridge.id}"))
        return views

    def _landscape_views(self, city: City, risks: Sequence[str]) -> list[ViewSpec]:
        views: list[ViewSpec] = []
        for index, site in enumerate(city.metadata.get("landscape_sites", [])):
            raw = site.get("bounds", {}) if isinstance(site, dict) else {}
            try:
                min_x, min_y = float(raw["min_x"]), float(raw["min_y"])
                max_x, max_y = float(raw["max_x"]), float(raw["max_y"])
            except (KeyError, TypeError, ValueError):
                continue
            site_id = str(site.get("id", f"landscape_{index:03d}"))
            style = str(site.get("style", "park"))
            cx, cy = (min_x + max_x) / 2, (min_y + max_y) / 2
            extent = max(max_x - min_x, max_y - min_y)
            views.append(
                ViewSpec(
                    view_id=f"{site_id}_landscape_00",
                    kind="landscape",
                    purpose="检查公共空间路径、植被层次、设施密度和空间空旷感",
                    target_entity_ids=(site_id, city.id),
                    coverage_entity_ids=(site_id,),
                    # Inspect public-space composition from outside its planting
                    # edge, not from a fixed eye point that may be inside a tree.
                    camera_position=(cx - extent * 0.65, cy - extent * 0.60, max(12.0,extent * .65)),
                    look_at=(cx, cy, 1.0),
                    mode="overview",
                    fov_deg=58.0,
                    risk_score=1.0 if site_id in risks else 0.0,
                    novelty_key=f"landscape_{style}",
                )
            )
        return views

    def _building_views(self, city: City, risks: Sequence[str]) -> list[ViewSpec]:
        buildings = list(city.iter_buildings())
        views: list[ViewSpec] = []
        for building in buildings:
            center = building.footprint.center
            width = max(building.footprint.width, building.footprint.depth, 4.0)
            height = max(
                (floor.elevation_m + floor.height_m for floor in building.floors),
                default=6.0,
            )
            orientation = float(
                building.metadata.get("orientation_contract", {}).get(
                    "orientation_deg", building.metadata.get("orientation_deg", 0.0)
                )
            )
            landmark = bool(building.metadata.get("height_contract", {}).get("landmark"))
            risk = 1.0 if building.id in risks else 0.0
            # Prefer the authored entrance face, not always the local east wall.
            # A mild oblique angle reveals both articulation and facade depth.
            primary_angle = {"east": 0, "north": 90, "west": 180, "south": 270}.get(
                building.metadata.get("entrance_side", "west"), 180)
            facade_azimuth = orientation + primary_angle + 25.0
            angles = [facade_azimuth]
            if risk or landmark or height >= 30.0:
                angles.append(facade_azimuth + 90.0)
            for index, azimuth in enumerate(angles):
                angle = math.radians(azimuth)
                distance = max(width * 1.8, 18.0)
                views.append(
                    ViewSpec(
                        view_id=f"{building.id}_exterior_{index:02d}",
                        kind="building_exterior",
                        semantic_context={"building_id": building.id,
                                          "building_function": building.function,
                                          "appearance_plan": building.metadata.get("appearance_plan", {})},
                        purpose="检查建筑形体、立面连续性和与街道的关系",
                        target_entity_ids=(building.id,),
                        camera_position=(
                            center.x + math.cos(angle) * distance,
                            center.y + math.sin(angle) * distance,
                            max(8.0, height * .70, width * .30),
                        ),
                        look_at=(center.x, center.y, height * 0.45),
                        # Exterior inspection must never request the viewer's
                        # unfiltered ``full`` mode.  On a normal city this
                        # would also load every wall and furniture instance in
                        # every building, even though none can contribute to
                        # the facade image.  ``overview`` retains roads,
                        # streetscape and every building shell; the target ID
                        # still lets the Review LOD preserve extra detail for
                        # the inspected building.
                        mode="overview",
                        risk_score=risk + (0.35 if landmark else 0.0),
                        novelty_key=f"building_{building.function}_{index}",
                    )
                )
        return views

    def _room_views(
        self,
        city: City,
        risks: Sequence[str],
        realized_rooms: _RealizedRoomIndex | None = None,
    ) -> list[ViewSpec]:
        views: list[ViewSpec] = []
        seen_archetypes: set[str] = set()
        for building in city.iter_buildings():
            from cityg.planning.interior_scope import floor_enabled
            floors = sorted((f for f in building.floors if floor_enabled(city,building,f)), key=lambda floor: floor.level)
            selected_floors = floors[:1] + (floors[len(floors) // 2 : len(floors) // 2 + 1] if len(floors) > 2 else [])
            if len(floors) > 1:
                selected_floors += floors[-1:]
            selected_floors += [f for f in floors if f not in selected_floors and any(
                r.metadata.get("detail_tier") == "hero" or r.id in risks for r in f.rooms)]
            for floor in selected_floors:
                for room in floor.rooms:
                    if room.function == "corridor":
                        continue
                    frame = (
                        realized_rooms.frame(building, floor, room)
                        if realized_rooms is not None
                        else _canonical_room_frame(floor, room)
                    )
                    # A compiled manifest is authoritative. Rooms clipped to a
                    # thin wall fragment or lacking one of their enclosed
                    # boundaries must not consume a VLM observation slot.
                    if frame is None:
                        continue
                    is_hero = room.metadata.get("detail_tier") == "hero"
                    archetype = (
                        f"{building.function}:{room.function}:"
                        f"{round(frame.width)}x{round(frame.depth)}"
                    )
                    # Hero rooms are the deliberate visual feedback targets.
                    # Keep each of them as an independent candidate even when
                    # several rooms share a deterministic archetype; ordinary
                    # rooms remain deduplicated to keep observation bounded.
                    if not is_hero and archetype in seen_archetypes:
                        continue
                    if not is_hero:
                        seen_archetypes.add(archetype)
                    risk = 1.0 if room.id in risks or building.id in risks else 0.0
                    if is_hero:
                        risk += 1.5
                    geometry_context = {
                        "room_geometry_source": (
                            "compiled_manifest"
                            if realized_rooms is not None
                            else "canonical_fallback"
                        ),
                        "realized_wall_count": frame.wall_count,
                        "realized_furniture_primitive_count": frame.furniture_count,
                        "realized_room_width_m": round(frame.width, 4),
                        "realized_room_depth_m": round(frame.depth, 4),
                        **room_visual_contract(building,floor,room),
                        "realized_surface_items": realized_rooms.surface_reports.get(room.id)
                            if realized_rooms is not None else None,
                        "furnishing_sufficiency": realized_rooms.sufficiency_reports.get(room.id)
                            if realized_rooms is not None else None,
                        "compiled_object_ids": realized_rooms.compiled_object_ids(room.id)
                            if realized_rooms is not None else None,
                        "furniture_groups": [
                            {"object_id": obj.id, "category": obj.category,
                             "group_id": obj.metadata.get("group_id"),
                             "local_group_key": obj.metadata.get("group_key"),
                             "anchor_id": obj.metadata.get("group_anchor_id"),
                             "wall_binding":obj.metadata.get("wall_binding"),
                             "circulation":obj.metadata.get("room_circulation"),
                             "zone_id": obj.metadata.get("zone_id")}
                            for obj in floor.objects if obj.room_id == room.id
                        ][:32],
                    }
                    # A furnished room is best audited from above: this avoids
                    # a valid wall hiding every object while still exposing
                    # containment, circulation and orientation.  The height is
                    # derived from the realized room extent so large rooms fit
                    # without a hard-coded camera distance.
                    if frame.furniture_count:
                        audit = frame.local_audit_bounds
                        audit_center_local = audit.center
                        audit_center = frame.local_to_world(*audit_center_local)
                        extent = max(
                            audit.max_x - audit.min_x,
                            audit.max_y - audit.min_y,
                            2.0,
                        )
                        top_height = max(7.0, extent * 1.38)
                        corners = [frame.local_to_world(x,y) for x in (audit.min_x,audit.max_x)
                                   for y in (audit.min_y,audit.max_y)]
                        audit_world = [min(p[0] for p in corners),min(p[1] for p in corners),frame.elevation,
                                       max(p[0] for p in corners),max(p[1] for p in corners),
                                       frame.elevation+max(room.height_m,floor.height_m)]
                        views.append(
                            ViewSpec(
                                view_id=f"{room.id}_top_00",
                                kind="room_interior",
                                purpose="俯视检查房间家具覆盖、边界内放置、朝向和通行空间",
                                target_entity_ids=(room.id, floor.id, building.id),
                                camera_position=(
                                    audit_center[0],
                                    audit_center[1],
                                    frame.elevation + top_height,
                                ),
                                look_at=(
                                    audit_center[0],
                                    audit_center[1],
                                    frame.elevation + 0.05,
                                ),
                                up=(0.0, 1.0, 0.0),
                                fov_deg=50.0,
                                mode="room",
                                auto_cutaway=False,
                                risk_score=risk + 0.72,
                                novelty_key=f"room_top_{room.function}",
                                semantic_context={**geometry_context,'top_down_audit_bounds_world':audit_world},
                            )
                        )

                    # The perspective camera is selected from four inset room
                    # corners. Prefer a corner away from furniture and doors,
                    # then aim at the furnishing centroid. This keeps the
                    # camera inside the room and avoids starting in a wall,
                    # doorway, or occupied footprint.
                    inset = max(
                        0.55,
                        min(1.35, min(frame.width, frame.depth) * 0.14),
                    )
                    inset = min(inset, frame.width * 0.35, frame.depth * 0.35)
                    wall_bounds = frame.local_wall_bounds
                    corners = (
                        (wall_bounds.min_x + inset, wall_bounds.min_y + inset),
                        (wall_bounds.max_x - inset, wall_bounds.min_y + inset),
                        (wall_bounds.max_x - inset, wall_bounds.max_y - inset),
                        (wall_bounds.min_x + inset, wall_bounds.max_y - inset),
                    )
                    def clearance(point: tuple[float, float]) -> tuple[float, float, float]:
                        object_clearance = min(
                            (
                                _distance_to_footprint(point, item)
                                for item in frame.furniture_footprints
                            ),
                            default=max(frame.width, frame.depth),
                        )
                        door_clearance = min(
                            (
                                math.hypot(point[0] - item[0], point[1] - item[1])
                                for item in frame.door_points
                            ),
                            default=max(frame.width, frame.depth),
                        )
                        # Stable final components make symmetric rooms replay
                        # identically across processes and machines.
                        return object_clearance, door_clearance, -point[0] - point[1]

                    camera_local = max(corners, key=clearance)
                    camera_x, camera_y = frame.local_to_world(*camera_local)
                    if frame.furniture_footprints:
                        furniture_union = _union_bounds(frame.furniture_footprints)
                        assert furniture_union is not None
                        target_local_x, target_local_y = furniture_union.center
                        target_local_x = min(
                            max(target_local_x, wall_bounds.min_x + 0.1),
                            wall_bounds.max_x - 0.1,
                        )
                        target_local_y = min(
                            max(target_local_y, wall_bounds.min_y + 0.1),
                            wall_bounds.max_y - 0.1,
                        )
                    else:
                        target_local_x = target_local_y = 0.0
                    target_x, target_y = frame.local_to_world(
                        target_local_x, target_local_y
                    )
                    views.append(
                        ViewSpec(
                            view_id=f"{room.id}_perspective_00",
                            kind="room_interior",
                            purpose="从空闲角落检查房间尺度、家具立面、门和通行空间",
                            target_entity_ids=(room.id, floor.id, building.id),
                            camera_position=(
                                camera_x,
                                camera_y,
                                frame.elevation + max(1.65, room.height_m * 0.76),
                            ),
                            look_at=(
                                target_x,
                                target_y,
                                frame.elevation + min(1.15, room.height_m * 0.38),
                            ),
                            fov_deg=64.0,
                            mode="room",
                            auto_cutaway=False,
                            risk_score=risk + (
                                0.42 if frame.furniture_count else 0.68
                            ),
                            novelty_key=(
                                f"hero_room_perspective_{room.id}"
                                if is_hero
                                else f"room_perspective_{room.function}"
                            ),
                            semantic_context=geometry_context,
                        )
                    )
        return views

    @staticmethod
    def _deduplicate(views: Sequence[ViewSpec]) -> list[ViewSpec]:
        unique: dict[str, ViewSpec] = {}
        for view in views:
            unique.setdefault(view.view_id, view)
        return [unique[key] for key in sorted(unique)]

    def _select(
        self, candidates: Sequence[ViewSpec], budget: int, risks: Sequence[str]
    ) -> list[ViewSpec]:
        if not candidates:
            return []
        selected: list[ViewSpec] = []
        remaining = list(candidates)
        covered: set[str] = set()
        novelty: set[str] = set()

        # Reserve at least two global perspectives whenever the budget allows.
        globals_ = [view for view in remaining if view.kind == "global"]
        reserve = min(self.min_global_views, budget, len(globals_))
        for view in sorted(globals_, key=lambda item: item.view_id)[:reserve]:
            selected.append(view)
            covered.update(view.covered_entities)
            novelty.add(view.novelty_key)
            remaining.remove(view)

        # Keep the observation budget semantically diverse.  Without this
        # reservation, room views can dominate because each one introduces a
        # previously uncovered floor/room ID, starving exterior inspection.
        for kind, requested in self.minimum_diversity_views.items():
            slots = budget - len(selected)
            if slots <= 0:
                break
            pool = [view for view in remaining if view.kind == kind]
            reserve_kind = min(requested, slots, len(pool))
            ordered_pool = sorted(pool, key=lambda item: (-item.risk_score, item.view_id))
            if kind == "road":
                # Reserve representative street archetypes before spending a
                # second view on a visually equivalent cross-section.
                distinct: list[ViewSpec] = []
                seen_novelty: set[str] = set()
                for view in ordered_pool:
                    if view.novelty_key in seen_novelty:
                        continue
                    distinct.append(view)
                    seen_novelty.add(view.novelty_key)
                ordered_pool = distinct + [
                    view for view in ordered_pool if view not in distinct
                ]
            if kind in {"building_exterior", "room_interior"}:
                # Prefer different buildings before taking a second facade
                # angle of the same building.  High-rise corner views remain
                # available to the greedy phase if budget permits.
                distinct: list[ViewSpec] = []
                seen_targets: set[str] = set()
                for view in ordered_pool:
                    target = view.target_entity_ids[0]
                    if target in seen_targets:
                        continue
                    distinct.append(view)
                    seen_targets.add(target)
                ordered_pool = distinct + [
                    view for view in ordered_pool if view not in distinct
                ]
            for view in ordered_pool[:reserve_kind]:
                selected.append(view)
                covered.update(view.covered_entities)
                novelty.add(view.novelty_key)
                remaining.remove(view)

        while remaining and len(selected) < budget:
            def score(view: ViewSpec) -> tuple[bool, float, str]:
                gain = len(set(view.covered_entities) - covered)
                risk_gain = sum(1.0 for entity in view.covered_entities if entity in risks and entity not in covered)
                new_type = 1.0 if view.novelty_key not in novelty else 0.0
                kind_bonus = {"road": 0.48, "landscape": 0.40, "building_exterior": 0.35, "room_interior": 0.25, "global": 0.1}[view.kind]
                value = 2.0 * gain + 4.0 * risk_gain + 0.9 * new_type + kind_bonus + view.risk_score
                return risk_gain > 0, value, view.view_id

            best = max(remaining, key=score)
            selected.append(best)
            covered.update(best.covered_entities)
            novelty.add(best.novelty_key)
            remaining.remove(best)
        return selected


__all__ = ["AdaptiveObservationPlanner", "ObservationPlan", "ViewSpec", "VIEW_KINDS"]
