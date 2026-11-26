"""Run paired, controlled editing cases against a real OpenAI-compatible service."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path

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
from cityg.services.interfaces import ModelEndpoint
from cityg.services.openai_compatible import OpenAICompatibleService
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


def plot_case(path, floor, updated, room, case):
    """Draw selected rooms in their actual metric frame at one common scale."""
    from xml.etree.ElementTree import Element, ElementTree, SubElement

    svg = Element('svg', xmlns='http://www.w3.org/2000/svg', width='1100', height='258',
                  viewBox='0 0 1100 258')
    def draw(tag, **attrs):
        return SubElement(svg, tag, {k.replace('_', '-'): str(v) for k, v in attrs.items()})
    def label(x, y, value, size=14, color='#253b51'):
        draw('text', x=x, y=y, font_family='sans-serif', font_size=size, fill=color).text = value

    draw('rect', width=1100, height=258, fill='white')
    title = 'Reallocate floor area' if case == 'meeting_area' else 'Change tower proportions at fixed site area'
    label(18, 26, title, 21)
    neighbor = next(r for r in floor.rooms if r.function == 'break_room')
    ids = {room.id, neighbor.id}
    for index, stage in enumerate(('Original', 'Fixed-ratio proposal', 'Accepted edit')):
        level = updated if index == 2 else floor
        origin = next(r.bounds for r in level.rooms if r.id == room.id)
        scale = .8 ** .5 if index == 1 else 1
        left = 18 + index*365
        def x(value):
            return left + (value-origin.min_x)*scale*18
        def y(value):
            return 210 - (value-origin.min_y)*scale*18
        def rect(bounds, color):
            draw('rect', x=x(bounds.min_x), y=y(bounds.max_y), width=bounds.width*scale*18,
                 height=bounds.depth*scale*18, fill=color, stroke='#435263', stroke_width=1)
        label(left, 55, stage, 17)
        for cell in level.rooms:
            if cell.id in ids:
                rect(cell.bounds, '#e8f0f7' if cell.id == room.id else '#edf1e9')
        for door in level.doors:
            if ids.intersection((door.room_a_id, door.room_b_id)):
                px, py = x(door.position.x), y(door.position.y)
                draw('line', x1=px-door.width_m*9, x2=px+door.width_m*9, y1=py, y2=py,
                     stroke='#127871', stroke_width=4)
        if index != 1:
            for obj in level.objects:
                if obj.room_id == room.id:
                    rect(obj.bounds, '#4879a1' if obj.category == 'meeting_chair' else '#d6ab78')
        else:
            label(left+6, 140, '52.03 m² available' if case == 'meeting_area' else '6.76 m available', 12, '#933b2e')
            label(left+6, 159, '60 m² required' if case == 'meeting_area' else '7.06 m required', 12, '#933b2e')
        caption = ('Meeting room and adjacent break room' if index == 0 else
                   'Proposed rooms before refurnishing' if index == 1 else
                   f'{sum(o.room_id == room.id for o in level.objects)} existing objects retained')
        label(left, 238, caption, 13)
    ElementTree(svg).write(path, encoding='utf-8', xml_declaration=True)


class RecordedDecisions:
    def __init__(self, record):
        self.decisions = iter(e for e in record['coordination']['exchanges'] if 'decision' in e)

    def complete(self, messages, schema):
        row = next(self.decisions)
        supplied = json.loads(messages[1].content)
        if supplied['actions'] != row['options'] or supplied['evidence'] != row['evidence']:
            raise ValueError('Recorded proposal differs from the live solver inputs')
        return json.dumps(row['decision'])


def run(case, service, model, figure_path=None):
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
    if figure_path is not None:
        plot_case(figure_path, floor, updated, room, case)
    return {'case':case, 'source':'controlled programmed tower with placed furniture', 'building_id':building.id,
            'floors':len(building.floors), 'floor':floor.level, 'room_id':room.id,
            'room_area_before_m2':room.bounds.area, 'room_area_after_m2':new_room.bounds.area,
            'objects_retained':len(new_room.object_ids), 'before_footprint':asdict(building.footprint),
            'after_footprint':asdict(target.footprint), 'requested':details, 'coordination':coordination,
            'compiled_furniture_primitives':gate['checked_furniture_primitives'],
            'geometry_ok':gate['geometry']['ok'], 'compiled_access_floors':gate['compiled_access_floors'],
            'room_checks_ok':gate['room_retention']['ok'], 'transaction':trace['transaction']['status'],
            'source_preserved':True, 'model':model}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--base-url')
    mode.add_argument('--replay', type=Path, help='Directory of recorded model decisions')
    parser.add_argument('--model', default='cityg-llm')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    service = None if args.replay else OpenAICompatibleService(ModelEndpoint(args.base_url, args.model, temperature=0, max_tokens=768))
    args.output.mkdir(parents=True, exist_ok=True)
    for case in ('meeting_area', 'conference_depth'):
        if args.replay:
            stored = json.loads((args.replay / (case+'.json')).read_text())
            service = RecordedDecisions(stored)
        report = run(case, service, args.model, args.output / (case+'.svg'))
        if args.replay:
            # Centred box subtraction and analytical extents can differ by an ulp.
            actual_area = report['room_area_after_m2']
            expected_area = stored['room_area_after_m2']
            assert abs(actual_area - expected_area) < 1e-8
            assert {**report, 'room_area_after_m2': expected_area} == stored
            assert next(service.decisions, None) is None
            print(case, 'replayed and verified', flush=True)
            continue
        (args.output / (case+'.json')).write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
        print(case, report['transaction'], report['objects_retained'], flush=True)
