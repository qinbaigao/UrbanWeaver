from copy import deepcopy
from dataclasses import asdict
import unittest

from cityg.schemas import (Bounds2D,Building,City,District,Door,Floor,Parcel,Point2D,
                          RoadNetwork,RoadSegment,Junction,Room,VerticalConnector)
from cityg.ccwp import build_world_program
from cityg.planning.transport_retrofit import plan_transport_retrofit
from cityg.geometry.slab_openings import subtract_openings,transport_slab_holes
from cityg.geometry import GeometryCompiler
from cityg.geometry.transport_retrofit import compile_transport_retrofit
from cityg.runtime.transport_readiness import audit_transport_readiness
from cityg.runtime.transport import Box


def fixture():
    floors=[]
    for level in range(2):
        fid=f'b_floor_{level:02d}';corridor=Room(fid+'_corridor','Hall','corridor',Bounds2D(5.8,0,8.7,40))
        rooms=[corridor];doors=[]
        for wing,(x0,x1) in enumerate(((0,5.8),(8.7,14.5))):
            for i in range(4):
                r=Room(fid+f'_wing{wing}_{i}','Room','office',Bounds2D(x0,i*10,x1,(i+1)*10))
                rooms.append(r);doors.append(Door(r.id+'_door',r.id,corridor.id,
                    Point2D(x1 if wing==0 else x0,i*10+5)))
        floors.append(Floor(fid,level,level*3.2,3.2,rooms,doors,metadata={'spatial_layout':{'status':'accepted'}}))
    b=Building('b','Building','commercial',Bounds2D(0,0,14.5,40),Point2D(7.25,40),floors,
        [VerticalConnector('b_stairs','stairs',Bounds2D(6.09,18.8,8.41,21.2),0,1,
            metadata={'stair_run_axis':'x'})])
    road=RoadSegment('road','j0','j1',(Point2D(-5,45),Point2D(45,45)))
    network=RoadNetwork([Junction('j0',Point2D(-5,45)),Junction('j1',Point2D(45,45))],[road])
    city=City('city','City',Bounds2D(-10,-10,50,50),network,
        [District('district','District','commercial',Bounds2D(-10,-10,50,50),
            [Parcel('parcel',Bounds2D(-5,-5,45,45),[b])])])
    city.world_program=build_world_program(city,producer='test',seed=0)
    return city


class RetrofitTests(unittest.TestCase):
    def test_authorization_and_locked_room_guards(self):
        city=fixture();before=asdict(city)
        with self.assertRaises(PermissionError):plan_transport_retrofit(city,{'b'})
        city.districts[0].parcels[0].buildings[0].floors[0].rooms[2].metadata['room_design']={'status':'accepted'}
        with self.assertRaisesRegex(ValueError,'furnished/locked'):plan_transport_retrofit(city,{'b'},authorized=True)
        self.assertEqual(city.districts[0].parcels[0].buildings[0].vertical_connectors[0].bounds,
                         Bounds2D(**before['districts'][0]['parcels'][0]['buildings'][0]['vertical_connectors'][0]['bounds']))

    def test_canonical_scope_preserves_rooms_exterior_stair_identity(self):
        city=fixture();before=asdict(city);adapted,r=plan_transport_retrofit(city,{'b'},authorized=True)
        b=next(adapted.iter_buildings());old=next(city.iter_buildings())
        self.assertEqual(asdict(city),before)
        self.assertEqual(b.footprint,old.footprint);self.assertEqual(b.entrance,old.entrance)
        self.assertEqual(b.vertical_connectors[0].id,old.vertical_connectors[0].id)
        self.assertEqual(len(r['buildings'][0]['changed_rooms']),4)
        self.assertEqual(len(list(adapted.iter_rooms())),len(list(city.iter_rooms()))+2)
        for f in b.floors:
            lobby=next(x for x in f.rooms if x.id.endswith('_transport_lobby'))
            self.assertTrue(all(lobby.bounds.contains_bounds(c.bounds) for c in b.vertical_connectors))
            self.assertFalse(any(c.bounds.overlaps_area(f.rooms[0].bounds) for c in b.vertical_connectors))

    def test_explicit_world_program_lock_is_not_overridden(self):
        city=fixture()
        node=next(n for n in city.world_program.nodes if n.entity_id=='b_floor_00_wing0_1')
        node.locked=True;before=asdict(city)
        with self.assertRaisesRegex(ValueError,'explicitly locked'):
            plan_transport_retrofit(city,{'b'},authorized=True)
        self.assertEqual(asdict(city),before)

    def test_empty_and_unsupported_floor_order_rejected(self):
        with self.assertRaisesRegex(ValueError,'At least one'):
            plan_transport_retrofit(fixture(),set(),authorized=True)
        city=fixture();next(city.iter_buildings()).floors.reverse()
        with self.assertRaisesRegex(ValueError,'contiguous, ordered'):
            plan_transport_retrofit(city,{'b'},authorized=True)

    def test_separate_openings_preserve_between_core_support(self):
        outer=Bounds2D(0,0,10,10);a=Bounds2D(1,3,3,5);b=Bounds2D(5,3,7,5)
        pieces=subtract_openings(outer,[a,b])
        self.assertAlmostEqual(sum(p.width*p.depth for p in pieces),92)
        self.assertTrue(any(p.contains_point(Point2D(4,4)) for p in pieces))
        self.assertTrue(all(not p.overlaps_area(a) and not p.overlaps_area(b) for p in pieces))
        city,_=plan_transport_retrofit(fixture(),{'b'},authorized=True);building=next(city.iter_buildings())
        self.assertEqual(len(transport_slab_holes(building,building.floors[0])),1)
        self.assertEqual(len(transport_slab_holes(building,building.floors[1])),2)

    def test_compilation_retains_exterior_and_moves_connector_navigation(self):
        city=fixture();before=GeometryCompiler().compile(city)
        adapted,receipt=plan_transport_retrofit(city,{'b'},authorized=True)
        scene=compile_transport_retrofit(adapted,before,receipt)
        exterior=lambda s:{p.id:asdict(p) for p in s.primitives if p.layer_id=='shell:b' and p.semantic_class not in ('floor_slab','collision_envelope')}
        self.assertEqual(exterior(before),exterior(scene))
        self.assertTrue(audit_transport_readiness(adapted,scene,['b'],Box('r',(0,0,.75),(.65,.8,1.5)))['ok'])
        edges=[e for e in scene.navigation.edges if e.traversal in ('stairs','elevator')]
        self.assertTrue(edges)
        self.assertTrue(all('transport_lobby' in e.start_node_id for e in edges))
        building=next(adapted.iter_buildings())
        for floor in building.floors:
            holes=transport_slab_holes(building,floor)
            plates=[p for p in scene.primitives if p.owner_id==floor.id and p.layer_id=='shell:b'
                    and p.semantic_class in ('floor_slab','collision_envelope') and p.size.z<.5]
            self.assertTrue(plates)
            for p in plates:
                bounds=Bounds2D(p.center.x-p.size.x/2,p.center.y-p.size.y/2,
                                p.center.x+p.size.x/2,p.center.y+p.size.y/2)
                self.assertFalse(any(bounds.overlaps_area(h) for h in holes))
                self.assertLessEqual(p.center.z+p.size.z/2,floor.elevation_m+1e-7)


if __name__=='__main__':unittest.main()
