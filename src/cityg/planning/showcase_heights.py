"""Seeded height edits for curated exterior scenes, not structural certification.

Keep the site, architectural language and storey heights. Clone semantic floor
templates (with new IDs) rather than scaling meshes/windows. Detailed interiors
and authored vertical programmes need their own replanning and are not edited.
"""
from collections import Counter
from copy import deepcopy
import math
import random

from cityg.geometry.roof_programs import roof_profile
from cityg.geometry.roof_textures import texture_choice
from cityg.planning.highrise import HighRisePolicy
from cityg.schemas import Building
from cityg.serialization import _floor, to_primitive

KEY = 'showcase_height_variation_v1'


def floor_band(building):
    n=len(building.floors)
    if not n:return (0,0)
    high=building.metadata.get('highrise',{}).get('enabled',False)
    radius=1 if n<=5 else 2 if n<10 else 3 if n<15 else 5
    lo=max(10 if high else 2,n-radius)
    # Do not silently promote a low-rise into a different core/typology regime,
    # or cross the two-elevator threshold without the corresponding core.
    elevators=sum(c.connector_type=='elevator' for c in building.vertical_connectors)
    hi=min(n+radius,48 if high and elevators>=2 else 17 if high else 9)
    return lo,hi


def select_landmarks(buildings,count=3,min_spacing=200):
    eligible=[b for b in buildings if len(b.floors)>=15
        and b.function in {'commercial','mixed_use'}
        and b.metadata.get('highrise',{}).get('enabled')
        and min(b.footprint.width,b.footprint.depth)>=30
        and sum(c.connector_type=='elevator' for c in b.vertical_connectors)>=2]
    if not eligible:return []
    center=(sum(b.footprint.center.x for b in eligible)/len(eligible),
            sum(b.footprint.center.y for b in eligible)/len(eligible))
    chosen=[]
    def distance(a,b):return math.hypot(a.x-b.x,a.y-b.y)
    def score(b):
        p=b.footprint.center
        central=1/(1+math.hypot(p.x-center[0],p.y-center[1])/300)
        spread=min((distance(p,c.footprint.center) for c in chosen),default=0)/300
        return central+.3*min(b.footprint.area/4000,1)+.6*spread
    for _ in range(count):
        available=[b for b in eligible if b not in chosen and all(
            distance(b.footprint.center,c.footprint.center)>=min_spacing for c in chosen)]
        if not available:break
        chosen.append(max(sorted(available,key=lambda b:b.id),key=score))
    return [b.id for b in chosen]


def resize_floor_stack(building: Building, count: int, landmark=False):
    """Mutate one private candidate, preserving existing retained floor contents."""
    original=len(building.floors)
    if not 2<=count<=48 or original<2:raise ValueError('Unsupported exterior floor count')
    if building.metadata.get('vertical_zoning',{}).get('zones'):
        raise ValueError('Authored vertical zones require joint replanning')
    # Pin roof choices before a height threshold could choose a different use.
    building.metadata.setdefault('roof_program',{'profile':roof_profile(building)})
    building.metadata.setdefault('roof_texture',texture_choice(building))
    old_floors=list(building.floors)
    template=old_floors[-1]
    building.floors=old_floors[:count]
    def remap(value,old,new):
        if isinstance(value,str):return value.replace(old,new)
        if isinstance(value,list):return [remap(v,old,new) for v in value]
        if isinstance(value,dict):return {remap(k,old,new):remap(v,old,new) for k,v in value.items()}
        return value
    for level in range(original,count):
        fid=f'{building.id}_floor_{level:02d}'
        data=remap(to_primitive(template),template.id,fid)
        data.update(id=fid,level=level,elevation_m=building.floors[-1].elevation_m+building.floors[-1].height_m)
        data['metadata']['exterior_height_template_source']=template.id
        building.floors.append(_floor(data))
    building.vertical_connectors=[c for c in building.vertical_connectors if c.from_level<count]
    for connector in building.vertical_connectors:
        if connector.to_level==original-1:connector.to_level=count-1
        else:connector.to_level=min(connector.to_level,count-1)
    high=building.metadata.get('highrise',{})
    if high.get('enabled'):
        podium=HighRisePolicy.podium_floors(count)
        groups=HighRisePolicy.annotate_typical_floors(building.id,building.floors,podium)
        high.update(HighRisePolicy.metadata(count,groups,massing_variant=high.get('massing_variant'),
            massing_palette=tuple(high.get('massing_palette',()))))
    building.metadata['floor_plate_contract']=HighRisePolicy.floor_plate_contract(
        building.footprint,count,high.get('massing_variant'),
        orientation_deg=float(building.metadata.get('orientation_deg',0)))
    contract=building.metadata.setdefault('height_contract',{})
    contract.update(source=KEY,min_floors=min(int(contract.get('min_floors',count)),count),
        max_floors=max(int(contract.get('max_floors',count)),count),realized_floors=count,
        recommended_floors=count,landmark=landmark,
        height_role='landmark' if landmark else 'highrise' if high.get('enabled') else 'lowrise' if count<=5 else 'midrise')
    building.metadata[KEY]={'before':original,'after':count,'delta':count-original,'landmark':landmark}


