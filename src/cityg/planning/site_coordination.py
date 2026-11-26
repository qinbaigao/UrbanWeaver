"""Bounded Room → Floor → Room negotiation during a building footprint edit."""
from dataclasses import replace
import json
import math

from cityg.planning.prototype_adaptation import door_side
from cityg.planning.room_envelope import metric_envelope
from cityg.services.interfaces import ChatMessage


class CapacityConflict(ValueError):
    def __init__(self, room_id, reason):
        self.room_id = room_id
        super().__init__(reason)


class FloorCapacityConflict(ValueError):
    """A permitted floor revision could not realize its fixed footprint."""
    def __init__(self, evidence, reason):
        self.evidence = {**evidence, 'floor_feedback': reason}
        super().__init__(reason)


def capacity(room, bounds):
    requirement = room.metadata.get('spatial_requirement') or {}
    if bounds.area > requirement.get('max_area_m2', math.inf) + 1e-5:
        raise ValueError(f'{room.id}: usable area exceeds its maximum area')
    if bounds.area < requirement.get('min_area_m2', 0) - 1e-5:
        raise CapacityConflict(room.id, f'{room.id}: usable area {bounds.area:.2f} m² violates {requirement}')


def partition_options(building, floor, receiver):
    """Transfer a strip across one full shared edge. Keep all door anchors."""
    options = []
    for donor in floor.rooms:
        if donor.id == receiver.id or donor.function == 'corridor' or receiver.function == 'corridor':
            continue
        for axis, tangent in (('x', 'y'), ('y', 'x')):
            a, b = receiver.bounds, donor.bounds
            if any(abs(getattr(a, k+'_'+tangent)-getattr(b, k+'_'+tangent)) > 1e-6
                   for k in ('min', 'max')):
                continue
            for side, other, sign in (('max', 'min', 1), ('min', 'max', -1)):
                edge, opposite = side+'_'+axis, other+'_'+axis
                if abs(getattr(a, edge)-getattr(b, opposite)) > 1e-6:
                    continue
                for fraction in (.08, .16, .24, .32):
                    delta = fraction * (b.width if axis == 'x' else b.depth)
                    boundary = getattr(a, edge) + sign * delta
                    revised = {receiver.id: replace(a, **{edge: boundary}),
                               donor.id: replace(b, **{opposite: boundary})}
                    realized_areas = []
                    pair = [replace(r, bounds=revised[r.id]) for r in (receiver, donor)]
                    trial = replace(floor, rooms=[replace(r, bounds=revised[r.id]) if r.id in revised else r
                                                  for r in floor.rooms])
                    try:
                        for room in pair:
                            env = metric_envelope(building, trial, room)
                            if env['status'] != 'supported':
                                raise ValueError('unsupported room')
                            capacity(room, env['bounds'])
                            realized_areas.append(env['bounds'].area)
                            for door in env['floor'].doors:
                                door_side(env['room'], door)
                    except ValueError:
                        continue
                    options.append(({'donor': donor.id, 'donor_function': donor.function,
                                     'axis': axis, 'shift_m': round(delta, 4),
                                     'receiver_area_m2': round(realized_areas[0], 3),
                                     'donor_area_m2': round(realized_areas[1], 3)}, revised))
    return sorted(options, key=lambda opt: opt[0]['shift_m'])


