import unittest
from types import SimpleNamespace

from cityg.geometry.model import GeometryPrimitive,GeometryScene,Vec3
from cityg.runtime.transport import Box
from cityg.runtime.transport_readiness import audit_transport_readiness
from cityg.schemas import Bounds2D,Floor,Room,VerticalConnector,Point2D


class TransportReadinessTests(unittest.TestCase):
    def fixture(self):
        corridor=Room('corridor','corridor','corridor',Bounds2D(0,0,2.9,20))
        floor=Floor('f0',0,0,3.2,rooms=[corridor])
        b=SimpleNamespace(id='b',entrance=Point2D(1.45,20),floors=[floor],
            vertical_connectors=[VerticalConnector('stairs','stairs',Bounds2D(.29,9,2.61,11),0,1)])
        city=SimpleNamespace(iter_buildings=lambda:iter([b]))
        scene=GeometryScene('fixture','right_handed_z_up_meters')
        scene.primitives=[GeometryPrimitive('stair','stairs','box',Vec3(1.45,10,1),Vec3(2.32,2,2),
            0,'stair_tread','stairs','floor:f0')]
        return city,scene,Box('r',(0,0,.75),(.65,.8,1.5))

    def test_diagnoses_actual_stair_clearance_without_modification(self):
        city,scene,robot=self.fixture();p=scene.primitives[0]
        report=audit_transport_readiness(city,scene,['b'],robot)
        self.assertFalse(report['ok'])
        self.assertFalse(report['scene_mutated'])
        gaps=report['buildings'][0]['corridor_bottlenecks'][0]['side_gaps_m']
        self.assertAlmostEqual(gaps[0],.29);self.assertAlmostEqual(gaps[1],.29)
        self.assertEqual(scene.primitives[0],p)

    def test_missing_compiled_stairs_is_not_reported_as_observed_blockage(self):
        city,scene,robot=self.fixture();scene.primitives=[]
        report=audit_transport_readiness(city,scene,['b'],robot)
        self.assertEqual(report['buildings'][0]['corridor_bottlenecks'],[])
        self.assertEqual(report['issues'][0]['code'],'missing_realized_transport_elevator')


if __name__=='__main__':unittest.main()
