"""Independent, bounded room facts. VLM confidence cannot override these checks.

This checks supported identity metric rooms, not perceived mesh quality or
arbitrary polygons. Unknown claims remain pending, never silently pass.
"""
from collections import Counter
from copy import deepcopy
import hashlib
import json
import math

from cityg.issue_rechecks import issue_key
from cityg.planning.room_constraints import direction, wall_contact, placement_policy, circulation_check
from cityg.planning.room_envelope import metric_envelope
from cityg.serialization import to_primitive

CHECKER_VERSION = 'room_facts_v3_attributed'
CODE_CHECK = {'room_group_misaligned':'alignment', 'room_access_blocked':'access',
              'room_function_incomplete':'inventory', 'room_object_outside':'containment'}


def digest(value):
    return hashlib.sha256(json.dumps(to_primitive(value),sort_keys=True).encode()).hexdigest()


def front_verified(obj):
    score=obj.metadata.get('orientation_confidence')
    return (obj.metadata.get('front_axis') in ('+X','-X','+Y','-Y') and
            (score=='reviewed' or (type(score) in (int,float) and math.isfinite(score) and .7<=score<=1)))


def room_facts(city, room_id, *, reference=None):
    """Recompute from objects, never trust cached constraint_checks metadata.

    reference freezes the original design/geometry during after-checks. Changing
    an intended wall or deleting a requirement cannot manufacture resolution.
    """
    target=next(((b,f,r) for b in city.iter_buildings() for f in b.floors
                 for r in f.rooms if r.id==room_id),None)
    if target is None: return {'supported':False,'reason':'room_missing'}
    b,f,r=target
    try: env=metric_envelope(b,f,r)
    except (ValueError,KeyError,TypeError) as error:
        return {'supported':False,'reason':'envelope_unavailable','detail':str(error)}
    if env['status']!='supported':
        return {'supported':False,'reason':env.get('reason','metric_room_not_certified')}
    design=r.metadata.get('room_design',{})
    if design.get('status')!='accepted': return {'supported':False,'reason':'no_accepted_design'}
    brief=design.get('furnishing_brief')
    if brief is None:
        # A valid minimum-reference design can omit the optional prose brief.
        # Preserve its concrete inventory instead of dropping the check.
        counts=Counter(item['category'] for group in design.get('groups',[])
                       for item in [group['anchor'],*group.get('members',[])])
        minimum_inventory=[{'category':category,'minimum':count} for category,count in counts.items()]
    else:
        minimum_inventory=brief.get('items',[])
    contract={'bounds':to_primitive(r.bounds),'metric_bounds':to_primitive(env['bounds']),
        'geometry_frame':to_primitive(env['frame']), 'doors':to_primitive([
        d for d in f.doors if room_id in (d.room_a_id,d.room_b_id)]),
        'groups':design.get('groups',[]),'relations':design.get('group_relations',[]),
        'minimum_inventory':minimum_inventory}
    if reference is not None:
        if any(to_primitive(contract[k]) != to_primitive(reference['contract'].get(k)) for k in contract):
            return {'supported':False,'reason':'protected_room_contract_changed'}
        contract=deepcopy(reference['contract'])
    from cityg.planning.room_metric_frame import restore_metric_object, MetricRoomInfeasible
    try:
        objects=[restore_metric_object(o,b,f,r,env) for o in f.objects if o.room_id==room_id]
    except MetricRoomInfeasible as error:
        return {'supported':False,'reason':'metric_pose_not_certified','detail':str(error)}
    r,f=env['room'],env['floor']
    anchors={o.metadata.get('group_key'):o for o in objects
             if o.id==o.metadata.get('group_anchor_id')}
    checks=[]
    def add(key,kind,ok,**details):
        checks.append({'check_id':key,'kind':kind,'ok':ok,**details})
    for o in objects:
        add('containment:'+o.id,'containment',r.bounds.contains_bounds(o.bounds,tolerance=1e-5),
            object_id=o.id,group_id=o.metadata.get('group_key'))
    for g in contract['groups']:
        a=anchors.get(g['id']);policy=placement_policy(g)
        if a is None:
            add('anchor:'+g['id'],'inventory',False,group_id=g['id']);continue
        if policy['mode']=='wall' and policy.get('wall') in ('north','south','east','west'):
            side,gap=wall_contact(a,r,policy)
            known=front_verified(a)
            add('wall:'+g['id'],'alignment',(side==policy['wall'] and -.02<=gap<=policy['max_gap_m']+.02) if known else None,
                group_id=g['id'],object_id=a.id,expected_wall=policy['wall'],actual_wall=side,gap_m=gap)
    for rule in contract['relations']:
        if rule.get('relation')!='faces' or not rule.get('required'): continue
        a,c=anchors.get(rule['subject']),anchors.get(rule['target'])
        if a is None or c is None: continue
        dx,dy=c.position.x-a.position.x,c.position.y-a.position.y
        norm=math.hypot(dx,dy);front=direction(a)
        cosine=(front[0]*dx+front[1]*dy)/max(norm,1e-9)
        known=front_verified(a)
        add('faces:'+rule['subject']+':'+rule['target'],'alignment',
            cosine>=.94 if known and norm>1e-6 else None,
            group_id=rule['subject'],target_group_id=rule['target'],cosine=cosine,
            orientation_verified=known)
    actual=Counter(o.category for o in objects)
    for item in contract['minimum_inventory']:
        add('minimum:'+item['category'],'inventory',actual[item['category']]>=item['minimum'],
            category=item['category'],minimum=item['minimum'],actual=actual[item['category']])
    walk=circulation_check(objects,r,f,r.bounds.inset(.08))
    access=walk['ok'] if walk.get('reason')!='circulation grid budget exceeded' else None
    if not any(room_id in (d.room_a_id,d.room_b_id) for d in f.doors): access=None
    add('access:'+room_id,'access',access,details=walk)
    # Conservative attribution: removing this object alone must restore the
    # existing all-door circulation checker. Mere proximity is not causality.
    # Multi-blocker/large-room cases remain unknown rather than guessing scope.
    attribution_work = len(objects)**2 * max(1,math.ceil(r.bounds.width/.25)) * max(1,math.ceil(r.bounds.depth/.25))
    for o in objects:
        attributable = None
        if access is True:
            attributable = True
        elif access is False and len(objects)<=64 and attribution_work<=300000:
            without = circulation_check([x for x in objects if x.id!=o.id],r,f,r.bounds.inset(.08))
            if without.get('ok') is True:
                attributable = False
        add('access_object:'+o.id,'access',attributable,
            object_id=o.id,group_id=o.metadata.get('group_key'),
            attribution='single_object_removal_restores_circulation',
            attribution_budget_exceeded=len(objects)>64 or attribution_work>300000)
    return {'supported':True,'source':'deterministic_checker','checker_version':CHECKER_VERSION,
        'entity_id':room_id,'entity_version':next((n.version for n in city.world_program.nodes if n.entity_id==room_id),None),
        'contract':contract,'contract_hash':digest(contract),
        'state_hash':digest({'contract':contract,'objects':objects}),'checks':checks}


