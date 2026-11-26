"""Conservative fixed-yaw mobile occupancy, floor support and door rotation.

Translation is swept continuously. Revolving-door sweeps use angular intervals
inflated by a bound on corner displacement, not just endpoint snapshots.
"""
from dataclasses import replace
import heapq
import math

from cityg.runtime.transport import Box
from cityg.runtime.transport_validation import axes, radius, sweep_hit
from cityg.geometry.door_kinematics import local_hinge


def inflated(box, margin):
    return replace(box, size=(box.size[0]+2*margin, box.size[1]+2*margin, box.size[2]))


def xy_bounds(box):
    rx,ry=radius(box,(1,0,0)),radius(box,(0,1,0))
    return (box.center[0]-rx,box.center[1]-ry,box.center[0]+rx,box.center[1]+ry)


def segment_bounds(box, end):
    lo=xy_bounds(box);dx,dy=end[0]-box.center[0],end[1]-box.center[1]
    return (lo[0]+min(0,dx),lo[1]+min(0,dy),lo[2]+max(0,dx),lo[3]+max(0,dy))


def rect_overlap(a,b):
    return not (a[2]<b[0] or b[2]<a[0] or a[3]<b[1] or b[3]<a[1])


def supported_sweep(box, end, slabs):
    """Require the entire swept XY bounding rectangle covered by slab union.

    This can conservatively reject diagonal routes beside a hole, never bridge
    one. Slabs are actual axis-aligned collision slabs, not visual floor skins.
    """
    if any(abs(s.yaw%90)>1e-7 for s in slabs):
        raise ValueError('Rotated slabs need polygonal support checking')
    rect=segment_bounds(box,end)
    bottom=box.center[2]-box.size[2]/2
    if abs(end[2]-box.center[2])>1e-7:return False
    patches=[xy_bounds(s) for s in slabs if abs(s.center[2]+s.size[2]/2-bottom)<1e-5]
    patches=[p for p in patches if rect_overlap(rect,p)]
    cuts=sorted({rect[0],rect[2],*(max(rect[0],min(rect[2],x)) for p in patches for x in (p[0],p[2]))})
    for a,b in zip(cuts,cuts[1:]):
        if b-a<1e-9:continue
        middle=(a+b)/2
        intervals=sorted((p[1],p[3]) for p in patches if p[0]-1e-7<=middle<=p[2]+1e-7)
        covered=rect[1]
        for low,high in intervals:
            if low>covered+1e-7:break
            covered=max(covered,high)
        if covered<rect[3]-1e-7:return False
    return bool(patches)


def hit_ids(box,end,obstacles):
    envelope=segment_bounds(box,end)
    return [o.id for o in obstacles
            if rect_overlap(envelope,xy_bounds(o)) and sweep_hit(box,end,o)]


def door_pose(closed,angle_deg,hinge_local_m=None):
    """Same explicit/legacy hinge convention as UsdaWriter."""
    local=local_hinge(closed.size,{'hinge_local_m':hinge_local_m})
    yaw=math.radians(closed.yaw);c,s=math.cos(yaw),math.sin(yaw)
    hinge=(closed.center[0]+c*local[0]-s*local[1],closed.center[1]+s*local[0]+c*local[1])
    angle=math.radians(closed.yaw+angle_deg);c,s=math.cos(angle),math.sin(angle)
    center=(hinge[0]-c*local[0]+s*local[1],hinge[1]-s*local[0]-c*local[1],closed.center[2])
    return replace(closed,center=center,yaw=closed.yaw+angle_deg)


def door_sweep_hit(closed,start_angle,end_angle,stationary,hinge_local_m=None):
    steps=max(1,math.ceil(abs(end_angle-start_angle)))
    local=local_hinge(closed.size,{'hinge_local_m':hinge_local_m})
    reach=math.hypot(closed.size[0]/2+abs(local[0]),closed.size[1]/2+abs(local[1]))
    # Midpoint OBB plus corner-displacement bound encloses the WHOLE arc.
    # Refine only ambiguous intervals; never accept based on samples alone.
    # A still-ambiguous 1/64 degree interval is conservatively a collision.
    def interval_hit(a,b,depth=0):
        box=door_pose(closed,(a+b)/2,hinge_local_m)
        error=2*reach*math.sin(abs(math.radians(b-a))/4)
        bound=inflated(box,error)
        if not sweep_hit(bound,bound.center,stationary):return False
        if sweep_hit(box,box.center,stationary) or depth>=6:return True
        mid=(a+b)/2
        return interval_hit(a,mid,depth+1) or interval_hit(mid,b,depth+1)
    delta=(end_angle-start_angle)/steps
    return any(interval_hit(start_angle+i*delta,start_angle+(i+1)*delta) for i in range(steps))


