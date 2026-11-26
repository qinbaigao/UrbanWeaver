"""Small two-level fixtures and deliberately simple floor-review furnishings."""
from copy import deepcopy
from itertools import combinations

from cityg.planning.floor_prototypes import box, connection_segment, circulation_raster
from cityg.planning.interiors import ASSET_CATALOG
from cityg.planning.room_regions import region_bounds
from cityg.schemas import (Bounds2D, Building, City, District, Door, Floor, InteriorObject,
                           Junction, Parcel, Point2D, RoadNetwork, RoadSegment, Room, VerticalConnector)


def door_point(r):
    e=r['entry'];b=box(next(s['bounds_m'] for s in r['spaces'] if s['id']==e['space']))
    return Point2D(b.min_x+b.width*e['fraction'],b.min_y if e['side']=='south' else b.max_y) if e['side'] in {'north','south'} else Point2D(b.min_x if e['side']=='west' else b.max_x,b.min_y+b.depth*e['fraction'])


def grouped_preview(s, bounds, obstacles):
    """Keep new shared-space previews coherent; never relocate chairs alone."""
    fn=s['function'];placed=[];skipped=[]
    for ix in range(1,max(2,int(bounds.width/4))):
        for iy in range(1,max(2,int(bounds.depth/4))):
            x=bounds.min_x+ix*bounds.width/max(2,int(bounds.width/4))
            y=bounds.min_y+iy*bounds.depth/max(2,int(bounds.depth/4))
            if fn in {'coworking','classroom'}:
                slots=[('desk',x,y),('office_chair' if fn=='coworking' else 'meeting_chair',x,y+.95)]
            elif fn in {'reading_room','food_court'}:
                slots=[('dining_table',x,y),('dining_chair',x,y+1.1),('dining_chair',x,y-1.1)]
            else:slots=[('bookcase',x,y)]
            group=[]
            for cat,px,py in slots:
                spec=ASSET_CATALOG[cat]
                bb=Bounds2D(px-spec.width_m/2,py-spec.depth_m/2,px+spec.width_m/2,py+spec.depth_m/2)
                if (not bounds.inset(.28).contains_bounds(bb) or any(bb.overlaps_area(a) for a in obstacles)
                        or any(bb.overlaps_area(o['bounds'].inset(-.12)) for o in placed+group)):
                    break
                group.append({'space':s['id'],'category':cat,'x':px,'y':py,'bounds':bb,'rotation':0})
            if len(group)==len(slots):placed.extend(group)
            else:skipped.extend({'space':s['id'],'category':cat,'reason':'preview group clearance'} for cat,_,_ in slots)
    return placed,skipped


def furnish_reference(r):
    """Preview-only proxies: no room-template approval or fine design implied."""
    objects=[];skipped=[]
    for s in r['spaces']:
        if s['function']=='corridor':continue
        b=box(s['bounds_m']);fn=s['function'];candidates=[]
        if fn in {'open_office','shop'}:
            for ix in range(1,max(2,int(b.width/4))):
                for iy in range(1,max(2,int(b.depth/4))):
                    x=b.min_x+ix*b.width/max(2,int(b.width/4));y=b.min_y+iy*b.depth/max(2,int(b.depth/4))
                    if fn=='open_office':candidates.extend([('desk',x,y),('office_chair',x,y+.95)])
                    else:candidates.append(('display_shelf',x,y))
        else:
            categories={'bedroom':['bed','wardrobe'], 'living_room':['sofa','coffee_table','dining_table'],
                'kitchen':['kitchen_counter','refrigerator'], 'bathroom':['toilet','sink'],
                'office':['desk','office_chair','cabinet'], 'meeting_room':['meeting_table','meeting_chair','meeting_chair'],
                'break_room':['kitchen_counter','dining_table','dining_chair'],
                'waiting_room':['sofa','coffee_table','waiting_bench','waiting_bench'],
                'storage':['storage_rack','storage_rack']}.get(fn,[])
            slots=[(.25,.25),(.75,.75),(.25,.75),(.75,.25)]
            candidates=[(cat,b.min_x+b.width*u,b.min_y+b.depth*v) for cat,(u,v) in zip(categories,slots)]
        reservations=[region_bounds(b,uv) for uv in s.get('clear_aisles_uv',[])]
        doors=[]
        for c in r['connections']:
            if s['id'] not in (c['a'],c['b']):continue
            axis,edge,start,end=connection_segment(r,c)
            doors.append(Bounds2D(start-.35,edge-1.4,end+.35,edge+1.4) if axis=='x'
                         else Bounds2D(edge-1.4,start-.35,edge+1.4,end+.35))
        if fn in {'coworking','classroom','reading_room','library_stack','food_court'}:
            groups,omitted=grouped_preview(s,b,doors+reservations)
            objects.extend(groups);skipped.extend(omitted)
            continue
        for cat,x,y in candidates:
            spec=ASSET_CATALOG[cat];placed=None
            # Small bedrooms need a wall-aligned bed, not a fractional center
            # that clips the wall. Retry bounded actual-size poses, unscaled.
            for rotation in ((0,90) if fn not in {'open_office','shop'} else (0,)):
                bw,bd=(spec.width_m,spec.depth_m) if rotation==0 else (spec.depth_m,spec.width_m)
                xlo,xhi=b.min_x+.28+bw/2,b.max_x-.28-bw/2
                ylo,yhi=b.min_y+.28+bd/2,b.max_y-.28-bd/2
                if xlo>xhi or ylo>yhi:continue
                poses=[(x,y)]
                if fn not in {'open_office','shop'}:
                    poses.extend((xlo+(xhi-xlo)*u,ylo+(yhi-ylo)*v) for u in (0,1,.5,.25,.75) for v in (1,0,.5,.25,.75))
                for px,py in poses:
                    bb=Bounds2D(px-bw/2,py-bd/2,px+bw/2,py+bd/2)
                    if (not b.inset(.28).contains_bounds(bb) or any(bb.overlaps_area(a) for a in doors+reservations)
                            or any(bb.overlaps_area(o['bounds'].inset(-.12)) for o in objects if o['space']==s['id'])):continue
                    placed={'space':s['id'],'category':cat,'x':px,'y':py,'bounds':bb,'rotation':rotation};break
                if placed:break
            if placed:objects.append(placed)
            else:skipped.append({'space':s['id'],'category':cat,'reason':'preview clearance'})
    return objects,skipped


