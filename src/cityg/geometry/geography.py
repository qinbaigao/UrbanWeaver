"""Polygonal ground, recessed river channels and explicit same-grade bridges."""
from __future__ import annotations

import math
from dataclasses import replace

from cityg.geometry.model import MaterialSpec
from cityg.geometry.path_mesh import inline_mesh, path_slab
from cityg.paths import PlanarPath2D
from cityg.polygons import (box_shape, geos, line_shape, parcel_shape, polygon_parts,
                            record_shape, river_shape, road_shape)
from cityg.schemas import Point2D


def polygon_mesh(primitive_id, owner_id, shape, top_z, thickness, semantic, material,
                 *, collision=False, metadata=None, layer="roads"):
    """Closed, constrained triangulation, preserving concavity and holes."""
    s = geos()
    parts = polygon_parts(shape)
    if not parts:
        return None
    vertices, faces = [], []
    for polygon in parts:
        polygon = s.orient_polygons(polygon)
        coords, lookup = [], {}
        def index(xy):
            xy = tuple(xy[:2])
            if xy not in lookup:
                lookup[xy] = len(coords)
                coords.append(xy)
            return lookup[xy]
        triangles = []
        for tri in s.constrained_delaunay_triangles(polygon).geoms:
            a, b, c = list(tri.exterior.coords)[:3]
            if (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0]) < 0:
                b, c = c, b
            triangles.append((index(a), index(b), index(c)))
        walls = []
        for ring in (polygon.exterior, *polygon.interiors):
            values = list(ring.coords)
            # Boolean unions can retain a repeated ring coordinate. Extruding
            # its zero-length edge creates faces with repeated vertex indices.
            # Keep the polygon and its holes intact, but omit that empty wall.
            walls.extend((index(a), index(b)) for a, b in zip(values, values[1:]) if a != b)
        base, count = len(vertices), len(coords)
        for delta in (-thickness, 0.0):
            vertices.extend((x, y, (top_z(x, y) if callable(top_z) else top_z) + delta) for x, y in coords)
        for a, b, c in triangles:
            faces.extend(((base+c, base+b, base+a), (base+count+a, base+count+b, base+count+c)))
        for a, b in walls:
            faces.extend(((base+a, base+b, base+count+b), (base+a, base+count+b, base+count+a)))
    result = inline_mesh(primitive_id, owner_id, vertices, faces, semantic, material,
                         collision=collision, metadata={**(metadata or {}), "polygon_clipped": True})
    result.layer_id = layer
    return result


def primitive_footprint(primitive):
    s = geos()
    if primitive.primitive_type == "path_mesh":
        vertices = primitive.metadata["mesh_vertices"]
        points = [(p[0]*primitive.size.x+primitive.center.x, p[1]*primitive.size.y+primitive.center.y) for p in vertices]
        triangles = [s.Polygon([points[i] for i in tri]) for tri in primitive.metadata["mesh_triangles"]]
        return s.union_all([p for p in triangles if p.area > 1e-9])
    angle = math.radians(primitive.rotation_z_deg)
    co, si = math.cos(angle), math.sin(angle)
    return s.Polygon([(primitive.center.x + x*co - y*si, primitive.center.y + x*si + y*co)
                      for x, y in ((-primitive.size.x/2, -primitive.size.y/2),
                                   (primitive.size.x/2, -primitive.size.y/2),
                                   (primitive.size.x/2, primitive.size.y/2),
                                   (-primitive.size.x/2, primitive.size.y/2))])


def bridge_shape(bridge, road):
    path = PlanarPath2D(road.centerline).slice(bridge.start_m, bridge.end_m)
    return line_shape(path.points).buffer(road.width_m/2+road.sidewalk_width_m+.35,
                                          cap_style="flat", join_style="round")


