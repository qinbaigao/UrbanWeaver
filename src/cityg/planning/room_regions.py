"""Opt-in normalized functional regions and metric-width clear reservations.

These are layout constraints, not walls, fire exits or building-code approval.
"""
import math
from cityg.schemas import Bounds2D


def validate_uv(values):
    if (not isinstance(values, (list, tuple)) or len(values) != 4
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in values)
            or not (0 <= values[0] < values[2] <= 1 and 0 <= values[1] < values[3] <= 1)):
        raise ValueError('bounds_uv must be a nonempty normalized rectangle')


def region_bounds(bounds, values):
    validate_uv(values)
    return Bounds2D(bounds.min_x+values[0]*bounds.width, bounds.min_y+values[1]*bounds.depth,
                    bounds.min_x+values[2]*bounds.width, bounds.min_y+values[3]*bounds.depth)


def reserved_bounds(bounds, reservations):
    result = []
    for reservation in reservations:
        area = region_bounds(bounds, reservation['bounds_uv'])
        if min(area.width, area.depth) + 1e-6 < reservation['min_width_m']:
            raise ValueError('Room cannot preserve the declared aisle width: '+reservation['id'])
        result.append(area)
    return result
