"""Explicit, reversible conversion of whole building parcels into static worksites.

Construction equipment is visual/static geometry, not an operable crane or a
construction simulator. Canonical buildings and their navigation are retired.
"""
from dataclasses import replace
import math

from cityg.geometry.geography import polygon_mesh, primitive_footprint
from cityg.geometry.incremental import entity_building_index
from cityg.geometry.model import MaterialSpec, Vec3
from cityg.geometry.path_mesh import inline_mesh
from cityg.polygons import geos, parcel_shape, line_shape
from cityg.serialization import to_primitive

KEY = 'construction_sites'
VERSION = 'static_construction_sites_v1'


def plan_construction_sites(city, building_ids):
    """Validate every target before removing anything; reserve dedicated parcels."""
    if city.metadata.get(KEY):
        raise ValueError('Construction plan already exists; edit that plan instead')
    wanted = set(building_ids)
    if not wanted or len(wanted) != len(building_ids):
        raise ValueError('Provide distinct building IDs')
    index = entity_building_index(city)
    records = []
    for district in city.districts:
        for parcel in district.parcels:
            for building in parcel.buildings:
                if building.id not in wanted:
                    continue
                if len(parcel.buildings) != 1:
                    raise ValueError(f'{parcel.id} is shared; whole-parcel conversion refused')
                shape = parcel_shape(parcel).buffer(-2)
                x0, y0, x1, y1 = shape.bounds
                # A conservative rectangle inside a possibly sloping parcel.
                for inset in range(20):
                    rect = geos().box(x0+inset, y0+inset, x1-inset, y1-inset)
                    if shape.covers(rect):
                        break
                else:
                    raise ValueError(f'No safe construction envelope in {parcel.id}')
                a, b, c, d = rect.bounds
                if c-a < 48 or d-b < 38:
                    raise ValueError(f'{parcel.id} is too small for this worksite kit')
                records.append(dict(id=f'construction_{building.id}', parcel_id=parcel.id,
                    district_id=district.id, replaced_building_id=building.id,
                    retired_entity_ids=sorted(k for k, v in index.items() if v == building.id),
                    work_bounds=list(rect.bounds), original_footprint=to_primitive(building.footprint),
                    completed_levels=6 if len(records) % 2 == 0 else 3,
                    entrance_side='west', equipment_operable=False))
    if {r['replaced_building_id'] for r in records} != wanted:
        raise ValueError('Some requested buildings do not exist')
    for parcel in city.iter_parcels():
        parcel.buildings[:] = [b for b in parcel.buildings if b.id not in wanted]
    scope = city.metadata.get('interior_scope', {}).get('building_levels', {})
    for bid in wanted:
        scope.pop(bid, None)
    city.metadata[KEY] = dict(version=VERSION, sites=records,
        source='explicit_showcase_edit', navigation_into_sites=False)
    return city.metadata[KEY]


def _materials(scene):
    current = {m.id: m for m in scene.materials}
    specs = [MaterialSpec('construction_steel', (.25, .28, .29), .65, .65),
        MaterialSpec('construction_yellow', (.94, .59, .07), .52, .35),
        MaterialSpec('construction_hoarding', (.18, .37, .48), .72, .15),
        MaterialSpec('construction_white', (.79, .82, .79), .8),
        MaterialSpec('construction_timber', (.56, .38, .19), .95),
        MaterialSpec('construction_brick', (.51, .26, .16), .95),
        MaterialSpec('construction_net', (.15, .40, .32), .95, opacity=.45),
        MaterialSpec('construction_glass', (.18, .30, .36), .3, .3)]
    base = current.get('service_concrete_light', current.get('concrete'))
    specs.append(replace(base, id='construction_concrete', display_color=(.61, .61, .56))
                 if base else MaterialSpec('construction_concrete', (.61, .61, .56)))
    gravel = current.get('gravel_warm')
    specs.append(replace(gravel, id='construction_ground', display_color=(.58, .48, .34))
                 if gravel else MaterialSpec('construction_ground', (.58, .48, .34)))
    scene.materials.extend(m for m in specs if m.id not in current)


