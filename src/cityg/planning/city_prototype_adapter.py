"""Apply room references to an existing city without replacing its architecture.

Whole-floor references are assessed but not transplanted without a verified
entry/core correspondence. This first live-city path retains every partition,
door, core, building footprint and ID. Each room is a compiled transaction.
"""
from collections import Counter
from copy import deepcopy
from dataclasses import replace
import math

from cityg.ccwp import build_world_program
from cityg.geometry.model import Vec3
from cityg.geometry.room_decorations import box_bounds
from cityg.geometry.surface_dressing import surfaces, overlaps
from cityg.planning.prototype_adaptation import room_candidates, populate_adapted_room
from cityg.planning.prototype_integration import floor_candidates
from cityg.planning.room_envelope import metric_envelope
from cityg.planning.room_regions import region_bounds, reserved_bounds
from cityg.serialization import to_primitive
from cityg.validation import CityValidator


def architecture(city):
    """Only room metadata, inventory and compile scope may change in this mode."""
    data=to_primitive(city)
    data.pop('world_program',None)
    data['metadata'].pop('interior_scope',None)
    data['metadata'].pop('city_prototype_adaptation',None)
    # Derived index legitimately gains the new furniture IDs after CCWP rebuild.
    data['metadata'].pop('identity_registry',None)
    for district in data['districts']:
        for parcel in district['parcels']:
            for b in parcel['buildings']:
                for f in b['floors']:
                    f['objects']=[]
                    for r in f['rooms']:r['metadata']={};r['object_ids']=[]
    return data


def validate_options(options):
    allowed={'max_buildings','max_floors_per_building','max_rooms','max_attempts','max_attempts_per_room','variation_limit','floor_repartition','design_variation'}
    if set(options)-allowed:raise ValueError('Unknown adaptation config fields')
    result={'max_buildings':3,'max_floors_per_building':2,'max_rooms':10,
            'max_attempts':None,'max_attempts_per_room':3,'variation_limit':.2,**options}
    from cityg.planning.reference_variations import variation_limits
    result['design_variation'] = variation_limits(result.get('design_variation'))
    for key,cap in [('max_buildings',10),('max_floors_per_building',3)]:
        if type(result[key]) is not int or not 1<=result[key]<=cap:raise ValueError('Invalid budget: '+key)
    for key in ('max_rooms','max_attempts_per_room'):
        if type(result[key]) is not int or result[key]<1:raise ValueError('Invalid budget: '+key)
    # A finite work budget, not a limit on scene size. Explicit totals remain
    # authoritative; null/missing scales with the requested fine-room count.
    if result['max_attempts'] is None:
        result['max_attempts']=result['max_rooms']*result['max_attempts_per_room']
    if type(result['max_attempts']) is not int or result['max_attempts']<1:
        raise ValueError('Invalid budget: max_attempts')
    v=result['variation_limit']
    if type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=.3:raise ValueError('Invalid variation_limit')
    if 'floor_repartition' in result:
        from cityg.planning.floor_repartition import options as floor_options
        result['floor_repartition']=floor_options(result['floor_repartition'])
    return result