def make_floor_lab(library, keys):
    if not keys or len(keys)>16 or len(set(keys))!=len(keys) or any(k not in library.floors for k in keys):
        raise ValueError('Select 1..16 unique existing floor prototypes')
    spacing=64;extent=spacing*len(keys)+12
    road=RoadSegment('floor_lab_road','start','end',(Point2D(2,5),Point2D(extent-2,5)),width_m=6,sidewalk_width_m=1,parking_allowed=False)
    district=District('floor_lab_district','Floor prototype lab','mixed_use',Bounds2D(0,10,extent,65))
    city=City('city_floor_prototype_lab','CityG floor prototype review',Bounds2D(0,0,extent,70),
        RoadNetwork([Junction('start',road.centerline[0]),Junction('end',road.centerline[-1])],[road]),[district])
    rows=[]
    access_branches=[]
    for index,key in enumerate(keys):
        r=deepcopy(library.floors[key]);w,d,h=(r['reference'][k] for k in ('width_m','depth_m','height_m'))
        ox=8+spacing*index+(spacing-w)/2;oy=18
        def point(x,y):return Point2D(ox+x,oy+y)
        def rect(v):return Bounds2D(ox+v[0],oy+v[1],ox+v[2],oy+v[3])
        entry=door_point(r)
        if r['entry']['side']=='west':
            access_branches.append((ox-6,oy+entry.y+3))
        b=Building(key+'_building',r['display_name'],r['function'],rect([0,0,w,d]),point(entry.x,entry.y),
            metadata={'prototype_review_fixture':True,'floor_layout_prototype_id':key})
        furniture,skipped=furnish_reference(r)
        raster=circulation_raster(r,[o['bounds'] for o in furniture])
        if not raster['ok']:raise ValueError(f"Preview furniture blocks {key}: {raster}")
        for level in range(2):
            fid=f'{b.id}_floor_{level:02d}';ids={s['id']:fid+'_'+s['id'] for s in r['spaces']}
            rooms=[Room(ids[s['id']],s['display_name'],s['function'],rect(s['bounds_m']),h,
                metadata={'space_group_id':fid+'_'+s['unit_id'] if s.get('unit_id') else ids[s['id']],
                          'unit_id':fid+'_'+s['unit_id'] if s.get('unit_id') else None,
                          'floor_prototype_space':s['id'],'detail_tier':'preview',
                          'room_prototype_hints':s['room_reference_hints'],
                          'functional_zones':deepcopy(s.get('functional_zones',[])),
                          'open_plan':s['function']=='open_office' or bool(s.get('functional_zones')),
                          'corridor_role':'central' if s['id']=='circulation' else 'secondary'}) for s in r['spaces']]
            doors=[]
            for n,c in enumerate(r['connections']):
                axis,edge,lo,hi=connection_segment(r,c)
                pos=point((lo+hi)/2,edge) if axis=='x' else point(edge,(lo+hi)/2)
                doors.append(Door(fid+f'_door_{n:03d}',ids[c['a']],ids[c['b']],pos,c['width_m'],
                                  door_type='open_passage' if c['kind']=='open' else 'interior',interactive=c['kind']!='open'))
            if level==0:doors.append(Door(fid+'_entrance',ids[r['entry']['space']],None,b.entrance,r['entry']['width_m'],'exterior'))
            f=Floor(fid,level,level*h,h,rooms,doors,metadata={
                'floor_prototype_id':key,'floor_prototype_fingerprint':library.content_fingerprint(key),
                'spatial_layout':{'status':'accepted','family':'reviewed_floor_reference',
                    'open_boundaries':[[ids[a],ids[c]] for a,c in r['open_boundaries']]},
                'dwelling_units':[{**u,'id':fid+'_'+u['id'],'room_ids':[ids[k] for k in u['room_ids']],
                                  'entry_space':ids[u['entry_space']]} for u in r['units']]})
            for n,item in enumerate(furniture):
                spec=ASSET_CATALOG[item['category']]
                obj=InteriorObject(fid+f'_preview_{n:03d}',ids[item['space']],spec.category,spec.id,
                    point(item['x'],item['y']),spec.width_m,spec.depth_m,spec.height_m,
                    rotation_deg=item['rotation'],metadata={'preview_only':True,'front_axis':spec.front_axis})
                f.objects.append(obj);next(room for room in rooms if room.id==obj.room_id).object_ids.append(obj.id)
            b.floors.append(f)
        for c in r['cores']:
            b.vertical_connectors.append(VerticalConnector(b.id+'_'+c['id'],c['kind'],rect(c['bounds_m']),0,1,
                interactive=c['kind']=='elevator',metadata={'stack_key':c['stack_key'],'floor_prototype_core':True}))
        district.parcels.append(Parcel(key+'_parcel',Bounds2D(8+spacing*index,11,8+spacing*(index+1),64),[b]))
        rows.append({'prototype_id':key,'content_fingerprint':library.content_fingerprint(key),
            'display_name':r['display_name'],'intent':r['intent'],'reference':r['reference'],
            'building_id':b.id,'floor_id':b.floors[0].id,'stack_check_floor_id':b.floors[1].id,
            'unit_count':len(r['units']),'space_count':len(r['spaces']),
            'preview_furniture_count':len(furniture),'skipped_preview_slots':skipped,
            'layout_validation':library.validate(r),'circulation_check':raster})
    # Lab access roads must face the reference entrance, too. A west entrance
    # cannot be declared connected to a road entirely south of the fixture.
    if access_branches:
        xs=[2,*sorted(x for x,_ in access_branches),extent-2]
        junctions=[Junction(f'lab_main_{i}',Point2D(x,5)) for i,x in enumerate(xs)]
        roads=[RoadSegment(f'lab_main_edge_{i}',junctions[i].id,junctions[i+1].id,
                (junctions[i].position,junctions[i+1].position),width_m=6,sidewalk_width_m=1,parking_allowed=False)
               for i in range(len(xs)-1)]
        for i,(x,y) in enumerate(access_branches):
            root=next(j for j in junctions if j.position.x==x and j.position.y==5)
            tip=Junction(f'lab_branch_{i}',Point2D(x,y));junctions.append(tip)
            roads.append(RoadSegment(f'lab_access_{i}',root.id,tip.id,(root.position,tip.position),
                                     width_m=4,sidewalk_width_m=.8,parking_allowed=False))
        city.road_network=RoadNetwork(junctions,roads)
    return city,rows


