"""New-scene capability reservation, before entries/cores become contracts.

This is not an existing-building editor. Only unfurnished generation drafts
may reserve a bounded set of rectangular, axis-aligned low-rise buildings.
Unsupported explicit envelopes are retained rather than silently removed.
"""
from cityg.buildings import BuildingSelector, BuildingSelectionContext
from cityg.envelopes import envelope_config
from cityg.serialization import to_primitive
from cityg.schemas import Bounds2D
from cityg.planning.interior_frame import InteriorFrame


def reserve_interiors(city, *, limit, explicit_ids=(), room_library=None, corridor_ratios=None):
    if any(city.iter_objects()):
        raise ValueError('Interior reservation requires an unfurnished generation draft')
    buildings = list(city.iter_buildings())
    known = {b.id for b in buildings}
    if set(explicit_ids) - known or len(set(explicit_ids)) > limit:
        raise ValueError('Invalid explicit interior scope')
    selector = BuildingSelector()
    feasible = []; rejected = []
    for b in buildings:
        reason = None
        frontages = b.metadata.get('available_frontages', [])
        entry = b.metadata.get('entrance_side')
        sides = [s for s in frontages if s in ('west', 'east', 'south', 'north')]
        ctx = BuildingSelectionContext.from_building(b)
        candidates = [c for c in selector.candidates(ctx) if c.massing_style == 'bar' and not c.highrise_only]
        if envelope_config(b): reason = 'explicit_exterior_envelope_preserved'
        elif ctx.highrise: reason = 'highrise_interiors_not_in_rectangular_reservation'
        elif abs(float(b.metadata.get('orientation_deg', 0))) > 1e-6: reason = 'rotated_plate_not_supported_by_reservation'
        elif not sides: reason = 'no_street_frontage_for_supported_circulation_axis'
        elif not candidates: reason = 'no_compatible_rectangular_catalog_entry'
        if reason:
            rejected.append({'building_id': b.id, 'reason': reason})
            continue
        preferred = set(b.metadata.get('semantic_archetype_palette', []))
        ids = tuple(c.archetype_id for c in candidates if c.archetype_id in preferred) or tuple(c.archetype_id for c in candidates)
        selected = selector.select(ctx, preferred_ids=ids)
        feasible.append((b, {'archetype_id': selected.archetype.archetype_id,
            'entrance_side': entry if entry in sides else sides[0],
            'circulation_axis': InteriorFrame.for_entry(entry if entry in sides else sides[0]).axis,
            'source_archetype_id': b.metadata.get('archetype_id'),
            'source_entrance_side': entry,
            'source': 'new_scene_rectangular_interior_v1'}))
    # Favor viable broad plates, then semantic diversity. Exact requested IDs
    # are never replaced with different buildings to disguise infeasibility.
    feasible.sort(key=lambda pair: (max(pair[0].footprint.width/pair[0].footprint.depth,
        pair[0].footprint.depth/pair[0].footprint.width), pair[0].id))
    selected = []; functions = set()
    if explicit_ids:
        selected = [p for p in feasible if p[0].id in explicit_ids]
    else:
        for p in feasible:
            if len(selected) < limit and p[0].function not in functions:
                selected.append(p); functions.add(p[0].function)
        for p in feasible:
            if len(selected) >= limit: break
            if p not in selected: selected.append(p)
    targets = {b.id: record for b, record in selected}
    if room_library is not None:
        for b, record in selected:
            frame=InteriorFrame(record['circulation_axis'])
            plate=frame.bounds(b.footprint)
            functions = {r.function for f in b.floors for r in f.rooms}
            refs = [r for r in room_library.rooms.values() if r['room_type'] in functions
                    and r['reference']['width_m'] * r['reference']['depth_m'] <= 100]
            if not refs: continue
            # Do not average disjoint reference size ranges (e.g. private and
            # four-person offices): their median may fit neither reference.
            # Keep the available frontage for multiple rooms and reserve two
            # depth bands against the draft's actual circulation proportion.
            reference = max(refs, key=lambda r: (
                r['reference']['width_m'] * r['reference']['depth_m'], r['id']))
            corridors = [r for f in b.floors for r in f.rooms if r.function == 'corridor'
                         and abs(r.bounds.width-b.footprint.width) < 1e-5]
            ratio = (corridor_ratios or {}).get(b.function,
                (corridors[0].bounds.depth/b.footprint.depth) if corridors else .18)
            ratio = min(.4, max(.1, ratio))
            w = plate.width
            from cityg.planning.programmed import ProgrammedCityPlanner
            band_depth = reference['reference']['depth_m']
            d = 2 * band_depth + 5
            for _ in range(30):
                d = 2 * band_depth + ProgrammedCityPlanner._corridor_depth(d, ratio)
            d = min(plate.depth, d)
            # Retain the chosen street-facing edge of the buildable footprint.
            x0 = plate.min_x if frame.side(record['entrance_side']) == 'west' else plate.max_x-w
            y0 = plate.center.y-d/2
            record['footprint'] = to_primitive(frame.bounds(Bounds2D(x0, y0, x0+w, y0+d)))
            record['source_footprint'] = to_primitive(b.footprint)
            record['dimension_reference_ids'] = sorted(r['id'] for r in refs)
            record['depth_reference_id'] = reference['id']
            record['reference_band_depth_m'] = reference['reference']['depth_m']
            record['draft_corridor_ratio'] = ratio
            record['dimension_policy'] = 'two_reference_depth_bands_with_bounded_circulation'
    # Pin every other archetype so changing the diversity history for a target
    # cannot accidentally change downstream, out-of-scope building silhouettes.
    pins = {b.id: b.metadata['archetype_id'] for b in buildings if b.metadata.get('archetype_id')}
    pins.update({bid: r['archetype_id'] for bid, r in targets.items()})
    report = {'schema_version': 1, 'policy': 'new_scene_rectangular_interior_v1',
        'target_buildings': targets, 'rejected': rejected, 'requested_limit': limit,
        'explicit_ids': list(explicit_ids), 'existing_scene_edit': False,
        'limitations': ['axis_aligned_lowrise', 'cardinal_frontage', 'catalog_supported_functions']}
    return targets, pins, report
