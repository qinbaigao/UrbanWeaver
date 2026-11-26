"""Additive showcase landscapes: western park and an eastern terrain-backed hill.

Existing city geometry is untouched. Trails follow the triangulated heightfield;
terrain is a static collision mesh, not a claim of an extended robot route graph.
"""
from collections import Counter
import math
import random

from shapely.ops import nearest_points

from cityg.geometry.model import Vec3
from cityg.geometry.path_mesh import inline_mesh
from cityg.paths import PlanarPath2D
from cityg.polygons import geos, line_shape
from cityg.schemas import Bounds2D, Point2D
from cityg.serialization import to_primitive

VERSION = 'edge_landscape_v1'
KEY = 'edge_landscape_extension'


def plan_extension(city, west_m=260., east_m=340.):
    if KEY in city.metadata:
        raise ValueError('An edge extension already exists; edit its plan instead of extending twice')
    if min(west_m,east_m)<120 or city.bounds.depth<300:
        raise ValueError('Extension requires at least 120 m width and 300 m north-south extent')
    old=city.bounds; s=geos(); entries={}
    for side,x in [('west',old.min_x),('east',old.max_x)]:
        sign=-1 if side=='west' else 1; rows=[]
        for fraction in (.25,.5,.75):
            target=s.Point(x,old.min_y+old.depth*fraction)
            roads=[r for r in city.road_network.segments if r.sidewalk_width_m>0]
            if not roads:raise ValueError('Need existing perimeter sidewalks for access')
            road=min(roads,key=lambda r:line_shape(r.centerline).distance(target))
            point=nearest_points(target,line_shape(road.centerline))[1]
            if abs(point.x-x)>35:
                raise ValueError(f'No nearby {side} perimeter sidewalk')
            # Start inside the existing outer sidewalk, not in a traffic lane.
            root=(point.x+sign*(road.width_m/2+road.sidewalk_width_m*.65),point.y)
            rows.append({'road_id':road.id,'sidewalk_point':list(root)})
        entries[side]=rows
    city.bounds=Bounds2D(old.min_x-west_m,old.min_y,old.max_x+east_m,old.max_y)
    plan={'version':VERSION,'original_bounds':to_primitive(old),
          'park_bounds':to_primitive(Bounds2D(old.min_x-west_m,old.min_y,old.min_x,old.max_y)),
          'hill_bounds':to_primitive(Bounds2D(old.max_x,old.min_y,old.max_x+east_m,old.max_y)),
          'hill_height_m':54.,'grid_step_m':6.,'entrances':entries,
          'park_tree_count':300,'hill_tree_count':750,'seed':20261016,
          'layout_source':'explicit_showcase_edit','navigation_graph_extended':False}
    city.metadata[KEY]=plan
    return plan


class Heightfield:
    def __init__(self,bounds,height,step):
        self.bounds=Bounds2D(**bounds); b=self.bounds
        self.nx=math.ceil(b.width/step); self.ny=math.ceil(b.depth/step)
        self.dx=b.width/self.nx;self.dy=b.depth/self.ny
        self.points=[]
        for j in range(self.ny+1):
            v=j/self.ny
            for i in range(self.nx+1):
                u=i/self.nx
                z=height*math.sin(math.pi*u)**2*math.sin(math.pi*v)**2*(.85+.15*math.sin(math.tau*v+.4))
                self.points.append((b.min_x+i*self.dx,b.min_y+j*self.dy,z))
        self.faces=[]
        for j in range(self.ny):
            for i in range(self.nx):
                a=j*(self.nx+1)+i;d=a+self.nx+1
                self.faces.extend(((a,a+1,d+1),(a,d+1,d)))

    def __call__(self,x,y):
        b=self.bounds
        u=max(0.,min(self.nx-1e-8,(x-b.min_x)/self.dx));v=max(0.,min(self.ny-1e-8,(y-b.min_y)/self.dy))
        i,j=int(u),int(v);tx,ty=u-i,v-j;a=j*(self.nx+1)+i;d=a+self.nx+1
        z00,z10,z11,z01=[self.points[k][2] for k in (a,a+1,d+1,d)]
        if tx>=ty:return z00+(z10-z00)*tx+(z11-z10)*ty
        return z00+(z11-z01)*tx+(z01-z00)*ty


