from copy import deepcopy
from dataclasses import asdict
from types import SimpleNamespace
import unittest

from cityg.geometry.model import GeometryScene,GeometryPrimitive,Vec3
from cityg.geometry.transport_access import choose_exterior_route
from cityg.schemas import Bounds2D,Point2D
from cityg.runtime.transport import Box,Surface
from cityg.runtime.city_transport import execute_city_task
from cityg.runtime.city_transport_validation import validate_city_trace


def fixture():
    source=Surface('table_a:top','table_a',(.8,0,.8),(.8,1.),0)
    target=Surface('table_b:top','table_b',(.8,2,.8),(.8,1.),0)
    obj=Box('cup',(.8,0,.855),(.09,.09,.11));robot=Box('robot',(0,0,.75),(.65,.8,1.5))
    def p(key,center,size,semantic,layer='floor:f',metadata=None):
        return GeometryPrimitive(key,key,'box',Vec3(*center),Vec3(*size),0,semantic,'concrete',layer,metadata=metadata or {})
    scene=GeometryScene('probe','right_handed_z_up_meters',primitives=[
        p('cup_primitive',obj.center,obj.size,'cup',metadata={'subentity_id':'cup'}),
        p('table_a',(.8,0,.4),(.8,1,.8),'table'),p('table_b',(.8,2,.4),(.8,1,.8),'table'),
        p('floor',(0,1,-.1),(5,5,.2),'collision_envelope','shell:b')])
    ops=[{'kind':'attach'},
         *({'kind':'manipulate','target':v} for v in ((.8,0,1.8),(0,0,1.8),(0,0,1.575))),
         {'kind':'walk','target':(0,2,.75)},
         *({'kind':'manipulate','target':v} for v in ((0,2,1.8),(.8,2,1.8),(.8,2,.855))),
         {'kind':'release'}]
    task={'scene_sha256':'fixture','object_id':'cup','source_primitive_ids':['cup_primitive'],
          'object':asdict(obj),'robot':asdict(robot),'source':asdict(source),'target':asdict(target),
          'destination':(.8,2,.855),'final_robot':(0,2,.75),'carry_offset':(0,0,.825),
          'dt_s':.1,'base_speed_mps':.5,'effector_speed_mps':.25,'door_s':.8,'reach_m':1.6,
          'margin_m':.01,'doors':{},'lifts':{},'operations':ops}
    return task,scene


class CityTransportTests(unittest.TestCase):
    def test_persistent_attachment_and_release(self):
        task,scene=fixture();trace=execute_city_task(task)
        report=validate_city_trace(task,trace,scene,scene_sha256='fixture')
        self.assertTrue(report['ok'],report['errors'])
        self.assertTrue(all(set(f['objects'])=={'cup'} for f in trace['frames']))
        self.assertEqual(trace['frames'][-1]['objects']['cup']['support'],'table_b:top')

    def test_duplicate_and_teleport_rejected(self):
        task,scene=fixture();trace=execute_city_task(task)
        bad=deepcopy(trace);f=next(f for f in bad['frames'] if f['action']=='walk')
        f['objects']['copy']=deepcopy(f['objects']['cup'])
        self.assertIn('object_identity_or_duplicate',validate_city_trace(task,bad,scene,scene_sha256='fixture')['errors'])
        bad=deepcopy(trace);f=next(f for f in bad['frames'] if f['action']=='walk');f['robot_base'][0]+=3
        self.assertIn('base_speed_discontinuity',validate_city_trace(task,bad,scene,scene_sha256='fixture')['errors'])

    def test_missing_support_and_closed_wall_are_not_ignored(self):
        task,scene=fixture();trace=execute_city_task(task)
        scene.primitives=[p for p in scene.primitives if p.id!='floor']
        result=validate_city_trace(task,trace,scene,scene_sha256='fixture')
        self.assertTrue(any(e.startswith('unsupported_base') for e in result['errors']))
        task,scene=fixture()
        scene.primitives.append(GeometryPrimitive('wall','wall','box',Vec3(0,1,1),Vec3(2,.1,2),0,'interior_wall','concrete','floor:f'))
        result=validate_city_trace(task,trace,scene,scene_sha256='fixture')
        self.assertTrue(any(e.startswith('robot_collision') for e in result['errors']))

    def test_source_binding_and_missing_release_rejected(self):
        task,scene=fixture();trace=execute_city_task(task);trace['frames'].pop()
        self.assertIn('incomplete_operation_sequence',validate_city_trace(task,trace,scene,scene_sha256='fixture')['errors'])
        scene.primitives[0].metadata['subentity_id']='not_the_cup'
        self.assertIn('source_binding_mismatch',validate_city_trace(task,trace,scene,scene_sha256='fixture')['errors'])

    def test_exterior_candidates_preserve_input(self):
        buildings=[SimpleNamespace(entrance=Point2D(5,30),footprint=Bounds2D(0,20,10,30),metadata={}),
                   SimpleNamespace(entrance=Point2D(5,10),footprint=Bounds2D(0,0,10,10),metadata={})]
        scene=GeometryScene('probe','right_handed_z_up_meters')
        before=asdict(scene);route,attempts=choose_exterior_route(scene,buildings)
        self.assertEqual(asdict(scene),before);self.assertTrue(route);self.assertFalse(attempts[-1]['hits'])


if __name__=='__main__':unittest.main()
