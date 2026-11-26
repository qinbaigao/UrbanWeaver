"""Opt-in roof zoning on realized support surfaces; no invented roof navigation."""
from collections import Counter, defaultdict
from dataclasses import replace
import math

from shapely.ops import nearest_points

from cityg.geometry.facade_colorways import owner_buildings
from cityg.geometry.geography import polygon_mesh, primitive_footprint
from cityg.geometry.model import MaterialSpec, Vec3
from cityg.geometry.roof_assemblies import furnish_roof_zone
from cityg.geometry.roof_programs import roof_profile, roof_seed, zone_brief
from cityg.geometry.roof_surfaces import roof_surfaces, to_local, to_world
from cityg.geometry.site_routing import route_in_polygon
from cityg.polygons import geos, polygon_parts

VERSION='roofscape_v1'
SIZES={'equipment':(12.,8.),'solar':(14.,11.),'garden':(14.,10.),'terrace':(10.,8.)}


def materials_for_roofs(scene):
    source={m.id:m for m in scene.materials if not m.id.startswith('roofscape_')}
    def inherited(name,base,color,roughness=.85):
        old=source.get(base,MaterialSpec(base,color))
        return replace(old,id=name,display_color=color,roughness=roughness,metallic=0,
                       texture_scale_m=3.)
    specs=[inherited('roof_zone_gravel','gravel_warm',(.55,.58,.58)),
           inherited('roof_zone_paver','paving_light',(.63,.65,.64)),
           inherited('roof_plant_cover','parcel_lawn',(.40,.54,.28)),
           MaterialSpec('roof_unit_shell',(.48,.54,.56),.62,.35),
           MaterialSpec('roof_vent_dark',(.065,.08,.085),.85,.20),
           MaterialSpec('roof_screen',(.29,.34,.35),.65,.25),
           MaterialSpec('roof_solar_cells',(.018,.045,.085),.34,.35),
           MaterialSpec('roof_service_path',(.48,.50,.48),.92)]
    existing={m.id for m in scene.materials}
    scene.materials.extend(m for m in specs if m.id not in existing)


