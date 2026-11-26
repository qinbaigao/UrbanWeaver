from copy import deepcopy
import unittest

from cityg.ccwp import entity_index
from cityg.geometry import GeometryCompiler
from cityg.geometry.validation import GeometryValidator
from cityg.planning.baseline import BaselineCityPlanner
from cityg.planning.generation_prototypes import DeferredFurniture
from cityg.planning.negotiation import negotiate
from cityg.planning.scope_requirements import ScopeRequirements
from cityg.repair import PatchRejected
from cityg.schemas import CitySpec
from cityg.subtree_transactions import FloorSubtreePlanner
from cityg.transactions import MutationProposal, accept_candidate, fingerprint


class NegotiationTests(unittest.TestCase):
    def setUp(self):
        self.city=BaselineCityPlanner(floor_detail_agent=DeferredFurniture()).plan(
            CitySpec(building_count=2,min_floors=2,max_floors=2,width_m=180,depth_m=140))
        self.building=next(self.city.iter_buildings());self.floor=self.building.floors[0]
        self.room=next(r for r in self.floor.rooms if r.function!='corridor')
        self.conflict={'conflict_id':'test_room_capacity','entity_id':self.room.id,
                       'base_fingerprint':fingerprint(self.city),'requested_floor_room_count':6}
        self.calls=[]

    def compiler(self,city):
        scene=GeometryCompiler().compile(city)
        report=GeometryValidator().validate(city,scene)
        return {'ok':report.ok,'errors':[i.message for i in report.errors]}

    def resolution(self,city,conflict):
        floor=entity_index(city)[self.floor.id]
        return sum(r.function!='corridor' for r in floor.rooms)==conflict['requested_floor_room_count']

    def room_strategy(self,city,scope,conflict):
        self.calls.append('room')
        raise ValueError('Room-local furniture edits cannot change floor capacity')

    def floor_strategy(self,city,scope,conflict):
        self.calls.append('floor')
        return FloorSubtreePlanner().replace(city,scope,{'room_count':conflict['requested_floor_room_count']}).city

    def run_case(self,authority,**kw):
        return negotiate(self.city,self.conflict,authorized_roots=authority,
            strategies={'room':self.room_strategy,'floor':self.floor_strategy},
            compiled_gate=self.compiler,resolution_gate=self.resolution,source='user_edit',**kw)

    def test_authorized_floor_upgrade_compiles_and_invalidates_old_child_proposal(self):
        before=deepcopy(self.city)
        old=MutationProposal.bind(self.city,[self.room.id],source='user_edit',kind='test',proposal_id='old')
        result,report=self.run_case([self.floor.id])
        self.assertEqual(report['status'],'resolved',report)
        self.assertTrue(report['child_proposals_require_rebinding'])
        self.assertEqual(self.calls,['room','floor'])
        self.assertEqual(before,self.city)
        self.assertEqual(list(result.iter_buildings())[1],list(before.iter_buildings())[1])
        self.assertEqual(next(result.iter_buildings()).vertical_connectors,self.building.vertical_connectors)
        receipt=report['attempts'][-1]['implementation_receipt']
        self.assertEqual(set(receipt['obligations'].values()),{'passed'})
        self.assertEqual(report['attempts'][0]['implementation_receipt']['obligations']['compiled_feasibility'],'not_run')
        with self.assertRaises(PatchRejected): accept_candidate(result,old,lambda c:c)

    def test_parent_scope_requires_permission_and_no_partial_changes(self):
        result,report=self.run_case([self.room.id])
        self.assertEqual(report['status'],'needs_authorization')
        self.assertEqual(report['requested_scope'],self.floor.id)
        self.assertEqual(self.calls,['room'])
        self.assertEqual(result,self.city)

    def test_capability_preflight_skips_room_without_spending_attempt(self):
        result,report=self.run_case([self.floor.id],max_attempts=1,
            scope_requirements=ScopeRequirements((self.floor.id,),('floor','building')))
        self.assertEqual(report['status'],'resolved',report)
        self.assertEqual(self.calls,['floor'])
        self.assertEqual(len(report['attempts']),1)
        self.assertEqual(report['scope_preflight'][0]['status'],'skipped')
        self.assertTrue(self.resolution(result,self.conflict))

    def test_capability_preflight_does_not_grant_parent_authority(self):
        result,report=self.run_case([self.room.id],
            scope_requirements=ScopeRequirements((self.floor.id,),('floor',)))
        self.assertEqual(report['status'],'needs_authorization')
        self.assertFalse(self.calls)
        self.assertEqual(result,self.city)

    def test_unsupported_capability_is_not_a_permission_request(self):
        result,report=self.run_case([self.room.id],
            scope_requirements=ScopeRequirements((self.floor.id,),('floor',),'room_count outside supported range'))
        self.assertEqual(report['status'],'unsupported_capability')
        self.assertFalse(report['requires_user_approval'])
        self.assertFalse(self.calls)
        self.assertEqual(result,self.city)

    def test_unknown_dependency_cannot_silently_shrink_scope(self):
        with self.assertRaisesRegex(ValueError,'existing entities'):
            self.run_case([self.floor.id],scope_requirements=ScopeRequirements(('missing',)))
        self.assertFalse(self.calls)

    def test_budget_and_stale_requests_never_expand_scope(self):
        result,report=self.run_case([self.floor.id],max_attempts=1)
        self.assertEqual(report['status'],'budget_exhausted');self.assertEqual(result,self.city)
        self.conflict['base_fingerprint']='old'
        self.calls.clear(); result,report=self.run_case([self.floor.id])
        self.assertEqual(report['status'],'stale_conflict');self.assertFalse(self.calls)

    def test_service_outage_does_not_trigger_larger_edit(self):
        def unavailable(*args): raise RuntimeError('offline')
        self.room_strategy=unavailable
        result,report=self.run_case([self.floor.id])
        self.assertEqual(report['status'],'service_unavailable')
        self.assertFalse(self.calls);self.assertEqual(result,self.city)

    def test_compiler_private_mutation_cannot_fake_resolution(self):
        def mutating_compiler(candidate):
            entity_index(candidate)[self.floor.id].metadata['fake_resolution']=True
            return {'ok':True}
        def independent(candidate,conflict):
            return entity_index(candidate)[self.floor.id].metadata.get('fake_resolution') is True
        result,report=negotiate(self.city,self.conflict,authorized_roots=[self.floor.id],
            strategies={'floor':self.floor_strategy},compiled_gate=mutating_compiler,
            resolution_gate=independent,source='user_edit')
        self.assertEqual(report['status'],'unresolved')
        self.assertEqual(result,self.city)
        self.assertEqual(report['attempts'][0]['implementation_receipt']['obligations'],
            {'protected_geometry':'passed','compiled_feasibility':'passed','specific_conflict_resolution':'failed'})

    def test_failed_compile_does_not_invoke_resolution(self):
        called=[]
        result,report=negotiate(self.city,self.conflict,authorized_roots=[self.floor.id],
            strategies={'floor':self.floor_strategy},compiled_gate=lambda _: {'ok':False},
            resolution_gate=lambda *_:called.append(True),source='user_edit')
        self.assertFalse(called)
        self.assertEqual(result,self.city)
        self.assertEqual(report['attempts'][0]['implementation_receipt']['obligations']['specific_conflict_resolution'],'not_run')

    def test_explicit_building_authority_can_coordinate_two_floors(self):
        def floor_cannot_resolve(*args): raise ValueError('Two floors require coordinated capacity')
        def building_strategy(city,scope,conflict):
            self.assertEqual(scope,self.building.id)
            for floor in entity_index(city)[scope].floors:
                city=FloorSubtreePlanner().replace(city,floor.id,{'room_count':6}).city
            return city
        def resolved(city,conflict):
            return all(sum(r.function!='corridor' for r in f.rooms)==6
                       for f in entity_index(city)[self.building.id].floors)
        result,report=negotiate(self.city,self.conflict,authorized_roots=[self.building.id],
            strategies={'room':self.room_strategy,'floor':floor_cannot_resolve,'building':building_strategy},
            compiled_gate=self.compiler,resolution_gate=resolved,source='user_edit',max_attempts=3)
        self.assertEqual(report['status'],'resolved',report)
        self.assertEqual([r['scope_type'] for r in report['attempts']],['room','floor','building'])
        self.assertTrue(report['child_proposals_require_rebinding'])
        self.assertEqual(list(result.iter_buildings())[1],list(self.city.iter_buildings())[1])
        self.assertEqual(next(result.iter_buildings()).entrance,self.building.entrance)

