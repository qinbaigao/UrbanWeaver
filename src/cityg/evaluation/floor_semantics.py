"""Read-only postconditions over realized rooms and compiled door geometry.

Independent of topology IDs, profile access_via and planner satisfaction receipts.
Checks single-corridor rectangular identity-frame floors only; no robot
clearance certification or implicit connectivity between multiple corridors.
"""
from collections import Counter, deque
import hashlib
import json
import math

from cityg.serialization import to_primitive


def fingerprint(value):
    return hashlib.sha256(json.dumps(to_primitive(value),sort_keys=True).encode()).hexdigest()


def _shared_edge(a,b):
    for axis,other in (('x','y'),('y','x')):
        lo=max(getattr(a,'min_'+axis),getattr(b,'min_'+axis))
        hi=min(getattr(a,'max_'+axis),getattr(b,'max_'+axis))
        for edge,opposite in (('min_','max_'),('max_','min_')):
            c=getattr(a,edge+other)
            if hi>lo and abs(c-getattr(b,opposite+other))<1e-5:return axis,c,lo,hi
    return None


def inspect_floor(floor, manifest):
    """Build access graph only from valid, compiled, boundary-aligned doors."""
    primitives=manifest['primitives']
    panels={}
    for p in primitives:
        if p['semantic_class']=='door' and p['layer_id']=='floor:'+floor.id:
            panels.setdefault(p['owner_id'],[]).append(p)
    rooms={r.id:r for r in floor.rooms};graph={rid:set() for rid in rooms};errors=[]
    if len(rooms)!=len(floor.rooms):errors.append('duplicate_room_ids')
    roots={r.id for r in floor.rooms if r.function=='corridor'}
    if len(roots)!=1:errors.append('unsupported_corridor_count')
    for door in floor.doors:
        if door.room_b_id is None:continue
        a,b=rooms.get(door.room_a_id),rooms.get(door.room_b_id)
        panel=panels.get(door.id,[])
        edge=_shared_edge(a.bounds,b.bounds) if a and b else None
        if not edge or len(panel)!=1:
            errors.append({'door_id':door.id,'reason':'missing_shared_edge_or_compiled_panel'});continue
        axis,coordinate,lo,hi=edge;p=panel[0];other='y' if axis=='x' else 'x'
        position=p['center'];width=p['size'][axis]
        values=[position[axis],position[other],width]
        good=(all(type(v) in (int,float) and math.isfinite(v) for v in values)
              and width>0 and abs(position[other]-coordinate)<.12
              and position[axis]-width/2>=lo-1e-4 and position[axis]+width/2<=hi+1e-4)
        if not good:
            errors.append({'door_id':door.id,'reason':'compiled_panel_outside_shared_edge'});continue
        graph[a.id].add(b.id);graph[b.id].add(a.id)
    def reached(blocked=None):
        seen=roots-{blocked};queue=deque(seen)
        while queue:
            for nxt in graph[queue.popleft()]-seen-{blocked}:
                seen.add(nxt);queue.append(nxt)
        return seen
    reachable=reached();ordinary=set(rooms)-roots
    direct={r for r in ordinary if graph[r]&roots}
    children=ordinary-direct
    # A transit-critical room disconnects some other room when removed.
    transit={rid for rid in ordinary if (ordinary-{rid})-reached(rid)}
    parents={rid:None for rid in sorted(roots)};queue=deque(sorted(roots))
    while queue:
        current=queue.popleft()
        for nxt in sorted(graph[current]):
            if nxt not in parents:parents[nxt]=current;queue.append(nxt)
    witnesses={}
    for rid in sorted(transit):
        blocked=sorted(((ordinary&reachable)-{rid})-reached(rid))
        if not blocked:continue
        path=[];current=blocked[0]
        while current is not None:path.append(current);current=parents[current]
        witnesses[rid]={'disconnected_room_id':blocked[0],'access_path':list(reversed(path))}
    return {'floor_id':floor.id,'level':floor.level,'graph':{k:sorted(v) for k,v in graph.items()},
            'room_functions':{r.id:r.function for r in floor.rooms},
            'function_counts':dict(Counter(r.function for r in floor.rooms if r.id in ordinary)),
            'direct_room_ids':sorted(direct),'private_child_room_ids':sorted(children),
            'transit_room_ids':sorted(transit),'transit_witnesses':witnesses,
            'unreachable_room_ids':sorted(ordinary-reachable),
            'valid':bool(ordinary and roots) and not errors and ordinary<=reachable,'errors':errors}