def compile_roofscape(compiler,city,scene,building_ids=None,progress=None):
    enabled=city.metadata.get('roofscape',{}).get('enabled',False)
    buildings=[b for b in city.iter_buildings() if building_ids is None or b.id in building_ids]
    buildings=[b for b in buildings if enabled or b.metadata.get('roof_program')]
    if not buildings:return {'status':'not_requested'}
    profiles={b.id:roof_profile(b) for b in buildings}  # validate before mutation
    ids=set(profiles);s=geos();owners=owner_buildings(city)
    base=[p for p in scene.primitives if not (p.metadata.get('roof_system')==VERSION and p.owner_id in ids)]
    by_building=defaultdict(list)
    for p in base:
        bid=owners.get(p.owner_id)
        if bid in ids:by_building[bid].append(p)
    materials_for_roofs(scene)
    materials={m.id:m for m in scene.materials};additions=[];records=[];skips=Counter()
    for building_index,building in enumerate(buildings):
        owned=by_building[building.id];surfaces=roof_surfaces(owned)
        if not surfaces:
            skips['no_supported_flat_roof']+=1;continue
        profile=profiles[building.id];seed=roof_seed(building.id)
        angle=float(building.metadata.get('orientation_deg',0));top=max(r['z'] for r in surfaces)
        origin=(building.footprint.center.x,building.footprint.center.y)
        for index,roof in enumerate(surfaces):
            z=roof['z'];shape=to_local(roof['shape'],origin,angle)
            prefix=f'{building.id}_roofscape_{index:02d}'
            meta={'roof_system':VERSION,'roof_detail':True,'building_id':building.id,
                  'roof_profile':profile,'support_z':z,'source_roof_ids':roof['source_ids'],
                  'interactive':False,'exterior_only':True}
            obstacles=s.union_all([to_local(primitive_footprint(p),origin,angle).buffer(.6) for p in owned
                if p.semantic_class not in {'roof','collision_envelope'} and p.center.z+p.size.z/2>z+.12
                and p.center.z-p.size.z/2<z+3.5])
            safe=shape.buffer(-1.1).difference(obstacles)
            roof_items=[];zones=[];paths=[];accesses=[]
            def surface(name,polygon,h,t,material,semantic='roof_surface_detail'):
                p=polygon_mesh(prefix+'_'+name,building.id,to_world(polygon,origin,angle),z+h,t,
                    semantic,material,layer='shell:'+building.id,metadata=meta)
                if p:roof_items.append(p)

            # Subtle 5–9 m membrane courses, restrained repair patches, and an
            # edge strip survive downsampling without random grime everywhere.
            original=next(p.material_id for p in owned if p.id==roof['source_ids'][0])
            source=materials.get(original,MaterialSpec(original,(.5,.5,.5)))
            for tone,factor in enumerate((.86,.94,1.035)):
                mid=f'roofscape_tone_{original}_{tone}'
                if mid not in materials:
                    m=replace(source,id=mid,display_color=tuple(min(1.,c*factor) for c in source.display_color),
                              roughness=min(1.,source.roughness+.03))
                    materials[mid]=m;scene.materials.append(m)
            inner=shape.buffer(-.25)
            surface('edge_weathering',inner.difference(inner.buffer(-.45)),.014,.014,f'roofscape_tone_{original}_0')
            x0,y0,x1,y1=shape.bounds;step=6.+seed%4
            for row in range(math.ceil((y1-y0)/step)):
                for col in range(math.ceil((x1-x0)/step)):
                    key=roof_seed(f'{prefix}:{row}:{col}')
                    if key%4==0:continue
                    tile=s.box(x0+col*step+.025,y0+row*step+.025,
                               x0+(col+1)*step-.025,y0+(row+1)*step-.025).intersection(inner)
                    surface(f'course_{row}_{col}',tile,.012,.012,f'roofscape_tone_{original}_{1+key%2}')

            # Each disconnected exposed roof component gets its own service
            # root. It is a visual maintenance hatch, not a claimed stair link.
            for component_index,component in enumerate(polygon_parts(safe)):
                if component.area<40:continue
                # A central hatch can block the only usable strip on a narrow
                # roof. Prefer a feasible edge-side root, never an arbitrary
                # centroid in a hole or behind an existing rooftop structure.
                sx0,sy0,sx1,sy1=component.bounds
                roots=[component.representative_point()]+[
                    s.Point(sx0+(sx1-sx0)*fx,sy0+(sy1-sy0)*fy)
                    for fx in (.08,.16,.3,.5,.7,.84,.92) for fy in (.12,.25,.5,.75,.88)]
                roots=[r for r in roots if component.covers(s.box(r.x-1.6,r.y-1.3,r.x+1.6,r.y+1.3))]
                if not roots:continue
                root=min(roots,key=lambda r:r.distance(component.boundary));rx,ry=root.x,root.y
                hatch=s.box(rx-1.2,ry-.9,rx+1.2,ry+.9)
                if not component.covers(hatch.buffer(.4)):continue
                cp=f'{prefix}_component_{component_index}'
                surface(f'hatch_base_{component_index}',hatch,.14,.14,'roof_zone_paver')
                surface(f'hatch_{component_index}',hatch.buffer(-.12),.35,.21,'roof_unit_shell','roof_equipment')
                accesses.append({'center':[rx,ry],'kind':'visual_maintenance_hatch','simulation_connected':False})
                # Start alongside the hatch, leaving a full-width apron.
                root_shape=hatch.buffer(.9).difference(hatch.buffer(.15)).intersection(component)
                network=root_shape;used=hatch.buffer(.25);protected=root_shape
                kinds=zone_brief(profile,component.area,z<top-.5)
                sx0,sy0,sx1,sy1=component.bounds
                for slot,kind in enumerate(kinds):
                    # Adaptive envelopes retain the assembly's clear apron;
                    # prefer full-size zones, then compact variants.
                    dimensions=[SIZES[kind],{'equipment':(8.,6.),'solar':(8.,5.),
                        'garden':(8.,5.),'terrace':(8.,6.)}[kind]]
                    candidates=[]
                    for attempt in range(360):
                        size_rank=attempt//180;w,d=dimensions[size_rank]
                        x=sx0+((seed%997/997+attempt*.61803398875)%1)*(sx1-sx0)
                        y=sy0+((seed%991/991+attempt*.41421356237)%1)*(sy1-sy0)
                        pad=s.box(x-w/2,y-d/2,x+w/2,y+d/2)
                        if not component.covers(pad.buffer(.35)) or pad.intersects(used.union(protected)):continue
                        goal=s.Point(x,y-d/2-.85)
                        candidates.append((size_rank,network.distance(goal),attempt,pad,goal))
                    # Reserve attempts for compact fits even when large zones
                    # fit geometrically but cannot be reached around obstacles.
                    ordered=[]
                    for rank in range(len(dimensions)):
                        ordered.extend(sorted((c for c in candidates if c[0]==rank),key=lambda c:c[1:3])[:12])
                    for _,_,_,pad,goal in ordered:
                        free=component.difference(used).difference(pad.buffer(.08))
                        roots=network.intersection(free.buffer(-.60))
                        if roots.is_empty:continue
                        start=nearest_points(roots,goal)[0]
                        route=route_in_polygon((start.x,start.y),(goal.x,goal.y),free,width=1.1,step=1.,budget=1500)
                        if not route:continue
                        # Straight final segment meets the clear apron at the
                        # front of the assembly, not a diagonal through furniture.
                        route.append((goal.x,pad.bounds[1]+.65))
                        path=s.LineString(route).buffer(.55,quad_segs=4)
                        if not component.covers(path) or path.intersects(used):continue
                        key=f'{cp}_zone_{slot}'
                        parts=furnish_roof_zone(compiler,building,key,kind,pad.bounds,origin,angle,z,meta)
                        world_path=to_world(path,origin,angle)
                        if any(primitive_footprint(p).intersection(world_path).area>1e-6
                               for p in parts if p.metadata.get('ground_obstacle')):continue
                        roof_items.extend(parts);paths.append(path)
                        zones.append({'id':key,'kind':kind,'bounds_local':list(pad.bounds),
                                      'primitive_count':len(parts)})
                        used=used.union(pad.buffer(.30));protected=protected.union(path.buffer(.2))
                        network=network.union(path.difference(pad.buffer(.35)))
                        break
                    else:skips[f'no_space_for_{kind}']+=1
            if paths:surface('service_paths',s.union_all(paths),.025,.025,'roof_service_path')
            # Final independent boundary/height guard, including imported GLBs.
            for p in roof_items:
                if not roof['shape'].buffer(1e-5).covers(primitive_footprint(p)):
                    raise AssertionError(f'Roof detail exceeds actual support: {p.id}')
                if p.center.z-p.size.z/2<z-1e-5:
                    raise AssertionError(f'Roof detail below support: {p.id}')
            additions.extend(roof_items)
            records.append({'building_id':building.id,'profile':profile,'support_z':z,
                'source_roof_ids':roof['source_ids'],'exposed_area_m2':round(shape.area,2),
                'origin':list(origin),'angle_deg':angle,'zones':zones,'accesses':accesses,
                'primitive_count':len(roof_items)})
        if progress:progress(building_index+1,len(buildings),building.id)
    scene.primitives=base+additions
    report={'version':VERSION,'building_count':len({r['building_id'] for r in records}),
            'surface_count':len(records),'new_primitives':len(additions),
            'asset_instances':sum(bool(p.metadata.get('asset_id')) for p in additions),
            'profile_counts':dict(Counter(profiles[b] for b in {r['building_id'] for r in records})),
            'zone_counts':dict(Counter(z['kind'] for r in records for z in r['zones'])),
            'skips':dict(skips),'surfaces':records,'navigation_graph_extended':False,
            'simulation_rooftop_access':False}
    scene.metadata['roofscape']=report
    return report
