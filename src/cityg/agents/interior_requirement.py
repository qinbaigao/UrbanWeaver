"""Focused extraction and independent omission review of explicit interiors.

The review is semantic model evidence, not proof of arbitrary language coverage.
Only literal, supported additions may enter the deterministic requirement ledger.
"""
from copy import deepcopy
import hashlib
import json
import time

from cityg.services.interfaces import ChatMessage
from cityg.interior_requirements import response_schema, validate_requirements
from cityg.inventory_provenance import deduplicate_identical_inventory


def apply_coverage_review(rows, review, instruction):
    """Add grounded omissions without silently rewriting existing requirements."""
    if set(review) != {'missing_items', 'missing_functions', 'issues'}:
        raise ValueError('Coverage review requires missing_items, missing_functions and issues')
    if not isinstance(review['issues'],list):raise ValueError('issues must be a list')
    for issue in review['issues']:
        if not isinstance(issue,dict) or not issue.get('source_quote','').strip() or issue['source_quote'] not in instruction:
            raise ValueError('Coverage issues must cite a literal original statement')
    if review['issues']:
        raise ValueError('Interior coverage conflicts: '+json.dumps(review['issues'],ensure_ascii=False))
    result=deepcopy(rows)
    for kind in ('missing_items','missing_functions'):
        for addition in review[kind]:
            quote=addition['source_quote']
            owners=[r for r in result if r['label']==addition['label'] and quote in r['source_quote']]
            if not quote.strip() or quote not in instruction or len(owners)!=1:
                raise ValueError('Coverage addition needs an exact quote and one unambiguous existing owner')
            row=owners[0]
            function=addition['room_function']
            if function not in row['required_functions']:row['required_functions'].append(function)
            if kind=='missing_items':
                item={k:v for k,v in addition.items() if k!='label'}
                item['count_basis']='presence' if item['min_count']==1 else 'explicit_number'
                existing=[i for i in row['inventory'] if (i['room_function'],i['category'])==(function,item['category'])]
                if existing:
                    if existing[0]['min_count']!=item['min_count']:
                        raise ValueError('Coverage review found conflicting counts; re-extract from the original request')
                else:row['inventory'].append(item)
    validate_requirements(result,instruction=instruction)
    return result


