"""Literal, target-bound edit postconditions; not a general NLP verifier.

Only explicit stable IDs and supported literal requests create hard
postconditions. Ambiguous count assignment is rejected, never guessed.
"""
import json
import re

from cityg.ccwp import entity_index
from cityg.naming import alias_index
from cityg.schemas import Building, Floor


def explicit_entity_ids(city, instruction):
    aliases=alias_index(city)
    tokens=re.findall(r'[A-Za-z][A-Za-z0-9_:./-]*',instruction)
    return {key for token in tokens for key in aliases.get(token.rstrip('.'),())}


def explicit_edit_constraints(city,instruction):
    entities=entity_index(city);ids=explicit_entity_ids(city,instruction);result=[]
    if not ids: return result
    target=next(iter(ids)) if len(ids)==1 else None
    entity=entities.get(target)
    name=re.search(r'''(?:命名为|改名为|rename\s+.+?\s+to|(?:显示名称|名称|名字|name|display_name)\s*(?:改为|改成|设置为|to|=|:))\s*[“"']([^”"'\n]+)[”"']''',instruction,re.I)
    if name and hasattr(entity,'name'):
        result.append({'kind':'name','entity_id':target,'expected':name.group(1),'source_excerpt':name.group()})
    from cityg.subtree_transactions import _details_spec
    details = _details_spec(instruction)
    if isinstance(entity, Building):
        if 'floor_count' in details:
            result.append({'kind':'building_floor_count','entity_id':target,
                           'expected':details['floor_count'],'source_excerpt':instruction})
        if 'room_count' in details and re.search(r'每层|各层|每个楼层|each\s+floor|per\s+floor',instruction,re.I):
            result.append({'kind':'building_rooms_per_floor','entity_id':target,
                           'expected':details['room_count'],'source_excerpt':instruction})
    floors={key for key in ids if isinstance(entities[key],Floor)}
    count=_details_spec(instruction).get('room_count')
    assignments={}
    if count is not None and floors:
        if len(ids)==1:
            assignments={target:count}
        else:
            # First bind independent clauses, e.g. A -> 4 rooms; B -> 5 rooms.
            # Do not split English thousands separators.
            text=re.sub(r'\b\d{1,3}(?:,\d{3})+\b',lambda m:m.group().replace(',',''),instruction)
            for clause in re.split(r'[;；，。\n]|,(?!\d)',text):
                local=explicit_entity_ids(city,clause)&floors
                value=_details_spec(clause).get('room_count')
                if len(local)==1 and value is not None:
                    key=next(iter(local))
                    if key in assignments and assignments[key]!=value:
                        raise ValueError('同一楼层有冲突的房间数量，请明确每层的目标数量。')
                    assignments[key]=value
            # A single shared number is distributive only with explicit EACH.
            if not assignments and ids==floors and re.search(r'每层|各层|每个楼层|each\s+(?:of\s+these\s+)?floor|per\s+floor',instruction,re.I):
                # Reject positional/multiple quantities rather than guessing.
                remainder=re.sub(r'[A-Za-z][A-Za-z0-9_:./-]*','',text)
                if len(re.findall(r'\d+',remainder))==1:
                    assignments={key:count for key in floors}
            if not assignments:
                raise ValueError('多个楼层的房间数量指代不明确；请说明每层各多少间，或逐个 ID 指定。')
        result.extend({'kind':'floor_room_count','entity_id':key,'expected':value,
                       'source_excerpt':instruction} for key,value in sorted(assignments.items()))
    return result


def validate_edit_plan_constraints(plan,constraints):
    if plan['status']=='needs_clarification': return
    for constraint in constraints:
        target=constraint['entity_id'];expected=constraint['expected']
        if constraint['kind']=='name':
            matches=[o for o in plan['operations'] if o['target_id']==target
                and o['op'] in {'replace_entity','replace_node','add_relation'} and o['path'] in {'name','display_name'}
                and json.loads(o['value_json'])==expected]
            if plan['status']!='apply' or not matches:
                raise ValueError(f'Literal rename requires replace_entity/name = {expected!r}; '
                                 'Building Refinement cannot implement a rename')
        elif constraint['kind']=='floor_room_count':
            from cityg.subtree_transactions import _details_spec
            matches=[r for r in plan['replan_requests'] if r['kind']=='floor_layout' and r['target_id']==target
                     and _details_spec(r['details']).get('room_count')==expected]
            if plan['status']!='replan_required' or not matches:
                raise ValueError(f'Preserve explicit room_count={expected}; use floor_layout details '
                                 'as a JSON object string with this exact room_count. Do not lower or omit it.')
        elif constraint['kind'] in {'building_floor_count','building_rooms_per_floor'}:
            from cityg.subtree_transactions import _details_spec
            key = 'floor_count' if constraint['kind']=='building_floor_count' else 'room_count'
            matches = [r for r in plan['replan_requests'] if r['kind']=='building_subtree'
                       and r['target_id']==target and _details_spec(r['details']).get(key)==expected]
            if plan['status']!='replan_required' or not matches:
                raise ValueError(f'Preserve explicit {key}={expected}; use building_subtree with '
                                 'these exact counts in JSON details. Do not lower or omit them.')


def check_edit_constraints(city,constraints):
    entities=entity_index(city);rows=[]
    for constraint in constraints:
        entity=entities.get(constraint['entity_id']);actual=None
        if constraint['kind']=='name': actual=getattr(entity,'name',None)
        elif constraint['kind']=='floor_room_count' and isinstance(entity,Floor):
            actual=sum(r.function!='corridor' for r in entity.rooms)
        elif constraint['kind']=='building_floor_count' and isinstance(entity,Building):
            actual=len(entity.floors)
        elif constraint['kind']=='building_rooms_per_floor' and isinstance(entity,Building):
            actual=[sum(r.function!='corridor' for r in f.rooms) for f in entity.floors]
        ok = (bool(actual) and all(n==constraint['expected'] for n in actual)
              if constraint['kind']=='building_rooms_per_floor' else actual==constraint['expected'])
        rows.append({**constraint,'actual':actual,'ok':ok})
    return {'ok':all(r['ok'] for r in rows),'checks':rows,
            'scope':'explicit_target_literal_name_floor_count_and_room_count_only',
            'arbitrary_natural_language_verified':False}
