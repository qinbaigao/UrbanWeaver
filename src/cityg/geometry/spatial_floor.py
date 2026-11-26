"""Shared-edge wall compilation for topology-first floor layouts.

Unlike the legacy band compiler, handles T-junctions, unequal room depths and
doors between private rooms. Each shared wall is emitted exactly once, with
ownership limited to its two actual neighbours.
"""
from itertools import combinations
from dataclasses import replace

from cityg.geometry.model import Vec3
from cityg.planning.spatial_layout import shared_boundary
from cityg.schemas import Bounds2D


def compile_spatial_floor(compiler, building, floor, prototype, scene):
    thickness = max(.12, prototype.wall_thickness_m * .75)
    # Explicit reviewed public-space continuities are not dividing walls.
    # Keep a noninteractive door edge in the navigation graph, but no panel.
    open_pairs = {frozenset(pair) for pair in
                  floor.metadata.get('spatial_layout', {}).get('open_boundaries', [])}
    open_doors = set()
    for pair in open_pairs:
        rooms = [r for r in floor.rooms if r.id in pair]
        if len(rooms) != 2 or any(r.function != 'corridor' for r in rooms) or not shared_boundary(rooms[0].bounds, rooms[1].bounds):
            raise ValueError('Open boundaries require two adjacent circulation spaces')
        doors = [d for d in floor.doors if frozenset((d.room_a_id, d.room_b_id)) == pair]
        if not doors or any(d.interactive for d in doors):
            raise ValueError('Open boundaries require a noninteractive navigation connection')
        open_doors.update(d.id for d in doors)
    for index, (a, b) in enumerate(combinations(floor.rooms, 2)):
        if frozenset((a.id, b.id)) in open_pairs:
            continue
        shared = shared_boundary(a.bounds, b.bounds)
        if shared is None:
            continue
        axis, boundary, start, end = shared
        openings = []
        for door in floor.doors:
            if {door.room_a_id, door.room_b_id} != {a.id, b.id}:
                continue
            point = compiler._door_geometry_position(floor, door)
            width = compiler._door_effective_width(floor, door)
            tangent = point.x if axis == "x" else point.y
            openings.append((tangent-width/2, tangent+width/2))
        for segment, (left, right) in enumerate(compiler._segments_excluding(start, end, openings)):
            # Extend junction endpoints by half wall thickness to close seams,
            # but never extend into a door opening.
            lo = left - thickness/2 if abs(left-start) < 1e-6 else left
            hi = right + thickness/2 if abs(right-end) < 1e-6 else right
            center = Vec3((lo+hi)/2, boundary, floor.elevation_m+floor.height_m/2) if axis == "x" else Vec3(boundary, (lo+hi)/2, floor.elevation_m+floor.height_m/2)
            size = Vec3(hi-lo, thickness, floor.height_m) if axis == "x" else Vec3(thickness, hi-lo, floor.height_m)
            scene.primitives.append(compiler._box(
                f"{floor.id}_shared_{index:03d}_{segment:02d}", floor.id,
                center, size, 0.0, "interior_wall", "interior_wall", f"floor:{floor.id}",
                metadata={"room_ids": [a.id, b.id], "wall_role": "spatial_shared_boundary",
                          "canonical_axis": axis, "canonical_boundary": boundary,
                          "canonical_span": [left, right]},
            ))
    # Upper floors can occupy only the realized tower plate, not the podium.
    plate = Bounds2D(min(r.bounds.min_x for r in floor.rooms), min(r.bounds.min_y for r in floor.rooms),
                     max(r.bounds.max_x for r in floor.rooms), max(r.bounds.max_y for r in floor.rooms))
    compiler._compile_room_exterior_boundaries(replace(building, footprint=plate), floor, thickness, scene)
    for door in floor.doors:
        if door.id not in open_doors:
            compiler._compile_door(floor, door, scene)
        else:
            axis = compiler._door_wall_axis(floor, door)
            size = Vec3(door.width_m, .16, .02) if axis == 'horizontal' else Vec3(.16, door.width_m, .02)
            scene.primitives.append(compiler._box(
                f'geom_{door.id}_passage', door.id,
                Vec3(door.position.x, door.position.y, floor.elevation_m+.01),
                size, 0, 'open_passage', 'concrete', f'floor:{floor.id}',
                collision_enabled=False, metadata={'room_ids':[door.room_a_id,door.room_b_id],
                                                   'permanently_open':True}))
    compiler._compile_furniture(floor, scene)
