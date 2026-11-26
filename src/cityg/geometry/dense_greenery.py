"""Opt-in layered groves on unused dry land, preserving authored city geometry.

The additive layer is replayable. Placement uses compiled paths/structures, not
just parcel rectangles. Only existing realistic meshes are accepted; absence of
an asset never creates a geometric tree proxy. This is landscape dressing, not
a botanical growth or trunk-collision simulation.
"""
from collections import Counter
from dataclasses import dataclass, replace
import math
import random

from cityg.geometry.edge_landscape import Heightfield
from cityg.geometry.geography import primitive_footprint
from cityg.geometry.asset_fitting import outdoor_asset_ground_offset
from cityg.geometry.model import Vec3
from cityg.polygons import box_shape, geos, parcel_shape, record_shape, river_shape, road_shape
from cityg.schemas import Bounds2D

KEY = 'dense_greenery'
VERSION = 'layered_groves_v1'
PLANTS = {'street_tree', 'park_tree', 'shrub', 'plant'}
TREES = {
    'island': ('island',), 'jacaranda': ('jacaranda',),
    'small_tree': ('tree', 'small', '02'), 'pine': ('pine',),
    'fir': ('fir',), 'quiver': ('quiver',),
}
PATHS = {'frontage_connector', 'parcel_walkway', 'parcel_activity_pad',
         'landscape_path', 'plaza', 'sidewalk', 'road_surface', 'parking_space',
         'sidewalk_frontage_strip', 'sidewalk_furnishing_strip', 'curb'}


@dataclass
class Zone:
    id: str
    owner: str
    shape: object
    theme: str
    height: object
    metadata: dict


def planting_zones(city):
    construction = {r['parcel_id'] for r in city.metadata.get('construction_sites', {}).get('sites', [])}
    zones = []
    for d in city.districts:
        for p in d.parcels:
            if p.id in construction:
                continue
            theme = 'residential' if any(b.function == 'residential' for b in p.buildings) else d.function
            if any(b.metadata.get('residential_group', {}).get('kind') == 'townhouses' for b in p.buildings):
                theme = 'townhouses'
            zones.append(Zone(p.id, p.id, parcel_shape(p), theme, lambda x,y: .1,
                              {'parcel_id': p.id, 'district_id': d.id}))
    for r in city.metadata.get('landscape_sites', []):
        if r.get('boundary'):
            # Landscape-site IDs are metadata labels, not canonical entities.
            zones.append(Zone(r['id'], city.id, record_shape(r), 'park', lambda x,y: .06,
                              {'landscape_site': r['id']}))
    edge = city.metadata.get('edge_landscape_extension')
    if edge:
        for side in ('park', 'hill'):
            field = Heightfield(edge[side+'_bounds'], edge['hill_height_m'] if side == 'hill' else 0,
                                edge['grid_step_m'])
            zones.append(Zone('edge_'+side, city.id, box_shape(Bounds2D(**edge[side+'_bounds'])),
                              side, field, {'site': side, 'edge_greenery': True}))
    return zones


def obstacle_index(city, base, *, include_vegetation=True):
    """Protect actual ground-level shells, all access surfaces and existing props."""
    s = geos()
    shapes = [road_shape(r, .65) for r in city.road_network.segments]
    shapes += [river_shape(r, 'reserve') for r in city.rivers]
    building_owners = {b.id for b in city.iter_buildings()}
    building_owners.update(f.id for b in city.iter_buildings() for f in b.floors)
    ground_slabs = set()
    for p in base:
        m = p.metadata
        if not include_vegetation and m.get('asset_category') in PLANTS:
            # A new low layer may occupy soil beneath existing crowns. Paths,
            # tree stems and spacing are still checked by the border planner.
            continue
        building = p.owner_id in building_owners
        bottom = p.center.z-p.size.z/2
        if building and p.semantic_class == 'floor_slab' and p.center.z < 1:
            ground_slabs.add(p.owner_id)
            shapes.append(primitive_footprint(p).buffer(1.2))
        elif building and bottom < 12 and p.center.z+p.size.z/2 > .3:
            if p.semantic_class == 'collision_envelope' and not p.collision_enabled:
                continue
            shapes.append(primitive_footprint(p).buffer(.8))
        elif not building:
            asset = m.get('resolved_asset')
            protected = p.semantic_class in PATHS or m.get('metro_system') or m.get('construction_system')
            # Grass/terrain/colour patches are plantable; physical site props,
            # shelters and even thin circulation slabs are not.
            solid = (m.get('site_system') and p.center.z+p.size.z/2 > .3
                     and p.semantic_class not in {'parcel_ground', 'parcel_surface_patch'})
            if asset or protected or solid or p.semantic_class == 'parcel_planting_bed':
                shapes.append(primitive_footprint(p).buffer(.25 if asset else .55))
    for b in city.iter_buildings():
        if not ({b.id, *(f.id for f in b.floors if f.level == 0)} & ground_slabs):
            shapes.append(box_shape(b.footprint).buffer(1.2))
    return s.STRtree(shapes)


