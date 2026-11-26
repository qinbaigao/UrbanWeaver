"""Deterministic, topology-aware streetscape compilation.

The streetscape layer is visual-first but placement-constrained.  Vehicles are
bound to lane offsets, pedestrians to sidewalk offsets, and street trees/lights
to the sidewalk furniture strip.  Every generated item keeps its road owner so
that a later traffic or VLM repair agent can address an exact segment.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Any

from cityg.assets import AssetRegistry, choose_asset_variant
from cityg.geometry.vegetation_clearance import PEDESTRIAN_RADIUS, tree_placement_radius
from cityg.geometry.asset_fitting import fit_outdoor_asset, outdoor_asset_yaw_offset, outdoor_asset_ground_offset
from cityg.geometry.model import GeometryPrimitive, Vec3
from cityg.planning.appearance import UrbanAppearanceProgram
from cityg.planning.streetscape import (
    StreetProgramPlanner,
    StreetSegmentProgram,
)
from cityg.schemas import City, Point2D, RoadSegment
from cityg.paths import PlanarPath2D
from cityg.ccwp import point_segment_distance
from cityg.geometry.path_mesh import path_slab
from cityg.geometry.parking_markings import outline_mesh
from cityg.geometry.crossings import connect_crossings


@dataclass(frozen=True)
class _Frame:
    start: Point2D
    length: float
    ux: float
    uy: float
    nx: float
    ny: float
    path: PlanarPath2D | None = None

    def point(self, distance: float, offset: float = 0.0) -> Point2D:
        if self.path is not None:
            return self.path.point(distance, offset)
        return Point2D(
            self.start.x + self.ux * distance + self.nx * offset,
            self.start.y + self.uy * distance + self.ny * offset,
        )

    def project(self, point: Point2D):
        path = self.path or PlanarPath2D((self.start, self.point(self.length)))
        return path.project(point)

    def at_point(self, point: Point2D) -> _Frame:
        if self.path is None:
            return self
        tangent = self.path.tangent(self.path.project(point).distance)
        return _Frame(self.start, self.length, tangent.x, tangent.y,
                      -tangent.y, tangent.x, self.path)


class StreetscapeCompiler:
    """Compile road details without changing the canonical road graph."""

    def __init__(self, asset_registry: AssetRegistry | None = None) -> None:
        self.asset_registry = asset_registry
        self._junction_clearance: dict[str, float] = {}
        self._junction_degree: dict[str, int] = {}
        self._road_bounds = {}
        self.program_planner = StreetProgramPlanner()

    def compile(
        self,
        city: City,
        scene: Any,
        appearance: UrbanAppearanceProgram,
    ) -> dict[str, int | str]:
        self._road_bounds = {}
        connected: dict[str, list[RoadSegment]] = {}
        for item in city.road_network.segments:
            connected.setdefault(item.start_junction_id, []).append(item)
            connected.setdefault(item.end_junction_id, []).append(item)
        self._junction_degree = {key: len(value) for key, value in connected.items()}
        self._junction_clearance = {
            key: (
                max(road.width_m / 2 + road.sidewalk_width_m for road in roads)
                if len(roads) >= 2 else 0.0
            )
            for key, roads in connected.items()
        }
        street_program = self.program_planner.plan(city, appearance)
        programs = {item.road_id: item for item in street_program.segments}
        scene.metadata["street_network_program"] = street_program.to_dict()
        stats = {
            "curb_count": 0,
            "lane_marking_count": 0,
            "crosswalk_count": 0,
            "street_tree_count": 0,
            "street_light_count": 0,
            "sidewalk_assets_relocated": 0,
            "sidewalk_placements_omitted": 0,
            "vehicle_count": 0,
            "pedestrian_count": 0,
            "activity_cluster_count": 0,
            "activity_person_count": 0,
            "transit_waiting_person_count": 0,
            "intersection_waiting_person_count": 0,
            "retail_activity_person_count": 0,
            "cyclist_count": 0,
            "service_activity_count": 0,
            "street_furniture_count": 0,
            "street_program_count": len(street_program.segments),
            "bicycle_lane_segment_count": 0,
            "parking_bay_count": 0,
            "parked_vehicle_count": 0,
            "sidewalk_zone_count": 0,
            "frontage_connector_count": 0,
            "frontage_detail_count": 0,
            "programmed_amenity_count": 0,
            "arterial_median_greenery_count": 0,
            "arterial_signal_count": 0,
            "arterial_stop_line_count": 0,
            "resolved_outdoor_asset_count": 0,
            "procedural_outdoor_fallback_count": 0,
        }
        for road in city.road_network.segments:
            frame = self._frame(road)
            if frame is None:
                continue
            primitive_start = len(scene.primitives)
            profile = appearance.profile_for_road(road.road_class)
            segment_program = programs[road.id]
            if profile.curbs:
                self._compile_curbs(road, frame, scene, stats)
            if profile.lane_markings:
                self._compile_lane_markings(road, frame, scene, stats)
            if profile.crosswalks:
                self._compile_crosswalks(road, frame, scene, stats)
            self._compile_cross_section(
                city, road, frame, segment_program, scene, appearance, stats
            )
            if road.road_class == "arterial":
                self._compile_arterial_details(city, road, frame, scene, stats)
            self._compile_sidewalk_assets(
                city,
                road,
                frame,
                scene,
                profile,
                appearance,
                segment_program,
                stats,
            )
            if frame.path is not None:
                for index in range(primitive_start, len(scene.primitives)):
                    primitive = scene.primitives[index]
                    if not primitive.metadata.get("path_strip"):
                        continue
                    projection = frame.project(primitive.center)
                    start = max(0.0, projection.distance - primitive.size.x / 2)
                    end = min(frame.length, projection.distance + primitive.size.x / 2)
                    if end - start <= 1e-6:
                        continue
                    scene.primitives[index] = path_slab(
                        primitive.id, road.id, frame.path.slice(start, end), primitive.size.y,
                        primitive.center.z, primitive.size.z, primitive.semantic_class,
                        primitive.material_id, offset=projection.lateral,
                        collision=primitive.collision_enabled, metadata=primitive.metadata,
                    )
        stats.update(connect_crossings(scene.primitives))
        stats["crosswalk_count"] = sum(p.semantic_class == "crosswalk" for p in scene.primitives)
        return stats

    def _compile_arterial_details(
        self, city: City, road: RoadSegment, frame: _Frame, scene: Any, stats: dict[str, int]
    ) -> None:
        """Add boulevard-specific visual cues on top of the generic street kit."""

        median = max(0.0, float(road.median_width_m))
        if median <= 0.0:
            return
        start_clear = self._junction_clearance.get(road.start_junction_id, 0.0)
        end_clear = self._junction_clearance.get(road.end_junction_id, 0.0)
        start = max(start_clear + 7.0, 8.0)
        end = min(frame.length - end_clear - 7.0, frame.length - 8.0)
        if end <= start:
            return

        # Low planting islands break up a long concrete reservation without
        # introducing tall objects that would obstruct intersection sightlines.
        spacing = 30.0
        cursor = start + spacing * 0.35
        index = 0
        while cursor < end:
            point = frame.point(cursor, 0.0)
            planter_length = min(3.2, max(1.4, spacing * 0.72))
            planter_width = max(0.55, median * 0.76)
            base = f"{road.id}_median_landscape_{index:02d}"
            scene.primitives.extend(
                [
                    self._box(
                        f"{base}_bed", road.id,
                        Vec3(point.x, point.y, 0.12),
                        Vec3(planter_length, planter_width, 0.18),
                        self._rotation(frame, point), "median_planter", "planting_soil", "roads",
                        collision_enabled=False,
                        metadata={"road_id": road.id, "road_detail": "median_greenery", "index": index},
                    ),
                    self._sphere(
                        f"{base}_shrub", road.id,
                        Vec3(point.x, point.y, 0.42),
                        Vec3(planter_length * 0.34, planter_width * 0.40, 0.48),
                        self._rotation(frame, point), "median_shrub", "landscape_shrub", "roads",
                        collision_enabled=False,
                        metadata={"road_id": road.id, "road_detail": "median_greenery", "index": index},
                    ),
                ]
            )
            stats["arterial_median_greenery_count"] += 1
            cursor += spacing
            index += 1

        # Stop bars sit immediately before the intersection crossing.  They
        # are perpendicular to the road and are split around the median.
        carriageway = max(1.0, road.width_m - median)
        for endpoint, distance in (
            ("start", max(start_clear + 1.8, 3.0)),
            ("end", min(frame.length - end_clear - 1.8, frame.length - 3.0)),
        ):
            if distance <= 1.0 or distance >= frame.length - 1.0:
                continue
            for side_index, lateral in enumerate((-(median / 2 + carriageway / 4), median / 2 + carriageway / 4)):
                point = frame.point(distance, lateral)
                scene.primitives.append(
                    self._box(
                        f"{road.id}_stop_line_{endpoint}_{side_index}", road.id, point,
                        Vec3(0.32, carriageway / 2, 0.035), self._rotation(frame, point),
                        "stop_line", "road_marking", "roads", collision_enabled=False,
                        metadata={"road_id": road.id, "road_detail": "stop_bar", "junction_side": endpoint},
                    )
                )
                stats["arterial_stop_line_count"] += 1

        # One signal pole per controlled end, placed in the furnishing strip.
        for endpoint, distance in (
            ("start", max(start_clear + 2.8, 4.5)),
            ("end", min(frame.length - end_clear - 2.8, frame.length - 4.5)),
        ):
            if distance <= 2.0 or distance >= frame.length - 2.0:
                continue
            side = 1.0 if self._seed(road.id, endpoint, "signal_side") % 2 == 0 else -1.0
            lateral = side * (road.width_m / 2 + road.sidewalk_width_m * 0.62)
            point = frame.point(distance, lateral)
            base = f"{road.id}_signal_{endpoint}"
            scene.primitives.extend(
                [
                    self._cylinder(
                        f"{base}_pole", road.id, Vec3(point.x, point.y, 2.1),
                        Vec3(0.10, 0.10, 4.2), self._rotation(frame, point), "traffic_signal",
                        "street_furniture", "roads", collision_enabled=False,
                        instance_key="traffic_signal_pole",
                        metadata={"road_id": road.id, "road_detail": "traffic_signal", "junction_side": endpoint},
                    ),
                    self._box(
                        f"{base}_head", road.id, Vec3(point.x, point.y, 3.65),
                        Vec3(0.28, 0.24, 0.92), self._rotation(frame, point), "traffic_signal",
                        "street_furniture", "roads", collision_enabled=False,
                        instance_key="traffic_signal_head",
                        metadata={"road_id": road.id, "road_detail": "traffic_signal", "junction_side": endpoint},
                    ),
                    self._sphere(
                        f"{base}_red", road.id, Vec3(point.x, point.y - 0.13, 3.92),
                        Vec3(0.14, 0.14, 0.14), self._rotation(frame, point),
                        "traffic_signal_red", "facade_accent_warm", "roads",
                        collision_enabled=False, instance_key="traffic_signal_light",
                        metadata={"road_id": road.id, "road_detail": "traffic_signal", "state": "red"},
                    ),
                    self._sphere(
                        f"{base}_green", road.id, Vec3(point.x, point.y - 0.13, 3.38),
                        Vec3(0.14, 0.14, 0.14), self._rotation(frame, point),
                        "traffic_signal_green", "tree_canopy", "roads",
                        collision_enabled=False, instance_key="traffic_signal_light",
                        metadata={"road_id": road.id, "road_detail": "traffic_signal", "state": "green"},
                    ),
                ]
            )
            stats["arterial_signal_count"] += 1

    @staticmethod
    def _frame(road: RoadSegment) -> _Frame | None:
        try:
            path = PlanarPath2D(road.centerline)
        except ValueError:
            return None
        t = path.tangent(0)
        return _Frame(path.points[0], path.length, t.x, t.y, -t.y, t.x,
                      path if len(road.centerline) > 2 else None)

    @staticmethod
    def _seed(*values: str) -> int:
        digest = hashlib.sha256("|".join(values).encode("utf-8")).digest()
        return int.from_bytes(digest[:4], "big")

    def _unit_noise(self, *values: str) -> float:
        """Return stable noise in [0, 1] without global RNG state."""

        return (self._seed(*values) % 10001) / 10000.0

    def _rhythm_distances(
        self,
        road_id: str,
        side: str,
        start: float,
        end: float,
        spacing: float,
        pattern: str,
        kind: str,
    ):
        """Yield safe, deterministic positions with correlated street rhythm.

        The result deliberately avoids independent white-noise placement: a
        street should read as designed, but not as a perfectly repeated array.
        Lights remain more regular than vegetation and population, while the
        two sidewalk sides receive different phases to avoid mirror symmetry.
        """

        if end <= start or spacing <= 0:
            return
        initial = spacing * (
            0.18
            + 0.36 * self._unit_noise(road_id, side, kind, "initial_phase")
        )
        if side == "right":
            initial += spacing * (0.48 if pattern in {"formal", "staggered"} else 0.23)
        cursor = start + initial
        index = 0
        clustered = (0.58, 0.72, 1.58, 0.66, 1.46)
        while cursor < end:
            yield index, cursor
            noise = self._unit_noise(road_id, side, kind, str(index), "step")
            if kind == "light":
                ranges = {
                    "formal": (0.97, 1.03),
                    "staggered": (0.91, 1.09),
                    "clustered": (0.88, 1.14),
                    "organic": (0.88, 1.16),
                    "sparse": (0.96, 1.28),
                }
                low, high = ranges.get(pattern, ranges["organic"])
                factor = low + (high - low) * noise
            elif pattern == "formal":
                factor = 0.90 + 0.20 * noise
            elif pattern == "staggered":
                factor = 0.76 + 0.48 * noise
            elif pattern == "clustered":
                factor = clustered[index % len(clustered)] * (0.94 + 0.12 * noise)
            elif pattern == "sparse":
                factor = 0.88 + 0.82 * noise
            else:
                factor = 0.66 + 0.72 * noise
            cursor += spacing * factor
            index += 1

    def _rhythm_keeps(
        self,
        road_id: str,
        side: str,
        index: int,
        pattern: str,
        kind: str,
    ) -> bool:
        """Create bounded intentional gaps without compromising regular lights."""

        if kind == "light":
            threshold = 90 if pattern == "sparse" else 100
        else:
            threshold = {
                "formal": 100,
                "staggered": 91,
                "clustered": 96,
                "organic": 84,
                "sparse": 70,
            }.get(pattern, 84)
        # Correlate neighboring candidates so omissions read as a deliberate
        # frontage/utility gap rather than salt-and-pepper random deletion.
        block = index // 2 if pattern in {"organic", "sparse"} else index
        return self._seed(road_id, side, kind, str(block), "keep") % 100 < threshold

    def _compile_curbs(self, road, frame: _Frame, scene, stats: dict[str, int]) -> None:
        start_distance, end_distance = self._usable_limits(
            road, frame, extra=road.sidewalk_width_m * 0.45
        )
        usable_length = end_distance - start_distance
        if usable_length <= 0.2:
            return
        for side, sign in (("left", 1.0), ("right", -1.0)):
            point = frame.point((start_distance + end_distance) / 2, sign * (road.width_m / 2 + 0.10))
            scene.primitives.append(
                self._box(
                    f"{road.id}_curb_{side}", road.id, point,
                    Vec3(usable_length, 0.20, 0.18),
                    self._rotation(frame, point), "curb", "concrete", "roads",
                    collision_enabled=False,
                    metadata={"road_id": road.id, "road_detail": "curb", "path_strip": True},
                )
            )
            stats["curb_count"] += 1

    def _compile_lane_markings(self, road, frame: _Frame, scene, stats: dict[str, int]) -> None:
        start_distance, end_distance = self._usable_limits(road, frame, extra=0.8)
        if road.lane_count >= 2:
            dash = 4.5
            gap = 3.2
            cursor = max(4.0, start_distance)
            index = 0
            while cursor + dash < min(frame.length - 3.0, end_distance):
                offsets = (0.0,)
                if road.median_width_m > 0.0:
                    offsets = (-(road.median_width_m / 2.0 + 0.10), road.median_width_m / 2.0 + 0.10)
                for side_index, lateral in enumerate(offsets):
                    point = frame.point(cursor + dash / 2, lateral)
                    scene.primitives.append(
                        self._box(
                            f"{road.id}_centerline_{index:03d}_{side_index}", road.id, point,
                            Vec3(dash, 0.12, 0.025), self._rotation(frame, point),
                            "lane_marking", "road_marking", "roads",
                            collision_enabled=False,
                            metadata={"road_id": road.id, "marking": "center_dashed", "median_adjacent": road.median_width_m > 0.0, "path_strip": True},
                        )
                    )
                    stats["lane_marking_count"] += 1
                cursor += dash + gap
                index += 1
        if road.road_class in {"collector", "local"}:
            for side, sign in (("left", 1.0), ("right", -1.0)):
                point = frame.point((start_distance + end_distance) / 2, sign * (road.width_m / 2 - 0.22))
                scene.primitives.append(
                    self._box(
                        f"{road.id}_edge_{side}", road.id, point,
                        Vec3(end_distance - start_distance, 0.08, 0.022), self._rotation(frame, point),
                        "lane_marking", "road_marking", "roads",
                        collision_enabled=False,
                        metadata={"road_id": road.id, "marking": "edge", "path_strip": True},
                    )
                )
                stats["lane_marking_count"] += 1

    def _compile_crosswalks(self, road, frame: _Frame, scene, stats: dict[str, int]) -> None:
        # A short, explicit crossing near each endpoint gives the road network a
        # legible pedestrian rhythm without attempting to solve traffic signals.
        # Shared-space and service lanes already operate as pedestrian-priority
        # or access roads; drawing a full zebra crossing on them creates the
        # duplicated stripes seen at diagonal/branch junctions.
        if road.road_class not in {"arterial", "collector", "local"}:
            return
        start_clearance = self._junction_clearance.get(road.start_junction_id, 0.0)
        end_clearance = self._junction_clearance.get(road.end_junction_id, 0.0)
        endpoints = []
        if self._junction_degree.get(road.start_junction_id, 0) >= 2:
            endpoints.append(("start", max(start_clearance + 1.2, 3.0)))
        if self._junction_degree.get(road.end_junction_id, 0) >= 2:
            endpoints.append(("end", frame.length - max(end_clearance + 1.2, 3.0)))
        for endpoint, distance in endpoints:
            if distance <= 2.0 or distance >= frame.length - 1.0:
                continue
            center = frame.point(distance)
            for stripe in range(6):
                offset = (stripe - 2.5) * 0.72
                point = frame.point(distance + offset)
                scene.primitives.append(
                    self._box(
                        f"{road.id}_crosswalk_{endpoint}_{stripe:02d}", road.id, point,
                        Vec3(0.48, road.width_m - 0.9, 0.025), self._rotation(frame, point),
                        "crosswalk", "road_marking", "roads",
                        collision_enabled=False,
                        metadata={"road_id": road.id, "junction_side": endpoint},
                    )
                )
                stats["crosswalk_count"] += 1

    @staticmethod
    def _program_metadata(program: StreetSegmentProgram) -> dict[str, Any]:
        return {
            "street_program_archetype": program.archetype,
            "street_program_function": program.dominant_function,
            "street_activity_level": program.activity_level,
            "street_activity_modes": list(program.activity_modes),
            "street_activity_cluster_count": program.activity_cluster_count,
            "street_program_source": program.source,
        }

    def _compile_cross_section(
        self,
        city: City,
        road: RoadSegment,
        frame: _Frame,
        program: StreetSegmentProgram,
        scene: Any,
        appearance: UrbanAppearanceProgram,
        stats: dict[str, int],
    ) -> None:
        """Render semantic road and sidewalk bands from one segment program."""

        del appearance  # Reserved for future weather/time-dependent materials.
        metadata = self._program_metadata(program)
        bicycle_sides = program.bicycle_lane_sides or (("left", "right") if road.bike_lane else ())
        parking_sides = program.parking_sides if road.parking_allowed else ()
        for side in bicycle_sides:
            sign = 1.0 if side == "left" else -1.0
            count = self._compile_linear_strip(
                city,
                road,
                frame,
                scene,
                lateral_offset=sign * (road.width_m / 2 - 0.82),
                strip_width=1.36,
                semantic="bicycle_lane_surface",
                material="bike_lane",
                z=0.018,
                id_token=f"bike_{side}",
                metadata={**metadata, "cross_section_zone": "bicycle_lane", "side": side},
                extra_clearance=1.4,
            )
            stats["bicycle_lane_segment_count"] += count

        for side in parking_sides:
            sign = 1.0 if side == "left" else -1.0
            start_limit, end_limit = self._usable_limits(road, frame, extra=2.2)
            cursor = max(start_limit, 7.0)
            bay_index = 0
            while cursor + 5.7 < end_limit:
                center = frame.point(cursor + 2.85, sign * (road.width_m / 2 - 1.05))
                bay_start = frame.point(
                    cursor, sign * (road.width_m / 2 - 1.05)
                )
                bay_end = frame.point(
                    cursor + 5.7, sign * (road.width_m / 2 - 1.05)
                )
                if not self._path_intrudes_other_road(
                    city, road.id, bay_start, bay_end, 1.0
                ):
                    length, width = 5.45, 1.95
                    vertices, triangles = outline_mesh(
                        [(-length/2, -width/2), (length/2, -width/2),
                         (length/2, width/2), (-length/2, width/2)], z=0.0,
                    )
                    scene.primitives.append(
                        GeometryPrimitive(
                            f"{road.id}_parking_{side}_{bay_index:03d}",
                            road.id,
                            "path_mesh",
                            Vec3(center.x, center.y, 0.002),
                            Vec3(length, width, 1e-6),
                            self._rotation(frame, center),
                            "parking_bay",
                            "road_marking",
                            "roads",
                            collision_enabled=False,
                            instance_key="parking_outline_5_45_1_95_v1",
                            metadata={
                                **metadata,
                                "representation": "painted_outline",
                                "line_width_m": 0.10,
                                "mesh_vertices": [(x/length, y/width, z) for x, y, z in vertices],
                                "mesh_triangles": triangles,
                                "cross_section_zone": "parking",
                                "side": side,
                                "parking_role": (
                                    "loading"
                                    if "loading_bay" in program.amenity_types
                                    else "short_stay"
                                ),
                            },
                        )
                    )
                    stats["parking_bay_count"] += 1
                cursor += 6.2
                bay_index += 1

        sidewalk_width = max(0.0, road.sidewalk_width_m)
        if sidewalk_width <= 0.25:
            return
        furnishing_width = min(
            program.furnishing_strip_width_m, sidewalk_width * 0.42
        )
        frontage_width = min(
            program.frontage_strip_width_m, sidewalk_width * 0.34
        )
        for side, sign in (("left", 1.0), ("right", -1.0)):
            furnishing_offset = sign * (
                road.width_m / 2 + furnishing_width / 2 + 0.08
            )
            count = self._compile_linear_strip(
                city,
                road,
                frame,
                scene,
                lateral_offset=furnishing_offset,
                strip_width=furnishing_width,
                semantic="sidewalk_furnishing_strip",
                material="paving_furnishing",
                z=0.158,
                id_token=f"furnishing_{side}",
                metadata={
                    **metadata,
                    "cross_section_zone": "furnishing",
                    "side": side,
                },
                extra_clearance=road.sidewalk_width_m + 0.5,
            )
            stats["sidewalk_zone_count"] += count
            frontage_offset = sign * (
                road.width_m / 2 + sidewalk_width - frontage_width / 2 - 0.06
            )
            count = self._compile_linear_strip(
                city,
                road,
                frame,
                scene,
                lateral_offset=frontage_offset,
                strip_width=frontage_width,
                semantic="sidewalk_frontage_strip",
                material=f"frontage_{program.frontage_treatment}",
                z=0.160,
                id_token=f"frontage_{side}",
                metadata={
                    **metadata,
                    "cross_section_zone": "frontage",
                    "frontage_treatment": program.frontage_treatment,
                    "side": side,
                },
                extra_clearance=road.sidewalk_width_m + 0.5,
            )
            stats["sidewalk_zone_count"] += count

    def _compile_linear_strip(
        self,
        city: City,
        road: RoadSegment,
        frame: _Frame,
        scene: Any,
        *,
        lateral_offset: float,
        strip_width: float,
        semantic: str,
        material: str,
        z: float,
        id_token: str,
        metadata: dict[str, Any],
        extra_clearance: float,
    ) -> int:
        """Compile short strip tiles so diagonal crossings remain clear."""

        start_limit, end_limit = self._usable_limits(
            road, frame, extra=extra_clearance
        )
        cursor = start_limit
        count = 0
        while cursor < end_limit - 0.4:
            tile_length = min(11.8, end_limit - cursor)
            center = frame.point(cursor + tile_length / 2, lateral_offset)
            strip_start = frame.point(cursor, lateral_offset)
            strip_end = frame.point(cursor + tile_length, lateral_offset)
            if not self._path_intrudes_other_road(
                city,
                road.id,
                strip_start,
                strip_end,
                max(0.12, strip_width * 0.52),
            ):
                scene.primitives.append(
                    self._box(
                        f"{road.id}_{id_token}_{count:03d}",
                        road.id,
                        Vec3(center.x, center.y, z),
                        Vec3(max(0.2, tile_length - 0.12), strip_width, 0.026),
                        self._rotation(frame, center),
                        semantic,
                        material,
                        "roads",
                        collision_enabled=False,
                        metadata={**metadata, "road_id": road.id, "path_strip": True},
                    )
                )
                count += 1
            cursor += tile_length
        return count

    @staticmethod
    def _frontage_width(program):
        return {"retail": 3.0, "civic": 3.4, "industrial": 3.6,
                "residential": 2.1}.get(program.frontage_treatment, 2.4)

    def _entrance_approaches(self, city, road, frame, program):
        """Reserve the sidewalk crossing at the street end of each approach."""
        approaches = {"left": [], "right": []}
        adjacent = set(program.adjacent_building_ids)
        for building in city.iter_buildings():
            access = building.metadata.get("group_access") or {}
            if access.get("road_id", road.id) != road.id or (not access and building.id not in adjacent):
                continue
            point = building.entrance
            width = self._frontage_width(program)
            if access.get("points"):
                point = Point2D(*access["points"][0])
                width = access["width_m"]
            at = frame.project(point)
            curb_offset = road.width_m / 2 + road.sidewalk_width_m
            if abs(abs(at.lateral) - curb_offset) > 24.0:
                continue
            side = "left" if at.lateral >= 0 else "right"
            curb = frame.point(at.distance, math.copysign(road.width_m / 2, at.lateral))
            approaches[side].append(((curb, point), width / 2))
        return approaches

    def _sidewalk_station(self, city, road, frame, distance, offset, limits,
                          protected, occupied, radius, door_gap, stats):
        """Keep the original rhythm, moving a conflicting item along its own strip."""
        for shift in (0., 2.5, -2.5, 5., -5., 7.5, -7.5):
            d = distance + shift
            if not limits[0] <= d <= limits[1]:
                continue
            point = frame.point(d, offset)
            if any(point_segment_distance(point, approach) <= half_width + radius + PEDESTRIAN_RADIUS
                   for approach, half_width in protected):
                continue
            if any(math.hypot(point.x - p.x, point.y - p.y) < radius + r for p, r in occupied):
                continue
            if self._inside_other_road(city, road.id, point, radius) or (
                door_gap and self._near_entrance(city, point, door_gap)
            ):
                continue
            occupied.append((point, radius))
            if shift:
                stats["sidewalk_assets_relocated"] += 1
            return d
        stats["sidewalk_placements_omitted"] += 1
        return None

    def _compile_sidewalk_assets(
        self, city: City, road, frame: _Frame, scene,
        profile, appearance: UrbanAppearanceProgram,
        program: StreetSegmentProgram, stats: dict[str, int],
    ) -> None:
        sidewalk_center = road.width_m / 2 + road.sidewalk_width_m * 0.48
        outer_strip = road.width_m / 2 + road.sidewalk_width_m * 0.78
        start_limit, end_limit = self._usable_limits(road, frame, extra=2.0)
        protected = self._entrance_approaches(city, road, frame, program)
        occupied = {"left": [], "right": []}
        for side, sign in (("left", 1.0), ("right", -1.0)):
            tree_start = max(start_limit, 6.0)
            tree_end = min(frame.length - 6.0, end_limit)
            entrance_gap = 5.4 if program.activity_level == "high" else 4.2
            for tree_index, distance in self._rhythm_distances(
                road.id,
                side,
                tree_start,
                tree_end,
                program.tree_spacing_m,
                program.placement_pattern,
                "tree",
            ):
                if not self._rhythm_keeps(
                    road.id,
                    side,
                    tree_index,
                    program.placement_pattern,
                    "tree",
                ):
                    continue
                point = frame.point(distance, sign * sidewalk_center)
                first = len(scene.primitives)
                resolved = self._tree(city, road, point, side, tree_index, distance, program, scene)
                parts = scene.primitives[first:]
                if not parts:
                    continue
                station = self._sidewalk_station(
                    city, road, frame, distance, sign * sidewalk_center, (tree_start, tree_end),
                    protected[side], occupied[side], tree_placement_radius(parts, point), entrance_gap, stats,
                )
                if station is None:
                    del scene.primitives[first:]
                    continue
                if station != distance:
                    moved = frame.point(station, sign * sidewalk_center)
                    for p in parts:
                        p.center = Vec3(p.center.x + moved.x - point.x, p.center.y + moved.y - point.y, p.center.z)
                        p.metadata["longitudinal_m"] = round(station, 3)
                stats["street_tree_count"] += 1
                stats["resolved_outdoor_asset_count" if resolved else "procedural_outdoor_fallback_count"] += 1

            light_start = max(start_limit, 7.0)
            light_end = min(frame.length - 6.0, end_limit)
            for light_index, distance in self._rhythm_distances(
                road.id,
                side,
                light_start,
                light_end,
                program.street_light_spacing_m,
                program.placement_pattern,
                "light",
            ):
                if not self._rhythm_keeps(
                    road.id,
                    side,
                    light_index,
                    program.placement_pattern,
                    "light",
                ):
                    continue
                distance = self._sidewalk_station(city, road, frame, distance, sign * outer_strip,
                    (light_start, light_end), protected[side], occupied[side], 0.6, 0, stats)
                if distance is not None:
                    point = frame.point(distance, sign * outer_strip)
                    resolved = self._street_light(
                        road, point, side, light_index, distance, program, scene
                    )
                    stats["street_light_count"] += 1
                    stats["resolved_outdoor_asset_count" if resolved else "procedural_outdoor_fallback_count"] += 1

            # Small furniture clusters make the sidewalk read as an inhabited
            # public space while remaining sparse enough for first-person views.
            if profile.street_furniture and frame.length > 34.0:
                # High-activity and civic/commercial roads get two compact
                # furniture clusters so the middle of a long block does not
                # read as an empty corridor.  Other roads retain one cluster.
                cluster_fractions = (
                    (0.30, 0.62)
                    if program.activity_level == "high"
                    or program.dominant_function in {"civic", "commercial"}
                    else (0.58,)
                )
                for cluster_index, fraction in enumerate(cluster_fractions):
                    distance = self._sidewalk_station(city, road, frame, frame.length * fraction,
                        sign * outer_strip, (start_limit, end_limit), protected[side], occupied[side], 2.0, 2.5, stats)
                    if distance is None:
                        continue
                    point = frame.point(distance, sign * outer_strip)
                    resolved_count = self._street_furniture(
                        road, point, side, scene, cluster_index=cluster_index
                    )
                    stats["street_furniture_count"] += 1
                    stats["resolved_outdoor_asset_count"] += resolved_count
                    stats["procedural_outdoor_fallback_count"] += 2 - resolved_count

        self._compile_programmed_amenities(
            city, road, frame, program, scene, stats, protected, occupied
        )
        self._compile_frontages(city, road, frame, program, scene, stats)
        self._compile_population(
            city, road, frame, scene, profile, appearance, program, stats
        )
        self._compile_activity_motifs(
            city, road, frame, scene, program, stats
        )

    def _compile_programmed_amenities(
        self,
        city: City,
        road: RoadSegment,
        frame: _Frame,
        program: StreetSegmentProgram,
        scene: Any,
        stats: dict[str, int],
        protected, occupied,
    ) -> None:
        supported = [
            item
            for item in program.amenity_types
            if item
            in {
                "planter",
                "bench",
                "bicycle_rack",
                "bus_stop",
                "fire_hydrant",
                "bollard",
                "small_sign",
            }
        ]
        if not supported or frame.length < 24.0:
            return
        start_limit, end_limit = self._usable_limits(road, frame, extra=3.0)
        span = end_limit - start_limit
        if span < 8.0:
            return
        metadata = self._program_metadata(program)
        outer_offset = road.width_m / 2 + road.sidewalk_width_m * 0.76
        for index, amenity in enumerate(supported):
            fraction = (index + 1) / (len(supported) + 1)
            distance = start_limit + span * fraction
            side = (
                "left"
                if (self._seed(road.id, amenity, str(index)) % 2 == 0)
                else "right"
            )
            sign = 1.0 if side == "left" else -1.0
            radius = {"bus_stop": 1.9, "bench": 1.05, "bicycle_rack": 1.0, "planter": .8}.get(amenity, .4)
            distance = self._sidewalk_station(city, road, frame, distance, sign * outer_offset,
                (start_limit, end_limit), protected[side], occupied[side], radius, 3.0, stats)
            if distance is None:
                continue
            point = frame.point(distance, sign * outer_offset)
            resolved = self._programmed_amenity(
                road,
                frame,
                point,
                amenity,
                side,
                index,
                metadata,
                scene,
            )
            stats["programmed_amenity_count"] += 1
            stats[
                "resolved_outdoor_asset_count"
                if resolved
                else "procedural_outdoor_fallback_count"
            ] += 1

    def _programmed_amenity(
        self,
        road: RoadSegment,
        frame: _Frame,
        point: Point2D,
        amenity: str,
        side: str,
        index: int,
        program_metadata: dict[str, Any],
        scene: Any,
    ) -> bool:
        specs = {
            "planter": (
                "large rectangular street planter with shrubs",
                "street_planter",
                Vec3(1.25, 0.72, 0.72),
                "street_planter",
            ),
            "bench": (
                "public street bench wood metal",
                "street_bench",
                Vec3(1.9, 0.62, 0.86),
                "bench",
            ),
            "bicycle_rack": (
                "inverted U public bicycle rack",
                "bicycle_rack",
                Vec3(1.8, 0.72, 0.82),
                "bicycle_rack",
            ),
            "bus_stop": (
                "modern transparent public bus shelter",
                "bus_shelter",
                Vec3(3.4, 1.45, 2.55),
                "bus_shelter",
            ),
            "fire_hydrant": (
                "red urban fire hydrant",
                "fire_hydrant",
                Vec3(0.55, 0.55, 0.95),
                "fire_hydrant",
            ),
            "bollard": (
                "short black metal street bollard",
                "bollard",
                Vec3(0.28, 0.28, 0.86),
                "bollard",
            ),
            "small_sign": (
                "small pedestrian wayfinding sign",
                "small_sign",
                Vec3(0.55, 0.16, 1.65),
                "small_sign",
            ),
        }
        frame = frame.at_point(point)
        query, category, size, semantic = specs[amenity]
        base = f"{road.id}_program_{amenity}_{side}_{index:02d}"
        metadata = {
            **program_metadata,
            "road_id": road.id,
            "street_asset": amenity,
            "programmed_amenity": True,
            "side": side,
        }
        if self._asset(
            query,
            category,
            road.id,
            point,
            size,
            self._rotation(frame, point),
            base,
            scene,
            semantic=semantic,
            metadata=metadata,
        ):
            return True
        rotation = self._rotation(frame, point)
        if amenity == "planter":
            scene.primitives.extend(
                [
                    self._box(
                        f"{base}_box",
                        road.id,
                        Vec3(point.x, point.y, 0.30),
                        Vec3(1.18, 0.66, 0.56),
                        rotation,
                        "street_planter",
                        "facade_frame_stone",
                        "roads",
                        metadata={**metadata, "asset_fallback": "procedural"},
                    ),
                    self._sphere(
                        f"{base}_plant",
                        road.id,
                        Vec3(point.x, point.y, 0.72),
                        Vec3(0.92, 0.58, 0.54),
                        rotation,
                        "street_planter_vegetation",
                        "tree_canopy",
                        "roads",
                        metadata=metadata,
                    ),
                ]
            )
        elif amenity == "bench":
            scene.primitives.append(
                self._box(
                    base,
                    road.id,
                    Vec3(point.x, point.y, 0.48),
                    Vec3(1.9, 0.52, 0.18),
                    rotation,
                    "bench",
                    "furniture_wood",
                    "roads",
                    metadata={**metadata, "asset_fallback": "procedural"},
                )
            )
        elif amenity == "bicycle_rack":
            for rack_index in range(2):
                rack = Point2D(
                    point.x + frame.ux * (rack_index - 0.5) * 0.75,
                    point.y + frame.uy * (rack_index - 0.5) * 0.75,
                )
                scene.primitives.extend(
                    [
                        self._cylinder(
                            f"{base}_{rack_index}_a",
                            road.id,
                            Vec3(rack.x + frame.nx * 0.24, rack.y + frame.ny * 0.24, 0.38),
                            Vec3(0.055, 0.055, 0.76),
                            rotation,
                            "bicycle_rack",
                            "furniture_metal",
                            "roads",
                            metadata={**metadata, "asset_fallback": "procedural"},
                        ),
                        self._cylinder(
                            f"{base}_{rack_index}_b",
                            road.id,
                            Vec3(rack.x - frame.nx * 0.24, rack.y - frame.ny * 0.24, 0.38),
                            Vec3(0.055, 0.055, 0.76),
                            rotation,
                            "bicycle_rack",
                            "furniture_metal",
                            "roads",
                            metadata=metadata,
                        ),
                    ]
                )
        elif amenity == "bus_stop":
            scene.primitives.extend(
                [
                    self._box(
                        f"{base}_roof",
                        road.id,
                        Vec3(point.x, point.y, 2.46),
                        Vec3(3.2, 1.32, 0.12),
                        rotation,
                        "bus_shelter",
                        "street_furniture",
                        "roads",
                        metadata={**metadata, "asset_fallback": "procedural"},
                    ),
                    self._box(
                        f"{base}_glass",
                        road.id,
                        Vec3(
                            point.x + frame.nx * (0.58 if side == "left" else -0.58),
                            point.y + frame.ny * (0.58 if side == "left" else -0.58),
                            1.25,
                        ),
                        Vec3(3.0, 0.06, 2.12),
                        rotation,
                        "bus_shelter_glass",
                        "facade_glass_smoke",
                        "roads",
                        metadata=metadata,
                    ),
                ]
            )
        elif amenity == "small_sign":
            # Keep the fallback readable at first-person scale: a slim post
            # with a double-sided directional plate, placed fully in the
            # furnishing strip rather than on the carriageway.
            scene.primitives.extend(
                [
                    self._cylinder(
                        f"{base}_post",
                        road.id,
                        Vec3(point.x, point.y, 0.78),
                        Vec3(0.045, 0.045, 1.56),
                        rotation,
                        "small_sign_post",
                        "furniture_metal",
                        "roads",
                        metadata={**metadata, "asset_fallback": "procedural"},
                    ),
                    self._box(
                        f"{base}_plate",
                        road.id,
                        Vec3(point.x, point.y, 1.48),
                        Vec3(0.56, 0.08, 0.32),
                        rotation,
                        "small_sign",
                        "street_furniture",
                        "roads",
                        metadata={**metadata, "asset_fallback": "procedural"},
                    ),
                ]
            )
        else:
            material = (
                "facade_accent_warm"
                if amenity == "fire_hydrant"
                else "street_furniture"
            )
            scene.primitives.append(
                self._cylinder(
                    base,
                    road.id,
                    Vec3(point.x, point.y, size.z / 2),
                    size,
                    rotation,
                    semantic,
                    material,
                    "roads",
                    metadata={**metadata, "asset_fallback": "procedural"},
                )
            )
        return False

    def _compile_frontages(
        self,
        city: City,
        road: RoadSegment,
        frame: _Frame,
        program: StreetSegmentProgram,
        scene: Any,
        stats: dict[str, int],
    ) -> None:
        if not program.adjacent_building_ids:
            return
        buildings = {
            building.id: building
            for building in city.iter_buildings()
            if building.id in set(program.adjacent_building_ids)
        }
        metadata = self._program_metadata(program)
        for building_id in program.adjacent_building_ids:
            building = buildings.get(building_id)
            if building is None:
                continue
            entrance = building.entrance
            projection = frame.project(entrance)
            distance = projection.distance
            signed_offset = projection.lateral
            sign = 1.0 if signed_offset >= 0 else -1.0
            side = "left" if sign > 0 else "right"
            sidewalk_edge = frame.point(
                distance,
                sign * (road.width_m / 2 + road.sidewalk_width_m),
            )
            connector_dx = entrance.x - sidewalk_edge.x
            connector_dy = entrance.y - sidewalk_edge.y
            connector_length = math.hypot(connector_dx, connector_dy)
            if connector_length < 0.45 or connector_length > 24.0:
                continue
            if self._path_intrudes_other_road(
                city, road.id, sidewalk_edge, entrance, 0.35
            ):
                continue
            connector_rotation = math.degrees(
                math.atan2(connector_dy, connector_dx)
            )
            connector_width = self._frontage_width(program)
            center = Vec3(
                (entrance.x + sidewalk_edge.x) / 2,
                (entrance.y + sidewalk_edge.y) / 2,
                0.135,
            )
            frontage_meta = {
                **metadata,
                "road_id": road.id,
                "building_id": building.id,
                "frontage_treatment": program.frontage_treatment,
                "frontage_role": "entrance_path",
                "path_width_m": round(float(connector_width), 3),
                "side": side,
            }
            scene.primitives.append(
                self._box(
                    f"{road.id}_{building.id}_frontage_connector",
                    road.id,
                    center,
                    Vec3(connector_length, connector_width, 0.10),
                    connector_rotation,
                    "frontage_connector",
                    f"frontage_{program.frontage_treatment}",
                    "roads",
                    collision_enabled=False,
                    metadata=frontage_meta,
                )
            )
            # A short entrance landing makes the road-to-door connection
            # legible at aerial and street scale even when the long path
            # shares a similar paving family with the sidewalk.
            landing_center = Point2D(
                entrance.x - connector_dx / max(connector_length, 1e-6) * 0.22,
                entrance.y - connector_dy / max(connector_length, 1e-6) * 0.22,
            )
            scene.primitives.append(
                self._box(
                    f"{road.id}_{building.id}_entrance_landing",
                    road.id,
                    Vec3(landing_center.x, landing_center.y, 0.19),
                    Vec3(0.52, min(connector_width + 0.35, 3.8), 0.08),
                    connector_rotation,
                    "entrance_landing",
                    f"frontage_{program.frontage_treatment}",
                    "roads",
                    collision_enabled=False,
                    metadata={**frontage_meta, "frontage_role": "entrance_landing"},
                )
            )
            stats["frontage_connector_count"] += 1
            stats["frontage_detail_count"] += self._compile_frontage_details(
                road,
                frame,
                building,
                connector_length,
                connector_dx,
                connector_dy,
                program,
                frontage_meta,
                scene,
            )

    def _compile_frontage_details(
        self,
        road: RoadSegment,
        frame: _Frame,
        building: Any,
        setback: float,
        connector_dx: float,
        connector_dy: float,
        program: StreetSegmentProgram,
        metadata: dict[str, Any],
        scene: Any,
    ) -> int:
        entrance = building.entrance
        length = max(1e-6, math.hypot(connector_dx, connector_dy))
        along_x, along_y = connector_dx / length, connector_dy / length
        side_x, side_y = -along_y, along_x
        rotation = self._rotation(frame, entrance)
        clear_offset = metadata["path_width_m"] / 2 + PEDESTRIAN_RADIUS
        count = 0
        if "planter" in program.amenity_types:
            offset = clear_offset + math.hypot(1.0, .62) / 2
            for index, sign in enumerate((-1.0, 1.0)):
                point = Point2D(
                    entrance.x + side_x * sign * offset - along_x * 0.50,
                    entrance.y + side_y * sign * offset - along_y * 0.50,
                )
                base = f"{road.id}_{building.id}_frontage_planter_{index}"
                if not self._asset(
                    "architectural entrance planter with shrubs",
                    "street_planter",
                    road.id,
                    point,
                    Vec3(1.0, 0.62, 0.70),
                    rotation,
                    base,
                    scene,
                    semantic="frontage_planter",
                    metadata={**metadata, "frontage_detail": "planter"},
                ):
                    scene.primitives.extend(
                        [
                            self._box(
                                f"{base}_box",
                                road.id,
                                Vec3(point.x, point.y, 0.27),
                                Vec3(0.94, 0.58, 0.50),
                                rotation,
                                "frontage_planter",
                                "facade_frame_stone",
                                "roads",
                                metadata={**metadata, "asset_fallback": "procedural"},
                            ),
                            self._sphere(
                                f"{base}_plant",
                                road.id,
                                Vec3(point.x, point.y, 0.66),
                                Vec3(0.74, 0.48, 0.48),
                                rotation,
                                "frontage_vegetation",
                                "tree_canopy",
                                "roads",
                                metadata=metadata,
                            ),
                        ]
                    )
                count += 1
        sign_setback = 1.65 if "planter" in program.amenity_types else .42
        if program.frontage_treatment in {"retail", "civic"} and setback >= sign_setback + .15:
            offset = clear_offset + math.hypot(1.05, .10) / 2
            sign_point = Point2D(
                entrance.x + side_x * offset - along_x * sign_setback,
                entrance.y + side_y * offset - along_y * sign_setback,
            )
            scene.primitives.extend(
                [
                    self._cylinder(
                        f"{road.id}_{building.id}_frontage_sign_post",
                        road.id,
                        Vec3(sign_point.x, sign_point.y, 0.82),
                        Vec3(0.08, 0.08, 1.64),
                        rotation,
                        "frontage_sign",
                        "street_furniture",
                        "roads",
                        metadata=metadata,
                    ),
                    self._box(
                        f"{road.id}_{building.id}_frontage_sign_panel",
                        road.id,
                        Vec3(sign_point.x, sign_point.y, 1.42),
                        Vec3(1.05, 0.10, 0.58),
                        rotation,
                        "frontage_sign",
                        "facade_accent_warm",
                        "roads",
                        metadata={**metadata, "frontage_detail": "identity_sign"},
                    ),
                ]
            )
            count += 1
        if (
            program.frontage_treatment == "retail"
            and "cafe_terrace" in program.amenity_types
            and setback >= 5.2
        ):
            for index, sign in enumerate((-1.0, 1.0)):
                offset = clear_offset + math.hypot(.78, .78) / 2
                table_x = entrance.x - along_x * min(3.2, setback * 0.48) + side_x * sign * offset
                table_y = entrance.y - along_y * min(3.2, setback * 0.48) + side_y * sign * offset
                scene.primitives.extend(
                    [
                        self._cylinder(
                            f"{road.id}_{building.id}_cafe_table_{index}",
                            road.id,
                            Vec3(table_x, table_y, 0.56),
                            Vec3(0.78, 0.78, 0.10),
                            rotation,
                            "cafe_table",
                            "furniture_wood",
                            "roads",
                            metadata={**metadata, "frontage_detail": "cafe_terrace"},
                        ),
                        self._box(
                            f"{road.id}_{building.id}_cafe_chair_{index}",
                            road.id,
                            Vec3(
                                table_x + side_x * sign * 0.72,
                                table_y + side_y * sign * 0.72,
                                0.46,
                            ),
                            Vec3(0.48, 0.48, 0.80),
                            rotation,
                            "cafe_chair",
                            "furniture_wood",
                            "roads",
                            metadata=metadata,
                        ),
                    ]
                )
            count += 1
        if program.frontage_treatment == "industrial":
            for index, sign in enumerate((-1.0, 1.0)):
                point = Point2D(
                    entrance.x + side_x * sign * (clear_offset + .16) - along_x * 0.35,
                    entrance.y + side_y * sign * (clear_offset + .16) - along_y * 0.35,
                )
                scene.primitives.append(
                    self._cylinder(
                        f"{road.id}_{building.id}_loading_bollard_{index}",
                        road.id,
                        Vec3(point.x, point.y, 0.44),
                        Vec3(0.22, 0.22, 0.82),
                        rotation,
                        "loading_bollard",
                        "street_furniture",
                        "roads",
                        metadata={**metadata, "frontage_detail": "loading_control"},
                    )
                )
            count += 1
        return count

    def _compile_population(
        self, city, road, frame, scene, profile, appearance, program, stats
    ) -> None:
        # Vehicles use lane offsets and are intentionally static snapshot bodies;
        # metadata carries enough information for a future traffic backend.
        start_limit, end_limit = self._usable_limits(road, frame, extra=2.5)
        lane_count = max(1, int(road.lane_count))
        carriageway_width = max(road.width_m - road.median_width_m, road.width_m * 0.65)
        parking_offsets = tuple(
            (1.0 if side == "left" else -1.0) * (road.width_m / 2 - 1.08)
            for side in (program.parking_sides if road.parking_allowed else ())
        )
        # Treat the curbside lane as occupied by parked cars. Dynamic vehicles
        # are assigned only to lane centers with a conservative lateral gap,
        # preventing body meshes from nearly touching parked vehicles on narrow
        # local/service roads. If every lane is occupied, the safe result is no
        # moving snapshot on that segment rather than a collision.
        safe_lane_indices = tuple(
            lane
            for lane in range(lane_count)
            if all(
                abs(
                    (lane - (lane_count - 1) / 2)
                    * (carriageway_width / max(lane_count, 1))
                    - parked_offset
                ) >= 2.10
                for parked_offset in parking_offsets
            )
        )
        for index, distance in self._rhythm_distances(
            road.id,
            "center",
            max(start_limit, 8.0),
            min(frame.length - 9.0, end_limit),
            program.vehicle_spacing_m,
            program.placement_pattern,
            "vehicle",
        ):
            if index % 2 == 0 or profile.parking_ratio > 0.25:
                if not safe_lane_indices:
                    continue
                lane = safe_lane_indices[index % len(safe_lane_indices)]
                lane_offset = (lane - (lane_count - 1) / 2) * (carriageway_width / max(lane_count, 1))
                point = frame.point(distance, lane_offset)
                if not self._near_entrance(city, point, 2.2) and not self._inside_other_road(city, road.id, point, 0.8):
                    vehicle_kind = appearance.vehicle_mix[index % len(appearance.vehicle_mix)]
                    resolved = self._vehicle(
                        road, point, self._rotation(frame, point), index, scene,
                        parked=False, vehicle_kind=vehicle_kind,
                        metadata={
                            "lane_offset_m": round(float(lane_offset), 3),
                            "parking_clearance_enforced": bool(parking_offsets),
                        },
                    )
                    stats["vehicle_count"] += 1
                    stats["resolved_outdoor_asset_count" if resolved else "procedural_outdoor_fallback_count"] += 1

        self._compile_background_parking_and_pedestrians(
            city, road, frame, scene, profile, appearance, program, stats
        )

    def _compile_activity_motifs(
        self,
        city: City,
        road: RoadSegment,
        frame: _Frame,
        scene: Any,
        program: StreetSegmentProgram,
        stats: dict[str, int],
    ) -> None:
        """Compile bounded, semantically bound street activity clusters.

        Background population communicates density. These motifs communicate
        *why* people and vehicles are present: waiting at a crossing or bus
        stop, browsing a retail frontage, dwelling at a cafe, cycling, or
        servicing a loading frontage. The agent owns only the mode selection;
        this method owns all metric positions and clearance checks.
        """

        modes = tuple(program.activity_modes[: program.activity_cluster_count])
        if not modes or frame.length < 24.0:
            return
        start_limit, end_limit = self._usable_limits(road, frame, extra=3.5)
        start_limit = max(start_limit, 7.0)
        end_limit = min(end_limit, frame.length - 7.0)
        if end_limit - start_limit < 8.0:
            return

        for cluster_index, mode in enumerate(modes):
            distance = self._activity_distance(
                road, frame, program, mode, cluster_index, len(modes),
                start_limit, end_limit,
            )
            side = (
                "left"
                if self._seed(road.id, mode, str(cluster_index), "activity_side") % 2 == 0
                else "right"
            )
            sign = 1.0 if side == "left" else -1.0
            if mode == "cycle_flow":
                if program.bicycle_lane_sides:
                    side = program.bicycle_lane_sides[
                        self._seed(road.id, mode, "cycle_side")
                        % len(program.bicycle_lane_sides)
                    ]
                    sign = 1.0 if side == "left" else -1.0
                    lateral = sign * (road.width_m / 2 - 0.82)
                elif road.road_class == "shared_space":
                    lateral = sign * min(1.8, road.width_m * 0.20)
                else:
                    continue
            else:
                sidewalk_fraction = 0.66 if mode in {"retail_browsing", "cafe_dwell"} else 0.48
                lateral = sign * (
                    road.width_m / 2
                    + max(0.42, road.sidewalk_width_m * sidewalk_fraction)
                )

            center = frame.point(distance, lateral)
            if self._inside_other_road(city, road.id, center, 0.30):
                continue
            if self._near_entrance(city, center, 1.25):
                shifted = frame.point(min(end_limit, distance + 2.6), lateral)
                if self._near_entrance(city, shifted, 1.25):
                    shifted = frame.point(max(start_limit, distance - 2.6), lateral)
                center = shifted
                distance = frame.project(center).distance
            if self._inside_other_road(city, road.id, center, 0.30):
                continue

            cluster_id = f"{road.id}_activity_{cluster_index:02d}_{mode}"
            compiled = self._compile_activity_cluster(
                city,
                road,
                frame,
                scene,
                program,
                mode,
                cluster_id,
                cluster_index,
                distance,
                side,
                sign,
                lateral,
                stats,
            )
            if compiled:
                stats["activity_cluster_count"] += 1

    def _activity_distance(
        self,
        road: RoadSegment,
        frame: _Frame,
        program: StreetSegmentProgram,
        mode: str,
        cluster_index: int,
        cluster_count: int,
        start_limit: float,
        end_limit: float,
    ) -> float:
        """Choose a deterministic longitudinal anchor tied to the activity."""

        span = end_limit - start_limit
        if mode == "intersection_waiting":
            return (
                start_limit + min(2.0, span * 0.12)
                if self._seed(road.id, mode, "junction") % 2 == 0
                else end_limit - min(2.0, span * 0.12)
            )
        if mode == "transit_waiting" and "bus_stop" in program.amenity_types:
            supported = [
                item for item in program.amenity_types
                if item in {
                    "planter", "bench", "bicycle_rack", "bus_stop",
                    "fire_hydrant", "bollard", "small_sign",
                }
            ]
            bus_index = supported.index("bus_stop")
            amenity_start, amenity_end = self._usable_limits(road, frame, extra=3.0)
            amenity_span = max(0.0, amenity_end - amenity_start)
            candidate = amenity_start + amenity_span * (
                (bus_index + 1) / (len(supported) + 1)
            )
            return max(start_limit, min(end_limit, candidate))
        fraction = (cluster_index + 1) / (cluster_count + 1)
        jitter = (
            self._unit_noise(road.id, mode, str(cluster_index), "activity_anchor")
            - 0.5
        ) * min(5.0, span / max(4.0, cluster_count * 1.5))
        return max(start_limit, min(end_limit, start_limit + span * fraction + jitter))

    def _compile_activity_cluster(
        self,
        city: City,
        road: RoadSegment,
        frame: _Frame,
        scene: Any,
        program: StreetSegmentProgram,
        mode: str,
        cluster_id: str,
        cluster_index: int,
        distance: float,
        side: str,
        sign: float,
        lateral: float,
        stats: dict[str, int],
    ) -> bool:
        group_sizes = {
            "commute_flow": 2,
            "retail_browsing": 2,
            "cafe_dwell": 2,
            "transit_waiting": 4,
            "intersection_waiting": 3,
            "cycle_flow": 1,
            "loading_service": 1,
            "residential_stroll": 2,
        }
        states = {
            "commute_flow": "walking",
            "retail_browsing": "standing browsing",
            "cafe_dwell": "seated relaxing",
            "transit_waiting": "standing waiting",
            "intersection_waiting": "standing waiting",
            "cycle_flow": "cycling bicycle",
            "loading_service": "standing worker",
            "residential_stroll": "walking leisure",
        }
        roles = {
            "commute_flow": "commuter",
            "retail_browsing": "shopper",
            "cafe_dwell": "cafe_visitor",
            "transit_waiting": "transit_passenger",
            "intersection_waiting": "crossing_waiter",
            "cycle_flow": "cyclist",
            "loading_service": "service_worker",
            "residential_stroll": "resident",
        }
        if mode not in group_sizes:
            return False

        if mode in {"retail_browsing", "cafe_dwell"}:
            heading = self._rotation(frame, frame.point(distance)) + (90.0 if sign > 0 else -90.0)
        elif mode in {"transit_waiting", "intersection_waiting", "loading_service"}:
            heading = self._rotation(frame, frame.point(distance)) + (-90.0 if sign > 0 else 90.0)
        else:
            heading = self._rotation(frame, frame.point(distance)) + (
                180.0 if self._seed(cluster_id, "direction") % 2 else 0.0
            )

        compiled = False
        for member in range(group_sizes[mode]):
            along = (member - (group_sizes[mode] - 1) / 2) * (
                0.88 if mode != "transit_waiting" else 0.72
            )
            across = (
                self._unit_noise(cluster_id, str(member), "member_across") - 0.5
            ) * min(0.52, road.sidewalk_width_m * 0.24)
            point = frame.point(distance + along, lateral + across)
            if self._inside_other_road(city, road.id, point, 0.22):
                continue
            person_index = 6000 + cluster_index * 100 + member
            metadata = {
                "activity_motif": mode,
                "activity_cluster_id": cluster_id,
                "activity_role": roles[mode],
                "activity_binding": (
                    "bicycle_lane" if mode == "cycle_flow" and program.bicycle_lane_sides
                    else "shared_space" if mode == "cycle_flow"
                    else "bus_stop" if mode == "transit_waiting"
                    else "junction" if mode == "intersection_waiting"
                    else "active_frontage" if mode in {"retail_browsing", "cafe_dwell"}
                    else "service_frontage" if mode == "loading_service"
                    else "sidewalk"
                ),
                "activity_group_member": member,
                "activity_group_size": group_sizes[mode],
                "placement_side": side,
                "longitudinal_m": round(float(distance + along), 3),
                "sidewalk_bound": mode != "cycle_flow",
                "cycle_lane_bound": mode == "cycle_flow",
            }
            resolved = self._pedestrian(
                road,
                point,
                heading + (member - (group_sizes[mode] - 1) / 2) * 5.0,
                person_index,
                sign,
                scene,
                state=states[mode],
                metadata=metadata,
            )
            stats["pedestrian_count"] += 1
            stats["activity_person_count"] += 1
            if mode == "transit_waiting":
                stats["transit_waiting_person_count"] += 1
            elif mode == "intersection_waiting":
                stats["intersection_waiting_person_count"] += 1
            elif mode in {"retail_browsing", "cafe_dwell"}:
                stats["retail_activity_person_count"] += 1
            elif mode == "cycle_flow":
                stats["cyclist_count"] += 1
            elif mode == "loading_service":
                stats["service_activity_count"] += 1
            stats[
                "resolved_outdoor_asset_count"
                if resolved
                else "procedural_outdoor_fallback_count"
            ] += 1
            compiled = True

        if mode == "loading_service":
            vehicle_point = frame.point(
                distance,
                sign * max(0.0, road.width_m / 2 - 1.12),
            )
            if not self._inside_other_road(city, road.id, vehicle_point, 0.65):
                resolved = self._vehicle(
                    road,
                    vehicle_point,
                    self._rotation(frame, frame.point(distance)) + (180.0 if sign > 0 else 0.0),
                    7000 + cluster_index,
                    scene,
                    parked=True,
                    vehicle_kind="van",
                    metadata={
                        "activity_motif": mode,
                        "activity_cluster_id": cluster_id,
                        "activity_role": "delivery_vehicle",
                        "activity_binding": "service_frontage",
                    },
                )
                stats["vehicle_count"] += 1
                stats["parked_vehicle_count"] += 1
                stats["service_activity_count"] += 1
                stats[
                    "resolved_outdoor_asset_count"
                    if resolved
                    else "procedural_outdoor_fallback_count"
                ] += 1
                compiled = True
        return compiled

    def _compile_background_parking_and_pedestrians(
        self, city, road, frame, scene, profile, appearance, program, stats
    ) -> None:
        """Compile the non-event background population for a street segment."""

        start_limit, end_limit = self._usable_limits(road, frame, extra=2.5)
        for side_index, side in enumerate(program.parking_sides if road.parking_allowed else ()):
            sign = 1.0 if side == "left" else -1.0
            parking_offset = sign * (road.width_m / 2 - 1.08)
            cursor = max(
                start_limit,
                14.0 + (self._seed(road.id, side, "parked") % 500) / 100.0,
            )
            parked_index = 0
            while cursor < min(frame.length - 9.0, end_limit):
                occupancy = self._seed(road.id, side, str(parked_index), "occupancy") % 100
                if occupancy < max(18, round(profile.parking_ratio * 100)):
                    position_jitter = (
                        self._unit_noise(
                            road.id, side, str(parked_index), "parked_jitter"
                        )
                        - 0.5
                    ) * 0.8
                    point = frame.point(cursor + position_jitter, parking_offset)
                    if not self._near_entrance(city, point, 4.2):
                        vehicle_kind = appearance.vehicle_mix[
                            (parked_index + side_index) % len(appearance.vehicle_mix)
                        ]
                        if vehicle_kind == "bus":
                            vehicle_kind = "van"
                        resolved = self._vehicle(
                            road,
                            point,
                            self._rotation(frame, point) + (180.0 if side == "left" else 0.0),
                            1000 + side_index * 100 + parked_index,
                            scene,
                            parked=True,
                            vehicle_kind=vehicle_kind,
                        )
                        stats["vehicle_count"] += 1
                        stats["parked_vehicle_count"] += 1
                        stats[
                            "resolved_outdoor_asset_count"
                            if resolved
                            else "procedural_outdoor_fallback_count"
                        ] += 1
                cursor += 6.4
                parked_index += 1

        activity_group_cap = {"low": 1, "medium": 2, "high": 3}[
            program.activity_level
        ]
        for event_index, distance in self._rhythm_distances(
            road.id,
            "population",
            max(start_limit, 8.0),
            min(frame.length - 8.0, end_limit),
            program.pedestrian_spacing_m,
            program.placement_pattern,
            "pedestrian",
        ):
            side_selector = self._seed(
                road.id, str(event_index), "pedestrian_side"
            ) % 5
            signs = (
                (1.0, -1.0)
                if program.activity_level == "high" and side_selector == 0
                else ((1.0,) if side_selector % 2 == 0 else (-1.0,))
            )
            for sign in signs:
                group_size = 1 + (
                    self._seed(
                        road.id, str(event_index), str(sign), "pedestrian_group"
                    )
                    % activity_group_cap
                )
                for member in range(group_size):
                    member_offset = (member - (group_size - 1) / 2) * 0.92
                    lateral_jitter = (
                        self._unit_noise(
                            road.id,
                            str(event_index),
                            str(sign),
                            str(member),
                            "pedestrian_lateral",
                        )
                        - 0.5
                    ) * min(0.42, road.sidewalk_width_m * 0.18)
                    point = frame.point(
                        distance + member_offset,
                        sign
                        * (
                            road.width_m / 2
                            + road.sidewalk_width_m * 0.50
                            + lateral_jitter
                        ),
                    )
                    if self._near_entrance(city, point, 1.8) or self._inside_other_road(city, road.id, point, 0.35):
                        continue
                    person_index = event_index * 10 + member + (1000 if sign < 0 else 0)
                    state = appearance.pedestrian_mix[
                        person_index % len(appearance.pedestrian_mix)
                    ]
                    rotation_jitter = (
                        self._unit_noise(
                            road.id, str(person_index), "pedestrian_heading"
                        )
                        - 0.5
                    ) * 28.0
                    resolved = self._pedestrian(
                        road, point,
                        self._rotation(frame, point)
                        + (180.0 if person_index % 2 else 0.0)
                        + rotation_jitter,
                        person_index, sign, scene, state=state,
                    )
                    stats["pedestrian_count"] += 1
                    stats["resolved_outdoor_asset_count" if resolved else "procedural_outdoor_fallback_count"] += 1

    @staticmethod
    def _near_entrance(city: City, point: Point2D, radius: float) -> bool:
        return any(math.hypot(point.x - b.entrance.x, point.y - b.entrance.y) < radius for b in city.iter_buildings())

    def _usable_limits(self, road: RoadSegment, frame: _Frame, *, extra: float = 0.0) -> tuple[float, float]:
        """Return the safe longitudinal interval outside junction footprints."""

        start = self._junction_clearance.get(road.start_junction_id, 0.0)
        end = self._junction_clearance.get(road.end_junction_id, 0.0)
        if start > 0:
            start += extra
        if end > 0:
            end += extra
        return min(start, frame.length / 2), max(frame.length / 2, frame.length - end)

    @staticmethod
    def _point_segment_distance(point: Point2D, start: Point2D, end: Point2D) -> float:
        dx, dy = end.x - start.x, end.y - start.y
        length_sq = dx * dx + dy * dy
        if length_sq <= 1e-9:
            return math.hypot(point.x - start.x, point.y - start.y)
        factor = max(0.0, min(1.0, ((point.x - start.x) * dx + (point.y - start.y) * dy) / length_sq))
        nearest_x = start.x + factor * dx
        nearest_y = start.y + factor * dy
        return math.hypot(point.x - nearest_x, point.y - nearest_y)

    def _inside_other_road(
        self,
        city: City,
        owner_road_id: str,
        point: Point2D,
        margin: float = 0.0,
    ) -> bool:
        """Return whether a sidewalk-bound point intrudes into another carriageway."""

        for candidate in city.road_network.segments:
            if candidate.id == owner_road_id:
                continue
            # Cache all sampled vertices, never the endpoint chord. Reset for
            # each compile and invalidate when a road's centerline is replaced.
            cached = self._road_bounds.get(candidate.id)
            if cached is None or cached[0] is not candidate.centerline:
                points = candidate.centerline
                cached = (points, (min(p.x for p in points), min(p.y for p in points),
                                   max(p.x for p in points), max(p.y for p in points)))
                self._road_bounds[candidate.id] = cached
            x0, y0, x1, y1 = cached[1]
            radius = candidate.width_m / 2 + margin + 1e-8
            if (point.x < x0 - radius or point.x > x1 + radius or
                    point.y < y0 - radius or point.y > y1 + radius):
                continue
            if point_segment_distance(point, candidate.centerline) <= candidate.width_m / 2 + margin:
                return True
        return False

    def _path_intrudes_other_road(
        self,
        city: City,
        owner_road_id: str,
        start: Point2D,
        end: Point2D,
        margin: float = 0.0,
    ) -> bool:
        """Sample a finite strip/path instead of checking only its center."""

        length = math.hypot(end.x - start.x, end.y - start.y)
        steps = max(1, math.ceil(length / 1.25))
        for index in range(steps + 1):
            ratio = index / steps
            point = Point2D(
                start.x + (end.x - start.x) * ratio,
                start.y + (end.y - start.y) * ratio,
            )
            if self._inside_other_road(city, owner_road_id, point, margin):
                return True
        return False

    @staticmethod
    def _is_edge_road(city: City, road: RoadSegment) -> bool:
        """Whether a road forms part of the realized city boundary.

        Baseline and agent-authored plans both expose junction coordinates, so
        this remains independent of a particular grid. A small tolerance keeps
        boundary collectors stable after floating-point/VLM edits.
        """

        junctions = {item.id: item.position for item in city.road_network.junctions}
        endpoints = [
            junctions.get(road.start_junction_id),
            junctions.get(road.end_junction_id),
        ]
        if any(point is None for point in endpoints):
            return False
        points = [item.position for item in city.road_network.junctions]
        if not points:
            return False
        min_x = min(item.x for item in points)
        max_x = max(item.x for item in points)
        min_y = min(item.y for item in points)
        max_y = max(item.y for item in points)
        tolerance = max(0.75, min(3.0, road.width_m * 0.18))
        return all(
            min(
                abs(point.x - min_x), abs(point.x - max_x),
                abs(point.y - min_y), abs(point.y - max_y),
            ) <= tolerance
            for point in endpoints
        )

    def _tree_variant(self, city, road, index, program) -> tuple[str, str]:
        """Choose a context-aware botanical preference and query.

        The returned variant is still semantic (and therefore safe for legacy
        registries); exact species names are lexical hints that resolve to the
        downloaded Poly Haven models when available.
        """

        roll = self._seed(road.id, str(index), "species_preference") % 100
        edge = self._is_edge_road(city, road)
        residential = program.frontage_treatment == "residential"
        if edge and road.road_class in {"collector", "arterial"}:
            # Boundary collectors read as gateways into the district/city.
            # Jacaranda and Quiver Tree are accent species here, not a rigid
            # monoculture.
            if roll < 42:
                return ("jacaranda", "jacaranda tree gateway accent")
            if roll < 78:
                return ("quiver", "quiver tree gateway accent")
        if residential or edge:
            # Pine Sapling is deliberately a minority element on residential
            # and edge roads, preserving a mostly broadleaf streetscape.
            if index == 0 or roll < (38 if residential else 28):
                return ("pine_sapling", "pine sapling residential edge tree")
        if road.road_class in {"local", "shared_space", "service"}:
            # Ordinary roads use the two compact, realistic island/tree-small
            # assets to avoid repeating the same broad canopy everywhere.
            return (
                ("island", "island tree ordinary street tree")
                if roll % 2 == 0
                else ("tree_small_02", "tree small 02 ordinary street tree")
            )
        return ("ordinary", "street tree broadleaf")

    def _tree(self, city, road, point, side, index, distance, program, scene) -> bool:
        scale = 0.86 + 0.28 * self._unit_noise(
            road.id, side, str(index), "tree_scale"
        )
        height = (4.8 + (self._seed(road.id, side, str(index)) % 140) / 100.0) * scale
        owner = road.id
        base = f"{road.id}_street_tree_{side}_{index:02d}"
        palette = tuple(program.tree_palette)
        weighted_palette = (palette[0], palette[0], palette[0], *palette[1:])
        preferred_variant, preferred_query = self._tree_variant(city, road, index, program)
        variant = preferred_variant if preferred_variant != "ordinary" else weighted_palette[
            self._seed(road.id, side, str(index), "tree_palette")
            % len(weighted_palette)
        ]
        crown_width = {
            "columnar": 3.2,
            "evergreen": 3.8,
            "ornamental": 4.2,
            "broadleaf": 5.2,
            "deciduous": 4.8,
            "jacaranda": 5.0,
            "quiver": 3.8,
            "island": 4.8,
            "tree_small_02": 3.8,
            "pine_sapling": 2.8,
        }[variant] * scale
        rotation = self._unit_noise(
            road.id, side, str(index), "tree_rotation"
        ) * 360.0
        metadata = {
            "road_id": road.id,
            "street_asset": "tree",
            "variant": variant,
            "vegetation_preference": preferred_variant,
            "placement_side": side,
            "longitudinal_m": round(float(distance), 3),
            "placement_pattern": program.placement_pattern,
            "scale_factor": round(scale, 3),
        }
        resolved = self._asset(
            preferred_query, "street_tree", owner, point,
            Vec3(crown_width, crown_width, height),
            rotation, base, scene, semantic="street_tree_asset",
            metadata=metadata,
        )
        if not resolved and variant != "deciduous":
            # The semantic program may ask for a palette that the current
            # local pack cannot yet realize. Prefer a visually compatible,
            # reviewed deciduous tree over the conspicuous procedural blob;
            # retain the requested type in metadata for future asset autofill.
            resolved = self._asset(
                "street tree deciduous",
                "street_tree",
                owner,
                point,
                Vec3(crown_width, crown_width, height),
                rotation,
                base,
                scene,
                semantic="street_tree_asset",
                metadata={
                    **metadata,
                        "requested_variant": variant,
                    "variant": "deciduous_fallback",
                },
            )
        if resolved:
            return True
        # In production the curated asset registry is the visual source of
        # truth for vegetation.  Do not fall back to the old cyan procedural
        # blob when a realistic tree is unavailable: omitting one tree is
        # preferable to silently regressing the whole streetscape's style.
        # Unit/legacy callers without a registry retain the procedural proxy
        # for backwards compatibility.
        if getattr(self, "asset_registry_configured", False):
            return False
        scene.primitives.extend([
            self._cylinder(f"{base}_trunk", owner, Vec3(point.x, point.y, height * .34), Vec3(.28 * scale, .28 * scale, height * .68), rotation, "street_tree_trunk", "tree_trunk", "roads", collision_enabled=False, instance_key="street_tree_trunk", metadata=metadata),
            self._sphere(f"{base}_canopy_low", owner, Vec3(point.x, point.y, height * .68), Vec3(crown_width, crown_width, 1.8 * scale), rotation, "street_tree_canopy", "tree_canopy", "roads", collision_enabled=False, instance_key="street_tree_canopy", metadata=metadata),
            self._sphere(f"{base}_canopy_high", owner, Vec3(point.x + .18, point.y - .12, height * .88), Vec3(crown_width * .78, crown_width * .78, 1.65 * scale), rotation, "street_tree_canopy", "tree_canopy", "roads", collision_enabled=False, instance_key="street_tree_canopy", metadata=metadata),
        ])
        return False

    def _street_light(self, road, point, side, index, distance, program, scene) -> bool:
        base = f"{road.id}_street_light_{side}_{index:02d}"
        rotation = self._rotation(self._frame(road), point) + (180.0 if side == "right" else 0.0)
        metadata = {
            "road_id": road.id,
            "street_asset": "street_light",
            "light_family": program.light_family,
            "placement_side": side,
            "longitudinal_m": round(float(distance), 3),
            "placement_pattern": program.placement_pattern,
        }
        if self._asset(
            f"{program.light_family} urban street light", "street_light", road.id, point,
            Vec3(.8, .8, 5.2), rotation, base, scene,
            semantic="street_light_asset",
            metadata=metadata,
        ):
            return True
        scene.primitives.extend([
            self._cylinder(f"{base}_pole", road.id, Vec3(point.x, point.y, 2.2), Vec3(.12, .12, 4.4), rotation, "street_light", "street_furniture", "roads", collision_enabled=False, instance_key="street_light_pole", metadata=metadata),
            self._box(f"{base}_head", road.id, Vec3(point.x, point.y, 4.42), Vec3(.72, .20, .16), rotation, "street_light", "street_furniture", "roads", collision_enabled=False, instance_key="street_light_head", metadata=metadata),
        ])
        return False

    def _street_furniture(self, road, point, side, scene, *, cluster_index: int = 0) -> int:
        base = f"{road.id}_street_furniture_{side}_{cluster_index:02d}"
        frame = self._frame(road)
        assert frame is not None
        frame = frame.at_point(point)
        resolved = 0
        if self._asset(
            "public street bench wood metal", "street_bench", road.id, point,
            Vec3(1.9, .62, .86), self._rotation(frame, point), f"{base}_bench", scene,
            semantic="bench", metadata={"road_id": road.id, "street_asset": "bench"},
        ):
            resolved += 1
        else:
            scene.primitives.append(
                self._box(f"{base}_bench", road.id, Vec3(point.x, point.y, .48), Vec3(2.0, .48, .18), self._rotation(frame, point), "bench", "street_furniture", "roads", collision_enabled=False, instance_key="street_bench", metadata={"road_id": road.id, "street_asset": "bench"})
            )
        bin_point = Point2D(point.x + frame.ux * 1.6, point.y + frame.uy * 1.6)
        if self._asset(
            "modern covered public waste bin", "street_bin", road.id, bin_point,
            Vec3(.48, .48, .95), self._rotation(frame, point), f"{base}_bin", scene,
            semantic="street_bin", metadata={"road_id": road.id, "street_asset": "bin"},
        ):
            resolved += 1
        else:
            scene.primitives.append(
                self._box(f"{base}_bin", road.id, Vec3(bin_point.x, bin_point.y, .48), Vec3(.38, .38, .85), 0.0, "street_bin", "street_furniture", "roads", collision_enabled=False, instance_key="street_bin", metadata={"road_id": road.id, "street_asset": "bin"})
            )
        return resolved

    def _street_civic_details(self, road, point, frame: _Frame, scene) -> None:
        """Add compact procedural street hardware when curated meshes are absent."""

        base = f"{road.id}_civic_details"
        rotation = self._rotation(frame, point)
        # Bollard pair with a contrasting reflective cap.
        for index, offset in enumerate((-0.58, 0.58)):
            p = frame.point(frame.length * 0.38, road.width_m / 2 + road.sidewalk_width_m * 0.78 + offset)
            scene.primitives.extend([
                self._cylinder(f"{base}_bollard_{index}", road.id, Vec3(p.x, p.y, .42), Vec3(.16, .16, .78), rotation, "bollard", "street_furniture", "roads", collision_enabled=False, instance_key="bollard", metadata={"road_id": road.id, "street_asset": "bollard", "asset_fallback": "procedural"}),
                self._cylinder(f"{base}_bollard_cap_{index}", road.id, Vec3(p.x, p.y, .82), Vec3(.18, .18, .08), rotation, "bollard_reflector", "civic_limestone", "roads", collision_enabled=False, instance_key="bollard_reflector", metadata={"road_id": road.id, "street_asset": "bollard"}),
            ])
        # A compact bicycle rack made from inverted-U metal hoops.
        rack_origin = frame.point(frame.length * 0.38 + 1.8, road.width_m / 2 + road.sidewalk_width_m * 0.76)
        for index in range(2):
            p = frame.point(frame.length * 0.38 + 1.8 + index * 0.9, road.width_m / 2 + road.sidewalk_width_m * 0.76)
            scene.primitives.extend([
                self._cylinder(f"{base}_rack_post_a_{index}", road.id, Vec3(p.x, p.y - .28, .38), Vec3(.055, .055, .76), rotation, "bicycle_rack", "furniture_metal", "roads", collision_enabled=False, instance_key="bicycle_rack", metadata={"road_id": road.id, "street_asset": "bicycle_rack", "asset_fallback": "procedural"}),
                self._cylinder(f"{base}_rack_post_b_{index}", road.id, Vec3(p.x, p.y + .28, .38), Vec3(.055, .055, .76), rotation, "bicycle_rack", "furniture_metal", "roads", collision_enabled=False, instance_key="bicycle_rack", metadata={"road_id": road.id, "street_asset": "bicycle_rack", "asset_fallback": "procedural"}),
                self._box(f"{base}_rack_bar_{index}", road.id, Vec3(p.x, p.y, .72), Vec3(.055, .60, .055), rotation, "bicycle_rack", "furniture_metal", "roads", collision_enabled=False, instance_key="bicycle_rack", metadata={"road_id": road.id, "street_asset": "bicycle_rack", "asset_fallback": "procedural"}),
            ])
        # A red hydrant placed near the civic detail cluster.
        hydrant = frame.point(frame.length * 0.38 + 4.2, road.width_m / 2 + road.sidewalk_width_m * 0.76)
        scene.primitives.extend([
            self._cylinder(f"{base}_hydrant_body", road.id, Vec3(hydrant.x, hydrant.y, .42), Vec3(.24, .24, .84), rotation, "fire_hydrant", "facade_accent_warm", "roads", collision_enabled=False, instance_key="fire_hydrant", metadata={"road_id": road.id, "street_asset": "fire_hydrant", "asset_fallback": "procedural"}),
            self._cylinder(f"{base}_hydrant_cap", road.id, Vec3(hydrant.x, hydrant.y, .88), Vec3(.32, .32, .16), rotation, "fire_hydrant", "facade_accent_warm", "roads", collision_enabled=False, instance_key="fire_hydrant", metadata={"road_id": road.id, "street_asset": "fire_hydrant"}),
            self._cylinder(f"{base}_hydrant_nozzle", road.id, Vec3(hydrant.x + .16, hydrant.y, .56), Vec3(.16, .16, .16), rotation, "fire_hydrant", "facade_accent_warm", "roads", collision_enabled=False, instance_key="fire_hydrant", metadata={"road_id": road.id, "street_asset": "fire_hydrant"}),
        ])
        # One compact shelter/sign cluster per collector road, kept sparse so
        # it does not turn every sidewalk into a repeated kit.
        shelter = frame.point(frame.length * 0.68, road.width_m / 2 + road.sidewalk_width_m * 0.76)
        shelter_start = len(scene.primitives)
        for index, lateral in enumerate((-0.62, 0.62)):
            p = frame.point(frame.length * 0.68, road.width_m / 2 + road.sidewalk_width_m * 0.76 + lateral)
            scene.primitives.append(
                self._cylinder(f"{base}_shelter_post_{index}", road.id, Vec3(p.x, p.y, 1.25), Vec3(.07, .07, 2.5), rotation, "bus_shelter", "street_furniture", "roads", collision_enabled=False, instance_key="bus_shelter_post", metadata={"road_id": road.id, "street_asset": "bus_shelter", "asset_fallback": "procedural"})
            )
        scene.primitives.extend([
            self._box(f"{base}_shelter_roof", road.id, Vec3(shelter.x, shelter.y, 2.48), Vec3(3.0, 1.55, .12), rotation, "bus_shelter", "street_furniture", "roads", collision_enabled=False, instance_key="bus_shelter_roof", metadata={"road_id": road.id, "street_asset": "bus_shelter", "asset_fallback": "procedural"}),
            self._box(f"{base}_shelter_glass", road.id, Vec3(shelter.x, shelter.y + .70, 1.28), Vec3(2.8, .05, 2.1), rotation, "bus_shelter_glass", "facade_glass_smoke", "roads", collision_enabled=False, instance_key="bus_shelter_glass", metadata={"road_id": road.id, "street_asset": "bus_shelter", "asset_fallback": "procedural"}),
            self._box(f"{base}_shelter_bench", road.id, Vec3(shelter.x, shelter.y - .18, .48), Vec3(2.0, .45, .16), rotation, "bus_shelter_bench", "furniture_wood", "roads", collision_enabled=False, instance_key="bus_shelter_bench", metadata={"road_id": road.id, "street_asset": "bus_shelter", "asset_fallback": "procedural"}),
        ])
        shelter_end = len(scene.primitives)
        if self._asset(
            "bus shelter transit", "bus_shelter", road.id, shelter,
            Vec3(3.6, 1.6, 3.0), rotation, f"{base}_shelter", scene,
            semantic="bus_shelter", metadata={"road_id": road.id, "street_asset": "bus_shelter", "side": "left"},
        ):
            # Replace only this shelter's procedural pieces; retain the newly
            # appended mesh and the rest of this civic cluster.
            del scene.primitives[shelter_start:shelter_end]
        # Traffic signal at the same civic node, facing the road.
        signal = frame.point(frame.length * 0.68, road.width_m / 2 + road.sidewalk_width_m * 0.76 + 2.1)
        scene.primitives.extend([
            self._cylinder(f"{base}_signal_pole", road.id, Vec3(signal.x, signal.y, 2.1), Vec3(.10, .10, 4.2), rotation, "traffic_signal", "street_furniture", "roads", collision_enabled=False, instance_key="traffic_signal_pole", metadata={"road_id": road.id, "street_asset": "traffic_signal", "asset_fallback": "procedural"}),
            self._box(f"{base}_signal_head", road.id, Vec3(signal.x, signal.y, 3.65), Vec3(.28, .24, .92), rotation, "traffic_signal", "street_furniture", "roads", collision_enabled=False, instance_key="traffic_signal_head", metadata={"road_id": road.id, "street_asset": "traffic_signal", "asset_fallback": "procedural"}),
            self._sphere(f"{base}_signal_red", road.id, Vec3(signal.x, signal.y - .13, 3.92), Vec3(.14, .14, .14), rotation, "traffic_signal_red", "facade_accent_warm", "roads", collision_enabled=False, instance_key="traffic_signal_light", metadata={"road_id": road.id, "street_asset": "traffic_signal"}),
            self._sphere(f"{base}_signal_green", road.id, Vec3(signal.x, signal.y - .13, 3.38), Vec3(.14, .14, .14), rotation, "traffic_signal_green", "tree_canopy", "roads", collision_enabled=False, instance_key="traffic_signal_light", metadata={"road_id": road.id, "street_asset": "traffic_signal"}),
        ])

    def _vehicle(
        self,
        road,
        point,
        rotation,
        index,
        scene,
        parked: bool,
        vehicle_kind: str,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        base = f"{road.id}_vehicle_{index:03d}"
        vehicle_metadata = {
            "road_id": road.id,
            "population_role": "vehicle",
            "vehicle_kind": vehicle_kind,
            "parked": parked,
            "lane_bound": True,
            **(metadata or {}),
        }
        dimensions = {
            "sedan": Vec3(4.55, 1.82, 1.48),
            "suv": Vec3(4.75, 1.95, 1.72),
            "van": Vec3(5.25, 2.05, 2.35),
            "bus": Vec3(11.8, 2.55, 3.25),
            "pickup": Vec3(5.3, 2.1, 1.85),
            "ambulance": Vec3(6.2, 2.3, 2.7),
            "fire_truck": Vec3(9.0, 2.5, 3.2),
        }.get(vehicle_kind, Vec3(4.5, 1.85, 1.45))
        vehicle = self._asset(
            f"{vehicle_kind} vehicle", "vehicle", road.id, point, dimensions,
            rotation, base, scene, semantic="vehicle_asset",
            metadata=vehicle_metadata,
        )
        if not vehicle:
            if vehicle_kind == "bus":
                # A recognizable bus proxy is preferable to silently using a
                # sedan-sized box while a real bus asset is unavailable.
                body_size = Vec3(11.0, 2.45, 2.35)
                scene.primitives.extend([
                    self._box(f"{base}_body", road.id, Vec3(point.x, point.y, 1.38), body_size, rotation, "city_bus_body", "vehicle_paint", "roads", collision_enabled=False, instance_key="city_bus_body", metadata={**vehicle_metadata, "vehicle_kind": "bus", "asset_fallback": "procedural"}),
                    self._box(f"{base}_glass", road.id, Vec3(point.x, point.y, 2.05), Vec3(8.8, 2.50, .46), rotation, "city_bus_windows", "facade_glass_smoke", "roads", collision_enabled=False, instance_key="city_bus_windows", metadata={**vehicle_metadata, "vehicle_kind": "bus"}),
                    self._box(f"{base}_front", road.id, Vec3(point.x + math.cos(math.radians(rotation)) * 4.7, point.y + math.sin(math.radians(rotation)) * 4.7, 1.48), Vec3(.18, 2.3, 1.45), rotation, "city_bus_front", "facade_glass_blue", "roads", collision_enabled=False, instance_key="city_bus_front", metadata={**vehicle_metadata, "vehicle_kind": "bus"}),
                ])
            else:
                scene.primitives.extend([
                    self._box(f"{base}_body", road.id, Vec3(point.x, point.y, .78), Vec3(4.5, 1.85, 1.15), rotation, "vehicle_body", "vehicle_paint", "roads", collision_enabled=False, instance_key="vehicle_body", metadata=vehicle_metadata),
                    self._box(f"{base}_glass", road.id, Vec3(point.x, point.y, 1.34), Vec3(1.85, 1.42, .38), rotation, "vehicle_glass", "facade_glass_smoke", "roads", collision_enabled=False, instance_key="vehicle_glass", metadata=vehicle_metadata),
                ])
        return vehicle

    def _pedestrian(
        self,
        road,
        point,
        rotation,
        index,
        side,
        scene,
        state: str,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        side_key = "left" if side > 0 else "right"
        base = f"{road.id}_pedestrian_{side_key}_{index:03d}"
        pedestrian_metadata = {
            "road_id": road.id,
            "population_role": "pedestrian",
            "pedestrian_state": state,
            "sidewalk_bound": True,
            **(metadata or {}),
        }
        torso = self._asset(
            f"pedestrian {state}", "person", road.id, point,
            Vec3(.96 if state == "walking" else .65, .70, 1.80),
            rotation, base, scene, semantic="pedestrian_asset",
            metadata=pedestrian_metadata,
        )
        if torso:
            return True
        scene.primitives.extend([
            self._box(f"{base}_body", road.id, Vec3(point.x, point.y, .92), Vec3(.42, .32, 1.35), rotation, "pedestrian_body", "furniture_fabric", "roads", collision_enabled=False, instance_key="pedestrian_body", metadata=pedestrian_metadata),
            self._sphere(f"{base}_head", road.id, Vec3(point.x, point.y, 1.76), Vec3(.28, .28, .28), 0.0, "pedestrian_head", "civic_limestone", "roads", collision_enabled=False, instance_key="pedestrian_head", metadata=pedestrian_metadata),
        ])
        return False

    def _asset(self, query, category, owner, point, size, rotation, base, scene, *, semantic, metadata) -> bool:
        if self.asset_registry is None:
            return False
        required_tokens: tuple[str, ...] = ()
        query_tokens = set(str(query).lower().replace("-", "_").split())
        if category == "vehicle":
            required_tokens = tuple(
                token for token in ("sedan", "suv", "van", "delivery", "bus", "pickup", "ambulance", "fire_truck")
                if token in query_tokens
            )
        elif category == "person":
            if {"walking", "walk"} & query_tokens:
                required_tokens = ("walking", "walk")
            elif {"standing", "stand", "idle"} & query_tokens:
                required_tokens = ("standing", "stand", "idle")
            elif {"cycling", "cycle", "bicycle"} & query_tokens:
                required_tokens = ("cycling", "cycle", "bicycle")
        elif category == "street_tree":
            if "quiver" in query_tokens:
                required_tokens = ("quiver", "tree")
            elif "jacaranda" in query_tokens:
                required_tokens = ("jacaranda", "tree")
            elif "island" in query_tokens:
                required_tokens = ("island", "tree")
            elif "tree" in query_tokens and {"small", "02"}.issubset(query_tokens):
                required_tokens = ("small", "02")
            elif {"pine", "sapling"}.issubset(query_tokens):
                required_tokens = ("pine", "sapling")
            elif "evergreen" in query_tokens:
                required_tokens = ("evergreen", "conifer", "pine", "fir")
            elif "columnar" in query_tokens or "narrow" in query_tokens:
                required_tokens = ("columnar", "narrow", "thin")
            elif "ornamental" in query_tokens:
                required_tokens = ("ornamental", "small_canopy", "twisted", "jacaranda")
            elif "broadleaf" in query_tokens or "deciduous" in query_tokens:
                required_tokens = ("broadleaf", "deciduous", "oak", "common")
        candidates = self.asset_registry.search(
            query,
            category=category,
            limit=64,
            require_geometry=True,
            required_tokens=required_tokens,
        )
        # Quiver Tree is classified as a park_tree in the curated registry,
        # while a gateway road still legitimately requests it as street
        # vegetation. Prefer the cross-context lookup whenever it is asked
        # for; otherwise the broad street-tree result set could dilute the
        # species preference through deterministic variant sampling.
        if category == "street_tree" and "quiver" in query_tokens:
            candidates = self.asset_registry.search(
                query,
                category="park_tree",
                limit=64,
                require_geometry=True,
                required_tokens=("quiver",),
            )
        concrete_species = {
            "jacaranda", "island", "quiver", "pine", "sapling", "small", "02"
        } & query_tokens
        if concrete_species and candidates:
            # Use tokenized IDs/tags (rather than a substring match) so
            # `small` does not accidentally select unrelated `small_canopy`
            # records when an exact Tree Small 02 asset is present.
            def species_tokens(item):
                values = [
                    item[0].asset_id,
                    item[0].metadata.get("source_relative_path", ""),
                    *item[0].tags,
                ]
                return {
                    token
                    for value in values
                    for token in str(value).lower().replace("-", "_").replace("/", "_").split("_")
                    if token
                }
            preferred = []
            if "jacaranda" in query_tokens:
                preferred = [item for item in candidates if "jacaranda" in species_tokens(item)]
            elif "quiver" in query_tokens:
                preferred = [item for item in candidates if "quiver" in species_tokens(item)]
            elif "island" in query_tokens:
                preferred = [item for item in candidates if "island" in species_tokens(item)]
            elif {"small", "02"}.issubset(query_tokens):
                preferred = [item for item in candidates if {"small", "02"}.issubset(species_tokens(item))]
            elif {"pine", "sapling"}.issubset(query_tokens):
                preferred = [item for item in candidates if {"pine", "sapling"}.issubset(species_tokens(item))]
            if preferred:
                candidates = preferred
        if not candidates:
            return False
        if category in {"street_tree", "park_tree", "shrub", "plant"}:
            # Keep legacy stylized packs in the registry for compatibility,
            # but never use their simple cyan/low-poly proxies in the
            # presentation streetscape when a textured alternative exists.
            realistic = [
                item for item in candidates
                if str(item[0].metadata.get("style", "")).lower()
                not in {"stylized_low_poly", "stylized_pbr"}
            ]
            # If this subtype has no realistic candidate, return failure so
            # the caller can try a compatible PBR fallback instead of using a
            # conspicuous low-poly proxy.
            candidates = realistic
        if category == "street_tree":
            # Kenney's `tree_blocks` models are intentionally blocky test
            # assets; they create conspicuous green cubes beside roads. Keep
            # them available in the registry, but never select them for the
            # presentation streetscape.
            candidates = [
                item for item in candidates
                if "blocks" not in {
                    str(item[0].asset_id).lower(),
                    str(item[0].metadata.get("source_relative_path", "")).lower(),
                    *[str(tag).lower() for tag in item[0].tags],
                }
            ]
            if not {"fall", "autumn"} & query_tokens:
                candidates = [
                    item
                    for item in candidates
                    if not any(
                        token in " ".join(
                            (
                                item[0].asset_id,
                                str(item[0].metadata.get("source_relative_path", "")),
                                *item[0].tags,
                            )
                        ).lower()
                        for token in ("fall", "autumn")
                    )
                ]
            if "palm" not in query_tokens:
                candidates = [
                    item
                    for item in candidates
                    if "palm" not in " ".join(
                        (
                            item[0].asset_id,
                            str(item[0].metadata.get("source_relative_path", "")),
                            *item[0].tags,
                        )
                    ).lower()
                ]
            if not candidates:
                return False
        record = choose_asset_variant(
            candidates,
            f"{base}|{query}",
            # Jacaranda is a deliberately detailed hero species (the
            # curated 1K model is just under 4M triangles). Keep the normal
            # street-tree guard for other assets, but do not silently replace
            # this explicit preference with an unrelated broadleaf fallback.
            max_triangle_count=(4_000_000 if "jacaranda" in query_tokens else 2_500_000),
            premium_probability=0.90,
        )
        if record is None:
            return False
        if not record.geometry_path:
            return False
        material = record.material_id or "street_furniture"
        if material not in {item.id for item in scene.materials}:
            material = "street_furniture"
        size = fit_outdoor_asset(record, size)
        rotation += outdoor_asset_yaw_offset(record)
        if record.metadata.get("face_road") and metadata.get("side") == "left":
            rotation += 180.0
        scene.primitives.append(
            self._mesh(
                f"{base}_mesh", owner, Vec3(point.x, point.y, size.z / 2 - outdoor_asset_ground_offset(record, size)), size,
                rotation, semantic, material, "roads", collision_enabled=False,
                instance_key=f"asset_{record.asset_id}", metadata={
                    **metadata, "asset_id": record.asset_id, "asset_category": record.category,
                    "asset_source": record.source, "asset_license": record.license_id,
                    "asset_geometry_path": str(self.asset_registry.resolve_path(record.geometry_path)),
                    "outdoor_slot": record.metadata.get("outdoor_slot"),
                    "resolved_asset": True,
                },
            )
        )
        return True

    @staticmethod
    def _rotation(frame: _Frame | None, point: Point2D | None = None) -> float:
        if frame is None:
            return 0.0
        if point is not None and frame.path is not None:
            return frame.path.heading(frame.path.project(point).distance)
        return math.degrees(math.atan2(frame.uy, frame.ux))

    @staticmethod
    def _box(primitive_id, owner_id, point, size, rotation, semantic, material, layer, *, collision_enabled=False, instance_key="unit_box", metadata=None):
        center = point if isinstance(point, Vec3) else Vec3(point.x, point.y, size.z / 2)
        return GeometryPrimitive(primitive_id, owner_id, "box", center, size, rotation, semantic, material, layer, collision_enabled=collision_enabled, instance_key=instance_key, metadata=metadata or {})

    @staticmethod
    def _mesh(primitive_id, owner_id, point, size, rotation, semantic, material, layer, *, collision_enabled=False, instance_key="asset_mesh", metadata=None):
        center = point if isinstance(point, Vec3) else Vec3(point.x, point.y, size.z / 2)
        return GeometryPrimitive(primitive_id, owner_id, "mesh", center, size, rotation, semantic, material, layer, collision_enabled=collision_enabled, instance_key=instance_key, metadata=metadata or {})

    @staticmethod
    def _cylinder(primitive_id, owner_id, point, size, rotation, semantic, material, layer, *, collision_enabled=False, instance_key="unit_cylinder", metadata=None):
        center = point if isinstance(point, Vec3) else Vec3(point.x, point.y, size.z / 2)
        return GeometryPrimitive(primitive_id, owner_id, "cylinder", center, size, rotation, semantic, material, layer, collision_enabled=collision_enabled, instance_key=instance_key, metadata=metadata or {})

    @staticmethod
    def _sphere(primitive_id, owner_id, point, size, rotation, semantic, material, layer, *, collision_enabled=False, instance_key="unit_sphere", metadata=None):
        center = point if isinstance(point, Vec3) else Vec3(point.x, point.y, size.z / 2)
        return GeometryPrimitive(primitive_id, owner_id, "sphere", center, size, rotation, semantic, material, layer, collision_enabled=collision_enabled, instance_key=instance_key, metadata=metadata or {})


__all__ = ["StreetscapeCompiler"]