def verify_room(scene,building,floor,room,row):
    """Post-compile checks in the actual unrotated building frame."""
    env=metric_envelope(building,floor,room)
    if env['status']!='supported':raise ValueError('Unsupported compiled room envelope')
    b=env['bounds'];origin=building.footprint.center;yaw=building.metadata.get('orientation_deg',0)
    c,s=math.cos(math.radians(-yaw)),math.sin(math.radians(-yaw))
    def local(p):
        x,y=p.center.x-origin.x,p.center.y-origin.y
        return replace(p,center=Vec3(origin.x+c*x-s*y,origin.y+s*x+c*y,p.center.z),rotation_z_deg=p.rotation_z_deg-yaw)
    objs={o.id:o for o in floor.objects if o.room_id==room.id}
    design = room.metadata.get('room_design', {})
    zones={z['id']:region_bounds(b,z['bounds_uv']) for z in design.get('zones', []) if 'bounds_uv' in z}
    aisles=reserved_bounds(b,design.get('reserved_areas',[]))
    checks=[];seen=set()
    for p in scene.primitives:
        obj=objs.get(p.owner_id)
        decor=p.owner_id==room.id and p.metadata.get('decoration_kind') in ('floor_asset','rug')
        if not decor and (obj is None or not p.semantic_class.startswith('furniture_')):continue
        bb=box_bounds(local(p));zone=zones.get(obj.metadata.get('zone_id')) if obj else None
        checks.append({'kind':'metric_containment','entity':p.id,'ok':b.contains_bounds(bb,tolerance=1e-5)
            and (zone is None or zone.contains_bounds(bb,tolerance=1e-5)) and not any(a.overlaps_area(bb) for a in aisles)})
        if obj:seen.add(obj.id)
    checks.append({'kind':'compiled_major_inventory','ok':seen==set(objs) and len(objs)==row['major_count']})
    for kind,expected in row['expected_inventory'].items():
        actual=scene.metadata.get(kind,{}).get(room.id,{})
        checks.append({'kind':kind,'expected':expected,'placed':actual.get('placed',0),
            'ok':expected==actual.get('placed',0)==actual.get('requested',0)})
    by_id={p.id:p for p in scene.primitives}
    children=[p for p in scene.primitives if p.metadata.get('surface_subentity') and room.id in p.metadata.get('room_ids',[])]
    for p in children:
        support=by_id[p.metadata['support_primitive_id']]
        kind='shelves' if p.metadata['support_kind']=='shelf' else 'top'
        surface=next(q for q in surfaces([support],kind) if q.id==p.metadata['support_surface_id'])
        angle=math.radians(-surface.yaw);dx,dy=p.center.x-surface.center.x,p.center.y-surface.center.y
        x,y=dx*math.cos(angle)-dy*math.sin(angle),dx*math.sin(angle)+dy*math.cos(angle)
        a=math.radians(p.rotation_z_deg-surface.yaw)
        w=abs(math.cos(a))*p.size.x+abs(math.sin(a))*p.size.y
        d=abs(math.sin(a))*p.size.x+abs(math.cos(a))*p.size.y
        bottom=p.center.z-p.size.z/2
        supported=(abs(x)+w/2<=surface.width/2+1e-6 and abs(y)+d/2<=surface.depth/2+1e-6
            and bottom>=surface.center.z-1e-6)
        if p.metadata.get('resolved_asset'):supported &= abs(bottom-surface.center.z)<1e-6
        if surface.clearance_m is not None:supported &= p.center.z+p.size.z/2<=surface.center.z+surface.clearance_m+1e-6
        checks.append({'kind':'surface_support','entity':p.id,'ok':supported})
    for i,a in enumerate(children):
        for b in children[i+1:]:
            if a.metadata['subentity_id']!=b.metadata['subentity_id'] and overlaps(a,b,gap=0):
                checks.append({'kind':'surface_overlap','entity':a.id,'ok':False})
    if not all(c['ok'] for c in checks):raise ValueError('Compiled room verification failed: '+str([c for c in checks if not c['ok']][:5]))
    return checks