class SiteCoordination:
    def __init__(self, service, model_id):
        self.service = service
        self.model_id = model_id
        self.exchanges = []
        self.revised_floors = []

    def choice(self, role, task, evidence, options):
        schema = {'type': 'object', 'additionalProperties': False, 'required': ['action', 'reason'],
                  'properties': {'action': {'type': 'string', 'enum': list(options)},
                                 'reason': {'type': 'string', 'maxLength': 200}}}
        messages = [ChatMessage('system', f'You are the {role} in a constrained building edit. {task} '
                                'Select an available action. Return JSON with a concise factual reason.'),
                    ChatMessage('user', json.dumps({'evidence': evidence, 'actions': options}, ensure_ascii=False))]
        for attempt in range(2):
            raw = self.service.complete(messages, schema)
            try:
                reply = json.loads(raw)
                if reply['action'] not in options or not isinstance(reply['reason'], str):
                    raise ValueError('Unknown action or missing reason')
                break
            except (ValueError, KeyError, TypeError) as exc:
                if attempt:
                    raise ValueError(f'Invalid decision from {role} after two attempts') from exc
                messages.append(ChatMessage('user', 'Return only one valid JSON object. Keep the reason under 25 words.'))
        self.exchanges.append({'role': role, 'model': self.model_id, 'evidence': evidence,
                               'options': options, 'decision': reply})
        return reply['action']

    def revise(self, building, floor, conflict, refurnish):
        if len(self.revised_floors) >= 3:
            raise ValueError('Site edit exceeds the three-floor local replanning budget') from conflict
        room = next(r for r in floor.rooms if r.id == conflict.room_id)
        env = metric_envelope(building, floor, room)
        evidence = {'floor': floor.id, 'room': room.id, 'function': room.function,
                    'available_area_m2': round(env['area_m2'], 3), 'issue': str(conflict),
                    'requirement': room.metadata.get('spatial_requirement', {}),
                    'furniture': [o.category for o in floor.objects if o.room_id == room.id]}
        evidence['available_dimensions_m'] = [round(env['bounds'].width, 3), round(env['bounds'].depth, 3)]
        from cityg.planning.site_furniture import GroupCapacityError
        if isinstance(conflict.__cause__, GroupCapacityError):
            evidence['group_dimensions_m'] = list(conflict.__cause__.required)
            evidence['available_group_region_m'] = list(conflict.__cause__.available)
        action = self.choice('Room Agent', 'Preserve the room function and furniture. Request a floor revision '
                             'when its current size prevents the required layout.', evidence,
                             {'request_space': 'Ask Floor Agent for space', 'defer': 'Leave the edit unresolved'})
        if action == 'defer':
            raise ValueError('Room Agent deferred the site edit') from conflict
        options = partition_options(building, floor, room)[:12]
        original = {r.id: r.bounds for r in floor.rooms}
        last_failure = None
        for _ in range(3):
            actions = {str(i): row for i, (row, _) in enumerate(options)}
            actions['escalate'] = 'Return the dimensional conflict to the Building Agent if the available walls cannot resolve it'
            selected = self.choice('Floor Agent', 'Choose the least disruptive sufficient transfer. '
                                   'Doors, circulation, fixed building footprint and inventory must survive.',
                                   {**evidence, 'room_action': action, 'previous_failure': last_failure}, actions)
            if selected == 'escalate':
                break
            row, bounds = options.pop(int(selected))
            for r in floor.rooms:
                r.bounds = bounds.get(r.id, original[r.id])
            try:
                objects = refurnish()
            except CapacityConflict as exc:
                last_failure = str(exc)
                continue
            self.revised_floors.append(floor.id)
            self.exchanges.append({'from': 'Floor Agent', 'to': 'Room Agent', 'floor': floor.id,
                                   'room': room.id, 'revised_partition': row,
                                   'result': 'room_layout_realized', 'floor_object_count': len(objects)})
            return objects
        self.exchanges.append({'from': 'Floor Agent', 'to': 'Building Agent', 'issue': last_failure or str(conflict)})
        raise FloorCapacityConflict(evidence, f'{room.id}: no verified shared partition proposal; {last_failure or conflict}')


def site_options(city, building, request):
    """Clip the bounded aspect search to the site before offering any choice."""
    from cityg.planning.building_site import footprint_bounds, SiteLimits
    parcel = next(p for p in city.iter_parcels() if any(b.id == building.id for b in p.buildings))
    limits = SiteLimits(city, building, parcel)
    ratio = building.footprint.width / building.footprint.depth
    def bounds(value):
        return footprint_bounds(building, request['area_m2'], value, request)
    base_fits = not limits.violation(bounds(ratio))
    options = {}
    seen = {round(ratio, 6)}
    for i, factor in enumerate((.81, .91, 1.10, 1.23)):
        value = round(ratio * factor, 6)
        if not .25 <= value <= 4:
            continue
        if limits.violation(bounds(value)):
            if not base_fits:
                continue
            # Find a tested feasible alternative between the original aspect and
            # the rejected extreme. Never use an unchecked interpolated shape.
            good, bad = ratio, value
            for _ in range(20):
                mid = round((good + bad)/2, 6)
                if mid == good or mid == bad:
                    break
                if limits.violation(bounds(mid)):
                    bad = mid
                else:
                    good = mid
            value = good
        if round(value, 6) in seen:
            continue
        seen.add(round(value, 6))
        shape = bounds(value)
        options[str(i)] = {'aspect_ratio': value, 'width_m':round(shape.width, 3),
                           'depth_m':round(shape.depth, 3)}
    return options


