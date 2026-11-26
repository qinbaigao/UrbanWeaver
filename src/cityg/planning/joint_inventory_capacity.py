"""Bounded joint capacity planning for empty, newly generated floors.

Whole furniture bundles are placed at actual asset dimensions before accepting
floor changes. An end bay is a fallback topology, not an arbitrary floor editor:
shell, exterior doors and cores stay fixed; internal doors may be replanned.
"""
from copy import deepcopy
from dataclasses import asdict, replace
from itertools import combinations

from cityg.assets import AssetResolver
from cityg.ccwp import build_world_program
from cityg.interior_requirements import requirements_for
from cityg.planning.functional_seeds import find_inventory_witness
from cityg.planning.interior_frame import InteriorFrame, circulation_axis
from cityg.refinement.inventory_allocation import allocate_remaining_inventory
from cityg.schemas import Bounds2D, Door, Point2D, Room


def floor_capacity(building, floor, resolver, *, seed=17):
    rows = requirements_for(building, floor.level)
    functions = sorted({i['room_function'] for row in rows for i in row['inventory']})
    required = {fn for row in rows for fn in row['required_functions']}
    checks = [{'function':fn,'status':'missing_function','tested':0}
              for fn in sorted(required-{r.function for r in floor.rooms})]
    for function in functions:
        allocated = allocate_remaining_inventory(building, floor, function)
        if function not in required and not any(r.function == function for r in floor.rooms):
            checks.append({'function': function, 'status': 'missing_function', 'tested': 0})
        for room in floor.rooms:
            if room.id not in allocated:
                continue
            _, evidence = find_inventory_witness(building, floor, room, allocated[room.id], resolver, seed=seed)
            checks.append({'room_id': room.id, 'function': function,
                           'size_m': [room.bounds.width, room.bounds.depth],
                           'inventory': allocated[room.id], **evidence})
    failed = [c for c in checks if c['status'] == 'missing_function' or
              (c['status'] == 'no_reference_witness' and c['tested'] > 0)]
    return {'status': 'references_fit' if checks and all(c['status'] == 'metric_witness' for c in checks)
            else 'unresolved' if failed else 'partial_reference_coverage',
            'failed_functions': sorted({c['function'] for c in failed}), 'checks': checks,
            'compiled_furniture_verified': False}


def end_bay_proposals(building, floor, function, *, widths=(4.2, 4.8, 5.4, 6.0)):
    """At most four metric topologies, transposed for N/S entrances.

    Only uncontracted/fallback single-spine floors are eligible. Never replace
    a semantic spatial program, private units, occupied or protected rooms.
    """
    from cityg.planning.floor_repartition import _envelopes
    if (floor.objects or floor.metadata.get('dwelling_units') or
            floor.metadata.get('spatial_layout', {}).get('status') == 'accepted' or
            any(r.object_ids or any(r.metadata.get(k) for k in
                ('locked', 'protected', 'unit_id', 'room_design', 'spatial_requirement')) for r in floor.rooms)):
        return []
    corridors = [r for r in floor.rooms if r.function == 'corridor']
    if len(corridors) != 1:
        return []
    try:
        envs = _envelopes(building, floor)
    except ValueError:
        return []
    if any(any(abs(getattr(envs[r.id]['bounds'],k)-getattr(r.bounds,k))>1e-5
               for k in ('min_x','min_y','max_x','max_y')) for r in floor.rooms):
        return []
    frame = InteriorFrame(circulation_axis(building)); plate = frame.bounds(building.footprint)
    corridor = corridors[0]; cb = frame.bounds(corridor.bounds)
    if abs(cb.min_x-plate.min_x)>1e-5 or abs(cb.max_x-plate.max_x)>1e-5:
        return []
    exterior = [d for d in floor.doors if d.room_b_id is None]
    entry = frame.point(building.entrance)
    left_bay = abs(entry.x-plate.max_x)<1e-5
    if not left_bay and abs(entry.x-plate.min_x)>1e-5:
        return []
    existing = {}
    for room in floor.rooms:
        if room.function != 'corridor': existing.setdefault(room.function, room)
    if function not in existing:
        return []
    others = [fn for fn in existing if fn != function]
    if len(others)<2:
        return []
    proposals = []
    for width in widths:
        edge = plate.min_x+width if left_bay else plate.max_x-width
        bay = Bounds2D(plate.min_x if left_bay else edge,plate.min_y,
                       edge if left_bay else plate.max_x,plate.max_y)
        remaining = replace(cb, min_x=edge) if left_bay else replace(cb, max_x=edge)
        if remaining.width<4 or any(not remaining.contains_bounds(frame.bounds(core.bounds),tolerance=1e-6)
            for core in building.vertical_connectors if core.from_level<=floor.level<=core.to_level):
            continue
        if any(not remaining.contains_point(frame.point(d.position),tolerance=1e-6) or
               d.room_a_id != corridor.id for d in exterior):
            continue
        rooms = [replace(corridor,bounds=frame.bounds(remaining),metadata={})]
        doors = deepcopy(exterior)
        def add(fn, bounds, point):
            old = existing[fn]
            room = Room(old.id,old.name,fn,frame.bounds(bounds),old.height_m,
                        metadata={'joint_capacity_topology':'end_bay', 'detail_tier':'preview'})
            rooms.append(room)
            doors.append(Door(old.id+'_capacity_entry',old.id,corridor.id,frame.point(point)))
        add(function,bay,Point2D(edge,cb.center.y))
        for side, functions in enumerate((others[::2],others[1::2])):
            w = remaining.width/len(functions)
            for i, fn in enumerate(functions):
                x = remaining.min_x+i*w
                bounds = Bounds2D(x,plate.min_y if side==0 else cb.max_y,x+w,
                                  cb.min_y if side==0 else plate.max_y)
                if min(bounds.width,bounds.depth)<2:
                    break
                add(fn,bounds,Point2D(bounds.center.x,cb.min_y if side==0 else cb.max_y))
        if len(rooms)!=len(existing)+1:
            continue
        candidate = deepcopy(floor);candidate.rooms=rooms;candidate.doors=doors
        candidate.metadata = {k:v for k,v in floor.metadata.items() if k in
                              ('core_bounds','core_policy','floor_plate_zone','realized_floor_plate',
                               'program_role','vertical_role','vertical_zone','vertical_zone_id','vertical_use_type')}
        candidate.metadata['spatial_layout']={'status':'accepted','family':'inventory_end_bay'}
        candidate.metadata['joint_capacity_replan']={'retired_room_ids':sorted({r.id for r in floor.rooms}-{r.id for r in rooms}),
            'internal_doors_replanned':True,'exterior_doors_preserved':True,'target_function':function}
        if any(a.bounds.overlaps_area(b.bounds) for a,b in combinations(rooms,2)):
            continue
        if abs(sum(r.bounds.area for r in rooms)-building.footprint.area)>1e-5:
            continue
        proposals.append((width,candidate))
    return proposals