def constrain_ground_geometry(city, scene):
    """One polygon mask for all parcel dressing; no decorations outside dry land.

    Thin ground surfaces are clipped; rigid props are retained only when their
    entire placement envelope fits. Clipping never deforms furniture/GLBs.
    """
    s = geos()
    parcels = {p.id: parcel_shape(p) for p in city.iter_parcels() if p.boundary}
    landscape = {r["id"]: record_shape(r) for r in city.metadata.get("landscape_sites", []) if r.get("boundary")}
    banks = s.union_all([river_shape(r, "banks") for r in city.rivers])
    roads = {r.id: r for r in city.road_network.segments}
    decks = s.union_all([bridge_shape(b, roads[b.road_id]) for b in city.bridges])
    kept, removed, clipped = [], 0, 0
    for primitive in scene.primitives:
        mask = parcels.get(primitive.owner_id)
        if mask is None:
            mask = landscape.get(primitive.metadata.get("landscape_site"))
        if primitive.semantic_class == "city_ground" and city.rivers:
            dry = box_shape(city.bounds).difference(banks)
            result = polygon_mesh(primitive.id, city.id, dry, -.02, .18,
                "city_ground", primitive.material_id, collision=True,
                metadata={"ground_plane": True, "channel_cut": True})
            if result:
                kept.append(result)
            clipped += 1
            continue
        # Regenerate the border on the actual polygon instead of clipping four
        # old AABB edges (which would omit the curved waterfront boundary).
        if mask is not None and primitive.semantic_class == "parcel_edge":
            if primitive.metadata.get("edge_side") != "south":
                continue
            border = mask.difference(mask.buffer(-.18))
            result = polygon_mesh(primitive.id, primitive.owner_id, border, .07, .07,
                primitive.semantic_class, primitive.material_id, metadata=primitive.metadata)
            if result:
                kept.append(result)
            continue
        if mask is not None:
            footprint = primitive_footprint(primitive)
            if primitive.primitive_type in {"box", "path_mesh"} and primitive.size.z <= .20:
                intersection = footprint.intersection(mask)
                result = polygon_mesh(primitive.id, primitive.owner_id, intersection,
                    primitive.center.z+primitive.size.z/2, primitive.size.z, primitive.semantic_class,
                    primitive.material_id, collision=primitive.collision_enabled, metadata=primitive.metadata,
                    layer=primitive.layer_id)
                if result:
                    kept.append(result)
                    clipped += 1
                else:
                    removed += 1
                continue
            if not mask.covers(footprint):
                removed += 1
                continue
        if city.rivers and primitive.owner_id in roads:
            # Road/sidewalk/paint are the deck's upper layers. Small street
            # furnishings may stay on the bridge, but never median trees or
            # soil planting. Road footprints were checked by the city validator.
            structural = primitive.semantic_class in {"road_surface", "road_median", "sidewalk", "curb", "curb_ramp",
                "lane_marking", "crosswalk", "stop_line", "bicycle_lane_surface"}
            if not structural:
                footprint = primitive_footprint(primitive)
                if footprint.intersects(banks):
                    planting = any(word in primitive.semantic_class for word in ("tree", "shrub", "planter", "planting"))
                    if planting or not decks.covers(footprint):
                        removed += 1
                        continue
        kept.append(primitive)
    scene.primitives = kept
    scene.metadata["geography_clipping"] = {"clipped_surface_count": clipped, "removed_out_of_bounds_props": removed}


