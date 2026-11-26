from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import unittest

from cityg.assets import AssetRegistry,AssetResolver
from cityg.ccwp import build_world_program
from cityg.geometry import GeometryCompiler
from cityg.planning.generation_prototypes import GenerationPrototypes,load_options
from cityg.planning.prototype_lab import make_lab,populate_reference
from cityg.planning.prototypes import reference_registry
from cityg.refinement.room_preflight import prepare_preflight
from cityg.refinement.room import RoomProgramAgent

ROOT=Path(__file__).resolve().parents[1]


class RoomPreflightTests(unittest.TestCase):
    def test_truncated_constrained_response_gets_complete_schema_in_plain_retry(self):
        from types import SimpleNamespace
        from cityg.agents import AgentGenerationError
        from cityg.planning.baseline import BaselineCityPlanner
        from cityg.schemas import CitySpec
        from cityg.refinement.room import ROOM_PROGRAM_RESPONSE_SCHEMA
        city=BaselineCityPlanner().plan(CitySpec(building_count=1))
        building=next(city.iter_buildings());floor=building.floors[0]
        room=next(r for r in floor.rooms if r.function!='corridor')
        class Service:
            def __init__(self):self.calls=[]
            def complete_with_metadata(self,messages,schema):
                self.calls.append((messages,schema))
                return SimpleNamespace(content='{"room_id":',finish_reason='length',
                                       usage={'completion_tokens':100})
        service=Service()
        with self.assertRaises(AgentGenerationError) as raised:
            RoomProgramAgent(service,max_attempts=2).propose(city,building,floor,room)
        self.assertEqual(raised.exception.attempts[0].finish_reason,'length')
        self.assertEqual(raised.exception.attempts[0].usage['completion_tokens'],100)
        self.assertIsNone(service.calls[1][1])
        reminder=service.calls[1][0][-1].content
        self.assertIn('COMPLETE response',reminder)
        schema=json.loads(reminder.split('Response JSON schema: ',1)[1])
        self.assertEqual(schema['required'],ROOM_PROGRAM_RESPONSE_SCHEMA['required'])
        self.assertIn('furnishing_brief',schema['properties']['design']['required'])

    def test_real_compiled_support_failure_retries_before_any_asset_generation(self):
        runtime=GenerationPrototypes(load_options(ROOT/'configs/generation_prototypes.json'))
        city,targets=make_lab(runtime.floors.room_library,['office_private_v1'])
        key,b,f,r=targets[0];proto=runtime.floors.room_library.materialize(key)
        # This fixture tests furniture support feasibility, not optional local
        # decoration downloads (which may be absent in a code-only checkout).
        r.metadata.pop('room_decorations',None)
        compiler=GeometryCompiler(asset_registry=AssetRegistry(ROOT/'assets/asset_registry.json'))
        registry=runtime.prepare_resources(compiler.asset_registry,compiler)
        registry=reference_registry(registry,proto)
        compiler.asset_registry=registry
        populate_reference(city,targets[0],runtime.floors.room_library,registry)
        city.world_program=build_world_program(city,producer='test',seed=17)
        context,check,_=prepare_preflight(city,r.id,compiler,registry)
        self.assertTrue(context['supports'])
        before=deepcopy(city)
        good=proto.program(r.id)
        chair=next(m['id'] for g in good.design.groups for m in g['members'] if 'chair' in m['category'])
        bad=replace(good,design=replace(good.design,surface_items=(*good.design.surface_items,
            {'id':'impossible_chair_prop','support_member_id':chair,'surface':'top',
             'category':'book','count':1,'placement':'spread'})))
        support_failure = 'Compiled room verification failed|lacks requested verified supports'
        with self.assertRaisesRegex(ValueError,support_failure):
            check(bad)
        self.assertTrue(check(good)['ok']);self.assertEqual(city,before)
        payloads=[{'room_id':r.id,'style':p.style,'density':p.density,'requests':[],
                   'design':p.design.to_dict()} for p in (bad,good)]
        class Service:
            def __init__(self): self.calls=[]
            def complete(self,messages,schema):
                self.calls.append(messages)
                return json.dumps(payloads[min(len(self.calls)-1,1)])
        class Provider:
            name='must_not_generate'
            def generate(self,*args,**kwargs): raise AssertionError('Preflight generated an asset')
        service=Service();resolver=AssetResolver(registry,(Provider(),),max_provider_calls=1)
        result=RoomProgramAgent(service,max_attempts=2,asset_resolver=resolver).propose(
            city,b,f,r,use_cache=False,visual_feedback={'compiled_support_context':context},compiled_preflight=check)
        self.assertEqual(len(result.attempts),2)
        self.assertRegex(result.attempts[0].error,support_failure)
        self.assertTrue(result.raw['_compiled_preflight']['ok'])
        self.assertEqual(resolver.stats()['provider_calls'],0)
        self.assertEqual(city,before)
