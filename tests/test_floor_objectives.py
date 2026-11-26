from copy import deepcopy
import json
from types import SimpleNamespace
import unittest

from cityg.agents import AgentGenerationError
from cityg.agents.building_floor import BuildingFloorAgent
from cityg.design_goals import validate_goals
from cityg.planning.floor_brief import geometry_summary, resolve_brief
from cityg.planning.floor_objectives import compose_organization, interpret_organization, preferred_topologies, organization_receipt
from cityg.planning.floor_topologies import topology_catalog
import test_floor_brief as floor_fixtures


class FloorObjectiveTests(unittest.TestCase):
    def test_compositional_predicates_preserve_compatible_anchor_access(self):
        clauses=[{'relation':r,'applicability':'uniform','supporting_goal_ids':['g']} for r in
                 ('neutral','some_rooms_indirect')]
        self.assertEqual(compose_organization(clauses,['g'])['organization'],'private_groups')
        clauses.append({'relation':'all_rooms_direct','applicability':'uniform','supporting_goal_ids':['g']})
        result=compose_organization(clauses,['g'])
        self.assertEqual(result['applicability'],'conflicting')
        self.assertEqual(result['organization'],'unspecified')
        clauses=clauses[-1:];clauses[0]['applicability']='qualified'
        self.assertEqual(compose_organization(clauses,['g'])['organization'],'unspecified')
        with self.assertRaises(ValueError):compose_organization(clauses,['another_goal'])

    def test_native_clause_interpretation_separates_transit_bans(self):
        b,_,_,_=floor_fixtures.FloorBriefTests().fixture();goals=self.goals()
        refs=[goals[0]['id']]
        class Service:
            def complete(self,messages,response_schema=None):
                assert 'organization_clauses' in response_schema['required']
                return json.dumps({'organization_clauses':[
                    {'relation':'some_rooms_indirect','applicability':'uniform','supporting_goal_ids':refs}],
                    'reason':'Private children; bedroom leaves', 'access_constraints':[
                    {'predicate':'not_through_room','function':'bedroom','applicability':'uniform',
                     'supporting_goal_ids':refs}]})
        agent=BuildingFloorAgent(Service(),model_id='test');agent.design_goals=goals
        objective,_=interpret_organization(agent,b)
        self.assertEqual(objective['organization'],'private_groups')
        self.assertEqual(objective['access_constraints'][0]['function'],'bedroom')
        self.assertEqual(objective['interpretation_policy'],'typed_access_predicates_v2')

    def goals(self):
        quote='Prefer private groups with anchor spaces and private child rooms.'
        return validate_goals({'goals':[{'source_quote':quote,'preference':quote,'levels':['floor']}]},quote)

    def test_interpretation_requires_supplied_goal_citation(self):
        b,_,_,_=floor_fixtures.FloorBriefTests().fixture()
        class Service:
            def complete(self,messages,response_schema=None):
                assert 'uniqueItems' not in json.dumps(response_schema)
                return json.dumps({'applicability':'uniform','organization':'private_groups','supporting_goal_ids':['invented'],
                                   'reason':'Explicit preference'})
        agent=BuildingFloorAgent(Service(),model_id='test',max_calls=3)
        agent.design_goals=self.goals()
        with self.assertRaises(AgentGenerationError) as ctx:interpret_organization(agent,b)
        self.assertEqual(len(ctx.exception.attempts),1)

    def test_preference_subset_preserves_required_function_capacity(self):
        catalog=[{'room_count':2,'children_per_anchor':1},
                 {'room_count':6,'children_per_anchor':1},
                 {'room_count':6,'children_per_anchor':0}]
        self.assertEqual(preferred_topologies(catalog,{'organization':'private_groups'},
                                             {'0':['a','b','c']}),[catalog[1]])
        self.assertEqual(preferred_topologies(catalog,{'organization':'unspecified'},{}),catalog)

    def test_qualified_interpretation_cannot_become_uniform_preference(self):
        b,_,_,_=floor_fixtures.FloorBriefTests().fixture();goals=self.goals()
        class Service:
            def complete(self,*args):
                return json.dumps({'applicability':'qualified','organization':'private_groups',
                    'supporting_goal_ids':[goals[0]['id']],'reason':'Only one floor'})
        agent=BuildingFloorAgent(Service(),model_id='test');agent.design_goals=goals
        with self.assertRaises(AgentGenerationError):interpret_organization(agent,b)

    def test_small_floor_schema_owns_mechanical_zone_identifiers(self):
        from cityg.planning.floor_topologies import topology_schema
        b,base,_,_=floor_fixtures.FloorBriefTests().fixture()
        schema=topology_schema(['living_room'],['residential'],topology_catalog(geometry_summary(b,base)),2)
        for level,zone in enumerate(schema['properties']['zones']['prefixItems']):
            for variant in zone['oneOf']:
                self.assertEqual(variant['properties']['zone_id']['const'],f'level_{level}')

    def test_receipt_measures_realization_not_requested_intent(self):
        b,base,spec,brief=floor_fixtures.FloorBriefTests().fixture()
        profile=resolve_brief(brief,b,base,spec)
        receipt=organization_receipt(profile,{'organization':'private_groups'},selection_status='fallback')
        self.assertFalse(receipt['organization_preference_met'])
        self.assertFalse(receipt['all_user_goals_satisfied'])
        self.assertFalse(organization_receipt(SimpleNamespace(vertical_zones=[]),
            {'organization':'independent'},selection_status='empty')['organization_preference_met'])

    def test_failed_preferred_realization_falls_back_within_total_budget(self):
        b,base,spec,brief=floor_fixtures.FloorBriefTests().fixture()
        b.metadata['interior_layout_contract']={'reserved':True};before=deepcopy(b)
        catalog=topology_catalog(geometry_summary(b,base))
        option=next(c for c in catalog if c['children_per_anchor']==0)
        zones=[{k:z[k] for k in ('zone_id','start_level','end_level','role','use_type')} | {
            'topology_id':option['id'],'functions':['living_room']*option['room_count'],
            'weight_adjustments':[1.0]*option['room_count']} for z in brief['zones']]
        goals=self.goals()
        class Service:
            calls=0
            def complete(self,messages,response_schema=None):
                assert 'uniqueItems' not in json.dumps(response_schema)
                self.calls+=1
                if self.calls==1:return json.dumps({'applicability':'uniform','organization':'private_groups',
                    'supporting_goal_ids':[goals[0]['id']],'reason':'Explicit private groups'})
                if self.calls==2:return '{}'
                return json.dumps({'zones':zones})
        service=Service();agent=BuildingFloorAgent(service,model_id='test',max_calls=3)
        agent.design_goals=goals
        result=agent.plan(b,base,spec)
        self.assertEqual(service.calls,3)
        self.assertEqual(len(result.attempts),3)
        self.assertEqual(result.program.decision_receipt['selection_status'],'preferred_realization_failed_fallback')
        self.assertFalse(result.program.decision_receipt['organization_preference_met'])
        self.assertEqual(b,before)