class SiteBuilder:
    def __init__(self, compiler, record):
        self.compiler = compiler
        self.record = record
        self.owner = record['parcel_id']
        self.prefix = record['id']
        self.primitives = []
        self.beams = {}

    def metadata(self, **extra):
        return dict(construction_system=VERSION, construction_site=self.prefix,
                    parcel_id=self.owner, static_showcase=True, **extra)

    def box(self, role, center, size, material, yaw=0, collision=True):
        p = self.compiler._box(f'{self.prefix}_{role}', self.owner, Vec3(*center), Vec3(*size),
            yaw, 'construction_'+role.split('_')[0], material, 'roads',
            collision_enabled=collision, metadata=self.metadata(role=role))
        self.primitives.append(p)
        return p

    def beam(self, a, b, radius=.07, material='construction_yellow'):
        """A genuinely diagonal square-section member, batched by material."""
        delta = [b[i]-a[i] for i in range(3)]
        length = math.sqrt(sum(x*x for x in delta))
        if length < 1e-6:
            return
        axis = [x/length for x in delta]
        def cross(u, v):
            return [u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0]]
        u = cross(axis, [0, 0, 1] if abs(axis[2]) < .9 else [0, 1, 0])
        scale = math.sqrt(sum(x*x for x in u)); u = [x/scale*radius for x in u]
        v = cross(axis, u)
        vertices, faces = self.beams.setdefault(material, ([], [])); offset = len(vertices)
        for p in (a, b):
            for s, t in [(-1,-1), (1,-1), (1,1), (-1,1)]:
                vertices.append([p[i]+s*u[i]+t*v[i] for i in range(3)])
        for quad in [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]:
            faces.extend(tuple(offset+i for i in tri) for tri in
                         [(quad[0],quad[1],quad[2]), (quad[0],quad[2],quad[3])])

    def finish(self):
        for material, (vertices, faces) in self.beams.items():
            self.primitives.append(inline_mesh(f'{self.prefix}_members_{material}', self.owner,
                vertices, faces, 'construction_frame', material, collision=True,
                metadata=self.metadata(role='batched_structural_members')))
        return self.primitives

    def asset(self, key, x, y, yaw=0, scale=1, mast_anchor=False):
        record=self.compiler.asset_registry.get('construction_innerscene_'+key)
        if not (record and record.geometry_path and record.dimensions_m
                and record.metadata.get('outdoor_pack_status')=='ready'
                and record.metadata.get('visual_review',{}).get('status')=='accepted'
                and self.compiler.asset_registry.resolve_path(record.geometry_path).is_file()):
            return False
        sx,sy,sz=[v*scale for v in record.dimensions_m]
        if mast_anchor:
            fraction=record.metadata.get('mast_anchor_x_fraction')
            if fraction is None:return False
            x-=fraction*sx*math.cos(math.radians(yaw))
            y-=fraction*sx*math.sin(math.radians(yaw))
        p=self.compiler._mesh(f'{self.prefix}_asset_{key}_{len(self.primitives)}',self.owner,
            Vec3(x,y,.18+sz/2),Vec3(sx,sy,sz),yaw,'construction_equipment','construction_white','roads',
            instance_key='asset_'+record.asset_id,metadata=self.metadata(resolved_asset=True,
                asset_id=record.asset_id,asset_category=record.category,asset_source=record.source,
                asset_license=record.license_id,asset_geometry_path=str(self.compiler.asset_registry.resolve_path(record.geometry_path)),
                equipment_operable=False,scale_factor=scale))
        if not geos().box(*self.record['work_bounds']).covers(primitive_footprint(p)):
            return False
        self.primitives.append(p)
        return True


