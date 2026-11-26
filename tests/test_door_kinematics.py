from dataclasses import asdict, replace
import json
import math
import unittest

from cityg.geometry.door_kinematics import fit_door_leaf, local_hinge
from cityg.geometry.model import GeometryPrimitive, Vec3
from cityg.runtime.transport import Box
from cityg.runtime.transport_planning import primitive_box
from cityg.runtime.mobile_geometry import audit_door_static_clearance, door_pose
from cityg.runtime.mobile_transport import mobile_task_from_dict, plan_mobile_route, execute_mobile_roundtrip
from cityg.runtime.mobile_validation import validate_mobile_trace
from cityg.usd.writer import UsdaWriter
from test_mobile_transport import fixture


def leaf(horizontal=False, yaw=0):
    return GeometryPrimitive('door','door','box',Vec3(0,0,1.075),
        Vec3(.9,.08,2.15) if horizontal else Vec3(.08,.9,2.15),
        yaw,'door','wood','floor',body_type='articulated',
        metadata={'room_ids':['room','corridor'],'effective_width_m':.9})


class DoorFitTests(unittest.TestCase):
    def test_fit_preserves_opening_identity_center_and_is_idempotent(self):
        for horizontal in (False,True):
            original=leaf(horizontal,37);saved=asdict(original);p=fit_door_leaf(original)
            self.assertEqual(asdict(original),saved)
            self.assertEqual(p.center,original.center)
            self.assertEqual(p.id,original.id)
            self.assertEqual(p.rotation_z_deg,37)
            self.assertEqual(p.metadata['effective_width_m'],.9)
            self.assertEqual(p.metadata['aperture_size_m'],list(asdict(original.size).values()))
            self.assertAlmostEqual(max(p.size.x,p.size.y),.884)
            self.assertAlmostEqual(min(p.size.x,p.size.y),.04)
            self.assertAlmostEqual(p.size.z,2.134)
            self.assertEqual(fit_door_leaf(p),p)

    def test_both_orientations_and_rotated_frames_clear_unchanged_jambs(self):
        for horizontal in (False,True):
            for yaw in (0,37,90,180,270):
                original=leaf(horizontal,yaw);p=fit_door_leaf(original)
                # Opening .9m, wall ends exactly at +/- .45m, no exemptions.
                walls=[];a=math.radians(yaw)
                for sign in (-1,1):
                    x,y=(sign*.95,0) if horizontal else (0,sign*.95)
                    walls.append(Box(str(sign),(x*math.cos(a)-y*math.sin(a),
                        x*math.sin(a)+y*math.cos(a),1.5),
                        (1,.18,3) if horizontal else (.18,1,3),yaw))
                walls.append(Box('header',(0,0,2.575),(.9,.18,.85) if horizontal else (.18,.9,.85),yaw))
                walls.append(Box('floor',(0,0,-.1),(5,5,.2)))
                self.assertFalse(audit_door_static_clearance(primitive_box(original),walls)['ok'])
                report=audit_door_static_clearance(primitive_box(p),walls,p.metadata['hinge_local_m'])
                self.assertTrue(report['ok'],(horizontal,yaw,report))
                self.assertFalse(report['jambs_exempted'])

    def test_hinge_world_point_is_fixed_at_all_angles(self):
        for horizontal in (False,True):
            p=fit_door_leaf(leaf(horizontal,37));box=primitive_box(p)
            h=local_hinge(box.size,p.metadata)
            def anchor(b):
                a=math.radians(b.yaw)
                return (b.center[0]+math.cos(a)*h[0]-math.sin(a)*h[1],
                    b.center[1]+math.sin(a)*h[0]+math.cos(a)*h[1])
            for angle in range(91):
                moved=door_pose(box,angle,h)
                self.assertLess(math.dist(anchor(box),anchor(moved)),1e-12)

    def test_usd_explicit_corner_and_rotated_joint_frames(self):
        p=fit_door_leaf(leaf(False,90))
        text='\n'.join(UsdaWriter()._articulated_primitive(p,0))
        self.assertIn('physics:localPos1 = (-0.02, -0.442, 0)',text)
        self.assertIn('physics:localPos0 = (0.442, -0.02, 1.075)',text)
        self.assertIn('physics:localRot0 = (0.707106781, 0, 0, 0.707106781)',text)
        self.assertIn('physics:localRot1 = (1, 0, 0, 0)',text)

    def test_bad_fit_or_hinge_rejected(self):
        for gap in (-1,float('nan'),.5):
            with self.assertRaises(ValueError):fit_door_leaf(leaf(),gap_m=gap)
        for hinge in ((0,0,.2),(.5,0,0),(0,float('nan'),0)):
            with self.assertRaises(ValueError):local_hinge((.04,.884,2.134),{'hinge_local_m':hinge})

    def test_fitted_roundtrip_serializes_and_keeps_aperture_separate(self):
        task,_=fixture()
        original=replace(leaf(),size=Vec3(*task.door.size))
        p=fit_door_leaf(original)
        task=replace(task,door=primitive_box(p),door_aperture=task.door,
            door_hinge_local_m=p.metadata['hinge_local_m'])
        task=mobile_task_from_dict(json.loads(json.dumps(asdict(task))))
        candidate,route,receipt=plan_mobile_route(task)
        self.assertIsNotNone(candidate,receipt)
        self.assertGreater(max(task.door_aperture.size[:2]),max(task.door.size[:2]))
        self.assertTrue(audit_door_static_clearance(task.door,task.obstacles,task.door_hinge_local_m)['ok'])
        checked=validate_mobile_trace(candidate,execute_mobile_roundtrip(candidate,route))
        self.assertTrue(checked['ok'],checked)


if __name__=='__main__':unittest.main()
