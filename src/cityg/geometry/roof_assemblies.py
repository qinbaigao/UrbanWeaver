"""Roof-scale architectural assemblies, supported on the supplied actual plane."""
import math

from cityg.geometry.geography import polygon_mesh, primitive_footprint
from cityg.geometry.model import Vec3
from cityg.geometry.roof_surfaces import to_world
from cityg.polygons import geos


def furnish_roof_zone(compiler, building, prefix, kind, bounds, origin, angle, z, meta):
    s=geos();x0,y0,x1,y1=bounds;cx=(x0+x1)/2;cy=(y0+y1)/2
    pad=to_world(s.box(*bounds),origin,angle);items=[];co=math.cos(math.radians(angle));si=math.sin(math.radians(angle))
    def position(x,y,h):return Vec3(origin[0]+x*co-y*si,origin[1]+x*si+y*co,z+h)
    def add(p):
        if p and pad.buffer(1e-6).covers(primitive_footprint(p)):items.append(p)
    def box(name,x,y,h,w,d,t,material,solid=True):
        p=compiler._box(prefix+'_'+name,building.id,position(x,y,h+t/2),Vec3(w,d,t),angle,
            'roof_equipment' if solid else 'roof_surface_detail',material,'shell:'+building.id,
            collision_enabled=False,metadata={**meta,'assembly_part':name,'ground_obstacle':solid})
        add(p)
    def surface(name,shape,h,t,material):
        add(polygon_mesh(prefix+'_'+name,building.id,to_world(shape,origin,angle),z+h,t,
            'roof_surface_detail',material,layer='shell:'+building.id,metadata=meta))
    def asset(name,x,y,h,category,size,query,tags=(),yaw=0):
        p=compiler._outdoor_mesh(prefix+'_'+name,building.id,position(x,y,h+size[2]/2),Vec3(*size),angle+yaw,
            'roof_plant_asset' if category=='plant' else 'roof_furniture_asset',category,query,'shell:'+building.id,
            metadata={**meta,'ground_obstacle':True},required_asset_tags=tags,exclude_stylized=True)
        if p:p.collision_enabled=False
        add(p)
        return p if p in items else None

    surface('pad',s.box(*bounds),.06,.06,'roof_zone_paver' if kind in {'garden','terrace'} else 'roof_zone_gravel')
    if kind=='equipment':
        # Three ventilated units on plinths, plus a low screen; not giant cubes.
        for i,x in enumerate((cx-3.,cx,cx+3.) if x1-x0>=10 else (cx,)):
            box(f'plinth_{i}',x,cy+.5,.06,2.6,3.,.20,'roof_zone_paver')
            if i==1 or x1-x0<10:
                # These scanned units have wall brackets and a dangling pipe.
                # Their rear face rests against a real service backing wall;
                # do not mistake their bounding-box bottom for support feet.
                mounted=asset('wall_aircon',x,cy+.1,.26,'roof_hvac',(.484,1.035,1.2),
                              'exterior aircon unit',('exterior_aircon_unit',),yaw=-90)
                if mounted:
                    box('aircon_service_wall',x,cy+.492,.26,2.2,.30,1.4,'roof_unit_shell')
                    continue
            box(f'unit_{i}',x,cy+.5,.26,2.2,2.6,1.25,'roof_unit_shell')
            for side in (-1,1):
                for row in range(5):
                    box(f'louver_{i}_{side}_{row}',x,cy+.5+side*1.31,.42+row*.19,1.85,.035,.075,'roof_vent_dark')
            # Two shallow circular fan grilles on each unit top.
            for j,y in enumerate((cy-.12,cy+1.12)):
                surface(f'fan_{i}_{j}',s.Point(x,y).buffer(.43,quad_segs=10),1.54,.03,'roof_vent_dark')
                box(f'fan_bar_{i}_{j}',x,y,1.545,.74,.045,.025,'roof_unit_shell',False)
        if y1-y0>=8:
            box('pipe_tray',cx,cy-1.65,.06,min(8.5,x1-x0-2),.25,.18,'roof_unit_shell')
        screen_width=min(9.7,x1-x0-1.5);screen_y=min(cy+2.8,y1-.4)
        for side in (-1,1):
            box(f'screen_post_{side}',cx+side*(screen_width/2-.05),screen_y,.06,.12,.12,1.75,'roof_unit_shell')
        for i in range(8):
            box(f'screen_louver_{i}',cx,screen_y,.2+i*.20,screen_width,.10,.10,'roof_screen')
    elif kind=='solar':
        cols=max(1,int((x1-x0-1)/2.6));rows=max(1,int((y1-y0-2)/1.8))
        for row in range(rows):
            for col in range(cols):
                x=x0+.6+col*2.6+1.1;y=y0+2.+row*1.8
                # Genuine tilted faces, with supports touching their underside.
                for j,dy in enumerate((-.42,.42)):
                    height=.34+(dy+.55)*.26
                    box(f'rail_{row}_{col}_{j}',x,y+dy,.06,2.2,.10,height-.06,'roof_unit_shell')
                def height(wx,wy):
                    ly=-(wx-origin[0])*si+(wy-origin[1])*co
                    return z+.39+(ly-y+.55)*.26
                for name,w,d,mat,raise_by in [('frame',2.3,1.2,'roof_unit_shell',0),('cells',2.17,1.07,'roof_solar_cells',.012)]:
                    shape=to_world(s.box(x-w/2,y-d/2,x+w/2,y+d/2),origin,angle)
                    add(polygon_mesh(f'{prefix}_{name}_{row}_{col}',building.id,shape,
                        lambda a,b:height(a,b)+raise_by,.05 if name=='frame' else .012,
                        'roof_solar_panel',mat,layer='shell:'+building.id,metadata=meta))
    elif kind=='garden':
        # Broad planted islands read at aerial scale; real low vegetation adds
        # near-view volume without loading large rooftop trees across the city.
        for side in (-1,1):
            bx=cx+side*(x1-x0)/4
            soil=s.box(bx-(x1-x0)/4+.7,y0+2.,bx+(x1-x0)/4-.7,y1-.7)
            surface(f'bed_{side}',soil,.30,.24,'roof_plant_cover')
            surface(f'edge_{side}',soil.buffer(.13,join_style='mitre').difference(soil),.36,.30,'roof_zone_paver')
            a,b,c,d=soil.bounds
            for i in range(3):
                for j in range(3):
                    tag=('grass_medium_02','periwinkle','flower_ursinia')[(i+j)%3]
                    asset(f'plant_{side}_{i}_{j}',a+.65+i*(c-a-1.3)/2,b+.65+j*(d-b-1.3)/2,.30,
                          'plant',(.75,.75,.65),tag,(tag,))
    elif kind=='terrace':
        # Slatted shade and two benches; keep the front 1.5 m aisle unoccupied.
        for i,(x,y) in enumerate([(cx-3,cy-1),(cx+3,cy-1),(cx-3,cy+2.5),(cx+3,cy+2.5)]):
            box(f'post_{i}',x,y,.06,.17,.17,2.7,'furniture_wood_dark')
        for j,y in enumerate((cy-1,cy+2.5)):
            box(f'beam_{j}',cx,y,2.76,6.3,.20,.20,'furniture_wood_dark',False)
        for i in range(13):
            box(f'slat_{i}',cx-3+i*.5,cy+.75,2.96,.14,4.,.12,'furniture_wood',False)
        for i,x in enumerate((cx-1.8,cx+1.8)):
            asset(f'bench_{i}',x,cy+.6,.06,'street_bench',(1.85,.72,.88),'outdoor wood bench')
    return items
