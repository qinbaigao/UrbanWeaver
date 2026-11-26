"""Budgeted room reference choice over compatible, version-bound candidates."""
from dataclasses import asdict
import hashlib
import json
import math
import time

from cityg.agents.requirement import AgentAttempt, AgentGenerationError, _parse_json_object
from cityg.services.interfaces import ChatMessage
from cityg.transactions import fingerprint


def coverage_key(building, room):
    if building.function == 'public_service': return 'public_service'
    if room.function in {'office','open_office','meeting_room','break_room'}: return 'office'
    if building.function == 'residential': return 'residential'
    if room.function in {'shop','reception','restaurant','cafe'}: return 'commercial'
    return building.function


def balanced_candidates(candidates):
    """Round-robin functional groups; stable fallback, never an LLM decision."""
    buckets={}
    for row in candidates:
        b,_,r,_=row
        buckets.setdefault((coverage_key(b,r),r.function,b.id),[]).append(row)
    result=[]
    while buckets:
        for key in list(buckets):
            result.append(buckets[key].pop(0))
            if not buckets[key]: del buckets[key]
    return result


def validate_choice(value, offered, library, requirement, options):
    if not isinstance(value,dict) or set(value)!={'choices'} or not isinstance(value['choices'],list):
        raise ValueError('Return choices only')
    choices=value['choices']; seen=set(); buildings={}
    if not 1<=len(choices)<=options['max_rooms']: raise ValueError('Room selection exceeds budget')
    by_id={r.id:(b,f,r,cs) for b,f,r,cs in offered}
    for choice in choices:
        fields={'room_id','prototype_id','quarter_turns','reason','requirement_quote','spacing_adjustments'}
        if not isinstance(choice,dict) or not fields<=set(choice) or set(choice)-fields-{'design_adjustments','goal_ids'}:
            raise ValueError('Invalid choice fields')
        rid=choice['room_id']
        if rid not in by_id or rid in seen: raise ValueError('Unknown or repeated room ID')
        seen.add(rid); b,f,_,cs=by_id[rid]
        if type(choice['quarter_turns']) is not int:
            raise ValueError('quarter_turns must be an integer, not a boolean')
        if not any(c['prototype_id']==choice['prototype_id'] and c['quarter_turns']==choice['quarter_turns'] for c in cs):
            raise ValueError('Prototype/orientation not compatible with selected room')
        if not isinstance(choice['reason'],str) or not choice['reason'].strip(): raise ValueError('A reason is required')
        quote=choice['requirement_quote']
        if not isinstance(quote,str) or (quote and quote not in requirement):
            raise ValueError('requirement_quote must be an exact excerpt, or empty for an inferred preference')
        buildings.setdefault(b.id,set()).add(f.level)
        if len(buildings)>options['max_buildings'] or any(len(v)>options['max_floors_per_building'] for v in buildings.values()):
            raise ValueError('Building/floor detail budget exceeded')
        # Validate the personalized design before any scene mutation.
        personalize_reference(library.materialize(choice['prototype_id']),choice['spacing_adjustments'],
                              options['variation_limit'])
        if choice.get('design_adjustments'):
            from cityg.planning.reference_variations import personalize_design
            personalize_design(library.materialize(choice['prototype_id']),choice['design_adjustments'],
                               library,options.get('design_variation'))
        goals=choice.get('goal_ids',[])
        if not isinstance(goals,list) or any(not isinstance(g,str) for g in goals) or len(set(goals))!=len(goals):
            raise ValueError('Invalid goal IDs')
    return choices