def evaluate_floor_requirements(before,after,building_id,manifest,contract):
    """Contract is frozen by the evaluator, never supplied by the planning model."""
    levels=contract.get('levels')
    if (not isinstance(levels,list) or not levels
            or any(type(n) is not int or n<0 for n in levels)
            or len(set(levels))!=len(levels)
            or contract.get('organization') not in (None,'independent','private_groups')):
        raise ValueError('Evaluator needs explicit unique levels and a supported organization predicate')
    for key in ('required_functions','no_transit_functions'):
        values=contract.get(key,[])
        if (not isinstance(values,list) or any(not isinstance(v,str) or not v for v in values)
                or (key=='required_functions' and not values)):
            raise ValueError('Evaluator needs explicit function lists')
    old={b.id:b for b in before.iter_buildings()};new={b.id:b for b in after.iter_buildings()}
    checks=[]
    def add(key,ok,**detail):checks.append({'id':key,'ok':bool(ok),**detail})
    add('building_inventory_preserved',set(old)==set(new))
    if building_id not in old or building_id not in new:
        return {'passed':False,'checks':checks,'floors':[],'reason':'missing_target'}
    a,b=old[building_id],new[building_id]
    add('shell_entry_core_preserved',fingerprint((a.footprint,a.entrance,a.vertical_connectors))==
        fingerprint((b.footprint,b.entrance,b.vertical_connectors)))
    add('non_target_buildings_preserved',all(fingerprint(v)==fingerprint(new.get(k))
        for k,v in old.items() if k!=building_id))
    add('site_preserved',fingerprint((before.bounds,before.road_network,before.rivers,before.bridges,[(d.id,d.bounds,[(p.id,p.bounds) for p in d.parcels]) for d in before.districts]))==
        fingerprint((after.bounds,after.road_network,after.rivers,after.bridges,[(d.id,d.bounds,[(p.id,p.bounds) for p in d.parcels]) for d in after.districts])))
    oldfloors={f.level:f for f in a.floors};newfloors={f.level:f for f in b.floors}
    add('floor_inventory_preserved',set(oldfloors)==set(newfloors)
        and len(oldfloors)==len(a.floors) and len(newfloors)==len(b.floors))
    targets=contract['levels'];reports=[]
    add('non_target_floors_preserved',all(fingerprint(f)==fingerprint(newfloors.get(level))
        for level,f in oldfloors.items() if level not in targets))
    for level in targets:
        if level not in newfloors:add(f'floor_{level}_exists',False);continue
        floor=newfloors[level];report=inspect_floor(floor,manifest);reports.append(report)
        add(f'floor_{level}_rooms_within_plate',all(b.footprint.contains_bounds(r.bounds,tolerance=1e-5) for r in floor.rooms))
        add(f'floor_{level}_no_room_overlap',not any(
            min(r.bounds.max_x,s.bounds.max_x)-max(r.bounds.min_x,s.bounds.min_x)>1e-5 and
            min(r.bounds.max_y,s.bounds.max_y)-max(r.bounds.min_y,s.bounds.min_y)>1e-5
            for i,r in enumerate(floor.rooms) for s in floor.rooms[i+1:]))
        if level==0:
            exterior={d.id for d in floor.doors if d.room_b_id is None}
            add('compiled_entrance_preserved',any(p['owner_id'] in exterior and p['semantic_class']=='door'
                and math.hypot(p['center']['x']-b.entrance.x,p['center']['y']-b.entrance.y)<.15
                for p in manifest['primitives']))
        add(f'floor_{level}_realized_access',report['valid'])
        functions=report['function_counts']
        add(f'floor_{level}_required_functions',set(contract['required_functions'])<=set(functions))
        organization=contract.get('organization')
        if organization=='independent':add(f'floor_{level}_organization',not report['private_child_room_ids'])
        elif organization=='private_groups':add(f'floor_{level}_organization',bool(report['private_child_room_ids']))
        for fn in contract.get('no_transit_functions',[]):
            violations={rid:report['transit_witnesses'].get(rid)
                for rid in report['transit_room_ids'] if report['room_functions'][rid]==fn}
            add(f'floor_{level}_no_transit_{fn}',not violations,witnesses=violations)
    return {'passed':bool(checks) and all(c['ok'] for c in checks),'checks':checks,'floors':reports,
        'scope':'compiled panel geometry and canonical rectangular access graph; not collision-free robot transit',
        'planner_receipts_used':False}
