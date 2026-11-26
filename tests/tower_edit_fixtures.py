"""Furnished tower fixtures for editing and transaction regression tests."""
import json

from cityg.ccwp import build_world_program
from cityg.editing import _apply_replans
from cityg.geometry import GeometryCompiler, GeometryValidator
from cityg.planning.baseline import ROOM_FUNCTIONS
from cityg.planning.generation_prototypes import DeferredFurniture
from cityg.planning.programmed import ProgrammedCityPlanner
from cityg.planning.programs import (BuildingProfile, BuildingProgram, FloorProfile, FloorProgram,
                                     HierarchicalProgram, UrbanProgram)
from cityg.planning.room_envelope import metric_envelope
from cityg.planning.room_metric_frame import bind_metric_object
from cityg.schemas import CitySpec, InteriorObject, Point2D, ZoneSpec
from cityg.transactions import fingerprint


def fixture(case):
    spec = CitySpec(width_m=180, depth_m=160, building_count=4, min_floors=12, max_floors=12,
                    rooms_per_floor=6, room_count_strategy='fixed', layout_style='regular_grid',
                    road_pattern='connected_grid', zones=(ZoneSpec('Offices', 'commercial', 1),))
    program = HierarchicalProgram(UrbanProgram(('zone_00',), spec.road_pattern, 'row_major'),
        BuildingProgram((BuildingProfile('commercial', 'seeded_uniform', 'west', 'commercial_tower'),)),
        FloorProgram((FloorProfile('commercial', 'double_loaded_corridor', .18, tuple(ROOM_FUNCTIONS['commercial'])),)))
    city = ProgrammedCityPlanner(program, floor_detail_agent=DeferredFurniture()).plan(spec)
    building = next(city.iter_buildings())
    city.metadata['interior_scope'] = {'building_levels': {building.id: [0, 1, 2]}}
    floor = building.floors[2]
    room = next(r for r in floor.rooms if r.function == 'meeting_room')
    if case == 'conference_depth':
        door = next(d for d in floor.doors if room.id in (d.room_a_id, d.room_b_id))
        door.position = Point2D(room.bounds.min_x + .19*room.bounds.width, door.position.y)
    env = metric_envelope(building, floor, room)
    center = env['bounds'].center
    if case == 'meeting_area':
        room.metadata['spatial_requirement'] = {'min_area_m2': 60}
        items = [('meeting_table', 0, 0, 3., 1.1, .75)]
        items.extend(('meeting_chair', x, y, .5, .5, .9) for x in (-1., 0, 1.) for y in (-1., 1.))
    else:
        # Fixed longitudinal conference suite with ten seats along the sides.
        items = [('meeting_table', 0, y, 1.25, 3.5, .75) for y in (-1.78, 1.78)]
        items.extend(('meeting_chair', x, y, .5, .5, .9)
                     for x in (-1.1, 1.1) for y in (-2.8, -1.4, 0, 1.4, 2.8))
    room.metadata['room_design'] = {'status': 'accepted'}
    if case == 'conference_depth':
        center = Point2D(center.x, center.y + .25)
    for i, (category, x, y, width, depth, height) in enumerate(items):
        obj = InteriorObject(f'{room.id}_seat_group_{i}', room.id, category, 'procedural::'+category,
                             Point2D(center.x+x, center.y+y), width, depth, height,
                             metadata={'group_key': 'conference_suite'})
        obj.metadata.update(group_id='conference_suite', front_axis='-Y')
        if category == 'meeting_chair':
            if case == 'meeting_area':
                obj.rotation_deg = 0 if y > 0 else 180
            else:
                obj.rotation_deg = 270 if x > 0 else 90
        bind_metric_object(obj, building, floor, room, env)
        room.object_ids.append(obj.id)
        floor.objects.append(obj)
    city.world_program = build_world_program(city, producer='controlled_edit_case', seed=spec.seed)
    return city, building, floor, room


def run(case, service, model):
    city, building, floor, room = fixture(case)
    compiler = GeometryCompiler()
    from cityg.planning.room_constraints import circulation_check
    from cityg.planning.interiors import FloorDetailAgent
    zones = FloorDetailAgent()._door_clearance_zones(floor, room)[0]
    assert not any(o.bounds.overlaps_area(z) for o in floor.objects for z in zones)
    source_access = circulation_check(floor.objects, room, floor, room.bounds)
    assert source_access['ok'], source_access
    source = fingerprint(city)
    assert GeometryValidator().validate(city, compiler.compile(city)).ok
    area = building.footprint.area * .8
    details = {'area_m2': area}
    if case == 'conference_depth':
        details['allow_aspect_adjustment'] = True
    result, _, traces = _apply_replans(city, [{'kind':'building_site', 'target_id':building.id,
                                     'details':json.dumps(details)}], service, model_id=model,
                                     asset_resolver=None, room_compiler=compiler)
    target = next(b for b in result.iter_buildings() if b.id == building.id)
    updated = next(f for f in target.floors if f.id == floor.id)
    new_room = next(r for r in updated.rooms if r.id == room.id)
    trace = traces[0]
    gate = trace['transaction']['compiled_gate']
    assert fingerprint(city) == source and abs(target.footprint.area-area) < 1e-6
    assert set(room.object_ids) == set(new_room.object_ids)
    assert trace['transaction']['status'] == 'accepted' and floor.id in gate['compiled_access_floors']
    coordination = trace['metadata']['coordination']
    assert (floor.id in coordination['revised_floors'] if case == 'meeting_area' else
            any(e.get('role') == 'Building Agent' for e in coordination['exchanges']))
    return trace['transaction']['status']
