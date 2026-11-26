"""Dimension evidence linking a floor proposal to downstream room references.

Compatibility is only a prefilter: furniture, doors and compiled inventory still
require the existing transaction gates. No reference approval is inferred here.
"""
def compatible_references(function, width, depth, height, references):
    matches=[]
    values={'width_m':width,'depth_m':depth,'area_m2':width*depth,'aspect_ratio':width/depth}
    for row in references:
        bounds=row['applicability']
        if row['function']!=function or height<bounds['min_height_m']: continue
        if all(bounds[k][0]-1e-6<=v<=bounds[k][1]+1e-6 for k,v in values.items()):
            matches.append(row['id'])
    return matches


def check_floor_reference_fit(profile, building, geometry, context):
    from cityg.planning.spatial_layout import solve_spatial_floor
    from cityg.schemas import Bounds2D
    references=context.get('room_dimensions', [])
    required=context.get('minimum_compatible_rooms_per_detailed_floor', 0)
    if not references or not required: return []
    levels=context.get('detailed_levels', [0,1])
    reports=[]
    for floor in building.floors:
        if floor.level not in levels: continue
        zone=profile.zone_for_level(floor.level)
        result=solve_spatial_floor(zone.spatial_program, floor_id=floor.id,level=floor.level,
            height=floor.height_m,footprint=building.footprint,
            corridor_depth=geometry['corridor_depth_m'],core_bounds=Bounds2D(**geometry['core']),
            entrance=building.entrance,min_width=zone.min_room_width_m,
            max_aspect=zone.max_room_aspect_ratio,max_depth=zone.max_room_depth_m,
            circulation_axis=geometry.get('circulation_axis','x'))
        matched=[]
        for room in result.rooms:
            from cityg.planning.prototype_adaptation import door_side, SIDES
            ids=set()
            for door in result.doors:
                if room.id not in (door.room_a_id,door.room_b_id): continue
                turns=SIDES.index(door_side(room,door))
                w,d=(room.bounds.depth,room.bounds.width) if turns%2 else (room.bounds.width,room.bounds.depth)
                ids.update(compatible_references(room.function,w,d,room.height_m,references))
            ids=sorted(ids)
            if ids: matched.append({'room_id':room.id,'function':room.function,'reference_ids':ids})
        if len(matched)<required:
            raise ValueError(f'Level {floor.level}: only {len(matched)} rooms dimensionally match references; '
                f'detail budget needs at least {required}. Choose a topology with matching '
                'nominal_reference_slots and assign their compatible functions to those slots. '
                'Keep every required global function. Do not change plate/core/entry or shrink furniture.')
        reports.append({'level':floor.level,'dimensionally_compatible_rooms':matched,
                        'placement_verified':False})
    return reports
