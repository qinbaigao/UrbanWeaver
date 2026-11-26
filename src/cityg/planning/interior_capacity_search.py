"""Bounded new-scene footprint proposals evaluated by the actual floor planner.

Semantic functions/programs remain Agent-owned. This geometric feasibility
search only shrinks reserved empty buildings within their already buildable
footprint; it never edits a realized scene or scales furniture.
"""
from copy import deepcopy
import time

from cityg.planning.programmed import ProgrammedCityPlanner
from cityg.planning.generation_prototypes import DeferredFurniture
from cityg.planning.prototype_adaptation import room_candidates
from cityg.schemas import Bounds2D
from cityg.serialization import to_primitive
from cityg.planning.interior_frame import InteriorFrame


def capacity_floors(building, max_floors, target_levels=None):
    """Score requested detail levels, not convenient ground-floor substitutes."""
    ordered = sorted(building.floors, key=lambda f: f.level)
    if target_levels is None:
        return ordered[:max_floors]
    return [f for f in ordered if f.level in target_levels][:max_floors]


def improve_reserved_capacity(program, spec, targets, pins, library, *,
                              max_floors=2, variation_limit=.2, max_candidates=36,
                              target_levels=None):
    if not 0 <= variation_limit <= .3 or not 1 <= max_candidates <= 100:
        raise ValueError('Invalid bounded capacity search budget')
    result = deepcopy(targets); reports = []
    started=time.monotonic()
    timings={'draft_s':0., 'compatibility_s':0., 'draft_count':0,
             'compatibility_count':0, 'baseline_candidates_reused':0}
    if spec.room_count_strategy == 'fixed':
        return result, {'status':'skipped_fixed_room_count', 'buildings':[]}
    def draft():
        begin=time.monotonic()
        try:
            return ProgrammedCityPlanner(program, floor_detail_agent=DeferredFurniture(),
                interior_targets=result, archetype_pins=pins).plan(spec)
        finally:
            timings['draft_s']+=time.monotonic()-begin
            timings['draft_count']+=1
    def score(building):
        begin=time.monotonic()
        matches = [(f.level, r.id, [c['prototype_id'] for c in room_candidates(library, building, f, r)])
                   for f in capacity_floors(building, max_floors, target_levels)
                   for r in f.rooms if r.function != 'corridor']
        timings['compatibility_s']+=time.monotonic()-begin
        timings['compatibility_count']+=1
        return [(level, rid, keys) for level, rid, keys in matches if keys]
    for building_id, record in result.items():
        if record.get('source') != 'new_scene_rectangular_interior_v1' or 'footprint' not in record:
            continue
        if record.get('area_contract'):
            reports.append({'building_id':building_id,'status':'explicit_area_preserved',
                            'selected_footprint':record['footprint']})
            continue
        baseline = next(b for b in draft().iter_buildings() if b.id == building_id)
        frame=InteriorFrame(record.get('circulation_axis','x'))
        original = frame.bounds(Bounds2D(**record['footprint']))
        source = frame.bounds(Bounds2D(**record['source_footprint']))
        refs = [library.rooms[key] for key in record.get('dimension_reference_ids', [])]
        widths = {original.width}; depths = {original.depth}
        ratio = record['draft_corridor_ratio']
        for ref in refs:
            w, d = ref['reference']['width_m'], ref['reference']['depth_m']
            for unit, band in ((w, d), (d, w)):
                for count in range(1, int(original.width/unit)+1):
                    width = count*unit
                    if width >= original.width*(1-variation_limit): widths.add(width)
                depth = 2*band+5
                for _ in range(30): depth = 2*band+ProgrammedCityPlanner._corridor_depth(depth, ratio)
                if original.depth*(1-variation_limit) <= depth <= min(source.depth, original.depth*(1+variation_limit)):
                    depths.add(depth)
        # Closest-to-source candidates first; no random seed-dependent retry.
        candidates = sorted(((w,d) for w in widths for d in depths),
            key=lambda p: (abs(p[0]-original.width)/original.width+
                           abs(p[1]-original.depth)/original.depth, p))[:max_candidates]
        best = deepcopy(record); matches = score(baseline)
        best_rank = (len(matches), original.area)
        before_count = len(matches); audits = []
        for width, depth in candidates:
            candidate_started=time.monotonic()
            if abs(width-original.width)<1e-8 and abs(depth-original.depth)<1e-8:
                timings['baseline_candidates_reused']+=1
                audits.append({'width_m':width,'depth_m':depth,'compatible_rooms':before_count,
                               'baseline_reused':True,'elapsed_s':0.})
                continue
            x = source.min_x if frame.side(record['entrance_side']) == 'west' else source.max_x-width
            y = source.center.y-depth/2
            bounds = Bounds2D(x,y,x+width,y+depth)
            if not source.contains_bounds(bounds, tolerance=1e-6): continue
            record['footprint'] = to_primitive(frame.bounds(bounds))
            try:
                candidate = next(b for b in draft().iter_buildings() if b.id == building_id)
                found = score(candidate)
                rank = (len(found), bounds.area)
                audits.append({'width_m':width,'depth_m':depth,'compatible_rooms':len(found),
                               'elapsed_s':round(time.monotonic()-candidate_started,6)})
                if rank > best_rank:
                    best_rank = rank; best = deepcopy(record); matches = found
            except ValueError as error:
                audits.append({'width_m':width,'depth_m':depth,'rejected':str(error),
                               'elapsed_s':round(time.monotonic()-candidate_started,6)})
        record.clear(); record.update(best)
        selected_depth = frame.bounds(Bounds2D(**record['footprint'])).depth
        record['capacity_selected_band_depth_m'] = (selected_depth-
            ProgrammedCityPlanner._corridor_depth(selected_depth, ratio))/2
        reports.append({'building_id':building_id, 'before_compatible_rooms':before_count,
            'scored_levels':[f.level for f in capacity_floors(baseline, max_floors, target_levels)],
            'after_compatible_rooms':len(matches), 'selected_footprint':best['footprint'],
            'matched_rooms':matches, 'candidates':audits})
    return result, {'status':'bounded_geometry_search', 'buildings':reports,
        'timings':{**timings,'total_s':time.monotonic()-started},
        'max_candidates_per_building':max_candidates, 'variation_limit':variation_limit,
        'semantic_program_changed':False, 'existing_scene_edit':False,
        'furniture_scaled':False, 'compiled_furnishing_verified':False}
