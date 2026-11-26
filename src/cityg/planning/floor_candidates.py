"""Nominal full-profile feasibility certificates for floor topology offers.

A certificate proves one assignment at unit weights, not arbitrary model
adjustments, reference furnishing fits, or compiled geometry.
"""
from cityg.planning.floor_brief import required_functions_by_level, resolve_brief
from cityg.planning.floor_topologies import expand_topology_brief


def nominal_brief(candidate,building,base,forbidden_transit=()):
    required=required_functions_by_level(building,base);zones=[]
    count=candidate['room_count'];children=candidate['children_per_anchor'];stride=children+1
    for floor in building.floors:
        functions=required[str(floor.level)]
        if count<len(functions):raise ValueError('Candidate cannot retain all required functions')
        anchors=[fn for fn in functions if fn not in forbidden_transit or not children]
        if not anchors:raise ValueError('No allowed anchor for private children')
        anchor=next((fn for fn in ('living_room','reception','open_office','office') if fn in anchors),anchors[0])
        slots=[anchor]*count
        order=([i for i in range(count) if i%stride] if children else [])
        order += [i for i in range(count) if i not in order]
        for fn,index in zip([fn for fn in functions if fn!=anchor],order):slots[index]=fn
        if children and any(fn in forbidden_transit and i%stride==0 for i,fn in enumerate(slots)):
            raise ValueError('Not enough leaf slots for forbidden transit functions')
        zone={'zone_id':f'level_{floor.level}','start_level':floor.level,'end_level':floor.level,
            'role':'ground' if floor.level==0 else 'top' if floor.level==len(building.floors)-1 else 'typical',
            'use_type':{'residential':'residential','commercial':'office','public_service':'public_service',
                        'industrial':'industrial'}.get(building.function,'mixed'),
            'topology_id':candidate['id'],'functions':slots,'weight_adjustments':[1.0]*count}
        # Preserve distinct vertical programs but compress equal typical bands.
        if (zones and zone['role']=='typical' and zones[-1]['role']=='typical'
                and zones[-1]['functions']==slots):zones[-1]['end_level']=floor.level
        else:zones.append(zone)
    return {'zones':zones}


def feasible_candidates(catalog,building,base,spec,*,_geometry=None):
    from cityg.agents.building_floor import BuildingFloorProgram, BuildingFloorAgent
    from cityg.planning.floor_brief import geometry_summary
    geometry=_geometry if _geometry is not None else geometry_summary(building,base)
    accepted=[];rejected=[]
    for candidate in catalog:
        try:
            profile=resolve_brief(expand_topology_brief(nominal_brief(candidate,building,base),[candidate]),
                                  building,base,spec,_geometry=geometry)
            BuildingFloorProgram(building.function,profile).validate(building)
            BuildingFloorAgent._check_spatial_feasibility(profile,building,spec,_geometry=geometry)
            accepted.append({**candidate,'full_profile_checked_at_nominal_assignment':True})
        except ValueError as exc:rejected.append({'topology_id':candidate['id'],'error':str(exc)})
    return accepted,{'offered_before_check':len(catalog),'accepted':len(accepted),'rejected':rejected,
        'scope':'Nominal function assignment and unit weights; adjusted proposals and references must be revalidated.'}
