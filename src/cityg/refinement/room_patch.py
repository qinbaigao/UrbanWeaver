"""Small, scope-bound room proposals expanded against the accepted design."""
from copy import deepcopy
from cityg.planning.room_design import PLACEMENT_SCHEMA

LOCAL_ROOM_PATCH_SCHEMA = {
    'type':'object','additionalProperties':False,
    'properties':{
        'room_id':{'type':'string'},'reason':{'type':'string','maxLength':500},
        'group_updates':{'type':'array','minItems':1,'maxItems':16,'items':{
            'type':'object','additionalProperties':False,
            'properties':{'group_id':{'type':'string'},'placement':PLACEMENT_SCHEMA},
            'required':['group_id','placement']}},
    },'required':['room_id','reason','group_updates'],
}


def expand_local_patch(data, room, scope):
    """Never reinterpret identifiers or remove members to make a patch fit."""
    if set(data)!={'room_id','reason','group_updates'} or data['room_id']!=room.id:
        raise ValueError('Local patch requires exact room_id, reason and group_updates')
    if not isinstance(data['reason'],str) or len(data['reason'])>500:
        raise ValueError('Local patch needs a bounded textual reason')
    source=room.metadata.get('room_design',{})
    if source.get('status')!='accepted': raise ValueError('Local patch needs an accepted design')
    from cityg.planning.room_design import RoomDesign
    design={k:deepcopy(v) for k,v in source.items() if k in RoomDesign.__dataclass_fields__}
    groups={g['id']:g for g in design['groups']}
    updates=data['group_updates']
    if not isinstance(updates,list) or not 1<=len(updates)<=16:
        raise ValueError('Local patch needs 1..16 group updates')
    seen=set()
    for update in updates:
        if not isinstance(update,dict) or set(update)!={'group_id','placement'}:
            raise ValueError('Each local update requires group_id and placement only')
        key=update['group_id']
        if not isinstance(key,str) or key not in groups or key not in scope or key in seen:
            raise ValueError('Duplicate or out-of-scope local group update')
        seen.add(key)
        groups[key]['placement']=deepcopy(update['placement'])
    # All groups not actually edited are frozen, even within the allowed scope.
    design['protected_groups']=sorted(set(groups)-seen)
    return {'room_id':room.id,'style':design['palette'],'density':.5,
            'requests':[],'relations':[],'design':design,
            '_local_patch':deepcopy(data)}
