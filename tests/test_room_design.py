import math
import unittest
from copy import deepcopy
from dataclasses import replace

from cityg.schemas import Room, Floor, Bounds2D, Point2D, Door
from cityg.planning.interiors import FloorDetailAgent, FurnishingProgram, ASSET_CATALOG
from cityg.planning.room_design import RoomDesign, group_integrity
from cityg.planning.room_groups import place_room_design, RoomDesignInfeasible, _front, service_bounds
from cityg.geometry.model import GeometryScene, Vec3
from cityg.geometry.primitives import PrimitiveFactoryMixin
from cityg.geometry.room_appearance import compile_room_appearance


def office_design():
    return RoomDesign("two independent workstations", "warm",
        ({"id":"work", "purpose":"work", "position":"north"},), tuple(
            {"id":f"desk_{i}", "zone":"work", "anchor":{"id":f"table_{i}", "category":"desk"},
             "members":[{"id":f"chair_{i}","category":"office_chair", "side":"front", "slot":0,
                         "gap_m":.25, "face_anchor":True}]}
            for i in range(2)), wall_art=True, tabletop=True)


class RoomDesignTests(unittest.TestCase):
    def setUp(self):
        self.room = Room("room", "Office", "office", Bounds2D(0,0,8,7))
        self.floor = Floor("floor",0,0,3, rooms=[self.room],
                           doors=[Door("door","room",None,Point2D(4,0))])
        self.detail = FloorDetailAgent()
        self.program = FurnishingProgram("room","office","warm modern",.4,(),design=office_design())

    def place(self, program=None):
        return place_room_design(self.detail,None,self.floor,self.room,program or self.program,17)

    def test_instance_binding_and_front_axis(self):
        objects=self.place()
        self.assertEqual(len(objects),4)
        for obj in objects:
            self.assertTrue(self.room.bounds.contains_bounds(obj.bounds))
            self.assertTrue(self.room.bounds.contains_bounds(service_bounds(obj)))
            if obj.category=="office_chair":
                anchor=next(a for a in objects if a.id==obj.metadata["group_anchor_id"])
                direction=_front(obj)
                dx,dy=anchor.position.x-obj.position.x,anchor.position.y-obj.position.y
                self.assertAlmostEqual((direction[0]*dx+direction[1]*dy)/math.hypot(dx,dy),1)

    def test_door_and_object_clearance(self):
        objects=self.place()
        zones,_=self.detail._door_clearance_zones(self.floor,self.room)
        for obj in objects:
            self.assertTrue(self.detail._relation_position_valid(obj,objects,
                self.room.bounds.inset(self.detail.wall_clearance_m),zones))

    def test_duplicate_instance_rejected(self):
        design=deepcopy(office_design())
        design.groups[1]["anchor"]["id"]="table_0"
        with self.assertRaises(ValueError): design.validate(ASSET_CATALOG)

    def test_undeclared_zone_error_identifies_group_and_allowed_ids(self):
        design=deepcopy(office_design())
        design.groups[0]['zone']='east'
        with self.assertRaisesRegex(ValueError, "group 'desk_0'.*undeclared zone 'east'.*'work'"):
            design.validate(ASSET_CATALOG)

    def test_duplicate_group_has_distinct_feedback(self):
        design=deepcopy(office_design())
        design.groups[1]['id']=design.groups[0]['id']
        with self.assertRaisesRegex(ValueError, 'duplicate group id'):
            design.validate(ASSET_CATALOG)

    def test_infeasible_is_explicit(self):
        self.room.bounds=Bounds2D(0,0,1,1)
        with self.assertRaises(RoomDesignInfeasible): self.place()

    def test_six_seat_group_fits_beside_door_in_long_narrow_room(self):
        # Measured failed N30 case: a room-wide 5x5 anchor grid missed the
        # feasible interval. Keep all six full-size chairs and pull-back space.
        from cityg.planning.room_constraints import usable_envelopes, circulation_check
        self.room.bounds=Bounds2D(0,0,9.820980489216549,3.4365204204465627)
        self.room.function='meeting_room'
        self.floor.doors=[Door('door','room',None,Point2D(self.room.bounds.width/2,self.room.bounds.max_y))]
        def resolve(asset,**kwargs):
            if asset.category=='meeting_table':
                return replace(asset,width_m=2.2,depth_m=1.1,height_m=.75,front_axis='+Y')
            return replace(asset,width_m=.54,depth_m=.54,height_m=.92,front_axis='-Y')
        self.detail._resolve_asset=resolve
        design=RoomDesign('six seat meeting','warm',({'id':'meeting','purpose':'meeting','position':'center'},),
            ({'id':'table','zone':'meeting','anchor':{'id':'table','category':'meeting_table'},
              'members':[{'id':f'{side}{slot+1}','category':'meeting_chair','side':side,'slot':slot,
                          'gap_m':.15,'face_anchor':True} for side in ['front','back'] for slot in [-1,0,1]],
              'placement':{'mode':'free','wall':'auto','contact':'auto','max_gap_m':.35}},))
        objects=self.place(replace(self.program,design=design))
        self.assertEqual(len(objects),7)
        self.assertEqual(sum(o.category=='meeting_chair' for o in objects),6)
        usable=self.room.bounds.inset(.12)
        doors,_=self.detail._door_clearance_zones(self.floor,self.room)
        self.assertTrue(all(self.detail._relation_position_valid(o,objects,usable,doors) for o in objects))
        self.assertTrue(all(usable_envelopes(o,objects,usable) for o in objects))
        self.assertTrue(circulation_check(objects,self.room,self.floor,usable)['ok'])

    def test_group_cannot_be_torn_apart(self):
        before=self.place(); after=deepcopy(before)
        after[1].position=Point2D(after[1].position.x+.5,after[1].position.y)
        self.assertFalse(group_integrity(before,after)[0])
        self.assertFalse(group_integrity(before,after[:-1])[0])

    def test_whole_group_translation_allowed(self):
        before=self.place(); after=deepcopy(before)
        for obj in after: obj.position=Point2D(obj.position.x+.5,obj.position.y+.5)
        self.assertTrue(group_integrity(before,after)[0])

    def test_actual_asset_dimensions_used_before_layout(self):
        self.detail._resolve_asset=lambda asset,**kwargs: replace(asset,width_m=asset.width_m*1.1)
        objects=self.place()
        for obj in objects: self.assertAlmostEqual(obj.width_m,ASSET_CATALOG[obj.category].width_m*1.1)

    def test_seed_is_repeatable(self):
        self.assertEqual(self.place(),self.place())

    def test_palette_and_prose_do_not_move_furniture(self):
        before=self.place()
        after=self.place(replace(self.program,design=replace(office_design(),intent="Reworded brief",palette="industrial")))
        self.assertEqual([(o.position,o.rotation_deg) for o in before],[(o.position,o.rotation_deg) for o in after])

    def test_failed_transaction_preserves_original_objects_and_metadata(self):
        self.floor.objects=self.place()
        self.room.object_ids=[o.id for o in self.floor.objects]
        self.room.metadata={"original":True}
        before=deepcopy(self.floor)
        def fail(*args):
            self.room.metadata["temporary"]=True
            raise RuntimeError("asset failure")
        self.detail._place_program=fail
        building=type("B",(),{"id":"b", "floors":[self.floor]})()
        city=type("C",(),{"iter_buildings":lambda _:iter([building])})()
        with self.assertRaises(RuntimeError):
            self.detail.populate_rooms(city,{self.room.id},seed=17)
        self.assertEqual(self.floor,before)

    def test_group_redesign_gate_preserves_previous_design(self):
        self.floor.objects=self.place(); self.room.object_ids=[o.id for o in self.floor.objects]
        self.room.metadata["room_design"]={"status":"accepted",**office_design().to_dict()}
        old=deepcopy(self.room.metadata["room_design"])
        design=replace(office_design(),groups=office_design().groups[:1])
        self.detail.program_overrides={self.room.id:replace(self.program,design=design)}
        building=type("B",(),{"id":"b", "floors":[self.floor]})()
        city=type("C",(),{"iter_buildings":lambda _:iter([building])})()
        stats=self.detail.populate_rooms(city,{self.room.id},seed=17)
        self.assertEqual(stats["furnishing_non_degradation_gate_rejected_room_count"],1)
        self.assertEqual(len(self.floor.objects),4)
        self.assertEqual(self.room.metadata["room_design"],old)

    def test_supported_dressing_uses_realized_geometry(self):
        objects=self.place()
        self.floor.objects=objects
        self.room.metadata["room_design"]={"status":"accepted",**office_design().to_dict()}
        compiler=PrimitiveFactoryMixin()
        scene=GeometryScene(city_id="city",coordinate_system="z_up")
        wall=compiler._box("wall","floor",Vec3(40,30,1.5),Vec3(6,.2,3),30,
            "interior_wall","interior_wall","floor:floor",metadata={"room_ids":["room"]})
        top=compiler._box("table_top",objects[0].id,Vec3(40,34,.70),Vec3(1.4,.7,.1),30,
            "furniture_table","furniture_wood","floor:floor",
            metadata={"component":"top","proxy_style":"table"})
        scene.primitives.extend([wall,top])
        building=type("B",(),{"floors":[self.floor]})()
        city=type("C",(),{"iter_buildings":lambda _:iter([building])})()
        compile_room_appearance(compiler,city,scene)
        books=next(p for p in scene.primitives if p.metadata.get("support_kind")=="tabletop")
        self.assertEqual(books.center.x,40)
        self.assertEqual(books.rotation_z_deg,30)
        self.assertAlmostEqual(books.center.z-books.size.z/2,top.center.z+top.size.z/2)
        self.assertFalse(books.collision_enabled)
        self.assertEqual(wall.material_id,"room_warm_wall")
        self.assertEqual(top.material_id,"room_warm_floor")
        self.assertEqual(books.metadata["support_primitive_id"],top.id)

    def test_glb_material_and_unverified_surface_preserved(self):
        objects=self.place(); self.floor.objects=objects
        self.room.metadata["room_design"]={"status":"accepted",**office_design().to_dict()}
        compiler=PrimitiveFactoryMixin(); scene=GeometryScene(city_id="city",coordinate_system="z_up")
        scene.primitives.append(compiler._box("wall","floor",Vec3(0,0,1.5),Vec3(8,.2,3),0,
            "interior_wall","interior_wall","floor:floor",metadata={"room_ids":["room"]}))
        mesh=compiler._box("mesh",objects[0].id,Vec3(4,4,.4),Vec3(1.4,.7,.8),0,
            "furniture_table","embedded","floor:floor",metadata={"resolved_asset":True})
        scene.primitives.append(mesh)
        city=type("C",(),{"iter_buildings":lambda _:iter([type("B",(),{"floors":[self.floor]})()])})()
        compile_room_appearance(compiler,city,scene)
        self.assertEqual(mesh.material_id,"embedded")
        self.assertFalse(any(p.metadata.get("support_kind")=="tabletop" for p in scene.primitives))

    def test_empty_requests_design_failure_has_template_fallback(self):
        # Invalidly large asset group fails; the existing template remains usable.
        design=replace(office_design(),groups=tuple(
            {"id":f"g{i}","zone":"work","anchor":{"id":f"rack{i}","category":"storage_rack"},"members":[]}
            for i in range(8)))
        self.room.bounds=Bounds2D(0,0,3,3)
        building=type("B",(),{"id":"b"})()
        result=self.detail._place_program(building,self.floor,self.room,replace(self.program,design=design),17)
        self.assertEqual(self.room.metadata["room_design"]["status"],"fallback")
        self.assertTrue(result)


if __name__ == "__main__": unittest.main()