def coordinated_edit(city, building_id, request, service, model_id, exterior_only, *, finish=None):
    from cityg.planning.building_site import adapt_building_site, SiteConstraintConflict, CompiledSiteConflict
    flex = request.pop('allow_aspect_adjustment', False)
    if flex and (type(request.get('area_m2')) not in (int, float) or
                 not math.isfinite(request['area_m2']) or request['area_m2'] <= 0):
        raise ValueError('Shape flexibility requires a finite positive area')
    if type(flex) is not bool or (flex and ('aspect_ratio' in request or 'area_m2' not in request)):
        raise ValueError('Shape flexibility requires an area target and no fixed aspect ratio')
    original = next(b for b in city.iter_buildings() if b.id == building_id)
    ratio = original.footprint.width / original.footprint.depth
    options = None
    protocol = SiteCoordination(service, model_id)
    attempt = dict(request)
    for turn in range(3):
        # Every building proposal starts from the unchanged source city.
        protocol.revised_floors = []
        try:
            result = adapt_building_site(city, building_id, attempt, exterior_only=exterior_only, coordination=protocol)
            if turn:
                protocol.exchanges.append({'from': 'Building Agent', 'to': 'Floor / Room planners',
                                           'accepted_aspect_ratio': attempt['aspect_ratio'],
                                           'result': 'reinstantiated_and_refurnished'})
            if flex:
                result.metadata['requested_shape_flexibility'] = True
                next(b for b in result.city.iter_buildings() if b.id == building_id).metadata[
                    'site_adaptation']['requested_shape_flexibility'] = True
            return finish(result) if finish else result

        except (FloorCapacityConflict, SiteConstraintConflict, CompiledSiteConflict) as conflict:
            if isinstance(conflict, CompiledSiteConflict) and turn and 'accepted_aspect_ratio' in protocol.exchanges[-1]:
                protocol.exchanges.pop()
            if not flex or turn == 2:
                raise
            if options is None:
                options = site_options(city, original, request)
            if not options:
                raise
            evidence = (conflict.evidence if isinstance(conflict, FloorCapacityConflict)
                        else {'rejected_candidate': str(conflict)})
            if not isinstance(conflict, FloorCapacityConflict):
                protocol.exchanges.append({'rejected_aspect_ratio': attempt.get('aspect_ratio', ratio),
                                           'reason': str(conflict)})
            previous_ratio = attempt.get('aspect_ratio', ratio)
            required = evidence.get('group_dimensions_m')
            choices = {}
            for key, option in options.items():
                projection = dict(option)
                if required:
                    scale = math.sqrt(option['aspect_ratio']/previous_ratio)
                    width, depth = evidence['available_dimensions_m']
                    available = evidence['available_group_region_m']
                    predicted = [available[0]+width*(scale-1), available[1]+depth*(1/scale-1)]
                    projection['estimated_group_region_m'] = [round(v, 3) for v in predicted]
                    if any(v < need-1e-6 for v, need in zip(predicted, required)):
                        continue
                choices[key] = projection
            # An alternative disproved by a measured dimension remains excluded on
            # subsequent attempts, even if the next failure is a circulation check.
            options = {key: options[key] for key in choices}
            if not choices:
                raise
            selected = protocol.choice('Building Agent',
                'The previous candidate failed its floor, site or compiled geometry check. Retain the exact area, '
                'choose a footprint with more span on the constrained axis, and resubmit it to the floor.',
                {**evidence, 'fixed_site_area_m2': request['area_m2'],
                 'failed_aspect_ratio': previous_ratio}, choices)
            attempt = {**request, 'aspect_ratio': options.pop(selected)['aspect_ratio']}
