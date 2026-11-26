"""Paired development diagnosis of a saved global FloorAgent protocol failure.

Clarify the profile-vs-role interface, then test native structured output.
Same parsers, budgets and model; the native arm intentionally changes schema.
No production code patch and no relaxed handling of malformed profiles.
"""
import argparse
from copy import deepcopy
from dataclasses import asdict, replace
import json
from pathlib import Path

from cityg.agents import AgentGenerationError
from cityg.agents.hierarchy import FloorAgent
from cityg.planning.programs import BuildingProgram
from cityg.planning.baseline import ROOM_FUNCTIONS
from cityg.run_provenance import source_snapshot
from cityg.schemas import CitySpec
from cityg.serialization import save_json
from cityg.services.interfaces import ModelEndpoint
from cityg.services.openai_compatible import OpenAICompatibleService
from run_edit_method_pilot import RecordedService


def space_action_schema(functions):
    profiles=[]
    for function in functions:
        archetypes=[]
        for role in ('ground','typical'):
            props={'role':{'const':role},
                **{k:{'type':'integer','minimum':1,'maximum':32}
                   for k in ('preferred_room_count','min_room_count','max_room_count')},
                'target_room_area_m2':{'type':'number','minimum':8,'maximum':250},
                'min_room_width_m':{'type':'number','minimum':2.4,'maximum':12},
                'max_room_depth_m':{'type':'number','minimum':4,'maximum':30},
                'max_room_aspect_ratio':{'type':'number','minimum':1.4,'maximum':8},
                'unit_group_size':{'type':'integer','minimum':1,'maximum':12},
                'layout_template':{'type':'string','enum':['auto','residential_units','office_core',
                    'commercial_retail','podium_core','tower_core','open_plan']},
                'room_function_cycle':{'type':'array','minItems':1,'items':{
                    'type':'string','enum':list(ROOM_FUNCTIONS[function])}}}
            archetypes.append({'type':'object','additionalProperties':False,'properties':props,'required':list(props)})
        profiles.append({'type':'object','additionalProperties':False,
            'properties':{'function':{'const':function},'archetypes':{
                'type':'array','prefixItems':archetypes,'items':False,'minItems':2,'maxItems':2}},
            'required':['function','archetypes']})
    program={'type':'object','additionalProperties':False,'required':['profiles'],
        'properties':{'profiles':{'type':'array','prefixItems':profiles,'items':False,
                                  'minItems':len(profiles),'maxItems':len(profiles)}}}
    return {'oneOf':[
        {'type':'object','additionalProperties':False,'required':['action','detail_keys','program'],
         'properties':{'action':{'const':'request_details'},
            'detail_keys':{'type':'array','minItems':1,'maxItems':3,'items':{'type':'string',
                'enum':['building_program','room_function_catalog','space_program_guidance']}},
            'program':{'type':'object','additionalProperties':False,'properties':{}}}},
        {'type':'object','additionalProperties':False,'required':['action','detail_keys','program'],
         'properties':{'action':{'const':'final'},'detail_keys':{'type':'array','maxItems':0},'program':program}}]}


class NativeSpaceService:
    def __init__(self,service,schema):self.service,self.schema=service,schema

    def complete_with_metadata(self,messages,response_schema=None):
        converted=[]
        for m in messages:
            if m.role=='assistant':
                try:
                    data=json.loads(m.content)
                    if 'program_json' in data:data['program']=json.loads(data.pop('program_json'))
                    m=replace(m,content=json.dumps(data))
                except (ValueError,TypeError):pass
            if m.role=='system':
                m=replace(m,content=m.content+' For this structured endpoint, replace program_json with '
                    'program, a NATIVE JSON OBJECT. Never encode the program as a string. '
                    'request_details uses program={}; final uses the typed program schema.')
            converted.append(m)
        response=self.service.complete_with_metadata(converted,self.schema)
        data=json.loads(response.content)
        converted={'action':data['action'],'detail_keys':data['detail_keys'],
                   'program_json':json.dumps(data['program'])}
        return replace(response,content=json.dumps(converted))


