"""Dependency-free planar paths shared by roads, placement and navigation.

The canonical representation is a polyline in metres. Control curves are sampled
once at planning time; consumers must never reinterpret them as endpoint chords.
"""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from functools import lru_cache
import math
from typing import Iterable

from cityg.schemas import Point2D


@dataclass(frozen=True)
class PathProjection:
    point: Point2D
    distance: float  # arc length from start
    lateral: float  # positive to the left of travel
    separation: float


class PlanarPath2D:
    def __init__(self, points: Iterable[Point2D]):
        clean = []
        for p in points:
            if not math.isfinite(p.x) or not math.isfinite(p.y):
                raise ValueError("Path coordinates must be finite")
            if not clean or math.hypot(p.x - clean[-1].x, p.y - clean[-1].y) > 1e-8:
                clean.append(p)
        if len(clean) < 2:
            raise ValueError("Path needs at least two distinct points")
        self.points = tuple(clean)
        # All sampled vertices, not just the endpoint chord of a curved road.
        self.bounds = (min(p.x for p in clean), min(p.y for p in clean),
                       max(p.x for p in clean), max(p.y for p in clean))
        lengths = [0.0]
        for a, b in zip(clean, clean[1:]):
            lengths.append(lengths[-1] + math.hypot(b.x - a.x, b.y - a.y))
        self.stations = tuple(lengths)
        self.length = lengths[-1]
        self._segments = tuple((a.x, a.y, b.x-a.x, b.y-a.y, lengths[i+1]-lengths[i], lengths[i],
                                min(a.x,b.x),max(a.x,b.x),min(a.y,b.y),max(a.y,b.y))
                               for i,(a,b) in enumerate(zip(clean,clean[1:])))

    def bounds_overlap(self, bounds: tuple[float, float, float, float],
                       padding: float = 0.0) -> bool:
        """Conservative broad phase only; a hit still needs the exact test.

        Bounds use (min_x, min_y, max_x, max_y). Inclusive comparisons and
        outward tolerance retain contacts on the original distance threshold.
        """
        x0, y0, x1, y1 = self.bounds
        a0, b0, a1, b1 = bounds
        pad = padding + 1e-8
        return not (x1 + pad < a0 or a1 + pad < x0 or
                    y1 + pad < b0 or b1 + pad < y0)

    def _index(self, distance: float) -> int:
        return max(0, min(len(self.points) - 2, bisect_right(self.stations, distance) - 1))

    def tangent(self, distance: float) -> Point2D:
        i = self._index(distance)
        a, b = self.points[i:i + 2]
        length = self.stations[i + 1] - self.stations[i]
        return Point2D((b.x - a.x) / length, (b.y - a.y) / length)

    def heading(self, distance: float) -> float:
        t = self.tangent(distance)
        return math.degrees(math.atan2(t.y, t.x))

    def point(self, distance: float, offset: float = 0.0) -> Point2D:
        distance = max(0.0, min(self.length, distance))
        i = self._index(distance)
        t = self.tangent(distance)
        a = self.points[i]
        delta = distance - self.stations[i]
        return Point2D(a.x + t.x * delta - t.y * offset,
                       a.y + t.y * delta + t.x * offset)

    def project(self, p: Point2D) -> PathProjection:
        best_sq, best = float("inf"), None
        for ax,ay,dx,dy,length,station,x0,x1,y0,y1 in self._segments:
            bx, by = max(x0-p.x, 0, p.x-x1), max(y0-p.y, 0, p.y-y1)
            if bx*bx+by*by >= best_sq:
                continue
            delta = max(0.0, min(length, ((p.x-ax)*dx+(p.y-ay)*dy)/length))
            qx, qy = ax+dx*delta/length, ay+dy*delta/length
            squared = (p.x-qx)**2 + (p.y-qy)**2
            if squared < best_sq:
                best_sq = squared
                best = (qx,qy,station+delta,((p.y-qy)*dx-(p.x-qx)*dy)/length)
        qx,qy,distance,lateral = best
        return PathProjection(Point2D(qx,qy),distance,lateral,math.sqrt(best_sq))

    def slice(self, start: float = 0.0, end: float | None = None) -> PlanarPath2D:
        start = max(0.0, start)
        end = min(self.length, self.length if end is None else end)
        if end - start <= 1e-8:
            raise ValueError("Path slice must have positive length")
        return PlanarPath2D([self.point(start), *[p for p, s in zip(self.points, self.stations)
                            if start < s < end], self.point(end)])

    def offset_points(self, offset: float, miter_limit: float = 2.0) -> tuple[Point2D, ...]:
        """Shared offset vertices (bounded miters, no cracks between strips)."""
        result = []
        for i, p in enumerate(self.points):
            after = self.tangent(self.stations[i])
            before = self.tangent(max(0.0, self.stations[i] - 1e-7))
            nx, ny = -(after.y + before.y), after.x + before.x
            norm = math.hypot(nx, ny)
            if norm < 1e-6:
                raise ValueError("Path makes a U-turn; offset is undefined")
            nx, ny = nx / norm, ny / norm
            dot = nx * -after.y + ny * after.x
            scale = min(miter_limit, 1.0 / max(1e-6, dot)) * offset
            result.append(Point2D(p.x + nx * scale, p.y + ny * scale))
        return tuple(result)

    def intersections(self, other: PlanarPath2D, *, include_endpoints=False) -> list[tuple[float, float, Point2D]]:
        """Interior crossings, including crossings at sampling vertices.

        Shared semantic endpoints and collinear overlap are excluded. Distances
        are arc lengths, not fractions of the endpoint chord.
        """
        if not self.bounds_overlap(other.bounds):
            return []
        hits = []
        for i, (a, b) in enumerate(zip(self.points, self.points[1:])):
            rx, ry = b.x - a.x, b.y - a.y
            for j, (c, d) in enumerate(zip(other.points, other.points[1:])):
                if (max(a.x, b.x) < min(c.x, d.x) - 1e-8 or max(c.x, d.x) < min(a.x, b.x) - 1e-8
                    or max(a.y, b.y) < min(c.y, d.y) - 1e-8 or max(c.y, d.y) < min(a.y, b.y) - 1e-8):
                    continue
                sx, sy = d.x - c.x, d.y - c.y
                den = rx * sy - ry * sx
                if abs(den) < 1e-9:
                    continue
                qx, qy = c.x - a.x, c.y - a.y
                t, u = (qx * sy - qy * sx) / den, (qx * ry - qy * rx) / den
                if not (-1e-8 <= t <= 1 + 1e-8 and -1e-8 <= u <= 1 + 1e-8):
                    continue
                s = self.stations[i] + t * (self.stations[i + 1] - self.stations[i])
                v = other.stations[j] + u * (other.stations[j + 1] - other.stations[j])
                if not include_endpoints and not (1e-7 < s < self.length - 1e-7 and 1e-7 < v < other.length - 1e-7):
                    continue
                if not any(abs(s - h[0]) < 1e-6 and abs(v - h[1]) < 1e-6 for h in hits):
                    hits.append((s, v, Point2D(a.x + t * rx, a.y + t * ry)))
        return sorted(hits, key=lambda h: h[0])

    def validate_corridor(self, half_width: float) -> None:
        """Conservative feasibility guard, not a full civil-engineering solver."""
        for a, b, c in zip(self.points, self.points[1:], self.points[2:]):
            ab, bc, ac = math.hypot(b.x-a.x, b.y-a.y), math.hypot(c.x-b.x, c.y-b.y), math.hypot(c.x-a.x, c.y-a.y)
            cross = abs((b.x-a.x)*(c.y-a.y) - (b.y-a.y)*(c.x-a.x))
            dot = (b.x-a.x)*(c.x-b.x) + (b.y-a.y)*(c.y-b.y)
            if dot <= 0:
                raise ValueError("Road path contains a sharp turn; use a wider, smoothly sampled curve")
            if cross > 1e-8 and ab*bc*ac/(2*cross) <= half_width * 1.1:
                raise ValueError("Road bend radius is too small for its carriageway and sidewalks")
        # Adjacent segments share vertices by design; any other crossing or
        # repeated vertex is a loop/overlap and cannot be a single road edge.
        if len(set(self.points)) != len(self.points):
            raise ValueError("Road path revisits a point")
        for i in range(len(self.points) - 2):
            first = PlanarPath2D(self.points[i:i+2])
            remaining = self.points[i+2:]
            if len(remaining) > 1 and first.intersections(PlanarPath2D(remaining), include_endpoints=True):
                raise ValueError("Road path intersects itself")

    def intersects_bounds(self, bounds, padding: float = 0.0) -> bool:
        """Segment/expanded-AABB clipping for conservative occupied-land checks."""
        for a, b in zip(self.points, self.points[1:]):
            enter, leave = 0.0, 1.0
            for origin, delta, low, high in (
                (a.x, b.x-a.x, bounds.min_x-padding, bounds.max_x+padding),
                (a.y, b.y-a.y, bounds.min_y-padding, bounds.max_y+padding),
            ):
                if abs(delta) < 1e-10:
                    if origin < low or origin > high:
                        leave = -1.0
                        break
                else:
                    lo, hi = sorted(((low-origin)/delta, (high-origin)/delta))
                    enter, leave = max(enter, lo), min(leave, hi)
            if enter <= leave:
                return True
        return False