def check_issue(issue, facts):
    kind=CODE_CHECK.get(issue.get('issue_code'))
    if not kind or not facts.get('supported'):
        return {'status':'unverified','reason':('unsupported_issue_code' if not kind else
                facts.get('reason','unsupported_room_geometry')),'checks':[]}
    rows=[r for r in facts['checks'] if r['kind']==kind]
    object_ids=issue.get('target_object_ids',[])
    known_objects={r['object_id'] for r in facts['checks']
                   if r['kind']=='containment' and r.get('object_id')}
    if object_ids and not set(object_ids)<=known_objects:
        return {'status':'unverified','reason':'unknown_object','checks':[]}
    if kind=='alignment':
        ids=issue.get('target_group_ids',[])
        if not ids: return {'status':'unverified','reason':'explicit_group_binding_required','checks':[]}
        known={g['id'] for g in facts['contract']['groups']}
        if not set(ids)<=known: return {'status':'unverified','reason':'unknown_group','checks':[]}
        rows=[r for r in rows if r.get('group_id') in ids]
    if kind in ('containment','access') and issue.get('target_group_ids'):
        ids=set(issue['target_group_ids'])
        if not ids<={g['id'] for g in facts['contract']['groups']}:
            return {'status':'unverified','reason':'unknown_group','checks':[]}
        rows=[r for r in rows if r.get('group_id') in ids]
    if object_ids:
        rows=[r for r in rows if r.get('object_id') in object_ids]
    if any(r['ok'] is False for r in rows): status='confirmed'
    elif not rows or any(r['ok'] is None for r in rows): status='unverified'
    else: status='not_supported_by_geometry'
    return {'status':status,'checks':rows}


