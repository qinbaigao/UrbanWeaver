"""Straight neighbourhood streets with independent, localized waterfront curves.

Build semantic junctions explicitly: staggered local streets terminate at a
collector rather than crossing an un-noded geometric intersection. The river
does not deform the neighbourhood grid. Only its two bank collectors curve.
"""
from __future__ import annotations

import math

from cityg.schemas import Junction, Point2D, River, RoadNetwork, RoadSegment


def adaptive_streets(spec, seed_network, *, compact=False):
    from cityg.planning.baseline import BaselineCityPlanner

    planner = BaselineCityPlanner()
    xmin = min(j.position.x for j in seed_network.junctions)
    xmax = max(j.position.x for j in seed_network.junctions)
    ymin = min(j.position.y for j in seed_network.junctions)
    ymax = max(j.position.y for j in seed_network.junctions)
    xs = sorted({j.position.x for j in seed_network.junctions
                 if abs(j.position.y-ymin) < 1e-6})
    ys = sorted({j.position.y for j in seed_network.junctions
                 if abs(j.position.x-xmin) < 1e-6})
    count = max(2, len(xs)-1)
    cycles = spec.morphology.get('river_cycles', 1.)
    amplitude = spec.width_m * spec.morphology.get('river_amplitude_ratio', .10)
    center = spec.width_m / 2

    def river_x(y):
        return center + amplitude * math.sin(2*math.pi*cycles*y/spec.depth_m)

    rivers = []
    bank_pair = None
    # A station and its coordinate are shared by all incident segments. No
    # tolerance-dependent pairwise intersection/noding after allocation.
    collectors = []
    if spec.river_mode != 'none':
        samples = max(2, math.ceil(spec.depth_m/2.5))
        river_points = tuple(Point2D(river_x(spec.depth_m*i/samples),
                                     spec.depth_m*i/samples) for i in range(samples+1))
        rivers = [River('river_000', 'Meandering river', river_points,
                        spec.river_width_m, spec.river_bank_width_m, spec.river_setback_m)]
        # Horizontal offsets must also respect *normal* river clearance at the
        # steepest tangent, and keep bridge ends clear of bank-side junctions.
        slope = amplitude * 2*math.pi*cycles/spec.depth_m
        max_width = max(r.width_m for r in seed_network.segments)
        offset = (spec.river_width_m/2 + spec.river_bank_width_m
                  + max(spec.river_setback_m, max_width+6)) * math.sqrt(1+slope*slope)
        margin = max(60., spec.parcel_setback_m*2+40, max_width*3)
        if compact:
            # This is street-layout spacing, NOT a reduced user river/setback.
            # Water profile, bank clearance and road cross sections stay fixed.
            margin = max(20., spec.parcel_setback_m*2+12, max_width+4)
        left_edge = center-amplitude-offset-margin
        right_edge = center+amplitude+offset+margin
        if left_edge <= xmin+margin or right_edge >= xmax-margin:
            raise ValueError('Insufficient dry land for independent waterfront streets; '
                             'enlarge the site or reduce river amplitude/width')
        left_count = max(1, count//2-1)
        right_count = max(1, count-left_count-2)
        for i in range(left_count+1):
            x = xmin+(left_edge-xmin)*i/left_count
            collectors.append(lambda y, x=x: Point2D(x, y))
        left_bank = len(collectors)
        collectors.append(lambda y: Point2D(river_x(y)-offset, y))
        collectors.append(lambda y: Point2D(river_x(y)+offset, y))
        bank_pair = (left_bank, left_bank+1)
        for i in range(right_count+1):
            x = right_edge+(xmax-right_edge)*i/right_count
            collectors.append(lambda y, x=x: Point2D(x, y))
    else:
        collectors = [lambda y, x=x: Point2D(x, y) for x in xs]

    stations = [{ymin, ymax} for _ in collectors]
    links = []
    for band in range(len(collectors)-1):
        waterfront = bank_pair == (band, band+1)
        for row, y in enumerate(ys):
            # Through routes are sparse; other streets stop at the river bank.
            through = row in (0, len(ys)-1) or row % 3 == 0
            if waterfront and not through:
                continue
            ya = yb = y
            if not through:
                pitch = min(y-ys[row-1], ys[row+1]-y)
                # Alternate street mouths by a substantial fraction of a block,
                # avoiding nearly coincident T junctions. Slight obliqueness is
                # still one straight segment, not a curved/warped road.
                stagger = pitch * .22 * (1 if band % 2 else -1)
                skew = pitch * spec.morphology.get('road_warp_ratio', .035)
                ya, yb = y+stagger-skew, y+stagger+skew
            stations[band].add(ya)
            stations[band+1].add(yb)
            kind = 'collector' if through else 'local'
            if (through and row == (len(ys)//2)//3*3
                    and planner._arterials_enabled(spec)):
                kind = 'arterial'
            links.append((band, ya, band+1, yb, kind))

    junctions, ids, points = [], {}, {}
    for col, levels in enumerate(stations):
        for row, y in enumerate(sorted(levels)):
            key = (col, y)
            jid = f'junction_adaptive_{col:02d}_{row:03d}'
            ids[key], points[key] = jid, collectors[col](y)
            junctions.append(Junction(jid, points[key]))

    roads = []

    def add(a, b, centerline, road_class, orientation, index):
        lanes, width, sidewalk = planner._road_cross_section(spec, road_class, index, orientation)
        roads.append(RoadSegment(f'road_adaptive_{len(roads):04d}', ids[a], ids[b],
            tuple(centerline), road_class=road_class, lane_count=lanes,
            width_m=width, sidewalk_width_m=sidewalk,
            **planner._road_semantics(spec, road_class, index, orientation)))

    for col, levels in enumerate(stations):
        ordered = sorted(levels)
        for row, (a, b) in enumerate(zip(ordered, ordered[1:])):
            curved = bank_pair is not None and col in bank_pair
            steps = max(1, math.ceil((b-a)/2.5)) if curved else 1
            path = [collectors[col](a+(b-a)*i/steps) for i in range(steps+1)]
            path[0], path[-1] = points[col, a], points[col, b]
            kind = 'collector' if curved or col in (0, len(collectors)-1) else 'local'
            if col == 1 and planner._arterials_enabled(spec):
                kind = 'arterial'
            add((col, a), (col, b), path, kind, 'vertical', col)
    for index, (ca, a, cb, b, kind) in enumerate(links):
        add((ca, a), (cb, b), (points[ca, a], points[cb, b]), kind, 'horizontal', index)
    return RoadNetwork(junctions, roads), rivers
