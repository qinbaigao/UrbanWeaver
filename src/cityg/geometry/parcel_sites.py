"""Connected parcel amenity pockets: paths first, then bounded activity nodes.

Deterministic geometric realization with optional per-parcel authored programs
in city.metadata['parcel_site_programs']. No LLM/network dependency at compile.
"""
from collections import Counter,defaultdict
import math

from shapely.ops import nearest_points
from cityg.geometry.geography import polygon_mesh,primitive_footprint
from cityg.geometry.site_furnishings import furnish_site
from cityg.geometry.site_routing import route_in_polygon
from cityg.polygons import box_shape,geos,parcel_shape,river_shape,road_shape

VERSION='connected_parcel_sites_v1'
KINDS={'seating_court','cycle_shelter','pergola','service_hut'}


def compile_parcel_sites(compiler,city,scene):
    if not compiler.asset_registry_configured:return {'status':'skipped_no_asset_registry'}
    s=geos();base=[p for p in scene.primitives if p.metadata.get('site_system')!=VERSION]
    index=defaultdict(list)
    for p in base:index[p.owner_id].append(p)
    roads=s.union_all([road_shape(r,.35) for r in city.road_network.segments])
    sidewalks=s.union_all([road_shape(r,r.sidewalk_width_m).difference(road_shape(r,.25)) for r in city.road_network.segments])
    water=s.union_all([river_shape(r,'reserve') for r in city.rivers])
    frontage=[p for p in base if p.semantic_class=='frontage_connector']
    front_shapes={p.id:primitive_footprint(p) for p in frontage}
    parcels=list(city.iter_parcels());shapes={p.id:parcel_shape(p) for p in parcels}
    additions=[];records=[];skips=Counter()
    for district in city.districts:
        for parcel in district.parcels:
            if not parcel.buildings:continue
            shape=shapes[parcel.id];function=compiler._parcel_function(parcel,district.function)
            building_ids={b.id for b in parcel.buildings}
            obstacles=[box_shape(b.footprint).buffer(.6) for b in parcel.buildings]
            for b in parcel.buildings:
                for f in b.floors:
                    if f.level==0:
                        obstacles.extend(primitive_footprint(p).buffer(.5) for p in index[f.id] if p.semantic_class=='floor_slab')
            obstacles.extend(primitive_footprint(p).buffer(.3) for p in index[parcel.id]
                if p.semantic_class=='parcel_planting_bed' or p.center.z+p.size.z/2>.25)
            blocked=s.union_all(obstacles).union(roads).union(water)
            free=shape.buffer(-.15).difference(blocked)
            safe=free.buffer(-1.0)
            if safe.is_empty or free.area<70:
                skips['insufficient_space']+=1;continue
            # Existing entry connector is the first choice: preserve the actual
            # building-to-street link instead of inferring a new door location.
            connections=[front_shapes[p.id] for p in frontage if p.metadata.get('building_id') in building_ids
                or p.metadata.get('residential_group_paths') and p.metadata.get('parcel_id') == parcel.id]
            connection=s.union_all(connections).intersection(safe)
            link=None;root=None;source='existing_entrance_path'
            if not connection.is_empty:
                root=connection.representative_point()
            elif not sidewalks.is_empty:
                a,b=nearest_points(safe,sidewalks)
                line=s.LineString([(a.x,a.y),(b.x,b.y)])
                other=s.union_all([v for k,v in shapes.items() if k!=parcel.id and v.distance(shape)<8])
                stub=line.buffer(.9,quad_segs=4)
                # At most a small setback link, never a cross-road connection.
                if a.distance(b)<=6 and not stub.intersects(blocked.union(other)) and box_shape(city.bounds).covers(stub):
                    root=a;link=stub;source='sidewalk_setback_link'
            if root is None:
                skips['no_safe_street_connection']+=1;continue
            # Protect *all* existing entry paths, not just the chosen root.
            protected=s.union_all(connections).buffer(.5)
            seed=compiler._parcel_seed(parcel.id,VERSION)
            defaults=['seating_court','cycle_shelter'] if function in {'commercial','mixed_use'} else ['pergola','seating_court']
            if function=='industrial':defaults=['cycle_shelter','service_hut']
            elif free.area>400 and seed%3==0:defaults.append('service_hut')
            program=city.metadata.get('parcel_site_programs',{}).get(parcel.id,{})
            requested=program.get('features',defaults)
            if not isinstance(requested,list) or any(k not in KINDS for k in requested):
                skips['invalid_program']+=1;continue
            target=min(3,len(requested),max(1,int(free.area/240)))
            chosen=[];used=s.GeometryCollection();routes=[];parcel_items=[]
            x0,y0,x1,y1=shape.bounds
            for attempt in range(90):
                if len(chosen)>=target:break
                x=x0+((seed%997/997+attempt*.61803398875)%1)*(x1-x0)
                y=y0+((seed%991/991+attempt*.41421356237)%1)*(y1-y0)
                if math.hypot(x-root.x,y-root.y)>85:continue
                # Pad front faces the route origin; assemblies keep their
                # porch/door and pedestrian space on that side.
                angle=math.atan2(root.y-y,root.x-x)+math.pi/2
                co,si=math.cos(angle),math.sin(angle)
                def world(lx,ly):return (x+lx*co-ly*si,y+lx*si+ly*co)
                pad=s.Polygon([world(a,b) for a,b in [(-3.5,-2.7),(3.5,-2.7),(3.5,2.7),(-3.5,2.7)]])
                if not free.covers(pad.buffer(.15)) or pad.intersects(used.union(protected)):continue
                goal=world(0,-2.4)
                path=route_in_polygon((root.x,root.y),goal,free.difference(used),budget=2500)
                if not path:continue
                path_shape=s.LineString(path).buffer(.9,quad_segs=4)
                prefix=f'{parcel.id}_site_node_{len(chosen):02d}';kind=requested[len(chosen)]
                meta={'parcel_id':parcel.id,'district_id':district.id,'site_system':VERSION,
                      'site_detail':True,'site_feature':kind,'site_node_id':prefix,
                      'exterior_only':True,'interactive':False,'activity_mode':'static_snapshot'}
                furnishings=furnish_site(compiler,parcel.id,prefix,kind,(x,y),angle,pad,meta)
                if not furnishings:continue
                # The front 1.2 m of every assembly is reserved for walking.
                protected_route=path_shape.difference(pad.buffer(-.05))
                if any(primitive_footprint(p).intersects(protected_route) for p in furnishings):continue
                material='brick_paving' if function=='residential' else 'paving_light'
                parcel_items.append(polygon_mesh(prefix+'_pad',parcel.id,pad,.105,.08,'parcel_activity_pad',material,collision=True,metadata=meta))
                parcel_items.extend(furnishings);routes.append(path_shape)
                chosen.append({'id':prefix,'kind':kind,'path':path,'root':[root.x,root.y],
                    'connection':source,'asset_count':sum(bool(p.metadata.get('asset_id')) for p in furnishings)})
                # Nodes cannot cover previously committed routes; subsequent
                # paths may join those routes, but cannot traverse occupied pads.
                protected=protected.union(path_shape.buffer(.2));used=used.union(pad.buffer(.3))
            if not chosen:
                skips['no_reachable_activity_pocket']+=1;continue
            if link is not None:routes.append(link)
            path_meta={'parcel_id':parcel.id,'district_id':district.id,'site_system':VERSION,
                       'site_detail':True,'site_feature':'pedestrian_path','path_width_m':1.8,
                       'connection':source,'routes':[node['path'] for node in chosen]}
            # A union avoids layered coplanar strips at branch junctions.
            path_surface=s.union_all(routes)
            pads=s.union_all([primitive_footprint(p) for p in parcel_items if p.semantic_class=='parcel_activity_pad'])
            path_surface=path_surface.difference(pads)
            path_mesh=polygon_mesh(f'{parcel.id}_site_paths',parcel.id,path_surface,.095,.07,
                'parcel_walkway','permeable_paver',collision=True,metadata=path_meta)
            if path_mesh:parcel_items.append(path_mesh)
            additions.extend(parcel_items);records.append({'parcel_id':parcel.id,'function':function,'nodes':chosen})
    scene.primitives=base+additions
    counts=Counter(p.metadata['asset_id'] for p in additions if p.metadata.get('asset_id'))
    report={'version':VERSION,'changed_parcel_count':len(records),'parcels':records,'skips':dict(skips),
            'node_counts':dict(Counter(n['kind'] for p in records for n in p['nodes'])),
            'new_asset_instances':sum(counts.values()),'asset_counts':dict(counts),'new_primitives':len(additions),
            'navigation_graph_extended':False}
    scene.metadata['parcel_sites']=report
    return report
