"""Read-only structural preflight; graph paths are not embodied routes.

Reports a conservative corridor-core bottleneck for axis-aligned rectangular
buildings. Does not invent elevators, remove stairs or relabel graph success.
"""
from cityg.runtime.transport_planning import primitive_box
from cityg.runtime.mobile_geometry import xy_bounds


def audit_transport_readiness(city,scene,endpoint_building_ids,robot):
    records=[];issues=[]
    for building_id in endpoint_building_ids:
        b=next(b for b in city.iter_buildings() if b.id==building_id)
        elevators=[c for c in b.vertical_connectors if c.connector_type=='elevator']
        physical=[]
        for c in elevators:
            parts=[p for p in scene.primitives if p.owner_id==c.id]
            roles=[p.metadata.get('elevator_role') for p in parts]
            machines=[m for m in scene.state_machines if m.owner_id==c.id and m.state_type=='elevator_controller']
            if (not parts or not all(p.collision_enabled and p.metadata.get('transport_elevator_version')==1 for p in parts)
                    or roles.count('cabin_floor')!=1 or roles.count('cabin_door')!=2
                    or 'cabin_roof' not in roles or 'cabin_wall' not in roles or len(machines)!=1):continue
            levels={v.get('current_level') for v in machines[0].states.values() if 'cabin_floor_z_m' in v}
            if not set(range(c.from_level,c.to_level+1))<=levels:continue
            if any(sum(p.metadata.get('elevator_role')=='landing_door'
                    and p.metadata.get('served_level')==level for p in parts)!=2 for level in levels):continue
            physical.append(c.id)
        if not physical:issues.append({'building_id':b.id,'code':'missing_realized_transport_elevator'})
        bottlenecks=[]
        for f in b.floors:
            corridors=[r for r in f.rooms if r.function=='corridor']
            for connector in b.vertical_connectors:
                if connector.connector_type!='stairs':continue
                parts=[p for p in scene.primitives if p.owner_id==connector.id
                    and p.layer_id==f'floor:{f.id}' and p.collision_enabled and p.semantic_class=='stair_tread'
                    and p.center.z+p.size.z/2>f.elevation_m+.05]
                if not parts:continue
                bounds=[xy_bounds(primitive_box(p)) for p in parts]
                x0,y0=min(p[0] for p in bounds),min(p[1] for p in bounds)
                x1,y1=max(p[2] for p in bounds),max(p[3] for p in bounds)
                for r in corridors:
                    if not (r.bounds.min_x<=x0<x1<=r.bounds.max_x and r.bounds.min_y<y0<y1<r.bounds.max_y):continue
                    # Only a diagnosed north/south straight corridor; other
                    # layouts require actual route search rather than guessing.
                    if r.bounds.depth<r.bounds.width*2:continue
                    slots=[x0-r.bounds.min_x,r.bounds.max_x-x1]
                    needed=min(robot.size[:2])+.02
                    if max(slots)<needed:
                        row={'floor_id':f.id,'level':f.level,'corridor_id':r.id,
                            'connector_id':connector.id,'corridor_width_m':r.bounds.width,
                            'compiled_stair_width_m':x1-x0,'side_gaps_m':slots,
                            'minimum_robot_width_with_margin_m':needed,
                            'stair_primitive_ids':[p.id for p in parts],
                            'scope':'direct_in_corridor_bypass_only_not_all_room_detours'}
                        bottlenecks.append(row)
        if bottlenecks:issues.append({'building_id':b.id,'code':'stair_blocks_direct_corridor_bypass',
            'affected_levels':[r['level'] for r in bottlenecks]})
        ordinary=[]
        for f in b.floors:
            ordinary.extend({'room_id':r.id,'floor_id':f.id,'function':r.function,
                             'area_m2':r.bounds.width*r.bounds.depth}
                for r in f.rooms if r.function!='corridor' and not r.metadata.get('room_design')
                and not any(o.room_id==r.id for o in f.objects))
        records.append({'building_id':b.id,'entrance':{'x':b.entrance.x,'y':b.entrance.y},
            'existing_elevators':[c.id for c in elevators],'physical_elevators':physical,
            'corridor_bottlenecks':bottlenecks,'unfurnished_room_candidates':ordinary})
    return {'schema_version':'cityg.transport_readiness.v1','ok':not issues,
        'status':'structural_adaptation_required' if issues else 'preflight_only',
        'issues':issues,'buildings':records,'scene_mutated':False,
        'full_route_verified':False,'model_calls':0,
        'required_decision':('Authorize a bounded interior core/circulation retrofit, preserving fine rooms and stairs, '
            'or select an exterior lift/access extension. Neither is silently applied.') if issues else None}
