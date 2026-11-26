"""Bounded geographic intent and measurable realization contracts.

Adaptive layouts use staggered straight streets and localized bank collectors.
All tolerances here concern visible shape, not physical safety.
"""
from __future__ import annotations

import math
from collections import Counter

MORPHOLOGY_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "river_amplitude_ratio": {"type": "number", "minimum": .03, "maximum": .14},
        "river_cycles": {"type": "number", "minimum": .5, "maximum": 1.5},
        "road_warp_ratio": {"type": "number", "minimum": .01, "maximum": .06},
    },
}


def validate_morphology(value):
    if not isinstance(value, dict) or set(value) - set(MORPHOLOGY_SCHEMA['properties']):
        raise ValueError('unknown morphology fields')
    for key, v in value.items():
        limits = MORPHOLOGY_SCHEMA['properties'][key]
        if (isinstance(v, bool) or not isinstance(v, (int, float)) or
                not math.isfinite(v) or not limits['minimum'] <= v <= limits['maximum']):
            raise ValueError(f'morphology.{key} outside safe range')


def path_metrics(points):
    a, b = points[0], points[-1]
    dx, dy = b.x-a.x, b.y-a.y
    chord = math.hypot(dx, dy)
    if chord <= 1e-9:
        raise ValueError('morphology path has coincident endpoints')
    length = sum(math.hypot(q.x-p.x, q.y-p.y) for p, q in zip(points, points[1:]))
    deviation = max(abs(dx*(p.y-a.y)-dy*(p.x-a.x))/chord for p in points)
    return {'length_m': length, 'chord_m': chord, 'max_deviation_m': deviation,
            'sinuosity': length/chord}


def realization_report(city):
    from cityg.architecture import is_expressive_envelope
    roads = [path_metrics(r.centerline) for r in city.road_network.segments]
    length = sum(r['length_m'] for r in roads)
    degrees = Counter(j for r in city.road_network.segments
                      for j in (r.start_junction_id, r.end_junction_id))
    envelopes = [b.metadata.get('appearance_plan', {}).get('envelope', {})
                 for b in city.iter_buildings()]
    return {
        'expressive_building_count': sum(is_expressive_envelope(e) for e in envelopes),
        'expressive_building_ratio': sum(is_expressive_envelope(e) for e in envelopes) / len(envelopes) if envelopes else 0.,
        'road_count': len(roads),
        'straight_road_length_ratio': sum(r['length_m'] for r in roads
            if r['max_deviation_m'] < .05) / length if length else 0.,
        'junction_degree_counts': dict(Counter(str(d) for d in degrees.values())),
        'visibly_curved_road_count': sum(r['max_deviation_m'] >= 1 for r in roads),
        'max_road_deviation_m': max((r['max_deviation_m'] for r in roads), default=0),
        'rivers': {r.id: path_metrics(r.centerline) for r in city.rivers},
        'exterior_shape_counts': dict(Counter(e.get('shape', 'rectangle') if e else
                                             'legacy_archetype' for e in envelopes)),
        'exterior_profile_counts': dict(Counter(e.get('profile', 'straight') for e in envelopes if e)),
    }


def contract_issues(city):
    """Recompute on validation; saved metrics cannot hide subsequent regression."""
    contract = city.metadata.get('morphology_contract')
    if not contract:
        return []
    issues = []
    report = realization_report(city)
    localized = contract.get('topology') == 'staggered_streets_local_waterfront'
    needs_curve = contract.get('adaptive_roads') and (not localized or bool(city.rivers))
    if needs_curve and report['visibly_curved_road_count'] < 1:
        issues.append(('roads', 'Adaptive roads requested, but no road deviates by at least 1 m'))
    if localized and report['straight_road_length_ratio'] < .65:
        issues.append(('roads', 'Localized waterfront layout must retain at least 65% straight road length'))
    if localized and report['road_count'] >= 12 and not report['junction_degree_counts'].get('3', 0):
        issues.append(('roads', 'Staggered streets requested, but no T junction was realized'))
    if contract.get('river_min_deviation_m'):
        metrics = report['rivers'].values()
        if not metrics or max(m['max_deviation_m'] for m in metrics) < contract['river_min_deviation_m']:
            issues.append(('river', 'Requested river bend was not realized'))
    buildings = {b.id: b for b in city.iter_buildings()}
    for bid, expected in contract.get('building_envelopes', {}).items():
        building = buildings.get(bid)
        actual = building.metadata.get('appearance_plan', {}).get('envelope', {}) if building else {}
        revision = building.metadata.get('morphology_envelope_revision', {}) if building else {}
        # Explicit validated refinement is allowed to revise an initial shape;
        # never make the original requirement immutable across legitimate edits.
        if revision.get('original') == expected and revision.get('accepted') and revision.get('reason'):
            expected = revision['accepted']
        if actual != expected:
            issues.append((bid, 'Explicit district envelope assignment changed or disappeared'))
    return issues
