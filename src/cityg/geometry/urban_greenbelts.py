"""Street-facing planting ribbons and mixed gardens, not another peripheral forest.

Beds are clipped to actual unoccupied parcel land. Entrances, pedestrian routes,
street furniture and buildings remain untouched. Planted-bed area is reported
separately from plant counts: neither is a measurement of green pixels.
"""
from collections import Counter, defaultdict
from dataclasses import replace
import math
import random

from cityg.geometry.dense_greenery import obstacle_index, PLANTS, TREES
from cityg.geometry.geography import primitive_footprint, polygon_mesh
from cityg.geometry.asset_fitting import outdoor_asset_ground_offset
from cityg.geometry.model import Vec3
from cityg.polygons import geos, box_shape, parcel_shape, polygon_parts, road_shape

KEY = 'urban_greenbelts'
VERSION = 'street_garden_borders_v1'
PALETTES = (
    ('fern_garden', ('fern_02','fern_02','searsia','searsia','grass_medium_01')),
    ('flower_border', ('searsia','fern_02','flower_gazania','shrub_sorrel_01','searsia','flower_ursinia')),
    ('mixed_hedge', ('searsia','searsia','fern_02','shrub_02','grass_medium_01','flower_heliophila')),
    ('meadow_border', ('grass_medium_01','fern_02','grass_medium_01','searsia','grass_medium_02','flower_ursinia')),
)


class SpacingGrid:
    def __init__(self, cell=6):
        self.cell=cell; self.buckets=defaultdict(list); self.max_radius=0.

    def add(self,x,y,r):
        self.buckets[(math.floor(x/self.cell),math.floor(y/self.cell))].append((x,y,r))
        self.max_radius=max(self.max_radius,r)

    def clear(self,x,y,r,factor=1.):
        reach=(r+self.max_radius)*factor
        for i in range(math.floor((x-reach)/self.cell),math.floor((x+reach)/self.cell)+1):
            for j in range(math.floor((y-reach)/self.cell),math.floor((y+reach)/self.cell)+1):
                if any(math.hypot(x-a,y-b)<(r+rr)*factor for a,b,rr in self.buckets.get((i,j),())):
                    return False
        return True


class PlantBank:
    def __init__(self,compiler):
        self.compiler=compiler;self.templates={}

    def make(self,owner,prefix,x,y,height,tag,tree,rng,metadata):
        category='park_tree' if tree else 'shrub' if tag in {'shrub_02','searsia'} else 'plant'
        key=(category,tag)
        if key not in self.templates:
            tags=TREES.get(tag,(tag,))
            options=[self.compiler._outdoor_mesh(f'border_template_{tag}_{i}',owner,Vec3(0,0,1),
                Vec3(2,2,2),0,'parcel_tree_asset' if tree else 'parcel_shrub_asset' if category=='shrub' else 'parcel_plant_asset',
                category,tag.replace('_',' ')+' outdoor','roads',required_asset_tags=tags,exclude_stylized=True)
                for i in range(8)]
            self.templates[key]=list({p.metadata['asset_id']:p for p in options if p is not None}.values())
        options=self.templates[key]
        if not options:return None
        template=rng.choice(options);record=self.compiler.asset_registry.get(template.metadata['asset_id'])
        dims=record.dimensions_m
        if not dims or min(dims)<=0:return None
        size=Vec3(*(v*height/dims[2] for v in dims));ground=.15
        return replace(template,id=prefix,owner_id=owner,size=size,rotation_z_deg=rng.uniform(0,360),
            center=Vec3(x,y,ground+height/2-outdoor_asset_ground_offset(record,size)),
            metadata={**template.metadata,**metadata,'planting_species':tag,'terrain_contact_z':ground,
                      'planting_role':'canopy' if tree else 'understory' if category=='shrub' else 'groundcover'})


def bed_candidates(shape, free, frontage, buildings, rng):
    """Separated ribbons at street-facing edges; irregular larger garden pockets."""
    s=geos()
    for part in polygon_parts(shape.buffer(-4.5)):
        ring=part.exterior;offset=rng.uniform(0,20)
        for start in range(math.ceil(ring.length/24)):
            mid=(offset+start*24)%ring.length
            length=rng.uniform(16,23);width=rng.uniform(5.5,9)
            points=[ring.interpolate((mid+length*(i/6-.5))%ring.length) for i in range(7)]
            bed=s.LineString([(p.x,p.y) for p in points]).buffer(width/2,quad_segs=4)
            bed=bed.intersection(free).intersection(frontage)
            if bed.area>=24:yield 'street_border',bed
    # Use compiled building outlines, not an oversized planning rectangle.
    near=buildings.buffer(24).intersection(free) if not buildings.is_empty else free
    if near.is_empty:return
    x0,y0,x1,y1=near.bounds
    for _ in range(100):
        x,y=rng.uniform(x0,x1),rng.uniform(y0,y1)
        if not near.contains(s.Point(x,y)):continue
        angle=rng.uniform(0,math.tau);length=rng.uniform(10,24);width=rng.uniform(7,13)
        dx,dy=math.cos(angle)*length/2,math.sin(angle)*length/2
        bed=s.LineString([(x-dx,y-dy),(x,y+width*.2),(x+dx,y+dy)]).buffer(width/2,quad_segs=5)
        bed=bed.intersection(near)
        if bed.area>=32:yield 'building_garden',bed


