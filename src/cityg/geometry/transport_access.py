"""Bounded entrance/circulation repair for the scripted transport fixture.

Not a general landscape planner: axis-aligned, ground-level north entrances.
An explicit geometry revision opens existing closed collision walls and cuts
flush walking strips through raised paving. It never deletes street objects.
"""
from copy import deepcopy
from dataclasses import asdict, replace
import math
import heapq

from cityg.geometry.model import GeometryPrimitive, Vec3
from cityg.geometry.slab_openings import subtract_openings
from cityg.runtime.transport import Box
from cityg.runtime.transport_planning import primitive_box
from cityg.runtime.mobile_geometry import hit_ids, rect_overlap, xy_bounds
from cityg.schemas import Bounds2D

PAVING = frozenset(('sidewalk', 'curb', 'sidewalk_furnishing_strip', 'sidewalk_frontage_strip',
    'frontage_connector', 'entrance_landing', 'parcel_ground', 'parcel_edge',
    'parcel_surface_patch', 'landscape_surface_patch', 'landscape_path', 'grass',
    'bicycle_lane_surface', 'crosswalk', 'lane_marking', 'parking_bay'))


def exterior_obstacles(scene):
    # Include visible assets even where the original USD disabled collisions.
    return tuple(primitive_box(p) for p in scene.primitives
        if p.semantic_class not in PAVING
        and p.center.z+p.size.z/2 > .02 and p.center.z-p.size.z/2 < 1.8)


def choose_exterior_route(scene, buildings):
    a,b=buildings
    for building in buildings:
        if (abs(building.entrance.y-building.footprint.max_y)>1e-6
            or abs(building.metadata.get('orientation_deg',0))>1e-6):
            raise ValueError('Access retrofit requires axis-aligned north ground entrances')
    obstacles=exterior_obstacles(scene);attempts=[]
    # Design candidates only. Actual slabs are compiled and independently checked later.
    for offset in (2.4,3.2,4.,5.):
        for west in (3.,4.,5.,6.,8.,10.,12.,14.,16.,18.,20.,24.,28.,32.,36.):
            x=min(v.footprint.min_x for v in buildings)-west
            points=[(a.entrance.x,a.entrance.y+offset,.75),(x,a.entrance.y+offset,.75),
                    (x,b.entrance.y+offset,.75),(b.entrance.x,b.entrance.y+offset,.75)]
            hits=set()
            for start,end in zip(points,points[1:]):
                hits.update(hit_ids(Box('path_clearance',start,(1.2,1.2,1.5)),end,obstacles))
            attempts.append({'offset':offset,'west':west,'hits':sorted(hits)})
            if not hits:return points,attempts
    # Detour around individual parked vehicles, planters and trees without
    # moving them. Grid occupancy is conservative world-AABB inflation.
    from shapely.geometry import box as polygon_box, Point
    from shapely.ops import unary_union
    from shapely.prepared import prep
    start=(a.entrance.x,a.entrance.y+2.4,.75)
    end=(b.entrance.x,b.entrance.y+2.4,.75)
    envelope=(min(v.footprint.min_x for v in buildings)-30, end[1]-1,
              max(v.footprint.max_x for v in buildings)+30,start[1]+1)
    local=[xy_bounds(o) for o in obstacles if rect_overlap(xy_bounds(o),envelope)]
    occupied=prep(unary_union([polygon_box(x0-.61,y0-.61,x1+.61,y1+.61) for x0,y0,x1,y1 in local]))
    step=.4
    def point(k):return (start[0]+k[0]*step,start[1]+k[1]*step,.75)
    def free(p):return (envelope[0]<=p[0]<=envelope[2] and envelope[1]<=p[1]<=envelope[3]
                        and not occupied.intersects(Point(p[:2])))
    if not free(start) or not free(end):raise ValueError('Exterior route endpoint occupied')
    goal=(0,round((end[1]-start[1])/step));queue=[(0.,(0,0))];cost={(0,0):0};parents={}
    while queue and len(cost)<150000:
        _,k=heapq.heappop(queue)
        if k==goal:
            keys=[k]
            while keys[-1]!=(0,0):keys.append(parents[keys[-1]])
            raw=[point(v) for v in reversed(keys)]+[end]
            route=[raw[0]]
            for i in range(1,len(raw)-1):
                before=raw[i-1];p=raw[i];after=raw[i+1]
                if abs((p[0]-before[0])*(after[1]-p[1])-(p[1]-before[1])*(after[0]-p[0]))>1e-7:
                    route.append(p)
            route.append(end)
            if any(hit_ids(Box('path',u,(1.2,1.2,1.5)),v,obstacles) for u,v in zip(route,route[1:])):
                raise ValueError('Grid route failed continuous clearance')
            attempts.append({'planner':'bounded_cardinal_astar','expanded':len(cost),'hits':[]})
            return route,attempts
        for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
            q=(k[0]+dx,k[1]+dy);g=cost[k]+1
            if g>=cost.get(q,math.inf) or not free(point(q)):continue
            parents[q]=k;cost[q]=g
            heapq.heappush(queue,(g+abs(q[0]-goal[0])+abs(q[1]-goal[1]),q))
    raise ValueError('Exterior detour exhausted; no landscape asset was removed')


