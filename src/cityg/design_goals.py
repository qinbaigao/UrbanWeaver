"""Shared, quoted soft design goals; never upgrades interpretation to a fact."""
from dataclasses import asdict
import hashlib
import json
import re
import time

from cityg.agents.requirement import AgentAttempt, _parse_json_object
from cityg.services.interfaces import ChatMessage

LEVELS = ('urban','building','floor','room')


def validate_goals(value, instruction):
    if not isinstance(value,dict) or set(value)!={'goals'} or not isinstance(value['goals'],list) or len(value['goals'])>8:
        raise ValueError('Expected at most eight quoted design goals')
    goals=[]; seen=set()
    for row in value['goals']:
        if not isinstance(row,dict) or set(row)!={'source_quote','preference','levels'}:
            raise ValueError('Invalid goal fields')
        quote=row['source_quote']; preference=row['preference']; levels=row['levels']
        if not isinstance(quote,str) or not quote.strip() or quote not in instruction:
            raise ValueError('Goal must quote the user exactly')
        if not isinstance(preference,str) or not preference.strip() or len(preference)>300:
            raise ValueError('Invalid goal preference')
        if not isinstance(levels,list) or not levels or any(x not in LEVELS for x in levels) or len(set(levels))!=len(levels):
            raise ValueError('Invalid goal hierarchy levels')
        key=hashlib.sha256(json.dumps(row,sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:16]
        if key in seen: raise ValueError('Duplicate design goal')
        seen.add(key)
        goals.append({'id':'goal_'+key,**row,'kind':'soft_interpretation',
                      'status':'unverified','authority':'user_quote_with_model_interpretation'})
    return goals


def goal_context(goals, level):
    level={'skyline':'building','appearance':'building','building_floor':'floor'}.get(level,level)
    # A room's access/size dependencies are decided upstream. Disclose them for
    # review without changing their quoted scope or promoting them to authority.
    return [dict(g) if level in g.get('levels',[]) else
            {**g,'routing_reason':'room_goal_requires_upstream_floor_dependency_review'}
            for g in goals if level in g.get('levels',[]) or
            (level=='floor' and 'room' in g.get('levels',[]))]


def recovery_quotes(instruction, previous):
    """Only literal source spans; never fuzzy-match or expand invented ellipses."""
    spans=[part.strip() for part in re.split(r'(?<=[。！？!?])|\n+',instruction) if part.strip()]
    if isinstance(previous,dict):
        for row in previous.get('goals',[]):
            if isinstance(row,dict) and isinstance(row.get('source_quote'),str):
                quote=row['source_quote']
                if quote.strip() and quote in instruction:spans.append(quote)
    return list(dict.fromkeys(spans))


def extract_goals(service, instruction, *, max_calls=2):
    if type(max_calls) is not int or not 1<=max_calls<=2: raise ValueError('Goal budget is 1..2')
    props={'source_quote':{'type':'string'},'preference':{'type':'string','maxLength':300},
           'levels':{'type':'array','minItems':1,'maxItems':4,'items':{'type':'string','enum':list(LEVELS)}}}
    schema={'type':'object','additionalProperties':False,'required':['goals'],'properties':{
        'goals':{'type':'array','maxItems':8,'items':{'type':'object','additionalProperties':False,
                                                  'properties':props,'required':list(props)}}}}
    messages=[ChatMessage('system','Extract only useful qualitative design goals explicitly supported by the user. '
        'Quote exact original text. Interpretations remain SOFT, not user-approved hard constraints. '
        'Do not invent numeric targets, replace explicit counts, infer country stereotypes, or broaden scope. '
        'Do not copy building counts, numeric assignments, or mandatory function inventories into soft goals: '
        'these belong to the separate hard-requirement ledger. Preserve negative preferences and qualifications. '
        'Empty goals is valid. Assign ALL levels where a preference directly affects decisions, not merely the '
        'level of the noun used in the sentence. For example collaborative office atmosphere can affect '
        'floor and room organization; a facade color preference affects building, not room furniture. '
        'A warm room atmosphere should include room. Do not assign building to every goal by default. Return JSON.'),
        ChatMessage('user',instruction)]
    attempts=[];require_nonempty=False
    for index in range(max_calls):
        start=time.monotonic(); raw=''; usage={}; finish=None; error=None; goals=[]
        serialized=tuple({'role':m.role,'content':m.content} for m in messages)
        try:
            method=getattr(service,'complete_with_metadata',None)
            if callable(method):
                result=method(messages,schema); raw=result.content;usage=result.usage;finish=result.finish_reason
            else: raw=service.complete(messages,schema)
            if finish=='length': raise ValueError('Design goals truncated')
            parsed=_parse_json_object(raw)
            goals=validate_goals(parsed,instruction)
            if require_nonempty and not goals:
                raise ValueError('Recovery cannot erase a previously proposed nonempty goal set')
        except (ValueError,TypeError,KeyError,RuntimeError) as exc: error=str(exc)
        attempts.append(AgentAttempt(index+1,hashlib.sha256(json.dumps(serialized).encode()).hexdigest(),
            serialized,raw,time.monotonic()-start,error,finish,usage))
        if error is None: break
        try:previous=_parse_json_object(raw)
        except ValueError:previous={}
        require_nonempty=require_nonempty or bool(previous.get('goals'))
        if error=='Goal must quote the user exactly':
            options=recovery_quotes(instruction,previous)
            # Constrain the recovery request, not the validator: every accepted
            # quote must still occur byte-for-byte in the original instruction.
            props['source_quote']={'type':'string','enum':options}
            recovery=' Choose literal source_quote values from the offered enum. Do not use ellipses, '
            recovery+='paraphrases or stitch separated spans. Preserve qualifications and negative intent; '
            recovery+='restate the entire valid goal set, do not drop goals to evade validation.'
        else:recovery=' Correct the entire response without dropping relevant goals.'
        messages.extend([ChatMessage('assistant',raw[:6000]),ChatMessage('user','Rejected: '+error+recovery)])
    return {'status':'extracted' if error is None else 'unavailable','goals':goals,
            'attempts':[asdict(a) for a in attempts],'semantic_satisfaction_proven':False},tuple(attempts)
