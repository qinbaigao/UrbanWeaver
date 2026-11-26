"""Sparse, connected exterior metro entrances from explicitly reviewed assets.

No underground routing, moving escalators, station interiors or transit claims.
Placement is optional/local-only and never substitutes a random building asset.
"""
from collections import Counter
import math

from shapely.ops import nearest_points
from cityg.geometry.geography import polygon_mesh, primitive_footprint
from cityg.geometry.incremental import scene_from_manifest
from cityg.geometry.model import Vec3
from cityg.geometry.site_routing import route_in_polygon
from cityg.polygons import box_shape, geos, parcel_shape, river_shape, road_shape, line_shape
from cityg.serialization import to_primitive

VERSION='exterior_metro_entrances_v1'
GROUND={'city_ground','parcel_ground','parcel_surface_patch'}
REMOVABLE={'parcel_tree_asset','parcel_shrub_asset','street_tree_asset','landscape_shrub_asset',
           'flower_cluster','parcel_flower_mass','small_sign','street_bin'}


def ready_assets(registry):
    result=[]
    for record in registry.list_all():
        spec=record.metadata.get('metro_placement',{})
        if (record.category=='metro_entrance' and record.environment=='outdoor'
            and record.metadata.get('outdoor_pack_status')=='ready' and spec.get('reviewed')
            and record.dimensions_m and record.geometry_path and registry.resolve_path(record.geometry_path).is_file()
            and spec.get('front_axis') in {'+X','-X','+Y','-Y'}):
            result.append(record)
    return result


def transformed_rect(bounds, center, angle):
    s=geos();co,si=math.cos(angle),math.sin(angle)
    x0,y0,x1,y1=bounds
    return s.Polygon([(center[0]+x*co-y*si,center[1]+x*si+y*co)
                      for x,y in [(x0,y0),(x1,y0),(x1,y1),(x0,y1)]])