def terrain_meshes(city,field,prefix):
    points=list(field.points); n=len(points); points.extend((x,y,-.3) for x,y,z in field.points)
    faces=list(field.faces)+[(c+n,b+n,a+n) for a,b,c in field.faces]
    edge_counts=Counter(tuple(sorted((a,b))) for tri in field.faces for a,b in zip(tri,tri[1:]+tri[:1]))
    boundary=[(a,b) for tri in field.faces for a,b in zip(tri,tri[1:]+tri[:1])
              if edge_counts[tuple(sorted((a,b)))]==1]
    for a,b in boundary:
        faces.extend(((a,b+n,b),(a,a+n,b+n)))
    meta={'edge_landscape_system':VERSION,'site':prefix,'terrain':True}
    result=[inline_mesh(prefix+'_terrain',city.id,points,faces,'grass','grass',collision=True,metadata=meta)]
    # Large, gentle colour variation supplements metre-scaled PBR; no giant tile.
    groups={-1:[],1:[]}
    for tri in field.faces:
        x,y,z=(sum(field.points[i][axis] for i in tri)/3 for axis in range(3))
        noise=math.sin(x/47+y/93)+.6*math.cos(y/71-x/39)
        if noise>.6:groups[1].append(tri)
        elif noise<-.65:groups[-1].append(tri)
    for key,tris in groups.items():
        if tris:
            result.append(inline_mesh(prefix+f'_turf_{key}',city.id,
                [(x,y,z+.018) for x,y,z in field.points],tris,'grass',
                'grass_deep' if key==1 else 'grass_dry',collision=False,metadata=meta))
    return result


def draped_path(city,prefix,coords,width,height,site):
    path=PlanarPath2D(tuple(Point2D(*p) for p in coords))
    # Densification avoids an uphill segment cutting through a convex hillside.
    count=max(2,math.ceil(path.length/2.5))
    sampled=PlanarPath2D(tuple(path.point(path.length*i/count) for i in range(count+1)))
    left=sampled.offset_points(width/2);right=sampled.offset_points(-width/2)
    points=[]
    for a,b in zip(left,right):
        points.extend((p.x,p.y,height(p.x,p.y)+dz) for p,dz in ((a,.015),(b,.015),(a,.085),(b,.085)))
    faces=[]
    for i in range(count):
        a=4*i;b=a+4
        for q in ((a+2,a+3,b+3,b+2),(a,b,b+1,a+1),(a,a+2,b+2,b),(a+1,b+1,b+3,a+3)):
            faces.extend(((q[0],q[1],q[2]),(q[0],q[2],q[3])))
    faces.extend(((0,1,3),(0,3,2),(count*4,count*4+2,count*4+3),(count*4,count*4+3,count*4+1)))
    grades=[abs(height(a.x,a.y)-height(b.x,b.y))/max(math.hypot(a.x-b.x,a.y-b.y),1e-6)
            for a,b in zip(sampled.points,sampled.points[1:])]
    return inline_mesh(prefix,city.id,points,faces,'landscape_path','landscape_path',collision=True,
        metadata={'edge_landscape_system':VERSION,'site':site,'path_width_m':width,
                  'path_xy':coords,'max_grade':max(grades,default=0),'terrain_draped':True})


