from copy import deepcopy
from dataclasses import asdict, replace
import json
import unittest

from cityg.geometry import GeometryCompiler
from cityg.geometry.model import GeometryScene
from cityg.geometry.transport_elevator import compile_transport_elevator
from cityg.schemas import Bounds2D, Floor, VerticalConnector
from cityg.runtime.transport import Box
from cityg.runtime.elevator_transit import bind_elevator_transit, execute_elevator_transit, transit_task_from_dict
from cityg.runtime.elevator_validation import validate_elevator_transit
from cityg.usd.writer import UsdaWriter


def compiled_fixture():
    scene=GeometryScene('lift_test','right_handed_z_up_meters')
    connector=VerticalConnector('lift','elevator',Bounds2D(-1.2,-1.4,1.2,1.4),0,2,True,
        {'transport_elevator_version':1})
    floors={i:Floor(f'f{i}',i,i*3.2,3.2) for i in range(3)}
    compile_transport_elevator(GeometryCompiler(),connector,floors,scene)
    slabs=tuple(Box(f'landing_{i}',(0,-3.6,i*3.2-.1),(5,4,.2)) for i in range(3))
    robot=Box('robot',(0,-2.4,.75),(.65,.8,1.5))
    payload=Box('cup',(0,-2.4,1.575),(.09,.09,.11))
    task=bind_elevator_transit(scene,scene_sha256='fixture',elevator_id='lift',robot=robot,
        payload=payload,start_level=0,end_level=2,goal=(0,-2.4,7.15),obstacles=slabs,landing_slabs=slabs)
    return task,scene


class ElevatorTransitTests(unittest.TestCase):
    def test_kinematic_export_has_one_moving_collider_and_no_static_duplicate(self):
        _,scene=compiled_fixture()
        for p in scene.primitives:
            if p.metadata['elevator_role'].startswith('cabin') or p.metadata['elevator_role']=='landing_door':
                self.assertEqual(p.body_type,'kinematic')
                text='\n'.join(UsdaWriter()._primitive(p,'assets.usda',0))
                self.assertIn('physics:kinematicEnabled = true',text)
                self.assertIn('physics:collisionEnabled = true',text)
                self.assertNotIn('static_collision',text)
                self.assertEqual(text.count('def Cube'),1)

    def test_descending_entry_and_exit(self):
        task,_=compiled_fixture()
        task=replace(task,robot=replace(task.robot,center=(0,-2.4,7.15)),
            payload=replace(task.payload,center=(0,-2.4,7.975)),start_z=6.4,end_z=0,goal=(0,-2.4,.75))
        report=validate_elevator_transit(task,execute_elevator_transit(task))
        self.assertTrue(report['ok'],report)

    def test_compiled_cabin_full_entry_ride_exit(self):
        task,scene=compiled_fixture();trace=execute_elevator_transit(task)
        checked=validate_elevator_transit(task,trace)
        self.assertTrue(checked['ok'],checked)
        self.assertAlmostEqual(checked['vertical_travel_m'],6.4)
        self.assertTrue(all(p.collision_enabled for p in scene.primitives))
        restored=transit_task_from_dict(json.loads(json.dumps(asdict(task))))
        self.assertEqual(task.fingerprint,restored.fingerprint)

    def test_teleport_closed_door_identity_and_stale_negative_controls(self):
        task,_=compiled_fixture();trace=execute_elevator_transit(task)
        for kind,error in [('teleport','base_discontinuity'),('door','crossing_closed_lift_door'),
                           ('identity','object_identity_or_duplicate'),('stale','stale_transit_contract')]:
            bad=deepcopy(trace);f=next(f for f in bad['frames'] if f['action']=='enter')
            if kind=='teleport':f['robot_base'][1]+=.8
            elif kind=='door':f['opening']=0
            elif kind=='identity':f['objects']['copy']=deepcopy(f['objects']['cup'])
            else:f['contract_sha256']='stale'
            self.assertIn(error,validate_elevator_transit(task,bad)['errors'])

    def test_floor_gap_and_shaft_obstruction_are_not_ignored(self):
        task,_=compiled_fixture()
        broken=replace(task,landing_slabs=())
        self.assertIn('unsupported_entry_exit_sweep',
            validate_elevator_transit(broken,execute_elevator_transit(broken))['errors'])
        obstruction=Box('uncut_floor',(0,0,3.1),(3,3,.2))
        broken=replace(task,obstacles=(*task.obstacles,obstruction))
        errors=validate_elevator_transit(broken,execute_elevator_transit(broken))['errors']
        self.assertIn('elevator_static_collision:uncut_floor',errors)

    def test_open_door_in_motion_and_missing_exit_fail(self):
        task,_=compiled_fixture();trace=execute_elevator_transit(task)
        bad=deepcopy(trace);next(f for f in bad['frames'] if f['action']=='ride')['opening']=1
        self.assertIn('open_door_during_travel',validate_elevator_transit(task,bad)['errors'])
        bad={**trace,'frames':[f for f in trace['frames'] if f['action'] not in ('exit','close_end','done')]}
        self.assertIn('incomplete_elevator_transit',validate_elevator_transit(task,bad)['errors'])

    def test_legacy_visual_cabin_and_disabled_collider_fail_binding(self):
        _,scene=compiled_fixture()
        scene.primitives[0].collision_enabled=False
        with self.assertRaises(ValueError):
            bind_elevator_transit(scene,scene_sha256='fixture',elevator_id='lift',
                robot=Box('r',(0,-2.4,.75),(.65,.8,1.5)),payload=Box('p',(0,-2.4,1.575),(.09,.09,.11)),
                start_level=0,end_level=2,goal=(0,-2.4,7.15),obstacles=(),landing_slabs=())


if __name__=='__main__':unittest.main()
