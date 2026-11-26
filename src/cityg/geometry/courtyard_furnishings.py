"""Human-scale exterior groups with a reserved two-metre circulation spine.

Real local GLBs for plants/people/street furniture; authored geometry for timber
tables, shade structures, edging and small closed kiosks. No generated proxies
are substituted when a textured plant or person is missing.
"""
import math

from cityg.geometry.geography import polygon_mesh, primitive_footprint
from cityg.geometry.model import Vec3
from cityg.geometry.path_mesh import inline_mesh
from cityg.polygons import geos
from cityg.geometry.courtyard_programs import SIZES


def furnish_courtyard(compiler, owner, prefix, kind, center, angle, pad, metadata):
    s = geos()
    co, si = math.cos(angle), math.sin(angle)
    items = []
    base = .16

    def position(x, y, z):
        return Vec3(center[0]+x*co-y*si, center[1]+x*si+y*co, base+z)

    def rect(x, y, width, depth):
        return s.Polygon([(p.x,p.y) for p in [position(x+a,y+b,0) for a,b in
            [(-width/2,-depth/2),(width/2,-depth/2),(width/2,depth/2),(-width/2,depth/2)]]])

    def append(item):
        if item and pad.buffer(1e-7).covers(primitive_footprint(item)):
            items.append(item)
            return item
        return None

    def box(name, x, y, z, sx, sy, sz, material, *, obstacle=True, yaw=0, semantic='parcel_shelter'):
        return append(compiler._box(prefix+'_'+name, owner, position(x,y,z), Vec3(sx,sy,sz),
            math.degrees(angle)+yaw, semantic, material, 'roads', collision_enabled=obstacle,
            metadata={**metadata, 'ground_obstacle':obstacle, 'assembly_part':name}))

    def asset(name, x, y, category, size, query, tags=(), yaw=0, z=0, region=None):
        item=compiler._outdoor_mesh(prefix+'_'+name, owner,
            position(x,y,z+size[2]/2), Vec3(*size), math.degrees(angle)+yaw,
            'parcel_plant_asset' if category in {'plant','shrub'} else 'parcel_site_asset',
            category, query, 'roads', metadata={**metadata, 'ground_obstacle':True, 'assembly_part':name},
            required_asset_tags=tags, exclude_stylized=True)
        if item and region is not None and not region.covers(primitive_footprint(item)):
            return None
        return append(item)

    def bed(name, x, y, width=4.4, depth=1.25):
        soil = rect(x,y,width,depth)
        append(polygon_mesh(prefix+'_'+name+'_soil',owner,soil,base+.20,.20,
            'parcel_planting_bed','mulch_warm',metadata={**metadata,'ground_obstacle':True}))
        edge = soil.buffer(.10, join_style='mitre').difference(soil)
        append(polygon_mesh(prefix+'_'+name+'_edge',owner,edge,base+.28,.28,
            'parcel_shelter','civic_stone',collision=True,metadata={**metadata,'ground_obstacle':True}))
        palette = ('flower_gazania','grass_medium_02','flower_ursinia','periwinkle')
        count=max(3,round(width/.65))
        rows=max(1,int(depth/1.2))
        for i in range(count*rows):
            px = x-width/2+.46+(i%count)*(width-.92)/(count-1)
            py = y if rows==1 else y-depth/2+.6+(i//count)*(depth-1.2)/(rows-1)
            # Shrub accents plus two staggered perennial rows give the bed
            # volume, rather than a single row of tiny flowers on bare soil.
            if i%4==1:
                tag='shrub_02' if i%8==1 else 'searsia'
                asset(name+f'_shrub_{i}',px,py,'shrub',(.7,.7,.85),tag,(tag,),yaw=i*47,z=.20,region=soil)
            else:
                for row in (-1,1):
                    tag = palette[(i+row+sum(map(ord,prefix)))%len(palette)]
                    # A rotated .60 m envelope can project .85 m onto the
                    # bed's short axis; leave that clearance inside a 1.05 m bed.
                    asset(name+f'_plant_{i}_{row}',px,py+row*.09,'plant',(.60,.60,.60),tag,(tag,),
                          yaw=i*47+row*61,z=.20,region=soil)

    def bench(name, x, y, yaw=-90):
        asset(name,x,y,'street_bench',(1.85,.72,.88),'outdoor wood bench',yaw=yaw)

    def table(name, x, y, umbrella=False):
        # Picnic/table set: independently modelled legs, timber slats, two
        # seats. Companion pieces have real vertical support, not floating tops.
        box(name+'_frame',x,y,.62,1.6,.66,.10,'facade_frame_graphite')
        for sign in (-1,1):
            box(name+f'_leg_{sign}',x+sign*.65,y,.34,.09,.60,.68,'facade_frame_graphite')
            for i in range(3):
                box(name+f'_seat_{sign}_{i}',x,y+sign*.94+(i-1)*.13,.47,1.8,.12,.07,'furniture_wood')
            for side in (-1,1):
                box(name+f'_seatleg_{sign}_{side}',x+side*.65,y+sign*.94,.22,.09,.32,.44,'facade_frame_graphite')
        for i in range(6):
            box(name+f'_top_{i}',x,y+(i-2.5)*.13,.77,1.8,.12,.08,'furniture_wood')
        if umbrella:
            box(name+'_parasol_pole',x,y,1.43,.06,.06,2.86,'facade_frame_silver')
            vertices = []
            for z,radius in [(2.8,0),(2.43,1.65),(2.40,1.65),(2.77,0)]:
                if radius == 0:
                    p=position(x,y,z);vertices.append((p.x,p.y,p.z))
                else:
                    for i in range(8):
                        a=math.tau*i/8;p=position(x+radius*math.cos(a),y+radius*math.sin(a),z)
                        vertices.append((p.x,p.y,p.z))
            faces=[]
            for i in range(8):
                a=1+i;b=1+(i+1)%8;c=9+i;d=9+(i+1)%8
                faces.extend([(0,a,b),(17,d,c),(a,c,d),(a,d,b)])
            canopy=inline_mesh(prefix+'_'+name+'_parasol',owner,vertices,faces,'parcel_shelter',
                'facade_frame_cream',collision=False,metadata={**metadata,'ground_obstacle':False})
            canopy.layer_id='roads';append(canopy)

    def pergola(name, x, y, width=5.4, depth=3.6):
        for i,(dx,dy) in enumerate([(-1,-1),(1,-1),(1,1),(-1,1)]):
            box(name+f'_post_{i}',x+dx*(width/2-.2),y+dy*(depth/2-.2),1.4,.16,.16,2.8,'furniture_wood_dark')
        for sign in (-1,1):
            box(name+f'_beam_{sign}',x,y+sign*(depth/2-.2),2.84,width,.16,.22,'furniture_wood_dark',obstacle=False)
        for i in range(11):
            box(name+f'_slat_{i}',x-width/2+i*width/10,y,3.,.16,depth+.25,.16,'furniture_wood',obstacle=False)

    width, depth = SIZES[kind]
    # Edged surfaces, subtle expansion joints and a central continuous walking
    # strip add readable ground structure at both parcel and street scales.
    for sign in (-1,1):
        box(f'edge_{sign}',sign*(width/2-.09),0,.045,.14,depth-.2,.09,'civic_stone',obstacle=False)
        box(f'back_edge_{sign}',sign*(width/4+.65),depth/2-.10,.045,width/2-1.5,.14,.09,
            'civic_stone',obstacle=False)
    spine=rect(0,0,2.2,depth-.05)
    append(polygon_mesh(prefix+'_clear_spine',owner,spine,base+.012,.012,'parcel_walkway','paving_light',
        metadata={**metadata,'ground_obstacle':False,'clear_width_m':2.2}))
    for i in range(1,int(depth/2)):
        box(f'joint_{i}',0,-depth/2+i*2,.014,width-.35,.025,.008,'paving_dark',obstacle=False,
            semantic='parcel_surface_patch')
    for sign in (-1,1):
        # Back planting is split so it never closes the circulation spine.
        bed(f'border_{sign}',sign*(width/4+.55),depth/2-.85,width/2-1.8,1.05)

    if kind == 'pocket':
        bench('pocket_seat',-2.5,-.35,yaw=0)
        bed('pocket_flowers',2.5,-.35,1.5,1.5)
    elif kind in {'grove', 'pavilion', 'promenade'}:
        # Large, legible outdoor rooms. Keep all ground-level furnishings on
        # either side of the continuous 2.2 m circulation spine.
        if kind == 'grove':
            for side in (-1,1):
                for row in (-1,1):
                    x,y=side*8.,row*4.
                    soil=rect(x,y,5.8,4.8)
                    append(polygon_mesh(prefix+f'_tree_soil_{side}_{row}',owner,soil,base+.10,.10,
                        'parcel_planting_bed','mulch_warm',metadata={**metadata,'ground_obstacle':True}))
                    tags=('island',) if row<0 else ('tree','small','02')
                    asset(f'tree_{side}_{row}',x,y,'park_tree',(5.,4.,6.5),
                          ' '.join(tags),tags,z=.1,region=soil)
            pergola('garden_gallery',-4.5,0,width=5.2,depth=3.)
            bench('gallery_seat',-4.5,0)
            table('garden_table',4.4,0)
        elif kind == 'pavilion':
            pergola('long_gallery',-7.,0,width=8.8,depth=9.2)
            # Partial solid roof makes the pavilion readable from city altitude;
            # the remainder is an open timber pergola, not another main building.
            box('gallery_roof',-7.,2.4,3.15,9.2,4.8,.18,'facade_frame_cream',obstacle=False)
            for i,y in enumerate((-3.,.2,3.4)):
                table(f'covered_table_{i}',-7.,y)
            pergola('small_gallery',6.5,2.6,width=6.8,depth=4.2)
            table('open_table',6.5,2.6)
            table('cafe_table',6.5,-3.3,umbrella=True)
            bed('pavilion_side',10.8,0,1.4,3.)
        else:
            # Two raised ornamental islands and sheltered seats create a civic
            # forecourt without a giant empty slab or repeated miniature props.
            for side in (-1,1):
                bed(f'island_{side}',side*8.,0,7.,4.)
                pergola(f'arcade_{side}',side*8.,-5.,width=8.2,depth=3.)
                bench(f'arcade_seat_{side}',side*8.,-5.)
                bench(f'island_seat_{side}',side*8.,3.,yaw=90)
    elif kind == 'garden':
        pergola('shade',-4.5,.2)
        bench('shade_bench',-4.5,1.1)
        table('picnic',4.4,.1)
        bed('side_garden',-6.6,-2.8,1.8,1.3)
        bed('side_perennials',6.4,-2.9,2.,1.3)
    elif kind == 'terrace':
        for i,(x,y) in enumerate([(-4.5,-1.6),(4.5,-1.6),(-4.5,1.7),(4.5,1.7)]):
            table(f'table_{i}',x,y,umbrella=i in {0,3})
    elif kind == 'arrival':
        fountain=asset('fountain',-3.5,.6,'fountain',(2.1,2.1,2.4),'outdoor fountain')
        if fountain is None:
            bed('arrival_planting',-3.5,.6,2.6,2.2)
        bench('seat_a',3.7,.1,yaw=180)
        bench('seat_b',-3.5,-2.2,yaw=90)
        box('directory_post',5.45,-1.8,1.,.1,.1,2.,'facade_frame_graphite')
        box('directory_panel',5.45,-1.8,1.65,.9,.10,.7,'facade_frame_graphite')
        for i in range(3):
            box(f'directory_rule_{i}',5.45,-1.86,1.85-i*.16,.62,.025,.035,'facade_frame_cream')
    elif kind == 'cycle':
        pergola('shelter',-3.5,.3,width=4.6,depth=3.2)
        box('shelter_weather_roof',-3.5,.3,3.11,4.9,3.5,.12,'facade_frame_silver',obstacle=False)
        asset('rack',-3.5,.3,'bicycle_rack',(2.4,.9,1.),'bicycle rack',('bicycle_rack',))
        bench('waiting_seat',3.9,.8,yaw=180)
        bed('waiting_border',4.,-1.8,2.6,1.1)
    elif kind == 'kiosk':
        # Static concession/management pavilion: no fabricated walkable room.
        for sign in (-1,1):
            box(f'kiosk_side_{sign}',-3.5+sign*1.5,.55,1.38,.14,2.5,2.76,'civic_limestone',semantic='parcel_outbuilding')
        box('kiosk_back',-3.5,1.78,1.38,3.1,.14,2.76,'civic_limestone',semantic='parcel_outbuilding')
        box('kiosk_sill',-3.5,-.72,.49,3.1,.14,.98,'furniture_wood_dark',semantic='parcel_outbuilding')
        box('kiosk_glass',-3.5,-.76,1.62,2.85,.04,1.2,'facade_glass_neutral',semantic='parcel_outbuilding')
        box('kiosk_header',-3.5,-.72,2.55,3.1,.16,.43,'facade_frame_graphite',semantic='parcel_outbuilding')
        box('kiosk_counter',-3.5,-.94,1.04,3.3,.65,.10,'furniture_wood',semantic='parcel_outbuilding')
        box('kiosk_roof',-3.5,.5,2.87,3.55,2.9,.18,'facade_frame_graphite',obstacle=False,semantic='parcel_outbuilding')
        box('kiosk_awning',-3.5,-1.05,2.56,3.55,1.25,.10,'facade_frame_cream',obstacle=False,semantic='parcel_outbuilding')
        table('kiosk_seating',3.6,.1,umbrella=True)

    asset('bin',width/2-.75,-depth/2+1.1,'street_bin',(.55,.55,.9),'outdoor litter bin')
    for i,(x,y) in enumerate([(-2.,-depth/2+1.3),(2.1,-depth/2+1.8)]):
        asset(f'visitor_{i}',x,y,'person',(.65,.65,1.76),'person standing',('standing',),yaw=45+i*160)
    # Small recessed drains; not random stains or litter painted across lawns.
    for j,x in enumerate((-width/2+1.4,width/2-1.4)):
        box(f'drain_{j}',x,-depth/2+.6,.018,.55,.35,.024,'facade_frame_graphite',obstacle=False)
        for i in range(5):
            box(f'drain_{j}_bar_{i}',x-.2+i*.1,-depth/2+.6,.034,.025,.32,.012,'facade_frame_silver',obstacle=False)
    return items
