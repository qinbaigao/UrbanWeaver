from copy import deepcopy
from dataclasses import asdict,replace
import json
import unittest

from cityg.runtime.transport import Box,Surface,TransportTask
from cityg.runtime.transport_validation import sweep_hit
from cityg.runtime.mobile_geometry import (door_pose,door_sweep_hit,supported_sweep,
    plan_fixed_yaw_route,audit_door_static_clearance)
from cityg.runtime.mobile_transport import MobileTask,execute_mobile_roundtrip,mobile_task_from_dict,plan_mobile_route
from cityg.runtime.mobile_validation import validate_mobile_trace


def fixture():
    surface=Surface('table:top','table',(3,0,.8),(1.2,1.6),0)
    table=Box('table',(3,0,.4),(1.2,1.6,.8))
    walls=(Box('south_jamb',(0,-1.8,1.6),(.18,2.4,3.2)),
           Box('north_jamb',(0,1.8,1.6),(.18,2.4,3.2)))
    ref=TransportTask('scene','room','cup',('original_cup',),
        Box('cup',(3,0,.85),(.08,.08,.1)),surface,surface,(3,0,.85),
        (table,*walls),Box('robot',(4,0,.75),(.65,.8,1.5)),(4,0,1.15))
    task=MobileTask(ref,'prior_trace',Box('door',(0,0,1.075),(.08,1.2,2.15)),
        'door_controller',.8,.8,(table,*walls),
        (Box('slab',(1,0,-.1),(8,8,.2)),),(-3,-3,5,3),
        (1,0,.75),(-1.4,0,.75),(0,0,.82))
    route=[(4,0,.75),(4,2,.75),(1,2,.75),(1,0,.75)]
    return task,route


class MobileGeometryTests(unittest.TestCase):
    def test_door_matches_usd_hinge(self):
        task,_=fixture();opened=door_pose(task.door,90)
        self.assertAlmostEqual(opened.center[0],-.6)
        self.assertAlmostEqual(opened.center[1],-.6)
        self.assertEqual(opened.yaw,90)
        rotated=replace(task.door,yaw=90)
        pose=door_pose(rotated,90)
        self.assertAlmostEqual(pose.center[0],.6)
        self.assertAlmostEqual(pose.center[1],-.6)

    def test_rotating_door_catches_mid_arc_collision(self):
        task,_=fixture();person=Box('person',(-.42,-.18,1.1),(.1,.1,.2))
        self.assertFalse(sweep_hit(task.door,task.door.center,person))
        opened=door_pose(task.door,90)
        self.assertFalse(sweep_hit(opened,opened.center,person))
        self.assertTrue(door_sweep_hit(task.door,0,90,person))

    def test_static_jamb_overlap_cannot_be_reported_as_operable(self):
        task,_=fixture()
        audit=audit_door_static_clearance(task.door,task.obstacles)
        self.assertFalse(audit['ok'])
        self.assertTrue(audit['confirmed_endpoint_overlap'])
        self.assertFalse(audit['jambs_exempted'])
        self.assertTrue(audit_door_static_clearance(task.door,[])['ok'])

    def test_support_union_does_not_bridge_hole(self):
        base=Box('base',(2.5,0,.75),(.65,.8,1.5))
        continuous=(Box('left',(-1,0,-.1),(4,8,.2)),Box('right',(3,0,-.1),(4,8,.2)))
        gap=(continuous[0],Box('right',(3.5,0,-.1),(3,8,.2)))
        self.assertTrue(supported_sweep(base,(0,0,.75),continuous))
        self.assertFalse(supported_sweep(base,(0,0,.75),gap))
        with self.assertRaises(ValueError):supported_sweep(base,(0,0,.75),(replace(gap[0],yaw=20),))

    def test_route_avoids_table_and_respects_budget(self):
        task,_=fixture()
        candidate,route,report=plan_mobile_route(task)
        self.assertEqual(report['status'],'planned')
        self.assertGreater(len(route),2)
        checked=validate_mobile_trace(candidate,execute_mobile_roundtrip(candidate,route))
        self.assertTrue(checked['ok'],checked)
        path,result=plan_fixed_yaw_route(task.reference.robot_base,task.approach,
            (*task.obstacles,task.door),task.floor_slabs,task.workspace,max_expansions=1)
        self.assertIsNone(path);self.assertEqual(result['status'],'budget_exhausted')


