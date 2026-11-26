"""Persistent budgeted interior scope; canonical floor plans remain available."""


def floor_enabled(city, building, floor):
    scope=getattr(city,"metadata",{}).get("interior_scope")
    return scope is None or floor.level in scope["building_levels"].get(building.id,[])


def materialize_access_dependencies(city, detail_levels):
    """Enable lower circulation even if furnishing a selected upper room fails.

    This changes compilation scope only. Detail authorization remains separate;
    access floors do not acquire permission to repartition or furnish rooms.
    """
    buildings = {b.id: b for b in city.iter_buildings()}
    scope = city.metadata['interior_scope']
    scope['detail_building_levels'] = {bid: list(levels) for bid, levels in detail_levels.items()}
    dependencies = {}
    for bid, levels in detail_levels.items():
        if not levels:
            continue
        access = {f.level for f in buildings[bid].floors if 0 <= f.level <= max(levels)}
        scope['building_levels'][bid] = sorted(set(scope['building_levels'].get(bid, [])) | access)
        dependencies[bid] = sorted(access - set(levels))
    scope['access_dependency_levels'] = dependencies
    return scope


def select_scope(city, building_limit, floor_limit):
    from cityg.interior_requirements import requirements_for
    buildings=list(city.iter_buildings())
    selected=[b for b in buildings if requirements_for(b)]
    if len(selected)>building_limit: raise ValueError('Explicit interior buildings exceed detail budget')
    # Prefer distinct functions, then fill deterministically. Avoid changing
    # requested massing just to get easier room geometry.
    for function in ("residential","commercial","public_service"):
        b=next((b for b in buildings if b.function==function and b not in selected),None)
        if b is not None and len(selected)<building_limit:selected.append(b)
    for b in buildings:
        if len(selected)>=building_limit:break
        if b not in selected:selected.append(b)
    mapping={b.id:[f.level for f in sorted(b.floors,key=lambda f:f.level)[:floor_limit]] for b in selected}
    for b in selected:
        levels=sorted({level for r in requirements_for(b) for level in r['levels']})
        if levels:
            if len(levels)>floor_limit: raise ValueError('Explicit interior floors exceed detail budget')
            mapping[b.id]=levels
    city.metadata["interior_scope"]={"policy":"selected_buildings_first_floors_v1",
        "building_levels":mapping,"building_limit":building_limit,"floors_per_building":floor_limit,
        "canonical_uncompiled_rooms_retained":True}
    return city.metadata["interior_scope"]