def repair_joint_capacity(city, compiler, registry, target_levels, *, selector=None,
                          preserve_partition=False, seed=17, max_floors=2):
    """Detached bounded proposals; full floor counts, entry/core and compile gate.

    Refused/unsupported proposals leave the original floor untouched. Runtime
    furnishing remains necessary; capacity witnesses are not furnished output.
    """
    from cityg.planning.floor_repartition import _check_compiled_access
    from cityg.validation import CityValidator
    resolver=AssetResolver(registry,(),max_provider_calls=0)
    result=deepcopy(city);report={'floors':[], 'max_floors':max_floors,'candidate_limit_per_floor':4,
                                'placement_seed':seed}
    for building in result.iter_buildings():
        for index, floor in enumerate(building.floors):
            if floor.level not in target_levels.get(building.id,[]) or not requirements_for(building,floor.level):
                continue
            before=floor_capacity(building,floor,resolver,seed=seed)
            row={'building_id':building.id,'floor_id':floor.id,'before':before,'after':before,'attempts':[]}
            report['floors'].append(row)
            if before['status']=='references_fit':
                floor.metadata['inventory_capacity']=before;row['status']='already_feasible';continue
            if preserve_partition or len([r for r in report['floors'] if r['attempts']])>=max_floors:
                row['status']='preserved_partition_or_budget';continue
            candidates=[];offered=[]
            for function in before['failed_functions'][:1]:
                for width, candidate in end_bay_proposals(building,floor,function):
                    checked=floor_capacity(building,candidate,resolver,seed=seed)
                    attempt={'width_m':width,'capacity':checked};row['attempts'].append(attempt)
                    if checked['status']!='references_fit': continue
                    pid=f'joint_capacity_{floor.id}_{len(candidates)}'
                    candidates.append((pid,candidate,checked))
                    offered.append({'id':pid,'kind':'whole_floor_inventory_capacity','floor_id':floor.id,
                        'building_id':building.id,'target_function':function,'bay_width_m':width,
                        'compatible_before':0,'compatible_after':len(checked['checks']),'shift_m':width,
                        'before_capacity':before,'after_capacity':checked,
                        'constraints':'New empty fallback floor only; preserve shell/exterior entry/core; replan internal doors',
                        'rooms':[{'room_id':r.id,'function':r.function,'bounds':asdict(r.bounds),
                                  'size_m':[r.bounds.width,r.bounds.depth]} for r in candidate.rooms]})
            if not candidates:row['status']='unresolved_no_verified_topology';continue
            from cityg.planning.generation_coordination import ordered_offers
            ordered,selection=ordered_offers(offered,result,selector)
            row['selection']=selection
            row['compile_attempts']=[]
            by_id={c[0]:c for c in candidates}
            for offer in ordered:
                _,candidate,checked=by_id[offer['id']]
                row['compile_attempts'].append(offer['id'])
                original_program=result.world_program
                try:
                    baseline=compiler.compile(result,building_ids={building.id})
                    locked={d.id for d in floor.doors if d.room_b_id is None}|{v.id for v in building.vertical_connectors}
                    def locks(scene):
                        return {p.id:(p.owner_id,p.center,p.size,p.rotation_z_deg) for p in scene.primitives if p.owner_id in locked}
                    building.floors[index]=candidate
                    result.world_program=build_world_program(result,producer='joint_inventory_capacity',seed=seed)
                    validation=CityValidator().validate(result)
                    if not validation.ok:raise ValueError('Joint floor semantic check failed: '+str(validation.to_dict()['issues'][:3]))
                    scene=compiler.compile(result,building_ids={building.id})
                    if locks(scene)!=locks(baseline):raise ValueError('Compiled exterior entry/core changed')
                    _check_compiled_access(scene,building,floor,candidate)
                    candidate.metadata['inventory_capacity']=checked
                    row.update(status='accepted',after=checked,compiled_floor_verified=True,
                               compiled_furniture_verified=False,exterior_entry_core_preserved=True)
                    break
                except ValueError as exc:
                    building.floors[index]=floor;result.world_program=original_program
                    row.update(status='rejected',error=str(exc))
    return result,report
