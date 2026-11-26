import math
import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

from cityg.assets import AssetRecord, AssetRegistry, choose_asset_variant
from cityg.geometry.indoor_assets import preserve_indoor_proportions
from cityg.geometry.model import GeometryScene, Vec3
from cityg.geometry.surface_dressing import surfaces
from cityg.schemas import Building, Bounds2D, Point2D, InteriorObject
import test_room_enrichment as enrichment


class IndoorAssetPlacementTests(unittest.TestCase):
    setUp = enrichment.RoomEnrichmentTests.setUp
    setup_geometry = enrichment.RoomEnrichmentTests.setup_geometry
    compile = enrichment.RoomEnrichmentTests.compile
    def prop(self, **metadata):
        record = AssetRecord("real_book", "book", geometry_path="book.glb", dimensions_m=(.16,.045,.23),
            environment="indoor",room_types=("office",),metadata={
                "runtime_enabled":True,"indoor_annotation_version":1,"placement_kind":"surface",
                "orientation":{"canonical_forward_axis":"+X","orientation_confidence":"reviewed"},**metadata})
        self.compiler.asset_registry=AssetRegistry()
        self.compiler.asset_registry.register(record)
        return record

    def book_request(self):
        self.room.metadata["room_design"]["surface_items"]=[{
            "id":"books","support_member_id":"desk","surface":"shelves",
            "category":"book","count":2,"placement":"spread"}]

    def test_curated_mesh_shelf_uses_true_size_front_and_clearance(self):
        top=self.setup_geometry(37)
        self.floor.objects[0].metadata["front_axis"]="+X"
        self.prop();self.book_request()
        top.size=Vec3(1,1,1)
        top.metadata={"resolved_asset":True,"asset_metadata":{"room_support_surfaces":[
            {"id":"low","kind":"shelves","verified":True,"center":[0,0,-.3],"size":[.8,.8],"clearance_fraction":.20},
            {"id":"high","kind":"shelves","verified":True,"center":[0,0,0],"size":[.8,.8],"clearance_fraction":.30}]}}
        report=self.compile()
        self.assertEqual(report["placed"],2)
        children=[p for p in self.scene.primitives if p.metadata.get("surface_subentity")]
        for p in children:
            self.assertEqual(p.primitive_type,"mesh")
            self.assertEqual(p.size,Vec3(.16,.045,.23))
            self.assertEqual(p.metadata["asset_id"],"real_book")
            self.assertEqual(p.metadata["support_surface_id"],"top:high")
            self.assertAlmostEqual(p.rotation_z_deg,37)
            self.assertFalse(p.collision_enabled)

    def test_mesh_shelf_with_unknown_ceiling_is_not_trusted(self):
        top=self.setup_geometry()
        top.metadata={"resolved_asset":True,"asset_metadata":{"room_support_surfaces":[
            {"id":"unknown","kind":"shelves","verified":True,"center":[0,0,0],"size":[.8,.8]}]}}
        self.assertEqual(surfaces([top],"shelves"),[])

    def test_unreviewed_and_wrong_room_props_fall_back(self):
        self.setup_geometry()
        record=self.prop(runtime_enabled=False)
        registry=self.compiler.asset_registry
        self.assertEqual(registry.search("book",category="book"),[])
        self.assertIsNone(choose_asset_variant([(record,10)],"x"))
        from cityg.geometry.indoor_assets import surface_asset
        self.assertIsNone(surface_asset(self.compiler,"book","office","x"))
        self.prop()
        self.assertIsNone(surface_asset(self.compiler,"book","bedroom","x"))

    def test_post_massing_fit_preserves_physical_proportions_and_bottom(self):
        top=self.setup_geometry()
        top.center=Vec3(1,2,.5);top.size=Vec3(2,.5,1)
        top.metadata={"resolved_asset":True,"asset_metadata":{
            "indoor_annotation_version":1,"physical_dimensions_m":[2,1,1]}}
        preserve_indoor_proportions(self.scene)
        self.assertEqual(top.size,Vec3(1,.5,.5))
        self.assertEqual(top.center,Vec3(1,2,.25))
        preserve_indoor_proportions(self.scene)
        self.assertEqual(top.size,Vec3(1,.5,.5))

    def test_metric_planning_roundtrip_and_stale_pose_rejection(self):
        from cityg.planning.room_metric_frame import place_metric_room
        from cityg.geometry import GeometryCompiler
        from cityg.planning.interiors import FloorDetailAgent, FurnishingProgram
        from cityg.assets import AssetResolver
        record=AssetRecord("desk_mesh","desk",geometry_path="desk.glb",dimensions_m=(1.5,.7,.75),
            environment="indoor",room_types=("office",),metadata={"runtime_enabled":True,
                "indoor_annotation_version":1,"physical_dimensions_m":[1.5,.7,.75]})
        registry=AssetRegistry();registry.register(record)
        detail=FloorDetailAgent(asset_resolver=AssetResolver(registry,(),max_provider_calls=0))
        building=Building("b","test","commercial",Bounds2D(0,0,20,20),Point2D(10,0),
                          floors=[self.floor],metadata={"massing_style":"bar","orientation_deg":19})
        program=FurnishingProgram("r","office","warm",.5,(),design=self.design)
        def solved(_detail,_building,_floor,room,_program,_seed,*,existing_objects=None):
            self.assertLess(room.bounds.width,self.room.bounds.width)
            self.assertIs(existing_objects,self.floor.objects)
            return [InteriorObject("o","r","desk","desk_mesh",room.bounds.center,1.5,.7,.75,90)]
        with patch("cityg.planning.room_groups.place_room_design",side_effect=solved):
            result=place_metric_room(detail,building,self.floor,self.room,program,1)
        self.floor.objects=result
        compiler=GeometryCompiler(asset_registry=registry)
        scene=GeometryScene("c","z_up",materials=compiler._materials())
        compiler._compile_furniture(self.floor,scene)
        self.assertEqual(scene.primitives[0].size,Vec3(1.5,.7,.75))
        compiler._conform_building_details(building,scene,0,clip_interior_walls=True)
        self.assertAlmostEqual(scene.primitives[0].rotation_z_deg,109)
        self.assertEqual(scene.primitives[0].size,Vec3(1.5,.7,.75))
        result[0].position=Point2D(100,100)
        with self.assertRaisesRegex(ValueError,"replan affected room"):
            compiler._compile_furniture(self.floor,GeometryScene("c","z_up"))


class MeshSupportProbeTests(unittest.TestCase):
    def test_probe_detects_hole_and_upper_slab(self):
        import numpy as np
        from scripts.annotate_interior_assets import check_surface
        slab=np.array([[[-.5,-.5,0],[.5,-.5,0],[.5,.5,0]],
                       [[-.5,-.5,0],[.5,.5,0],[-.5,.5,0]]])
        spec={"id":"top","kind":"top","center":[0,0,0],"size":[.8,.8]}
        self.assertEqual(check_surface(slab,(1,1,1),spec)["geometry_probe"]["samples"],169)
        with self.assertRaisesRegex(ValueError,"Unsupported patch"):
            check_surface(slab[:1],(1,1,1),spec)
        upper=slab+np.array([0,0,.2])
        with self.assertRaisesRegex(ValueError,"clearance too large"):
            check_surface(np.concatenate([slab,upper]),(1,1,1),{**spec,"clearance_m":.21})


if __name__=="__main__":unittest.main()
