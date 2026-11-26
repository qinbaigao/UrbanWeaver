"""Reviewed floor references, isolated from automatic city generation.

Metric rectangular partitions are reference designs, not arbitrary-scale
templates. Units and access edges survive materialization as explicit metadata.
"""
from collections import deque
from copy import deepcopy
from itertools import combinations
import json
import math
from pathlib import Path
import re

from cityg.planning.prototypes import fingerprint, LayoutPrototypeLibrary
from cityg.planning.spatial_layout import shared_boundary
from cityg.schemas import Bounds2D


def box(values):
    if (not isinstance(values, list) or len(values) != 4 or
            any(type(v) not in (int,float) or not math.isfinite(v) for v in values) or
            values[2] <= values[0] or values[3] <= values[1]):
        raise ValueError('Invalid floor rectangle')
    return Bounds2D(*values)


def connection_segment(record, connection):
    spaces={s['id']:s for s in record['spaces']}
    a,b=spaces[connection['a']],spaces[connection['b']]
    shared=shared_boundary(box(a['bounds_m']),box(b['bounds_m']))
    if shared is None:
        raise ValueError(f"Nonadjacent access edge: {connection['a']} / {connection['b']}")
    axis,boundary,start,end=shared
    center=start+(end-start)*connection['fraction']
    half=connection['width_m']/2
    if min(center-start,end-center) < half+.15-1e-6:
        raise ValueError('Door crosses a partition corner')
    return axis,boundary,center-half,center+half


