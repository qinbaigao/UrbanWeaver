import tempfile
import unittest
from pathlib import Path

from cityg.memory import MemoryStore
from cityg.planning.baseline import BaselineCityPlanner
from cityg.review_memory import record_observations, bounded_review_outcome
from cityg.schemas import CitySpec
from cityg.serialization import save_json


class ReviewMemoryTests(unittest.TestCase):
    def test_issue_resolution_needs_comparable_current_and_independent_proof(self):
        from cityg.issue_rechecks import issue_key
        issue={'entity_id':'r','category':'room','issue_code':'access','description':'blocked'}
        token=issue_key(issue)
        before={'batch_count':1,'available_batches':1,'aggregated_issues':[issue]}
        evidence={'issue_key':token,'verdict':'not_observed','confidence':.95,
                  'expected_entity_version':2,'comparable_loaded_evidence':True,'target_visibility':'clear'}
        after={'batch_count':1,'available_batches':1,'aggregated_issues':[], 'issue_followups':[evidence]}
        plan={'selected_views':[{'target_entity_ids':['r']}],
              'issue_recheck_queue':[{'issue_key':token,'status':'scheduled'}]}
        proof={'ok':True,'before_failed':True,'entity_id':'r','entity_version':2,
               'check_id':'access','source':'deterministic_checker'}
        traces={'room':[{'room_id':'r','repair_issue_keys':[token], 'transaction':{'status':'accepted'}}]}
        def outcome(**kwargs):
            return bounded_review_outcome(before,after,plan,traces,current_versions={'r':2},**kwargs)['issue_followup'][0]
        self.assertEqual(outcome()['status'],'visual_absence_requires_independent_check')
        self.assertTrue(outcome(deterministic_checks={token:proof})['verified_resolved'])
        missing=bounded_review_outcome(before,after,plan,{},current_versions={'r':2},deterministic_checks={token:proof})
        self.assertEqual(missing['issue_followup'][0]['status'],'no_accepted_issue_repair')
        self.assertEqual(missing['structurally_resolved_issue_count'],1)
        self.assertEqual(missing['verified_resolved_issue_count'],0)
        for key,value,status in (
            ('target_visibility','occluded','inconclusive'),('target_visibility',None,'inconclusive'),
            ('comparable_loaded_evidence',False,'noncomparable_or_unready_evidence'),
            ('expected_entity_version',1,'stale_or_unverified_evidence'),
            ('verdict','uncertain','inconclusive'),('verdict','present','observed_again')):
            after['issue_followups']=[dict(evidence,**{key:value})]
            row=outcome(deterministic_checks={token:proof})
            self.assertEqual(row['status'],status);self.assertFalse(row['verified_resolved'])
        after['issue_followups']=[evidence]
        for key,value in (('before_failed',False),('entity_version',1),('source','vlm')):
            self.assertFalse(outcome(deterministic_checks={token:dict(proof,**{key:value})})['verified_resolved'])
        after['aggregated_issues']=[dict(issue,issue_code='unrelated',description='different defect')]
        self.assertEqual(outcome()['status'],'visual_absence_requires_independent_check')
        after['aggregated_issues']=[issue]
        row=outcome(deterministic_checks={token:proof})
        self.assertEqual(row['status'],'contradictory_evidence');self.assertFalse(row['verified_resolved'])
        after['aggregated_issues']=[dict(issue,description='possibly same defect differently worded')]
        self.assertEqual(outcome()['status'],'related_issue_requires_disambiguation')

    def test_staged_evidence_paths_relocated_and_rehashed(self):
        from cityg.memory import MemoryRecord
        with tempfile.TemporaryDirectory() as tmp, MemoryStore(Path(tmp)/'memory.sqlite') as store:
            before = MemoryRecord('v','visual_evidence','entity','room',
                {'image':'/tmp/.pending/view.png'}, validation_status='accepted')
            store.put(before)
            store.relocate_artifact_paths('/tmp/.pending','/tmp/published')
            after = store.get('v')
            self.assertEqual(after.content['image'],'/tmp/published/view.png')
            self.assertNotEqual(before.content_hash,after.content_hash)

    def test_upward_conflict_never_authorizes_parent_mutation(self):
        from cityg.planning.conflicts import planning_conflict
        city = BaselineCityPlanner().plan(CitySpec(building_count=1))
        room = next(city.iter_rooms())
        conflict = planning_conflict(city, room.id, code='capacity', reason='insufficient area',
            stage='room', attempts_used=2, attempt_limit=2)
        self.assertTrue(conflict['entity_binding_verified'])
        self.assertIsNotNone(conflict['responsible_ancestor'])
        self.assertFalse(conflict['automatic_scope_expansion'])
        self.assertEqual(conflict['budget']['remaining'], 0)
        self.assertTrue(conflict['options'][-1]['requires_user_approval'])

    def test_evidence_tracks_versions_and_loading_failures(self):
        city = BaselineCityPlanner().plan(CitySpec(building_count=1))
        room = next(city.iter_rooms())
        with tempfile.TemporaryDirectory() as folder, MemoryStore(Path(folder)/'memory.sqlite') as store:
            root = Path(folder); (root/'view.png').write_bytes(b'fixture')
            plan = {'selected_views':[{'view_id':'view','target_entity_ids':[room.id], 'mode':'room'}]}
            save_json({'views':{'view':{'ready':True,'signal_available':True,'failed':0,'fallback':0,
                'geometry_streaming':{'ready':True}}}}, root/'asset_load_status.json')
            rows = record_observations(store, city, plan, root, stage='before')
            record = store.get(rows[0]['memory_id'])
            self.assertEqual(record.validation_status, 'accepted')
            self.assertEqual(record.content['entity_versions'][room.id], record.world_version)
            store.invalidate_entities([room.id], reason='edit')
            self.assertEqual(store.get(record.memory_id).validation_status, 'stale')
            save_json({'views':{'view':{'ready':True,'signal_available':True,'failed':0,'fallback':1}}}, root/'asset_load_status.json')
            row = record_observations(store, city, plan, root, stage='after')[0]
            self.assertFalse(row['ready'])
            self.assertEqual(store.get(row['memory_id']).validation_status, 'rejected')
            save_json({'views':{'view':{'ready':True,'signal_available':False}}}, root/'asset_load_status.json')
            self.assertFalse(record_observations(store, city, plan, root, stage='no_signal')[0]['ready'])

    def test_missing_coverage_is_never_called_resolution(self):
        before = {'batch_count':1,'available_batches':1,'aggregated_issues':[
            {'entity_id':'room_a','category':'layout'}, {'entity_id':'room_b','category':'lighting'}]}
        after = {'batch_count':1,'available_batches':1,'aggregated_issues':[]}
        result = bounded_review_outcome(before, after, {'selected_views':[{'target_entity_ids':['room_a']}]}, {})
        self.assertEqual([r['status'] for r in result['issue_followup']], ['not_observed_in_recheck','not_rechecked'])
        self.assertFalse(any(r['verified_resolved'] for r in result['issue_followup']))
        self.assertFalse(result['repair_rate_computed'])
        self.assertFalse(result['automatic_retry_allowed'])


if __name__ == '__main__': unittest.main()
