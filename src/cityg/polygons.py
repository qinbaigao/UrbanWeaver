"""Optional GEOS-backed operations for rivers and non-rectangular land parcels.

All consumers share these same polygon definitions. No implicit repair of invalid
input rings: invalid geometry is rejected before it can change topology silently.
"""
from __future__ import annotations

from cityg.schemas import Bounds2D, Point2D


def geos():
    try:
        import shapely
        from shapely import constrained_delaunay_triangles  # requires 2.1 / GEOS 3.10
        return shapely
    except ImportError as exc:
        raise RuntimeError("Polygonal geography requires Shapely >= 2.1: pip install 'cityg[geospatial]'") from exc


def box_shape(bounds):
    s = geos()
    return s.box(bounds.min_x, bounds.min_y, bounds.max_x, bounds.max_y)


def line_shape(points):
    return geos().LineString([(p.x, p.y) for p in points])


def parcel_shape(parcel):
    if not parcel.boundary:
        return box_shape(parcel.bounds)
    return ring_shape(parcel.boundary, parcel.holes)


def ring_shape(boundary, holes=()):
    polygon = geos().Polygon([(p.x, p.y) for p in boundary],
                             [[(p.x, p.y) for p in ring] for ring in holes])
    if polygon.is_empty or not polygon.is_valid or polygon.area <= 1e-8:
        raise ValueError("Invalid polygon boundary or holes")
    return polygon


def polygon_parts(shape):
    if shape.is_empty:
        return []
    if shape.geom_type == "Polygon":
        return [shape] if shape.area > 1e-7 else []
    return [p for item in getattr(shape, "geoms", ()) for p in polygon_parts(item)]


def rings(shape):
    return (tuple(Point2D(x, y) for x, y in list(shape.exterior.coords)[:-1]),
            tuple(tuple(Point2D(x, y) for x, y in list(r.coords)[:-1]) for r in shape.interiors))


def shape_record(shape):
    boundary, holes = rings(shape)
    return {"boundary": [{"x": p.x, "y": p.y} for p in boundary],
            "holes": [[{"x": p.x, "y": p.y} for p in ring] for ring in holes],
            "bounds": dict(zip(("min_x", "min_y", "max_x", "max_y"), shape.bounds))}


def record_shape(record):
    return ring_shape(tuple(Point2D(**p) for p in record["boundary"]),
                      tuple(tuple(Point2D(**p) for p in ring) for ring in record.get("holes", [])))


def river_shape(river, zone="water"):
    radius = river.width_m / 2
    if zone in {"banks", "reserve"}:
        radius += river.bank_width_m
    if zone == "reserve":
        radius += river.setback_m
    return line_shape(river.centerline).buffer(radius, cap_style="flat", join_style="round")


def road_shape(road, extra=0.0):
    return line_shape(road.centerline).buffer(road.width_m/2 + road.sidewalk_width_m + extra,
                                             cap_style="square", join_style="round")


def line_intervals(path, shape):
    """Intersections as arc-length intervals, including multi-crossing rivers."""
    line = line_shape(path.points)
    hit = line.intersection(shape)
    result = []
    def visit(item):
        if item.geom_type == "LineString" and item.length > 1e-6:
            coords = list(item.coords)
            a, b = sorted((line.project(geos().Point(coords[0])), line.project(geos().Point(coords[-1]))))
            result.append((a, b))
        for child in getattr(item, "geoms", ()):
            visit(child)
    visit(hit)
    return sorted(result)


def inscribed_bounds(polygon, min_size=12.0, *, score=None):
    """Deterministic, conservative building envelope; polygon stays canonical.

    Search candidate centres/aspect ratios, binary-expand a rectangle and keep
    only rectangles fully covered by the polygon (including holes/concavity).
    """
    s = geos()
    x0, y0, x1, y1 = polygon.bounds
    centres = [polygon.representative_point(), polygon.centroid]
    centres += [s.Point(x0 + (x1-x0)*fx, y0 + (y1-y0)*fy)
                for fx in (.2, .35, .5, .65, .8) for fy in (.2, .35, .5, .65, .8)]
    best = None
    best_score = None
    for p in centres:
        if not polygon.contains(p):
            continue
        for ratio in (.5, .75, 1.0, 1.5, 2.0, (x1-x0)/max(y1-y0, 1e-6)):
            lo, hi = 0.0, min(x1-x0, (y1-y0)*ratio)/2
            for _ in range(22):
                half = (lo+hi)/2
                rect = s.box(p.x-half, p.y-half/ratio, p.x+half, p.y+half/ratio)
                if polygon.covers(rect):
                    lo = half
                else:
                    hi = half
            width, depth = lo*2*.999, lo*2/ratio*.999
            if min(width, depth) < min_size:
                continue
            bounds = Bounds2D(p.x-width/2, p.y-depth/2, p.x+width/2, p.y+depth/2)
            value = score(bounds) if score is not None else bounds.area
            if best is None or value > best_score:
                best = bounds
                best_score = value
    return best