class FloorPrototypeLibrary:
    def __init__(self, root):
        self.root=Path(root)
        self.room_library=LayoutPrototypeLibrary(root)
        records=[]
        if not (self.root/'floors.json').is_file():raise ValueError('Missing floor library')
        for path in sorted(self.root.glob('floors*.json')):
            document=json.loads(path.read_text())
            if document.get('schema_version')!=1 or not isinstance(document.get('prototypes'),list):
                raise ValueError('Expected floor library schema_version=1: '+path.name)
            records.extend(document['prototypes'])
        self.floors={}
        for record in records:
            key=record.get('id','')
            if not re.fullmatch('[a-z][a-z0-9_]{0,47}',key) or key in self.floors:
                raise ValueError('Unsafe/duplicate floor prototype ID')
            self.validate(record)
            self.floors[key]=deepcopy(record)

    def content_fingerprint(self,key):
        r=self.floors[key]
        return fingerprint({**{k:v for k,v in r.items() if k!='review'},
            'room_reference_fingerprints':{hint:self.room_library.content_fingerprint(hint)
                for s in r['spaces'] for hint in s.get('room_reference_hints',[])}})

    def validate(self,r):
        if r['level']!='floor' or type(r['revision']) is not int or r['revision']<1:
            raise ValueError('Invalid floor revision/level')
        if r['review'].get('status') not in {'draft','pending_review','approved','needs_revision'}:
            raise ValueError('Invalid floor review status')
        if r['review']['status']=='approved' and not all(r['review'].get(k) for k in ('reviewer','reviewed_fingerprint')):
            raise ValueError('Approval needs reviewer and fingerprint')
        w,d,h=(r['reference'][k] for k in ('width_m','depth_m','height_m'))
        if any(type(v) not in (int,float) or not math.isfinite(v) or v<=0 for v in (w,d,h)):
            raise ValueError('Invalid floor dimensions')
        plate=Bounds2D(0,0,w,d)
        spaces={s['id']:s for s in r['spaces']}
        if not spaces or len(spaces)!=len(r['spaces']):
            raise ValueError('Duplicate/empty spaces')
        for s in spaces.values():
            if not re.fullmatch('[a-z][a-z0-9_]{0,47}',s['id']):raise ValueError('Unsafe space ID')
            b=box(s['bounds_m'])
            if not plate.contains_bounds(b) or min(b.width,b.depth)<1.2-1e-6:
                raise ValueError('Space outside plate or too narrow: '+s['id'])
            for hint in s.get('room_reference_hints',[]):
                if hint not in self.room_library.rooms:raise ValueError('Unknown room reference')
            from cityg.planning.room_regions import region_bounds
            for zone in s.get('functional_zones',[]):
                region_bounds(b,zone['bounds_uv'])
            for uv in s.get('clear_aisles_uv',[]):
                lane=region_bounds(b,uv)
                if min(lane.width,lane.depth)<1.2:raise ValueError('Open hall aisle is too narrow')
        for a,b in combinations(spaces.values(),2):
            if box(a['bounds_m']).overlaps_area(box(b['bounds_m'])):raise ValueError('Overlapping floor spaces')
        if abs(sum(box(s['bounds_m']).area for s in spaces.values())-plate.area)>1e-5:
            raise ValueError('Incomplete floor coverage')
        graph={k:set() for k in spaces};pairs=set()
        for c in r['connections']:
            if c['a'] not in spaces or c['b'] not in spaces or c['a']==c['b']:
                raise ValueError('Unknown/self access edge')
            if (type(c['fraction']) not in (int,float) or not 0<c['fraction']<1 or
                    type(c['width_m']) not in (int,float) or not .8<=c['width_m']<=4 or c['kind'] not in {'door','open'}):
                raise ValueError('Invalid connection width/fraction/kind')
            pair=frozenset((c['a'],c['b']))
            if pair in pairs:raise ValueError('Duplicate access edge')
            pairs.add(pair);connection_segment(r,c)
            graph[c['a']].add(c['b']);graph[c['b']].add(c['a'])
        opens={frozenset(pair) for pair in r['open_boundaries']}
        if opens!={frozenset((c['a'],c['b'])) for c in r['connections'] if c['kind']=='open'}:
            raise ValueError('Open boundary graph mismatch')
        if any(spaces[k]['function']!='corridor' for pair in opens for k in pair):
            raise ValueError('Only circulation spaces may have open boundaries')
        reached=set();queue=[r['entry']['space']]
        while queue:
            k=queue.pop()
            if k not in graph:raise ValueError('Unknown floor entry')
            if k not in reached:reached.add(k);queue.extend(graph[k]-reached)
        if reached!=set(spaces):raise ValueError('Disconnected floor graph')
        e=r['entry'];eb=box(spaces[e['space']]['bounds_m'])
        if e['side'] not in {'south','north','west','east'} or not 0<e['fraction']<1 or not .8<=e['width_m']<=4:
            raise ValueError('Invalid entry')
        boundary={'south':eb.min_y,'north':eb.max_y,'west':eb.min_x,'east':eb.max_x}[e['side']]
        if abs(boundary-{'south':0,'north':d,'west':0,'east':w}[e['side']])>1e-6:
            raise ValueError('Entry is not on exterior')
        length=eb.width if e['side'] in {'north','south'} else eb.depth
        if min(e['fraction'],1-e['fraction'])*length<e['width_m']/2+.15:
            raise ValueError('Entry crosses a corner')
        unit_members=set()
        if len({u['id'] for u in r['units']})!=len(r['units']):raise ValueError('Duplicate unit ID')
        for unit in r['units']:
            members=unit['room_ids'];ub=box(unit['bounds_m'])
            if len(set(members))!=len(members) or unit_members & set(members):raise ValueError('Duplicate unit ownership')
            unit_members.update(members)
            if unit['entry_space'] not in members:raise ValueError('Invalid unit entrance')
            for key in members:
                if spaces[key].get('unit_id')!=unit['id'] or not ub.contains_bounds(box(spaces[key]['bounds_m'])):
                    raise ValueError('Unit membership/containment mismatch')
                if graph[key]-set(members) and key!=unit['entry_space']:
                    raise ValueError('Private room bypasses unit entrance')
            if abs(sum(box(spaces[k]['bounds_m']).area for k in members)-ub.area)>1e-5:
                raise ValueError('Incomplete dwelling unit')
        if unit_members!={s['id'] for s in spaces.values() if s.get('unit_id')}:
            raise ValueError('Unregistered unit room')
        if (not r['cores'] or len({c['id'] for c in r['cores']})!=len(r['cores']) or
                len({c['stack_key'] for c in r['cores']})!=len(r['cores'])):raise ValueError('Duplicate/empty core stack')
        obstacles=[]
        for c in r['cores']:
            b=box(c['bounds_m']);owner=spaces[c['public_space']];ob=box(owner['bounds_m'])
            if owner['function']!='corridor' or owner.get('unit_id') or not ob.contains_bounds(b):
                raise ValueError('Core outside public circulation')
            if c['kind'] not in {'stairs','elevator'} or c['min_landing_m']<1.2:raise ValueError('Invalid core')
            if c['kind']=='stairs' and (b.depth<4.5 or b.width<2):raise ValueError('Undersized stair reference')
            if any(b.overlaps_area(other) for other in obstacles):raise ValueError('Core overlap')
            obstacles.append(b)
            land=c['min_landing_m']
            if b.min_y-ob.min_y <land or (c['kind']=='stairs' and ob.max_y-b.max_y<land):
                raise ValueError('Insufficient stair/lift landing')
        return {'ok':True,'space_count':len(spaces),'unit_count':len(r['units']),
                'plate_area_m2':plate.area,'door_graph_connected':True,'core_stack_contract':True}


