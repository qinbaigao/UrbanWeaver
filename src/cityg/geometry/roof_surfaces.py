"""Recover exposed horizontal roof polygons from compiled geometry, not plans."""
from collections import defaultdict
import math

from shapely import affinity

from cityg.geometry.geography import primitive_footprint
from cityg.polygons import geos


def flat_top(p):
    """Reject slopes and imported meshes; preserve holes in explicit top faces."""
    s=geos()
    if p.metadata.get('roof_style') in {'pitched','gable','hip','tiled'} or p.metadata.get('resolved_asset'):
        return None
    if p.primitive_type=='box':
        return p.center.z+p.size.z/2,primitive_footprint(p)
    if p.primitive_type!='path_mesh':
        return None
    co,si=math.cos(math.radians(p.rotation_z_deg)),math.sin(math.radians(p.rotation_z_deg))
    vertices=[(p.center.x+v[0]*p.size.x*co-v[1]*p.size.y*si,
               p.center.y+v[0]*p.size.x*si+v[1]*p.size.y*co,
               p.center.z+v[2]*p.size.z) for v in p.metadata['mesh_vertices']]
    top=max(v[2] for v in vertices);faces=[]
    for tri in p.metadata['mesh_triangles']:
        points=[vertices[i] for i in tri]
        if all(abs(v[2]-top)<1e-5 for v in points):
            polygon=s.Polygon([(v[0],v[1]) for v in points])
            if polygon.area>1e-7:faces.append(polygon)
    if not faces:return None
    shape=s.union_all(faces)
    # A sloped/tiered cap with only a small horizontal patch is not a flat roof.
    if shape.area<primitive_footprint(p).area*.95:return None
    return top,shape


def roof_surfaces(primitives):
    s=geos();groups=defaultdict(list);sources=defaultdict(list)
    for p in primitives:
        if p.semantic_class!='roof':continue
        top=flat_top(p)
        if top:
            z,shape=top;key=round(z,5)
            groups[key].append(shape);sources[key].append(p.id)
    unions={z:s.union_all(parts) for z,parts in groups.items()}
    result=[]
    for z,shape in sorted(unions.items()):
        # Remove upper roof projection AND any solid rising through this plane.
        # This keeps podium equipment out of tower shafts and offset overhangs.
        covers=[other for h,other in unions.items() if h>z+.05]
        covers.extend(primitive_footprint(p) for p in primitives
            if p.semantic_class=='exterior_wall' and p.center.z-p.size.z/2<z+.05
            and p.center.z+p.size.z/2>z+.1)
        shape=shape.difference(s.union_all(covers))
        if shape.area>12:
            result.append({'z':z,'shape':shape,'source_ids':sorted(sources[z])})
    return result


def to_local(shape, origin, angle):
    return affinity.rotate(affinity.translate(shape,-origin[0],-origin[1]),-angle,origin=(0,0))


def to_world(shape, origin, angle):
    return affinity.translate(affinity.rotate(shape,angle,origin=(0,0)),origin[0],origin[1])
