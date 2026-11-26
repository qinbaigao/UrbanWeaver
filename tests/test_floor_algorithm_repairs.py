from copy import deepcopy
from dataclasses import replace
import json
import unittest

from cityg.agents import AgentGenerationError
from cityg.agents.building_floor import BuildingFloorAgent, BuildingFloorProgram
from cityg.design_goals import extract_goals, goal_context, validate_goals
from cityg.planning.floor_brief import geometry_summary, resolve_brief
from cityg.planning.floor_candidates import feasible_candidates, nominal_brief
from cityg.planning.floor_topologies import topology_catalog, expand_topology_brief
from cityg.planning.floor_objectives import interpret_organization
from cityg.schemas import Bounds2D, Point2D
import test_floor_brief as floor_fixtures


class FloorAlgorithmRepairTests(unittest.TestCase):
    def test_quote_recovery_uses_literal_enum_without_fuzzy_acceptance(self):
        instruction='卧室不要作为通道。保留入口、核心筒。'
        class Service:
            calls=0
            def complete(self,messages,schema):
                self.calls+=1
                if self.calls==1:quote='保留...核心筒'
                else:
                    options=schema['properties']['goals']['items']['properties']['source_quote']['enum']
                    assert all(q in instruction for q in options)
                    assert '保留...核心筒' not in options
                    quote='卧室不要作为通道。'
                return json.dumps({'goals':[{'source_quote':quote,'preference':'Bedrooms must not be transit rooms','levels':['room']}]})
        report,attempts=extract_goals(Service(),instruction)
        self.assertEqual(report['status'],'extracted');self.assertEqual(len(attempts),2)
        self.assertEqual(attempts[0].error,'Goal must quote the user exactly')
        self.assertIn(report['goals'][0]['source_quote'],instruction)
        self.assertFalse(report['semantic_satisfaction_proven'])

    def test_recovery_cannot_succeed_by_emptying_goals_or_exceed_budget(self):
        class Service:
            calls=0
            def complete(self,*args):
                self.calls+=1
                return json.dumps({'goals':[] if self.calls>1 else [
                    {'source_quote':'invented','preference':'invented','levels':['room']}]})
        service=Service();report,attempts=extract_goals(service,'保留入口。')
        self.assertEqual(service.calls,2);self.assertEqual(report['status'],'unavailable')
        self.assertIn('erase',attempts[-1].error)
        report,attempts=extract_goals(Service(),'保留入口。',max_calls=1)
        self.assertEqual(report['status'],'unavailable');self.assertEqual(len(attempts),1)

    def test_upstream_disclosure_does_not_change_quote_levels_or_authority(self):
        goals=validate_goals({'goals':[{'source_quote':'卧室不要作为通道','preference':'No transit bedrooms',
                                     'levels':['room']}]},'卧室不要作为通道')
        original=deepcopy(goals);upstream=goal_context(goals,'building_floor')
        self.assertEqual(len(upstream),1);self.assertEqual(upstream[0]['levels'],['room'])
        self.assertEqual(upstream[0]['authority'],'user_quote_with_model_interpretation')
        self.assertEqual(goals,original);self.assertEqual(goal_context(goals,'urban'),[])

    def large_plate(self):
        b,base,spec,_=floor_fixtures.FloorBriefTests().fixture()
        b.footprint=Bounds2D(0,0,28,44);b.entrance=Point2D(14,0)
        b.metadata['interior_layout_contract']={'reserved':True,'circulation_axis':'y'}
        base=replace(base,room_function_cycle=('living_room','bedroom'),space_archetypes=tuple(
            replace(a,room_function_cycle=('living_room','bedroom')) for a in base.space_archetypes))
        return b,base,spec

    def test_area_filter_and_full_nominal_check_preserve_all_hard_gates(self):
        b,base,spec=self.large_plate();original=deepcopy(b);geometry=geometry_summary(b,base)
        catalog=topology_catalog(geometry)
        self.assertTrue(catalog)
        self.assertTrue(all(8<=geometry['usable_area_m2']/c['room_count']<=250 for c in catalog))
        accepted,receipt=feasible_candidates(catalog,b,base,spec)
        self.assertTrue(accepted)
        for candidate in accepted:
            profile=resolve_brief(expand_topology_brief(nominal_brief(candidate,b,base),accepted),b,base,spec)
            BuildingFloorProgram(b.function,profile).validate(b)
            BuildingFloorAgent._check_spatial_feasibility(profile,b,spec)
        self.assertEqual(b,original)
        self.assertTrue(all(c['full_profile_checked_at_nominal_assignment'] for c in accepted))

    def test_realized_door_graph_rejects_forbidden_anchor_but_accepts_leaf(self):
        b,base,spec=self.large_plate();catalog=topology_catalog(geometry_summary(b,base))
        candidate=next(c for c in catalog if c['children_per_anchor']>0)
        rule={'predicate':'not_through_room','function':'bedroom','applicability':'uniform','supporting_goal_ids':['g']}
        brief=nominal_brief(candidate,b,base,['bedroom'])
        profile=resolve_brief(expand_topology_brief(brief,catalog),b,base,spec)
        BuildingFloorAgent._check_spatial_feasibility(profile,b,spec,access_constraints=[rule])
        for zone in brief['zones']:
            zone['functions'][0],zone['functions'][1]='bedroom','living_room'
        bad=resolve_brief(expand_topology_brief(brief,catalog),b,base,spec)
        with self.assertRaisesRegex(ValueError,'required transit room'):
            BuildingFloorAgent._check_spatial_feasibility(bad,b,spec,access_constraints=[rule])
        # Scoped statements are not silently generalized to all floors.
        BuildingFloorAgent._check_spatial_feasibility(bad,b,spec,access_constraints=[{**rule,'applicability':'qualified'}])

    def test_no_nominal_candidate_fails_before_model_call(self):
        b,base,spec=self.large_plate()
        class Service:
            def complete(self,*args):raise AssertionError('Must not call model for empty feasible catalog')
        with self.assertRaises(AgentGenerationError) as raised:
            BuildingFloorAgent(Service(),model_id='test').plan(b,base,replace(spec,room_count_strategy='fixed',rooms_per_floor=2))
        self.assertEqual(raised.exception.attempts,())

    def test_access_interpretation_requires_cited_goals(self):
        b,base,spec=self.large_plate()
        quote='卧室不要作为通道'
        goals=validate_goals({'goals':[{'source_quote':quote,'preference':quote,'levels':['room']}]},quote)
        class Service:
            def complete(self,messages,schema):
                assert quote in messages[1].content
                return json.dumps({'applicability':'unrelated','organization':'unspecified','supporting_goal_ids':[],
                    'reason':'Access only','access_constraints':[{'predicate':'not_through_room','function':'bedroom',
                    'applicability':'uniform','supporting_goal_ids':['invented']}]})
        agent=BuildingFloorAgent(Service(),model_id='test');agent.design_goals=goals
        with self.assertRaises(AgentGenerationError):interpret_organization(agent,b)