def personalize_reference(prototype, adjustments, variation_limit):
    from dataclasses import replace
    from cityg.planning.room_design import RoomDesign
    from cityg.planning.interiors import ASSET_CATALOG
    if not isinstance(adjustments,list) or len(adjustments)>16: raise ValueError('Invalid spacing adjustments')
    data=prototype.design.to_dict(); members={m['id']:m for g in data['groups'] for m in g['members']}
    seen=set()
    for item in adjustments:
        if not isinstance(item,dict) or set(item)!={'member_id','gap_scale'}: raise ValueError('Invalid spacing patch')
        mid=item['member_id']; scale=item['gap_scale']
        if mid not in members or mid in seen: raise ValueError('Unknown or repeated furniture member')
        if (type(scale) not in (float,int) or not math.isfinite(scale)
                or not 1-variation_limit<=scale<=1+variation_limit):
            raise ValueError('Spacing change exceeds variation budget')
        seen.add(mid); members[mid]['gap_m']*=scale
    # Validation retains original inventory, asset bindings, contact policies,
    # reserved aisles and inter-group relations. Invalid new gaps are rejected.
    return replace(prototype,design=RoomDesign.from_dict(data,ASSET_CATALOG))


class RoomReferenceAgent:
    def __init__(self, service, *, max_calls=2):
        if type(max_calls) is not int or not 1 <= max_calls <= 3:
            raise ValueError('Room reference budget must be 1..3 calls')
        self.service=service; self.max_calls=max_calls

    def plan(self, city, candidates, library, requirement, options):
        offered=balanced_candidates(candidates)
        from cityg.interior_requirements import inventory_for
        from cityg.refinement.inventory_allocation import allocate_remaining_inventory
        offered.sort(key=lambda row:not bool(inventory_for(row[0],row[1].level,row[2].function)))
        offered=offered[:40]
        if not offered: return {'status':'no_compatible_candidates','choices':[],'attempts':[]}, ()
        ids={c['prototype_id'] for _,_,_,cs in offered for c in cs}
        prototypes=[]
        for key in sorted(ids):
            row=library.rooms[key]; design=library.materialize(key).design
            from cityg.planning.reference_variations import variation_context
            from collections import Counter
            counts=Counter(i['category'] for g in design.groups for i in [g['anchor'],*g['members']])
            prototypes.append({'id':key,'inventory':dict(counts),'intent':row['intent'],'occupants':row['occupants'],
                'hard_constraints':row['hard_constraints'],
                'design_variation':variation_context(library.materialize(key),library,options.get('design_variation')),
                'spacing_members':[{'member_id':m['id'],'gap_m':m['gap_m']} for g in design.groups for m in g['members']]})
        from cityg.design_goals import goal_context
        goals=goal_context(city.metadata.get('design_goals',[]),'room')
        payload={'instruction':requirement,'budget':options,'shared_design_goals':goals,
            'rooms':[{'room_id':r.id,'building_id':b.id,'floor_level':f.level,'function':r.function,
                      'floor_function_inventory_targets':inventory_for(b,f.level,r.function),
                      'allocated_room_inventory_targets':allocate_remaining_inventory(b,f,r.function).get(r.id,[]),
                      'coverage_group':coverage_key(b,r),'bounds':asdict(r.bounds),'candidates':cs}
                     for b,f,r,cs in offered], 'prototypes':prototypes,
            'candidate_limit':40,'total_candidate_rooms':len(candidates)}
        def obj(properties): return {'type':'object','additionalProperties':False,
                                    'properties':properties,'required':list(properties)}
        from cityg.planning.reference_variations import variation_limits
        limits=variation_limits(options.get('design_variation'))
        variation_schema=obj({
            'group_copies':{'type':'array','minItems':0,'maxItems':limits['max_group_copies'],'items':obj({
                k:{'type':'string'} for k in ('source_group_id','new_group_id','zone_id')})},
            'zone_positions':{'type':'array','minItems':0,'maxItems':limits['max_zone_moves'],'items':obj({
                'zone_id':{'type':'string'},'position':{'type':'string','enum':['north','south','east','west']}})},
            'asset_choices':{'type':'array','minItems':0,'maxItems':limits['max_asset_changes'],'items':obj({
                'category':{'type':'string'},'asset_id':{'type':'string'}})}})
        choice_schema=obj({
            'room_id':{'type':'string','enum':[r.id for _,_,r,_ in offered]},
            'prototype_id':{'type':'string','enum':sorted(ids)},'quarter_turns':{'type':'integer','minimum':0,'maximum':3},
            'reason':{'type':'string','maxLength':300},'requirement_quote':{'type':'string','maxLength':400},
            'spacing_adjustments':{'type':'array','maxItems':16,'items':obj({
                'member_id':{'type':'string'},'gap_scale':{'type':'number',
                    'minimum':1-options['variation_limit'],'maximum':1+options['variation_limit']}})},
            'goal_ids':{'type':'array','maxItems':len(goals),'items':
                {'type':'string','enum':[g['id'] for g in goals]} if goals else {'type':'string'}},
            'design_adjustments':variation_schema})
        schema=obj({'choices':{'type':'array','minItems':1,'maxItems':options['max_rooms'],'items':choice_schema}})
        messages=[ChatMessage('system',
            'You are the Room Reference Agent. Choose compatible room references based on the user instruction. '
            'Fill the detail budget when feasible and spread it across requested functional uses and buildings. '
            'Prioritize explicit floor_function_inventory_targets. These counts apply across ALL selected rooms '
            'of that function on the same floor, not once per room. Compare the offered prototype inventory, '
            'allocated_room_inventory_targets distributes the residual functional bundles to individual rooms; '
            'prefer references satisfying this allocation before aesthetic preferences. The allocator will '
            'recompute residual targets after each committed room. '
            'choose sufficient functional groups and use allowed group copies when capacity is explicitly requested. '
            'Never substitute decorations for missing primary furniture. '
            'Do not select only the easiest room type. Choose only a room-specific candidate/orientation. '
            'Explain each choice; requirement_quote is an EXACT excerpt or empty for an inferred preference. '
            'You may personalize spacing of named furniture members within the variation budget when useful; '
            'empty adjustments are valid. Optionally use design_adjustments within each budget: '
            'replicate a work/table group only for a requested capacity need, move eligible zones '
            'or select offered same-role assets. All coordinates are UNROTATED reference coordinates. '
            'Respect explicit user counts and reference hard constraints. Cite only relevant shared goal IDs. '
            'No inventory deletion, physical asset rescaling, new assets, room geometry changes, '
            'or removal of reference hard constraints. '
            'Selections are proposals: geometry/compiled inventory gates remain authoritative. '
            'Return COMPACT JSON without indentation or blank lines. For no semantic changes use '
            'design_adjustments={"group_copies":[],"zone_positions":[],"asset_choices":[]}. '
            'Do not fill unused array slots or budget with commentary.'),
            ChatMessage('user',json.dumps(payload,ensure_ascii=False))]
        attempts=[]
        for index in range(self.max_calls):
            started=time.monotonic();raw='';usage={};finish=None;error=None
            try:
                method=getattr(self.service,'complete_with_metadata',None)
                if callable(method):
                    reply=method(messages,schema);raw=reply.content;usage=reply.usage;finish=reply.finish_reason
                else: raw=self.service.complete(messages,schema)
                if finish=='length': raise ValueError('Reference selection was truncated')
                choices=validate_choice(_parse_json_object(raw),offered,library,requirement,options)
                for choice in choices:
                    if not set(choice.get('goal_ids',[]))<={g['id'] for g in goals}:
                        raise ValueError('Unknown shared design goal')
            except (ValueError,TypeError,KeyError,RuntimeError) as exc: error=str(exc)
            serialized=tuple({'role':m.role,'content':m.content} for m in messages)
            attempts.append(AgentAttempt(index+1,hashlib.sha256(json.dumps(serialized).encode()).hexdigest(),
                serialized,raw,time.monotonic()-started,error,finish,usage))
            if error is None:
                return {'status':'proposed','choices':choices,'scene_fingerprint':fingerprint(city),
                    'original_instruction':requirement,
                    'selection_mode':'llm_compatible_reference_and_bounded_design',
                    'offered_room_ids':[r.id for _,_,r,_ in offered],
                    'attempts':[asdict(a) for a in attempts]}, tuple(attempts)
            messages.extend([ChatMessage('assistant',raw.rstrip()[:16000]),ChatMessage('user',
                'Rejected: '+error+'. Return a complete COMPACT object, no indentation or repeated whitespace. '
                'Use empty arrays for unused adjustments; keep reasons short.')])
        raise AgentGenerationError('Room reference selection exhausted its budget',attempts)
