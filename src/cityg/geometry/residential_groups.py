"""Opt-in attached housing envelope and connected shared gardens."""
from dataclasses import replace

from cityg.geometry.facade_colorways import owner_buildings
from cityg.geometry.geography import polygon_mesh, primitive_footprint
from cityg.geometry.model import MaterialSpec
from cityg.geometry.path_mesh import inline_mesh
from cityg.polygons import geos


def compile_attached_envelopes(city, scene):
    present = {p.owner_id for p in scene.primitives if p.semantic_class == 'roof'}
    buildings = {b.id:b for b in city.iter_buildings()
                 if b.id in present and b.metadata.get('residential_group', {}).get('kind') == 'townhouses'}
    if not buildings:
        return
    all_buildings = {b.id:b for b in city.iter_buildings()}
    for b in buildings.values():
        group = b.metadata['residential_group']
        if abs(float(b.metadata.get('orientation_deg',0))) > 1e-6:
            raise ValueError('Attached rows require joint rotation/replanning: '+b.id)
        for side in group['party_sides']:
            neighbor = all_buildings.get(group.get('neighbors',{}).get(side))
            if neighbor is None:
                raise ValueError('Missing party-wall neighbor: '+b.id)
            a, c = b.footprint, neighbor.footprint
            edge, opposite = (a.min_x,c.max_x) if side == 'west' else (a.max_x,c.min_x)
            if (abs(edge-opposite)>1e-6 or abs(a.min_y-c.min_y)>1e-6 or abs(a.max_y-c.max_y)>1e-6
                or abs(max(f.elevation_m+f.height_m for f in b.floors)
                       -max(f.elevation_m+f.height_m for f in neighbor.floors))>1e-6):
                raise ValueError('Attached neighbors no longer share a complete wall: '+b.id)
    owners = owner_buildings(city)
    def retained(p):
        b = buildings.get(owners.get(p.owner_id))
        if b is None:
            return True
        if p.semantic_class == 'roof' or p.metadata.get('roof_detail'):
            return False
        return p.metadata.get('facade_side') not in b.metadata['residential_group']['party_sides']
    scene.primitives = [p for p in scene.primitives if retained(p)]
    source = next((m for m in scene.materials if m.id == 'facade_frame_stone'), MaterialSpec('stone', (.4,.4,.4)))
    mid = 'townhouse_slate_roof'
    if not any(m.id == mid for m in scene.materials):
        scene.materials.append(replace(source, id=mid, base_color_path=None,
            display_color=(.19,.24,.27), texture_scale_m=1.4, roughness=.83))
    for b in buildings.values():
        f = b.footprint; top = max(f.elevation_m+f.height_m for f in b.floors)
        # East-west continuous ridge. No overhang across a party-wall boundary.
        group = b.metadata['residential_group']; sides = group['party_sides']
        x0, x1 = f.min_x-(.25 if 'west' not in sides else 0), f.max_x+(.25 if 'east' not in sides else 0)
        y0, y1, ym = f.min_y-.38, f.max_y+.38, f.center.y
        z, ridge = top+.12, top+2.9
        vertices = [(x,y,h) for x in (x0,x1) for y,h in [(y0,z),(ym,ridge),(y1,z)]]
        faces = [(0,3,4),(0,4,1),(1,4,5),(1,5,2),(0,1,2),(3,5,4),(0,2,5),(0,5,3)]
        # Independent face vertices retain hard roof ridges in both the Viewer
        # and USD consumers that otherwise average normals across shared edges.
        vertices = [vertices[i] for face in faces for i in face]
        faces = [tuple(range(i,i+3)) for i in range(0,len(vertices),3)]
        roof = inline_mesh(b.id+'_gable_roof', b.id, vertices, faces, 'roof', mid,
                          metadata={'roof_style':'gable', 'residential_group':group, 'building_id':b.id})
        roof.layer_id = 'shell:'+b.id; scene.primitives.append(roof)


def compile_group_paths(compiler, city, scene):
    """Routes have continuous width clearance; landscape is trimmed around them.

    This authors exterior pedestrian surfaces, not a certified accessibility plan.
    Connectors are owned by parcels so incremental replacement stays local.
    """
    s = geos(); routes = []; records = []
    grouped = {b.id for b in city.iter_buildings() if b.metadata.get('residential_group')}
    scene.primitives = [p for p in scene.primitives if not p.metadata.get('residential_group_paths')
        and not (p.metadata.get('building_id') in grouped and p.metadata.get('frontage_role'))]
    from cityg.planning.group_access import group_access_valid
    for parcel in city.iter_parcels():
        if not any(b.metadata.get('residential_group') for b in parcel.buildings):
            continue
        all_paths = []; paths = []
        for b in parcel.buildings:
            if not group_access_valid(city,b):
                raise ValueError('Invalid authored group path: '+b.id)
            access = b.metadata['group_access']; path = access['points']
            surface = s.LineString(path).buffer(access['width_m']/2, cap_style='flat', quad_segs=4)
            all_paths.append(surface); paths.append({'building_id':b.id,'path':path,'entrance':[b.entrance.x,b.entrance.y]})
        network = s.union_all(all_paths)
        meta = {'parcel_id':parcel.id, 'residential_group_paths':True, 'site_detail':True,
                'path_width_m':2., 'connected_to_sidewalk':True, 'routes':paths,
                'building_ids':[b.id for b in parcel.buildings]}
        p = polygon_mesh(parcel.id+'_group_paths',parcel.id,network,.13,.08,
                         'frontage_connector','permeable_paver',metadata=meta)
        routes.append(p); records.append({'parcel_id':parcel.id,'connected_entrances':len(paths)})
        # Preserve the ground, but not trees, huts or flower beds obstructing paths.
        protected = network.buffer(.25)
        scene.primitives = [p for p in scene.primitives if not (p.owner_id == parcel.id
            and p.semantic_class != 'parcel_ground' and p.center.z+p.size.z/2 > .15
            and primitive_footprint(p).intersects(protected))]
    scene.primitives.extend(routes)
    scene.metadata['residential_group_paths'] = records
    return records
