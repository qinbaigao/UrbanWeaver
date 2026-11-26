"""Advisory furnishing completeness, separate from hard placement safety.

Triggers bounded semantic reconsideration, never inserts furniture by itself.
Counts are not density targets; circulation and purposeful negative space win.
"""
from collections import Counter
import math


def compiled_footprint_area(objects, owners, building_rotation_deg):
    """Sum per-object realized XY boxes, not component counts/template sizes."""
    rotation=math.radians(building_rotation_deg)
    c,s=math.cos(rotation),math.sin(rotation)
    total=0.
    for obj in objects:
        points=[]
        for p in owners.get(obj.id,[]):
            if not p.semantic_class.startswith('furniture_'): continue
            a=math.radians(p.rotation_z_deg)
            for x in (-p.size.x/2,p.size.x/2):
                for y in (-p.size.y/2,p.size.y/2):
                    wx=p.center.x+x*math.cos(a)-y*math.sin(a)
                    wy=p.center.y+x*math.sin(a)+y*math.cos(a)
                    points.append((wx*c+wy*s,-wx*s+wy*c))
        if points:
            total+=(max(x for x,y in points)-min(x for x,y in points))*(max(y for x,y in points)-min(y for x,y in points))
    return total


FUNCTION_BUNDLES = {
    'bedroom': [('sleep',['bed','bedside_table']),('clothes',['wardrobe']),('reading_or_work',['desk','bookcase'])],
    'living_room': [('seating',['sofa','coffee_table']),('media',['tv_console']),('reading_or_storage',['bookcase','cabinet'])],
    'office': [('work',['desk','office_chair']),('documents',['cabinet','bookcase']),('visitor_or_discussion',['meeting_table','meeting_chair'])],
    'open_office': [('work',['desk','office_chair']),('documents',['cabinet','bookcase']),('discussion',['meeting_table','meeting_chair'])],
    'kitchen': [('preparation',['kitchen_counter','sink']),('dining',['dining_table','dining_chair'])],
    'break_room': [('refreshment',['kitchen_counter']),('seating',['dining_table','dining_chair'])],
    'shop': [('checkout',['checkout_counter']),('display',['display_shelf']),('stock',['storage_rack'])],
    'reception': [('service',['reception_desk']),('waiting',['waiting_bench','coffee_table'])],
    'waiting_room': [('waiting',['waiting_bench','coffee_table']),('service',['desk','office_chair'])],
    'meeting_room': [('meeting',['meeting_table','meeting_chair']),('presentation_or_storage',['tv_console','cabinet'])],
    'storage': [('stock',['storage_rack']),('administration',['desk','office_chair'])],
}


ESSENTIAL_BUNDLES = {
    'bedroom': [('sleep', ['bed'])],
    'office': [('work_surface', ['desk']), ('work_seating', ['office_chair'])],
    'open_office': [('work_surface', ['desk']), ('work_seating', ['office_chair'])],
    'meeting_room': [('meeting_surface', ['meeting_table']), ('meeting_seating', ['meeting_chair'])],
    'living_room': [('primary_seating', ['sofa'])],
    'restaurant': [('dining_surface', ['dining_table']), ('dining_seating', ['dining_chair'])],
    'shop': [('checkout', ['checkout_counter']), ('display', ['display_shelf'])],
    'kitchen': [('preparation', ['kitchen_counter']), ('washing', ['sink'])],
}


def assess_furnishing(room, objects, *, area_m2=None, surface_report=None, realized_footprint_m2=None):
    area=area_m2 if area_m2 is not None else room.bounds.area
    objects=[o for o in objects if o.room_id==room.id]
    counts=Counter(o.category for o in objects)
    footprint=0.
    for obj in objects:
        dims=obj.metadata.get('metric_room_placement',{}).get('dimensions_m')
        footprint+=dims[0]*dims[1] if dims else obj.width_m*obj.depth_m
    if realized_footprint_m2 is not None: footprint=realized_footprint_m2
    occupancy=footprint/max(area,1e-6)
    groups={o.metadata.get('group_key',o.id) for o in objects}
    suggestions=[{'purpose':purpose,'candidate_categories':categories}
                 for purpose,categories in FUNCTION_BUNDLES.get(room.function,[])
                 if not any(counts[c] for c in categories)]
    reasons=[]
    essential=[{'purpose':purpose,'candidate_categories':cats}
               for purpose,cats in ESSENTIAL_BUNDLES.get(room.function,[])
               if not any(counts[c] for c in cats)]
    if essential: reasons.append('missing_primary_functional_bundle')
    if area>=18 and occupancy<.10:
        reasons.append('low_furniture_footprint_for_available_area')
    if area>=28 and len(groups)<3 and suggestions:
        reasons.append('secondary_functional_bundle_not_considered')
    design=room.metadata.get('room_design',{})
    brief=design.get('furnishing_brief') or {}
    shortfalls=[{'category':i['category'],'target':i['target'],'placed':counts[i['category']]}
                for i in brief.get('items',[]) if counts[i['category']]<i['target']]
    if shortfalls: reasons.append('inventory_targets_unrealized')
    requested=(surface_report or {}).get('requested',0)
    placed=(surface_report or {}).get('placed',0)
    if requested and placed/requested<.7: reasons.append('support_dressing_low_realization')
    return {'policy':'advisory_furnishing_sufficiency_v1','needs_review':bool(reasons),
            'reasons':reasons,'area_m2':round(area,3),'major_count':len(objects),
            'major_footprint_ratio':round(occupancy,4),'group_count':len(groups),
            'category_counts':dict(counts),'candidate_functional_bundles':suggestions,
            'missing_essential_bundles':essential,'inventory_shortfalls':shortfalls,'surface_requested':requested,'surface_placed':placed,
            'surface_failures':(surface_report or {}).get('skipped',[]),
            'policy_note':'Advisory, not a minimum density. Do not fill circulation or add unrelated functions; explain deliberate spaciousness.'}
