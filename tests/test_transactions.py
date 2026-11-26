from copy import deepcopy
import tempfile
import unittest
from pathlib import Path

from cityg.ccwp import entity_index
from cityg.planning.baseline import BaselineCityPlanner
from cityg.schemas import CitySpec
from cityg.repair import PatchEngine, PatchOperation, PatchRejected, WorldPatch
from cityg.transactions import MutationProposal, accept_candidate, fingerprint
from cityg.memory import MemoryRecord, MemoryStore


class TransactionTests(unittest.TestCase):
    def test_first_furniture_can_create_derived_parent_contract(self):
        from cityg.ccwp import build_world_program
        from cityg.transactions import refresh_local_overlay
        floor = next(f for f in self.city.iter_floors() if any(r.id == self.room.id for r in f.rooms))
        obj = deepcopy(next(o for o in floor.objects if o.room_id == self.room.id))
        floor.objects = []
        for room in floor.rooms: room.object_ids = []
        self.city.world_program = build_world_program(self.city, producer='test', seed=None)
        def add(candidate):
            cf = next(f for f in candidate.iter_floors() if f.id == floor.id)
            cf.objects.append(obj)
            next(r for r in cf.rooms if r.id == self.room.id).object_ids.append(obj.id)
            return refresh_local_overlay(self.city, candidate, [self.room.id])
        result = accept_candidate(self.city, self.proposal(), add)
        self.assertIn('contracts:contract_furnishing_clearance__'+floor.id,
                      result.report['derived_dependency_changes'])

    def test_streetscape_exact_scope_lock_and_versioned_evidence(self):
        from cityg.refinement.streetscape import apply_streetscape_visual_refinement
        road = self.city.road_network.segments[0]
        self.city.metadata['street_network_program'] = {'version':'street_network_program.v1',
            'producer':'Streetscape Agent', 'review_note':'keep global intent', 'segments':[]}
        issue = {'entity_id':road.id, 'issue_code':'street_underfurnished', 'binding_confidence':.95}
        with tempfile.TemporaryDirectory() as tmp, MemoryStore(Path(tmp)/'memory.sqlite') as memory:
            memory.put(MemoryRecord('street_evidence', 'visual_evidence', 'entity', road.id,
                {}, validation_status='accepted'))
            result = apply_streetscape_visual_refinement(self.city, [issue], memory_store=memory)
            self.assertEqual(result.transaction_report['changed_entity_ids'], [road.id])
            self.assertEqual(result.city.metadata['street_network_program']['review_note'], 'keep global intent')
            self.assertEqual(memory.get('street_evidence').validation_status, 'stale')
        next(n for n in self.city.world_program.nodes if n.entity_id == road.id).locked = True
        with self.assertRaises(PatchRejected):
            apply_streetscape_visual_refinement(self.city, [issue])

    def setUp(self):
        self.city = BaselineCityPlanner().plan(CitySpec(building_count=2, min_floors=2, max_floors=2))
        self.room = next(r for r in self.city.iter_rooms() if r.function != 'corridor')

    def proposal(self, **kw):
        return MutationProposal.bind(self.city, [self.room.id], source='user_edit',
            kind='rename', proposal_id='unit_mutation', **kw)

    def rename(self, c):
        entity_index(c)[self.room.id].name = 'renamed'
        return c

    def test_local_commit_source_unchanged_and_noop_exact(self):
        before = deepcopy(self.city)
        result = accept_candidate(self.city, self.proposal(), self.rename)
        self.assertEqual(self.city, before)
        self.assertEqual(result.report['changed_entity_ids'], [self.room.id])
        noop = accept_candidate(self.city, self.proposal(), lambda c: c)
        self.assertEqual(noop.city, self.city)
        self.assertEqual(noop.report['status'], 'no_change')

    def test_stale_out_of_scope_and_parent_lock_rejected(self):
        p = self.proposal(); other = deepcopy(self.city); other.name = 'concurrent edit'
        with self.assertRaises(PatchRejected): accept_candidate(other, p, self.rename)
        def wrong(c): c.name = 'wrong'; return c
        with self.assertRaises(PatchRejected): accept_candidate(self.city, p, wrong)
        parent = next(b for b in self.city.iter_buildings() if any(r.id == self.room.id for f in b.floors for r in f.rooms))
        next(n for n in self.city.world_program.nodes if n.entity_id == parent.id).locked = True
        with self.assertRaises(PatchRejected): accept_candidate(self.city, self.proposal(), self.rename)

    def test_overlay_edits_preserved_and_out_of_scope_overlay_detected(self):
        node = next(n for n in self.city.world_program.nodes if n.entity_id == self.room.id)
        patch = WorldPatch('overlay_edit', self.room.id,
            (PatchOperation('replace_node', self.room.id, 'intent.description', 'custom intent'),),
            {self.room.id: node.version})
        result = accept_candidate(self.city, self.proposal(), lambda c: PatchEngine().apply(c, patch).city)
        self.assertEqual(next(n for n in result.city.world_program.nodes if n.entity_id == self.room.id).intent.description, 'custom intent')
        def wrong(c): c.world_program.nodes[0].intent.description = 'wrong scope'; return c
        with self.assertRaises(PatchRejected): accept_candidate(self.city, self.proposal(), wrong)

    def test_inventory_and_failed_compilation_rollback(self):
        before = fingerprint(self.city)
        def clear(c):
            for f in c.iter_floors(): f.objects[:] = [o for o in f.objects if o.room_id != self.room.id]
            entity_index(c)[self.room.id].object_ids.clear()
            return c
        with self.assertRaises(PatchRejected): accept_candidate(self.city, self.proposal(), clear)
        with self.assertRaises(PatchRejected):
            accept_candidate(self.city, self.proposal(), self.rename, compiled_gate=lambda c: {'ok': False})
        with self.assertRaises(PatchRejected):
            accept_candidate(self.city, self.proposal(), self.rename, compiled_gate=lambda c: None)
        self.assertEqual(fingerprint(self.city), before)
        with self.assertRaises(ValueError):
            MutationProposal.bind(self.city, [self.room.id], source='visual_repair', kind='furniture',
                                  proposal_id='unsafe', preserve_inventory=False)

    def test_dependency_evidence_invalidated_not_unrelated(self):
        other = list(self.city.iter_buildings())[-1].id
        with tempfile.TemporaryDirectory() as folder, MemoryStore(Path(folder)/'memory.sqlite') as memory:
            for key, scope, content in [('room', self.room.id, {}), ('remote', other, {}),
                    ('dependent', other, {'dependency_entity_ids': [self.room.id]})]:
                memory.put(MemoryRecord(key, 'visual_evidence', 'entity', scope, content, validation_status='accepted'))
            accept_candidate(self.city, self.proposal(), self.rename, memory_store=memory)
            self.assertEqual(memory.get('room').validation_status, 'stale')
            self.assertEqual(memory.get('dependent').validation_status, 'stale')
            self.assertEqual(memory.get('remote').validation_status, 'accepted')

    def test_memory_write_failure_rolls_back_invalidation(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as folder, MemoryStore(Path(folder)/'memory.sqlite') as memory:
            memory.put(MemoryRecord('evidence', 'visual_evidence', 'entity', self.room.id,
                                    {}, validation_status='accepted'))
            with patch.object(memory, '_put', side_effect=RuntimeError('injected write failure')):
                with self.assertRaises(RuntimeError):
                    accept_candidate(self.city, self.proposal(), self.rename, memory_store=memory)
            self.assertEqual(memory.get('evidence').validation_status, 'accepted')
            self.assertIsNone(memory.get('unit_mutation'))

    def test_direct_proposal_cannot_bypass_policy(self):
        from dataclasses import replace
        unsafe = replace(self.proposal(), source='visual_repair', preserve_inventory=False)
        with self.assertRaises(ValueError): accept_candidate(self.city, unsafe, self.rename)

    def test_floor_subtree_uses_shared_gate_and_preserves_remote_overlay(self):
        from cityg.editing import _apply_replans
        from test_subtree_transactions import make_city
        city = make_city(); buildings = list(city.iter_buildings())
        remote = next(n for n in city.world_program.nodes if n.entity_id == buildings[-1].id)
        remote.intent.description = 'user-authored remote intent'; remote.locked = True
        before = fingerprint(city)
        result, changed, traces = _apply_replans(city, [{'kind':'floor_layout',
            'target_id': buildings[0].floors[0].id, 'details': {'room_count': 10}}],
            None, model_id='offline', asset_resolver=None)
        self.assertEqual(fingerprint(city), before)
        self.assertEqual(next(n for n in result.world_program.nodes if n.entity_id == remote.entity_id), remote)
        self.assertEqual(traces[0]['transaction']['status'], 'accepted')
        self.assertTrue(traces[0]['transaction']['derived_dependency_changes'])

    def test_local_overlay_keeps_custom_room_intent_and_state(self):
        from cityg.transactions import refresh_local_overlay
        city = self.city
        node = next(n for n in city.world_program.nodes if n.entity_id == self.room.id)
        node.intent.description = 'keep the family photos'
        node.state.properties['custom'] = 'preserve'
        candidate = deepcopy(city); entity_index(candidate)[self.room.id].name = 'local rename'
        refresh_local_overlay(city, candidate, [self.room.id])
        result = accept_candidate(city, self.proposal(), lambda _: candidate)
        updated = next(n for n in result.city.world_program.nodes if n.entity_id == self.room.id)
        self.assertEqual(updated.intent.description, node.intent.description)
        self.assertEqual(updated.state, node.state)


if __name__ == '__main__': unittest.main()