class InteriorRequirementAgent:
    def __init__(self, service, max_attempts=3):
        self.service=service
        self.max_attempts=max_attempts

    def extract(self, instruction):
        from cityg.agents.requirement import AgentAttempt, AgentGenerationError, _parse_json_object
        from cityg.planning.baseline import ROOM_FUNCTIONS
        schema={'type':'object','additionalProperties':False,
                'properties':{'interior_requirements':response_schema()},'required':['interior_requirements']}
        inventory=schema['properties']['interior_requirements']['items']['properties']['inventory']['items']
        inventory['properties'].pop('count_basis')
        inventory['required'].remove('count_basis')
        item=deepcopy(inventory)
        item['properties']['source_quote']={'type':'string'}
        item['required'].append('source_quote')
        audit_schema={'type':'object','additionalProperties':False,'properties':{
            'missing_items':{'type':'array','maxItems':16,'items':item}},'required':['missing_items']}
        prompt=(
            'Extract ONLY explicit building-specific interior requirements. Do not plan the city or invent furniture. '
            'Return interior_requirements: [] if none. ONE row per building and level set, with the FULL exact '
            'building-specific passage as source_quote. A/B are labels; building_id is null unless the user supplies '
            'an existing building_ ID. Ground/first floor is level 0. Office/cafe/shop buildings are commercial. '
            'Resolve a named building use from the full instruction, including heading sentences shared by A and B. '
            'A district described as mixed-use can contain individually residential and commercial buildings. '
            'An approximately N m2 ground floor is floor_gross, including circulation. Net or whole-building area '
            'must retain its stated meaning. Without an area request use area_m2=null and area_basis="floor_gross". '
            'A room function alone entails NO user furniture minimum: if the text only names an open office '
            'or meeting room, set required_functions and inventory=[]. The Room Agent plans its furniture later. '
            'Dining in a home belongs to living_room or kitchen, never dining_room. '
            'Cafe dining/preparation belong to break_room, waiting to reception, retail to shop. '
            'Use only supported room functions: '+json.dumps(ROOM_FUNCTIONS)+'. '
            'Capture every explicitly requested furniture role once: desk + office_chair, meeting_table + '
            'meeting_chair, dining_table + dining_chair, sofa + coffee_table, bed + wardrobe, kitchen_counter '
            '+ cabinet, display_shelf, checkout_counter, storage cabinet, waiting_bench as appropriate. '
            'Unnumbered plurals mean presence min_count=1, not invented quantities; explicit seating for six '
            'means six chairs. Do not output count_basis. Actual desired density is planned later. '
            'Do not invent reception desks when only waiting seating is requested. Do not invent separate '
            'rooms for storage/preparation surfaces. Requirements apply across rooms of that function per floor.')
        base=[ChatMessage('system',prompt+' Return a compact JSON object conforming to: '+json.dumps(schema)),
              ChatMessage('user',instruction)]
        messages=list(base);attempts=[]

        def call(stage, msgs, response, parse):
            from cityg.progress import progress
            progress(stage,'请求模型',call=len(attempts)+1)
            start=time.monotonic();raw='';finish=None;usage={};error=None;value=None
            try:
                method=getattr(self.service,'complete_with_metadata',None)
                if callable(method):
                    result=method(msgs,response if stage=='室内需求遗漏核对' else None)
                    raw=result.content;finish=result.finish_reason;usage=result.usage
                else:raw=self.service.complete(msgs,response if stage=='室内需求遗漏核对' else None)
                if finish=='length':raise ValueError('Truncated output; return concise unique requirements, not repeated rows')
                value=parse(_parse_json_object(raw))
            except (ValueError,TypeError,KeyError,RuntimeError) as exc:error=f'{type(exc).__name__}: {exc}'
            trace=tuple({'role':m.role,'content':m.content} for m in msgs)
            attempts.append(AgentAttempt(len(attempts)+1,hashlib.sha256(json.dumps(trace).encode()).hexdigest(),
                trace,raw,time.monotonic()-start,error,finish,usage))
            return value,error

        def parse(data):
            if set(data)!={'interior_requirements'}:raise ValueError('Only interior_requirements is allowed')
            rows=deduplicate_identical_inventory(data)['interior_requirements']
            from cityg.agents.building_uses import ground_named_uses
            ground_named_uses(rows, instruction)
            for row in rows:
                if row.get('area_m2') is None and row.get('area_basis') is None:
                    # Unused when no area was requested. Preserve a numeric area's original basis.
                    row['area_basis'] = 'floor_gross'
                for item in row['inventory']:
                    item['count_basis']='presence' if item['min_count']==1 else 'explicit_number'
            validate_requirements(rows,instruction=instruction)
            return rows

        for _ in range(self.max_attempts):
            rows,error=call('室内需求提取',messages,schema,parse)
            if not error:
                checked=deepcopy(rows)
                for index,row in enumerate(rows):
                    audit=[ChatMessage('system',
                        'Check one building ledger for omitted EXPLICIT furniture only. A room name alone, e.g. '
                        '开放办公室 or 会议室, is never a quoted furniture request. When only room names are supplied '
                        'return {"missing_items":[]}. '
                        'Return {"missing_items":[]} when all requested roles are represented. Do not recommend new assets. '
                        'Preserve the ledger function assignments: home dining may be in living_room/kitchen, cafe '
                        'preparation/dining may be in break_room/reception. A kitchen with preparation surfaces and '
                        'storage is covered by kitchen_counter and cabinet: do NOT add oven, sink or refrigerator. '
                        'A waiting area with seating is covered by waiting_bench: do NOT add sofa or reception_desk. '
                        'Unnumbered plural chairs/tables have minimum 1. If table and six seats are requested, '
                        'meeting_table and meeting_chair (6) together cover it. Only list a truly ABSENT explicitly '
                        'named category, quoting exactly the original words. Do not output label or count_basis. '
                        'Example: input says desk and chair; ledger has desk only -> missing office_chair, min_count 1. '
                        'Example: ledger already has desk and office_chair -> missing_items: []. '
                        'Output a result object such as {"missing_items":[]}, never a JSON schema. '
                        'Each omitted item has room_function, category, min_count, source_quote.'),
                        ChatMessage('user',json.dumps({'building_label':row['label'],
                            'original_building_instruction':row['source_quote'],
                            'functions':row['required_functions'],'existing_inventory':row['inventory']},ensure_ascii=False))]
                    def review(data):
                        if set(data)!={'missing_items'}:raise ValueError('Return only missing_items')
                        # An exact room title cannot be evidence of a missing furniture role.
                        room_titles={'开放办公室','开放式办公室','开放办公区','会议室','候诊室','卧室','厨房','客厅'}
                        room_titles.update(f.replace('_',' ') for f in row['required_functions'])
                        additions=[i for i in data['missing_items']
                                   if i['source_quote'].strip().lower() not in room_titles]
                        review_data={'missing_items':[{**i,'label':row['label']} for i in additions],
                                     'missing_functions':[],'issues':[]}
                        return apply_coverage_review([row],review_data,instruction)[0]
                    corrected,error=call('室内需求遗漏核对',audit,audit_schema,review)
                    if error:break
                    checked[index]=corrected
                if not error:return checked,tuple(attempts)
            # Start afresh from the request with actionable feedback, not long
            # rejected output. The complete rejected responses stay in traces.
            messages=[*base,ChatMessage('user','Previous attempt rejected: '+error+'. Re-extract the full concise ledger.')]
        raise AgentGenerationError('Focused interior extraction/coverage review failed within bounded attempts',attempts)
