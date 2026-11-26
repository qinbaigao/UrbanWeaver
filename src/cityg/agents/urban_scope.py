"""Disclose only source clauses that request a relation between urban entities."""
import hashlib
import json
import re
import time

from cityg.services.interfaces import ChatMessage


def urban_scope(instruction, service):
    from cityg.agents.requirement import AgentAttempt
    from cityg.progress import progress
    sentences = [s.strip() for s in re.split(r'(?<=[。！？；;])|(?<=[.!?])\s+|\n+', instruction) if s.strip()]
    schema = {'type':'object','properties':{'indices':{'type':'array',
              'items':{'type':'integer','minimum':0,'maximum':len(sentences)-1}}},
              'required':['indices'],'additionalProperties':False}
    system = ('Select only sentence indices explicitly requesting relative placement of urban entities '
              '(north/south/east/west, near/far, service distance), or a minimum BUILDING FOOTPRINT. '
              'A site size, a ground-floor interior area, street connectivity, access to entrances, or the mere '
              'presence of a park are recorded elsewhere; none alone specifies such a relation. '
              'A park north of the offices, or a school within 150 m of each home, does qualify. '
              'Use {"indices":[]} when there are no such sentences.')
    msgs=[ChatMessage('system',system),ChatMessage('user',json.dumps(list(enumerate(sentences)),ensure_ascii=False))]
    start=time.monotonic(); raw=''; usage={}; finish=None; error=None; selected=None
    progress('城市空间需求','核对原文中的城市实体关系')
    try:
        method=getattr(service,'complete_with_metadata',None)
        if callable(method):
            result=method(msgs,schema)
            raw,usage,finish=result.content,result.usage,result.finish_reason
        else:
            raw=service.complete(msgs,schema)
        indices=json.loads(raw)['indices']
        if finish=='length' or not isinstance(indices,list) or any(type(i) is not int or not 0<=i<len(sentences) for i in indices):
            raise ValueError('Invalid urban clause selection')
        # Retain explicit relation cues even if the semantic selector misses a clause.
        cue = re.compile(r'\b(?:north(?:ern)?|south(?:ern)?|east(?:ern)?|west(?:ern)?|near(?:by)?|far|'
                         r'adjacent|proximity|within|away from|footprints?|served by|next to|opposite|'
                         r'alongside|close to)\b|[东西南北](?:侧|边|部|半|面|区)|'
                         r'以[东西南北]|靠近|远离|邻近|相邻|附近|紧邻|占地|距.{0,16}米|服务半径', re.I)
        # A table beside a door and a waiting area near an entrance are room-level evidence.
        indoor = re.compile(r'\b(?:near(?:by)?|adjacent to|next to|close to)\s+(?:the |a |an )?'
                            r'(?:entrance|door|counter|desk)(?:way)?\b', re.I)
        from cityg.walking_requirements import route_clauses
        planar_cue = re.compile(r'直线|占地|服务半径|以[东西南北]|[东西南北](?:侧|边|部|半)|靠近|相邻|'
                                r'\b(?:straight.line|euclidean|footprint|north|south|east|west|adjacent)\b',re.I)
        selected=[s for i,s in enumerate(sentences) if (i in indices or cue.search(indoor.sub('', s)))
                  and (not route_clauses(s) or planar_cue.search(s))]
    except (ValueError, KeyError, TypeError, RuntimeError, OSError) as exc:
        # Bounded fallback to the full relation parser; a failed read never clears the requirements.
        error=str(exc)
    serialized=tuple({'role':m.role,'content':m.content} for m in msgs)
    trace=AgentAttempt(1,hashlib.sha256(json.dumps(serialized,ensure_ascii=False).encode()).hexdigest(),
                       serialized,raw,round(time.monotonic()-start,6),error,finish,usage)
    return selected,trace
