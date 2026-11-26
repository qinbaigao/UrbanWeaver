"""Authorized, bounded interior-core retrofit for rectangular paper fixtures.

Preserves all furnished rooms, their identities and the exterior; no fallback
deletion of furniture, stairs, collisions or fine-room walls is permitted.
"""
from copy import deepcopy
from dataclasses import asdict,replace

from cityg.schemas import Bounds2D,Door,Point2D,Room,VerticalConnector
from cityg.subtree_transactions import _refresh_world_program


def plan_transport_retrofit(city,building_ids,*,authorized=False):
    if not authorized:raise PermissionError('Interior core/ordinary-room changes require explicit authorization')
    building_ids=set(building_ids)
    if not building_ids:raise ValueError('At least one target building is required')
    candidate=deepcopy(city);changes=set();receipts=[]
    for b in candidate.iter_buildings():
        if b.id not in building_ids:continue
        if abs(float(b.metadata.get('orientation_deg',0))%360)>1e-7:
            raise ValueError('This bounded retrofit requires an unrotated building')
        if b.metadata.get('transport_core_retrofit'):raise ValueError('Already retrofitted')
        if [f.level for f in b.floors]!=list(range(len(b.floors))):
            raise ValueError('Retrofit requires contiguous, ordered floors starting at ground level')
        stairs=[c for c in b.vertical_connectors if c.connector_type=='stairs']
        if len(stairs)!=1 or len(b.vertical_connectors)!=1:raise ValueError('Expected one existing stair core')
        stair=stairs[0];cy=stair.bounds.center.y
        corridor=next(r for r in b.floors[0].rooms if r.function=='corridor')
        if corridor.bounds.depth<2*corridor.bounds.width:raise ValueError('Only north/south corridor retrofit supported')
        band=Bounds2D(b.footprint.min_x,cy-3.2,corridor.bounds.min_x,cy+3.2)
        if band.width<5.6:raise ValueError('Insufficient west wing for stairs and elevator')
        stair_box=Bounds2D(band.min_x+.35,cy-1.2,band.min_x+2.67,cy+1.2)
        lift_box=Bounds2D(band.max_x-2.8,cy-1.2,band.max_x-.2,cy+1.2)
        if stair_box.overlaps_area(lift_box):raise ValueError('Proposed cores overlap')
        before=asdict(stair);stair.bounds=stair_box
        stair.metadata={**stair.metadata,'transport_retrofit':True}
        lift=VerticalConnector(f'{b.id}_transport_elevator','elevator',lift_box,0,len(b.floors)-1,True,
            {'transport_elevator_version':1,'entrance_rotation_deg':90,'transport_retrofit':True})
        b.vertical_connectors.append(lift);changes.update((b.id,stair.id,lift.id))
        room_changes=[];door_changes=[]
        for f in b.floors:
            main=next(r for r in f.rooms if r.id.endswith('_corridor'))
            affected=[r for r in f.rooms if r.bounds.overlaps_area(band)]
            if not affected:raise ValueError('No realizable ordinary-room reserve')
            for r in affected:
                if r.function=='corridor' or r.metadata.get('room_design') or any(o.room_id==r.id for o in f.objects):
                    raise ValueError(f'Retrofit would touch furnished/locked room {r.id}')
                if r.bounds.min_x!=band.min_x or r.bounds.max_x!=band.max_x:
                    raise ValueError('Unsupported partial-width reserve')
                old=asdict(r.bounds)
                if r.bounds.min_y<band.min_y and r.bounds.max_y<=band.max_y:
                    new=replace(r.bounds,max_y=band.min_y)
                elif r.bounds.max_y>band.max_y and r.bounds.min_y>=band.min_y:
                    new=replace(r.bounds,min_y=band.max_y)
                else:raise ValueError('Would remove or split an ordinary room; larger redesign needed')
                if min(new.width,new.depth)<2 or new.width*new.depth<12:raise ValueError('Residual room too small')
                r.bounds=new;changes.add(r.id)
                room_changes.append({'room_id':r.id,'before':old,'after':asdict(new)})
                for d in f.doors:
                    if r.id not in (d.room_a_id,d.room_b_id):continue
                    if {d.room_a_id,d.room_b_id}!={r.id,main.id}:raise ValueError('Private-room door needs separate adaptation')
                    d.position=Point2D(new.max_x,new.center.y);changes.add(d.id);door_changes.append(d.id)
            lobby=Room(f'{f.id}_transport_lobby','Core lobby','corridor',band,f.height_m,
                metadata={'corridor_role':'core_lobby','transport_retrofit':True})
            f.rooms.append(lobby)
            passage=Door(f'{f.id}_transport_lobby_passage',lobby.id,main.id,
                Point2D(band.max_x,cy),6.0,'interior',False)
            f.doors.append(passage)
            f.metadata['spatial_layout']={**f.metadata.get('spatial_layout',{}),'status':'accepted',
                'open_boundaries':[*f.metadata.get('spatial_layout',{}).get('open_boundaries',[]),[lobby.id,main.id]]}
            f.metadata['core_bounds']=asdict(Bounds2D(stair_box.min_x,cy-1.2,lift_box.max_x,cy+1.2))
            changes.update((f.id,lobby.id,passage.id))
        b.metadata['transport_core_retrofit']={'version':1,'authorized':True,'band':asdict(band),
            'preserve_fine_rooms':True,'preserve_exterior':True}
        receipts.append({'building_id':b.id,'band':asdict(band),'stair_before':before,'stair_after':asdict(stair),
            'elevator':asdict(lift),'changed_rooms':room_changes,'changed_door_ids':door_changes})
    if {r['building_id'] for r in receipts}!=set(building_ids):raise ValueError('Unknown target building')
    locked_changes={n.entity_id for n in city.world_program.nodes if n.locked}&changes
    if locked_changes:
        raise ValueError(f'Retrofit would modify explicitly locked entities: {sorted(locked_changes)}')
    _refresh_world_program(candidate,producer='authorized_transport_core_retrofit',changed_ids=changes)
    return candidate,{'authorized':True,'buildings':receipts,'changed_ids':sorted(changes),
        'original_mutated':False,'fine_rooms_changed':False,'exterior_changed':False}
