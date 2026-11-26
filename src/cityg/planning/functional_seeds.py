"""Small functional references grounded by the existing metric layout solver.

These are minimum-inventory witnesses, not aesthetics or infeasibility proofs.
They neither shrink assets nor waive door, use-space or circulation checks.
"""
from collections import Counter
from copy import deepcopy

from cityg.planning.interiors import FurnishingProgram, ASSET_CATALOG
from cityg.planning.room_design import RoomDesign


def inventory_programs(room, inventory):
    counts=Counter()
    for item in inventory:counts[item['category']]=max(counts[item['category']],item['min_count'])
    if not counts or sum(counts.values())>32:return
    for seating_sides in [('front','back'),('left','right')]:
        left=counts.copy();groups=[]
        def group(category, members=(), wall=False):
            gid=f'functional_{len(groups):02d}'
            groups.append({'id':gid,'zone':'main','anchor':{'id':gid+'_anchor','category':category},
                'members':[{'id':gid+f'_member_{i:02d}','category':c,'side':s,'slot':slot,
                    'gap_m':gap,'face_anchor':face} for i,(c,s,slot,gap,face) in enumerate(members)],
                'placement':{'mode':'wall' if wall else 'free','wall':'auto','contact':'auto','max_gap_m':.25}})
        for table,chair in [('meeting_table','meeting_chair'),('dining_table','dining_chair'),('desk','office_chair')]:
            for i in range(left[table]):
                n=(left[chair]+left[table]-i-1)//(left[table]-i)
                # Stay inside RoomDesign's member limit. Unsupported references
                # are skipped; the Room Agent can still propose another layout.
                if n>8:return
                seats=[]
                parts=[n] if table=='desk' and n<=2 else [(n+1)//2,n//2]
                for side,number in zip(seating_sides,parts):
                    for k in range(number):seats.append((chair,side,k-(number-1)/2,.17,True))
                group(table,seats);left[chair]-=n
            left[table]=0
        for _ in range(left['sofa']):
            members=[('coffee_table','front',0,.45,False)] if left['coffee_table'] else []
            group('sofa',members,wall=True)
            if members:left['coffee_table']-=1
        left['sofa']=0
        wall_categories={'bed','wardrobe','cabinet','bookcase','storage_rack','kitchen_counter',
                         'display_shelf','waiting_bench','reception_desk'}
        for category,n in left.items():
            for _ in range(n):group(category,wall=category in wall_categories)
        if len(groups)>16:return
        design=RoomDesign('Grounded minimum functional reference','minimal',
            ({'id':'main','purpose':room.function,'position':'center'},),tuple(groups))
        design.validate(ASSET_CATALOG)
        yield FurnishingProgram(room.id,room.function,'minimal functional',.5,(),(),design)


def find_inventory_witness(building, floor, room, inventory, resolver, *, seed=17):
    from cityg.planning.interiors import FloorDetailAgent
    from cityg.planning.room_metric_frame import place_metric_room
    if any(o.room_id==room.id for o in floor.objects):
        return None,{'status':'existing_content_preserved','tested':0}
    errors=[]
    for program in inventory_programs(room,inventory):
        try:
            objects=place_metric_room(FloorDetailAgent(asset_resolver=resolver),building,floor,
                                      deepcopy(room),program,seed)
            if objects is None:raise ValueError('Metric grounding unavailable')
            actual=Counter(o.category for o in objects)
            if any(actual[i['category']]<i['min_count'] for i in inventory):
                raise ValueError('Reference does not cover requested inventory')
            return program,{'status':'metric_witness','tested':len(errors)+1,'object_count':len(objects),
                'scope':'Current assets, room and doors; compiled transaction still required'}
        except ValueError as exc:errors.append(str(exc))
    return None,{'status':'no_reference_witness','tested':len(errors),'errors':errors,
                 'not_a_proof_of_infeasibility':True}
