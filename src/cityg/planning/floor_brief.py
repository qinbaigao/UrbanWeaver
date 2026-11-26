"""Semantic floor briefs resolved against an immutable realized floor plate.

The agent chooses functions, counts, access topology and relative area weights.
The deterministic solver owns metric allocation; explicit area bounds remain hard.
"""
from dataclasses import asdict, replace
import json
import math

from cityg.planning.programs import FloorProfile, VERTICAL_USE_TYPES
from cityg.planning.baseline import ROOM_FUNCTIONS
from cityg.schemas import Bounds2D
from cityg.planning.interior_frame import InteriorFrame, circulation_axis


def interior_capability(building):
    rotated = abs(float(building.metadata.get('orientation_deg', 0))) % 180 > 1e-6
    highrise = bool(building.metadata.get('highrise', {}).get('enabled'))
    regular = building.metadata.get('massing_style', 'bar') == 'bar'
    supported = regular and not rotated and not highrise
    return {'semantic_brief_supported': supported,
            'scope': 'axis_aligned_rectangular_lowrise',
            'reason': 'supported' if supported else 'use_existing_planner_with_explicit_geometry_validation',
            'arbitrary_polygon_interiors_supported': False}


def geometry_summary(building, profile):
    from cityg.planning.programmed import ProgrammedCityPlanner
    if not interior_capability(building)['semantic_brief_supported']:
        raise ValueError('Semantic floor brief requires an axis-aligned rectangular low-rise')
    frame=InteriorFrame(circulation_axis(building))
    plate = frame.bounds(building.footprint)
    corridor_depth = ProgrammedCityPlanner._corridor_depth(plate.depth, profile.corridor_ratio)
    connectors=[replace(c,bounds=frame.bounds(c.bounds)) for c in building.vertical_connectors]
    core = ProgrammedCityPlanner._connector_core_bounds(plate, connectors, corridor_depth)
    low = min(core.center.y-corridor_depth/2, core.min_y)
    high = max(core.center.y+corridor_depth/2, core.max_y)
    corridor = Bounds2D(plate.min_x, low, plate.max_x, high)
    if not plate.contains_bounds(corridor):
        raise ValueError('Existing core/circulation lies outside the realized plate')
    bands = [Bounds2D(plate.min_x, high, plate.max_x, plate.max_y),
             Bounds2D(plate.min_x, plate.min_y, plate.max_x, low)]
    examples=[]
    from cityg.planning.spatial_layout import _place_band, SpatialLayoutInfeasible
    from cityg.planning.spatial_program import SpaceRequirement
    for children, aspect in [(n, a) for a in (2.8, 3.2) for n in range(4)]:
        for anchor_weight in (2,3,4):
            counts=[]
            for count in range(1,17):
                if count*(children+1)*2>32: break
                groups=[[SpaceRequirement(f'g{i}_{j}','living_room',10*anchor_weight if j==0 else 10,
                            min_area_m2=4,max_area_m2=5000)
                         for j in range(children+1)] for i in range(count)]
                try:
                    for band in bands:
                        _place_band(band,groups,True,2.4,aspect,30,0)
                    counts.append(count)
                except SpatialLayoutInfeasible: pass
            if counts:
                examples.append({'children_per_anchor':children,'groups_per_side':counts,
                    'total_rooms_formula':'2 * groups_per_side * (1 + children_per_anchor)',
                    'assumptions':{'min_room_width_m':2.4,'max_room_aspect_ratio':aspect,
                                   'anchor_weight':anchor_weight,'each_child_weight':1,'enclosure':'closed'},
                    'metric_checked':True,'semantic_program_selected':False})
                break
    return {'plate': asdict(building.footprint), 'core': asdict(frame.bounds(core)), 'entrance': asdict(building.entrance),
        'circulation_axis':frame.axis,
        'coordinate_contract':{'plate_core_entrance':'world_xy', 'band_dimensions':'solver_uv',
                               'solver_u':'world_y' if frame.axis=='y' else 'world_x',
                               'solver_v':'world_x' if frame.axis=='y' else 'world_y'},
        'corridor_ratio': profile.corridor_ratio, 'corridor_depth_m': corridor_depth,
        'bands': [{'width_m':b.width, 'depth_m':b.depth, 'area_m2':b.area,
                   'minimum_independent_closed_rooms_at_aspect_2_8':math.ceil(b.width/(b.depth*2.8))}
                  for b in bands],
        'usable_area_m2':sum(b.area for b in bands),
        'feasible_topology_examples':examples,
        'limits': {'minimum_allowed_room_width_m':2.4, 'room_count_max':32,
            'private_group_note':'anchor and children split one band; their minimum depths must both fit',
            'single_spine_only':True},
        'preserve':['plate','entrance','core','corridor_ratio']}