def adapt_city_rooms(source,library,registry,compiler,options=None,progress=None,target_levels=None,
                     reference_selector=None):
    """Detached result; only successful compiled proposals survive."""
    opt=validate_options(options or {});city=deepcopy(source)
    before=architecture(source);scan=[];floor_audits=[];candidates=[]
    for b in city.iter_buildings():
        for f in sorted(b.floors,key=lambda f:f.level):
            if target_levels is not None and f.level not in target_levels.get(b.id,[]):continue
            audit=floor_candidates(b,f,library,variation_limit=opt['variation_limit'])
            floor_audits.append({'building_id':b.id,'floor_id':f.id,'level':f.level,
                'placement_executed':False,'mode':'preserve_existing_floor_and_core',
                'status':audit['status'],'candidate_ids':[c['prototype_id'] for c in audit['candidates']],
                'note':('Locked-skeleton repartition already applied; room stage retains this geometry.'
                        if f.metadata.get('floor_repartition') else
                        'No verified whole-floor entry/core mapping; original floor retained.')})
            for room in f.rooms:
                if room.function=='corridor':continue
                try:cs=room_candidates(library.room_library,b,f,room)
                except ValueError as exc:
                    scan.append({'room_id':room.id,'status':'geometry_rejected','reason':str(exc)});continue
                if cs:
                    hint=room.metadata.get('joint_room_plan',{}).get('prototype_id')
                    cs.sort(key=lambda c:c['prototype_id']!=hint)
                    candidates.append((b,f,room,cs))
                else:scan.append({'room_id':room.id,'status':'no_compatible_reference'})
    # Stable geometric priors, followed by actual round-robin distribution.
    candidates.sort(key=lambda x:(not bool(x[2].metadata.get('joint_room_plan',{}).get('prototype_id')),
                                  x[1].level,x[0].id,x[2].id))
    from cityg.agents.room_reference import balanced_candidates, coverage_key, validate_choice
    from cityg.transactions import fingerprint
    candidates=balanced_candidates(candidates)
    selection={'status':'not_requested','choices':[]}; choices={}
    if reference_selector is not None and candidates:
        selection=reference_selector(city,candidates,library.room_library,opt)
        if selection.get('status')=='proposed':
            if selection.get('scene_fingerprint') != fingerprint(city):
                raise ValueError('Room reference proposal is stale')
            checked=validate_choice({'choices':selection['choices']},candidates,library.room_library,
                                    selection.get('original_instruction',''),opt)
            from cityg.design_goals import goal_context
            known={g['id'] for g in goal_context(city.metadata.get('design_goals',[]),'room')}
            if any(not set(c.get('goal_ids',[]))<=known for c in checked):
                raise ValueError('Room reference cites unknown shared goals')
            choices={c['room_id']:c for c in checked}
            priority={key:i for i,key in enumerate(choices)}
            candidates.sort(key=lambda row:priority.get(row[2].id,len(priority)))
    selected={};accepted=[];attempts=[];room_budget_exhausted=[]
    from cityg.planning.prototype_inventory import rooms_by_unmet_inventory
    for b,f,room,cs in rooms_by_unmet_inventory(candidates, library.room_library, opt['max_rooms']):
        if len(accepted)>=opt['max_rooms'] or len(attempts)>=opt['max_attempts']:break
        if b.id not in selected and len(selected)>=opt['max_buildings']:continue
        levels=selected.get(b.id,set())
        if f.level not in levels and len(levels)>=opt['max_floors_per_building']:continue
        choice=choices.get(room.id)
        if choice:
            cs=sorted(cs,key=lambda c:not (c['prototype_id']==choice['prototype_id'] and
                                          c['quarter_turns']==choice['quarter_turns']))
        # Recompute after each committed room so floor-level quantities are not
        # copied into every same-function room. Preserve agent order among
        # equally complete references, and retain incomplete fallbacks.
        from cityg.refinement.inventory_allocation import allocate_remaining_inventory
        from cityg.planning.prototype_inventory import prioritize_inventory
        allocated_inventory=allocate_remaining_inventory(b,f,room.function).get(room.id,[])
        cs=prioritize_inventory(cs,library.room_library,allocated_inventory)
        jobs=[]
        for candidate in cs:
            matched=bool(choice and candidate['prototype_id']==choice['prototype_id'] and
                         candidate['quarter_turns']==choice['quarter_turns'])
            edits=choice.get('design_adjustments',{}) if matched else {}
            if matched and (choice['spacing_adjustments'] or any(edits.values())):
                jobs.append((candidate,choice['spacing_adjustments'],edits,'agent_personalized'))
            jobs.append((candidate,[],{}, 'agent_reference' if matched else
                         'deterministic_fallback' if reference_selector else 'deterministic_feasibility'))
        room_attempts=0
        # Exhaust distinct references before a second placement search. Only a
        # local layout-search rejection can be resolved by changing its seed.
        jobs = [(candidate,patch,adjustments,source,17) for candidate,patch,adjustments,source in jobs]
        for candidate,patch,design_patch,selection_source,placement_seed in jobs:
            if len(attempts)>=opt['max_attempts']:break
            if room_attempts>=opt['max_attempts_per_room']:
                room_budget_exhausted.append(room.id)
                break
            room_attempts+=1
            old_metadata=deepcopy(room.metadata);old_objects=deepcopy(f.objects);old_ids=list(room.object_ids)
            old_city_metadata=deepcopy(city.metadata);old_program=city.world_program
            try:
                if progress:progress('attempt',room.id,candidate['prototype_id'])
                row=populate_adapted_room(city,b,f,room,library.room_library,registry,candidate,review_only=True,
                    placement_seed=placement_seed,personalization=patch,variation_limit=opt['variation_limit'],
                    design_adjustments=design_patch,design_limits=opt['design_variation'])
                if f.metadata.get('inventory_capacity',{}).get('status')=='references_fit':
                    counts=Counter(o.category for o in f.objects if o.room_id==room.id)
                    missing=[i for i in allocated_inventory if counts[i['category']]<i['min_count']]
                    if missing:
                        raise ValueError('Reference would consume certified functional capacity with '
                                         'incomplete furniture bundle: '+str(missing))
                if selection_source=='agent_personalized' and not row['design_changed']:
                    selection_source='agent_reference'
                row.update(placement_seed=placement_seed,room_function=room.function,coverage_group=coverage_key(b,room),
                    allocated_inventory=allocated_inventory,
                    selection_source=selection_source,selection_reason=choice['reason'] if choice else None,
                    requirement_quote=choice['requirement_quote'] if choice else None,
                    goal_ids=choice.get('goal_ids',[]) if choice else [])
                if city.metadata.get('interior_scope') is not None:
                    scope=city.metadata['interior_scope'];mapping=scope['building_levels']
                    mapping[b.id]=sorted(set(mapping.get(b.id,[]))|{q.level for q in b.floors if 0<=q.level<=f.level})
                    scope['policy']='prototype_adapter_preserve_scope_union'
                city.world_program=build_world_program(city,producer='existing_city_prototype_adapter',seed=17)
                semantic=CityValidator().validate(city)
                if not semantic.ok:raise ValueError('City validation failed: '+str(semantic.to_dict()['issues'][:3]))
                scene=compiler.compile(city,building_ids={b.id})
                row['checks']=verify_room(scene,b,f,room,row)
                row['compiled_verified']=True;accepted.append(row)
                selected.setdefault(b.id,set()).add(f.level)
                attempts.append({'room_id':room.id,**candidate,'status':'accepted','selection_source':selection_source,'placement_seed':placement_seed})
                if progress:progress('accepted',room.id,row['major_count'])
                break
            except ValueError as exc:
                room.metadata=old_metadata;f.objects[:]=old_objects;room.object_ids[:]=old_ids
                city.metadata=old_city_metadata;city.world_program=old_program
                attempts.append({'room_id':room.id,**candidate,'status':'rejected','reason':str(exc),'placement_seed':placement_seed,
                                 'selection_source':selection_source,'spacing_adjustments':patch,
                                 'design_adjustments':design_patch})
                if (placement_seed == 17 and not patch and not any(design_patch.values())
                        and ('no complete layout' in str(exc) or 'cannot fit with furniture' in str(exc))):
                    jobs.append((candidate,[],{},'local_placement_retry',31))
                if progress:progress('rejected',room.id,str(exc)[:200])
    if architecture(city)!=before:raise ValueError('Architecture or unrelated city state changed')
    report={'schema_version':1,'mode':'existing_city_room_adaptation','whole_floor_replacements':0,
        'production_approved':False,'llm_used':bool(selection.get('attempts')),'vlm_used':False,'source_mutated':False,
        'reference_selection':selection,
        'architecture_preserved':True,'options':opt,'floors':floor_audits,'room_scan':scan,
        'stop_reason':('target_reached' if len(accepted)>=opt['max_rooms'] else
                       'total_attempt_budget' if len(attempts)>=opt['max_attempts'] else
                       'eligible_candidates_exhausted'),
        'room_budget_exhausted':room_budget_exhausted,
        'attempts':attempts,'rooms':accepted,'selected_levels':{k:sorted(v) for k,v in selected.items()},
        'summary':{'candidate_rooms':len(candidates),'accepted_rooms':len(accepted),
            'selected_buildings':len(selected),'major_objects':sum(r['major_count'] for r in accepted),
            'functional_coverage':dict(Counter(r['coverage_group'] for r in accepted)),
            'room_function_coverage':dict(Counter(r['room_function'] for r in accepted)),
            'uncovered_available_groups':sorted({coverage_key(b,r) for b,_,r,_ in candidates}-
                                                 {r['coverage_group'] for r in accepted}),
            'scan_status':dict(Counter(s['status'] for s in scan)),'rejected_attempts':sum(a['status']=='rejected' for a in attempts)}}
    city.metadata['city_prototype_adaptation']={k:deepcopy(report[k]) for k in ('mode','architecture_preserved','selected_levels','summary')}
    return city,report