def audit_door_static_clearance(closed,obstacles,hinge_local_m=None):
    """Separate operability gate; do not ignore jambs to force a pass.

    Angular interval hits are conservative. Exact OBB overlap at 0/90 degrees
    is separately recorded and confirms a geometry conflict, not merely an
    interval approximation warning. This is still not a dynamics simulation.
    """
    opened=door_pose(closed,90,hinge_local_m);hits=[]
    for obstacle in obstacles:
        if not door_sweep_hit(closed,0,90,obstacle,hinge_local_m):continue
        hits.append({'obstacle_id':obstacle.id,
            'closed_pose_overlap':sweep_hit(closed,closed.center,obstacle),
            'open_pose_overlap':sweep_hit(opened,opened.center,obstacle),
            'swept_interval_hit':True})
    return {'ok':not hits,'status':'clear' if not hits else 'door_static_conflict',
        'confirmed_endpoint_overlap':any(h['closed_pose_overlap'] or h['open_pose_overlap'] for h in hits),
        'hits':hits,'scope':'door_vs_compiled_static_yaw_boxes',
        'angular_check':'conservative_corner_bound_adaptive_1_to_1_over_64_degree',
        'jambs_exempted':False,'physics_actuation_verified':False}


def plan_fixed_yaw_route(base, goal, obstacles, slabs, bounds, *, margin=.01,
                         step=.12, max_expansions=12000):
    """Bounded A* for a holonomic proxy. Does not model steering or arm links."""
    if (not math.isfinite(step) or step<=0 or type(max_expansions)!=int or max_expansions<1
            or len(goal)!=3 or len(bounds)!=4
            or not all(math.isfinite(v) for v in (*goal,*bounds,margin)) or margin<0):
        raise ValueError('Invalid route search budget')
    padded=inflated(base,margin);start=base.center
    def inside(p):
        rect=xy_bounds(replace(padded,center=p))
        return all((rect[0]>=bounds[0],rect[1]>=bounds[1],rect[2]<=bounds[2],rect[3]<=bounds[3]))
    def clear(a,b):
        box=replace(padded,center=a)
        return inside(b) and supported_sweep(box,b,slabs) and not hit_ids(box,b,obstacles)
    if not inside(start) or not clear(start,start) or not clear(goal,goal):
        return None,{'status':'blocked_endpoint','expanded':0}
    def position(key):return (start[0]+key[0]*step,start[1]+key[1]*step,start[2])
    queue=[(math.dist(start,goal),0,(0,0))];costs={(0,0):0};parents={};expanded=0
    neighbors=[(x,y) for x in (-1,0,1) for y in (-1,0,1) if x or y]
    occupied={}
    while queue and expanded<max_expansions:
        _,cost,key=heapq.heappop(queue)
        if cost!=costs[key]:continue
        expanded+=1;current=position(key)
        if math.dist(current,goal)<=step*1.6 and clear(current,goal):
            keys=[key]
            while keys[-1]!=(0,0):keys.append(parents[keys[-1]])
            raw=[position(k) for k in reversed(keys)]+[tuple(goal)]
            # Simplify only if the full shortcut sweep remains clear.
            path=[raw[0]];index=0
            while index<len(raw)-1:
                end=len(raw)-1
                while end>index+1 and not clear(raw[index],raw[end]):end-=1
                path.append(raw[end]);index=end
            return path,{'status':'planned','expanded':expanded,'grid_step_m':step,
                         'length_m':sum(math.dist(a,b) for a,b in zip(path,path[1:]))}
        for dx,dy in neighbors:
            nxt=(key[0]+dx,key[1]+dy);p=position(nxt)
            candidate=cost+step*math.hypot(dx,dy)
            if candidate>=costs.get(nxt,float('inf')):continue
            if nxt not in occupied:occupied[nxt]=clear(p,p)
            if not occupied[nxt] or not clear(current,p):continue
            costs[nxt]=candidate;parents[nxt]=key
            heapq.heappush(queue,(candidate+math.dist(p,goal),candidate,nxt))
    return None,{'status':'budget_exhausted' if queue else 'disconnected','expanded':expanded}