def required_functions_by_level(building, profile):
    """Carry the accepted global semantic program into the local proposal.

    These are planning commitments, not additional user-authored constraints.
    Changing them requires an explicit upstream revision, not a geometry retry.
    """
    requirements = {}
    for floor in building.floors:
        zone = profile.zone_for_level(floor.level)
        archetype = zone.archetype if zone else profile.for_role(
            'ground' if floor.level == 0 else 'typical')
        cycle = archetype.room_function_cycle if archetype else profile.room_function_cycle
        from cityg.interior_requirements import requirements_for
        explicit = [fn for row in requirements_for(building,floor.level) for fn in row['required_functions']]
        requirements[str(floor.level)] = list(dict.fromkeys(explicit or cycle))
    return requirements


def resolve_brief(data, building, base_profile, spec, *, _geometry=None):
    """Compile relative semantic choices; do not repair contradictory bounds."""
    if not isinstance(data, dict) or set(data) != {'zones'}:
        raise ValueError('Floor brief requires exactly zones')
    zones = data['zones']
    if not isinstance(zones, list) or not 1 <= len(zones) <= 8:
        raise ValueError('zones must contain 1..8 contiguous vertical bands')
    # Private per-call memo from the same immutable planning context, never
    # geometry supplied by the model. Candidate scans need not rebuild it.
    geometry = _geometry if _geometry is not None else geometry_summary(building, base_profile)
    area = geometry['usable_area_m2']
    allowed = set(ROOM_FUNCTIONS[building.function])
    required_functions = required_functions_by_level(building, base_profile)
    resolved = []
    for row in zones:
        required = {'zone_id','start_level','end_level','role','use_type','family','spaces',
                    'min_room_width_m','max_room_depth_m','max_room_aspect_ratio'}
        if not isinstance(row, dict) or set(row) != required:
            raise ValueError(f'Each zone requires exactly {sorted(required)}')
        if type(row['start_level']) is not int or type(row['end_level']) is not int:
            raise ValueError('Zone levels must be integers')
        if row['use_type'] not in VERTICAL_USE_TYPES:
            raise ValueError('Unsupported use_type')
        for field, lower, upper in [('min_room_width_m',2.4,12),('max_room_depth_m',4,30),
                                    ('max_room_aspect_ratio',1.4,8)]:
            value = row[field]
            if type(value) not in (int,float) or not math.isfinite(value) or not lower <= value <= upper:
                raise ValueError(f'{field} must be finite within [{lower}, {upper}]')
        spaces = row['spaces']
        if not isinstance(spaces, list) or not 2 <= len(spaces) <= 32:
            raise ValueError('Enumerate 2..32 actual spaces, not implicit repeated categories')
        if spec.room_count_strategy == 'fixed' and len(spaces) != spec.rooms_per_floor:
            raise ValueError('Brief space count must preserve explicit rooms_per_floor')
        for item in spaces:
            if not isinstance(item, dict) or not {'key','function','weight'} <= set(item):
                raise ValueError('Each space requires key, function and weight')
            if set(item)-{'key','function','weight','access_via','group','enclosure','daylight',
                         'near_entrance','min_area_m2','max_area_m2','adjacent_to','separate_from'}:
                raise ValueError('Unsupported space field; do not provide coordinates or target areas')
            if item['function'] not in allowed:
                raise ValueError(f'Unsupported function {item["function"]}')
            weight = item['weight']
            if type(weight) not in (int,float) or not math.isfinite(weight) or not 0 < weight <= 100:
                raise ValueError('Space weight must be finite in (0,100]')
        total = sum(s['weight'] for s in spaces)
        requirements = []
        for item in spaces:
            requirement = {k:v for k,v in item.items() if k != 'weight'}
            requirement.update(target_area_m2=area*item['weight']/total,
                min_area_m2=item.get('min_area_m2',4.0), max_area_m2=item.get('max_area_m2',5000.0))
            requirements.append(requirement)
        cycle = list(dict.fromkeys(s['function'] for s in spaces))
        for level in range(row['start_level'], row['end_level'] + 1):
            missing = set(required_functions.get(str(level), ())) - set(cycle)
            if missing:
                raise ValueError(f'Level {level} omits accepted global functions: {sorted(missing)}. '
                                 'Preserve these functions while revising counts/groups/weights.')
        count = len(spaces)
        resolved.append({k:v for k,v in row.items() if k not in {'family','spaces'}} | {
            'preferred_room_count':count, 'min_room_count':count, 'max_room_count':count,
            'target_room_area_m2':area/count, 'room_function_cycle':cycle,
            'unit_group_size':1, 'layout_template':'auto',
            'spatial_program':{'family':row['family'], 'spaces':requirements}})
    ground = next((z for z in resolved if z['role']=='ground'), None)
    typical = next((z for z in resolved if z['role']=='typical'), resolved[-1])
    if ground is None:
        raise ValueError('Provide a ground zone')
    def archetype(zone, role):
        return {k:v for k,v in zone.items() if k not in {'zone_id','start_level','end_level','use_type'}} | {'role':role}
    return FloorProfile.from_dict({'function':building.function, 'layout':base_profile.layout,
        'corridor_ratio':base_profile.corridor_ratio,
        'room_function_cycle':list(dict.fromkeys(s['function'] for z in zones for s in z['spaces'])),
        'space_archetypes':[archetype(ground,'ground'),archetype(typical,'typical')],
        'vertical_zones':resolved})