def compile_dense_greenery(compiler, city, scene):
    plan = city.metadata.get(KEY)
    if not plan or not plan.get('enabled', True):
        return {'status': 'not_requested'}
    density = float(plan.get('density', 1))
    if not math.isfinite(density) or not .1 <= density <= 3:
        raise ValueError('Greenery density must be within [0.1, 3]')
    if plan.get('version', VERSION) != VERSION:
        raise ValueError('Unknown greenery version')
    base = [p for p in scene.primitives if p.metadata.get(KEY) != VERSION]
    previous = [p for p in scene.primitives if p.metadata.get(KEY) == VERSION]
    s = geos(); index = obstacle_index(city, base)
    additions = []; records = []; counts = Counter(); roles = Counter(); templates = {}
    for zone in planting_zones(city):
        hits = index.query(zone.shape)
        free = zone.shape.buffer(-1).difference(s.union_all(index.geometries.take(hits)))
        if free.area < 40:
            continue
        s.prepare(free)
        rng = random.Random(compiler._parcel_seed(zone.id, VERSION, str(plan.get('seed', 20261017))))
        woodland = zone.theme in {'park', 'hill'}
        residential = zone.theme in {'residential', 'townhouses'}
        target = min(850 if zone.metadata.get('edge_greenery') else 70,
                     max(3, round(free.area*density/(360 if woodland or residential else 470))))
        palette = (['pine','pine','fir','island','small_tree'] if zone.theme == 'hill' else
                   ['island','island','small_tree','jacaranda','pine'] if residential else
                   ['island','small_tree','jacaranda','island','quiver'])
        x0,y0,x1,y1 = zone.shape.bounds
        local = []; canopy = []; low = []; clusters = []; tree_count = 0

        def place(x, y, role, tag, height, cluster):
            if not free.contains(s.Point(x,y)):
                return None
            category = 'park_tree' if role == 'canopy' else 'shrub' if role == 'understory' else 'plant'
            tags = TREES[tag] if role == 'canopy' else (tag,)
            prefix = f'{zone.id}_dense_greenery_{len(local):04d}'
            ground = zone.height(x,y)
            key = (category,tag)
            if key not in templates:
                templates[key] = [compiler._outdoor_mesh(f'greenery_template_{tag}_{i}',zone.owner,
                    Vec3(0,0,1),Vec3(2,2,2),0,
                    'parcel_tree_asset' if role == 'canopy' else 'parcel_shrub_asset' if role == 'understory' else 'parcel_plant_asset',
                    category,tag.replace('_',' ')+' outdoor','roads',required_asset_tags=tags,exclude_stylized=True)
                    for i in range(4)]
                templates[key] = [p for p in templates[key] if p is not None]
            if not templates[key]:
                return None
            template = rng.choice(templates[key])
            item = replace(template,id=prefix,owner_id=zone.owner,
                center=Vec3(x,y,ground+height/2),size=Vec3(height,height,height),
                rotation_z_deg=rng.uniform(0,360),metadata={**template.metadata,**zone.metadata, KEY:VERSION,
                    'planting_system':VERSION, 'planting_role':role, 'planting_species':tag,
                    'planting_cluster':cluster, 'terrain_contact_z':ground})
            # Several legacy tree records lack proportional fitting. Explicitly
            # restore their registered proportions here, without changing them
            # (or the appearance of any existing city instance).
            record = compiler.asset_registry.get(item.metadata['asset_id'])
            dims = record.dimensions_m
            if dims and min(dims) > 0:
                item.size = Vec3(*(v*height/dims[2] for v in dims))
                item.center = Vec3(x,y,ground+height/2-outdoor_asset_ground_offset(record,item.size))
            footprint = primitive_footprint(item)
            if not free.covers(footprint):
                return None
            radius = max(item.size.x,item.size.y)/2
            neighbors = canopy if role == 'canopy' else low
            # Canopy edges may overlap slightly to read as groves. Low layers
            # may sit under crowns, but never at tree trunks or atop each other.
            if any(math.hypot(x-a,y-b) < (radius+r)*(.85 if role == 'canopy' else 1.05)
                   for a,b,r in neighbors):
                return None
            if role != 'canopy' and any(math.hypot(x-a,y-b) < radius+.55 for a,b,r in canopy):
                return None
            neighbors.append((x,y,radius)); local.append(item)
            return item

        for attempt in range(target*35):
            if tree_count >= target:
                break
            # Several trees share an irregular grove; some stand independently.
            if not clusters or attempt % 8 == 0:
                cx,cy = rng.uniform(x0,x1),rng.uniform(y0,y1)
                if not free.contains(s.Point(cx,cy)):
                    continue
                clusters.append((cx,cy))
            cx,cy = clusters[-1]
            x,y = cx+rng.gauss(0,9),cy+rng.gauss(0,9)
            tag = rng.choice(palette)
            height = rng.uniform(5,8) if zone.theme == 'townhouses' else rng.uniform(7,12.5)
            if zone.theme == 'hill': height = rng.uniform(8,15)
            item = place(x,y,'canopy',tag,height,len(clusters)-1)
            if item:
                tree_count += 1
        # Denser, varied planting groups under/along the new canopy. Large
        # shrubs make aerial greenery legible; flowers stay physically small.
        for n,(cx,cy,_) in enumerate(canopy):
            for j in range(7):
                angle = rng.uniform(0,math.tau); distance = rng.uniform(2,6)
                x,y = cx+distance*math.cos(angle),cy+distance*math.sin(angle)
                role = 'understory' if j < 4 else 'groundcover'
                tag = rng.choice(['shrub_02','searsia','shrub']) if j < 4 else rng.choice(
                    ['grass_medium_02','flower_gazania','flower_heliophila','flower_ursinia','periwinkle'])
                place(x,y,role,tag,rng.uniform(1.1,2.1) if j < 4 else rng.uniform(.45,.85),n)
        if local:
            additions.extend(local)
            species = Counter(p.metadata['asset_id'] for p in local)
            counts.update(species); roles.update(p.metadata['planting_role'] for p in local)
            records.append({'zone_id':zone.id,'theme':zone.theme,'free_area_m2':round(free.area,1),
                            'trees':tree_count,'low_plants':len(local)-tree_count,'asset_counts':dict(species)})
    # A registry outage must not erase a previously successful planting pass.
    replaced = {r['zone_id'] for r in records}
    kept_old = [p for p in previous if p.metadata.get('greenery_zone') not in replaced]
    for p in additions:
        p.metadata['greenery_zone'] = p.metadata.get('parcel_id') or p.metadata.get('landscape_site') or 'edge_'+p.metadata['site']
    scene.primitives = base+kept_old+additions
    report = {'version':VERSION,'density':density,'zones':records,'changed_zones':len(records),
              'new_asset_instances':len(additions),'asset_counts':dict(counts),'role_counts':dict(roles),
              'retained_previous_instances':len(kept_old),'existing_primitives_modified':0,
              'placement_checks':'full fitted footprints inside dry free polygons; compiled paths and props excluded',
              'simulation_note':'visual foliage meshes; no new trunk colliders'}
    scene.metadata[KEY] = report
    return report
