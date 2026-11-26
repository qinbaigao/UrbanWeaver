"""Opt-in, collision-bearing elevator geometry for scripted transport.

Unlike the legacy display cabin, this is an empty cabin with floor, walls,
roof and sliding panels. Layout clearance and shaft floor openings are the
caller's responsibility and must be independently checked after compilation.
"""
import math

from cityg.geometry.model import InteractionStateMachine, StateTransition, Vec3


def compile_transport_elevator(compiler, connector, floors, scene):
    served=[floors[i] for i in range(connector.from_level,connector.to_level+1) if i in floors]
    if len(served)<2:raise ValueError('Transport elevator needs at least two realized stops')
    b=connector.bounds;w,d=b.width,b.depth
    yaw=float(connector.metadata.get('entrance_rotation_deg',0))
    if not math.isfinite(yaw) or yaw%90:raise ValueError('Transport elevator currently requires cardinal orientation')
    if yaw%180:w,d=d,w
    if w<2.2 or d<2.4:raise ValueError('Transport elevator requires >=2.2 x 2.4 m shaft')
    if min(f.height_m for f in served)<2.8:raise ValueError('Insufficient elevator headroom')
    machine=f'state_machine__{connector.id}';initial=served[0].elevation_m
    a=math.radians(yaw);c,s=math.cos(a),math.sin(a)
    def box(suffix,xyz,size,semantic,layer,role,**metadata):
        x,y,z=xyz
        p=compiler._box(f'{connector.id}_{suffix}',connector.id,
            Vec3(b.center.x+c*x-s*y,b.center.y+s*x+c*y,z),Vec3(*size),yaw,
            semantic,'industrial_metal',layer,collision_enabled=True,
            metadata={'transport_elevator_version':1,'elevator_id':connector.id,
                'elevator_role':role,'cabin_initial_floor_z_m':initial,
                'state_machine_id':machine if role.startswith('cabin') else None,**metadata})
        if role.startswith('cabin') or role=='landing_door':p.body_type='kinematic'
        scene.primitives.append(p)
    # Doors slide into exterior pockets in a dedicated front plane, not
    # through the shaft side walls. Opening is deliberately narrower than cabin.
    opening=min(1.2,w-.8);height=2.25;panel_w=opening/2
    front=-d/2;back=d/2-.18;floor_depth=back-(front+.10)
    floor_y=(back+front+.10)/2;inside_w=w-.4
    for f in served:
        layer=f'floor:{f.id}';z=f.elevation_m;h=f.height_m
        for side,sign in [('left',-1),('right',1)]:
            box(f'level_{f.level:02d}_shaft_{side}',(sign*(w/2-.07),.10,z+h/2),
                (.14,d-.20,h),'elevator_shaft',layer,'shaft',served_level=f.level)
        box(f'level_{f.level:02d}_shaft_back',(0,d/2-.07,z+h/2),
            (w,.14,h),'elevator_shaft',layer,'shaft',served_level=f.level)
        # Closed front facade outside the opening; protects the shaft even
        # when an inactive landing is represented without a cabin behind it.
        side_w=(w-opening)/2
        for sign in (-1,1):
            box(f'level_{f.level:02d}_front_{sign}',(sign*(opening/2+side_w/2),front-.07,z+h/2),
                (side_w,.12,h),'elevator_shaft',layer,'shaft',served_level=f.level)
        box(f'level_{f.level:02d}_header',(0,front-.07,z+height+(h-height)/2),
            (opening,.12,h-height),'elevator_shaft',layer,'shaft',served_level=f.level)
        # Threshold bridges the small gap from landing edge to cabin floor.
        box(f'level_{f.level:02d}_sill',(0,front-.05,z-.04),
            (opening,.30,.08),'elevator_sill',layer,'sill',served_level=f.level)
        for sign in (-1,1):
            box(f'level_{f.level:02d}_door_{sign}',(sign*panel_w/2,front-.17,z+height/2),
                (panel_w,.035,height),'elevator_landing_door',layer,'landing_door',
                served_level=f.level,slide_local_m=[sign*(panel_w+.03),0,0])
    layer=f'floor:{served[0].id}'
    box('cabin_floor',(0,floor_y,initial-.05),(inside_w,floor_depth,.1),
        'elevator_cabin',layer,'cabin_floor')
    box('cabin_roof',(0,floor_y,initial+2.45),(inside_w,floor_depth,.1),
        'elevator_cabin',layer,'cabin_roof')
    for sign in (-1,1):
        box(f'cabin_side_{sign}',(sign*(inside_w/2-.035),floor_y+.05,initial+1.2),
            (.07,floor_depth-.10,2.4),'elevator_cabin',layer,'cabin_wall')
    box('cabin_back',(0,back-.035,initial+1.2),(inside_w,.07,2.4),
        'elevator_cabin',layer,'cabin_wall')
    for sign in (-1,1):
        box(f'cabin_door_{sign}',(sign*panel_w/2,front+.13,initial+height/2),
            (panel_w,.035,height),'elevator_cabin_door',layer,'cabin_door',
            slide_local_m=[sign*(panel_w+.03),0,0])
    states={f'level_{f.level:02d}':{'current_level':f.level,'cabin_z_m':f.elevation_m,
        'cabin_floor_z_m':f.elevation_m,'nav_passable':False} for f in served}
    scene.state_machines.append(InteractionStateMachine(machine,connector.id,'elevator_controller',
        f'level_{served[0].level:02d}',states,[StateTransition(f'go_to_level_{t.level:02d}',
            f'level_{f.level:02d}',f'level_{t.level:02d}',max(1.,abs(t.elevation_m-f.elevation_m)/.8))
            for f in served for t in served if f.level!=t.level]))
