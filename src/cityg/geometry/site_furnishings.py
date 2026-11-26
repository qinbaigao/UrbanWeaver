"""Small exterior amenity assemblies; no implicit new habitable buildings."""
import math
from cityg.geometry.model import Vec3
from cityg.geometry.geography import primitive_footprint


def furnish_site(compiler, parcel_id, prefix, kind, center, angle, pad, metadata):
    co,si=math.cos(angle),math.sin(angle);items=[]
    def position(x,y,z):return Vec3(center[0]+x*co-y*si,center[1]+x*si+y*co,z)
    def box(name,x,y,z,sx,sy,sz,material,semantic='parcel_shelter',yaw=0):
        item=compiler._box(f'{prefix}_{name}',parcel_id,position(x,y,z),Vec3(sx,sy,sz),
            math.degrees(angle)+yaw,semantic,material,'roads',collision_enabled=True,metadata=metadata)
        items.append(item)
    def asset(name,x,y,category,size,query,tags=(),yaw=0):
        item=compiler._outdoor_mesh(f'{prefix}_{name}',parcel_id,position(x,y,.13+size[2]/2),Vec3(*size),
            math.degrees(angle)+yaw,'parcel_site_asset',category,query,'roads',metadata=metadata,
            required_asset_tags=tags,exclude_stylized=True)
        if item and pad.covers(primitive_footprint(item)):
            items.append(item)
            return item
        return None
    if kind in {'cycle_shelter','pergola'}:
        for i,(x,y) in enumerate([(-2.2,-.7),(2.2,-.7),(-2.2,1.7),(2.2,1.7)]):
            box(f'post_{i}',x,y,1.45,.12,.12,2.65,'facade_frame_graphite')
        box('beam_front',0,-.7,2.76,4.65,.18,.20,'facade_frame_graphite')
        box('beam_back',0,1.7,2.76,4.65,.18,.20,'facade_frame_graphite')
        if kind=='cycle_shelter':
            box('roof',0,.5,2.9,4.9,3.0,.12,'facade_frame_silver')
            asset('rack',0,.65,'bicycle_rack',(2.2,.75,.9),'bicycle rack outdoor',('bicycle_rack',))
        else:
            for i in range(9):box(f'slat_{i}',-2.2+i*.55,.5,2.9,.18,3.0,.14,'furniture_wood')
            asset('bench',0,1.1,'street_bench',(2.0,.75,.9),'outdoor wood bench')
    elif kind=='service_hut':
        # Small closed exterior management/storage cabin, not an extra room
        # in the City hierarchy. Explicit front doorway + lintel, no solid box
        # pretending to contain a walkable/interactable interior.
        box('back',0,1.8,1.48,3.8,.16,2.7,'residential_brick','parcel_outbuilding')
        for side in (-1,1):
            box(f'side_{side}',side*1.82,.5,1.48,.16,2.6,2.7,'residential_brick','parcel_outbuilding')
            box(f'front_{side}',side*1.18,-.8,1.48,1.28,.16,2.7,'residential_brick','parcel_outbuilding')
        box('lintel',0,-.8,2.61,1.08,.16,.44,'residential_brick','parcel_outbuilding')
        box('closed_door',0,-.83,1.22,1.02,.08,2.18,'facade_frame_graphite','parcel_outbuilding')
        box('door_window',0,-.88,1.63,.65,.025,.65,'facade_glass_blue','parcel_outbuilding')
        box('roof',0,.5,2.91,4.15,3.0,.18,'facade_frame_graphite','parcel_outbuilding')
    else:
        asset('bench_left',-1.8,.7,'street_bench',(1.9,.72,.9),'outdoor wood bench',yaw=90)
        asset('bench_right',1.8,.7,'street_bench',(1.9,.72,.9),'outdoor wood bench',yaw=-90)
        planter=asset('planter',0,1.3,'street_planter',(1.5,.75,.7),'outdoor planter box',('planter',))
        # Flower cluster above the planter; the compiled footprint is checked
        # independently and missing local assets simply leave it unpopulated.
        if planter:
            plant=compiler._outdoor_mesh(f'{prefix}_flowers',parcel_id,
                position(0,1.3,planter.center.z+planter.size.z/2+.12),Vec3(1.25,.65,.4),
                math.degrees(angle),'parcel_plant_asset','plant','flower gazania','roads',
                metadata=metadata,required_asset_tags=('flower_gazania',))
            if plant and pad.covers(primitive_footprint(plant)):items.append(plant)
    asset('bin',2.8,1.5,'street_bin',(.55,.55,.9),'outdoor litter bin')
    # Standing visitors occupy the pad, not the clear route to its front edge.
    for i,x in enumerate((-2.45,2.45)):
        # Outdoor suitability is a hard filter above, not a lexical keyword:
        # only one legacy person has an explicit 'outdoor' tag, which would
        # otherwise crowd every other valid standing pose out of selection.
        asset(f'visitor_{i}',x,-1.35,'person',(.75,.75,1.8),'person standing',('standing',),yaw=180*i)
    return items
