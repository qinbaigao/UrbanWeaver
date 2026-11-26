"""Quoted soft organization preferences, distinct from geometric feasibility.

The model interprets intent; code measures the realized access topology. This
does not certify general privacy, aesthetics, or satisfaction of other goals.
"""
from dataclasses import replace
import json

from cityg.agents.context import ProgressiveContext
from cityg.agents.hierarchy import _ProgressiveProgramAgent
from cityg.design_goals import goal_context
from cityg.services.openai_compatible import ModelCompletion


def compose_organization(clauses, goal_ids):
    """Compose quantified access predicates, not model-assigned conflict labels."""
    if not isinstance(clauses,list) or len(clauses)>16:
        raise ValueError('Invalid organization clauses')
    for clause in clauses:
        if (not isinstance(clause,dict) or set(clause)!={'relation','applicability','supporting_goal_ids'}
                or clause['relation'] not in ('all_rooms_direct','some_rooms_indirect','neutral')
                or clause['applicability'] not in ('uniform','qualified','unrelated')):
            raise ValueError('Invalid organization clause')
        refs=clause['supporting_goal_ids']
        if (not isinstance(refs,list) or not refs or any(k not in goal_ids for k in refs)
                or len(set(refs))!=len(refs)):
            raise ValueError('Organization clauses must cite supplied goal IDs')
    operative=[c for c in clauses if c['relation']!='neutral' and c['applicability']!='unrelated']
    predicates={c['relation'] for c in operative if c['applicability']=='uniform'}
    if len(predicates)>1:applicability='conflicting'
    elif any(c['applicability']=='qualified' for c in operative):applicability='qualified'
    elif predicates:applicability='uniform'
    else:applicability='unrelated'
    organization=('private_groups' if 'some_rooms_indirect' in predicates else 'independent') if applicability=='uniform' else 'unspecified'
    return {'applicability':applicability,'organization':organization,
            'supporting_goal_ids':list(dict.fromkeys(k for c in operative for k in c['supporting_goal_ids']))}


