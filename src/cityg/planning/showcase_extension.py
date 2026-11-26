"""Additive north/south districts for the curated central-river showcase.

This is an explicit scene edit, not a general autonomous city expansion agent.
Existing entities stay in place; new IDs never reuse retired building IDs.
"""
from copy import deepcopy
from dataclasses import replace
import math
import random

from cityg.paths import PlanarPath2D
from cityg.planning.appearance import appearance_program_for_city
from cityg.planning.baseline import BaselineCityPlanner
from cityg.planning.heights import HeightDecision
from cityg.planning.programmed import ProgrammedCityPlanner
from cityg.planning.programs import BuildingProgram, FloorProgram, HierarchicalProgram, UrbanProgram
from cityg.geometry.roof_finishes import assign_roof_finishes
from cityg.polygons import box_shape, line_intervals, rings, river_shape
from cityg.schemas import Bounds2D, Bridge, CitySpec, District, Junction, Parcel, Point2D, RoadSegment
from cityg.serialization import to_primitive


KEY = 'north_south_extension'


def extend_showcase(city, seed=20261016):
    """Plan on a copy, returning (city, audit); never mutate the input on failure."""
    if KEY in city.metadata:
        raise ValueError('This scene already has a north/south extension')
    if len(city.rivers) != 1:
        raise ValueError('This curated edit expects one central north/south river')
    old = city.bounds
    extra = (old.width-old.depth)/2
    if extra < 160:
        raise ValueError('Not enough north/south space for two additional block rows')
    river = city.rivers[0]
    if abs(river.centerline[0].y-old.min_y) > .01 or abs(river.centerline[-1].y-old.max_y) > .01:
        raise ValueError('River must already span the original north/south bounds')
    boundaries = {}
    for side, y in [('south', old.min_y), ('north', old.max_y)]:
        anchors = sorted((j for j in city.road_network.junctions if abs(j.position.y-y)<12), key=lambda j:j.position.x)
        if len(anchors)<4 or max(j.position.y for j in anchors)-min(j.position.y for j in anchors)>.01:
            raise ValueError('Expected aligned existing boundary junctions')
        boundaries[side] = anchors
    city = deepcopy(city)
    city.bounds = Bounds2D(old.min_x, old.min_y-extra, old.max_x, old.max_y+extra)
    # Preserve every original river sample. A bounded continuation matches the
    # original tangent approximately without bending the surrounding road grid.
    step_count = math.ceil(extra/3)
    south = [Point2D(river.centerline[0].x+18*math.sin(-extra*i/step_count/106),
                     old.min_y-extra*i/step_count) for i in range(step_count,0,-1)]
    north = [Point2D(river.centerline[-1].x+18*math.sin(extra*i/step_count/106),
                     old.max_y+extra*i/step_count) for i in range(1,step_count+1)]
    city.rivers = [replace(river, centerline=tuple(south)+river.centerline+tuple(north))]
    river = city.rivers[0]
    raw = city.metadata['hierarchical_program']
    program = HierarchicalProgram(UrbanProgram.from_dict(raw['urban']),
        BuildingProgram.from_dict(raw['building']), FloorProgram.from_dict(raw['floor']))
    planner = ProgrammedCityPlanner(program, appearance_program=appearance_program_for_city(city))
    spec = CitySpec(width_m=old.width,depth_m=old.width,min_floors=3,max_floors=16,
        seed=seed,rooms_per_floor=4,architecture=deepcopy(city.metadata.get('architecture',{})))
    reserved = [b.id for b in city.iter_buildings()]
    reserved += [r['replaced_building_id'] for r in city.metadata.get('construction_sites',{}).get('sites',[])]
    index = max(int(b.rsplit('_',1)[1]) for b in reserved if b.startswith('building_'))+1
    added_roads, added_junctions, added_buildings, added_districts, connections = [], [], [], [], []

    def junction(name,x,y):
        item=Junction('junction_ns_'+name,Point2D(x,y));city.road_network.junctions.append(item)
        added_junctions.append(item.id);return item

    def road(name,a,b,collector=False):
        item=RoadSegment('road_ns_'+name,a.id,b.id,(a.position,b.position),
            road_class='collector' if collector else 'local',lane_count=3 if collector else 2,
            width_m=13.5 if collector else 8.0,sidewalk_width_m=3 if collector else 2.5,
            speed_limit_kph=30 if collector else 20,parking_allowed=not collector,bike_lane=collector)
        city.road_network.segments.append(item);added_roads.append(item.id)
        intervals=line_intervals(PlanarPath2D(item.centerline),river_shape(river,'banks').buffer(4))
        if intervals:
            if len(intervals)!=1 or intervals[0][0]<8 or PlanarPath2D(item.centerline).length-intervals[0][1]<8:
                raise ValueError('River crossing has insufficient dry approaches')
            lo,hi=intervals[0]
            city.bridges.append(Bridge('bridge_ns_'+name,item.id,river.id,lo,hi))
        return item

    for side in ('south','north'):
        anchors=boundaries[side]
        original_river_x=city.rivers[0].centerline[len(south)].x
        # Preserve dry-side axes, widening only the bank-road reservation.
        xs=[j.position.x for j in anchors]
        bank_w=max(i for i,x in enumerate(xs) if x<original_river_x)
        bank_e=bank_w+1
        xs[bank_w]=original_river_x-76;xs[bank_e]=original_river_x+79
        xs=[old.min_x+22,(old.min_x+xs[0])/2,*xs,(xs[-1]+old.max_x)/2,old.max_x-22]
        ys=([old.min_y-25,old.min_y-extra*.52,old.min_y-extra+25] if side=='south' else
            [old.max_y+25,old.max_y+extra*.54,old.max_y+extra-25])
        grid=[[junction(f'{side}_{r}_{c}',x,y) for c,x in enumerate(xs)] for r,y in enumerate(ys)]
        for r,row in enumerate(grid):
            for c,(a,b) in enumerate(zip(row,row[1:])):
                road(f'{side}_cross_{r}_{c}',a,b,collector=(r==1))
        for r in range(2):
            for c in range(len(xs)):
                road(f'{side}_axis_{r}_{c}',grid[r][c],grid[r+1][c],collector=(c%4==2))
        for i,anchor in enumerate(anchors):
            road(f'{side}_join_{i}',anchor,grid[0][i+2])
            connections.append(anchor.id)
        district=District('district_ns_'+side,side.title()+' urban extension','mixed_use',
            Bounds2D(xs[0],min(ys),xs[-1],max(ys)))
        for r in range(2):
            for c in range(len(xs)-1):
                if c==bank_w+2:continue  # keep the complete river corridor open
                bounds=Bounds2D(xs[c]+14,min(ys[r:r+2])+14,xs[c+1]-14,max(ys[r:r+2])-14)
                rng=random.Random(f'{seed}:{side}:{r}:{c}')
                function=('residential','commercial','mixed_use','public_service')[(c+2*r+(side=='north'))%4]
                if bounds.width<65:function='residential'
                floors=rng.randint(4,9) if function=='residential' else rng.randint(6,13)
                if function=='public_service':floors=rng.randint(3,5)
                if function=='commercial' and r==0 and bounds.width>90:floors=rng.randint(12,16)
                decision=HeightDecision(index,function,'urban_extension','highrise' if floors>=10 else 'midrise',
                    floors,floors,floors,.55 if r==0 else .3,source='curated_square_extension',highrise=floors>=10)
                building=planner._make_building(spec,rng,index,function,bounds,('south','north','east','west'),
                    f'block_ns_{side}_{r}_{c}',height_decision=decision)
                building.metadata['north_south_extension']=side
                if index%5!=0:
                    building.metadata['facade_colorway']=('pearl_gray','cool_gray','muted_sage','slate_blue')[index%4]
                boundary,holes=rings(box_shape(bounds))
                district.parcels.append(Parcel(f'parcel_ns_{side}_{r}_{c}',bounds,[building],boundary,holes))
                added_buildings.append(building.id);index+=1
        city.districts.append(district);added_districts.append(district.id)
    # Align only new buildings; do not rewrite old orientation contracts.
    subset=replace(city,districts=[d for d in city.districts if d.id in added_districts],metadata=deepcopy(city.metadata))
    BaselineCityPlanner._resolve_street_orientations(subset,spec)
    assign_roof_finishes(subset)
    report={'version':'square_district_extension_v1','old_bounds':to_primitive(old),
        'new_bounds':to_primitive(city.bounds),'added_buildings':added_buildings,'added_districts':added_districts,
        'added_roads':added_roads,'added_junctions':added_junctions,'connected_existing_junctions':connections,
        'added_bridge_count':sum(b.id.startswith('bridge_ns_') for b in city.bridges),
        'source_agent_program_reused':True,'llm_called':False,'interiors_compiled':False}
    city.metadata[KEY]=report
    city.metadata['requested_buildings']=len(list(city.iter_buildings()))
    city.metadata.setdefault('geography',{}).update(bridge_count=len(city.bridges))
    return city,report
