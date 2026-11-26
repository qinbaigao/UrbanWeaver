"""Feed measured functional-reference failures back to the Floor Agent."""
from cityg.schemas import Bounds2D
from cityg.interior_requirements import requirements_for
from cityg.planning.interior_frame import InteriorFrame
from cityg.planning.programmed import ProgrammedCityPlanner
from cityg.planning.spatial_layout import solve_spatial_floor
from cityg.planning.functional_seeds import find_inventory_witness
from cityg.refinement.inventory_allocation import allocate_remaining_inventory


def inventory_asset_context(building, resolver):
    from cityg.planning.interiors import FloorDetailAgent, ASSET_CATALOG
    detail=FloorDetailAgent(asset_resolver=resolver);rows=[];seen=set()
    for requirement in requirements_for(building):
        for item in requirement['inventory']:
            key=(item['room_function'],item['category'])
            if key in seen:continue
            seen.add(key)
            resolved=detail._resolve_asset(ASSET_CATALOG[item['category']],room_type=item['room_function'])
            asset=resolved or ASSET_CATALOG[item['category']]
            rows.append({'function':item['room_function'],'category':item['category'],
                'dimensions_m':[asset.width_m,asset.depth_m,asset.height_m],'front_axis':asset.front_axis,
                'geometry_source':'asset_registry' if resolved else 'procedural_catalog'})
    return rows


def check_inventory_capacity(profile, building, geometry, resolver, *, seed=17):
    frame=InteriorFrame(geometry['circulation_axis']);checks=[]
    for original in building.floors:
        rows=requirements_for(building,original.level)
        if not any(row['inventory'] for row in rows):continue
        zone=profile.zone_for_level(original.level)
        archetype=zone.archetype if zone else profile.for_role('ground' if original.level==0 else 'typical')
        if archetype is None or archetype.spatial_program is None:
            raise ValueError('Inventory capacity requires a realized spatial floor program')
        floor=solve_spatial_floor(archetype.spatial_program,floor_id=original.id,level=original.level,
            height=original.height_m,footprint=building.footprint,entrance=building.entrance,
            core_bounds=Bounds2D(**geometry['core']),circulation_axis=frame.axis,
            corridor_depth=ProgrammedCityPlanner._corridor_depth(frame.bounds(building.footprint).depth,profile.corridor_ratio),
            min_width=archetype.min_room_width_m,max_aspect=archetype.max_room_aspect_ratio,
            max_depth=archetype.max_room_depth_m)
        floor.elevation_m=original.elevation_m
        allocations={rid:items for fn in {i['room_function'] for row in rows for i in row['inventory']}
            for rid,items in allocate_remaining_inventory(building,floor,fn).items()}
        for room in floor.rooms:
            if room.id not in allocations:continue
            program,evidence=find_inventory_witness(building,floor,room,allocations[room.id],resolver,seed=seed)
            checks.append({'level':floor.level,'room_id':room.id,'function':room.function,
                'size_m':[room.bounds.width,room.bounds.depth],'inventory':allocations[room.id],**evidence})
    # Unsupported reference families (e.g. >8 seats around one table) are not
    # evidence against the Floor Agent's geometry. Leave those to Room Agent
    # planning and the final count/compiled gates; do not label them certified.
    failed=[c for c in checks if c['status']!='metric_witness' and c.get('tested',0)>0]
    if failed:
        import json
        raise ValueError('Measured inventory reference has no feasible placement in proposed floor: '+json.dumps(failed)+
            '. Replan counts, function slots or area weights while preserving plate/core/entry and ALL requirements. '
            'For living+dining consider two living_room slots sharing the two functional bundles. '
            'Give table-and-seating groups usable width and door clearance, not just enough total area. '
            'This bounded reference search is conservative, not a mathematical proof of impossibility.')
    covered=bool(checks) and all(c['status']=='metric_witness' for c in checks)
    return {'status':'metric_references_fit' if covered else 'partial_reference_coverage',
            'checks':checks,'compiled_verified':False,
            'scope':'Minimum functional references only; final Room Agent transactions and compiled checks remain required'}