def interpret_organization(agent, building):
    goals=goal_context(getattr(agent,'design_goals',[]),'floor')
    if not goals:return {'organization':'unspecified','supporting_goal_ids':[],
                         'reason':'No applicable floor goals'},()
    ids=[g['id'] for g in goals]
    from cityg.planning.baseline import ROOM_FUNCTIONS
    functions=list(ROOM_FUNCTIONS[building.function])
    access_schema={'type':'object','additionalProperties':False,'properties':{
        'predicate':{'type':'string','const':'not_through_room'},
        'function':{'type':'string','enum':functions},
        'applicability':{'type':'string','enum':['uniform','qualified','conflicting','unrelated']},
        'supporting_goal_ids':{'type':'array','minItems':1,'items':{'type':'string','enum':ids}}},
        'required':['predicate','function','applicability','supporting_goal_ids']}
    clause_schema={'type':'object','additionalProperties':False,'properties':{
        'relation':{'type':'string','enum':['all_rooms_direct','some_rooms_indirect','neutral']},
        'applicability':{'type':'string','enum':['uniform','qualified','unrelated']},
        'supporting_goal_ids':{'type':'array','minItems':1,'items':{'type':'string','enum':ids}}},
        'required':['relation','applicability','supporting_goal_ids']}
    schema={'type':'object','additionalProperties':False,'properties':{
        'organization_clauses':{'type':'array','maxItems':16,'items':clause_schema},
        'reason':{'type':'string'},
        'access_constraints':{'type':'array','maxItems':8,'items':access_schema}},
        'required':['organization_clauses','reason','access_constraints']}
    class Service:
        def complete_with_metadata(self,messages,response_schema=None):
            direct=[]
            for m in messages:
                if m.role=='assistant':
                    try:m=replace(m,content=json.loads(m.content)['program_json'])
                    except (ValueError,KeyError):pass
                direct.append(m)
            method=getattr(agent.service,'complete_with_metadata',None)
            response=(method(direct,schema) if callable(method) else
                      ModelCompletion(agent.service.complete(direct,schema),None,{}))
            return replace(response,content=json.dumps({'action':'final','detail_keys':[],
                                                        'program_json':response.content}))
    def parse(value):
        clauses=value.get('organization_clauses')
        if 'organization_clauses' in value:
            if set(value)!=set(schema['required']):raise ValueError('Invalid typed organization objective')
            value={**compose_organization(clauses,ids),'reason':value['reason'],
                   'access_constraints':value['access_constraints']}
        # Accept historical replay payloads; live structured responses use clauses only.
        if set(value)-{'access_constraints'}!={'applicability','organization','supporting_goal_ids','reason'}:
            raise ValueError('Invalid organization objective')
        if value['applicability'] not in ('uniform','qualified','conflicting','unrelated'):
            raise ValueError('Invalid organization applicability')
        if value['applicability']!='uniform' and value['organization']!='unspecified':
            raise ValueError('Qualified, conflicting or unrelated goals cannot impose uniform organization')
        if value['organization'] not in ('private_groups','independent','unspecified'):
            raise ValueError('Unknown organization objective')
        refs=value['supporting_goal_ids']
        if not isinstance(refs,list) or any(k not in ids for k in refs) or len(set(refs))!=len(refs):
            raise ValueError('Objective must cite supplied goal IDs')
        if value['organization']!='unspecified' and not refs:
            raise ValueError('A preference cannot be invented without a quoted goal')
        if not isinstance(value['reason'],str) or not value['reason'].strip() or len(value['reason'])>240:
            raise ValueError('Interpretation reason must contain 1..240 characters')
        rules=value.get('access_constraints',[])
        if not isinstance(rules,list) or len(rules)>8:raise ValueError('Invalid access constraints')
        for rule in rules:
            if (not isinstance(rule,dict) or set(rule)!=set(access_schema['required'])
                    or rule['predicate']!='not_through_room' or rule['function'] not in functions
                    or rule['applicability'] not in ('uniform','qualified','conflicting','unrelated')):
                raise ValueError('Unsupported floor access predicate')
            refs=rule['supporting_goal_ids']
            if not isinstance(refs,list) or not refs or any(k not in ids for k in refs) or len(set(refs))!=len(refs):
                raise ValueError('Access constraints must cite supplied goal IDs')
        value={**value,'access_constraints':rules}
        if clauses is not None:
            value.update(organization_clauses=clauses,interpretation_policy='typed_access_predicates_v2')
        return value
    runner=_ProgressiveProgramAgent(Service(),model_id=agent.model_id,max_calls=1)
    runner.name='floor_objective'
    result=runner._run(ProgressiveContext(summary={'building':{'id':building.id,'name':building.name,
        'function':building.function},'quoted_soft_goals':goals},sections=()),
        'Extract organization_clauses from quoted goals; do NOT decide whether the whole request '
        'is contradictory. Code composes the predicates. Give a short reason under 100 characters. '
        'all_rooms_direct means EVERY ordinary room must connect directly to public circulation. '
        'some_rooms_indirect means AT LEAST ONE room is entered through another ordinary room, '
        'including a request that NOT ALL rooms directly connect to public circulation. '
        'neutral means neither quantified condition is asserted. An anchor room directly connected '
        'to the corridor alone is neutral, NOT all_rooms_direct. The graph corridor -> anchor -> child '
        'is compatible: public access to anchors and private access to children are not opposites. '
        'Only the combination of EVERY room direct and SOME room indirect contradicts these '
        'supported organization predicates. Preserve both clauses if both are explicitly requested. '
        'uniform applies to the whole current building; qualified singles out named buildings, '
        'levels or subsets that this uniform interface cannot bind; unrelated is outside access '
        'organization. A room function mentioned inside a building-wide access condition is NOT '
        'a floor/entity subset qualifier. Geometric feasibility conditions are NOT subset qualifiers. '
        'Extract access relations, not dimensions, aesthetics, stereotypes or general privacy. '
        'Cite supplied goal IDs. Empty clauses are valid when no access condition is requested. '
        'Also return access_constraints for EXPLICIT statements that a named room FUNCTION must not '
        'serve as a passage or gateway to other rooms. Use not_through_room, cite supplied goals, '
        'and map the function to the offered enum. This is separate from organization: a building '
        'can have private groups while its meeting rooms are leaf rooms. A restriction on all meeting '
        'rooms is uniform even though meeting_room is one function; a restriction only on level 3 '
        'or another named building is qualified and cannot be imposed uniformly. Conflicts remain '
        'conflicting, never choose a priority. Do not infer bans from general privacy, aesthetics, '
        'function stereotypes or mere required inventories. Empty access_constraints is valid. '
        'Room-level quoted goals were disclosed because access dependencies are owned by the FLOOR. '
        'This remains a soft interpretation; hard functions, footprint, entry and core stay fixed. '
        'Return the native JSON object in the response schema.',parse)
    return result.program,result.attempts


def preferred_topologies(catalog,objective,required_by_level):
    preference=objective['organization']
    if preference=='unspecified':return catalog
    minimum=max((len(v) for v in required_by_level.values()),default=0)
    return [c for c in catalog if c['room_count']>=minimum and
        ((c['children_per_anchor']>0) if preference=='private_groups' else c['children_per_anchor']==0)]


def organization_receipt(profile,objective,*,selection_status):
    levels=[]
    for zone in profile.vertical_zones:
        children=sum(s.access_via!='circulation' for s in zone.spatial_program.spaces)
        for level in range(zone.start_level,zone.end_level+1):
            levels.append({'level':level,'private_child_rooms':children,
                           'total_rooms':len(zone.spatial_program.spaces)})
    preference=objective['organization']
    met=(bool(levels) and all(r['private_child_rooms']>0 for r in levels) if preference=='private_groups' else
         bool(levels) and all(r['private_child_rooms']==0 for r in levels) if preference=='independent' else None)
    return {'policy':'semantic_choice_verified_execution_v1','objective':objective,
        'selection_status':selection_status,'realized_levels':levels,'organization_preference_met':met,
        'all_user_goals_satisfied':False,'interpretation_authority':'quoted_soft_model_interpretation',
        'measurement_scope':'access topology only; not general privacy or visual quality'}
