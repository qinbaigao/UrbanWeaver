"""Opt-in functional outdoor rooms, connected to existing building approaches.

Authored/agent programs live in ``city.metadata['parcel_courtyard_programs']``.
The compiler realizes them inside actual free polygons; it never moves a
building, removes existing assets, or invents an entrance to make a program fit.
"""
from collections import Counter, defaultdict
import math

from shapely.ops import nearest_points

from cityg.geometry.courtyard_furnishings import furnish_courtyard
from cityg.geometry.courtyard_programs import PROGRAMS, SIZES, adaptive_features, feature_fallbacks
from cityg.geometry.courtyard_collision import restore_collision_overrides, realize_exterior_collisions
from cityg.geometry.geography import polygon_mesh, primitive_footprint
from cityg.geometry.site_routing import route_in_polygon
from cityg.polygons import box_shape, geos, parcel_shape, river_shape, road_shape

VERSION = 'functional_courtyards_v1'


def oriented_rectangle(s, x, y, width, depth, angle):
    co, si = math.cos(angle), math.sin(angle)
    def xy(a, b):
        return (x+a*co-b*si, y+a*si+b*co)
    return s.Polygon([xy(a, b) for a, b in
        [(-width/2, -depth/2), (width/2, -depth/2),
         (width/2, depth/2), (-width/2, depth/2)]]), xy


