"""Opt-in review adapters. No production selection, approvals or asset scaling.

Floor boundary maps are explicit proposals, not a general floor solver.
Room designs rotate constraints and are solved again at real asset dimensions.
"""
from copy import deepcopy
from dataclasses import replace
import math

from cityg.assets import AssetResolver
from cityg.planning.floor_prototypes import box, circulation_raster
from cityg.planning.interiors import ASSET_CATALOG, FloorDetailAgent
from cityg.planning.prototypes import fingerprint, reference_registry
from cityg.planning.room_design import RoomDesign
from cityg.planning.room_envelope import metric_envelope


def boundary_map(knots, extent, variation_limit):
    if (not isinstance(knots,(list,tuple)) or len(knots)<2 or
            any(not isinstance(p,(list,tuple)) or len(p)!=2 or
                any(type(v) not in (int,float) or not math.isfinite(v) for v in p) for p in knots)):
        raise ValueError('Boundary map requires finite source/target pairs')
    if knots[0]!=[0,0] and knots[0]!=(0,0):raise ValueError('Boundary map starts at the plate origin')
    if abs(knots[-1][0]-extent)>1e-6:raise ValueError('Boundary map must span the plate')
    if any(b[0]<=a[0] or b[1]<=a[1] for a,b in zip(knots,knots[1:])):
        raise ValueError('Boundary map must be strictly monotone')
    if any(abs(t-s)>extent*variation_limit+1e-6 for s,t in knots):
        raise ValueError('Partition adjustment exceeds variation budget')
    def transform(value):
        for (s0,t0),(s1,t1) in zip(knots,knots[1:]):
            if s0-1e-6<=value<=s1+1e-6:return t0+(value-s0)*(t1-t0)/(s1-s0)
        raise ValueError('Coordinate outside boundary map')
    return transform


def adapt_floor_reference(library,key,*,x_knots=None,y_knots=None,variation_limit=.2,locked_cores=None,door_fractions=()):
    """Detached candidate; preserve door widths and physical core dimensions.

    locked_cores optionally pins every stack to existing *local* rectangles.
    Reject incompatible pins rather than moving stairs or shrinking landings.
    """
    if type(variation_limit) not in (int,float) or not math.isfinite(variation_limit) or not 0<=variation_limit<=.3:
        raise ValueError('variation_limit must be within [0,.3]')
    original=library.floors[key];r=deepcopy(original)
    w,d=(r['reference'][k] for k in ('width_m','depth_m'))
    x_knots=x_knots if x_knots is not None else [[0,0],[w,w]]
    y_knots=y_knots if y_knots is not None else [[0,0],[d,d]]
    mx,my=boundary_map(x_knots,w,variation_limit),boundary_map(y_knots,d,variation_limit)
    def rectangle(v):return [mx(v[0]),my(v[1]),mx(v[2]),my(v[3])]
    r['reference'].update(width_m=mx(w),depth_m=my(d))
    for s in r['spaces']:s['bounds_m']=rectangle(s['bounds_m'])
    for u in r['units']:u['bounds_m']=rectangle(u['bounds_m'])
    seen=set()
    for proposal in door_fractions:
        pair=frozenset((proposal['a'],proposal['b']))
        if pair in seen:raise ValueError('Duplicate door adjustment')
        seen.add(pair)
        c=next((c for c in r['connections'] if frozenset((c['a'],c['b']))==pair),None)
        value=proposal['fraction']
        if (c is None or c['kind']!='door' or type(value) not in (int,float) or not math.isfinite(value)
                or abs(value-c['fraction'])>variation_limit+1e-6):
            raise ValueError('Unknown door or adjustment exceeds variation budget')
        c['fraction']=value
    if locked_cores is not None and set(locked_cores)!={c['stack_key'] for c in r['cores']}:
        raise ValueError('Locked core contract must name every stack')
    for c in r['cores']:
        b=box(c['bounds_m'])
        if locked_cores is None:
            x,y=mx(b.center.x),my(b.center.y)
            c['bounds_m']=[x-b.width/2,y-b.depth/2,x+b.width/2,y+b.depth/2]
        else:
            pinned=box(locked_cores[c['stack_key']])
            if abs(pinned.width-b.width)>1e-6 or abs(pinned.depth-b.depth)>1e-6:
                raise ValueError('Core dimensions cannot change')
            c['bounds_m']=list(locked_cores[c['stack_key']])
    # Shared boundaries, door corners, units and core landings are revalidated.
    validation=library.validate(r);walk=circulation_raster(r)
    if not walk['ok']:raise ValueError('Adapted floor has disconnected circulation')
    r['review']={'status':'pending_review'}
    r['adaptation']={'source_id':key,'source_fingerprint':library.content_fingerprint(key),
        'boundary_maps':{'x':deepcopy(x_knots),'y':deepcopy(y_knots)},
        'door_fraction_proposals':deepcopy(list(door_fractions)),
        'variation_limit':variation_limit,'core_sizes_preserved':True,'core_locked':locked_cores is not None,
        'door_widths_preserved':True,'production_enabled':False}
    return r,{'layout':validation,'circulation':walk,'adapted_fingerprint':fingerprint(r)}


