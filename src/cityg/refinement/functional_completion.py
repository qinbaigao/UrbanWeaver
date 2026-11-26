"""Bounded inventory completion using the shared Room Agent transaction gates."""
from dataclasses import asdict
from cityg.interior_requirements import evaluate_requirements, requirements_for


def complete_inventory(city, service, compiler, registry, *, max_rooms=4, seed=17,
                       memory_store=None, on_attempts=None):
    from cityg.assets import AssetResolver
    from cityg.refinement.room import RoomProgramAgent
    from cityg.refinement.room_preflight import prepare_preflight
    from cityg.refinement.room_commit import commit_room_program
    from cityg.agents import AgentGenerationError
    from cityg.repair import PatchRejected
    from cityg.refinement.inventory_allocation import allocate_remaining_inventory
    rows=[r for b in city.iter_buildings() for r in requirements_for(b)]
    before=evaluate_requirements(city,rows); attempts=[]; seen=set(); attempted_functions={}
    resolver=AssetResolver(registry,(),max_provider_calls=0)
    agent=RoomProgramAgent(service,asset_resolver=resolver,max_attempts=3,
                           review_sufficiency=True,placement_seed=seed)
    for _ in range(max_rooms):
        deficits=evaluate_requirements(city,rows)
        jobs=[]
        for row in deficits:
            functions={i['room_function'] for i in row.get('inventory_shortfalls',[])}
            for b in city.iter_buildings():
                if b.id!=row['building_id']: continue
                for f in b.floors:
                    if f.level!=row['level']: continue
                    allocations={rid:items for function in functions
                        for rid,items in allocate_remaining_inventory(b,f,function,excluded=seen).items()}
                    required_groups = {}
                    for check in row.get('single_table_seating', []):
                        if check['ok']:
                            continue
                        candidates = [r for r in f.rooms if r.function == check['room_function'] and r.id not in seen]
                        if not candidates:
                            continue
                        chosen = max(candidates, key=lambda r:(r.id in allocations,r.bounds.area))
                        targets = allocations.setdefault(chosen.id, [])
                        for category, count in ((check['anchor'], 1), (check['seat'], check['required'])):
                            target = next((i for i in targets if i['category']==category), None)
                            if target:
                                target['min_count'] = max(count,target['min_count'])
                            else:
                                targets.append({'category':category,'room_function':chosen.function,'min_count':count})
                        required_groups.setdefault(chosen.id, []).append(check)
                    jobs.extend((b,f,r,allocations[r.id],required_groups.get(r.id, [])) for r in f.rooms if r.id in allocations)
        if not jobs: break
        b,f,r,targets,groups=min(jobs,key=lambda row:(attempted_functions.get((row[0].id,row[1].level,row[2].function),0),-row[2].bounds.area))
        seen.add(r.id)
        key=(b.id,f.level,r.function)
        attempted_functions[key]=attempted_functions.get(key,0)+1
        record={'room_id':r.id,'building_id':b.id,'level':f.level,'allocated_inventory':targets}
        witness=None
        if registry is not None:
            from cityg.planning.functional_seeds import find_inventory_witness
            witness,evidence=find_inventory_witness(b,f,r,targets,resolver,seed=seed)
            record['capacity_reference']=evidence
        def seating_gate(base_gate):
            def check(candidate):
                from cityg.planning.seating_contract import check_seating
                bb = next(q for q in candidate.iter_buildings() if q.id==b.id)
                ff = next(q for q in bb.floors if q.id==f.id)
                for group in groups:
                    contract = {k:group[k] for k in ('anchor','seat','required','room_function')}
                    if not check_seating(bb,ff,contract)['ok']:
                        raise ValueError('One accessible table with the explicitly requested seating is required')
                return base_gate(candidate)
            return check if groups else base_gate
        agent.max_attempts=2 if witness is not None else 3
        try:
            context,preflight,gate=prepare_preflight(city,r.id,compiler,registry,seed=seed)
            result=agent.propose(city,b,f,r,use_cache=False,compiled_preflight=preflight,inventory_targets=targets,
                visual_feedback={'source':'measured_inventory_shortfall','major_inventory_only':True,
                    'allow_capacity_review':True,'compiled_context':context,
                    'metric_feasible_reference':witness.design.to_dict() if witness is not None else None,
                    'instruction':'Complete this room allocated required_inventory; other same-function rooms cover other bundles. '
                                  'Do not copy the entire floor inventory into this room. Retain all existing functional furniture, '
                                  'support dressing and doors. Do not alter the room or scale furniture.'})
            if on_attempts: on_attempts(result.attempts)
            committed,stats=commit_room_program(city,r.id,result.program,asset_resolver=resolver,
                seed=seed,source='generation',compiled_gate=seating_gate(gate),memory_store=memory_store)
            city=committed.city
            record.update(status='accepted',placement=stats,transaction=committed.report,proposal=result.raw)
        except (ValueError,AgentGenerationError,PatchRejected) as error:
            if on_attempts: on_attempts(getattr(error,'attempts',()))
            record.update(status='rejected_previous_room_preserved',error=str(error),
                          attempts=[asdict(a) for a in getattr(error,'attempts',())])
            if witness is not None:
                # A reference is only a proposal. It must pass the same compiled
                # transaction and non-degradation gate as the model's design.
                try:
                    _,_,fallback_gate=prepare_preflight(city,r.id,compiler,registry,seed=seed)
                    committed,stats=commit_room_program(city,r.id,witness,asset_resolver=resolver,
                        seed=seed,source='generation',compiled_gate=seating_gate(fallback_gate),memory_store=memory_store)
                    city=committed.city
                    record.update(status='accepted',proposal_source='metric_reference_fallback',
                        placement=stats,transaction=committed.report,proposal={'design':witness.design.to_dict()})
                except (ValueError,PatchRejected) as fallback_error:
                    record['reference_rejection']=str(fallback_error)
        attempts.append(record)
    compiled_rooms=completion_certificates(city,attempts)
    return city,{'compiled_rooms':compiled_rooms,'policy':'bounded_inventory_completion_v1','max_rooms':max_rooms,
        'before':before,'attempts':attempts,'after':evaluate_requirements(city,rows),
        'asset_generation_used':False}


def completion_certificates(city, attempts):
    """Carry accepted local compile evidence into the final publication gate."""
    certificates=[]
    for attempt in attempts:
        if attempt['status']!='accepted': continue
        rid=attempt['room_id']
        gate=attempt.get('transaction',{}).get('compiled_gate',{})
        if not gate.get('ok'):
            raise ValueError('Functional completion lacks a successful compiled transaction')
        expected={r['kind']:r['expected'] for r in gate.get('room_checks',[])
                  if r['kind'] in ('room_surface_items','room_decorations')}
        certificates.append({'room_id':rid,'source':'functional_completion',
            'major_count':sum(o.room_id==rid for o in city.iter_objects()),
            'expected_inventory':expected,'compiled_verified':True})
    return certificates
