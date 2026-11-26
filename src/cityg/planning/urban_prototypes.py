"""Opt-in urban recipes and independently measured realization evidence."""
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
import re

from cityg.ccwp import build_world_program
from cityg.morphology import realization_report
from cityg.planning.baseline import BaselineCityPlanner
from cityg.planning.prototypes import fingerprint
from cityg.schemas import CitySpec


class NoPrototypeFurniture:
    def populate(self,city,seed):
        return {'skipped':True,'reason':'urban prototype exterior-only review'}


class UrbanPrototypeLibrary:
    def __init__(self,root):
        self.root=Path(root)
        records=[]
        if not (self.root/'urban.json').is_file():raise ValueError('Missing urban library')
        for path in sorted(self.root.glob('urban*.json')):
            data=json.loads(path.read_text())
            if data.get('schema_version')!=1:raise ValueError('Unsupported urban prototype version')
            records.extend(data['prototypes'])
        self.records={}
        from cityg.planning.floor_prototypes import FloorPrototypeLibrary
        self.floor_records=FloorPrototypeLibrary(self.root).floors
        for r in records:
            key=r.get('id','')
            if not re.fullmatch('[a-z][a-z0-9_]{0,47}',key) or key in self.records:raise ValueError('Unsafe/duplicate urban ID')
            if r['level']!='urban' or type(r['revision']) is not int or r['revision']<1:raise ValueError('Invalid urban record')
            if r['review']['status'] not in {'draft','pending_review','approved','needs_revision'}:raise ValueError('Invalid review state')
            spec=CitySpec.from_dict(r['spec'])
            if not 20<=spec.building_count<=40:raise ValueError('Review reference needs 20..40 buildings')
            if spec.architecture.get('expressive_ratio')!=.2:raise ValueError('Review defaults preserve 20% expressive quota')
            if any(k not in self.floor_records for k in r['floor_reference_hints']):raise ValueError('Unknown floor reference')
            policy=r['public_space_policy']
            if not policy['style_cycle'] or any(s not in {'park','plaza','garden'} for s in [*policy['style_cycle'],policy['anchor_style']]):raise ValueError('Unknown public-space style')
            if policy['anchor_selection']!='nearest_available_to_center' or policy['density_tier'] not in {'sparse','standard','lush'}:raise ValueError('Unknown public-space policy')
            self.records[key]=deepcopy(r)

    def content_fingerprint(self,key):
        r=self.records[key]
        return fingerprint({**{k:v for k,v in r.items() if k!='review'},
            'floor_reference_fingerprints':{k:fingerprint({a:b for a,b in self.floor_records[k].items() if a!='review'}) for k in r['floor_reference_hints']}})

    def spec(self,key,overrides=None):
        r=self.records[key];values=deepcopy(r['spec'])
        for name,value in (overrides or {}).items():
            limits=r['adjustable_parameters'].get(name)
            if limits is None or type(value) is not int or not limits[0]<=value<=limits[1]:raise ValueError('Unsupported/out-of-range urban adjustment')
            values[name]=value
        return CitySpec.from_dict(values)

    def plan(self,key,overrides=None):
        spec=self.spec(key,overrides);r=self.records[key]
        city=BaselineCityPlanner(floor_detail_agent=NoPrototypeFurniture()).plan(spec)
        policy=r['public_space_policy'];sites=city.metadata.get('landscape_sites',[])
        for i,site in enumerate(sites):
            site['style']=policy['style_cycle'][i%len(policy['style_cycle'])]
            site['density_tier']=policy['density_tier']
        anchor=None
        if sites:
            center=city.bounds.center
            def distance(s):
                b=s['bounds'];return ((b['min_x']+b['max_x'])/2-center.x)**2+((b['min_y']+b['max_y'])/2-center.y)**2
            anchor=min(sites,key=distance);anchor['style']=policy['anchor_style']
            anchor['urban_prototype_role']='public_space_anchor'
        city.metadata['urban_layout_prototype']={'id':key,'fingerprint':self.content_fingerprint(key),
            'status':'pending_human_review','production_enabled':False,
            'public_space_anchor_id':anchor['id'] if anchor else None,'floor_reference_hints':r['floor_reference_hints'],
            'recipe_overrides':overrides or {},'canonical_floor_skeletons_retained':True}
        city.metadata['interior_scope']={'building_levels':{},'policy':'urban_prototype_exterior_only'}
        city.world_program=build_world_program(city,producer='urban_prototype_lab',seed=spec.seed)
        return city


