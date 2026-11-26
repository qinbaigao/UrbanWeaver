from copy import deepcopy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import test_visual_grounding as fixtures
from cityg.room_review_context import compact_room_context, compact_review_request, ROOM_PROMPT
from cityg.refinement.room_repair_guard import RoomRepairGuard, validate_design
from cityg.validation.visual_grounding import ground_review, room_facts, check_issue
from cityg.schemas import Point2D
from cityg.visual_evidence import room_visual_contract


class RoomReviewIntegrationTests(unittest.TestCase):
    def setUp(self):
        fx=fixtures.VisualGroundingTests();fx.setUp()
        self.city,self.f,self.r,self.obj,self.issue=fx.city,fx.f,fx.r,fx.obj,fx.issue
        self.b=next(self.city.iter_buildings())

    def grounded(self):
        return ground_review(self.city,{'aggregated_issues':[self.issue]})['aggregated_issues'][0]

    def test_compact_payload_has_actual_metric_and_no_cached_truth(self):
        self.r.metadata['room_design']['intent']='private_cached_error'
        self.r.metadata['room_design']['constraint_checks']={'secret':'private_cached_error'}
        c=compact_room_context(self.b,self.f,self.r)
        self.assertEqual(c['metric_geometry']['room_bounds_xyxy'],[0,0,8,7])
        self.assertNotIn('private_cached_error',json.dumps(c))
        c=compact_room_context(self.b,self.f,self.r,max_objects=0)
        self.assertTrue(c['objects_truncated'])
        self.assertTrue(c['omitted_geometry_is_unknown'])

    def test_room_boundary_drops_duplicate_context_and_preserves_rechecks(self):
        view={'kind':'room_interior','semantic_context':room_visual_contract(self.b,self.f,self.r)}
        context={'room_group_bindings':{},'pending_issue_checks':[{'id':'check'}],
                 'view_semantic_context':'duplicate','design_language_definitions':'unrelated',
                 'image_evidence':[{'image_index':1,'view_id':'v','target_entity_ids':[self.r.id],
                                    'renderer_status':{},'semantic_context':'duplicate'}]}
        prompt,c=compact_review_request('old',context,[view])
        self.assertEqual(prompt,ROOM_PROMPT)
        self.assertEqual(c['pending_issue_checks'],context['pending_issue_checks'])
        self.assertNotIn('duplicate',json.dumps(c));self.assertNotIn('unrelated',json.dumps(c))
        self.assertEqual(compact_review_request('old',context,[{'kind':'global'}]),('old',context))

    def test_real_aggregator_separates_room_pair_from_outdoor_prompt(self):
        from cityg.adaptive_review import aggregate_visual_reviews
        from cityg.visual_review import VisualReviewAgent
        seen=[]
        class Service:
            def review(self,prompt,images):
                seen.append((prompt,len(images)))
                return json.dumps({'summary':'No problem','issues':[]})
        semantics=room_visual_contract(self.b,self.f,self.r)
        views=[{'view_id':'global','kind':'global','target_entity_ids':[self.city.id]},
               *[{'view_id':name,'kind':'room_interior','target_entity_ids':[self.r.id],
                  'semantic_context':semantics} for name in ('room_top','room_side')]]
        with tempfile.TemporaryDirectory() as directory:
            for view in views:Path(directory,view['view_id']+'.png').touch()
            report=aggregate_visual_reviews({'selected_views':views},directory,VisualReviewAgent(Service()))
        self.assertEqual(report['available_batches'],2)
        room_calls=[c for c in seen if 'metric_local_v1' in c[0]]
        self.assertEqual(len(room_calls),1);self.assertEqual(room_calls[0][1],2)
        self.assertNotIn('design_language_definitions',room_calls[0][0])

    def add_innocent(self):
        other=deepcopy(self.obj);other.id='innocent';other.position=Point2D(6,5)
        other.metadata.update(group_key='other',group_anchor_id='innocent')
        self.f.objects.append(other)
        self.r.metadata['room_design']['groups'].append({'id':'other',
            'anchor':{'id':'innocent','category':'bookcase'},'placement':{'mode':'free'}})
        return other

    def test_object_claim_cannot_borrow_another_objects_containment_failure(self):
        self.add_innocent();self.obj.position=Point2D(-1,3)
        claim={**self.issue,'issue_code':'room_object_outside','target_group_ids':['north','other'],
               'target_object_ids':['innocent']}
        self.assertEqual(check_issue(claim,room_facts(self.city,self.r.id))['status'],'not_supported_by_geometry')
        claim['target_object_ids']=['shelf','innocent']
        result=ground_review(self.city,{'aggregated_issues':[claim]})['aggregated_issues'][0]
        self.assertEqual(result['editable_group_ids'],['north'])
        claim['target_object_ids']=['foreign']
        self.assertEqual(check_issue(claim,room_facts(self.city,self.r.id))['status'],'unverified')

    def test_access_attribution_uses_all_four_door_sides(self):
        for entry,obstacle in [((4,0),(4,.3)),((4,7),(4,6.7)),((0,3),(0.3,3)),((8,3),(7.7,3))]:
            with self.subTest(entry=entry):
                self.f.doors[0].position=Point2D(*entry);self.obj.position=Point2D(*obstacle)
                claim={**self.issue,'issue_code':'room_access_blocked','target_object_ids':['shelf']}
                checked=check_issue(claim,room_facts(self.city,self.r.id))
                self.assertEqual(checked['status'],'confirmed')

    def test_access_cannot_blame_innocent_neighbor(self):
        self.add_innocent();self.obj.position=Point2D(4,.3)
        claim={**self.issue,'issue_code':'room_access_blocked','target_group_ids':['other'],
               'target_object_ids':['innocent']}
        self.assertEqual(check_issue(claim,room_facts(self.city,self.r.id))['status'],'unverified')

    def test_counterfactual_cost_is_bounded_for_dense_rooms(self):
        for i in range(63):
            obj=deepcopy(self.obj);obj.id='extra_'+str(i);self.f.objects.append(obj)
        with patch('cityg.validation.visual_grounding.circulation_check',
                   return_value={'ok':False,'reason':'blocked'}) as walk:
            facts=room_facts(self.city,self.r.id)
        self.assertEqual(walk.call_count,1)
        rows=[r for r in facts['checks'] if r['check_id'].startswith('access_object:')]
        self.assertTrue(all(r['ok'] is None and r['attribution_budget_exceeded'] for r in rows))

    def test_contract_guard_rejects_goalpost_movement_before_assets(self):
        self.obj.rotation_deg=180
        guard=RoomRepairGuard(self.city,self.r.id,[self.grounded()])
        design=deepcopy(self.r.metadata['room_design']);design['groups'][0]['placement']['wall']='east'
        with self.assertRaises(ValueError):guard.check_program(SimpleNamespace(design=design))
        design=deepcopy(self.r.metadata['room_design']);design['groups'][0]['placement']['max_gap_m']=3
        with self.assertRaises(ValueError):validate_design(guard.design,design)

    def test_contract_accepts_equivalent_json_and_in_memory_sequences(self):
        original=deepcopy(self.r.metadata['room_design'])
        candidate=deepcopy(original)
        candidate['group_relations']=tuple(candidate['group_relations'])
        candidate['groups']=tuple(candidate['groups'])
        validate_design(original,candidate)

    def test_guard_accepts_real_fix_rejects_noop_and_frozen_change(self):
        other=self.add_innocent();self.obj.rotation_deg=180
        guard=RoomRepairGuard(self.city,self.r.id,[self.grounded()])
        self.assertFalse(guard(self.city)['ok'])
        self.obj.rotation_deg=0
        self.assertTrue(guard(self.city)['ok'])
        other.position=Point2D(5,5)
        self.assertFalse(guard(self.city)['ok'])

    def test_unsupported_scope_is_never_promoted_to_roomwide_edit(self):
        issue={**self.issue,'issue_code':'room_style_incoherent'}
        row=ground_review(self.city,{'aggregated_issues':[issue]})['aggregated_issues'][0]
        self.assertFalse(row['automatic_repair_allowed']);self.assertEqual(row['editable_group_ids'],[])
        with self.assertRaises(ValueError):RoomRepairGuard(self.city,self.r.id,[row])


if __name__=='__main__':unittest.main()
