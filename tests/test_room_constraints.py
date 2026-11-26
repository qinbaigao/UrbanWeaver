import math
import json
import unittest
from copy import deepcopy
from dataclasses import replace

from cityg.planning.interiors import FloorDetailAgent, FurnishingProgram, ASSET_CATALOG
from cityg.planning.room_design import RoomDesign
from cityg.planning.room_groups import place_room_design, RoomDesignInfeasible
from cityg.planning.room_constraints import (wall_contact, wall_segments, use_envelopes,
    group_relation_cost, circulation_check, direction)
from cityg.schemas import Bounds2D, Room, Floor, Door, Point2D, InteriorObject
from cityg.refinement.room import RoomProgramAgent


def design(*categories):
    return RoomDesign("wall-aware room", "warm", ({"id":"main","position":"center","purpose":"use"},),
        tuple({"id":f"g{i}","zone":"main","anchor":{"id":f"a{i}","category":cat},"members":[]}
              for i,cat in enumerate(categories)))


class RoomConstraintsTests(unittest.TestCase):
    def setUp(self):
        self.room=Room("r","r","bedroom",Bounds2D(0,0,8,7))
        self.floor=Floor("f",0,0,3,rooms=[self.room],doors=[Door("d","r",None,Point2D(4,0))])
        self.detail=FloorDetailAgent()

    def place(self, d):
        return place_room_design(self.detail,None,self.floor,self.room,
            FurnishingProgram("r","bedroom","warm",.5,(),design=d),17)

    def test_bed_head_and_storage_back_contact(self):
        objects=self.place(design("bed","wardrobe","bookcase"))
        for obj in objects:
            side,gap=wall_contact(obj,self.room,{})
            self.assertAlmostEqual(gap,.12)
            self.assertEqual(obj.metadata["wall_binding"]["side"],side)
            self.assertTrue(obj.metadata["room_circulation"]["ok"])
            if obj.category=="bed":
                self.assertEqual(obj.metadata["front_axis"],"-Y")
                self.assertEqual(obj.metadata["wall_binding"]["contact_axis"],"+Y")

    def test_member_minimum_gap_respects_collision_margin(self):
        d=design("bed")
        d.groups[0]["members"]=[{"id":"nightstand","category":"bedside_table",
            "side":"right","slot":0,"gap_m":.15,"face_anchor":False}]
        objects=self.place(d)
        member=next(o for o in objects if o.category=="bedside_table")
        self.assertAlmostEqual(member.metadata["requested_gap_m"],.15)
        self.assertGreater(member.metadata["effective_gap_m"],self.detail.object_clearance_m)

    def test_explicit_freestanding_exception(self):
        d=design("wardrobe")
        d.groups[0]["placement"]={"mode":"free","wall":"auto","contact":"back","max_gap_m":.2}
        obj=self.place(d)[0]
        self.assertNotIn("wall_binding",obj.metadata)
        self.assertGreater(wall_contact(obj,self.room,{})[1],1)

    def test_free_counter_preserves_semantic_facing_for_each_front_axis(self):
        for axis in ('+X','-X','+Y','-Y'):
            self.detail.catalog = dict(ASSET_CATALOG)
            self.detail.catalog['reception_desk'] = replace(ASSET_CATALOG['reception_desk'],front_axis=axis)
            d=design('reception_desk')
            d.groups[0]['placement']={'mode':'free','wall':'auto','contact':'auto','max_gap_m':.2,'facing':'south'}
            fx,fy=direction(self.place(d)[0])
            self.assertAlmostEqual(fx,0,places=6)
            self.assertAlmostEqual(fy,-1,places=6)

    def test_conflicting_wall_and_facing_are_not_silently_ignored(self):
        d=design('wardrobe')
        d.groups[0]['placement']={'mode':'wall','wall':'north','contact':'back','max_gap_m':.2,'facing':'north'}
        with self.assertRaises(RoomDesignInfeasible): self.place(d)
        d.groups[0]['placement']['facing']='diagonal'
        with self.assertRaisesRegex(ValueError,'facing'):d.validate(ASSET_CATALOG)

    def test_wall_side_selection_and_door_gap(self):
        d=design("wardrobe")
        d.groups[0]["placement"]={"mode":"wall","wall":"south","contact":"back","max_gap_m":.2}
        obj=self.place(d)[0]
        self.assertEqual(wall_contact(obj,self.room,{})[0],"south")
        self.assertFalse(obj.bounds.min_x<4<obj.bounds.max_x)
        for wall in wall_segments(self.floor,self.room):
            if wall["side"]=="south": self.assertFalse(wall["start"]<4<wall["end"])

    def test_use_envelopes_depend_on_category(self):
        objects=self.place(design("bed","wardrobe"))
        bed,wardrobe=objects
        self.assertEqual(len(use_envelopes(bed)),2)
        self.assertEqual(len(use_envelopes(wardrobe)),1)
        self.assertAlmostEqual(min(use_envelopes(wardrobe)[0].width,use_envelopes(wardrobe)[0].depth),.75)

    def test_disconnected_door_paths_detected_even_for_thin_divider(self):
        self.floor.doors.append(Door("d2","r",None,Point2D(4,7)))
        barrier=InteriorObject("divider","r","cabinet","asset",Point2D(4,3.53),7.8,.04,2)
        result=circulation_check([barrier],self.room,self.floor,self.room.bounds.inset(.12))
        self.assertFalse(result["ok"])
        self.assertIn("disconnected",result["reason"])

    def test_no_door_is_not_reported_as_verified_entrance(self):
        self.floor.doors=[]
        result=circulation_check([],self.room,self.floor,self.room.bounds.inset(.12))
        self.assertTrue(result["ok"])
        self.assertFalse(result["entrance_verified"])

    def test_required_cross_group_facing(self):
        d=replace(design("sofa","tv_console"),group_relations=(
            {"subject":"g0","target":"g1","relation":"faces","min_distance_m":1,"max_distance_m":6,"required":True},
            {"subject":"g1","target":"g0","relation":"faces","min_distance_m":1,"max_distance_m":6,"required":True}))
        objects=self.place(d)
        self.assertIsNotNone(group_relation_cost(d.group_relations,objects))
        a,b=objects
        dx,dy=b.position.x-a.position.x,b.position.y-a.position.y
        fx,fy=direction(a)
        self.assertGreater((fx*dx+fy*dy)/math.hypot(dx,dy),.94)

    def test_protected_group_preserves_pose_asset_and_metadata(self):
        d=design("bed","wardrobe")
        self.floor.objects=self.place(d)
        self.room.metadata["room_design"]={"status":"accepted",**d.to_dict()}
        old=deepcopy(next(o for o in self.floor.objects if o.metadata["group_key"]=="g0"))
        revised=deepcopy(d)
        revised.groups[1]["placement"]={"mode":"wall","wall":"west","contact":"back","max_gap_m":.2}
        result=self.place(replace(revised,protected_groups=("g0",)))
        self.assertEqual(next(o for o in result if o.id==old.id),old)

    def test_infeasible_local_repair_does_not_unprotect_or_mutate(self):
        d=design("bed","wardrobe")
        self.floor.objects=self.place(d)
        self.room.object_ids=[o.id for o in self.floor.objects]
        self.room.metadata["room_design"]={"status":"accepted",**d.to_dict()}
        before=deepcopy(self.floor)
        bad=deepcopy(d);bad.groups[0]["anchor"]["category"]="desk"
        self.detail.program_overrides={"r":FurnishingProgram("r","bedroom","warm",.5,(),design=replace(bad,protected_groups=("g0",)))}
        building=type("B",(),{"id":"b","floors":[self.floor]})()
        city=type("C",(),{"iter_buildings":lambda _:iter([building])})()
        with self.assertRaises(RoomDesignInfeasible): self.detail.populate_rooms(city,{"r"},seed=17)
        self.assertEqual(before,self.floor)

    def test_invalid_cross_group_reference_rejected(self):
        d=replace(design("bed"),group_relations=({"subject":"g0","target":"unknown","relation":"near",
            "min_distance_m":0,"max_distance_m":3,"required":True},))
        with self.assertRaises(ValueError): d.validate(ASSET_CATALOG)

    def test_protected_group_uniqueness_is_enforced_locally(self):
        from cityg.planning.room_design import DESIGN_SCHEMA
        self.assertNotIn("uniqueItems",DESIGN_SCHEMA["properties"]["protected_groups"])
        with self.assertRaisesRegex(ValueError,"unique"):
            replace(design("bed"),protected_groups=("g0","g0")).validate(ASSET_CATALOG)

    def test_room_wire_schema_binds_catalog_without_mutating_generic_schema(self):
        from cityg.refinement.room import ROOM_PROGRAM_RESPONSE_SCHEMA
        from cityg.planning.room_design import DESIGN_SCHEMA
        props=ROOM_PROGRAM_RESPONSE_SCHEMA["properties"]["design"]["properties"]["groups"]["items"]["properties"]
        self.assertEqual(props["anchor"]["properties"]["category"]["enum"],sorted(ASSET_CATALOG))
        self.assertNotIn("enum",DESIGN_SCHEMA["properties"]["groups"]["items"]["properties"]["anchor"]["properties"]["category"])

    def test_broken_constrained_decode_retries_plain_json_with_validation(self):
        payload={"room_id":"r","style":"warm","density":.5,"requests":[],"design":design("bed").to_dict()}
        payload["design"]["furnishing_brief"]={"occupants":1,"capacity_reason":"one sleeper",
            "items":[{"category":"bed","minimum":1,"target":1,"purpose":"sleep"}],"tradeoffs":""}
        schemas=[]
        class Service:
            def complete(self,messages,schema):
                schemas.append(schema)
                return '{"design": ' if len(schemas)==1 else json.dumps(payload)
        building=type("B",(),{"id":"b","function":"residential"})()
        city=type("C",(),{"name":"fixture"})()
        result=RoomProgramAgent(Service(),max_attempts=2).propose(city,building,self.floor,self.room)
        self.assertIsNotNone(schemas[0])
        self.assertIsNone(schemas[1])
        self.assertEqual(len(result.attempts),2)
        self.assertIn("JSONDecodeError",result.attempts[0].error)
        result.program.validate(ASSET_CATALOG)

    def test_invalid_furniture_reports_exact_binding(self):
        d=design("invented_sofa")
        with self.assertRaisesRegex(ValueError,"invented_sofa.*a0"):
            d.validate(ASSET_CATALOG)
        d=design("bed","wardrobe")
        d.groups[1]["anchor"]["id"]="a0"
        with self.assertRaisesRegex(ValueError,"a0.*g1"):
            d.validate(ASSET_CATALOG)

    def test_agent_cannot_omit_non_target_protection(self):
        d=design("bed","wardrobe")
        self.floor.objects=self.place(d)
        self.room.object_ids=[o.id for o in self.floor.objects]
        self.room.metadata["room_design"]={"status":"accepted",**d.to_dict()}
        payload={"room_id":"r","style":"warm","density":.5,"requests":[],"design":d.to_dict()}
        service=type("S",(),{"complete":lambda _,*args:json.dumps(payload)})()
        building=type("B",(),{"id":"b","function":"residential"})()
        city=type("C",(),{"name":"fixture"})()
        result=RoomProgramAgent(service).propose(city,building,self.floor,self.room,
            visual_feedback={"target_group_ids":["g1"],"issues":["fix wardrobe"]})
        self.assertEqual(result.program.design.protected_groups,("g0",))
        self.assertEqual(result.raw["design"]["protected_groups"],("g0",))
        # A compiled group ID is valid only when an actual object in this room
        # witnesses its mapping to the local semantic key; no prefix guessing.
        obj=next(o for o in self.floor.objects if o.metadata.get('group_key')=='g1')
        alias=obj.metadata['group_id']
        rebound=RoomProgramAgent(service).propose(city,building,self.floor,self.room,
            visual_feedback={'target_group_ids':[alias]})
        self.assertEqual(rebound.program.design.protected_groups,('g0',))
        with self.assertRaises(ValueError):
            RoomProgramAgent(service).propose(city,building,self.floor,self.room,
                visual_feedback={"target_group_ids":["unknown"]})
        with self.assertRaises(ValueError):
            RoomProgramAgent(service).propose(city,building,self.floor,self.room,
                visual_feedback={'target_group_ids':['other_room_g1']})

    def test_explicit_mesh_head_axis_respected(self):
        def resolve(asset,**kwargs):
            return replace(asset,id="mesh_bed",front_axis="+X",head_axis="-X")
        self.detail._resolve_asset=resolve
        obj=self.place(design("bed"))[0]
        self.assertEqual(obj.metadata["head_axis"],"-X")
        self.assertAlmostEqual(wall_contact(obj,self.room,{})[1],.12)

    def test_real_bed_nightstand_head_alignment_in_compact_room(self):
        # Actual first HSSD trial proportions; test without downloaded binaries.
        self.room.bounds=Bounds2D(67.55,27.18,73.14,30.90)
        self.floor.doors=[Door("d","r",None,Point2D(70.345,27.18),.9)]
        d=design("bed")
        d.groups[0]["members"]=[{"id":"night","category":"bedside_table",
            "side":"right","slot":0,"gap_m":.30,"face_anchor":False}]
        for axis in ("+X","-X","+Y","-Y"):
            with self.subTest(axis=axis):
                def resolve(asset,**kwargs):
                    long,short,height=(2.1536,1.8547,.8449) if asset.category=="bed" else (.47,.48,.60)
                    width,depth=(long,short) if axis.endswith("X") else (short,long)
                    return replace(asset,id="mesh_"+asset.category,width_m=width,depth_m=depth,
                        height_m=height,front_axis=axis,
                        head_axis={"+X":"-X","-X":"+X","+Y":"-Y","-Y":"+Y"}[axis])
                self.detail._resolve_asset=resolve
                objects=self.place(d);bed,night=objects
                self.assertEqual(night.metadata["group_alignment"],"head_edge")
                hx,hy=direction(bed,bed.metadata["head_axis"])
                def head_edge(o):
                    return (hx*o.position.x+hy*o.position.y+
                            (abs(hx)*o.bounds.width+abs(hy)*o.bounds.depth)/2)
                self.assertAlmostEqual(head_edge(bed),head_edge(night))
                self.assertAlmostEqual(wall_contact(bed,self.room,{})[1],.12)
                self.assertTrue(all(o.metadata["room_circulation"]["ok"] for o in objects))
                for o in objects:
                    asset=resolve(self.detail.catalog[o.category])
                    self.assertEqual((o.width_m,o.depth_m,o.height_m),
                                     (asset.width_m,asset.depth_m,asset.height_m))
                # Infeasibility must still fail, not rescale/remove a member.
                before=deepcopy(self.floor)
                old_bounds=self.room.bounds
                self.room.bounds=Bounds2D(67.55,27.18,69.5,29.1)
                with self.assertRaises(RoomDesignInfeasible):self.place(d)
                self.room.bounds=old_bounds
                self.assertEqual(before,self.floor)

    def test_use_envelopes_invariant_to_mesh_axis_convention(self):
        for category in ("bed","office_chair"):
            baseline=InteriorObject("a","r",category,"mesh",Point2D(4,4),2.1,.8,1,
                                    metadata={"front_axis":"+X"})
            equivalent=replace(baseline,width_m=.8,depth_m=2.1,rotation_deg=270,
                               metadata={"front_axis":"+Y"})
            for a,b in zip(use_envelopes(baseline),use_envelopes(equivalent)):
                for key in ("min_x","min_y","max_x","max_y"):
                    self.assertAlmostEqual(getattr(a,key),getattr(b,key))


if __name__=="__main__": unittest.main()
