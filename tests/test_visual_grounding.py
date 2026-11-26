from copy import deepcopy
import unittest

from cityg.ccwp import build_world_program
from cityg.issue_rechecks import issue_key
from cityg.planning.baseline import BaselineCityPlanner
from cityg.schemas import CitySpec,Bounds2D,Point2D,Door,InteriorObject
from cityg.validation.visual_grounding import room_facts,check_issue,ground_review,resolution_proofs
from cityg.review_memory import bounded_review_outcome


class VisualGroundingTests(unittest.TestCase):
    def setUp(self):
        self.city=BaselineCityPlanner().plan(CitySpec(building_count=1,min_floors=1,max_floors=1))
        b=next(self.city.iter_buildings());b.metadata={};b.footprint=Bounds2D(0,0,12,10)
        self.f=b.floors[0];self.r=next(r for r in self.f.rooms if r.function!='corridor')
        self.r.bounds=Bounds2D(0,0,8,7);self.f.rooms=[self.r]
        self.f.doors=[Door('entry',self.r.id,None,Point2D(4,0),1.2)]
        self.r.metadata={'room_design':{'status':'accepted','intent':'north shelf (old reference prose)',
            'groups':[{'id':'north','anchor':{'id':'shelf','category':'bookcase'},'members':[],
                       'placement':{'mode':'wall','wall':'west','contact':'back','max_gap_m':.2}}],
            'group_relations':[], 'furnishing_brief':{'items':[{'category':'bookcase','minimum':1}]}}}
        self.obj=InteriorObject('shelf',self.r.id,'bookcase','bookcase',Point2D(.6,3),1,1,1.5,
            metadata={'group_key':'north','group_id':'room_north','group_anchor_id':'shelf',
                      'front_axis':'+X','orientation_confidence':1})
        self.f.objects=[self.obj];self.r.object_ids=[self.obj.id]
        self.city.world_program=build_world_program(self.city,producer='test',seed=17)
        self.issue={'entity_id':self.r.id,'category':'room','issue_code':'room_group_misaligned',
            'target_group_ids':['north'],'description':'shelf must face room','confidence':.99,'binding_confidence':.99}

    def test_reference_without_brief_keeps_concrete_inventory_check(self):
        self.r.metadata['room_design']['furnishing_brief']=None
        self.f.objects=[]
        facts=room_facts(self.city,self.r.id)
        self.assertEqual(facts['contract']['minimum_inventory'],[{'category':'bookcase','minimum':1}])
        self.assertEqual(check_issue({**self.issue,'issue_code':'room_function_incomplete'},facts)['status'],'confirmed')

    def test_old_compass_ids_prose_and_cached_checks_cannot_override_geometry(self):
        self.r.metadata['room_design']['constraint_checks']={'wall_bindings':False}
        source=deepcopy(self.city)
        report=ground_review(self.city,{'aggregated_issues':[self.issue]})
        i=report['aggregated_issues'][0]
        self.assertEqual(i['independent_verification']['status'],'not_supported_by_geometry')
        self.assertFalse(i['automatic_repair_allowed']);self.assertEqual(source,self.city)

    def test_real_failure_and_alias_binding_but_no_unknown_group_bypass(self):
        self.obj.rotation_deg=180
        self.issue['target_group_ids']=['room_north']
        report=ground_review(self.city,{'aggregated_issues':[self.issue]})
        self.assertTrue(report['aggregated_issues'][0]['automatic_repair_allowed'])
        for group in ([],['foreign']):
            issue={**self.issue,'target_group_ids':group}
            result=ground_review(self.city,{'aggregated_issues':[issue]})
            self.assertFalse(result['aggregated_issues'][0]['automatic_repair_allowed'])

    def test_style_and_unsupported_envelope_are_pending_not_success(self):
        issue={**self.issue,'issue_code':'room_style_incoherent'}
        self.assertEqual(check_issue(issue,room_facts(self.city,self.r.id))['status'],'unverified')
        outside={**self.issue,'entity_id':next(self.city.iter_buildings()).id,'category':'facade'}
        result=ground_review(self.city,{'aggregated_issues':[outside]})
        self.assertFalse(result['aggregated_issues'][0]['automatic_repair_allowed'])
        self.obj.metadata['orientation_confidence']='inferred'
        self.assertEqual(check_issue(self.issue,room_facts(self.city,self.r.id))['status'],'unverified')
        self.obj.metadata['orientation_confidence']='reviewed'
        self.assertEqual(check_issue(self.issue,room_facts(self.city,self.r.id))['status'],'not_supported_by_geometry')
        next(self.city.iter_buildings()).metadata['orientation_deg']=15
        self.assertFalse(room_facts(self.city,self.r.id)['supported'])

    def test_containment_inventory_and_door_access_are_recomputed(self):
        self.obj.position=Point2D(-1,3)
        facts=room_facts(self.city,self.r.id)
        self.assertEqual(check_issue({**self.issue,'issue_code':'room_object_outside'},facts)['status'],'confirmed')
        self.f.objects=[]
        facts=room_facts(self.city,self.r.id)
        self.assertEqual(check_issue({**self.issue,'issue_code':'room_function_incomplete'},facts)['status'],'confirmed')
        self.f.objects=[self.obj];self.obj.position=Point2D(4,.55);self.obj.width_m=4
        facts=room_facts(self.city,self.r.id)
        self.assertEqual(check_issue({**self.issue,'issue_code':'room_access_blocked'},facts)['status'],'confirmed')

    def test_grounding_reuses_live_checks_and_rechecks_retired_door_evidence(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        from cityg.memory import MemoryStore
        with TemporaryDirectory() as tmp, MemoryStore(Path(tmp)/'m.sqlite') as store:
            def verify():
                return ground_review(self.city,{'aggregated_issues':[self.issue]},memory_store=store)
            self.assertEqual(verify()['room_check_sources'][self.r.id],'recomputed')
            self.assertEqual(verify()['room_check_sources'][self.r.id],'reused')
            store.invalidate_entities([self.f.doors[0].id],reason='door_changed')
            self.assertEqual(verify()['room_check_sources'][self.r.id],'recomputed')
            self.obj.rotation_deg=180
            report=verify()
            self.assertEqual(report['room_check_sources'][self.r.id],'recomputed')
            self.assertTrue(report['aggregated_issues'][0]['automatic_repair_allowed'])

    def test_preproposal_guard_narrows_stale_scope(self):
        from cityg.refinement.room_repair_guard import RoomRepairGuard
        self.obj.rotation_deg=180
        issue={**self.issue,'editable_group_ids':['north','formerly_failed_neighbor']}
        guard=RoomRepairGuard(self.city,self.r.id,[issue])
        self.assertEqual(guard.feedback()['target_group_ids'],['north'])
        with self.assertRaises(ValueError):
            RoomRepairGuard(self.city,self.r.id,[dict(issue,editable_group_ids=['formerly_failed_neighbor'])])

    def test_actual_facing_dot_product_not_textual_compass_reasoning(self):
        other=deepcopy(self.obj);other.id='media';other.position=Point2D(6,3)
        other.metadata.update(group_key='media',group_anchor_id='media')
        self.f.objects.append(other)
        self.r.metadata['room_design']['group_relations']=[{'subject':'north','target':'media',
            'relation':'faces','required':True}]
        row=next(r for r in room_facts(self.city,self.r.id)['checks'] if r['check_id'].startswith('faces:'))
        self.assertTrue(row['ok']);self.assertAlmostEqual(row['cosine'],1)
        self.obj.rotation_deg=180
        row=next(r for r in room_facts(self.city,self.r.id)['checks'] if r['check_id'].startswith('faces:'))
        self.assertFalse(row['ok'])

    def test_resolution_requires_original_failure_unchanged_contract_and_current_evidence(self):
        correct=deepcopy(self.city);self.obj.rotation_deg=180
        before={'batch_count':1,'available_batches':1,'aggregated_issues':[self.issue]}
        proofs=resolution_proofs(self.city,correct,before);token=issue_key(self.issue)
        self.assertTrue(proofs[token]['ok'])
        version=proofs[token]['entity_version']
        after={'batch_count':1,'available_batches':1,'aggregated_issues':[],
            'issue_followups':[{'issue_key':token,'expected_entity_version':version,
                'comparable_loaded_evidence':True,'target_visibility':'clear','verdict':'not_observed','confidence':.95}]}
        plan={'selected_views':[{'target_entity_ids':[self.r.id]}],
              'issue_recheck_queue':[{'issue_key':token,'status':'queued'}]}
        traces={'room_layout':[{'room_id':self.r.id,'repair_issue_keys':[token],'transaction':{'status':'accepted'}}]}
        outcome=bounded_review_outcome(before,after,plan,traces,current_versions={self.r.id:version},
                                       deterministic_checks=proofs)
        self.assertEqual(outcome['verified_resolved_issue_count'],1)
        fake=deepcopy(correct)
        next(r for r in fake.iter_rooms() if r.id==self.r.id).metadata['room_design']['groups'][0]['placement']['wall']='east'
        self.assertFalse(resolution_proofs(self.city,fake,before)[token]['ok'])
        self.assertFalse(resolution_proofs(correct,correct,before))
        after['issue_followups'][0]['expected_entity_version']=version+1
        self.assertEqual(bounded_review_outcome(before,after,plan,{},current_versions={self.r.id:version},
            deterministic_checks=proofs)['verified_resolved_issue_count'],0)