def compile_edge_landscape(compiler,city,scene):
    plan=city.metadata.get(KEY)
    if not plan:return None
    if plan.get('version')!=VERSION:raise ValueError('Unknown edge landscape plan')
    scene.primitives=[p for p in scene.primitives if p.metadata.get('edge_landscape_system')!=VERSION]
    s=geos();rng=random.Random(plan['seed']); added=[];asset_counts=Counter();sites=[]
    for side in ('park','hill'):
        bounds=Bounds2D(**plan[side+'_bounds']);b=bounds;cx,cy=b.center.x,b.center.y
        field=Heightfield(plan[side+'_bounds'],plan['hill_height_m'] if side=='hill' else 0,plan['grid_step_m'])
        added.extend(terrain_meshes(city,field,'edge_'+side))
        routes=[];plazas=[]
        if side=='park':
            loop=[(cx+b.width*.32*math.sin(t)*(1+.08*math.cos(3*t)),
                   cy+b.depth*.42*math.cos(t)) for t in (i*math.tau/180 for i in range(181))]
            routes.append(loop);line=s.LineString(loop)
            for entry in plan['entrances']['west']:
                root=entry['sidewalk_point'];end=nearest_points(s.Point(root),line)[1]
                routes.append([root,[b.max_x-22,root[1]],[end.x,end.y]])
                plazas.append((b.max_x-25,root[1],10.))
            # A central garden cross-path links both arms of the loop.
            routes.append([(cx-b.width*.32,cy),(cx,cy+14),(cx+b.width*.32,cy)])
            plazas.append((cx,cy+14,15.))
        else:
            foot=[(b.min_x+22+6*math.sin(i/50*math.tau),b.min_y+b.depth*(.08+.84*i/50)) for i in range(51)]
            routes.append(foot)
            for entry in plan['entrances']['east']:
                root=entry['sidewalk_point'];end=nearest_points(s.Point(root),s.LineString(foot))[1]
                routes.append([root,[end.x,end.y]])
                plazas.append((b.min_x+23,root[1],7.))
            peak=max(field.points,key=lambda p:p[2]); px,py,_=peak
            routes.append([(foot[12][0],foot[12][1]),(b.min_x+b.width*.20,b.min_y+b.depth*.25),
                (b.min_x+b.width*.28,b.min_y+b.depth*.72),
                (b.min_x+b.width*.38,b.min_y+b.depth*.32),
                (b.min_x+b.width*.48,b.min_y+b.depth*.68),(px,py)])
            plazas.append((px,py,8.))
        for i,route in enumerate(routes):
            added.append(draped_path(city,f'edge_{side}_path_{i:02}',route,3.6 if side=='park' else 2.5,field,side))
        # Viewpoint/garden pads follow the same triangular surface as the terrain.
        for i,(x,y,radius) in enumerate(plazas):
            # Dense radial rings retain the hill's curvature under the pad.
            vertices=[(x,y,field(x,y)+.09)]
            for ring in range(1,9):
                for k in range(80):
                    xx=x+radius*ring/8*math.cos(k*math.tau/80);yy=y+radius*ring/8*math.sin(k*math.tau/80)
                    vertices.append((xx,yy,field(xx,yy)+.09))
            faces=[(0,1+k,1+(k+1)%80) for k in range(80)]
            for ring in range(1,8):
                for k in range(80):
                    a=1+(ring-1)*80+k;bn=1+(ring-1)*80+(k+1)%80;c=a+80;d=bn+80
                    faces.extend(((a,c,d),(a,d,bn)))
            added.append(inline_mesh(f'edge_{side}_plaza_{i}',city.id,vertices,faces,'plaza','plaza_paving',collision=False,
                metadata={'edge_landscape_system':VERSION,'site':side}))
            for k in range(4 if side=='park' else 2):
                angle=k*math.tau/(4 if side=='park' else 2)+.6
                bx=x+(radius-2)*math.cos(angle);by=y+(radius-2)*math.sin(angle)
                item=compiler._outdoor_mesh(f'edge_{side}_bench_{i}_{k}',city.id,
                    Vec3(bx,by,field(bx,by)+.5),Vec3(2.4,.9,1),math.degrees(angle)+180,
                    'bench','street_bench','outdoor wood metal seating','roads',exclude_stylized=True,
                    metadata={'edge_landscape_system':VERSION,'site':side})
                if item:added.append(item);asset_counts[item.metadata['asset_id']]+=1
        blocked=s.union_all([s.LineString(route).buffer(6.5) for route in routes]+
                            [s.Point(x,y).buffer(r+3) for x,y,r in plazas])
        meadow=s.Point(cx-b.width*.05,cy-b.depth*.21).buffer(1)
        from shapely.affinity import scale
        meadow=scale(meadow,b.width*.22,b.depth*.10,origin=(cx-b.width*.05,cy-b.depth*.21))
        tree_points=[];target=plan[side+'_tree_count'];tries=0
        species=['jacaranda','island','island','quiver','tree_small'] if side=='park' else ['pine','pine','fir','island','tree_small']
        while len(tree_points)<target and tries<target*22:
            tries+=1;x=rng.uniform(b.min_x+10,b.max_x-10);y=rng.uniform(b.min_y+12,b.max_y-12)
            # Soft woodland clusters, rather than rows or a uniform lattice.
            density=.55+.28*math.sin(x/36+y/87)+.15*math.cos(y/29)
            if rng.random()>density or blocked.contains(s.Point(x,y)):continue
            if side=='park' and meadow.contains(s.Point(x,y)):continue
            spacing=7 if side=='hill' else 9
            if any((x-xx)**2+(y-yy)**2<spacing**2 for xx,yy in tree_points):continue
            i=len(tree_points);tag=species[i%len(species)]
            tags=('small',) if tag=='tree_small' else (tag,)
            height=rng.uniform(8,15) if side=='hill' else rng.uniform(7,12)
            item=compiler._outdoor_mesh(f'edge_{side}_tree_{i:04}',city.id,
                Vec3(x,y,field(x,y)+height/2),Vec3(12,12,height),rng.uniform(0,360),
                'park_tree_asset','park_tree',tag.replace('_',' ')+' tree','roads',required_asset_tags=tags,
                exclude_stylized=True,metadata={'edge_landscape_system':VERSION,'site':side,
                    'terrain_contact_z':field(x,y)})
            if item:
                added.append(item);tree_points.append((x,y));asset_counts[item.metadata['asset_id']]+=1
            # Missing species must not stall forever on the same slot.
            elif tries>target*2:break
        # Small planted clusters around park rest nodes, not empty concrete discs.
        if side=='park':
            for i,(x,y,r) in enumerate(plazas):
                for k in range(18):
                    angle=k*math.tau/18;px=x+(r+5.2)*math.cos(angle);py=y+(r+5.2)*math.sin(angle)
                    if blocked.contains(s.Point(px,py)):continue
                    item=compiler._outdoor_mesh(f'edge_park_flower_{i}_{k}',city.id,
                        Vec3(px,py,.45),Vec3(1.4,1.4,.9),k*31,'parcel_plant_asset','plant',
                        'outdoor flower flowering plant','roads',exclude_stylized=True,
                        metadata={'edge_landscape_system':VERSION,'site':side})
                    if item:added.append(item);asset_counts[item.metadata['asset_id']]+=1
        sites.append({'side':side,'bounds':to_primitive(bounds),'tree_count':len(tree_points),
            'path_count':len(routes),'plaza_count':len(plazas),'max_height_m':max(p[2] for p in field.points)})
    scene.primitives.extend(added)
    report={'version':VERSION,'sites':sites,'asset_counts':dict(asset_counts),
            'new_primitives':len(added),'new_asset_instances':sum(asset_counts.values()),
            'maximum_trail_grade':max((p.metadata.get('max_grade',0) for p in added),default=0),
            'existing_primitives_modified':0,'navigation_graph_extended':False,
            'terrain_collision':True,'physics_runtime_tested':False}
    scene.metadata[KEY]=report
    return report