class MobileTraceTests(unittest.TestCase):
    def setUp(self):
        self.task,self.route=fixture();self.trace=execute_mobile_roundtrip(self.task,self.route)

    def test_complete_roundtrip_and_serialization(self):
        report=validate_mobile_trace(self.task,self.trace)
        self.assertTrue(report['ok'],report)
        self.assertEqual(report['portal_crossings'],2)
        restored=mobile_task_from_dict(json.loads(json.dumps(asdict(self.task))))
        self.assertEqual(restored.fingerprint,self.task.fingerprint)
        self.assertTrue(validate_mobile_trace(restored,json.loads(json.dumps(self.trace)))['ok'])

    def test_closed_door_and_instant_open_rejected(self):
        closed=deepcopy(self.trace)
        for f in closed['frames']:f['door_angle_deg']=0;f['door_state']='closed';f['door_moving']=False
        errors=validate_mobile_trace(self.task,closed)['errors']
        self.assertIn('closed_door_crossing',errors)
        self.assertIn('base_door_collision',errors)
        instant=deepcopy(self.trace);f=next(f for f in instant['frames'] if f['action']=='door_open')
        f['door_angle_deg']=90;f['door_state']='open';f['door_moving']=False
        self.assertIn('door_state_or_speed_mismatch',validate_mobile_trace(self.task,instant)['errors'])

    def test_teleport_duplicate_lost_attachment_and_turn_rejected(self):
        for name in ('teleport','duplicate','detach','turn','nan','stale'):
            bad=deepcopy(self.trace);frame=next(f for f in bad['frames'] if f['action']=='walk')
            if name=='teleport':frame['robot_base'][0]+=1
            elif name=='duplicate':frame['objects']['copy']=deepcopy(frame['objects']['cup'])
            elif name=='detach':frame['objects']['cup']['holder']=None
            elif name=='turn':frame['robot_yaw_deg']=90
            elif name=='nan':frame['robot_base'][0]=float('nan')
            elif name=='stale':frame['contract_sha256']='old'
            self.assertFalse(validate_mobile_trace(self.task,bad)['ok'],name)

    def test_missing_checkpoint_and_release_rejected(self):
        for action in ('checkpoint','release'):
            bad={**self.trace,'frames':[f for f in self.trace['frames'] if f['action']!=action]}
            self.assertIn('incomplete_roundtrip',validate_mobile_trace(self.task,bad)['errors'])

    def test_hole_in_real_support_is_not_ignored(self):
        task=replace(self.task,floor_slabs=(Box('left',(-1,0,-.1),(4,8,.2)),Box('right',(3.5,0,-.1),(3,8,.2))))
        report=validate_mobile_trace(task,execute_mobile_roundtrip(task,self.route))
        self.assertIn('unsupported_base_sweep',report['errors'])

    def test_payload_above_door_header_fails(self):
        header=Box('header',(0,0,2.55),(.18,1.2,.8))
        task=replace(self.task,obstacles=(*self.task.obstacles,header),carry_offset=(0,0,1.5))
        report=validate_mobile_trace(task,execute_mobile_roundtrip(task,self.route))
        self.assertIn('carried_collision:header',report['errors'])

    def test_narrow_aperture_and_no_stale_rebinding(self):
        task=replace(self.task,door=replace(self.task.door,size=(.08,.7,2.15)))
        report=validate_mobile_trace(task,execute_mobile_roundtrip(task,self.route))
        self.assertIn('outside_real_aperture',report['errors'])
        self.assertIn('stale_mobile_contract',validate_mobile_trace(task,self.trace)['errors'])


if __name__=='__main__':unittest.main()
