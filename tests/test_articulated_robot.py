import copy
import json
from pathlib import Path
import tempfile
import unittest
try:
    import numpy as np
    from cityg.runtime.articulated_robot import RobotModel,parse_urdf,rotation
    from cityg.runtime.articulated_validation import box_planes,convex_overlap,validate_fetch_trace
    from cityg.runtime.fetch_transport import angle_delta
except ImportError as error:
    raise unittest.SkipTest('Install the optional cityg[robot] dependencies') from error
from cityg.runtime.transport import Box


class ArticulatedRobotTests(unittest.TestCase):
    def test_parse_topology_and_fk(self):
        xml='''<robot name="test"><link name="root"/><link name="a"/><link name="b"/>
        <joint name="lift" type="prismatic"><parent link="a"/><child link="b"/><axis xyz="0 0 1"/></joint>
        <joint name="turn" type="revolute"><parent link="root"/><child link="a"/>
        <origin xyz="1 0 0"/><axis xyz="0 0 1"/><limit lower="-3" upper="3" velocity="1"/></joint></robot>'''
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'robot.urdf';path.write_text(xml)
            spec=parse_urdf(path)
        self.assertEqual([j['name'] for j in spec['joints']],['turn','lift'])
        fk=RobotModel(spec).fk({'turn':np.pi/2,'lift':.3},(2,3,4),np.pi/2)
        np.testing.assert_allclose(fk['b'][:3,3],[2,4,4.3])
        np.testing.assert_allclose(fk['b'][:3,:3],rotation((0,0,1),np.pi)[:3,:3],atol=1e-12)

    def test_convex_intersection_and_resting_contact(self):
        a=box_planes(Box('a',(0,0,.5),(1,1,1)))
        self.assertFalse(convex_overlap(a,box_planes(Box('b',(0,0,-.5),(1,1,1)))))
        self.assertTrue(convex_overlap(a,box_planes(Box('b',(0,0,0),(1,1,1)))))

    def test_shortest_turn(self):
        self.assertAlmostEqual(angle_delta(-np.pi+.1,np.pi-.1),.2)

    @unittest.skipUnless(Path('assets/robots/fetch/prepared/robot.json').is_file(),'Official robot is an optional downloaded asset')
    def test_real_fetch_pose_ik_and_limits(self):
        model=RobotModel(json.loads(Path('assets/robots/fetch/prepared/robot.json').read_text()))
        seed=dict(zip(model.arm_names,[.15,0,-.7,0,1.8,0,-1.1,0]))
        pose=model.solve([1.011,0,.819],seed,orientation=np.eye(3))
        np.testing.assert_allclose(model.effector(pose)[:3,3],[1.011,0,.819],atol=.003)
        with self.assertRaisesRegex(ValueError,'unreachable'):
            model.solve([5,0,1],seed,orientation=np.eye(3))

    @unittest.skipUnless(Path('outputs/fetch_transport_20261010_v2/trace.json').is_file(),'No local Fetch acceptance candidate')
    def test_negative_state_controls_before_geometry(self):
        root=Path('outputs/fetch_transport_20261010_v2')
        model=RobotModel(json.loads(Path('assets/robots/fetch/prepared/robot.json').read_text()))
        task=json.loads(Path('outputs/paper_cross_building_20261010_v2/task/task.json').read_text())
        source=json.loads((root/'trace.json').read_text())
        def reject(change,expected):
            trace=copy.deepcopy(source);change(trace)
            result=validate_fetch_trace(task,trace,model,None)
            self.assertFalse(result['ok']);self.assertIn(expected,result['errors'])
        reject(lambda t:t['frames'][1]['robot_joints'].update(torso_lift_joint=9),'joint_limit:torso_lift_joint')
        reject(lambda t:t['frames'][1]['robot_joints'].update(l_wheel_joint=9),'wheel_odometry_mismatch')
        reject(lambda t:t['frames'][-1]['objects'][task['object_id']].update(holder='fetch_gripper'),'attachment_state_sequence')
        reject(lambda t:t['frames'][1]['effector_matrix'][0].__setitem__(3,999),'forged_effector')


if __name__=='__main__':unittest.main()