def circulation_raster(record, furniture=(), step=.3):
    """Plan-level 0.3m walkability check with open doors, cores and proxies.

    A 0.22m center clearance is used, not a regulatory egress certification.
    Explicit adjacency and corner/landing checks run independently above.
    """
    r=record;w,d=(r['reference'][k] for k in ('width_m','depth_m'))
    spaces={s['id']:box(s['bounds_m']) for s in r['spaces']}
    margin=.22
    def padded(b):return Bounds2D(b.min_x-margin,b.min_y-margin,b.max_x+margin,b.max_y+margin)
    obstacles=[padded(box(c['bounds_m'])) for c in r['cores']]+[padded(b) for b in furniture]
    passages=[]
    for c in r['connections']:
        axis,edge,start,end=connection_segment(r,c)
        if c['kind']=='open':axis,edge,start,end=shared_boundary(spaces[c['a']],spaces[c['b']])
        passages.append(Bounds2D(start+margin,edge-.3,end-margin,edge+.3) if axis=='x'
                        else Bounds2D(edge-.3,start+margin,edge+.3,end-margin))
    interiors=[b.inset(margin) for b in spaces.values()]
    from cityg.schemas import Point2D
    cells={};nx,ny=math.ceil(w/step),math.ceil(d/step)
    for i in range(nx):
        for j in range(ny):
            p=Point2D((i+.5)*step,(j+.5)*step)
            if any(b.contains_point(p) for b in obstacles):continue
            if any(b.contains_point(p) for b in interiors) or any(b.contains_point(p) for b in passages):cells[i,j]=p
    eb=spaces[r['entry']['space']];start=next((k for k,p in cells.items() if eb.contains_point(p)),None)
    reached=set() if start is None else {start};queue=deque(reached)
    while queue:
        i,j=queue.popleft()
        for q in ((i-1,j),(i+1,j),(i,j-1),(i,j+1)):
            if q in cells and q not in reached:reached.add(q);queue.append(q)
    missing=[key for key,b in spaces.items() if not any(b.inset(margin).contains_point(cells[k]) for k in reached)]
    missing_landings=[]
    for c in r['cores']:
        b=box(c['bounds_m'])
        sides=[('south',b.min_y-.6)]
        if c['kind']=='stairs':sides.append(('north',b.max_y+.6))
        for side,y in sides:
            if not any(math.hypot(cells[k].x-b.center.x,cells[k].y-y)<.45 for k in reached):
                missing_landings.append(c['id']+'_'+side)
    return {'ok':not missing and not missing_landings,'grid_step_m':step,'body_clearance_m':margin,
            'unreachable_spaces':missing,'reachable_cells':len(reached),'walkable_cells':len(cells),
            'unreachable_core_landings':missing_landings,
            'doors_assumed_open':True,'certification':False}
