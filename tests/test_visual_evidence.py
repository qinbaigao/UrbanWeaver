from dataclasses import replace
import unittest
from cityg.visual_review import VisualIssue,filter_review_issues
from cityg.visual_evidence import prototype_review_context, batch_evidence_constraints, compiled_inventory_facts
import test_floor_repartition as fixtures


class VisualEvidenceTests(unittest.TestCase):
    def inventory_view(self):
        return {'view_id':'v','kind':'room_interior','target_entity_ids':['r','f','b'],
            'semantic_context':{'room_id':'r','room_geometry_source':'compiled_manifest',
                'actual_furniture':[{'object_id':'o1','category':'chair'},
                                    {'object_id':'o2','category':'bed'}],
                'actual_furniture_total':2,'actual_furniture_truncated':False,
                'compiled_object_ids':['o1']}}

    def test_inventory_queries_compiled_not_merely_planned_objects(self):
        view=self.inventory_view();facts=compiled_inventory_facts(view)
        self.assertEqual(facts['counts'],{'chair':1})
        self.assertEqual(facts['canonical_not_compiled_ids'],['o2'])
        self.assertFalse(facts['proves_visible_or_usable'])
        self.assertFalse(facts['scene_freshness_verified'])
        view['semantic_context']['compiled_object_ids'].append('o2')
        self.assertNotEqual(facts['snapshot_sha256'],compiled_inventory_facts(view)['snapshot_sha256'])

    def test_partial_unbound_duplicate_and_unknown_inventory_cannot_prove_absence(self):
        for change in ({'room_id':'another'},{'room_geometry_source':'canonical_fallback'},
                       {'actual_furniture_truncated':True},{'actual_furniture_total':3},
                       {'compiled_object_ids':['unknown']},{'compiled_object_ids':['o1','o1']},
                       {'actual_furniture':[{'object_id':'o1','category':'chair'}]*2}):
            with self.subTest(change=change):
                view=self.inventory_view();view['semantic_context'].update(change)
                facts=compiled_inventory_facts(view)
                self.assertEqual(facts['status'],'unknown');self.assertIsNone(facts['counts'])

    def test_current_contract_omits_unrotated_prose_without_mutating_scene(self):
        from copy import deepcopy
        from cityg.visual_evidence import room_visual_contract
        fixtures.FloorRepartitionTests.setUpClass()
        city,b,f=fixtures.FloorRepartitionTests().fixture();r=f.rooms[1]
        r.metadata['room_design']={'intent':'OLD north sofa','status':'accepted',
            'zones':[{'id':'north','position':'east'}], 'groups':[],
            'furnishing_brief':{'occupants':2,'capacity_reason':'OLD north sofa','items':[]}}
        old=deepcopy(r.metadata)
        result=room_visual_contract(b,f,r)
        self.assertNotIn('OLD',str(result))
        self.assertEqual(result['room_design']['zones'][0]['position'],'east')
        self.assertEqual(r.metadata,old)
        self.assertTrue(result['reference_prose_omitted'])

    def test_loaded_global_proxies_do_not_certify_detail(self):
        global_view={'view_id':'v','kind':'global','mode':'overview','target_entity_ids':['r']}
        status={'ready':True,'signal_available':True,'render_profile':'review',
                'expected':0,'loaded':0,'geometry_streaming':{'ready':True}}
        context=batch_evidence_constraints([global_view],{'v':status})
        detail=self.issue(category='road',issue_code='street_underfurnished')
        layout=self.issue(category='layout',issue_code='unspecified',asset_requests=())
        accepted,deferred,_=filter_review_issues([detail,layout],context)
        self.assertEqual(accepted,(layout,))
        self.assertEqual(deferred[0]['deferred_reason'],'proxy_overview_requires_local_detail_evidence')
        local={'view_id':'local','kind':'road','target_entity_ids':['r']}
        for local_status,expected in ((dict(status,pending=1),False),(status,True)):
            context=batch_evidence_constraints([global_view,local],{'v':status,'local':local_status})
            accepted,_,_=filter_review_issues([detail],context)
            self.assertEqual(bool(accepted),expected)

    def test_loaded_signal_required_and_cutaway_not_exterior_evidence(self):
        view={'view_id':'v','target_entity_ids':['r'],'auto_cutaway':True,'mode':'room'}
        ready={'ready':True,'signal_available':True,'geometry_streaming':{'ready':True}}
        for status in ({},dict(ready,pending=1),dict(ready,fallback=1),dict(ready,timed_out=True),
                       dict(ready,material_textures_pending=1)):
            context=batch_evidence_constraints([view],{'v':status})
            accepted,deferred,_=filter_review_issues([self.issue()],context)
            self.assertFalse(accepted);self.assertEqual(deferred[0]['deferred_reason'],'render_evidence_not_ready')
        context=batch_evidence_constraints([view],{'v':ready})
        accepted,_,_=filter_review_issues([self.issue()],context)
        self.assertTrue(accepted)
        accepted,deferred,_=filter_review_issues([self.issue(category='facade')],context)
        self.assertFalse(accepted)
        self.assertEqual(deferred[0]['deferred_reason'],'cutaway_is_not_exterior_facade_evidence')

    def issue(self, **kw):
        return replace(VisualIssue('i','error','room','r','Furniture absent','add furniture',
            issue_code='room_function_incomplete'),**kw)

    def test_duplicates_and_unsupported_binding_are_audited(self):
        a=self.issue(); foreign=self.issue(entity_id='another_floor')
        accepted,deferred,n=filter_review_issues([a,replace(a,issue_id='repeat'),foreign],{'allowed_entity_ids':['r']})
        self.assertEqual(accepted,(a,));self.assertEqual(n,1)
        self.assertEqual(deferred[0]['deferred_reason'],'entity_not_in_current_evidence')

    def test_empty_preview_is_not_an_automatic_furniture_repair(self):
        a=self.issue(); wall=self.issue(issue_code='room_access_blocked',description='door blocked')
        accepted,deferred,n=filter_review_issues([a,wall],{'furnishing_expected_by_entity':{'r':False}})
        self.assertEqual(accepted,(wall,));self.assertEqual(deferred[0]['deferred_reason'],'furnishing_not_in_scope')
        accepted,_,_=filter_review_issues([a],{'furnishing_expected_by_entity':{'r':True}})
        self.assertEqual(accepted,(a,))

    def test_floor_geometry_requires_more_than_one_view_not_silent_deletion(self):
        a=self.issue(issue_code='unspecified',description='triangular geometry')
        accepted,deferred,_=filter_review_issues([a],{'single_view_floor_ids':['r']})
        self.assertFalse(accepted);self.assertFalse(deferred[0]['automatic_repair_allowed'])

    def test_cutaway_is_not_a_missing_facade(self):
        a=self.issue(category='facade',issue_code='frontage_disconnect')
        accepted,deferred,_=filter_review_issues([a],{'cutaway_entity_ids':['r']})
        self.assertFalse(accepted)
        self.assertEqual(deferred[0]['deferred_reason'],'cutaway_is_not_exterior_facade_evidence')

    def test_context_contains_current_targets_not_global_failure_logs(self):
        fixtures.FloorRepartitionTests.setUpClass()
        city,b,f=fixtures.FloorRepartitionTests().fixture()
        views=[{'view_id':'floor','kind':'floor_plan','target_entity_ids':[b.id,f.id]}]
        context=prototype_review_context(city,{'primitives':[]},views)
        self.assertNotIn('prototype_summary',context)
        self.assertNotIn(b.floors[1].id,context['allowed_entity_ids'])
        self.assertFalse(context['furnishing_expected_by_entity'][f.id])
        self.assertIn(f.id,context['single_view_floor_ids'])
        duplicate=prototype_review_context(city,{'primitives':[]},views*2)
        self.assertIn(f.id,duplicate['single_view_floor_ids'])
        self.assertTrue(all(r['function']!='library' for r in context['image_evidence'][0]['entities']))


if __name__=='__main__':unittest.main()
