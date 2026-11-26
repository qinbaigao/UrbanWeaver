import unittest
from types import SimpleNamespace

from cityg.planning.prototype_inventory import prioritize_inventory
from cityg.planning.prototype_inventory import rooms_by_unmet_inventory


class PrototypeInventoryTests(unittest.TestCase):
    def setUp(self):
        def materialize(key):
            seats = {'four': 4, 'six': 6, 'six_other': 6}[key]
            return SimpleNamespace(design=SimpleNamespace(groups=[{
                'anchor': {'category': 'meeting_table'},
                'members': [{'category': 'meeting_chair'} for _ in range(seats)]}]))
        self.library = SimpleNamespace(materialize=materialize)
        self.candidates = [{'prototype_id': key} for key in ('four', 'six_other', 'six')]

    def test_explicit_capacity_precedes_incomplete_agent_choice(self):
        ranked = prioritize_inventory(self.candidates, self.library,
                                      [{'category': 'meeting_chair', 'min_count': 6}])
        self.assertEqual([c['prototype_id'] for c in ranked], ['six_other', 'six', 'four'])
        self.assertEqual(self.candidates[0]['prototype_id'], 'four')

    def test_no_allocated_need_keeps_agent_order(self):
        self.assertEqual(prioritize_inventory(self.candidates, None, []), self.candidates)
        self.assertEqual(prioritize_inventory(self.candidates, self.library,
                          [{'category': 'meeting_chair', 'min_count': 4}]), self.candidates)

    def test_room_budget_recounts_after_commit_and_keeps_agent_ties(self):
        req = {'levels':[0], 'inventory':[{'room_function':'meeting_room', 'category':'meeting_chair', 'min_count':6}]}
        b = SimpleNamespace(id='A',metadata={'interior_layout_contract':{'requirements':[req]}})
        rooms = [SimpleNamespace(id=str(i),function=f) for i,f in enumerate(('storage','meeting_room','meeting_room'))]
        f = SimpleNamespace(id='floor',level=0,rooms=rooms,objects=[])
        candidates = [(b,f,r,self.candidates) for r in rooms]
        ordered = rooms_by_unmet_inventory(candidates,self.library,2)
        self.assertEqual(next(ordered)[2].id, '1')
        f.objects.extend(SimpleNamespace(room_id='1',category='meeting_chair') for _ in range(6))
        self.assertEqual(next(ordered)[2].id, '0')

    def test_unsatisfied_candidates_are_not_dropped_or_marked_satisfied(self):
        ranked = prioritize_inventory(self.candidates, self.library,
                                      [{'category': 'meeting_chair', 'min_count': 8}])
        self.assertEqual(len(ranked), 3)
        self.assertEqual(ranked[-1]['prototype_id'], 'four')
