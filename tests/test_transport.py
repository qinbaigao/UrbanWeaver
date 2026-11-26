from copy import deepcopy
from dataclasses import asdict, replace
import json
import unittest

from cityg.geometry.model import InteractionStateMachine, StateTransition
from cityg.runtime.transport import (AttachmentRuntime, Box, Surface,
    TransportTask, execute_script, task_from_dict)
from cityg.runtime.transport_validation import sweep_hit, supported, validate_trace
from cityg.runtime.transport_planning import plan_relocation
from cityg.runtime.lift_transport import LiftTransport, validate_lift_ride


def task_fixture():
    support = Surface('table:top','table',(0,0,.8),(1.2,1.6),0)
    return TransportTask('frozen','room:1','cup',('cup_mesh',),
        Box('cup',(0,0,.85),(.08,.08,.1)), support,support,(0,.3,.85),
        (Box('table',(0,0,.4),(1.2,1.6,.8)),),
        Box('base',(1,0,.7),(.6,.7,1.4)),(1,0,1.15))


def lift_fixture():
    return InteractionStateMachine('lift','core','elevator_controller','level_0',
        {'level_0':{'cabin_z_m':0.,'current_level':0},
         'level_1':{'cabin_z_m':3.2,'current_level':1}},
        [StateTransition('go_to_level_1','level_0','level_1',4.),
         StateTransition('go_to_level_0','level_1','level_0',4.)])


class TransportTests(unittest.TestCase):
    def test_real_state_sequence_and_serialization(self):
        task=task_fixture(); trace=execute_script(task)
        self.assertTrue(validate_trace(task,trace)['ok'])
        restored=task_from_dict(json.loads(json.dumps(asdict(task))))
        self.assertEqual(task.fingerprint,restored.fingerprint)
        runtime=AttachmentRuntime(task); runtime.restore(trace['frames'][10])
        self.assertEqual(runtime.snapshot('move'),trace['frames'][10])

    def test_wrong_identity_stale_missing_release_and_time_rejected(self):
        task=task_fixture(); trace=execute_script(task)
        for mutation in ('identity','stale','release','time','nan','support','holder','effector','base'):
            bad=deepcopy(trace)
            f=bad['frames'][2]
            if mutation=='identity': f['objects']['copy']=deepcopy(f['objects']['cup'])
            elif mutation=='stale': f['contract_sha256']='old'
            elif mutation=='release': bad['frames'].pop()
            elif mutation=='time': f['time_s']=0
            elif mutation=='nan': f['objects']['cup']['position'][0]=float('nan')
            elif mutation=='support': f['objects']['cup']['support']='table:top'
            elif mutation=='holder': f['objects']['cup']['holder']=None
            elif mutation=='effector': f['effector'][0]+=1
            elif mutation=='base': f['robot_base'][0]+=1
            self.assertFalse(validate_trace(task,bad)['ok'],mutation)

    def test_thin_wall_continuous_sweep_and_rotated_boxes(self):
        box=Box('cup',(-1,0,1),(.1,.1,.1),35)
        wall=Box('wall',(0,0,1),(.001,2,2),20)
        self.assertTrue(sweep_hit(box,(1,0,1),wall))
        self.assertFalse(sweep_hit(box,(-.8,0,1),wall))

    def test_actual_obstruction_and_bad_support_fail(self):
        task=task_fixture()
        task=replace(task,obstacles=task.obstacles+(Box('block',(0,.15,1.05),(.3,.04,.5)),))
        self.assertFalse(validate_trace(task,execute_script(task))['ok'])
        outside=replace(task_fixture(),destination=(0,2,.85))
        self.assertIn('invalid_target_support',validate_trace(outside,execute_script(outside))['errors'])

    def test_top_rounding_does_not_exempt_mesh_cavity(self):
        task=task_fixture()
        for depth,passed in ((.0004,True),(.04,False)):
            table=replace(task.obstacles[0],size=(1.2,1.6,.8+depth*2))
            changed=replace(task,obstacles=(table,))
            self.assertEqual(validate_trace(changed,execute_script(changed))['ok'],passed)

    def test_contract_rejects_duplicates_and_nonfinite(self):
        task=task_fixture()
        for changes in ({'obstacles':task.obstacles*2},{'reach_m':float('nan')},
                        {'source_primitive_ids':('table',)}, {'destination':(0,0,float('inf'))}):
            with self.assertRaises(ValueError): replace(task,**changes)

    def test_restore_rejects_wrong_scene(self):
        task=task_fixture();runtime=AttachmentRuntime(task)
        frame=runtime.snapshot('start');frame['contract_sha256']='wrong'
        with self.assertRaises(ValueError):runtime.restore(frame)

    def test_requires_attachment_and_exact_destination(self):
        task=task_fixture();runtime=AttachmentRuntime(task)
        with self.assertRaises(ValueError):runtime.move_to(task.destination)
        runtime.attach()
        with self.assertRaises(ValueError):runtime.release()

    def test_budget_and_permissions_preserve_task(self):
        task=task_fixture();before=asdict(task)
        blocked=replace(task,destination=task.object_box.center)
        self.assertEqual(plan_relocation(blocked,max_candidates=1)[2]['status'],'unresolved_within_budget')
        self.assertEqual(plan_relocation(task,authorized=False)[2]['status'],'needs_authorization')
        selected,trace,report=plan_relocation(task,max_candidates=8)
        self.assertTrue(report['verified_resolved'])
        self.assertTrue(validate_trace(selected,trace)['ok'])
        self.assertEqual(before,asdict(task))

    def test_rotated_surface_edge_test(self):
        surface=Surface('s','p',(0,0,0),(2,.2),90)
        self.assertTrue(supported(Box('b',(0,.6,.05),(.08,.08,.1)),surface))
        self.assertFalse(supported(Box('b',(.6,0,.05),(.08,.08,.1)),surface))


class LiftTransportTests(unittest.TestCase):
    def test_continuous_payload_ride_and_negative_control(self):
        lift=LiftTransport(lift_fixture());lift.open_door()
        lift.board(object_id='cup',robot_local=(0,0,.75),object_local=(.1,0,1.2),robot_size=(.65,.8,1.5))
        with self.assertRaises(ValueError):lift.travel('go_to_level_1')
        lift.close_door();frames=[lift.snapshot()];lift.travel('go_to_level_1')
        with self.assertRaises(ValueError):lift.open_door()
        for _ in range(80):frames.append(lift.step(.05))
        report=validate_lift_ride(frames,object_id='cup',start_z=0,end_z=3.2,max_step_m=.04)
        self.assertTrue(report['ok'],report)
        broken=deepcopy(frames);broken[30]['object_world'][2]-=1
        self.assertFalse(validate_lift_ride(broken,object_id='cup',start_z=0,end_z=3.2,max_step_m=.04)['ok'])

    def test_board_closed_and_oversized_rejected(self):
        lift=LiftTransport(lift_fixture())
        with self.assertRaises(ValueError):lift.board(object_id='cup',robot_local=(0,0,.7),object_local=(0,0,1),robot_size=(.65,.8,1.4))
        lift.open_door()
        with self.assertRaises(ValueError):lift.board(object_id='cup',robot_local=(0,0,.7),object_local=(0,0,1),robot_size=(4,4,1.4))


if __name__=='__main__':
    unittest.main()
