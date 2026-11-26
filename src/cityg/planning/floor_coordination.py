"""Authorized, unfurnished, adjacent-room capacity negotiation.

Boundaries move only within explicit budgets. Existing doors, shell and core
stay fixed. The Agent chooses among dimensionally useful candidates; semantic
and compiled checks decide acceptance. Never enabled for furnished repair.
"""
from copy import deepcopy
from dataclasses import asdict, replace
from itertools import combinations

from cityg.planning.prototype_adaptation import room_candidates, door_side
from cityg.planning.room_envelope import metric_envelope
from cityg.planning.negotiation import negotiate
from cityg.planning.scope_requirements import ScopeRequirements
from cityg.transactions import fingerprint, refresh_local_overlay


def options(value=None):
    result={'enabled':False,'max_proposals':2,'max_boundary_shift_m':1.0,**(value or {})}
    if (set(result)!={'enabled','max_proposals','max_boundary_shift_m'} or type(result['enabled']) is not bool
            or type(result['max_proposals']) is not int or not 1<=result['max_proposals']<=3
            or type(result['max_boundary_shift_m']) not in (int,float)
            or not 0<result['max_boundary_shift_m']<=2):
        raise ValueError('Invalid floor coordination budget')
    return result


def _eligible(building,floor,room):
    if room.function=='corridor' or room.object_ids or any(o.room_id==room.id for o in floor.objects): return False
    if abs(building.metadata.get('orientation_deg',0))>1e-6: return False
    if any(room.metadata.get(k) for k in ('unit_id','room_design','functional_zones','room_decorations',
                                         'room_finishes','locked','protected','layout_prototype_id')): return False
    env=metric_envelope(building,floor,room)
    return env['status']=='supported' and all(abs(getattr(env['bounds'],k)-getattr(room.bounds,k))<1e-5
        for k in ('min_x','min_y','max_x','max_y'))


def _fit(library,b,f,r):
    try: return bool(room_candidates(library,b,f,r))
    except ValueError: return False


def proposals(city,library,target_levels,config):
    result=[]; config=options(config)
    if not config['enabled']: return result
    for b in city.iter_buildings():
        for f in b.floors:
            if f.level not in target_levels.get(b.id,[]): continue
            rooms=[r for r in f.rooms if _eligible(b,f,r)]
            for a,c in combinations(rooms,2):
                if any({d.room_a_id,d.room_b_id}=={a.id,c.id} for d in f.doors): continue
                before=int(_fit(library,b,f,a))+int(_fit(library,b,f,c))
                if before==2: continue
                for axis,lo,hi,other_lo,other_hi in [('x','min_x','max_x','min_y','max_y'),
                                                   ('y','min_y','max_y','min_x','max_x')]:
                    left,right=sorted((a,c),key=lambda r:getattr(r.bounds,lo))
                    if (abs(getattr(left.bounds,hi)-getattr(right.bounds,lo))>1e-6 or
                        any(abs(getattr(left.bounds,k)-getattr(right.bounds,k))>1e-6 for k in (other_lo,other_hi))): continue
                    edge=getattr(left.bounds,hi)
                    limit=min(config['max_boundary_shift_m'],.2*(getattr(left.bounds,hi)-getattr(left.bounds,lo)),
                              .2*(getattr(right.bounds,hi)-getattr(right.bounds,lo)))
                    # Include reference dimensions, rather than only arbitrary grid offsets.
                    offsets={-limit,limit,-limit/2,limit/2}
                    for record in library.rooms.values():
                        for size in (record['reference']['width_m'],record['reference']['depth_m']):
                            offsets.add(getattr(left.bounds,lo)+size-edge)
                            offsets.add(getattr(right.bounds,hi)-size-edge)
                    for shift in sorted(offsets):
                        if abs(shift)<1e-5 or abs(shift)>limit+1e-6: continue
                        pair=[replace(left,bounds=replace(left.bounds,**{hi:edge+shift})),
                              replace(right,bounds=replace(right.bounds,**{lo:edge+shift}))]
                        valid=True
                        for r in pair:
                            req=r.metadata.get('spatial_requirement',{})
                            valid &= (r.bounds.width>=2 and r.bounds.depth>=2 and
                                      req.get('min_area_m2',0)<=r.bounds.area<=req.get('max_area_m2',float('inf')))
                            try:
                                for d in f.doors:
                                    if r.id in (d.room_a_id,d.room_b_id): door_side(r,d)
                            except ValueError: valid=False
                        after=sum(int(_fit(library,b,f,r)) for r in pair)
                        if valid and after>before:
                            result.append({'id':f'capacity_{len(result)}','floor_id':f.id,'building_id':b.id,
                                'target_room_id':next(r.id for r in (left,right) if not _fit(library,b,f,r)),
                                'axis':axis,'shift_m':shift,'compatible_before':before,
                                'compatible_after':after,'room_bounds':{r.id:asdict(r.bounds) for r in pair},
                                'rooms':[{'room_id':old.id,'function':old.function,
                                    'unfurnished':True,'major_object_count':0,
                                    'current_bounds':asdict(old.bounds),'proposed_bounds':asdict(new.bounds),
                                    'compatible_references_before':room_candidates(library,b,f,old),
                                    'compatible_references_after':room_candidates(library,b,f,new)}
                                    for old,new in zip((left,right),pair)]})
                        if len(result)>=32: return result
    return result