def compile_metro_entrances(compiler,city,scene):
    s=geos()
    # Restore only surfaces clipped by this stage; repeated compilation and
    # disabling the feature must not accumulate irreversible holes.
    saved=scene.metadata.pop('metro_ground_originals',[])
    removed_saved=scene.metadata.pop('metro_removed_decorations',[])
    originals={p.id:p for p in scene_from_manifest({'city_id':city.id,
        'coordinate_system':city.coordinate_system,'primitives':saved}).primitives}
    base=[originals.get(p.id,p) for p in scene.primitives if p.metadata.get('metro_system')!=VERSION]
    restored=scene_from_manifest({'city_id':city.id,'coordinate_system':city.coordinate_system,
                                 'primitives':[entry['primitive'] for entry in removed_saved]}).primitives
    present={q.id for q in base}
    for entry,p in sorted(zip(removed_saved,restored),key=lambda pair:pair[0]['index']):
        if p.id not in present:base.insert(entry['index'],p);present.add(p.id)
    scene.primitives=base
    config=city.metadata.get('metro_entrances',{})
    if not isinstance(config,dict):raise ValueError('metro_entrances must be an object')
    count=config.get('count',min(6,max(1,sum(1 for _ in city.iter_buildings())//16)))
    spacing=float(config.get('min_spacing_m',160))
    decor_budget=config.get('max_decor_removals_per_entrance',0)
    if isinstance(decor_budget,bool) or not isinstance(decor_budget,int) or not 0<=decor_budget<=6:
        raise ValueError('Metro decoration removal budget must be 0..6')
    if isinstance(count,bool) or not isinstance(count,int) or not 0<=count<=24 or not math.isfinite(spacing) or spacing<0:
        raise ValueError('Metro count must be 0..24 and spacing nonnegative')
    assets=ready_assets(compiler.asset_registry)
    report={'version':VERSION,'requested_count':count,'placed_count':0,'entrances':[],
            'navigation_graph_extended':False,'underground_simulated':False,'skips':{}}
    scene.metadata['metro_entrances']=report
    if not config.get('enabled',True) or count==0:
        report['status']='disabled';return report
    if not assets:
        report['status']='skipped_no_reviewed_asset';return report
    roads=s.union_all([road_shape(r,.3) for r in city.road_network.segments])
    water=s.union_all([river_shape(r,'reserve') for r in city.rivers])
    frontages=[(p,primitive_footprint(p)) for p in base if p.semantic_class=='frontage_connector']
    # Low-level props across ALL owners, including roads and district furniture.
    occupied=[];decorations={};obstacle_ids=[]
    building_owners={b.id for b in city.iter_buildings()} | {f.id for b in city.iter_buildings() for f in b.floors}
    for p in base:
        # Thousands of facade panels are already covered by the building
        # envelope; do not triangulate every window for parcel-level planning.
        if p.owner_id in building_owners and p.semantic_class not in {'floor_slab','entrance_canopy'}:continue
        if p.semantic_class in GROUND or p.semantic_class in {'frontage_connector','parcel_walkway'}:continue
        if p.center.z-p.size.z/2<4.5 and p.center.z+p.size.z/2>.22:
            occupied.append(primitive_footprint(p).buffer(.35))
            removable=(p.semantic_class in REMOVABLE and not p.metadata.get('site_system')
                       and not p.metadata.get('planting_system'))
            obstacle_ids.append(p.id if removable else None)
            if removable:decorations[p.id]=p
    occupied.extend(box_shape(b.footprint).buffer(1) for b in city.iter_buildings())
    obstacle_ids.extend(None for _ in city.iter_buildings())
    tree=s.STRtree(occupied) if occupied else None
    candidates=[]
    for district in city.districts:
        for parcel in district.parcels:
            function=compiler._parcel_function(parcel,district.function)
            if function=='industrial':continue
            priority=0 if function in {'commercial','mixed_use','public_service','public'} else 1
            candidates.append((priority,compiler._parcel_seed(parcel.id,VERSION),district,parcel))
    candidates.sort(key=lambda row:(row[0],row[1]))
    additions=[];holes=[];skips=Counter();removed_ids=set()
    for _,seed,district,parcel in candidates:
        if report['placed_count']>=count:break
        shape=parcel_shape(parcel);bids={b.id for b in parcel.buildings}
        connections=[fp for p,fp in frontages if p.metadata.get('building_id') in bids]
        if not connections:
            skips['no_entrance_connection']+=1;continue
        nearby=[int(i) for i in tree.query(shape)] if tree is not None else []
        hard=s.union_all([occupied[i] for i in nearby if obstacle_ids[i] is None])
        soft={obstacle_ids[i]:occupied[i] for i in nearby if obstacle_ids[i] is not None and obstacle_ids[i] not in removed_ids}
        free_hard=shape.buffer(-.2).difference(hard.union(roads).union(water))
        strict_free=free_hard.difference(s.union_all(list(soft.values())))
        links=s.union_all(connections).intersection((free_hard if decor_budget else strict_free).buffer(-1.05))
        if links.is_empty:skips['no_safe_connection']+=1;continue
        existing_paths=s.union_all([primitive_footprint(p) for p in base
            if p.owner_id==parcel.id and p.semantic_class=='parcel_walkway']).union(s.union_all(connections))
        x0,y0,x1,y1=shape.bounds;placed=False
        for attempt in range(360 if decor_budget else 180):
            relaxed=bool(decor_budget and attempt>=180)
            free=free_hard if relaxed else strict_free
            x=x0+((seed%997/997+attempt*.61803398875)%1)*(x1-x0)
            y=y0+((seed%991/991+attempt*.41421356237)%1)*(y1-y0)
            if any(math.dist((x,y),n['center_xy'])<spacing for n in report['entrances']):continue
            point=s.Point(x,y)
            if not free.contains(point):continue
            root=nearest_points(point,links)[1]
            if point.distance(root)>85:continue
            # Face the nearest road normal, not an arbitrary path bend. With
            # no road data, use the already-authored street connector.
            toward=root
            if city.road_network.segments:
                road=min(city.road_network.segments,key=lambda r:line_shape(r.centerline).distance(point))
                toward=nearest_points(point,line_shape(road.centerline))[1]
            record=assets[(report['placed_count']+attempt//30)%len(assets)]
            spec=record.metadata['metro_placement'];sx,sy,sz=record.dimensions_m
            front={'+X':0,'+Y':math.pi/2,'-X':math.pi,'-Y':-math.pi/2}[spec['front_axis']]
            facing=math.atan2(toward.y-y,toward.x-x);angle=facing-front
            footprint=transformed_rect((-sx/2,-sy/2,sx/2,sy/2),(x,y),angle)
            pad=transformed_rect((-sx/2-1.5,-sy/2-1.5,sx/2+1.5,sy/2+1.5),(x,y),angle)
            if not free.covers(pad):skips['candidate_obstructed']+=1;continue
            if pad.intersects(existing_paths.buffer(.25)):skips['candidate_covers_path']+=1;continue
            displaced={key for key,geometry in soft.items() if geometry.intersects(pad)} if relaxed else set()
            if len(displaced)>decor_budget:skips['decoration_budget_exceeded']+=1;continue
            if relaxed:free=free_hard.difference(s.union_all([v for k,v in soft.items() if k not in displaced]))
            actual_links=s.union_all(connections).intersection(free.buffer(-1.05))
            if actual_links.is_empty:continue
            root=nearest_points(point,actual_links)[1]
            distance=(sx if spec['front_axis'].endswith('X') else sy)/2+1.3
            goal=(x+math.cos(facing)*distance,y+math.sin(facing)*distance)
            path=route_in_polygon((root.x,root.y),goal,free.difference(footprint.buffer(.25)),budget=3000)
            if not path:skips['candidate_unreachable']+=1;continue
            path_shape=s.LineString(path).buffer(.9,quad_segs=4)
            if not free.covers(path_shape):continue
            prefix=f'{parcel.id}_metro_entrance'
            meta={'metro_system':VERSION,'parcel_id':parcel.id,'district_id':district.id,
                  'exterior_only':True,'interactive':False,'underground_navigation':False,
                  'asset_id':record.asset_id,'ground_elevation_m':.13}
            center_z=.13+sz*(.5-record.metadata.get('ground_anchor_fraction',0))
            mesh=compiler._mesh(prefix,parcel.id,Vec3(x,y,center_z),Vec3(sx,sy,sz),math.degrees(angle),
                'metro_entrance','street_furniture','roads',collision_enabled=True,
                instance_key=f'asset_{record.asset_id}',metadata={**meta,'resolved_asset':True,
                    'asset_category':record.category,'asset_source':record.source,'asset_license':record.license_id,
                    'asset_geometry_path':str(compiler.asset_registry.resolve_path(record.geometry_path)),
                    'collision_policy':'static_envelope_not_walkable_station'})
            hole=s.GeometryCollection();opening=spec.get('opening_unit_bounds')
            if opening:
                hole=transformed_rect((opening[0]*sx,opening[1]*sy,opening[2]*sx,opening[3]*sy),(x,y),angle)
                if not footprint.covers(hole):raise ValueError('Reviewed opening lies outside asset envelope')
                holes.append(hole)
            padmesh=polygon_mesh(prefix+'_forecourt',parcel.id,pad.difference(hole),.105,.10,
                'metro_forecourt','paving_light',collision=True,metadata={k:v for k,v in meta.items() if k!='asset_id'})
            walkway=polygon_mesh(prefix+'_path',parcel.id,path_shape.difference(pad),.098,.07,
                'metro_access_path','permeable_paver',collision=True,metadata={'metro_system':VERSION,
                    'parcel_id':parcel.id,'path_width_m':1.8,'routes':[path],'underground_navigation':False})
            additions.extend(p for p in [mesh,padmesh,walkway] if p is not None)
            report['entrances'].append({'id':prefix,'parcel_id':parcel.id,'asset_id':record.asset_id,
                'center_xy':[x,y],'rotation_z_deg':math.degrees(angle),'path':path,'entrance_approach':list(goal),
                'removed_decoration_ids':sorted(displaced),
                'opening_polygon':list(hole.exterior.coords) if not hole.is_empty else None})
            removed_ids.update(displaced)
            report['placed_count']+=1;placed=True;break
        if not placed:skips['no_safe_reachable_space']+=1
    originals=[];cut=s.union_all(holes);updated=[]
    for p in base:
        if p.id in removed_ids:continue
        if not cut.is_empty and p.semantic_class in GROUND and primitive_footprint(p).intersects(cut):
            footprint=primitive_footprint(p);remaining=footprint.difference(cut)
            if remaining.is_empty:raise ValueError('Metro opening would remove entire ground primitive')
            originals.append(to_primitive(p))
            p=polygon_mesh(p.id,p.owner_id,remaining,p.center.z+p.size.z/2,p.size.z,p.semantic_class,
                p.material_id,collision=p.collision_enabled,layer=p.layer_id,
                metadata={**p.metadata,'metro_ground_cut':True})
        updated.append(p)
    scene.primitives=updated+additions
    scene.metadata['metro_ground_originals']=originals
    scene.metadata['metro_removed_decorations']=[{'index':i,'primitive':to_primitive(p)}
        for i,p in enumerate(base) if p.id in removed_ids]
    report.update(status='placed' if additions else 'no_safe_sites',skips=dict(skips),
        new_primitives=len(additions),new_asset_instances=report['placed_count'],cut_surface_count=len(originals),
        removed_decoration_ids=sorted(removed_ids),removed_decoration_count=len(removed_ids))
    return report
