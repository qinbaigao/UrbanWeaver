"""Simple finite-search baseline sharing production candidates and hard gates.

Semantic variant uses the same model interpreter, but no model layout choice.
Scoring knows only interpreted goals, never evaluator labels or hidden tests.
"""
from cityg.agents.building_floor import BuildingFloorProgram, BuildingFloorAgent
from cityg.agents.requirement import AgentGenerationError
from cityg.planning.floor_brief import geometry_summary, required_functions_by_level, resolve_brief
from cityg.planning.floor_topologies import topology_catalog, expand_topology_brief
from cityg.planning.floor_objectives import interpret_organization, organization_receipt
from cityg.planning.floor_candidates import nominal_brief, feasible_candidates
from cityg.planning.floor_access import forbidden_transit_functions


def simple_plan(agent,building,base,spec,*,interpret=True):
    objective,attempts=(interpret_organization(agent,building) if interpret else
        ({'organization':'unspecified','supporting_goal_ids':[],'reason':'Geometry-only baseline'},()))
    catalog=topology_catalog(geometry_summary(building,base),
        spec.rooms_per_floor if spec.room_count_strategy=='fixed' else None)
    catalog,preflight=feasible_candidates(catalog,building,base,spec)
    required=required_functions_by_level(building,base)
    preference=objective['organization']
    def rank(c):
        matches=(c['children_per_anchor']>0 if preference=='private_groups' else
                 c['children_per_anchor']==0 if preference=='independent' else True)
        return (not matches,c['room_count'],c['max_room_aspect_ratio'],c['id'])
    rejected=[]
    for candidate in sorted(catalog,key=rank):
        try:
            brief=nominal_brief(candidate,building,base,forbidden_transit_functions(objective))
            profile=resolve_brief(expand_topology_brief(brief,catalog),building,base,spec)
            result=BuildingFloorProgram(building.function,profile,'simple_semantic_score_v1',
                organization_receipt(profile,objective,selection_status='finite_search'))
            result.validate(building);BuildingFloorAgent._check_spatial_feasibility(profile,building,spec,
                access_constraints=objective.get('access_constraints',[]))
            return result,attempts,{'candidate_count':len(catalog),'tested':len(rejected)+1,
                                   'rejected':rejected,'preflight':preflight}
        except ValueError as exc:rejected.append({'id':candidate['id'],'error':str(exc)})
    raise AgentGenerationError('Simple finite baseline found no valid profile: '+str(rejected),attempts)