def plan_semantic_brief(agent, building, base_profile, spec, prototype_context=None):
    from cityg.agents.context import ProgressiveContext
    from cityg.agents.building_floor import BuildingFloorProgram
    from cityg.planning.floor_topologies import (topology_catalog, expand_topology_brief,
                                               topology_schema, reference_choices_by_level)
    from cityg.interior_requirements import requirements_for
    bound_requirements=requirements_for(building)
    if bound_requirements:
        prototype_context={**(prototype_context or {}),
            'minimum_compatible_rooms_per_detailed_floor':0,
            'reference_policy':'User area/functions override reference coverage. Unmatched rooms require bounded Room Agent furnishing; do not expand the floor to fit a reference.'}
    geometry = geometry_summary(building, base_profile)
    catalog = topology_catalog(geometry, spec.rooms_per_floor if spec.room_count_strategy=='fixed' else None,
        references=(prototype_context or {}).get('room_dimensions',()),
        allowed_functions=ROOM_FUNCTIONS[building.function], height=min(f.height_m for f in building.floors),
        retain_unmatched=bool(bound_requirements),
        enumerate_all_counts=bool((prototype_context or {}).get('local_only')))
    from cityg.planning.floor_candidates import feasible_candidates
    catalog,preflight=feasible_candidates(catalog,building,base_profile,spec,_geometry=geometry)
    capacity_resolver=getattr(agent,'inventory_asset_resolver',None) if bound_requirements else None
    if capacity_resolver is not None or (bound_requirements and (prototype_context or {}).get('local_only')):
        catalog=[{**c,'weight_min':.5,'weight_max':2.0} for c in catalog]
    from cityg.agents.requirement import AgentGenerationError
    if not catalog:
        raise AgentGenerationError('No fully feasible nominal floor candidate: '+json.dumps(preflight),())
    from cityg.design_goals import goal_context
    from cityg.planning.floor_objectives import interpret_organization, preferred_topologies, organization_receipt
    original_catalog=catalog
    objective={'organization':'unspecified','supporting_goal_ids':[],'reason':'No interpreted organization preference'}
    intent_attempts=()
    selection_status='no_organization_objective'
    enabled=getattr(agent,'semantic_objective_policy','verified')=='verified'
    if enabled and catalog and goal_context(getattr(agent,'design_goals',[]),'floor') and agent.max_calls>=2:
        try:
            objective,intent_attempts=interpret_organization(agent,building)
            preferred=preferred_topologies(catalog,objective,required_functions_by_level(building,base_profile))
            if objective['organization']!='unspecified':
                selection_status='preferred_candidate_subset' if preferred else 'no_preferred_topology_in_catalog'
                if preferred:catalog=preferred
        except AgentGenerationError as exc:
            intent_attempts=exc.attempts
            selection_status='interpretation_unavailable'
    elif not enabled:selection_status='legacy_unmeasured_preference'
    elif goal_context(getattr(agent,'design_goals',[]),'floor'):
        selection_status='interpretation_skipped_budget_or_capability'
    context = ProgressiveContext(summary={
        'interior_requirements':building.metadata.get('interior_layout_contract',{}).get('requirements',[]),
        'building_id':building.id, 'function':building.function,
        'floor_count':len(building.floors), 'geometry_contract':geometry,
        'room_functions':list(ROOM_FUNCTIONS[building.function]),
        'use_types':sorted(VERTICAL_USE_TYPES),
        'fixed_room_count':spec.rooms_per_floor if spec.room_count_strategy=='fixed' else None,
        'required_functions_by_level':required_functions_by_level(building, base_profile),
        'prototype_priors':prototype_context or {},
        'organization_objective':objective,
        'candidate_preflight':preflight,
        'access_postconditions':objective.get('access_constraints',[]),
        'schema':{'zones':[{'zone_id':'ground','start_level':0,'end_level':0,'role':'ground',
            'use_type':'entrance','family':'double_loaded','min_room_width_m':2.4,
            'max_room_depth_m':12,'max_room_aspect_ratio':2.8,
            'spaces':[{'key':'example','function':'FROM_ROOM_FUNCTIONS','weight':1,
                       'access_via':'circulation'}]}]},
    }, sections=())
    prompt = ('You are the Building-specific Floor Agent. Return a JSON brief with exactly zones, '
        'following the response schema. Stage 1: choose functional spaces, counts, access '
        'groups and relative area weights. EVERY level must contain ALL of its '
        'required_functions_by_level from the accepted global program. Never omit kitchens, '
        'bathrooms or other required functions to obtain a geometric fit. Stage 2: '
        'the deterministic solver allocates actual '
        'area and validates geometry, returning conflicts for bounded correction. Do not output '
        'coordinates or target_area_m2. All listed spaces are actual rooms; enumerate repeats '
        'with unique keys. Cover every level exactly once in ordered zones; level 0 must be '
        'ground and the last zone of a multi-floor building must be top. Other bands may be typical. '
        'The schema is an illustration, not a one-room layout. Provide at least two circulation '
        'roots, distributed across both bands. family is double_loaded for independent rooms, '
        'residential_clusters for private groups, or open_office for an open anchor with support rooms. '
        'Private children use their living/entry anchor key as access_via and share its group; '
        'double_loaded REQUIRES every access_via to equal circulation; private groups require '
        'residential_clusters or open_office, not double_loaded. '
        'only one access hierarchy level is supported. NEVER put a corridor into spaces. '
        'Read band depths: a grouped anchor and rear children must BOTH satisfy min_room_width_m. '
        'If a band is too shallow for a private group, choose an appropriate independent-space '
        'organization or report infeasibility; never fabricate a fit. Geometry bounds apply to '
        'every room. Keep enough roots to avoid long thin rooms. Weights determine preferred '
        'area fractions of the whole usable plate; optional min_area_m2/max_area_m2 are HARD '
        'bounds and cannot contradict those targets. Do not invent narrow hard ranges. '
        'Use prototype_priors to favor realistic same-function dimensions on detailed floors. '
        'Inspect feasible_topology_examples BEFORE choosing counts. Each example was checked '
        'at its explicitly listed geometry bounds; do not mix a count from one with tighter '
        'bounds from another. If choosing three children per anchor, check the total count '
        'and aspect bounds of a feasible example. Model-selected aspect limits may differ '
        'between zones; user hard requirements and protected geometry may never be relaxed. '
        'Preserve plate, entrance, core and corridor. Vary functions when appropriate, not '
        'by random geometry. No fallback or base-profile copying counts as successful planning.')
    if catalog:
        context.summary.pop('schema')
        context.summary['topology_candidates'] = catalog
        context.summary['reference_choices_by_level'] = reference_choices_by_level(
            catalog, required_functions_by_level(building,base_profile))
        prompt = (
            'You are the Building-specific Floor Agent. Select the functional organization of each '
            'level using topology_candidates, checked against the ACTUAL immutable plate, entrance '
            'and core. Return exactly the response schema (zones). Choose a topology_id for each '
            'vertical band, then assign exactly its room_count functions in slot_order. These are '
            'For small buildings the schema separates mandatory assignments: '
            'required_function_slots maps EVERY required function to a distinct zero-based room '
            'slot index; remaining_functions fills the unassigned slots in ascending order. '
            'For example 6 rooms and 3 required functions need 3 remaining_functions, not 6. '
            'For larger buildings use the complete functions array instead. These are '
            'ACTUAL rooms, not category labels: repeat a function where multiple rooms need it. '
            'Required functions on EVERY level are in required_functions_by_level and must all '
            'occur. For detailed levels, use nominal_reference_slots to assign enough functions '
            'that dimensionally match a reference, as required by prototype_priors. A topology '
            'fitting ground-floor reception does not necessarily fit upper-floor living rooms. '
            'Consult reference_choices_by_level for explicit topology IDs and slot indices '
            'matching THIS level\'s required functions. Prefer these compatible choices at unit '
            'weights, reserving/repeating enough compatible functions to meet the detail quota. This does not '
            'prove furniture placement: a later compiled transaction still validates it. '
            'occur. All levels must be covered exactly once; ground is level 0, top is the last '
            'zone of a multi-floor building. Select appropriate use_type. Private residential '
            'groups should use living_room or reception as anchor, with bedroom/kitchen/bathroom '
            'children; independent topology is appropriate for shared facilities and commercial '
            'rooms. Never treat a corridor as a listed function. Smaller room counts favor larger '
            'rooms, but do not discard functional requirements. Read prototype_priors for the '
            'desired room scale. Assign exactly room_count weight_adjustments: start with 1.0 '
            '(the checked dimensions), optionally vary within [0.8,1.2] for semantic needs. '
            'Adjusted geometry is revalidated, never assumed feasible. The same count alone does '
            'not determine a room layout: functions, access groups and weights matter. No raw '
            'coordinates, no fabricated topology IDs, no changing the protected plate/core/entry. '
            'This path currently supports symmetric, closed-room single-spine organizations only; '
            'it does not claim arbitrary floor topology support. '
            'Obey uniform access_postconditions: a not_through_room function must not occupy '
            'an anchor with child rooms. Choose a leaf slot or independent topology. Qualified '
            'constraints remain deferred; do not extend them to the whole building. Nominal '
            'candidate certificates are not proof of arbitrary weights or function assignments.')
    if bound_requirements and spec.room_count_strategy!='fixed':
        context.summary['count_priority']='explicit functional capacity before prototype count'
        context.summary['smallest_function_covering_topologies']={
            str(level):[c['id'] for c in catalog if c['room_count']==min(
                (x['room_count'] for x in catalog if x['room_count']>=len(required)),default=0)]
            for level,required in required_functions_by_level(building,base_profile).items()}
        prompt += (
            ' This building has an explicit area AND functional inventory contract. Prioritize usable furniture '
            'capacity over the number of prototype matches. Begin with the smallest topology covering required '
            'functions; repeat a function only for an explicit multi-unit/capacity need, not to fill a detail quota. '
            'A compact home normally needs one living/dining area, one kitchen and one bedroom rather than two '
            'undersized copies of each. A compact office needs a meeting room large enough for the requested '
            'table, all seats, pull-back space and entry clearance; give it more area than storage. '
            'Reference matching is advisory here. Do not multiply small rooms just because they match references; '
            'unused detail quota is preferable to rooms unable to hold their required functional groups.')
    if capacity_resolver is not None:
        from cityg.planning.functional_configuration import PROFILES, RECIPES
        context.summary['functional_configuration_priors'] = {
            'recipes_by_function': PROFILES, 'recipes': RECIPES,
            'authority': 'Soft service-capacity references, not added user inventory',
            'policy': 'Allocate room areas for plausible complete activity groups plus support and circulation. '
                      'Presence of one desk/chair is a user lower bound, not ideal capacity for an open office. '
                      'Coordinate shared support across neighboring rooms; retain intentional open space. '
                      'Room Agent later proposes capacity ranges and verifies complete groups at actual dimensions.'}
        context.summary['previous_functional_configuration_feedback'] = [
            item for floor in building.floors
            for item in floor.metadata.get('functional_configuration_feedback', [])]
        from cityg.planning.floor_inventory_capacity import inventory_asset_context
        context.summary['actual_inventory_asset_dimensions']=inventory_asset_context(building,capacity_resolver)
        prompt += (' Furniture capacity is checked by metric reference placement, including chair pull-back and doors. '
            'On a failed reference, revise function slots or split living/dining into two living_room slots, '
            'without dropping any requirements. For these contracted floors weight adjustments may range [0.5,2.0] '
            'to allocate more area to occupied spaces than storage. Geometry is revalidated after every change.')
    def parse(data):
        resolved = expand_topology_brief(data, catalog) if catalog else data
        profile = resolve_brief(resolved, building, base_profile, spec,_geometry=geometry)
        result = BuildingFloorProgram(building.function, profile,
            'semantic_topology_choice_metric_solver_v2' if catalog else 'semantic_brief_metric_solver_v1')
        result.validate(building)
        errors=[]
        frontage=max(b['width_m'] for b in geometry['bands'])
        for zone in profile.vertical_zones:
            spaces=zone.spatial_program.spaces
            roots=[s for s in spaces if s.access_via=='circulation']
            total_capacity=0
            capacities=[]
            for root in roots:
                children=[s for s in spaces if s.access_via==root.key]
                depth=max(b['depth_m'] for b in geometry['bands'])
                if children: depth=min(depth*.70,depth-zone.min_room_width_m)
                capacity = (depth*zone.max_room_aspect_ratio if root.enclosure=='closed'
                            else frontage)
                total_capacity += capacity
                capacities.append(capacity)
            needed=2*frontage
            # A root cannot span both sides of the corridor. Total frontage
            # alone can falsely admit an odd count (e.g. 5 roots requiring
            # at least 3 per band). This is only a necessary capacity bound;
            # the actual solver still checks every proposed assignment.
            minimum_roots = 2*math.ceil((frontage-1e-6)/max(capacities, default=1e-6))
            if total_capacity<needed-1e-6 or len(roots)<minimum_roots:
                errors.append(f'zone {zone.zone_id}: {len(roots)} roots provide AT MOST '
                    f'{total_capacity:.1f}m total frontage but BOTH bands require {needed:.1f}m. '
                    f'At these bounds at least {minimum_roots} circulation roots are necessary '
                    f'({minimum_roots//2} per band); a root cannot straddle the corridor. '
                    'Increase the number of actual rooms/groups, not just their weights. '
                    'Use feasible_topology_examples in the initial context, including their exact bounds/weights.')
        if errors: raise ValueError('Insufficient semantic capacity. '+'; '.join(errors))
        agent._check_spatial_feasibility(profile, building, spec,
            access_constraints=objective.get('access_constraints',[]),_geometry=geometry)
        if capacity_resolver is not None:
            from cityg.planning.floor_inventory_capacity import check_inventory_capacity
            capacity=check_inventory_capacity(profile,building,geometry,capacity_resolver,seed=spec.seed)
            result=replace(result,decision_receipt={'inventory_capacity':capacity})
        from cityg.planning.floor_reference_fit import check_floor_reference_fit
        try:
            check_floor_reference_fit(profile, building, geometry, prototype_context or {})
        except ValueError as error:
            hints=reference_choices_by_level(catalog,required_functions_by_level(building,base_profile))
            raise ValueError(str(error)+' Level-specific compatible alternatives at unit weights: '+
                             json.dumps(hints,separators=(',',':'))) from error
        return result
    # Constrain the actual brief, rather than just the legacy JSON-in-a-string
    # envelope. Reuse bounded retry/trace accounting; retain the exact response
    # text as program_json in the trace, including metadata and token usage.
    from cityg.agents.hierarchy import _ProgressiveProgramAgent
    from cityg.services.openai_compatible import ModelCompletion
    class BriefService:
        def complete_with_metadata(self, messages, response_schema=None):
            direct = []
            for message in messages:
                if message.role == 'assistant':
                    try: message = replace(message, content=json.loads(message.content)['program_json'])
                    except (KeyError, ValueError): pass
                direct.append(message)
            schema = (topology_schema(ROOM_FUNCTIONS[building.function], sorted(VERTICAL_USE_TYPES), catalog,
                        len(building.floors), required_functions_by_level(building,base_profile))
                      if catalog else brief_schema(building.function,len(building.floors)))
            method = getattr(agent.service, 'complete_with_metadata', None)
            response = (method(direct, schema) if callable(method) else
                        ModelCompletion(agent.service.complete(direct, schema), None, {}))
            return replace(response, content=json.dumps({'action':'final','detail_keys':[],
                                                        'program_json':response.content}))
    remaining=agent.max_calls-len(intent_attempts)
    restricted=catalog!=original_catalog
    # Reserve one attempt for a hard-valid fallback. Failure to realize a soft
    # preference is reported, never grounds for dropping mandatory functions.
    runner = _ProgressiveProgramAgent(BriefService(), model_id=agent.model_id,
        max_calls=max(1,remaining-1) if restricted else remaining)
    runner.name = agent.name
    runner.design_goals = getattr(agent,'design_goals',[])
    earlier=list(intent_attempts)
    try:
        result=runner._run(context,prompt,parse)
    except AgentGenerationError as exc:
        earlier.extend(exc.attempts)
        left=agent.max_calls-len(earlier)
        if not restricted or left<=0:
            raise AgentGenerationError(str(exc),tuple(replace(a,index=i+1) for i,a in enumerate(earlier))) from exc
        catalog=original_catalog
        context.summary['topology_candidates']=catalog
        context.summary['reference_choices_by_level']=reference_choices_by_level(
            catalog,required_functions_by_level(building,base_profile))
        context.summary['preference_tradeoff']='Preferred subset failed bounded realization; retain hard constraints, report actual outcome.'
        runner.max_calls=left
        selection_status='preferred_realization_failed_fallback'
        try:result=runner._run(context,prompt,parse)
        except AgentGenerationError as final:
            earlier.extend(final.attempts)
            raise AgentGenerationError(str(final),tuple(replace(a,index=i+1) for i,a in enumerate(earlier))) from final
    attempts=tuple(replace(a,index=i+1) for i,a in enumerate([*earlier,*result.attempts]))
    receipt=organization_receipt(result.program.profile,objective,selection_status=selection_status)
    if result.program.decision_receipt.get('inventory_capacity'):
        receipt['inventory_capacity']=result.program.decision_receipt['inventory_capacity']
    receipt['candidate_preflight']=preflight
    receipt['reference_policy']='advisory_under_explicit_user_contract' if bound_requirements else 'required_reference_capacity'
    receipt['access_postconditions']={'status':'checked_on_realized_solver_graph',
        'active':[r for r in objective.get('access_constraints',[]) if r['applicability']=='uniform'],
        'deferred':[r for r in objective.get('access_constraints',[]) if r['applicability']!='uniform'],
        'compiled_geometry_verified':False}
    return replace(result,attempts=attempts,program=replace(result.program,decision_receipt=receipt))


