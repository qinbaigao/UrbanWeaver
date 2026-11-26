"""Agent-authored urban relations with independently measurable semantics.

Distances are planar distances from building centres (not walking distances).
Hard requirements never disappear on bounded-search failure. Soft thresholds
are explicit design interpretations, not invented user limits.
"""
import math


class UrbanPlanningConflict(ValueError):
    def __init__(self, message, report=None):
        super().__init__(message)
        self.report = report or {}


RELATIONS = ('north_half', 'south_half', 'east_half', 'west_half',
             'near', 'far', 'served_by', 'min_footprint_area')


def response_schema():
    selector = {'type': 'string', 'pattern': '^(zone|function|building):.+$', 'description':
        'Exact selector: zone:<exact zone name>, function:<function>, building:<existing ID>, river, or road. '
        'Named facilities such as schools use separate named zones with the correct broad function.'}
    props = {'id': {'type': 'string'}, 'source_quote': {'type': 'string'},
             'subject': selector, 'relation': {'type': 'string', 'enum': list(RELATIONS)},
             'target': {'type': ['string', 'null'],
                        'pattern': '^((zone|function|building):.+|river|road)$'},
             'threshold': {'type': ['number', 'null'], 'minimum': 0},
             'strength': {'type': 'string', 'enum': ['hard', 'soft']},
             'reason': {'type': 'string'}}
    return {'type': 'array', 'maxItems': 20, 'items': {'type': 'object',
        'additionalProperties': False, 'properties': props, 'required': list(props)}}


def validate(rows, *, spec=None, instruction=None):
    if not isinstance(rows, (list, tuple)) or len(rows) > 20:
        raise ValueError('urban_requirements must contain at most 20 relations')
    seen = set()
    for r in rows:
        if not isinstance(r, dict) or set(r) != set(response_schema()['items']['properties']):
            raise ValueError('Invalid urban relation fields')
        if not isinstance(r['id'], str) or not r['id'] or r['id'] in seen:
            raise ValueError('Urban relation IDs must be nonempty and unique')
        seen.add(r['id'])
        if r['relation'] not in RELATIONS or r['strength'] not in ('hard', 'soft'):
            raise ValueError('Unsupported urban relation or strength')
        if any(not isinstance(r[k], str) or not r[k].strip() for k in ('source_quote', 'reason')):
            raise ValueError('Urban relations need source quotation and interpretation')
        if instruction is not None and r['source_quote'] not in instruction:
            raise ValueError('Urban relation must quote the original instruction exactly')
        if r['relation'].endswith('_half'):
            if r['threshold'] is not None or r['target'] is not None:
                raise ValueError('Half-plane relations use null threshold and target')
        else:
            v = r['threshold']
            if type(v) not in (int, float) or not math.isfinite(v) or v <= 0:
                raise ValueError(f"Urban relation {r['id']!r} ({r['relation']}) needs a positive numeric "
                    'distance/area threshold. River geometry belongs in river_width_m, river_bank_width_m, '
                    'river_setback_m, not a served_by relation; omit such redundant geometry-only rows.')
            if r['relation'] == 'min_footprint_area' and r['target'] is not None:
                raise ValueError('Footprint capacity uses null target')
            if r['relation'] in ('near', 'far', 'served_by') and r['target'] is None:
                raise ValueError('Distance relations require a target selector')
        for key in ('subject', 'target'):
            selector = r[key]
            if selector is None and key == 'target': continue
            if not isinstance(selector, str): raise ValueError('Selectors must be strings')
            if key == 'target' and selector in ('river', 'road'):
                if spec is not None and selector == 'river' and spec.river_mode == 'none':
                    raise ValueError('River relation requires a river')
                continue
            if ':' not in selector: raise ValueError('Use zone:, function:, or building: selector')
            kind, name = selector.split(':', 1)
            if kind not in ('zone', 'function', 'building') or not name:
                raise ValueError('Invalid urban selector')
            if spec is not None:
                if kind == 'zone' and sum(z.name == name for z in spec.zones) != 1:
                    raise ValueError('Zone selector must identify exactly one named zone')
                if kind == 'function' and not any(z.function == name for z in spec.zones):
                    raise ValueError('Unknown function selector')


def matches(entity, selector):
    kind, value = selector.split(':', 1)
    return entity.get({'building': 'id', 'zone': 'zone', 'function': 'function'}[kind]) == value


def measure(rows, entities, bounds, *, river_shapes=(), road_shapes=()):
    """Measure fresh entity geometry; missing/self-only targets never pass."""
    from cityg.polygons import geos
    results = []
    for r in rows:
        subjects = [e for e in entities if matches(e, r['subject'])]
        checks = []
        for e in subjects:
            x, y = e['center']; rel = r['relation']; value = None
            if rel.endswith('_half'):
                midx, midy = bounds.center.x, bounds.center.y
                value = {'north_half': midy-y, 'south_half': y-midy,
                         'east_half': midx-x, 'west_half': x-midx}[rel]
                violation = max(0, value) / max(bounds.width, bounds.depth)
            elif rel == 'min_footprint_area':
                value = e['area']; violation = max(0, r['threshold']-value)/r['threshold']
            else:
                if r['target'] in ('river', 'road'):
                    shapes = river_shapes if r['target'] == 'river' else road_shapes
                    distances = [s.distance(geos().Point(x, y)) for s in shapes]
                else:
                    distances = [math.dist(e['center'], t['center']) for t in entities
                                 if t['id'] != e['id'] and matches(t, r['target'])]
                value = min(distances) if distances else None
                violation = (1e6 if value is None else
                    max(0, r['threshold']-value) / r['threshold'] if rel == 'far' else
                    max(0, value-r['threshold']) / r['threshold'])
            checks.append({'entity_id': e['id'], 'observed': value, 'violation': violation,
                           'ok': violation <= 1e-8})
        ok = bool(subjects) and all(c['ok'] for c in checks)
        results.append({**r, 'status': 'satisfied' if ok else 'violated',
            'checks': checks, 'violation': sum(c['violation'] for c in checks) if subjects else 1e6,
            'reason_measured': 'actual geometry' if subjects else 'selector has no bound subjects'})
    return results


def evaluate(city, rows=None):
    from cityg.polygons import river_shape, road_shape
    rows = city.metadata.get('urban_requirements', []) if rows is None else rows
    validate(rows)
    entities = [{'id': b.id, 'zone': d.name, 'function': b.function,
                 'center': (b.footprint.center.x, b.footprint.center.y), 'area': b.footprint.area}
                for d in city.districts for p in d.parcels for b in p.buildings]
    return measure(rows, entities, city.bounds,
        river_shapes=[river_shape(r) for r in city.rivers] if rows else (),
        road_shapes=[road_shape(r) for r in city.road_network.segments] if rows else ())


def rank(results):
    return (sum(r['status'] != 'satisfied' for r in results if r['strength'] == 'hard'),
            sum(r['violation'] for r in results if r['strength'] == 'hard'),
            sum(r['violation'] for r in results if r['strength'] == 'soft'))