def compile_urban_greenbelts(compiler,city,scene):
    plan=city.metadata.get(KEY)
    if not plan or not plan.get('enabled',True):return {'status':'not_requested'}
    density=float(plan.get('density',1.))
    if plan.get('version',VERSION)!=VERSION or not math.isfinite(density) or not .2<=density<=2:
        raise ValueError('Unknown urban-greenbelt version or density outside [0.2, 2]')
    previous=[p for p in scene.primitives if p.metadata.get(KEY)==VERSION]
    base=[p for p in scene.primitives if p.metadata.get(KEY)!=VERSION]
    s=geos();obstacles=obstacle_index(city,base,include_vegetation=False)
    roads=s.STRtree([road_shape(r,18) for r in city.road_network.segments])
    trees=SpacingGrid();stems=SpacingGrid();low=SpacingGrid();by_owner=defaultdict(list)
    for p in base:
        by_owner[p.owner_id].append(p)
        cat=p.metadata.get('asset_category')
        if cat in PLANTS:
            r=max(p.size.x,p.size.y)/2
            if cat in {'street_tree','park_tree'}:
                trees.add(p.center.x,p.center.y,r);stems.add(p.center.x,p.center.y,.45)
            else:low.add(p.center.x,p.center.y,min(r,2.))
    construction={p['parcel_id'] for p in city.metadata.get('construction_sites',{}).get('sites',[])}
    bank=PlantBank(compiler);additions=[];records=[];counts=Counter();roles=Counter()
    for d in city.districts:
        for parcel in d.parcels:
            if not parcel.buildings or parcel.id in construction:continue
            shape=parcel_shape(parcel)
            free=shape.buffer(-.7).difference(s.union_all(obstacles.geometries.take(obstacles.query(shape))))
            if free.area<80:continue
            s.prepare(free)
            frontage=s.union_all(roads.geometries.take(roads.query(shape)))
            outlines=[]
            for b in parcel.buildings:
                slabs=[primitive_footprint(p) for owner in [b.id,*[f.id for f in b.floors if f.level==0]]
                       for p in by_owner[owner] if p.semantic_class=='floor_slab' and p.center.z<1]
                outlines.extend(slabs or [box_shape(b.footprint)])
            buildings=s.union_all(outlines)
            seed=compiler._parcel_seed(parcel.id,VERSION,str(plan.get('seed',20261017)))
            rng=random.Random(seed);used=s.GeometryCollection();placed=[];items=[]
            target_area=min(free.area*.38*density,2700*density)
            budget=min(540,round(360*density));tree_count=0
            # Street-facing beds have first claim, but leave room for 3–5 garden
            # islands instead of spending the entire budget on a perimeter fence.
            for candidate_index,(kind,candidate) in enumerate(bed_candidates(shape,free,frontage,buildings,rng)):
                if len(placed)>=18 or used.area>=target_area or len(items)>=budget:break
                if kind=='street_border' and (sum(b['kind']=='street_border' for b in placed)>=10
                                             or len(items)>=budget*.55):continue
                asset_limit=round(budget*.55) if kind=='street_border' else budget
                bed=candidate.difference(used.buffer(1.2))
                parts=polygon_parts(bed)
                if not parts:continue
                bed=max(parts,key=lambda p:p.area)
                if bed.area<24:continue
                bed=bed.simplify(.12,preserve_topology=True).intersection(free)
                palette=PALETTES[(seed+len(placed))%len(PALETTES)]
                prefix=f'{parcel.id}_greenbelt_{candidate_index:03d}'
                meta={KEY:VERSION,'parcel_id':parcel.id,'district_id':d.id,
                      'planting_system':VERSION,'planting_bed_id':prefix,'planting_palette':palette[0],
                      'planting_context':kind}
                x0,y0,x1,y1=bed.bounds;new=[]
                # Crowns can overhang their soil bed, but not protected paths.
                for attempt in range(24):
                    if tree_count>=18 or len([p for p in new if p.metadata['planting_role']=='canopy'])>=2:break
                    x,y=rng.uniform(x0,x1),rng.uniform(y0,y1)
                    if not bed.contains(s.Point(x,y)):continue
                    tag=rng.choice(['island','jacaranda','small_tree','medium_fir'])
                    height=rng.uniform(6.5,10.5)
                    item=bank.make(parcel.id,prefix+f'_tree_{attempt}',x,y,height,tag,True,rng,meta)
                    if not item:continue
                    radius=max(item.size.x,item.size.y)/2
                    if not free.covers(primitive_footprint(item)) or not trees.clear(x,y,radius,.7):continue
                    new.append(item);trees.add(x,y,radius);stems.add(x,y,.45);tree_count+=1
                # Staggered, jittered multi-row planting: low foliage coalesces
                # into masses, unlike the old seven scattered plants per tree.
                step=1.35
                for iy in range(math.ceil((y1-y0)/step)):
                    for ix in range(math.ceil((x1-x0)/step)):
                        if len(items)+len(new)>=asset_limit:break
                        x=x0+(ix+.5+(iy%2)*.5)*step+rng.uniform(-.22,.22)
                        y=y0+(iy+.5)*step+rng.uniform(-.22,.22)
                        if not bed.contains(s.Point(x,y)):continue
                        tag=palette[1][(ix//3+iy//2)%len(palette[1])]
                        height=(rng.uniform(1.6,2.2) if tag=='searsia' else
                                rng.uniform(1.2,1.7) if tag=='shrub_02' else
                                rng.uniform(1.,1.2) if tag=='fern_02' else
                                rng.uniform(.85,1.15) if 'grass' in tag else rng.uniform(.4,.65))
                        item=bank.make(parcel.id,prefix+f'_plant_{iy}_{ix}',x,y,height,tag,False,rng,meta)
                        if not item:continue
                        radius=max(item.size.x,item.size.y)/2
                        if not bed.covers(primitive_footprint(item)) or not stems.clear(x,y,radius) or not low.clear(x,y,radius,.62):continue
                        new.append(item);low.add(x,y,radius)
                if len(new)<5:
                    # Retain any accepted tree (spacing already reserved), but
                    # do not emit an empty brown bed when its flora is missing.
                    items.extend(new);continue
                # Don't leave a large bare mulched area when the instance
                # budget or missing assets only allowed one edge to be planted.
                planted=s.union_all([primitive_footprint(p).buffer(.15,quad_segs=3) for p in new]).intersection(bed)
                bed=bed.intersection(planted.buffer(.8).buffer(-.8))
                # Buffer-generated arcs need not retain centimetre-scale rings
                # in a city-wide mesh. Reclip after simplification for safety.
                bed=bed.simplify(.12,preserve_topology=True).intersection(free)
                soil=polygon_mesh(prefix+'_soil',parcel.id,bed,.145,.035,'parcel_planting_bed',
                                  'mulch_warm',metadata=meta)
                if soil is not None:additions.append(soil)
                items.extend(new);used=used.union(bed)
                placed.append({'id':prefix,'kind':kind,'palette':palette[0],'area_m2':round(bed.area,1),
                               'asset_instances':len(new)})
            if items:
                additions.extend(items);counts.update(p.metadata['asset_id'] for p in items)
                roles.update(p.metadata['planting_role'] for p in items)
                records.append({'parcel_id':parcel.id,'free_area_m2':round(free.area,1),
                    'planted_bed_area_m2':round(used.area,1),'bed_area_fraction':round(used.area/free.area,3),
                    'tree_count':tree_count,'asset_instances':len(items),'beds':placed})
    changed={r['parcel_id'] for r in records}
    retained=[p for p in previous if p.owner_id not in changed]
    scene.primitives=base+retained+additions
    report={'version':VERSION,'density':density,'parcels':records,'changed_parcels':len(records),
        'new_primitives':len(additions),'new_asset_instances':sum(counts.values()),'asset_counts':dict(counts),
        'role_counts':dict(roles),'bed_counts':dict(Counter(b['kind'] for r in records for b in r['beds'])),
        'planted_bed_area_m2':round(sum(r['planted_bed_area_m2'] for r in records),1),
        'existing_primitives_modified':0,'retained_previous_primitives':len(retained),
        'coverage_definition':'new soil-bed area inside free parcel land, not green-pixel/leaf coverage',
        'scope':'occupied urban parcels only; peripheral park/hill unchanged'}
    scene.metadata[KEY]=report
    return report