def brief_schema(function, floor_count=None):
    """Strict nested output keeps scarce retries for semantic/metric issues."""
    def obj(properties, required=None):
        return {'type':'object','additionalProperties':False,'properties':properties,
                'required':list(properties) if required is None else required}
    def enum(values): return {'type':'string','enum':list(values)}
    space = obj({'key':{'type':'string'},'function':enum(ROOM_FUNCTIONS[function]),
        'weight':{'type':'number','exclusiveMinimum':0,'maximum':100},
        'access_via':{'type':'string'},'group':{'type':'string'},
        'enclosure':enum(['open','closed'])})
    zone = obj({'zone_id':{'type':'string'},'start_level':{'type':'integer','minimum':0},
        'end_level':{'type':'integer','minimum':0},'role':enum(['ground','typical','top']),
        'use_type':enum(sorted(VERTICAL_USE_TYPES)),
        'family':enum(['double_loaded','residential_clusters','open_office']),
        'min_room_width_m':{'type':'number','minimum':2.4,'maximum':12},
        'max_room_depth_m':{'type':'number','minimum':4,'maximum':30},
        'max_room_aspect_ratio':{'type':'number','minimum':1.4,'maximum':8},
        'spaces':{'type':'array','minItems':2,'maxItems':32,'items':space}})
    if floor_count is not None and 1<=floor_count<=4:
        # Small buildings have only a few levels: bind compiler-owned indices
        # and roles in the schema, leaving every function/group/weight to LLM.
        import copy
        levels=[]
        for level in range(floor_count):
            item=copy.deepcopy(zone)
            item['properties']['start_level']={'type':'integer','const':level}
            item['properties']['end_level']={'type':'integer','const':level}
            item['properties']['role']={'type':'string','const':
                'ground' if level==0 else 'top' if level==floor_count-1 else 'typical'}
            levels.append(item)
        return obj({'zones':{'type':'array','minItems':floor_count,'maxItems':floor_count,
                             'prefixItems':levels}})
    return obj({'zones':{'type':'array','minItems':1,'maxItems':8,'items':zone}})