def compiled_floor_checks(city,scene):
    """Ensure the fixture actually emitted walls, furniture and aligned cores."""
    checks=[]
    by_owner={}
    for p in scene.primitives:by_owner.setdefault(p.owner_id,[]).append(p)
    for b in city.iter_buildings():
        for f in b.floors:
            for obj in f.objects:
                parts=by_owner.get(obj.id,[]);room=next(r for r in f.rooms if r.id==obj.room_id)
                inside=bool(parts)
                for p in parts:
                    from cityg.geometry.room_decorations import box_bounds
                    actual=box_bounds(p)
                    inside &= room.bounds.contains_bounds(actual,tolerance=.01)
                checks.append({'kind':'compiled_furniture_containment','entity':obj.id,'ok':bool(inside)})
        for c in b.vertical_connectors:
            parts=by_owner.get(c.id,[])
            layers={p.layer_id for p in parts}
            expected={f'floor:{b.floors[0].id}'} if c.connector_type=='stairs' else {f'floor:{f.id}' for f in b.floors}
            inside=all(c.bounds.contains_bounds(Bounds2D(p.center.x-p.size.x/2,p.center.y-p.size.y/2,
                       p.center.x+p.size.x/2,p.center.y+p.size.y/2),tolerance=.01) for p in parts)
            checks.append({'kind':'compiled_core_alignment','entity':c.id,'ok':bool(parts) and inside and expected<=layers})
    return checks