def vary_showcase_heights(source,seed=20261017,landmark_count=3):
    if source.metadata.get(KEY):raise ValueError('Already refined; use the retained pre-edit source for a new seed')
    scope=source.metadata.get('interior_scope',{})
    if scope.get('policy')!='prototype_exterior_only' or any(scope.get('building_levels',{}).values()):
        raise ValueError('This refinement requires an explicitly exterior-only city')
    city=deepcopy(source);buildings=list(city.iter_buildings())
    editable=[b for b in buildings if len(b.floors)>=2 and not b.metadata.get('vertical_zoning',{}).get('zones')]
    landmarks=select_landmarks(editable,landmark_count)
    changes=[]
    for b in editable:
        n=len(b.floors);lo,hi=floor_band(b)
        if b.id in landmarks:
            # Three distinct peaks, rather than another uniform landmark row.
            target=min(48,n+max(6,12-3*landmarks.index(b.id)))
        else:
            choices=[v for v in range(lo,hi+1) if v!=n]
            if not choices:continue
            target=random.Random(f'{seed}:showcase-height:{b.id}').choice(choices)
        resize_floor_stack(b,target,b.id in landmarks)
        changes.append({'building_id':b.id,'function':b.function,**b.metadata[KEY],
            'height_m':round(max(f.elevation_m+f.height_m for f in b.floors),3)})
    values=[len(b.floors) for b in buildings];hist=Counter(values)
    editable_ids={b.id for b in editable}
    report={'seed':seed,'landmarks':landmarks,'building_count':len(buildings),'changed_buildings':len(changes),
        'before_histogram':dict(sorted(Counter(len(b.floors) for b in source.iter_buildings()).items())),
        'after_histogram':dict(sorted(hist.items())),'changes':changes,
        'skipped_buildings':[b.id for b in buildings if b.id not in editable_ids]}
    city.metadata[KEY]=report
    city.metadata.setdefault('height_plan',{}).update(planner=KEY,
        realized_min_floors=min(values),realized_max_floors=max(values),
        realized_mean_floors=sum(values)/len(values),realized_floor_histogram={str(k):v for k,v in sorted(hist.items())},
        unique_realized_floor_count=len(hist),dominant_realized_floor_share=max(hist.values())/len(values),
        landmark_building_ids=landmarks,requested_landmark_count=len(landmarks),
        highrise_building_ids=[b.id for b in buildings if b.metadata.get('highrise',{}).get('enabled')],
        decision_sources={KEY:len(changes),'preserved':len(buildings)-len(changes)},
        height_role_histogram=dict(Counter(b.metadata.get('height_contract',{}).get('height_role','unspecified') for b in buildings)),
        height_zone_histogram=dict(Counter(b.metadata.get('height_contract',{}).get('height_zone','unspecified') for b in buildings)),
        function_floor_statistics={function:{'count':len(ns),'min':min(ns),'max':max(ns),
            'mean':sum(ns)/len(ns),'unique_floor_count':len(set(ns))} for function in {b.function for b in buildings}
            for ns in [[len(b.floors) for b in buildings if b.function==function]]})
    return city,report