def realization(city,spec):
    """Measure actual graph, block membership, skyline and local geography."""
    buildings=list(city.iter_buildings());roads=city.road_network.segments
    graph={j.id:set() for j in city.road_network.junctions}
    for road in roads:
        graph[road.start_junction_id].add(road.end_junction_id);graph[road.end_junction_id].add(road.start_junction_id)
    seen=set();queue=list(graph)[:1]
    while queue:
        n=queue.pop()
        if n not in seen:seen.add(n);queue.extend(graph[n]-seen)
    morphology=realization_report(city)
    clusters=Counter(b.metadata.get('urban_block_id',b.id) for b in buildings)
    checks={'exact_building_count':len(buildings)==spec.building_count,'road_graph_connected':bool(graph) and len(seen)==len(graph),
        'straight_roads_dominate':morphology['straight_road_length_ratio']>=.65,
        'expressive_quota':abs(morphology['expressive_building_ratio']-.2)<=1/max(1,len(buildings)),
        'floor_range':all(spec.min_floors<=len(b.floors)<=spec.max_floors for b in buildings),
        'public_space_present':bool(city.metadata.get('landscape_sites')),
        'no_furniture':not any(city.iter_objects()),
        'geography':bool(city.rivers and city.bridges) if spec.river_mode!='none' else not city.rivers}
    return {'ok':all(checks.values()),'checks':checks,'building_count':len(buildings),
        'function_counts':dict(Counter(b.function for b in buildings)),
        'floor_histogram':dict(sorted(Counter(len(b.floors) for b in buildings).items())),
        'multi_building_block_count':sum(n>1 for n in clusters.values()),
        'public_space_count':len(city.metadata.get('landscape_sites',[])),
        'road_class_counts':dict(Counter(r.road_class for r in roads)),
        'polygon_parcel_count':sum(bool(p.boundary) for p in city.iter_parcels()),
        'bridge_count':len(city.bridges),'morphology':morphology}


def topology_snapshot(city):
    """Realized editable references, not merely a raster or fixed point cloud."""
    from shapely.geometry import Polygon,box as shape_box
    parcels=list(city.iter_parcels())
    shapes={p.id:Polygon([(q.x,q.y) for q in p.boundary]) if p.boundary else shape_box(p.bounds.min_x,p.bounds.min_y,p.bounds.max_x,p.bounds.max_y) for p in parcels}
    neighbors=[]
    for i,a in enumerate(parcels):
        for b in parcels[i+1:]:
            if shapes[a.id].distance(shapes[b.id])<.25:neighbors.append([a.id,b.id])
    return {'schema_version':1,'road_edges':[{'id':r.id,'from':r.start_junction_id,'to':r.end_junction_id,
                'class':r.road_class,'width_m':r.width_m,'centerline':[asdict(p) for p in r.centerline]} for r in city.road_network.segments],
        'parcel_touching_pairs':neighbors,'parcel_neighbor_tolerance_m':.25,
        'parcels':[{'id':p.id,'building_ids':[b.id for b in p.buildings],'bounds':asdict(p.bounds),
                    'boundary':[asdict(q) for q in p.boundary]} for p in parcels],
        'building_groups':[{'building_id':b.id,'block_id':b.metadata.get('urban_block_id'),
            'function':b.function,'height_contract':b.metadata.get('height_contract'),
            'entrance':asdict(b.entrance),'orientation_contract':b.metadata.get('orientation_contract')}
            for b in city.iter_buildings()],
        'public_spaces':deepcopy(city.metadata.get('landscape_sites',[])),
        'rivers':[asdict(r) for r in city.rivers],'bridges':[asdict(b) for b in city.bridges]}
