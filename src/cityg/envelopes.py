"""Exterior-only, convex floor-ring contracts. No hidden rectangular interiors.

Rings are CCW world-space coordinates at actual floor boundaries. The same
rings drive shell geometry, facade panels, slabs and collision meshes.
"""
from __future__ import annotations

import math

SHAPES = ("rectangle", "chamfered", "trapezoid", "hexagon", "ellipse")
PROFILES = ("straight", "taper", "lean")
ENVELOPE_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "shape": {"type": "string", "enum": list(SHAPES)},
        "profile": {"type": "string", "enum": list(PROFILES)},
        "facade_system": {"type": "string", "enum": ["punched", "curtain_wall"]},
        "top_scale": {"type": "number", "minimum": .55, "maximum": 1},
        "lean_x": {"type": "number", "minimum": -.18, "maximum": .18},
        "lean_y": {"type": "number", "minimum": -.18, "maximum": .18},
        "segments": {"type": "integer", "minimum": 12, "maximum": 64},
    },
}


def validate_envelope(value):
    if not isinstance(value, dict) or set(value) - set(ENVELOPE_SCHEMA["properties"]):
        raise ValueError("invalid exterior envelope fields")
    if not value:
        return
    for key, allowed, default in (("shape", SHAPES, "rectangle"),
                                 ("profile", PROFILES, "straight"),
                                 ("facade_system", ("punched", "curtain_wall"), "punched")):
        if value.get(key, default) not in allowed:
            raise ValueError(f"unsupported envelope {key}")
    for key, low, high, default in (("top_scale", .55, 1, 1),
                                   ("lean_x", -.18, .18, 0), ("lean_y", -.18, .18, 0)):
        v = value.get(key, default)
        if isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v) or not low <= v <= high:
            raise ValueError(f"envelope {key} outside safe range")
    segments = value.get("segments", 32)
    if type(segments) is not int or not 12 <= segments <= 64:
        raise ValueError("ellipse segments must be an integer in 12..64")
    profile = value.get("profile", "straight")
    if profile != "taper" and value.get("top_scale", 1) != 1:
        raise ValueError("top_scale requires taper profile")
    if profile != "lean" and (value.get("lean_x", 0) or value.get("lean_y", 0)):
        raise ValueError("lean offsets require lean profile")


def envelope_config(building):
    value = building.metadata.get("appearance_plan", {}).get("envelope", {})
    validate_envelope(value)
    return value


def _unit_ring(shape, segments):
    if shape == "rectangle":
        return [(-.5, -.5), (.5, -.5), (.5, .5), (-.5, .5)]
    if shape == "trapezoid":
        return [(-.5, -.5), (.5, -.5), (.32, .5), (-.32, .5)]
    if shape == "chamfered":
        return [(-.32, -.5), (.32, -.5), (.5, -.32), (.5, .32),
                (.32, .5), (-.32, .5), (-.5, .32), (-.5, -.32)]
    n = 6 if shape == "hexagon" else segments
    return [(.5 * math.cos(2 * math.pi * i / n), .5 * math.sin(2 * math.pi * i / n))
            for i in range(n)]


def envelope_contract(building):
    config = envelope_config(building)
    if not config:
        return None
    floors = sorted(building.floors, key=lambda f: f.elevation_m)
    if not floors or any(f.height_m <= 0 for f in floors):
        raise ValueError("exterior envelope requires positive floor heights")
    if abs(floors[0].elevation_m) > 1e-6 or any(
        abs(a.elevation_m + a.height_m - b.elevation_m) > 1e-6
        for a, b in zip(floors, floors[1:])):
        raise ValueError("exterior envelope requires contiguous ground-based floors")
    height = floors[-1].elevation_m + floors[-1].height_m
    bounds = building.footprint
    angle = math.radians(float(building.metadata.get("orientation_deg", 0)))
    c, s = math.cos(angle), math.sin(angle)
    ring = _unit_ring(config.get("shape", "rectangle"), config.get("segments", 32))
    profile = config.get("profile", "straight")
    top_scale = config.get("top_scale", .72) if profile == "taper" else 1
    lean_x = config.get("lean_x", .10) if profile == "lean" else 0
    lean_y = config.get("lean_y", 0) if profile == "lean" else 0

    def local(t):
        scale = 1 + (top_scale - 1) * t
        return [((x * scale + lean_x * t) * bounds.width,
                 (y * scale + lean_y * t) * bounds.depth) for x, y in ring]

    endpoints = [(c*x-s*y, s*x+c*y) for t in (0, 1) for x, y in local(t)]
    # Fit the entire loft, including upper lean, not just the ground footprint.
    fit = min(bounds.width * .44 / max(abs(x) for x, y in endpoints),
              bounds.depth * .44 / max(abs(y) for x, y in endpoints))
    elevations = [f.elevation_m for f in floors] + [height]
    rings = []
    for z in elevations:
        rings.append([[bounds.center.x + fit * (c*x-s*y),
                       bounds.center.y + fit * (s*x+c*y), z]
                      for x, y in local(z / height)])
    entries = []
    for edge, a in enumerate(rings[0]):
        b = rings[0][(edge+1)%len(ring)]
        count = max(1, min(32, round(math.dist(a,b)/(2.6 if config.get("facade_system") == "curtain_wall" else 3.4))))
        for bay in range(count):
            point = [x+(y-x)*(bay+.5)/count for x,y in zip(a,b)]
            entries.append((math.hypot(point[0]-building.entrance.x, point[1]-building.entrance.y),edge,bay,point))
    _, edge, bay, point = min(entries)
    return {"version": "cityg.exterior_envelope.v1", "config": dict(config),
            "scope": "exterior_only", "interior_supported": False,
            "rings": rings, "floor_ids": [f.id for f in floors],
            "height_m": height, "fit_scale": fit,
            "ring_vertex_count": len(ring),
            "entrance": {"edge": edge, "bay": bay, "point": point, "interactive": False},
            "floor_plates": [{"floor_id": f.id, "level": f.level, "elevation_m": f.elevation_m,
                              "boundary": rings[i], "ceiling_boundary": rings[i+1]}
                             for i,f in enumerate(floors)]}
