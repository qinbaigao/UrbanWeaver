import unittest
from cityg.evidence_acquisition import EvidenceAction, EvidenceSession


class EvidenceAcquisitionTests(unittest.TestCase):
    def action(self,key,kind='query',supports=('inventory',),cost=1,version='v1'):
        return EvidenceAction(key,kind,'room',version,supports,cost)

    def evidence(self,action,**kw):
        return dict(target_id='room',version='v1',supports=action.supports,ready=True,**kw)

    def test_one_shared_budget_for_query_and_view(self):
        s=EvidenceSession('room','v1',['inventory','appearance'],budget=5)
        actions=[self.action('view','view',('appearance',),4),self.action('query')]
        self.assertEqual(s.choose(actions).id,'query')
        s.acquire(s.choose(actions),self.evidence)
        self.assertEqual(s.choose(actions).id,'view')
        s.acquire(s.choose(actions),self.evidence)
        self.assertTrue(s.report()['complete']);self.assertEqual(s.spent,5)
        self.assertIsNone(s.choose(actions))

    def test_stale_provider_cannot_satisfy_need(self):
        s=EvidenceSession('room','v1',['inventory'],budget=2)
        s.acquire(self.action('a'),lambda _:dict(target_id='room',version='old',ready=True,supports=['inventory']))
        self.assertFalse(s.report()['complete']);self.assertEqual(s.spent,1)

    def test_provider_failure_and_unready_view_still_cost_budget(self):
        s=EvidenceSession('room','v1',['appearance'],budget=5,max_views=1)
        view=self.action('view','view',('appearance',),4)
        s.acquire(view,lambda _:dict(target_id='room',version='v1',ready=False,supports=['appearance']))
        self.assertFalse(s.report()['complete'])
        self.assertIsNone(s.choose([self.action('second','view',('appearance',),1)]))

    def test_dependency_coverage_adapts_to_actual_partial_evidence(self):
        s=EvidenceSession('room','v1',['inventory','appearance'],budget=6)
        a=self.action('combined',supports=('inventory','appearance'))
        s.acquire(a,lambda _:dict(target_id='room',version='v1',ready=True,supports=['inventory']))
        self.assertEqual(s.pending,{'appearance'})
        self.assertEqual(s.choose([self.action('repeat'),self.action('view','view',('appearance',),4)]).id,'view')

    def test_cannot_claim_more_than_action_supports(self):
        s=EvidenceSession('room','v1',['inventory','appearance'],budget=2)
        s.acquire(self.action('a'),lambda _:dict(target_id='room',version='v1',ready=True,supports=['inventory','appearance']))
        self.assertEqual(len(s.pending),2)

    def test_invalid_cost_duplicates_and_unknown_versions(self):
        s=EvidenceSession('room','v1',['inventory'],budget=1)
        with self.assertRaises(ValueError):s.choose([self.action('a',cost=float('nan'))])
        with self.assertRaises(ValueError):s.choose([self.action('a'),self.action('a')])
        self.assertIsNone(s.choose([self.action('a',version='old')]))
        with self.assertRaises(ValueError):s.acquire(self.action('a',cost=2),self.evidence)

