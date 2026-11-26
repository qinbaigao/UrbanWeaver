"""Shared candidate eligibility and ranking for the from-scratch planning policies."""
from dataclasses import asdict

from cityg.planning.building_site import SiteLimits, footprint_bounds
from cityg.planning.site_coordination import site_options

POLICIES = ('one_way', 'fixed_feedback', 'agent_feedback')


def ordered_offers(offers, city, selector, limit=None):
    """Freeze the rule shortlist before reordering. A declined choice consumes no slot."""
    ordered = sorted(offers, key=lambda p: (p['compatible_before'] - p['compatible_after'],
                                             abs(p['shift_m']), p['id']))
    if limit is not None:
        ordered = ordered[:limit]
    selection = {'proposal_id': None, 'decision_owner': 'fixed_order'}
    if ordered and selector is not None:
        selection = selector(city, ordered)
        chosen = next((p for p in ordered if p['id'] == selection.get('proposal_id')), None)
        if chosen is not None:
            ordered = [chosen, *(p for p in ordered if p is not chosen)]
    return ordered, selection


def reserve_larger_sites(city, targets, bindings):
    """Before building realization, try parcel-verified growth for an explicit gross area shortfall."""
    if not any(r.get('area_m2') is not None for rows in bindings.values() for r in rows):
        return []
    from copy import deepcopy
    working = deepcopy(city)
    buildings = {b.id: b for b in working.iter_buildings()}
    parcels = {b.id: p for p in working.iter_parcels() for b in p.buildings}
    trace = []
    for bid, rows in bindings.items():
        areas = {r['area_m2'] for r in rows if r.get('area_m2') is not None}
        if bid not in targets or len(areas) != 1 or any(
                r.get('area_m2') is not None and r['area_basis'] != 'floor_gross' for r in rows):
            continue
        building = buildings[bid]
        area = next(iter(areas))
        if area <= building.footprint.area + 1e-6:
            continue
        request = {'area_m2': area}
        limits = SiteLimits(working, building, parcels[bid])
        aspects = [building.footprint.width / building.footprint.depth]
        aspects.extend(v['aspect_ratio'] for v in site_options(working, building, request).values())
        record = {'building_id': bid, 'requested_area_m2': area, 'attempts': [], 'accepted': False}
        trace.append(record)
        for aspect in aspects:
            bounds = footprint_bounds(building, area, aspect, request)
            reason = limits.violation(bounds)
            if min(bounds.width,bounds.depth)<6: reason = 'insufficient short side'
            record['attempts'].append({'aspect': aspect,'rejection':reason})
            if reason: continue
            targets[bid]['verified_site_growth'] = {'original': asdict(building.footprint),
                'bounds': asdict(bounds),'area_m2':area}
            building.footprint = bounds
            record['accepted'] = True
            break
    return trace