def compile_water_and_bridges(city, scene):
    s = geos()
    materials = [MaterialSpec("river_water", (.055, .28, .34), roughness=.20, metallic=.12),
                 MaterialSpec("river_bed", (.13, .16, .12), roughness=1),
                 MaterialSpec("river_bank", (.40, .43, .30), roughness=.94),
                 MaterialSpec("riparian_green", (.24, .34, .19), roughness=.95),
                 MaterialSpec("bridge_structure", (.40, .43, .45), roughness=.83),
                 MaterialSpec("bridge_railing", (.16, .21, .22), roughness=.40, metallic=.60)]
    present = {m.id for m in scene.materials}
    scene.materials.extend(m for m in materials if m.id not in present)
    extent = box_shape(city.bounds)
    road_areas = s.union_all([road_shape(r, .25) for r in city.road_network.segments])
    def add(item):
        if item is not None:
            scene.primitives.append(item)
    for river in city.rivers:
        water = river_shape(river).intersection(extent)
        banks = river_shape(river, "banks").intersection(extent)
        reserve = river_shape(river, "reserve").intersection(extent)
        path = PlanarPath2D(river.centerline)
        metadata = {"river_id": river.id, "fluid_simulation": False}
        add(polygon_mesh(f"{river.id}_bed", river.id, banks, river.bed_elevation_m, .3,
                         "river_bed", "river_bed", collision=True, metadata=metadata))
        add(polygon_mesh(f"{river.id}_water", river.id, water, river.water_elevation_m, .025,
                         "river_water", "river_water", metadata=metadata))
        def bank_height(x, y):
            fraction = min(1, max(0, (path.project(Point2D(x, y)).separation-river.width_m/2)/river.bank_width_m))
            return river.water_elevation_m-.08 + fraction*(-.02-river.water_elevation_m+.08)
        add(polygon_mesh(f"{river.id}_banks", river.id, banks.difference(water), bank_height, .18,
                         "river_bank", "river_bank", collision=True, metadata=metadata))
        promenade = banks.buffer(3).difference(banks).intersection(extent).difference(road_areas)
        add(polygon_mesh(f"{river.id}_promenade", river.id, promenade, .04, .12,
                         "river_promenade", "sidewalk", collision=True, metadata=metadata))
        green = reserve.difference(banks.buffer(3)).difference(road_areas)
        add(polygon_mesh(f"{river.id}_green", river.id, green, .015, .04,
                         "riparian_green", "riparian_green", metadata=metadata))
    roads = {r.id: r for r in city.road_network.segments}
    for bridge in city.bridges:
        road = roads[bridge.road_id]
        path = PlanarPath2D(road.centerline).slice(bridge.start_m, bridge.end_m)
        width = road.width_m + road.sidewalk_width_m*2 + .6
        metadata = {"bridge_id": bridge.id, "road_id": road.id, "river_id": bridge.river_id,
                    "min_clearance_m": bridge.min_clearance_m, "grade": "same_as_road"}
        scene.primitives.append(path_slab(f"{bridge.id}_deck", bridge.id, path, width,
            -(.20+bridge.structural_depth_m)/2, bridge.structural_depth_m-.20,
            "bridge_deck", "bridge_structure", metadata=metadata))
        for side, sign in (("left", 1), ("right", -1)):
            scene.primitives.append(path_slab(f"{bridge.id}_{side}_parapet", bridge.id, path,
                .22, .30, .6, "bridge_parapet", "bridge_structure", offset=sign*(width/2-.11), metadata=metadata))
            scene.primitives.append(path_slab(f"{bridge.id}_{side}_rail", bridge.id, path,
                .12, 1.10, .12, "bridge_railing", "bridge_railing", offset=sign*(width/2-.11), metadata=metadata))
            count = max(2, math.ceil(path.length/2))
            for i in range(count+1):
                p = path.point(path.length*i/count, sign*(width/2-.11))
                from cityg.geometry.model import GeometryPrimitive, Vec3
                scene.primitives.append(GeometryPrimitive(f"{bridge.id}_{side}_post_{i:03d}", bridge.id,
                    "box", Vec3(p.x,p.y,.80), Vec3(.1,.1,.60), path.heading(path.length*i/count),
                    "bridge_railing", "bridge_railing", "roads", metadata=metadata))
        for name, a, b in (("start", 0, min(1.2,path.length)), ("end", max(0,path.length-1.2), path.length)):
            scene.primitives.append(path_slab(f"{bridge.id}_abutment_{name}", bridge.id, path.slice(a,b),
                width, -1.5, 2.6, "bridge_abutment", "bridge_structure", metadata=metadata))