def apply_proposal(city,proposal,library,compiler,*,authorized_levels,config,memory_store=None):
    from cityg.planning.floor_repartition import _compiled_locks,_check_compiled_access
    from cityg.validation import CityValidator
    from cityg.schemas import Bounds2D
    offered=proposals(city,library,authorized_levels,config)
    if proposal not in offered: raise ValueError('Stale, unauthorized or infeasible floor proposal')
    before=fingerprint(city)
    conflict={'conflict_id':'floor_capacity_'+before[:16],'entity_id':proposal['target_room_id'],
              'base_fingerprint':before,'code':'room_reference_capacity'}
    building=next(b for b in city.iter_buildings() if b.id==proposal['building_id'])
    original=next(f for f in building.floors if f.id==proposal['floor_id'])
    baseline=compiler.compile(city,building_ids={building.id})
    locks=_compiled_locks(baseline,building,original)
    def floor_strategy(draft,scope,feedback):
        floor=next(f for f in draft.iter_floors() if f.id==scope)
        for room in floor.rooms:
            if room.id in proposal['room_bounds']:
                room.bounds=Bounds2D(**proposal['room_bounds'][room.id])
                room.metadata['realized_area_m2']=room.bounds.area
                room.metadata.pop('joint_room_plan',None)
        refresh_local_overlay(city,draft,[scope])
        return draft
    def room_strategy(*args): raise ValueError('Room-local assets cannot increase usable partition dimensions')
    def compile_gate(candidate):
        semantic=CityValidator().validate(candidate)
        if not semantic.ok: raise ValueError('Coordinated floor failed semantic validation')
        scene=compiler.compile(candidate,building_ids={proposal['building_id']})
        b=next(b for b in candidate.iter_buildings() if b.id==building.id)
        f=next(f for f in b.floors if f.id==original.id)
        if _compiled_locks(scene,b,f)!=locks: raise ValueError('Compiled door/core geometry changed')
        _check_compiled_access(scene,b,original,f)
        if any(a.bounds.overlaps_area(c.bounds) for a,c in combinations(f.rooms,2)):
            raise ValueError('Coordinated rooms overlap')
        if not any(p.semantic_class=='interior_wall' and p.layer_id=='floor:'+f.id for p in scene.primitives):
            raise ValueError('Coordinated partitions were not compiled')
        return {'ok':True,'source':'floor_coordination_compile','door_core_locks':True,'outdoor_access':True}
    def resolved(candidate,_):
        b=next(b for b in candidate.iter_buildings() if b.id==proposal['building_id'])
        f=next(f for f in b.floors if f.id==proposal['floor_id'])
        return sum(int(_fit(library,b,f,r)) for r in f.rooms if r.id in proposal['room_bounds'])>proposal['compatible_before']
    return negotiate(city,conflict,authorized_roots=[proposal['floor_id']],
        strategies={'room':room_strategy,'floor':floor_strategy},compiled_gate=compile_gate,
        resolution_gate=resolved,max_attempts=2,source='generation',memory_store=memory_store,
        scope_requirements=ScopeRequirements(tuple(proposal['room_bounds']),('floor','building')))


def choose_proposal(service,city,offered):
    """Solve metric-only choices directly; ask a model only about soft goals.

    Offers come from the trusted bounded candidate generator. Selecting one
    never bypasses apply_proposal's fresh feasibility, permissions or compile.
    """
    from cityg.design_goals import goal_context
    goals=goal_context(city.metadata.get('design_goals',[]),'floor')
    if not offered:return {'proposal_id':'none','reason':'No feasible offered adjustment',
                          'decision_owner':'deterministic'},()
    if not goals:
        chosen=min(offered,key=lambda p:(-(p['compatible_after']-p['compatible_before']),
                                        abs(p['shift_m']),p['id']))
        return {'proposal_id':chosen['id'],'reason':'Maximize compatible rooms, then minimize boundary displacement',
                'decision_owner':'deterministic','model_calls_avoided':1,
                'candidate_count':len(offered),'requires_compiled_acceptance':True},()
    if service is None:
        return {'proposal_id':'none','reason':'Soft goal choice requires an available model',
                'decision_owner':'unavailable'},()
    from cityg.agents.hierarchy import _ProgressiveProgramAgent
    from cityg.agents.context import ProgressiveContext
    runner=_ProgressiveProgramAgent(service,max_calls=2)
    runner.name='floor'; runner.design_goals=city.metadata.get('design_goals',[])
    def parse(value):
        if (not isinstance(value,dict) or set(value)!={'proposal_id','reason'} or
            value['proposal_id'] not in {'none',*[r['id'] for r in offered]} or
            not isinstance(value['reason'],str) or not value['reason'].strip()):
            raise ValueError('Choose one offered proposal_id or none, with a reason')
        return value
    result=runner._run(ProgressiveContext(summary={'candidates':offered},sections=[]),
        'You are the Floor Coordination Agent. A room lacks a compatible furniture reference or an actual '
        'floor lacks capacity for its complete required furniture bundles. Choose at most one offered '
        'proposal if appropriate to the shared goals. kind=whole_floor_inventory_capacity offers a '
        'new EMPTY fallback floor topology whose furniture bundles were placed at real asset dimensions; '
        'it may replan internal partitions/doors, but preserves the shell, exterior entry, cores and functions. '
        'Other proposals are adjacent-room boundary adjustments with every existing door preserved. '
        'Each candidate includes observed unfurnished state and actual reference/dimension checks for both rooms. '
        'All offered rooms have zero furniture; do not assume that an existing partition implies furnishing. '
        'A zero-to-nonzero compatible reference list is the explicit capacity conflict and improvement. '
        'Respect the scope and constraints on each candidate; all still need compilation. '
        'No existing furnished room may change. Do not invent dimensions or IDs. none is valid. '
        'All necessary candidate details are already provided; there are no detail sections to request. '
        'Return action=final, detail_keys=[] (always empty), with program_json encoding {proposal_id,reason}.',parse)
    return result.program,result.attempts