@lru_cache(maxsize=256)
def cached_path(points: tuple[Point2D, ...]) -> PlanarPath2D:
    return PlanarPath2D(points)


class RoadClearanceQuery:
    """Exact minimum distance to carriageway edges for an immutable road snapshot.

    Keep local path objects: scanning more roads than the shared LRU can hold
    otherwise rebuilds every polyline on every landscape placement query.
    AABB distance is only a lower bound; candidate roads use the original exact
    projection and distance calculation. Ties retain input order.
    """

    def __init__(self, roads):
        self.entries = []
        for road in roads:
            points = tuple(road.centerline)
            path = PlanarPath2D(points) if len(points) > 2 else None
            bounds = (min(p.x for p in points), min(p.y for p in points),
                      max(p.x for p in points), max(p.y for p in points))
            self.entries.append((points, path, bounds, road.width_m / 2))

    def __call__(self, point):
        from cityg.ccwp import point_segment_distance
        if not self.entries:
            raise ValueError('min() arg is an empty sequence')
        best = float('inf')
        for points, path, (x0, y0, x1, y1), half_width in self.entries:
            lower = math.hypot(max(x0-point.x, 0, point.x-x1),
                               max(y0-point.y, 0, point.y-y1)) - half_width
            if lower > best + 1e-8:
                continue
            if path is None:
                distance = point_segment_distance(point, points)
            else:
                projection = path.project(point).point
                distance = math.hypot(point.x-projection.x, point.y-projection.y)
            best = min(best, distance-half_width)
        return best


def sample_cubic_bezier(start: Point2D, control1: Point2D, control2: Point2D,
                        end: Point2D, max_step_m: float = 2.0) -> tuple[Point2D, ...]:
    """Bound sample spacing using the derivative; store the result, not the spline."""
    if max_step_m <= 0 or not math.isfinite(max_step_m):
        raise ValueError("max_step_m must be positive and finite")
    controls = (start, control1, control2, end)
    if any(not math.isfinite(p.x) or not math.isfinite(p.y) for p in controls):
        raise ValueError("Control points must be finite")
    derivative_bound = 3 * max(math.hypot(b.x - a.x, b.y - a.y) for a, b in zip(controls, controls[1:]))
    count = max(2, math.ceil(derivative_bound / max_step_m))
    result = []
    for i in range(count + 1):
        t, u = i / count, 1 - i / count
        weights = (u**3, 3*u*u*t, 3*u*t*t, t**3)
        result.append(Point2D(sum(p.x * w for p, w in zip(controls, weights)),
                              sum(p.y * w for p, w in zip(controls, weights))))
    return PlanarPath2D(result).points
