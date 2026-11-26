"""Offline authored candidates: mechanism tests, never model-success samples."""
import json
import unittest
from copy import deepcopy
from unittest.mock import patch
from dataclasses import replace

from cityg.agents.context import ProgressiveContext, ContextSection
from cityg.agents.hierarchy import _ProgressiveProgramAgent
from cityg.agents.protocol import normalize_program
from cityg.agents.requirement import AgentGenerationError
from cityg.agents.streetscape import StreetscapeAgent
from cityg.planning.baseline import BaselineCityPlanner
from cityg.planning.streetscape import StreetProgramPlanner
from cityg.schemas import CitySpec
from test_hierarchy_agents import FakeService, final, request
import test_room_constraints as room_fixtures
import test_visual_grounding as grounding_fixtures
from cityg.validation.visual_grounding import room_facts, check_issue


class ProtocolRecoveryTests(unittest.TestCase):
    def test_street_wrapper_and_unknown_fields_cannot_silently_become_noop(self):
        city=BaselineCityPlanner().plan(CitySpec(building_count=1))
        road=city.road_network.segments[0].id
        for invalid in ({'StreetNetworkProgram':{'segments':[]}},
                        {'segments':[{'road_id':road,'positive_spacings':{'tree_m':16}}]}):
            service=FakeService([final(invalid)])
            with self.assertRaises(AgentGenerationError):
                StreetscapeAgent(service,max_calls=1,segment_batch_size=32).plan(city)

    def test_street_provenance_only_is_not_a_semantic_change(self):
        city=BaselineCityPlanner().plan(CitySpec(building_count=1))
        service=FakeService([final({'segments':[{'road_id':city.road_network.segments[0].id}]})])
        result=StreetscapeAgent(service,max_calls=1,segment_batch_size=32).plan(city)
        self.assertEqual(result.diagnostics['changed_road_ids'],[])

    def test_two_disclosures_do_not_consume_only_proposal(self):
        service=FakeService([request('a'),request('b'),final({'ok':True})])
        ctx=ProgressiveContext({},(ContextSection('a','a',1),ContextSection('b','b',2)))
        result=_ProgressiveProgramAgent(service,max_calls=1)._run(ctx,'test',lambda x:x)
        self.assertEqual(len(result.attempts),3)
        self.assertEqual(result.diagnostics['proposal_attempts'],1)

    def test_repeat_details_are_bounded_and_feedback_has_remaining_keys(self):
        service=FakeService([request('a')]*5)
        ctx=ProgressiveContext({},(ContextSection('a','a',1),))
        with self.assertRaises(AgentGenerationError) as error:
            _ProgressiveProgramAgent(service,max_calls=2)._run(ctx,'test',lambda x:x)
        self.assertEqual(len(error.exception.attempts),3)
        feedback=json.loads(service.calls[-1][0][-1].content)
        self.assertEqual(feedback['context_state']['already_disclosed'],['a'])
        self.assertEqual(feedback['context_state']['available_keys'],[])

    def test_enum_wrappers_are_audited_but_unknowns_are_not_guessed(self):
        original={'profiles':[{'function':'residential','room_function_cycle':['>bedroom','`bathroom`','>spa']}],
                  'id':'>bedroom','count':10}
        changed,events=normalize_program(original)
        self.assertEqual(changed['profiles'][0]['room_function_cycle'],['bedroom','bathroom','>spa'])
        self.assertEqual(changed['id'],'>bedroom')
        self.assertEqual(len(events),2)
        self.assertEqual(original['profiles'][0]['room_function_cycle'][0],'>bedroom')

    def test_street_chunk_failure_preserves_other_chunks_and_source(self):
        city=BaselineCityPlanner().plan(CitySpec(building_count=4))
        before=deepcopy(city)
        from cityg.planning.appearance import appearance_program_for_city
        baseline=StreetProgramPlanner().plan(city,appearance_program_for_city(city))
        count=len(baseline.segments)
        self.assertGreater(count,1)
        responses=[]
        for i,row in enumerate(baseline.segments):
            responses.append(final({'segments':[{'road_id':'foreign'}] if i==1 else
                [{'road_id':row.road_id,'light_family':'square'}]}))
        result=StreetscapeAgent(FakeService(responses),max_calls=1,segment_batch_size=1).plan(city)
        self.assertEqual(result.diagnostics['fallback_road_ids'],[baseline.segments[1].road_id])
        self.assertEqual(result.program.segments[1],baseline.segments[1])
        self.assertEqual(result.program.segments[0].light_family,'square')
        self.assertEqual(city,before)


