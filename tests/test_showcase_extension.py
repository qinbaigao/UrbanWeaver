import json
import random
import unittest
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from extend_city_north_south import preserve_metro_ground_openings
from cityg.geometry.geography import polygon_mesh, primitive_footprint
from cityg.geometry.model import GeometryScene

from cityg.planning.showcase_extension import extend_showcase
from cityg.planning.programmed import ProgrammedCityPlanner
from cityg.planning.baseline import BaselineCityPlanner
from cityg.planning.programs import (HierarchicalProgram, UrbanProgram, BuildingProfile,
    BuildingProgram, FloorProfile, FloorProgram)
from cityg.polygons import box_shape, river_shape
from cityg.schemas import (Bounds2D, Bridge, City, CitySpec, District, Junction, Parcel,
    Point2D, River, RoadNetwork, RoadSegment)
from cityg.serialization import to_primitive
from cityg.subtree_transactions import _refresh_world_program
from cityg.validation import CityValidator


def fixture():
    functions=('residential','commercial','mixed_use','public_service')
    program=HierarchicalProgram(UrbanProgram(('zone_00',)),
        BuildingProgram(tuple(BuildingProfile(f,'minimum','west','residential_slab') for f in functions)),
        FloorProgram(tuple(FloorProfile(f,'double_loaded_corridor',.2,('office',)) for f in functions)))
    xs=[20,180,350,470,550,650,790,950,1100,1180]
    junctions=[Junction(f'j_{r}_{c}',Point2D(x,y)) for r,y in enumerate((10,990)) for c,x in enumerate(xs)]
    roads=[];bridges=[]
    for r in range(2):
        for c in range(9):
            a,b=junctions[r*10+c:r*10+c+2]
            road=RoadSegment(f'road_{r}_{c}',a.id,b.id,(a.position,b.position),width_m=8)
            roads.append(road)
            if c==4:bridges.append(Bridge(f'bridge_{r}',road.id,'river',22,78))
    for c in range(10):
        a,b=junctions[c],junctions[c+10]
        roads.append(RoadSegment(f'road_axis_{c}',a.id,b.id,(a.position,b.position),width_m=8))
    bounds=Bounds2D(192,40,320,150)
    building=ProgrammedCityPlanner(program)._make_building(CitySpec(min_floors=1,max_floors=1),
        random.Random(1),80,'residential',bounds,('west',))
    city=City('test_city','test',Bounds2D(-260,0,1540,1000),RoadNetwork(junctions,roads),
        [District('district_old','Old','residential',bounds,[Parcel('parcel_old',bounds,[building])])],
        metadata={'hierarchical_program':to_primitive(program),
            'interior_scope':{'policy':'prototype_exterior_only','building_levels':{}},
            'construction_sites':{'sites':[{'replaced_building_id':'building_100'}]}},
        rivers=[River('river','River',(Point2D(600,0),Point2D(600,1000)),width_m=36,bank_width_m=6,setback_m=10)],bridges=bridges)
    BaselineCityPlanner._resolve_street_orientations(city,CitySpec())
    return city


class ShowcaseExtensionTests(unittest.TestCase):
    def test_regenerated_base_keeps_metro_opening_and_new_backup_extent(self):
        bounds=Bounds2D(-10,-10,10,10)
        p=polygon_mesh('ground','city',box_shape(bounds),-.02,.18,'city_ground','city_ground')
        hole=[[1,1],[2,1],[2,3],[1,3],[1,1]]
        scene=GeometryScene('city','right_handed_z_up_meters',primitives=[p],
            metadata={'metro_entrances':{'entrances':[{'opening_polygon':hole}]},
                      'metro_ground_originals':[{'id':'ground','old_extent':True}]})
        self.assertEqual(len(preserve_metro_ground_openings(scene)),1)
        self.assertAlmostEqual(primitive_footprint(scene.primitives[0]).area,398)
        self.assertEqual(scene.metadata['metro_ground_originals'][0]['size'],{'x':20,'y':20,'z':.18})
        self.assertEqual(preserve_metro_ground_openings(scene),[])

    def test_square_preservation_connectivity_clearance_and_retired_ids(self):
        source=fixture();before=json.dumps(to_primitive(source),sort_keys=True)
        city,report=extend_showcase(source)
        self.assertEqual(json.dumps(to_primitive(source),sort_keys=True),before)
        self.assertEqual(city.bounds.width,city.bounds.depth)
        self.assertEqual(city.bounds.min_y,-400)
        self.assertEqual(city.districts[0],source.districts[0])
        self.assertEqual(len(report['added_buildings']),48)
        self.assertEqual(report['added_buildings'][0],'building_101')
        self.assertEqual(report['added_bridge_count'],6)
        self.assertTrue(all(p in city.rivers[0].centerline for p in source.rivers[0].centerline))
        original_ids={r.id for r in source.road_network.segments}
        self.assertEqual([r for r in city.road_network.segments if r.id in original_ids],source.road_network.segments)
        water=river_shape(city.rivers[0],'reserve')
        for district in city.districts[1:]:
            for parcel in district.parcels:
                self.assertTrue(box_shape(parcel.bounds).disjoint(water))
                self.assertTrue(parcel.buildings[0].metadata.get('roof_finish'))
        graph={j.id:set() for j in city.road_network.junctions}
        for road in city.road_network.segments:
            graph[road.start_junction_id].add(road.end_junction_id)
            graph[road.end_junction_id].add(road.start_junction_id)
        seen=set();todo=[next(iter(graph))]
        while todo:
            node=todo.pop()
            if node not in seen:seen.add(node);todo.extend(graph[node]-seen)
        self.assertEqual(seen,set(graph))
        _refresh_world_program(city,producer='test',changed_ids={city.id})
        validation=CityValidator().validate(city)
        self.assertTrue(validation.ok,validation.to_dict())

    def test_rejects_repeated_edit_and_wrong_river_without_mutation(self):
        source=fixture();source.metadata['north_south_extension']={}
        with self.assertRaisesRegex(ValueError,'already'):extend_showcase(source)
        source.metadata.pop('north_south_extension');source.rivers=[]
        with self.assertRaisesRegex(ValueError,'one central'):extend_showcase(source)


if __name__=='__main__':unittest.main()
