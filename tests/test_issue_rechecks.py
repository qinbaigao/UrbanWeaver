from copy import deepcopy
import unittest

from cityg.issue_rechecks import issue_key,plan_issue_rechecks
from cityg.planning.baseline import BaselineCityPlanner
from cityg.schemas import CitySpec


class IssueRecheckTests(unittest.TestCase):
    def setUp(self):
        self.city=BaselineCityPlanner().plan(CitySpec(building_count=1))
        self.rooms=[r for r in self.city.iter_rooms() if r.function!='corridor'][:2]
        self.views=[{'view_id':f'view_{i}','target_entity_ids':[r.id],'mode':'room',
                     'camera_position':[i,0,5],'look_at':[i,0,0]} for i,r in enumerate(self.rooms)]
        self.before={'selected_views':self.views}
        self.review={'aggregated_issues':[{'issue_id':'issue_001','entity_id':r.id,'category':'room',
            'issue_code':'room_access_blocked','description':f'access {i}', 'confidence':.9,
            'evidence_view_ids':[f'view_{i}']} for i,r in enumerate(self.rooms)]}
        self.after={'selected_views':self.views,'candidates':self.views}

    def test_recheck_uses_actual_applied_camera_canvas_and_object_binding(self):
        import json
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from cityg.adaptive_review import aggregate_visual_reviews
        from cityg.visual_evidence import capture_signature
        from cityg.visual_review import VisualReviewAgent
        camera={'camera_position':[0,0,5],'look_at':[0,0,0],'up':[0,1,0],'fov_deg':45}
        status={'ready':True,'signal_available':True,'geometry_streaming':{'ready':True},
                'view_status':{'camera':camera}, 'capture_canvas':{'width':600,'height':600}}
        self.review['capture_signatures']={'view_0':capture_signature(status)}
        issue=self.review['aggregated_issues'][0]
        self.assertNotEqual(issue_key(dict(issue,target_object_ids=['chair_A'])),
                            issue_key(dict(issue,target_object_ids=['chair_B'])))
        plan=plan_issue_rechecks(self.city,self.before,self.review,self.after,max_views=1)
        pending=next(r for r in plan['issue_recheck_queue'] if r['assigned_view_ids'])
        class Vision:
            def review(self,prompt,images):
                return json.dumps({'summary':'Review','issues':[],'issue_followups':[{
                    'issue_key':pending['issue_key'],'confidence':.95,'verdict':'not_observed',
                    'target_visibility':'clear','evidence_view_ids':['view_0'],'reason':'entry visible'}]})
        with TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'view_0.png').touch()
            for width,expected in ((600,True),(400,False)):
                status['capture_canvas']['width']=width
                (root/'asset_load_status.json').write_text(json.dumps({'views':{'view_0':status}}))
                result=aggregate_visual_reviews(plan,root,VisualReviewAgent(Vision()))
                self.assertEqual(result['issue_followups'][0]['comparable_loaded_evidence'],expected)

    def test_modified_issue_first_with_explicit_uncovered_queue(self):
        plan=plan_issue_rechecks(self.city,self.before,self.review,self.after,max_views=1,touched=[self.rooms[1].id])
        self.assertEqual(plan['selected_views'][0]['view_id'],'view_1')
        self.assertEqual(plan['issue_recheck_summary']['uncovered'],1)
        self.assertFalse(any(r['verified_resolved'] for r in plan['issue_recheck_queue']))
        self.assertTrue(plan['issue_recheck_queue'][0]['candidates'][0]['comparable_camera'])

    def test_recomputed_or_replacement_camera_is_not_comparable(self):
        after=deepcopy(self.after)
        after['candidates'][0]['camera_position']=[0,0,10]
        after['selected_views']=[]
        plan=plan_issue_rechecks(self.city,self.before,self.review,after,max_views=2)
        row=next(r for r in plan['issue_recheck_queue'] if r['entity_id']==self.rooms[0].id)
        self.assertEqual(row['candidates'][0]['relation'],'recomputed_camera')
        self.assertFalse(row['candidates'][0]['comparable_camera'])

    def test_model_local_ids_do_not_merge_distinct_issues(self):
        left,right=self.review['aggregated_issues']
        self.assertEqual(left['issue_id'],right['issue_id'])
        self.assertNotEqual(issue_key(left),issue_key(right))

    def test_missing_entity_cannot_be_counted_as_resolved(self):
        self.review['aggregated_issues'][0]['entity_id']='deleted_room'
        plan=plan_issue_rechecks(self.city,self.before,self.review,self.after,max_views=2)
        row=next(r for r in plan['issue_recheck_queue'] if r['entity_id']=='deleted_room')
        self.assertEqual(row['status'],'target_unavailable')
        self.assertFalse(row['verified_resolved'])

    def test_issue_directed_supplement_does_not_exceed_budget_or_claim_comparability(self):
        self.review['aggregated_issues']=self.review['aggregated_issues'][:1]
        top={**self.views[0],'view_id':'room_top_00','camera_position':[0,0,12]}
        self.after['candidates']=[*self.views,top]
        plan=plan_issue_rechecks(self.city,self.before,self.review,self.after,max_views=2)
        row=plan['issue_recheck_queue'][0]
        self.assertEqual(row['assigned_view_ids'],['view_0','room_top_00'])
        self.assertEqual(row['candidates'][1]['relation'],'question_directed_supplement')
        self.assertFalse(row['candidates'][1]['comparable_camera'])
        self.assertFalse(row['verified_resolved'])
        small=plan_issue_rechecks(self.city,self.before,self.review,self.after,max_views=1)
        self.assertEqual(len(small['selected_views']),1)