SIDES=('south','east','north','west')


def rotate_side(side,turns):
    return SIDES[(SIDES.index(side)+turns)%4] if side in SIDES else side


def rotate_uv(bounds,turns):
    corners=[(bounds[i],bounds[j]) for i in (0,2) for j in (1,3)]
    for _ in range(turns%4):corners=[(1-y,x) for x,y in corners]
    return [round(v,12) for v in (min(x for x,y in corners),min(y for x,y in corners),
            max(x for x,y in corners),max(y for x,y in corners))]


def rotated_design(prototype,turns):
    if type(turns) is not int or not 0<=turns<4:raise ValueError('Use quarter turns 0..3')
    data=deepcopy(prototype.design.to_dict())
    for zone in data['zones']:
        zone['position']=rotate_side(zone['position'],turns)
        if 'bounds_uv' in zone:zone['bounds_uv']=rotate_uv(zone['bounds_uv'],turns)
    for area in data.get('reserved_areas',[]):area['bounds_uv']=rotate_uv(area['bounds_uv'],turns)
    for group in data['groups']:
        for key in ('wall','facing'):
            if key in group.get('placement',{}):group['placement'][key]=rotate_side(group['placement'][key],turns)
    return replace(prototype,design=RoomDesign.from_dict(data,ASSET_CATALOG))


def door_side(room,door):
    b=room.bounds;p=door.position
    distances={'south':abs(p.y-b.min_y),'north':abs(p.y-b.max_y),
               'west':abs(p.x-b.min_x),'east':abs(p.x-b.max_x)}
    side=min(distances,key=distances.get)
    if distances[side]>.05 or not b.contains_point(p,tolerance=.05):
        raise ValueError('Door is not on the realized room boundary')
    length=b.width if side in ('south','north') else b.depth
    offset=p.x-b.min_x if side in ('south','north') else p.y-b.min_y
    if min(offset,length-offset)<door.width_m/2+.12-1e-6:
        raise ValueError('Room entrance crosses a corner')
    return side


def room_candidates(library,building,floor,room):
    envelope=metric_envelope(building,floor,room)
    if envelope['status']!='supported':return []
    metric=envelope['room'];doors=envelope['floor'].doors
    # Multiple entrances are all retained by the solver, but choose a single
    # orientation contract explicitly and deterministically for the design.
    if not doors:return []
    sides=list(dict.fromkeys(door_side(metric,d) for d in sorted(doors,key=lambda d:d.id)))
    result=[]
    for side in sides:
        turns=SIDES.index(side);b=metric.bounds
        w,d=(b.depth,b.width) if turns%2 else (b.width,b.depth)
        for key in sorted(library.rooms):
            if library.compatible(key,room_type=room.function,width_m=w,depth_m=d,height_m=room.height_m):
                result.append({'prototype_id':key,'quarter_turns':turns,'primary_door_side':side,
                    'door_count':len(doors),'status':'candidate_only'})
    return result