class LocalPoseTests(unittest.TestCase):
    def test_compact_patch_preserves_unedited_inventory(self):
        from cityg.refinement.room_patch import expand_local_patch
        fixture=room_fixtures.RoomConstraintsTests();fixture.setUp()
        authored=room_fixtures.design('bed','wardrobe')
        fixture.room.metadata['room_design']={'status':'accepted',**authored.to_dict()}
        patch_data={'room_id':'r','reason':'Move storage to west wall',
            'group_updates':[{'group_id':'g1','placement':{'mode':'wall','wall':'west',
                'contact':'back','max_gap_m':.2}}]}
        expanded=expand_local_patch(patch_data,fixture.room,['g0','g1'])
        self.assertEqual(expanded['design']['protected_groups'],['g0'])
        self.assertEqual(expanded['design']['groups'][0],authored.groups[0])
        self.assertEqual(expanded['design']['groups'][1]['anchor'],authored.groups[1]['anchor'])
        with self.assertRaisesRegex(ValueError,'out-of-scope'):
            expand_local_patch(patch_data,fixture.room,['g0'])

    def test_compact_patch_passes_real_room_agent_preflight(self):
        from cityg.refinement.room import RoomProgramAgent
        from types import SimpleNamespace
        fixture=room_fixtures.RoomConstraintsTests();fixture.setUp()
        authored=room_fixtures.design('bed','wardrobe')
        fixture.floor.objects=fixture.place(authored)
        fixture.room.metadata['room_design']={'status':'accepted',**authored.to_dict()}
        target=next(o for o in fixture.floor.objects if o.metadata['group_key']=='g1')
        wall=target.metadata['wall_binding']['side']
        service=FakeService([{'room_id':'r','reason':'Keep a feasible storage contact',
            'group_updates':[{'group_id':'g1','placement':{'mode':'wall','wall':wall,
                'contact':'back','max_gap_m':.2}}]}])
        city=BaselineCityPlanner().plan(CitySpec(building_count=1))
        building=next(city.iter_buildings())
        result=RoomProgramAgent(service,max_attempts=1).propose(city,building,fixture.floor,
            fixture.room,visual_feedback={'target_group_ids':['g1']},use_cache=False)
        self.assertEqual(result.program.design.protected_groups,('g0',))
        self.assertIn('_local_patch',result.raw)

    def test_local_candidate_search_uses_existing_pose_without_mutating_source(self):
        fixture=room_fixtures.RoomConstraintsTests();fixture.setUp()
        authored=room_fixtures.design('bed','wardrobe')
        fixture.floor.objects=fixture.place(authored)
        fixture.room.metadata['room_design']={'status':'accepted',**authored.to_dict()}
        before=deepcopy(fixture.floor.objects)
        fixture.place(authored)
        self.assertGreater(fixture.room.metadata['layout_solver_diagnostics']['prior_pose_candidates'],0)
        self.assertEqual(fixture.floor.objects,before)

    def test_confirmed_failure_not_hidden_by_an_unrelated_unknown_fact(self):
        facts={'supported':True,'checks':[{'kind':'containment','ok':False},
                                         {'kind':'containment','ok':None}]}
        self.assertEqual(check_issue({'issue_code':'room_object_outside'},facts)['status'],'confirmed')

    def test_metric_certificate_rejects_stale_pose(self):
        from cityg.planning.room_metric_frame import restore_metric_object, MetricRoomInfeasible
        from cityg.planning.room_envelope import metric_envelope, room_geometry_binding
        fixture=grounding_fixtures.VisualGroundingTests();fixture.setUp()
        b=next(fixture.city.iter_buildings());f=fixture.f;r=fixture.r;o=fixture.obj
        env=metric_envelope(b,f,r);bb=b.footprint;rb=env['bounds'];frame=env['frame']
        o.metadata['metric_room_placement']={
            'center':[o.position.x,o.position.y], 'dimensions_m':[o.width_m,o.depth_m,o.height_m],
            'canonical_binding':[o.position.x,o.position.y,o.width_m,o.depth_m,o.height_m,o.rotation_deg,o.asset_id],
            'source_room_geometry':room_geometry_binding(f,r),
            'source_floor_vertical_extent':[f.elevation_m,f.height_m],
            'source_footprint':[bb.min_x,bb.min_y,bb.max_x,bb.max_y],
            'source_massing_parts':frame['parts'],
            'source_frame_bounds':[frame[k] for k in ('min_x','min_y','max_x','max_y')],
            'room_bounds':[rb.min_x,rb.min_y,rb.max_x,rb.max_y], 'canonical_scale':env['scale']}
        self.assertEqual(restore_metric_object(o,b,f,r,env).position,o.position)
        self.assertTrue(room_facts(fixture.city,r.id)['supported'])
        o.rotation_deg=90
        self.assertFalse(room_facts(fixture.city,r.id)['supported'])
        with self.assertRaises(MetricRoomInfeasible):restore_metric_object(o,b,f,r,env)


if __name__=='__main__': unittest.main()