def compile_parcel_courtyards(compiler, city, scene):
    programs = city.metadata.get('parcel_courtyard_programs', {})
    if programs == {}:
        if 'parcel_courtyard_programs' in city.metadata and programs == {}:
            restore_collision_overrides(scene)
            scene.primitives = [p for p in scene.primitives if p.metadata.get('site_system') != VERSION]
            scene.metadata.pop('parcel_courtyards', None)
        return {'status': 'not_requested'}
    # Reject invalid programs *before* removing any previously compiled work.
    known = {p.id for p in city.iter_parcels()}
    if not isinstance(programs, dict) or set(programs)-known:
        raise ValueError('Courtyard programs must reference existing parcel IDs')
    for program in programs.values():
        if not isinstance(program, dict) or program.get('theme') not in PROGRAMS:
            raise ValueError('Unknown courtyard theme')
        features = program.get('features', PROGRAMS[program['theme']])
        if not isinstance(features, list) or not features or len(features) > 8 or any(k not in SIZES for k in features):
            raise ValueError('Expected 1..8 supported courtyard features')

    restore_collision_overrides(scene)
    collision_overrides=realize_exterior_collisions(compiler,city,scene,programs)
    s = geos()
    base = [p for p in scene.primitives if p.metadata.get('site_system') != VERSION]
    by_owner = defaultdict(list)
    dedicated = defaultdict(list)
    for p in base:
        by_owner[p.owner_id].append(p)
        if p.metadata.get('parcel_id') and p.owner_id != p.metadata['parcel_id']:
            if p.metadata.get('metro_system') or p.metadata.get('construction_system'):
                dedicated[p.metadata['parcel_id']].append(p)
    roads = s.union_all([road_shape(r, r.sidewalk_width_m+.25) for r in city.road_network.segments])
    water = s.union_all([river_shape(r, 'reserve') for r in city.rivers])
    entrances = defaultdict(list)
    for p in base:
        if p.semantic_class == 'frontage_connector':
            entrances[p.metadata.get('building_id')].append(primitive_footprint(p))
            if p.metadata.get('residential_group_paths'):
                for bid in p.metadata.get('building_ids', []):
                    entrances[bid].append(primitive_footprint(p))
    additions, records, omitted = [], [], []
    skips = Counter()
    for district in city.districts:
        for parcel in district.parcels:
            if parcel.id not in programs:
                continue
            program = programs[parcel.id]
            theme = program['theme']
            features = program.get('features', PROGRAMS[theme])
            shape = parcel_shape(parcel)
            obstacles = []
            footprint_sources = {}
            for b in parcel.buildings:
                ground_owners = {b.id, *(f.id for f in b.floors if f.level == 0)}
                slabs = [primitive_footprint(p) for owner in ground_owners for p in by_owner[owner]
                         if p.semantic_class == 'floor_slab' and p.center.z < 1.0]
                if slabs:
                    obstacles.append(s.union_all(slabs).buffer(.8))
                    footprint_sources[b.id] = 'compiled_ground_floor'
                    # Include real ground-touching wall/column/module envelopes;
                    # a narrow tower's unused planning AABB is not an obstacle.
                    obstacles.extend(primitive_footprint(p).buffer(.5)
                        for owner in ground_owners for p in by_owner[owner]
                        if p.center.z-p.size.z/2 < .5 and p.center.z+p.size.z/2 > .25
                        and not (p.semantic_class=='collision_envelope' and not p.collision_enabled))
                else:
                    obstacles.append(box_shape(b.footprint).buffer(.8))
                    footprint_sources[b.id] = 'planning_envelope_fallback'
            old_paths, old_pads = [], []
            for p in by_owner[parcel.id]:
                if p.semantic_class == 'parcel_walkway':
                    old_paths.append(primitive_footprint(p))
                elif p.semantic_class == 'parcel_activity_pad':
                    old_pads.append(primitive_footprint(p))
                elif p.semantic_class == 'parcel_planting_bed' or p.center.z+p.size.z/2 > .25:
                    obstacles.append(primitive_footprint(p).buffer(.35))
            # Metro openings and equipment may use a dedicated owner ID.
            obstacles.extend(primitive_footprint(p).buffer(.6) for p in dedicated[parcel.id])
            free = shape.buffer(-.4).difference(s.union_all(obstacles)).difference(roads.union(water))
            # Only previous site paths certified as connected may serve as roots.
            certified = [primitive_footprint(p) for p in by_owner[parcel.id]
                         if p.semantic_class == 'parcel_walkway' and p.metadata.get('connection')]
            approach = [g for b in parcel.buildings for g in entrances[b.id]]
            connection = 'existing_building_approach' if approach else 'existing_connected_site_path'
            network = s.union_all(approach+certified)
            if network.is_empty:
                skips['no_existing_connected_approach'] += 1
                omitted.append({'parcel_id':parcel.id,'reason':'no_existing_connected_approach'})
                continue
            network = network.intersection(free.buffer(-1.08))
            if network.is_empty:
                skips['approach_has_no_clear_connection'] += 1
                omitted.append({'parcel_id':parcel.id,'reason':'approach_has_no_clear_connection'})
                continue
            protected = s.union_all(old_paths+old_pads).union(network).buffer(.35)
            used = s.union_all(old_pads).buffer(.3)
            route_obstacles = used
            seed = compiler._parcel_seed(parcel.id, VERSION)
            if program.get('adaptive'):
                features = adaptive_features(theme, free.area, seed)
            orientation = float(parcel.buildings[0].metadata.get('orientation_deg', 0)) if parcel.buildings else 0
            x0, y0, x1, y1 = shape.bounds
            nodes, paths, items = [], [], []
            queue = [(i,kind,kind) for i,kind in enumerate(features)]
            while queue:
                feature_index, kind, requested = queue.pop(0)
                width, depth = SIZES[kind]
                candidates = []
                blocked = protected.union(used)
                safe_free = free.buffer(-.2)
                s.prepare(safe_free)
                s.prepare(blocked)
                # Stable stratified samples; keep courtyards parallel to the
                # building rather than rotating every pocket toward one point.
                for attempt in range(420):
                    x = x0+((seed%997/997+attempt*.61803398875)%1)*(x1-x0)
                    y = y0+((seed%991/991+attempt*.41421356237)%1)*(y1-y0)
                    for turn in range(4):
                        angle = math.radians(orientation+90*turn)
                        pad, xy = oriented_rectangle(s, x, y, width, depth, angle)
                        if not safe_free.covers(pad) or blocked.intersects(pad):
                            continue
                        goal = xy(0, -depth/2+1.15)
                        root = nearest_points(network, s.Point(goal))[0]
                        score = root.distance(s.Point(goal))
                        # Arrival is near the entrance, services are secondary;
                        # distance is only a ranking, not an impossible mandate.
                        if kind in {'cycle', 'kiosk'}:
                            score = abs(score-22)
                        candidates.append((score, attempt, turn, x, y, angle, pad, goal))
                placed = False
                for _, _, _, x, y, angle, pad, goal in sorted(candidates, key=lambda c:c[:3])[:32]:
                    _, local = oriented_rectangle(s, x, y, width, depth, angle)
                    spine = s.LineString([local(0,-depth/2-1),local(0,depth/2+1)]).buffer(1.1)
                    # Route through the reserved spine, not diagonally across
                    # the future tables/planters. This also avoids furnishing
                    # dozens of doomed candidates just to reject their paths.
                    routable = free.difference(route_obstacles.union(pad.difference(spine)))
                    safe_network = network.intersection(routable.buffer(-1.08))
                    if safe_network.is_empty:
                        continue
                    root = nearest_points(safe_network, s.Point(goal))[0]
                    route = route_in_polygon((root.x, root.y), goal, routable, width=2., budget=4000)
                    if not route:
                        continue
                    route_shape = s.LineString(route).buffer(1., quad_segs=4)
                    prefix = f'{parcel.id}_courtyard_{feature_index:02d}'
                    meta = {'site_system': VERSION, 'parcel_id': parcel.id, 'district_id': district.id,
                            'site_node_id': prefix, 'site_feature': kind, 'courtyard_theme': theme,
                            'site_detail': True, 'exterior_only': True, 'interactive': False,
                            'activity_mode': 'static_snapshot'}
                    parts = furnish_courtyard(compiler, parcel.id, prefix, kind, (x,y), angle, pad, meta)
                    # Keep the entire approach clear, including its portion
                    # inside the court. Overhead canopies are explicitly exempt.
                    if any(primitive_footprint(p).intersection(route_shape).area > 1e-5
                           for p in parts if p.metadata.get('ground_obstacle')):
                        continue
                    material = {'garden':'permeable_paver', 'terrace':'brick_paving',
                                'arrival':'paving_light', 'cycle':'paving_dark', 'kiosk':'gravel_warm',
                                'grove':'permeable_paver','pavilion':'brick_paving',
                                'promenade':'paving_light','pocket':'permeable_paver'}[kind]
                    surface = polygon_mesh(prefix+'_surface', parcel.id, pad, .16, .08,
                        'parcel_activity_pad', material, collision=True, metadata=meta)
                    items.extend([surface, *parts]); paths.append(route_shape)
                    nodes.append({'id':prefix, 'kind':kind, 'center':[x,y], 'angle_deg':math.degrees(angle),
                                  'requested_kind':requested,
                                  'size_m':[width,depth], 'route':route, 'primitive_count':len(parts)+1,
                                  'connection':connection,
                                  'asset_count':sum(bool(p.metadata.get('asset_id')) for p in parts)})
                    used = used.union(pad.buffer(.4))
                    protected = protected.union(route_shape.buffer(.25))
                    # A furnished court is not a dead-end obstacle: its reserved
                    # spine may carry later branches to the rear of the parcel.
                    route_obstacles = route_obstacles.union(pad.difference(spine))
                    network = network.union(route_shape).union(spine.intersection(pad))
                    placed = True
                    break
                if not placed:
                    skips[f'no_safe_space_for_{kind}'] += 1
                    if program.get('adaptive'):
                        alternatives=feature_fallbacks(requested)
                        next_index=alternatives.index(kind)+1
                        if next_index<len(alternatives):
                            queue.insert(0,(feature_index,alternatives[next_index],requested))
            if not nodes:
                omitted.append({'parcel_id':parcel.id,'reason':'no_safe_connected_space',
                                'free_area_m2':round(free.area,1)})
                continue
            pads = s.union_all([primitive_footprint(p) for p in items if p.semantic_class == 'parcel_activity_pad'])
            path_surface = s.union_all(paths).difference(pads).difference(s.union_all(old_paths))
            path = polygon_mesh(parcel.id+'_courtyard_paths', parcel.id, path_surface, .15, .07,
                                'parcel_walkway', 'paving_light', collision=True, metadata={
                                    'site_system':VERSION, 'site_feature':'pedestrian_path', 'site_detail':True,
                                    'parcel_id':parcel.id, 'path_width_m':2., 'connection':connection})
            if path:
                items.append(path)
            additions.extend(items)
            records.append({'parcel_id':parcel.id, 'theme':theme, 'free_area_m2':round(free.area,1),
                            'nodes':nodes, 'requested_nodes':len(features), 'footprint_sources':footprint_sources})
            if program.get('adaptive'):
                print(f'  {parcel.id}: {len(nodes)}/{len(features)} courts, '
                      f'{round(free.area)} m2 free, '+', '.join(n['kind'] for n in nodes),flush=True)
    scene.primitives = base+additions
    assets = Counter(p.metadata['asset_id'] for p in additions if p.metadata.get('asset_id'))
    report = {'version':VERSION, 'changed_parcel_count':len(records), 'parcels':records,
              'new_primitives':len(additions), 'new_asset_instances':sum(assets.values()),
              'asset_counts':dict(assets), 'skips':dict(skips), 'navigation_graph_extended':False,
              'requested_parcel_count':len(programs),'omitted_parcels':omitted,
              'updated_collision_primitives':len(collision_overrides),
              'collision_scope':'realized_solid_shells_exterior_only',
              'node_counts':dict(Counter(n['kind'] for r in records for n in r['nodes']))}
    scene.metadata['parcel_courtyards'] = report
    return report
