"""Immutable contract and scope gate for automatic visual room repairs only."""
from copy import deepcopy

from cityg.planning.room_constraints import placement_policy
from cityg.serialization import to_primitive
from cityg.validation.visual_grounding import room_facts, check_issue


def validate_design(original, candidate):
    # Loaded JSON uses lists; a freshly instantiated RoomDesign uses tuples.
    # Compare semantic payloads, not the in-memory container representation.
    original,candidate=to_primitive(original),to_primitive(candidate)
    old={g['id']:g for g in original.get('groups',[])}
    new={g['id']:g for g in candidate.get('groups',[])}
    if set(old)!=set(new):
        raise ValueError('Visual repair must preserve accepted group IDs')
    for gid,g in old.items():
        a,b=placement_policy(g),placement_policy(new[gid])
        if any(a.get(k)!=b.get(k) for k in ('mode','wall','contact','facing')) or b['max_gap_m']>a['max_gap_m']+1e-6:
            raise ValueError('Preserve original placement contract for '+gid+': '+str(a))
        if any(g.get(k)!=new[gid].get(k) for k in ('anchor','members','zone')):
            raise ValueError('Visual repair must preserve group inventory: '+gid)
    for key in ('group_relations','reserved_areas','zones','surface_items'):
        if original.get(key,[])!=candidate.get(key,[]):
            raise ValueError('Visual repair must preserve '+key)
    for key in ('palette','wall_art','tabletop'):
        if key in original and original[key]!=candidate.get(key):
            raise ValueError('Visual layout repair must preserve '+key)
    old_items=(original.get('furnishing_brief') or {}).get('items',[])
    new_items={i['category']:i for i in (candidate.get('furnishing_brief') or {}).get('items',[])}
    for item in old_items:
        if new_items.get(item['category'],{}).get('minimum',0)<item.get('minimum',0):
            raise ValueError('Visual repair may not lower minimum inventory')


class RoomRepairGuard:
    def __init__(self, city, room_id, issues):
        self.room_id=room_id
        self.before=room_facts(city,room_id)
        self.issues=deepcopy(issues)
        if not self.before.get('supported') or not issues:
            raise ValueError('Visual repair requires supported facts and verified editable groups')
        editable = set()
        for issue in self.issues:
            checked = check_issue(issue, self.before)
            if issue.get('entity_id') != room_id or checked['status'] != 'confirmed':
                raise ValueError('Visual repair issue no longer confirmed for this room')
            current = {r['group_id'] for r in checked['checks'] if r['ok'] is False and r.get('group_id')}
            allowed = current.intersection(issue.get('editable_group_ids', ()))
            if not allowed:
                raise ValueError('No previously authorized group still fails its check')
            issue['editable_group_ids'] = sorted(allowed)
            editable.update(allowed)
        self.editable = sorted(editable)
        _,r=self.target(city)
        self.design=deepcopy(r.metadata['room_design'])
        self.frozen=self.frozen_objects(city)

    def target(self, city):
        return next((f,r) for b in city.iter_buildings() for f in b.floors for r in f.rooms if r.id==self.room_id)

    def frozen_objects(self, city):
        f,_=self.target(city)
        return {o.id:to_primitive(o) for o in f.objects if o.room_id==self.room_id
                and o.metadata.get('group_key') not in self.editable}

    def feedback(self):
        return {'target_group_ids':self.editable,
                'immutable_placement_requirements':{g['id']:deepcopy(g.get('placement',{}))
                                                    for g in self.design['groups']},
                'repair_policy':'Repair realized poses, not accepted requirements. Preserve original '
                    'group IDs, anchors, members, required walls/contact/facing, maximum gaps, '
                    'relations, reserved areas and minimum inventory. Other groups are frozen.'}

    def check_program(self, program):
        validate_design(self.design,to_primitive(program.design))

    def __call__(self, candidate):
        try:
            _,r=self.target(candidate)
            validate_design(self.design,r.metadata.get('room_design',{}))
            if self.frozen_objects(candidate)!=self.frozen:
                raise ValueError('Non-editable furniture changed')
            after=room_facts(candidate,self.room_id,reference=self.before)
            if not after.get('supported'):
                raise ValueError('Original geometry/metric contract unavailable after repair')
            old={row['check_id']:row for row in self.before['checks']}
            rows={row['check_id']:row for row in after['checks']}
            if any(row['ok'] is True and rows.get(key,{}).get('ok') is not True for key,row in old.items()):
                raise ValueError('Previously valid constraint regressed or became unknown')
            if any(row['ok'] is False and old.get(key,{}).get('ok') is not False for key,row in rows.items()):
                raise ValueError('Repair introduced a new independently checked defect')
            for issue in self.issues:
                prior=check_issue(issue,self.before)
                checked=check_issue(issue,after)
                passed={r['check_id'] for r in checked['checks'] if r['ok'] is True}
                failed={r['check_id'] for r in prior['checks'] if r['ok'] is False}
                if checked['status']!='not_supported_by_geometry' or not failed<=passed:
                    raise ValueError('Original issue not resolved under original requirements')
            return {'ok':True,'editable_group_ids':self.editable,'contract_preserved':True}
        except (ValueError,KeyError,StopIteration) as error:
            return {'ok':False,'reason':str(error),'check':'visual_room_repair_contract'}
