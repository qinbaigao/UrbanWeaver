import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from audit_natural_issues import audit_run, packet_views, rejected_attempts
from run_natural_issue_sample import run
from cityg.serialization import save_json


class NaturalIssueAuditTests(unittest.TestCase):
    def test_absent_or_unconfirmed_problems_have_no_repair_rate(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            save_json({'review':{'aggregated_issues':[{'independent_verification':{'status':'unverified'}}]}},
                root/'visual_review/adaptive_review_report.json')
            report=audit_run(root)
            self.assertIsNone(report['structural_repair_success_rate'])
            self.assertIsNone(report['visual_repair_success_rate'])
            self.assertEqual(report['confirmed_issue_count'],0)
            self.assertEqual(report['before']['status'],'not_available')

    def test_only_confirmed_proofs_form_structural_denominator(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            save_json({'independent_issue_checks':{'a':{'ok':True},'b':{'ok':False}}},
                root/'visual_review/adaptive_review_report.json')
            self.assertEqual(audit_run(root)['structural_repair_success_rate'],.5)

    def test_rejected_plans_are_not_final_scene_defects(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            save_json({'buildings':[{'attempts':[{'error':'bad dimensions'},{'error':None}]}]},
                root/'programs/building_floor_trace.json')
            save_json({'stages':[{'attempts':[{'error':'bad dimensions'},{'error':None}]}]},
                root/'programs/trace.json')
            self.assertEqual(len(rejected_attempts(root)),1)
            self.assertEqual(len(rejected_attempts(root)[0]['duplicate_trace_sources']),1)
            self.assertEqual(audit_run(root)['confirmed_issue_count'],0)

    def test_unlabelled_packet_has_no_model_findings(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);packet=root/'packet';packet.mkdir()
            review=root/'visual_review';images=review/'observations_before';images.mkdir(parents=True)
            (images/'room.png').write_bytes(b'test-image')
            save_json({'selected_views':[{'view_id':'room','kind':'room','target_entity_ids':['r']}]},
                      review/'observation_plan_before.json')
            save_json({'review':{'aggregated_issues':[{'description':'MODEL CLAIM'}]}},
                      review/'adaptive_review_report.json')
            rows=packet_views(root,'case',packet)
            self.assertEqual(len(rows),1)
            self.assertIsNone(rows[0]['label'])
            self.assertNotIn('MODEL CLAIM',json.dumps(rows))

    def test_disk_budget_skip_is_persisted_not_counted_as_attempt(self):
        with TemporaryDirectory() as tmp,patch('run_natural_issue_sample.source_snapshot',return_value={}),patch(
                'run_natural_issue_sample.shutil.disk_usage') as usage:
            usage.return_value.free=0
            root=Path(tmp)/'sample'
            run(root,{'cases':[{'id':'a'},{'id':'b'}],'split':'development','sampling_stop':'two'},Path('test.env'))
            report=json.loads((root/'sampling_report.json').read_text())
            self.assertEqual(report['attempted'],0)
            self.assertEqual(len(report['cases']),2)
