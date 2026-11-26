import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from cityg.adaptive_review import aggregate_visual_reviews
from cityg.visual_review import VisualReviewAgent, validate_issue_followups, validate_followup_consistency, validate_review_bindings


class VisualReviewCompatibilityTests(unittest.TestCase):
    def test_production_review_receives_direct_compiled_inventory(self):
        from test_visual_evidence import VisualEvidenceTests
        view=VisualEvidenceTests().inventory_view()
        class Service:
            def review(self,*args):
                return json.dumps({'issues':[],'summary':'fixture'})
        class Reviewer(VisualReviewAgent):
            def review(self,prompt,paths,*,context=None):
                facts=context['compiled_inventory_by_view']['v']
                assert facts['counts']=={'chair':1}
                assert facts['scene_freshness_verified'] is False
                return super().review(prompt,paths,context=context)
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory)/'v.png').touch()
            report=aggregate_visual_reviews({'selected_views':[view]},directory,Reviewer(Service()))
        self.assertEqual(report['available_batches'],1,report)

    def test_group_from_another_room_cannot_bind(self):
        bindings={'room_a':[{'group_id':'desk'}],'room_b':[{'group_id':'bed'}]}
        with self.assertRaisesRegex(ValueError,'unknown for this room'):
            validate_review_bindings([{'entity_id':'room_a','issue_code':'room_group_misaligned',
                                       'target_group_ids':['bed']}],bindings)
        validate_review_bindings([{'entity_id':'room_a','issue_code':'room_group_misaligned',
                                   'target_group_ids':['desk']}],bindings)

    def test_missing_group_binding_is_retried_on_same_images(self):
        class Service:
            calls=[]
            def complete_with_metadata(self,messages,schema):
                self.calls.append(messages)
                self.enum=schema['properties']['issues']['items']['properties']['target_group_ids']['items']['enum']
                issue={'issue_id':'i','severity':'warning','category':'room','issue_code':'room_group_misaligned',
                    'entity_id':'r','description':'wall mismatch','suggested_action':'reposition',
                    'target_group_ids':[] if len(self.calls)==1 else ['desk']}
                return SimpleNamespace(content=json.dumps({'issues':[issue],'summary':'checked'}))
        service=Service()
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'r.png';p.touch()
            result=VisualReviewAgent(service).review('inspect',[p],context={'room_group_bindings':{
                'r':[{'group_id':'desk','accepted_placement':{'wall':'north'}}]}})
        self.assertTrue(result.available,result.error)
        self.assertEqual(len(result.attempts),2)
        self.assertEqual(result.issues[0].target_group_ids,('desk',))
        self.assertEqual(service.enum,['desk'])
        self.assertEqual(service.calls[0][0].image_paths,service.calls[1][0].image_paths)

    def test_followup_prose_contradiction_is_not_silently_flipped(self):
        context={'pending_issue_checks':[{'issue_key':'i','entity_id':'r'}]}
        for reason in ('The issue persists in the provided views.',
                       'The pending issue for building_000 is confirmed in the current view.',
                       '该问题仍然存在'):
            row={'issue_key':'i','verdict':'not_observed','reason':reason}
            with self.assertRaisesRegex(ValueError,'Contradictory'):
                validate_followup_consistency([], [row], context)
            self.assertEqual(row['verdict'],'not_observed')
        validate_followup_consistency([], [{'issue_key':'i','verdict':'not_observed',
            'reason':'The issue is not observed in the current view.'}],context)

    def test_persistent_contradiction_is_unavailable_not_clean(self):
        class Service:
            def review(self,*args):return json.dumps({'issues':[],'summary':'check',
                'issue_followups':[{'issue_key':'i','verdict':'not_observed','confidence':.9,
                    'reason':'The issue persists.','evidence_view_ids':['v']}]})
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'v.png';p.touch()
            result=VisualReviewAgent(Service()).review('inspect',[p],context={'view_ids':['v'],
                'pending_issue_checks':[{'issue_key':'i','assigned_view_ids':['v']}]})
        self.assertFalse(result.available)
        self.assertEqual(len(result.attempts),2)

    def test_schema_restricts_each_followup_to_its_own_views(self):
        class Service:
            def complete_with_metadata(self,messages,schema):
                entries=schema['properties']['issue_followups']['prefixItems']
                self.prompt=messages[0].content
                self.enums=[entry['properties']['evidence_view_ids']['items']['enum'] for entry in entries]
                return SimpleNamespace(content=json.dumps({'summary':'checked','issues':[],
                    'issue_followups':[{'issue_key':'i','verdict':'uncertain','confidence':.5,
                        'reason':'occluded','evidence_view_ids':['a']}]}),usage={},finish_reason='stop')
        service=Service()
        with tempfile.TemporaryDirectory() as folder:
            image=Path(folder)/'a.png'; image.touch()
            result=VisualReviewAgent(service).review('check',[image],context={'view_ids':['a','b'],
                'pending_issue_checks':[{'issue_key':'i','assigned_view_ids':['a','outside']}]})
        self.assertTrue(result.available)
        self.assertEqual(service.enums,[['a']])
        self.assertIn('present = the defect is visible or still remains',service.prompt)
        self.assertIn('A proxy-only or occluded view means uncertain',service.prompt)

    def test_candidate_promotion_cannot_bypass_proxy_only_evidence(self):
        class Service:
            def review(self,*args):
                return json.dumps({'summary':'test','issues':[{
                    'issue_id':'i','severity':'warning','category':'road','entity_id':None,
                    'candidate_entity_ids':['road'],'confidence':.99,'binding_confidence':.99,
                    'issue_code':'street_underfurnished','description':'missing benches','suggested_action':'add'}]})
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory)/'v.png').touch()
            (Path(directory)/'asset_load_status.json').write_text(json.dumps({'views':{'v':{
                'ready':True,'signal_available':True,'render_profile':'review',
                'geometry_streaming':{'ready':True}}}}))
            report=aggregate_visual_reviews({'selected_views':[{'view_id':'v','kind':'global',
                'target_entity_ids':['road']}]},directory,VisualReviewAgent(Service()))
        self.assertFalse(report['aggregated_issues'])
        self.assertEqual(report['deferred_issues'][0]['deferred_reason'],
                         'proxy_overview_requires_local_detail_evidence')

    def test_missing_or_invalid_confidence_never_becomes_certainty(self):
        payload={'summary':'test','issues':[{'issue_id':'i','severity':'warning','category':'room',
            'entity_id':'r','description':'uncertain','suggested_action':'inspect'}]}
        class Service:
            def review(self,*args): return json.dumps(payload)
        with tempfile.TemporaryDirectory() as directory:
            image=Path(directory)/'view.png';image.touch()
            result=VisualReviewAgent(Service(),max_attempts=1).review('test',[image])
            self.assertTrue(result.available)
            self.assertEqual(result.issues[0].confidence,0)
            self.assertEqual(result.issues[0].binding_confidence,0)
            self.assertEqual(result.issues[0].binding_basis,'none')
            for score in (float('nan'),float('inf'),1.1,-.1,True,'0.9'):
                payload['issues'][0]['confidence']=score
                self.assertFalse(VisualReviewAgent(Service(),max_attempts=1).review('test',[image]).available)

    def test_explicit_followups_require_complete_correct_view_binding(self):
        context={'view_ids':['a','b'],'pending_issue_checks':[
            {'issue_key':'i','assigned_view_ids':['a']}]}
        row={'issue_key':'i','verdict':'not_observed','confidence':.95,
             'reason':'examined','evidence_view_ids':['a']}
        self.assertEqual(validate_issue_followups([row],context),[row])
        for rows in ([],[row,row],[dict(row,issue_key='unknown')],
                     [dict(row,evidence_view_ids=['b'])],[dict(row,evidence_view_ids=[])],
                     [dict(row,confidence=float('nan'))]):
            with self.assertRaises(ValueError): validate_issue_followups(rows,context)

    def test_malformed_or_truncated_json_gets_bounded_same_image_retry(self):
        for first in (SimpleNamespace(content='{"issues": [',finish_reason='stop'),
                      SimpleNamespace(content='{"issues": [], "summary":"cut"}',finish_reason='length')):
            class Service:
                def __init__(self): self.calls=[]
                def complete_with_metadata(self,messages,schema):
                    self.calls.append(messages)
                    return first if len(self.calls)==1 else SimpleNamespace(
                        content='{"issues": [], "summary":"checked"}',finish_reason='stop')
            service=Service()
            with tempfile.TemporaryDirectory() as directory:
                image=Path(directory)/'room.png';image.touch()
                result=VisualReviewAgent(service).review('inspect',[image])
            self.assertTrue(result.available)
            self.assertEqual(len(result.attempts),2)
            self.assertIsNotNone(result.attempts[0]['error'])
            self.assertEqual(service.calls[0][0].image_paths,service.calls[1][0].image_paths)
            for call in service.calls:
                self.assertIn('room_design.zones[].position',call[0].content)
                self.assertIn('opaque identifiers',call[0].content)
                self.assertIn('unrotated reference',call[0].content)

    def test_repeated_bad_json_is_unavailable_not_clean(self):
        class Service:
            def review(self,*args): return '{}'
        with tempfile.TemporaryDirectory() as directory:
            image=Path(directory)/'room.png';image.touch()
            result=VisualReviewAgent(Service(),max_attempts=2).review('inspect',[image])
        self.assertFalse(result.available)
        self.assertEqual(result.to_dict()['model_calls'],2)

    def test_wire_schema_omits_unique_items_and_local_parser_deduplicates(self):
        class Service:
            def complete_with_metadata(self, messages, schema):
                assert 'uniqueItems' not in json.dumps(schema)
                return SimpleNamespace(content=json.dumps({'summary': 'test', 'issues': [{
                    'issue_id': 'i1', 'severity': 'warning', 'category': 'room',
                    'description': 'test', 'suggested_action': 'inspect',
                    'target_group_ids': ['desk', 'desk', 'bed'],
                }]}))
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / 'room.png'
            image.touch()
            result = VisualReviewAgent(Service()).review('test', [image])
        self.assertTrue(result.available, result.error)
        self.assertEqual(result.issues[0].target_group_ids, ('desk', 'bed'))

    def test_failed_batches_are_not_a_clean_review(self):
        class Service:
            def review(self, *args):
                raise RuntimeError('model unavailable')
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / 'room.png').touch()
            report = aggregate_visual_reviews(
                {'selected_views': [{'view_id': 'room', 'target_entity_ids': []}]},
                directory, VisualReviewAgent(Service()),
            )
        self.assertEqual(report['status'], 'unavailable')
        self.assertEqual(report['available_batches'], 0)
        self.assertEqual(report['batch_count'], 1)
        self.assertIn('model unavailable', report['batches'][0]['error'])

    def test_candidate_promotion_cannot_bypass_failed_loading(self):
        class Service:
            def review(self,*args):
                return json.dumps({'summary':'test','issues':[{
                    'issue_id':'i','severity':'warning','category':'room','entity_id':None,
                    'candidate_entity_ids':['r'],'confidence':.99,'binding_confidence':.99,
                    'description':'missing furniture','suggested_action':'add'}]})
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory)/'v.png').touch()
            report=aggregate_visual_reviews({'selected_views':[{'view_id':'v','target_entity_ids':['r']}]},
                directory,VisualReviewAgent(Service()))
        self.assertFalse(report['aggregated_issues'])
        self.assertEqual(report['deferred_issues'][0]['deferred_reason'],
                         'render_evidence_not_ready_after_binding')

    def test_complementary_weak_scores_do_not_become_strong_evidence(self):
        class Service:
            calls=0
            def review(self,*args):
                self.calls+=1
                return json.dumps({'summary':'test','issues':[{
                    'issue_id':'i','severity':'warning','category':'room','entity_id':'r',
                    'confidence':.99 if self.calls==1 else .4,
                    'binding_confidence':.4 if self.calls==1 else .99,
                    'description':'same claim','suggested_action':'inspect'}]})
        views=[{'view_id':v,'target_entity_ids':['r']} for v in ('a','b')]
        with tempfile.TemporaryDirectory() as directory:
            for v in views: (Path(directory)/(v['view_id']+'.png')).touch()
            (Path(directory)/'asset_load_status.json').write_text(json.dumps({'views':{
                v['view_id']:{'ready':True,'signal_available':True,'geometry_streaming':{'ready':True}}
                for v in views}}))
            report=aggregate_visual_reviews({'selected_views':views},directory,
                VisualReviewAgent(Service()),batch_size=1)
        self.assertEqual(len(report['aggregated_issues']),1)
        self.assertFalse(report['aggregated_issues'][0]['automatic_repair_allowed'])