class ObservedFloorAgent(FloorAgent):
    def __init__(self,*args,clarify=False,native=False,**kwargs):
        super().__init__(*args,**kwargs);self.clarify=clarify;self.native=native;self.stage_results=[]

    def _run(self,context,prompt,parse_and_validate):
        is_space='room_count_contract' in context.summary
        if self.clarify and is_space:
            context=deepcopy(context)
            functions=context.summary['functions']
            context.summary['profile_cardinality_contract']={
                'exact_count':len(functions),'exact_function_ids':functions,
                'profile_key':'one unique zone FUNCTION, never a district, floor, or functional space',
                'exact_profile_fields':['function','archetypes'],
                'required_archetype_roles':['ground','typical'],
                'archetype_role_is_not_room_function':True,
                'organization':[{'function':f,'archetype_roles':['ground','typical']} for f in functions]}
            prompt += (' The profile_cardinality_contract defines the exact outer organization. '
                'Two districts that both use commercial share ONE commercial profile. Ground and '
                'typical are archetypes INSIDE that profile, not two profiles. The profile has NO '
                'name field. At this stage role must be exactly ground or typical, never retail_front, '
                'lobby, ground_retail or typical_office. Put shop/office/meeting_room in the flat '
                'room_function_cycle array of the appropriate archetype; do not create per-room '
                'archetypes or append functional suffixes to role IDs.')
        original=self.service
        if self.native and is_space:
            self.service=NativeSpaceService(original,space_action_schema(context.summary['functions']))
        try:result=super()._run(context,prompt,parse_and_validate)
        finally:self.service=original
        self.stage_results.append({'stage':'space' if is_space else 'layout',
                                   'trace':result.trace_dict()})
        return result


def run(source,output,methods):
    output.mkdir(parents=True,exist_ok=False)
    save_json(source_snapshot(),output/'source_provenance.json')
    spec=CitySpec.from_dict(json.loads((source/'requirement/requested_spec.json').read_text()))
    building=BuildingProgram.from_dict(json.loads((source/'programs/building_program.json').read_text()))
    original=json.loads((source/'failures/hierarchy_floor.json').read_text())
    payload=json.loads(original['attempts'][0]['messages'][1]['content'])
    priors=payload['summary'].get('prototype_priors')
    configuration=json.loads((source/'run.json').read_text())['configuration']
    endpoint=ModelEndpoint(base_url=configuration['base_url'],model='cityg-llm',
        max_tokens=configuration['max_completion_tokens_per_call'],seed=configuration['model_seed'])
    budget=configuration['max_calls_per_hierarchy_agent']
    save_json({'source':str(source.resolve()),'endpoint':asdict(endpoint),'max_calls_per_stage':budget,
        'method_order':methods,
        'nonrandomized_order':True},output/'config.json')
    rows=[]
    for method in methods:
        print('profile_probe_start',method,flush=True)
        service=RecordedService(OpenAICompatibleService(endpoint),output/f'{method}_model_calls.json')
        agent=ObservedFloorAgent(service,model_id=endpoint.model,max_calls=budget,
                                 clarify=method!='current_protocol',native=method=='native_space_schema')
        agent.design_goals=payload.get('shared_design_goals',[])
        row={'method':method,'accepted':False}
        try:
            result=agent.plan(spec,building,prototype_context=priors)
            row['accepted']=True;save_json(result.trace_dict(),output/f'{method}_trace.json')
        except AgentGenerationError as exc:
            row['error']=str(exc);save_json([asdict(a) for a in exc.attempts],output/f'{method}_failure.json')
        row['model_calls']=len(service.calls)
        row['stage_results']=[{'stage':s['stage'],'calls':s['trace']['totals']['model_calls']}
                             for s in agent.stage_results]
        save_json(agent.stage_results,output/f'{method}_stages.json')
        rows.append(row)
        save_json({'evidence_type':'development_single_failure_protocol_probe','rows':rows,
            'production_code_modified':False,
            'limitations':['One selected failure, not an unbiased success-rate or causal M1 estimate.',
                'Shared strict parsers remain final authority; no malformed role merging or field dropping.',
                'Service seeds do not guarantee bitwise replay under concurrent serving.',
                'Global planning only; no scene compilation or full pipeline rerun.']},output/'summary.json')
        print('profile_probe_end',row,flush=True)
    return rows


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--methods',nargs='+',choices=['current_protocol','explicit_profile_contract','native_space_schema'],
                   default=['current_protocol','explicit_profile_contract','native_space_schema'])
    a=p.parse_args();run(a.source,a.output,a.methods)