def _current_room_facts(city, building, floor, room, store, versions, building_hashes):
    """Reuse only this geometry/checker revision on a live CCWP dependency set."""
    from uuid import uuid4
    from cityg.memory import MemoryQuery, MemoryRecord
    dependencies = [building.id, floor.id, room.id]
    dependencies.extend(d.id for d in floor.doors if room.id in (d.room_a_id, d.room_b_id))
    dependencies.extend(o.id for o in floor.objects if o.room_id == room.id)
    if store is None or any(entity not in versions for entity in dependencies):
        return room_facts(city, room.id), 'recomputed'
    if building.id not in building_hashes:
        building_hashes[building.id] = digest(building)
    signature = digest([CHECKER_VERSION, city.id, building_hashes[building.id],
                        sorted((entity, versions[entity]) for entity in dependencies)])
    query = MemoryQuery(scope_id=room.id, kinds=('room_geometry_check',),
                        world_version=versions[room.id], statuses=('accepted',))
    for record in store.query(query):
        if record.content.get('signature') == signature:
            return record.content['facts'], 'reused'
    facts = room_facts(city, room.id)
    if facts.get('supported'):
        store.put(MemoryRecord('room_check__'+uuid4().hex, 'room_geometry_check', 'entity', room.id,
            {'signature': signature, 'dependency_entity_ids': dependencies, 'facts': facts},
            world_version=versions[room.id], producer='room_geometry_checker', validation_status='accepted'))
    return facts, 'recomputed'


def ground_review(city, report, *, memory_store=None):
    """Keep original findings for audit; defer unproven automatic room edits."""
    result=deepcopy(report);cache={}
    sources = {}; building_hashes = {}
    versions = {n.entity_id: n.version for n in city.world_program.nodes}
    rooms={r.id:(b,f,r) for b in city.iter_buildings() for f in b.floors for r in f.rooms}
    for issue in result.get('aggregated_issues',[]):
        rid=issue.get('entity_id')
        if rid not in rooms:
            issue['independent_verification']={'status':'unverified',
                'reason':'no_registered_checker_for_target','checks':[]}
            issue['automatic_repair_allowed']=False
            issue['repair_policy']='unverified_visual_suggestion_requires_review'
            continue
        b,f,r=rooms[rid]
        if rid not in cache:
            cache[rid], sources[rid] = _current_room_facts(city,b,f,r,memory_store,versions,building_hashes)
        if issue.get('target_group_ids'):
            from cityg.refinement.room import resolve_local_group_scope
            try: issue['target_group_ids']=resolve_local_group_scope(r,f,issue['target_group_ids'])
            except ValueError:
                issue.update(independent_verification={'status':'unverified','reason':'unknown_group','checks':[]},
                             editable_group_ids=[], automatic_repair_allowed=False)
                continue
        checked=check_issue(issue,cache[rid]);issue['independent_verification']=checked
        # Affected groups may include innocent neighbors. Only a group with an
        # independently failed object/relation can be handed to the planner.
        editable=sorted({row['group_id'] for row in checked['checks']
                         if row.get('ok') is False and row.get('group_id')})
        issue['editable_group_ids']=editable
        issue['automatic_repair_allowed']=(issue.get('automatic_repair_allowed') is not False
                                          and checked['status']=='confirmed' and bool(editable))
        issue['repair_policy']='geometry_confirmed_room_issue_only'
    result['room_check_sources'] = sources
    result['independent_room_facts']=cache
    result['evidence_diagnostics'] = dict(Counter(
        i['independent_verification'].get('reason',i['independent_verification']['status'])
        for i in result.get('aggregated_issues',[])))
    return result


def resolution_proofs(before_city, after_city, review):
    """Proofs bind original failures, immutable requirements and final versions."""
    proofs={};cache={}
    for issue in review.get('aggregated_issues',[]):
        rid=issue.get('entity_id')
        if rid not in cache:
            before=room_facts(before_city,rid)
            after=room_facts(after_city,rid,reference=before) if before.get('supported') else {}
            cache[rid]=(before,after)
        before,after=cache[rid];old=check_issue(issue,before);new=check_issue(issue,after)
        if old['status']!='confirmed': continue
        failed=[r['check_id'] for r in old['checks'] if r['ok'] is False]
        passed={r['check_id'] for r in new['checks'] if r['ok'] is True}
        ok=(new['status']=='not_supported_by_geometry' and set(failed)<=passed
            and before['contract_hash']==after.get('contract_hash'))
        proofs[issue_key(issue)]={'ok':ok,'before_failed':True,'entity_id':rid,
            'entity_version':after.get('entity_version'),'check_id':CHECKER_VERSION,
            'source':'deterministic_checker','failed_check_ids':failed,
            'before_state_hash':before['state_hash'],'after_state_hash':after.get('state_hash'),
            'contract_hash':before['contract_hash'],'before':old,'after':new}
    return proofs
