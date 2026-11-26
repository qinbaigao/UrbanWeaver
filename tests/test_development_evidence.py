import sys
from pathlib import Path
from types import SimpleNamespace as NS
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from run_floor_contract_pilot import profile_metrics
from summarize_development_suite import visual_metrics
from probe_floor_profile_contract import NativeSpaceService, space_action_schema
from cityg.services.interfaces import ChatMessage
from cityg.services.openai_compatible import ModelCompletion
import json


class DevelopmentEvidenceTests(unittest.TestCase):
    def test_native_schema_binds_profiles_to_functions_and_roles(self):
        schema=space_action_schema(['commercial','residential'])
        profiles=schema['oneOf'][1]['properties']['program']['properties']['profiles']
        self.assertEqual(profiles['minItems'],2)
        self.assertEqual(profiles['maxItems'],2)
        self.assertFalse(profiles['items'])
        for profile,function in zip(profiles['prefixItems'],['commercial','residential']):
            self.assertEqual(profile['properties']['function']['const'],function)
            archetypes=profile['properties']['archetypes']['prefixItems']
            self.assertEqual([a['properties']['role']['const'] for a in archetypes],['ground','typical'])
            self.assertFalse(profile['additionalProperties'])

    def test_native_adapter_preserves_usage_and_progressive_disclosure(self):
        class Service:
            def complete_with_metadata(self,messages,schema):
                self.messages=messages
                return ModelCompletion(json.dumps({'action':'request_details',
                    'detail_keys':['building_program'],'program':{}}),'stop',{'prompt_tokens':17})
        service=Service();adapter=NativeSpaceService(service,space_action_schema(['commercial']))
        completion=adapter.complete_with_metadata([ChatMessage('system','Plan'),ChatMessage('assistant',
            json.dumps({'action':'request_details','detail_keys':['building_program'],'program_json':'{}'}))])
        self.assertEqual(completion.usage,{'prompt_tokens':17})
        self.assertEqual(json.loads(completion.content)['program_json'],'{}')
        self.assertIn('program',json.loads(service.messages[1].content))
        self.assertNotIn('program_json',json.loads(service.messages[1].content))

    def test_missing_usage_is_unknown_not_zero(self):
        review={'batches':[{'attempts':[{'error':None,'usage':{}}]}]}
        self.assertIsNone(visual_metrics(review)['usage']['prompt_tokens'])
        self.assertEqual(visual_metrics(review)['calls'],1)

    def test_zero_model_calls_have_known_zero_usage(self):
        self.assertEqual(visual_metrics({'batches':[]})['usage']['prompt_tokens'],0)

    def test_geometry_denial_does_not_count_as_human_false_positive(self):
        result=visual_metrics({'aggregated_issues':[{
            'independent_verification':{'status':'not_supported_by_geometry'}}]})
        self.assertEqual(result['grounding_status'],{'not_supported_by_geometry':1})
        self.assertNotIn('precision',result)

    def test_floor_signature_distinguishes_private_access_and_missing_function(self):
        spaces=[NS(function='living_room',access_via='circulation',target_area_m2=20),
                NS(function='kitchen',access_via='circulation',target_area_m2=10)]
        profile=NS(vertical_zones=[NS(start_level=0,end_level=0,spatial_program=NS(spaces=spaces))])
        building=NS(floors=[NS(level=0)])
        base=NS(zone_for_level=lambda _:None,for_role=lambda _:NS(room_function_cycle=['living_room','kitchen']))
        independent=profile_metrics(profile,building,base)
        spaces[1].access_via='living'
        grouped=profile_metrics(profile,building,base)
        self.assertEqual(grouped['private_child_total'],1)
        self.assertNotEqual(independent['topology_signature'],grouped['topology_signature'])
        self.assertTrue(grouped['required_functions_preserved'])
        spaces[1].function='bedroom'
        self.assertFalse(profile_metrics(profile,building,base)['required_functions_preserved'])