def populate_adapted_room(city,building,floor,room,library,registry,candidate,*,review_only=False,
                         placement_seed=17,personalization=None, variation_limit=.2,design_adjustments=None,design_limits=None):
    """Semantic placement transaction; caller must gate compiled output, too."""
    if not review_only:raise ValueError('Prototype adaptation is review-only, not production-approved')
    if candidate not in room_candidates(library,building,floor,room):
        raise ValueError('Stale or incompatible room candidate')
    key=candidate['prototype_id'];turns=candidate['quarter_turns']
    source=library.rooms[key];prototype=library.materialize(key)
    from cityg.planning.prototypes import fingerprint
    baseline=rotated_design(prototype,turns)
    baseline_fingerprint=fingerprint({'design':baseline.design.to_dict(),'asset_bindings':baseline.asset_bindings})
    if personalization:
        from cityg.agents.room_reference import personalize_reference
        prototype=personalize_reference(prototype,personalization,variation_limit)
    if design_adjustments:
        from cityg.planning.reference_variations import personalize_design
        prototype=personalize_design(prototype,design_adjustments,library,design_limits)
    prototype=rotated_design(prototype,turns)
    effective_fingerprint=fingerprint({'design':prototype.design.to_dict(),'asset_bindings':prototype.asset_bindings})
    design_changed=effective_fingerprint!=baseline_fingerprint
    pinned=reference_registry(registry,prototype)
    metadata=deepcopy(room.metadata);objects=deepcopy(floor.objects);ids=list(room.object_ids)
    try:
        detail=FloorDetailAgent(asset_resolver=AssetResolver(pinned,(),max_provider_calls=0),
            program_overrides={room.id:prototype.program(room.id)})
        room.metadata.update(detail_tier='hero',detail_level='hero')
        previous=[o for o in floor.objects if o.room_id==room.id]
        preview_count=0
        if previous and all(o.metadata.get('preview_only') is True for o in previous):
            # Explicit placeholders are not a reviewed furnishing contract.
            # Never bypass the non-degradation gate for real/mixed inventories.
            preview_count=len(previous)
            floor.objects[:]=[o for o in floor.objects if o.room_id!=room.id];room.object_ids.clear()
        stats=detail.populate_rooms(city,{room.id},seed=placement_seed)
        actual=[o for o in floor.objects if o.room_id==room.id]
        expected=sum(1+len(g['members']) for g in prototype.design.groups)
        if (stats['furnishing_non_degradation_gate_rejected_room_count'] or len(actual)!=expected or
                room.metadata.get('room_design',{}).get('status')!='accepted' or
                any(o.asset_id!=prototype.asset_bindings[o.category] for o in actual)):
            raise ValueError('Incomplete inventory or substituted asset')
        decorations=deepcopy(source.get('decorations',[]))
        for q in decorations:
            if 'walls' in q:q['walls']=[rotate_side(s,turns) for s in q['walls']]
        room.metadata.update(layout_prototype_id=key,layout_prototype_fingerprint=prototype.content_fingerprint,
            prototype_adaptation={**candidate,'production_enabled':False,
                                 'effective_fingerprint':effective_fingerprint,
                                 'reference_effective_fingerprint':baseline_fingerprint,
                                 'design_changed':design_changed,
                                 'design_adjustments':deepcopy(design_adjustments or {}),
                                 'spacing_adjustments':deepcopy(personalization or [])},room_decorations=decorations)
        if source.get('finishes'):room.metadata['room_finishes']=deepcopy(source['finishes'])
        return {**candidate,'room_id':room.id,'building_id':building.id,'floor_id':floor.id,
            'content_fingerprint':prototype.content_fingerprint,'major_count':len(actual),'stats':stats,
            'effective_fingerprint':effective_fingerprint,
            'reference_effective_fingerprint':baseline_fingerprint,'design_changed':design_changed,
            'spacing_adjustments':deepcopy(personalization or []),
            'design_adjustments':deepcopy(design_adjustments or {}),
            'replaced_preview_object_count':preview_count,
            'expected_inventory':{'room_surface_items':sum(q['count'] for q in prototype.design.surface_items),
                                  'room_decorations':len(decorations)},
            'asset_bindings':prototype.asset_bindings,'compiled_verified':False}
    except Exception:
        room.metadata=metadata;floor.objects[:]=objects;room.object_ids[:]=ids
        raise
