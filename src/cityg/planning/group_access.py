"""Explicit pedestrian access for buildings behind a shared parcel frontage."""
import math
from shapely.ops import nearest_points
from cityg.geometry.site_routing import route_in_polygon
from cityg.polygons import box_shape, geos, parcel_shape, road_shape, river_shape


def plan_group_access(city):
    s = geos()
    roads = s.union_all([road_shape(r,.15) for r in city.road_network.segments])
    for parcel in city.iter_parcels():
        if not any(b.metadata.get('residential_group') for b in parcel.buildings): continue
        buildings = s.union_all([box_shape(b.footprint) for b in parcel.buildings])
        free = parcel_shape(parcel).buffer(-.1).difference(buildings.buffer(.35))
        core = free.buffer(-1.3); candidates = []
        for road in city.road_network.segments:
            if road.sidewalk_width_m <= 0: continue
            sidewalk = road_shape(road,road.sidewalk_width_m).difference(road_shape(road,.3))
            a, root = nearest_points(sidewalk,core)
            link = s.LineString([(a.x,a.y),(root.x,root.y)]).buffer(1.1)
            if a.distance(root)<=20 and link.intersection(roads.union(buildings)).area<.01:
                candidates.append((a.distance(root),road.id,a,root))
        if not candidates: raise ValueError('No group sidewalk connection: '+parcel.id)
        _, rid, a, root = min(candidates,key=lambda c:(c[0],c[1]))
        # One side spine and one front walk per row, not a fan of independent
        # shortest paths across every garden. GEOS still checks the full width.
        spine_x = (min(b.footprint.min_x for b in parcel.buildings)-5.
                   if root.x <= parcel.bounds.center.x else
                   max(b.footprint.max_x for b in parcel.buildings)+5.)
        for b in parcel.buildings:
            end = (b.entrance.x,b.entrance.y-2.)
            preferred = [(root.x,root.y),(spine_x,root.y),(spine_x,end[1]),end]
            path = preferred if free.covers(s.LineString(preferred).buffer(1.03)) else None
            if path is None:
                join = route_in_polygon((root.x,root.y),(spine_x,end[1]),free,width=2.,budget=16000)
                if join and free.covers(s.LineString([join[-1],end]).buffer(1.03)):
                    path = join+[end]
            if path is None:
                path = route_in_polygon((root.x,root.y),end,free,width=2.,budget=16000)
            if not path: raise ValueError('No group entrance route: '+b.id)
            points = [[a.x,a.y],*[list(p) for p in path],[b.entrance.x,b.entrance.y]]
            points = [p for i,p in enumerate(points) if i==0 or math.dist(points[i-1],p)>1e-6]
            b.metadata['group_access'] = {'road_id':rid, 'parcel_id':parcel.id,'width_m':2.,
                'points':points,'length_m':sum(math.dist(a,c) for a,c in zip(points,points[1:]))}


def group_access_valid(city, building):
    """Do not waive the ordinary access rule without checked route evidence."""
    s = geos(); access = building.metadata.get('group_access',{})
    try:
        parcel = next(p for p in city.iter_parcels() if p.id == access['parcel_id'] and building in p.buildings)
        road = next(r for r in city.road_network.segments if r.id == access['road_id'])
        points = access['points']; width = float(access['width_m'])
        line = s.LineString(points)
        if len(points)<3 or not 1.8<=width<=3 or not math.isfinite(line.length): return False
        if abs(line.length-access['length_m'])>1e-5 or line.length>2*(parcel.bounds.width+parcel.bounds.depth): return False
        if math.dist(points[-1],(building.entrance.x,building.entrance.y))>1e-5: return False
        # South-facing group entrances need an outward final approach, not a shortcut through the house.
        if points[-2][1]>=points[-1][1] or abs(points[-2][0]-points[-1][0])>1e-5: return False
        sidewalk = road_shape(road,road.sidewalk_width_m).difference(road_shape(road,.25))
        if not sidewalk.buffer(.01).covers(s.Point(points[0])): return False
        surface = line.buffer(width/2,cap_style='flat',join_style='round')
        permitted = parcel_shape(parcel).buffer(20).intersection(box_shape(city.bounds))
        if not permitted.covers(surface): return False
        obstacles = s.union_all([box_shape(b.footprint) for b in city.iter_buildings()]+
            [road_shape(r,.1) for r in city.road_network.segments]+
            [river_shape(r,'reserve') for r in city.rivers])
        return surface.intersection(obstacles).area<1e-5
    except (KeyError,TypeError,ValueError,StopIteration):
        return False
