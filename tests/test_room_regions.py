import unittest
from dataclasses import replace
from copy import deepcopy

from cityg.planning.room_regions import region_bounds, reserved_bounds, validate_uv
from cityg.planning.room_design import RoomDesign
from cityg.planning.interiors import FloorDetailAgent, FurnishingProgram, ASSET_CATALOG
from cityg.planning.room_groups import place_room_design, RoomDesignInfeasible
from cityg.schemas import Bounds2D, Room, Floor, Door, Point2D


class RoomRegionTests(unittest.TestCase):
    def setUp(self):
        self.room=Room('r','open room','office',Bounds2D(10,20,22,30))
        self.floor=Floor('f',0,0,3,rooms=[self.room],doors=[Door('d','r',None,Point2D(16,20),1.2)])
        self.design=RoomDesign('zoned layout','warm',
            ({'id':'left','purpose':'work','position':'center','bounds_uv':[0,0,.4,1]},
             {'id':'right','purpose':'work','position':'center','bounds_uv':[.6,0,1,1]}),
            tuple({'id':zone,'zone':zone,'anchor':{'id':zone+'_desk','category':'desk'},'members':[],
                   'placement':{'mode':'free','wall':'auto','contact':'back','max_gap_m':.2,'facing':'south'}}
                  for zone in ('left','right')),
            reserved_areas=({'id':'aisle','purpose':'main aisle','bounds_uv':[.4,0,.6,1],'min_width_m':1.8},))

    def place(self,design=None):
        return place_room_design(FloorDetailAgent(),None,self.floor,self.room,
            FurnishingProgram('r','office','warm',.5,(),design=design or self.design),17)

    def test_zone_containment_and_metric_aisle(self):
        objects=self.place()
        aisle=reserved_bounds(self.room.bounds,self.design.reserved_areas)[0]
        self.assertAlmostEqual(aisle.width,2.4)
        for obj in objects:
            zone=next(z for z in self.design.zones if z['id']==obj.metadata['zone_id'])
            self.assertTrue(region_bounds(self.room.bounds,zone['bounds_uv']).contains_bounds(obj.bounds))
            self.assertFalse(aisle.overlaps_area(obj.bounds))

    def test_invalid_rectangles_and_too_narrow_actual_aisle(self):
        for uv in ([0,0,0,1],[-.1,0,.5,1],[0,0,2,1],[0,0,float('nan'),1]):
            with self.assertRaises(ValueError):validate_uv(uv)
        with self.assertRaisesRegex(ValueError,'width'):
            reserved_bounds(Bounds2D(0,0,4,4),self.design.reserved_areas)

    def test_member_cannot_spill_outside_its_functional_zone(self):
        d=deepcopy(self.design)
        d.zones[0]['bounds_uv']=[0,0,.05,.05]
        with self.assertRaises(RoomDesignInfeasible):self.place(d)

    def test_serialization_roundtrip_and_duplicate_reservations(self):
        self.assertEqual(RoomDesign.from_dict(self.design.to_dict(),ASSET_CATALOG),self.design)
        with self.assertRaisesRegex(ValueError,'unique'):
            replace(self.design,reserved_areas=self.design.reserved_areas*2).validate(ASSET_CATALOG)

    def test_compiled_audit_catches_intrusion_after_planning(self):
        from pathlib import Path
        from cityg.planning.prototypes import LayoutPrototypeLibrary
        from cityg.planning.prototype_lab import make_lab,compiled_open_plan_checks
        from cityg.planning.room_envelope import metric_envelope
        from cityg.geometry.model import GeometryScene,GeometryPrimitive,Vec3
        from cityg.schemas import InteriorObject
        library=LayoutPrototypeLibrary(Path(__file__).resolve().parents[1]/'configs/layout_prototypes/v1')
        _,targets=make_lab(library,['office_open_twelve_v1'])
        key,b,f,r=targets[0]
        r.metadata['room_design']=library.materialize(key).design.to_dict()
        bounds=metric_envelope(b,f,r)['bounds']
        # Within the room, but incorrectly compiled into the central aisle.
        obj=InteriorObject('desk',r.id,'desk','fixture',bounds.center,1,1,1,metadata={'zone_id':'south_west'})
        f.objects=[obj]
        scene=GeometryScene('test','z_up')
        scene.primitives=[GeometryPrimitive('p',obj.id,'box',Vec3(bounds.center.x,bounds.center.y,.5),
            Vec3(1,1,1),0,'furniture_desk','wood','floor')]
        report=compiled_open_plan_checks(scene,targets)
        self.assertFalse(report[0]['ok'])
        self.assertFalse(report[0]['aisles_clear'])
        self.assertFalse(report[0]['zone_contained'])


if __name__=='__main__':unittest.main()