def _crane(builder, x, y, height, reach):
    b = builder; z = height
    b.box('crane_base', (x,y,.7), (5,5,1.1), 'construction_concrete')
    for dx, dy in [(-.85,-.85),(.85,-.85),(.85,.85),(-.85,.85)]:
        b.beam((x+dx,y+dy,1.1),(x+dx,y+dy,z),.11)
    for k in range(math.ceil((z-1.1)/2.5)):
        low=1.1+k*2.5; high=min(z,low+2.5)
        corners=[(x-.85,y-.85),(x+.85,y-.85),(x+.85,y+.85),(x-.85,y+.85)]
        for a,c in zip(corners,corners[1:]+corners[:1]):
            b.beam((*a,low),(*c,high),.055)
            b.beam((*a,high),(*c,high),.06)
    # Horizontal triangular lattice jib, counter-jib, cables and cabin.
    left=x-10; right=x+reach
    for yy,zz in [(y-.8,z),(y+.8,z),(y,z+1.8)]:
        b.beam((left,yy,zz),(right,yy,zz),.10)
    for k in range(math.ceil((right-left)/3)):
        a=left+k*3; c=min(right,a+3)
        for yy in (y-.8,y+.8):
            b.beam((a,yy,z),(c,y,z+1.8),.06)
            b.beam((a,y,z+1.8),(c,yy,z),.06)
        b.beam((a,y-.8,z),(a,y+.8,z),.06)
    b.beam((x,y,z),(x,y,z+6),.14)
    for xx in (left+1, x+reach*.75):
        b.beam((x,y,z+6),(xx,y,z+1.8),.035,'construction_steel')
    b.box('crane_counterweight',(left+2,y,z+.4),(4,2.4,.8),'construction_concrete')
    b.box('crane_cabin',(x+2,y-1,z-.5),(2.6,2,2.2),'construction_yellow')
    b.box('crane_window',(x+2,y-2.02,z-.2),(2.1,.04,1.2),'construction_glass')
    hook=x+reach*.65
    b.beam((hook,y,z),(hook,y,z-9),.03,'construction_steel')
    b.box('crane_hook',(hook,y,z-9),( .38,.3,.65),'construction_steel')