def compile_transport_access(city, previous, building_ids):
    buildings=[next(b for b in city.iter_buildings() if b.id==bid) for bid in building_ids]
    if any(b.floors[0].elevation_m!=0 for b in buildings):raise ValueError('Ground level must be zero')
    points,attempts=choose_exterior_route(previous,buildings)
    scene=deepcopy(previous);removed=[];added=[];openings=[]
    for b in buildings:
        door=next(p for p in scene.primitives if p.owner_id==f'{b.floors[0].id}_entrance' and p.semantic_class=='door')
        width=door.metadata['aperture_size_m'][0];height=door.metadata['aperture_size_m'][2]
        openings.append({'building_id':b.id,'door_id':door.id,'width':width,'height':height})
        result=[]
        for p in scene.primitives:
            # The decorative GLB has a closed leaf too; replace that representation
            # with the existing articulated doorway, never retain duplicate leaves.
            is_frame=(p.layer_id==f'shell:{b.id}' and p.semantic_class in
                      ('facade_asset_entrance','entrance_door_core')
                      and abs(p.center.x-b.entrance.x)<.1 and abs(p.center.y-b.entrance.y)<.4)
            is_wall=(p.id==f'{b.floors[0].id}_wall_north')
            is_band=(p.semantic_class=='facade_ground_band' and p.layer_id==f'shell:{b.id}'
                     and abs(p.center.y-b.entrance.y)<.2 and p.center.z<1)
            if is_frame:removed.append(p);continue
            if not (is_wall or is_band):result.append(p);continue
            removed.append(p);x0=p.center.x-p.size.x/2;x1=p.center.x+p.size.x/2
            z0=p.center.z-p.size.z/2;z1=p.center.z+p.size.z/2
            lo=b.entrance.x-width/2;hi=b.entrance.x+width/2
            parts=[(x0,lo,z0,z1),(hi,x1,z0,z1)]
            if is_wall:parts.append((lo,hi,height,z1))
            for i,(left,right,bottom,top) in enumerate(parts):
                if right<=left or top<=bottom:continue
                q=replace(p,id=p.id+f'__access_{i}',center=Vec3((left+right)/2,p.center.y,(bottom+top)/2),
                          size=Vec3(right-left,p.size.y,top-bottom))
                result.append(q);added.append(q)
        scene.primitives=result
    # Cut a finite flush path, including entry thresholds. It does not cover the city
    # with an invisible floor, nor remove trees/furniture to manufacture a pass.
    a,b=buildings
    route=[(a.entrance.x,a.entrance.y-1.2,.75),*points,(b.entrance.x,b.entrance.y-1.2,.75)]
    strips=[]
    for start,end in zip(route,route[1:]):
        strips.append(Bounds2D(min(start[0],end[0])-.55,min(start[1],end[1])-.55,
                              max(start[0],end[0])+.55,max(start[1],end[1])+.55))
    for building,opening in zip(buildings,openings):
        width=opening['width'];x,y=building.entrance.x,building.entrance.y
        # Preserve a flush landing over the entire outward door sweep, not
        # only under the robot centerline. Raised paving must not block a leaf.
        strips.append(Bounds2D(x-width/2-.12,y-.55,x+width/2+.12,y+width+.2))
    # Parcel skins were originally drawn beneath buildings. They must not
    # protrude above the ground-floor slab or close the new elevator pit.
    paving_cuts=[*strips,*(b.footprint for b in buildings)]
    result=[]
    for p in scene.primitives:
        if p.semantic_class not in PAVING or p.center.z+p.size.z/2<=0:
            result.append(p);continue
        box=primitive_box(p);outer=Bounds2D(*xy_bounds(box))
        if not any(outer.overlaps_area(h) for h in paving_cuts):result.append(p);continue
        if p.primitive_type!='box' or abs(p.rotation_z_deg%90)>1e-6:
            raise ValueError(f'Cannot clip nonrectangular paving safely: {p.id}')
        removed.append(p)
        for i,part in enumerate(subtract_openings(outer,paving_cuts)):
            q=replace(p,id=p.id+f'__access_{i}',center=Vec3(part.center.x,part.center.y,p.center.z),
                      size=Vec3(part.width,part.depth,p.size.z),rotation_z_deg=0.)
            result.append(q);added.append(q)
    layer=next(p.layer_id for p in previous.primitives if p.semantic_class=='city_ground')
    for i,h in enumerate(strips):
        q=GeometryPrimitive(f'transport_walkway_{i:02d}',city.id,'box',
            Vec3(h.center.x,h.center.y,-.05),Vec3(h.width,h.depth,.1),0.,
            'transport_walkway','concrete',layer,collision_enabled=True,
            metadata={'transport_access_version':1,'surface_z_m':0.,'route_segment':i})
        result.append(q);added.append(q)
    scene.primitives=result
    receipt={'scope':'finite_flush_pedestrian_connection_and_existing_entrance_openings',
             'route':route,'design_attempts':attempts,'entrances':openings,
             'removed_primitives':[asdict(p) for p in removed],
             'added_primitive_ids':[p.id for p in added],
             'street_assets_removed':False,'original_mutated':False,
             'path_length_m':sum(math.dist(a,b) for a,b in zip(route,route[1:]))}
    scene.metadata['transport_access']=receipt
    return scene,receipt
