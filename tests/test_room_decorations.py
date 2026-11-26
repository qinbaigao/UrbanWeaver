from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from hashlib import sha256
import json
import tempfile
import unittest
from unittest.mock import patch

from cityg.assets import AssetRegistry, AssetRecord
from cityg.geometry import GeometryCompiler
from cityg.geometry.model import GeometryScene, Vec3
from cityg.geometry.room_decorations import compile_room_decorations, box_bounds
from cityg.planning.room_decorations import validate_decorations
from cityg.planning.prototype_lab import make_lab
from cityg.planning.prototypes import LayoutPrototypeLibrary
from cityg.planning.prototype_decor_assets import add_review_decorations
from cityg.planning.room_envelope import metric_envelope
from cityg.schemas import InteriorObject, Point2D


class RoomDecorationTests(unittest.TestCase):
    def setUp(self):
        library = LayoutPrototypeLibrary(Path(__file__).resolve().parents[1]/'configs/layout_prototypes/v1')
        self.city, targets = make_lab(library,['bedroom_double_v1'])
        _,self.building,self.floor,self.room=targets[0]
        self.bounds=metric_envelope(self.building,self.floor,self.room)['bounds']
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.path=Path(temporary.name)/'fixture.glb';self.path.write_bytes(b'geometry not decoded by compiler')
        self.registry=AssetRegistry()
        for key,kind,size in [('art','wall',(.03,.8,.6)),('rug','floor_overlay',(2,1.5,.01)),('plant','floor',(.5,.5,.8))]:
            self.registry.register(AssetRecord(key,key,geometry_path=str(self.path),environment='indoor',
                room_types=('bedroom',),dimensions_m=size,metadata={'placement_kind':kind,
                'decoration_review_version':1,'orientation':{'canonical_forward_axis':'+X'}}))
        self.compiler=GeometryCompiler(asset_registry=self.registry)
        self.scene=GeometryScene('fixture','z_up')
        self.room.metadata['room_decorations']=[]

    def compile(self,requests):
        self.room.metadata['room_decorations']=requests
        compile_room_decorations(self.compiler,self.building,self.floor,self.room,self.scene)
        return self.scene.metadata.get('room_decorations',{}).get(self.room.id,{})

    def wall(self):
        b=self.bounds
        p=self.compiler._box('solid_wall',self.floor.id,Vec3(b.center.x,b.max_y-.06,1.6),
            Vec3(b.width,.12,3.2),0,'interior_wall','wall',f'floor:{self.floor.id}',
            metadata={'room_ids':[self.room.id],'wall_role':'room_exterior_boundary','viewer_room_only':True})
        self.scene.primitives.append(p)
        return p

    def test_wall_art_faces_inward_and_stays_with_its_room_and_wall(self):
        wall=self.wall()
        report=self.compile([{'id':'art','kind':'wall_asset','asset_id':'art','walls':['north']}])
        self.assertEqual(report['placed'],1)
        p=self.scene.primitives[-1]
        self.assertAlmostEqual(p.rotation_z_deg,-90)
        self.assertLess(p.center.y,wall.center.y-wall.size.y/2)
        self.assertEqual(p.metadata['support_primitive_id'],wall.id)
        self.assertTrue(p.metadata['viewer_room_only'])
        self.assertEqual(p.owner_id,self.room.id)
        self.assertTrue(self.bounds.contains_bounds(box_bounds(p)))

    def test_art_never_spans_door_header_or_missing_wall(self):
        wall=self.wall();wall.metadata['wall_role']='door_header'
        report=self.compile([{'id':'art','kind':'wall_asset','asset_id':'art','walls':['north']}])
        self.assertEqual(report['placed'],0)
        self.assertEqual(len(report['skipped']),1)

    def test_rug_allows_anchor_overlap_but_is_not_a_collision_obstacle(self):
        b=self.bounds
        obj=InteriorObject('bed',self.room.id,'bed','bed',b.center,1.5,2,.8,
            metadata={'design_member_id':'bed','metric_room_placement':{
                'center':[b.center.x,b.center.y],'dimensions_m':[1.5,2,.8]}})
        self.floor.objects=[obj]
        self.scene.primitives.append(self.compiler._box('bed_mesh','bed',Vec3(b.center.x,b.center.y,.4),
            Vec3(1.5,2,.8),0,'furniture_bed','wood',f'floor:{self.floor.id}'))
        report=self.compile([{'id':'rug','kind':'rug','asset_id':'rug','anchor_member_id':'bed'}])
        self.assertEqual(report['placed'],1)
        p=self.scene.primitives[-1]
        self.assertFalse(p.collision_enabled)
        self.assertTrue(p.metadata['floor_overlay'])
        self.assertAlmostEqual(p.center.z+p.size.z/2,self.floor.elevation_m+.002)
        self.assertTrue(self.bounds.contains_bounds(box_bounds(p)))

    def test_floor_asset_cannot_bypass_circulation_failure(self):
        with patch('cityg.geometry.room_decorations.circulation_check',return_value={'ok':False}) as check:
            report=self.compile([{'id':'plant','kind':'floor_asset','asset_id':'plant','walls':['north']}])
        self.assertTrue(check.called)
        self.assertEqual(report['placed'],0)
        self.assertFalse(self.scene.primitives)

    def test_floor_decor_cannot_enter_reserved_open_space_even_when_reachable(self):
        self.room.metadata['room_design']={'reserved_areas':[{
            'id':'clear','purpose':'reserved circulation','bounds_uv':[0,0,1,1],'min_width_m':1}]}
        with patch('cityg.geometry.room_decorations.circulation_check',return_value={'ok':True}):
            report=self.compile([{'id':'plant','kind':'floor_asset','asset_id':'plant','walls':['north']}])
        self.assertEqual(report['placed'],0)
        self.assertFalse(self.scene.primitives)

    def test_unreviewed_or_missing_assets_are_not_replaced_by_proxy(self):
        self.registry.register(replace(self.registry.get('art'),metadata={}),overwrite=True)
        with self.assertRaisesRegex(ValueError,'unreviewed'):
            self.compile([{'id':'art','kind':'wall_asset','asset_id':'art','walls':['north']}])

    def test_schema_and_opt_in(self):
        self.assertFalse(self.compile([]))
        q={'id':'plant','kind':'floor_asset','asset_id':'plant','walls':['north']}
        for requests in ([q,q],[{**q,'walls':['ceiling']}],[{**q,'kind':'window'}],[q]*13):
            with self.assertRaises(ValueError):validate_decorations(requests)

    def test_rotated_building_preserves_rug_containment(self):
        # A local metric pose must rotate once with the building, not twice.
        self.building.metadata['orientation_deg']=30
        b=self.bounds
        self.floor.objects=[InteriorObject('anchor',self.room.id,'coffee_table','table',b.center,1,1,.5,
            metadata={'design_member_id':'anchor','metric_room_placement':{
                'center':[b.center.x,b.center.y],'dimensions_m':[1,1,.5]}})]
        report=self.compile([{'id':'rug','kind':'rug','asset_id':'rug','anchor_member_id':'anchor'}])
        self.assertEqual(report['placed'],1)
        self.assertAlmostEqual(self.scene.primitives[-1].rotation_z_deg,30)

    def test_trial_asset_annotations_do_not_modify_source_registry(self):
        root=self.path.parent
        source=AssetRegistry(root/'source.json')
        source.register(AssetRecord('source_plant','small_plant',geometry_path=str(self.path),
            dimensions_m=(.2,.2,.4),metadata={'runtime_enabled':False,'mesh_validation':{'triangle_count':10}}))
        before=(root/'source.json').read_bytes()
        annotations={'schema_version':1,'assets':[{'id':'trial_plant','registry':'source.json',
            'source_id':'source_plant','sha256':sha256(self.path.read_bytes()).hexdigest(),
            'category':'floor_plant','placement_kind':'floor','scale':2,'front_axis':'+X',
            'room_types':['bedroom'],'evidence':'fixture orientation evidence'}]}
        path=root/'annotations.json';path.write_text(json.dumps(annotations))
        registry=AssetRegistry()
        add_review_decorations(registry,path,project_root=root)
        self.assertEqual(registry.get('trial_plant').dimensions_m,(.4,.4,.8))
        self.assertEqual((root/'source.json').read_bytes(),before)
        self.assertFalse(source.get('source_plant').metadata['runtime_enabled'])
        self.assertTrue(registry.get('trial_plant').metadata['prototype_review_only'])
        with self.assertRaisesRegex(ValueError,'overwrite'):
            add_review_decorations(registry,path,project_root=root)
        self.path.write_bytes(b'changed geometry')
        with self.assertRaisesRegex(ValueError,'changed or missing'):
            add_review_decorations(AssetRegistry(),path,project_root=root)

    def test_trial_loader_cannot_write_to_production_registry(self):
        with self.assertRaisesRegex(ValueError,'detached'):
            add_review_decorations(AssetRegistry(self.path.parent/'registry.json'),
                                  self.path.parent/'unused.json',project_root=self.path.parent)

    def test_unselected_expansion_assets_do_not_require_downloaded_geometry(self):
        path=self.path.parent/'annotations.json'
        path.write_text(json.dumps({'schema_version':1,'assets':[
            {'id':'unselected','registry':'not_downloaded.json'}]}))
        registry=AssetRegistry()
        add_review_decorations(registry,path,project_root=self.path.parent,asset_ids=set())
        self.assertFalse(registry.list_all())


if __name__=='__main__':unittest.main()