def _build_site(compiler, city, parcel, record):
    s=geos(); b=SiteBuilder(compiler,record)
    x0,y0,x1,y1=record['work_bounds']; w=x1-x0; d=y1-y0
    cx=x0+w*.60; cy=y0+d*.55
    fw=min(52,w*.48); fd=min(32,d*.48); levels=record['completed_levels']; step=3.6
    fx0,fx1=cx-fw/2,cx+fw/2; fy0,fy1=cy-fd/2,cy+fd/2
    ground=polygon_mesh(record['id']+'_ground',parcel.id,parcel_shape(parcel).buffer(-.25),.16,.16,
        'construction_ground','construction_ground',collision=True,metadata=b.metadata())
    b.primitives.append(ground)
    # Gate on the west frontage. The connector reaches the existing sidewalk,
    # but does not manufacture a traversable indoor/robot navigation route.
    shape=parcel_shape(parcel).buffer(-1.3); gate_y=cy
    gate=s.box(x0-20,gate_y-4,x0+10,gate_y+4)
    fence=shape.boundary.buffer(.10,cap_style='flat').difference(gate)
    b.primitives.append(polygon_mesh(record['id']+'_fence',parcel.id,fence,2.6,2.4,
        'construction_fence','construction_hoarding',collision=True,metadata=b.metadata()))
    perimeter=list(shape.exterior.coords)
    for i,(a,c) in enumerate(zip(perimeter,perimeter[1:])):
        count=max(1,math.ceil(math.dist(a,c)/3))
        for j in range(count):
            px=a[0]+(c[0]-a[0])*j/count;py=a[1]+(c[1]-a[1])*j/count
            if gate.contains(s.Point(px,py)):continue
            b.box(f'fencepost_{i}_{j}',(px,py,1.45),(.14,.14,2.7),'construction_white')
    from shapely.ops import nearest_points
    roads=[r for r in city.road_network.segments if r.sidewalk_width_m>0]
    if roads:
        point=s.Point(x0,gate_y); road=min(roads,key=lambda r:line_shape(r.centerline).distance(point))
        root=nearest_points(point,line_shape(road.centerline))[1]
        dx,dy=point.x-root.x,point.y-root.y; length=math.hypot(dx,dy)
        offset=road.width_m/2+road.sidewalk_width_m*.65
        start=(root.x+dx/length*offset,root.y+dy/length*offset)
        end=(fx0-4,gate_y)
        route=s.LineString([start,(x0+3,gate_y),end]).buffer(3,cap_style='flat')
        b.primitives.append(polygon_mesh(record['id']+'_access',parcel.id,route,.19,.08,
            'construction_access','service_concrete_dark' if compiler.material_library else 'construction_concrete',
            collision=True,metadata=b.metadata(route=[start,end],width_m=6)))
    # Repeated structural bays, open facades and a partially cast upper slab.
    nx=max(2,math.ceil(fw/8));ny=max(2,math.ceil(fd/7))
    xs=[fx0+fw*i/nx for i in range(nx+1)]; ys=[fy0+fd*j/ny for j in range(ny+1)]
    for level in range(levels+1):
        z=.28+level*step
        slab=s.box(fx0-.3,fy0-.3,fx1+.3,fy1+.3)
        if level==levels:slab=slab.intersection(s.box(fx0-1,fy0-1,cx+fw*.12,fy1+1))
        slab=slab.difference(s.box(cx-2,cy-2,cx+2,cy+2)) if level else slab
        b.primitives.append(polygon_mesh(f'{record["id"]}_slab_{level}',parcel.id,slab,z+.24,.24,
            'construction_slab','construction_concrete',collision=True,metadata=b.metadata(level=level)))
        if level<levels:
            for i,x in enumerate(xs):
                for j,y in enumerate(ys):
                    b.box(f'column_{level}_{i}_{j}',(x,y,z+step/2+.12),(.60,.60,step),'construction_concrete')
            for y in ys:b.box(f'beamx_{level}_{y:.2f}',(cx,y,z+step-.15),(fw,.38,.55),'construction_concrete')
            for x in xs:b.box(f'beamy_{level}_{x:.2f}',(x,cy,z+step-.15),(.38,fd,.55),'construction_concrete')
        else:
            for i,x in enumerate(xs):
                for j,y in enumerate(ys):
                    for dx,dy in [(-.17,-.17),(.17,.17)]:
                        b.beam((x+dx,y+dy,z+.25),(x+dx,y+dy,z+1.5),.023,'construction_steel')
    for x in (cx-2.25,cx+2.25):
        b.box(f'core_{x:.2f}',(x,cy,.28+levels*step/2),(.35,4.5,levels*step),'construction_concrete')
    # Incomplete green safety screens and scaffold along one face only.
    for k in range(math.ceil(fw/3)):
        x=fx0+k*3
        b.beam((x,fy0-1,.25),(x,fy0-1,levels*step+.8),.045,'construction_steel')
    for level in range(1,levels+1):
        z=.28+level*step
        b.beam((fx0,fy0-1,z),(fx1,fy0-1,z),.045,'construction_steel')
        if level>=levels-1:
            b.box(f'safetynet_{level}',(cx-fw*.12,fy0-1,z-1.5),(fw*.72,.04,2.8),'construction_net',collision=False)
    crane=compiler.asset_registry.get('construction_innerscene_tower_crane')
    crane_scale=(levels*step+13)/crane.dimensions_m[2] if crane and crane.dimensions_m else 1
    # Keep the static suspended hook over the northern staging strip, not
    # intersecting the partially cast slabs; ground anchor is the mast, not bbox.
    if not b.asset('tower_crane',fx0-9,fy1+5,scale=crane_scale,mast_anchor=True):
        _crane(b,fx0-9,cy,levels*step+13,min(fw*.85,x1-(fx0-9)-4))
    # Site office, stacked timber, brick pallets, steel stock and gravel heaps.
    ox=x0+w*.20; oy=y0+6
    if not b.asset('site_cabin',ox,oy):
        b.box('office',(ox,oy,1.7),(9,3.4,3),'construction_white')
        b.box('office_roof',(ox,oy,3.3),(9.4,3.8,.18),'construction_hoarding')
        for k in range(3):
            b.box(f'office_window_{k}',(ox-3+k*2.4,oy+1.72,1.9),(1.4,.05,1.0),'construction_glass')
        b.box('office_door',(ox+3.5,oy+1.73,1.25),(.9,.06,2.1),'construction_hoarding')
    b.asset('backhoe_loader',x0+18,y1-21,-15)
    b.asset('dump_truck',x0+w*.52,y0+d*.20,180)
    b.asset('concrete_mixer',x0+w*.78,y0+d*.20,180)
    b.asset('mobile_scaffold',fx1+4,cy,180)
    b.asset('site_toilet',x0+8,y0+6)
    b.asset('site_toilet',x0+8,y0+9)
    for k in range(10):
        b.box(f'timber_{k}',(x0+w*.43, y0+4+(k%5)*.5,.35+(k//5)*.3),(6,.42,.24),'construction_timber')
    for k in range(12):
        b.box(f'brick_{k}',(x0+w*.62+(k%4)*1.5,y0+4+(k//4)*1.5,.65),(1.2,1.2,1),'construction_brick')
    for k in range(9):
        b.beam((x0+w*.80,y0+4+k*.2,.4),(x0+w*.80+7,y0+4+k*.2,.4),.065,'construction_steel')
    for k in range(2):
        hx=x0+12+k*9;hy=y1-8
        vertices=[(hx,hy,2.0)]+[(hx+3.5*math.cos(i*math.tau/12),hy+3*math.sin(i*math.tau/12),.18) for i in range(12)]
        vertices.append((hx,hy,.18))
        faces=[(0,1+i,1+(i+1)%12) for i in range(12)]+[(13,1+(i+1)%12,1+i) for i in range(12)]
        b.primitives.append(inline_mesh(f'{record["id"]}_aggregate_{k}',parcel.id,vertices,faces,
            'construction_aggregate','construction_ground',metadata=b.metadata()))
    worker=compiler.asset_registry.get('converted_v3_construction_male_01_standing')
    if worker and worker.geometry_path and compiler.asset_registry.resolve_path(worker.geometry_path).is_file():
        for i,(x,y) in enumerate([(fx0-3,fy0-3),(fx1+3,fy0-2),(ox-2,oy+4)]):
            sx,sy,sz=worker.dimensions_m
            b.primitives.append(compiler._mesh(f'{record["id"]}_worker_{i}',parcel.id,Vec3(x,y,.18+sz/2),
                Vec3(sx,sy,sz),i*110,'construction_worker','construction_white','roads',
                instance_key=f'asset_{worker.asset_id}',metadata=b.metadata(resolved_asset=True,
                    asset_id=worker.asset_id,asset_category=worker.category,asset_source=worker.source,
                    asset_license=worker.license_id,asset_geometry_path=str(compiler.asset_registry.resolve_path(worker.geometry_path)))))
    return b.finish()


def compile_construction_sites(compiler, city, scene):
    plan=city.metadata.get(KEY)
    if not plan:return None
    if plan.get('version')!=VERSION:raise ValueError('Unknown construction plan version')
    parcels={p.id:p for p in city.iter_parcels()}
    records=plan['sites']; target_parcels={r['parcel_id'] for r in records}
    retired={eid for r in records for eid in r['retired_entity_ids']}
    for r in records:
        if r['parcel_id'] not in parcels or parcels[r['parcel_id']].buildings:
            raise ValueError('Construction parcels must exist and contain no finished buildings')
    if any(p.owner_id in target_parcels and p.metadata.get('metro_system') for p in scene.primitives):
        raise ValueError('Refusing to remove a metro entrance; an explicit relocation is needed')
    removed=[]; kept=[]
    for p in scene.primitives:
        if (p.owner_id in retired|target_parcels or p.metadata.get('building_id') in retired
            or p.metadata.get('construction_system')==VERSION):removed.append(p.id)
        else:kept.append(p)
    scene.primitives=kept
    scene.layers=[l for l in scene.layers if l.owner_id not in retired]
    scene.state_machines=[m for m in scene.state_machines if m.owner_id not in retired]
    machines={m.id for m in scene.state_machines}
    scene.navigation.nodes=[n for n in scene.navigation.nodes if n.owner_id not in retired]
    nodes={n.id for n in scene.navigation.nodes}
    scene.navigation.edges=[e for e in scene.navigation.edges if e.start_node_id in nodes and e.end_node_id in nodes
        and (not e.condition_state_machine_id or e.condition_state_machine_id in machines)]
    scene.building_prototypes={k:v for k,v in scene.building_prototypes.items() if k not in retired}
    for key in ('exterior_only_building_ids','compiled_building_ids'):
        if key in scene.metadata:scene.metadata[key]=[x for x in scene.metadata[key] if x not in retired]
    _materials(scene)
    added=[]
    for r in records:added.extend(_build_site(compiler,city,parcels[r['parcel_id']],r))
    scene.primitives.extend(added)
    from collections import Counter
    report=dict(version=VERSION,sites=records,removed_primitive_ids=removed,new_primitives=len(added),
        retired_entity_count=len(retired),building_count=sum(1 for _ in city.iter_buildings()),
        equipment_operable=False,physics_runtime_tested=False,navigation_into_sites=False,
        asset_counts=dict(Counter(p.metadata['asset_id'] for p in added if p.metadata.get('resolved_asset'))))
    scene.metadata[KEY]=report
    return report
