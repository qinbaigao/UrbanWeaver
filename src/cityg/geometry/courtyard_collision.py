"""Use realized solid shells for explicitly exterior-only courtyard showcases.

Old rectangular simulation envelopes may surround an entire planning lot even
when a much smaller massing was realized. Never route through an active invisible
wall: replace that approximation with the existing solid massing colliders.
All overrides are reversible and disabled when interiors are compiled.
"""

KEY='courtyard_collision_originals'


def restore_collision_overrides(scene):
    originals=scene.metadata.pop(KEY,{})
    for p in scene.primitives:
        if p.id in originals:
            p.collision_enabled=originals[p.id]['collision_enabled']
            p.metadata=originals[p.id]['metadata']


def realize_exterior_collisions(compiler, city, scene, programs):
    if compiler.include_interiors or scene.metadata.get('interiors_compiled') is True:
        return {}
    by_owner={}
    for p in scene.primitives:by_owner.setdefault(p.owner_id,[]).append(p)
    originals={}
    for parcel in city.iter_parcels():
        if parcel.id not in programs:continue
        for building in parcel.buildings:
            # Only explicit massing proxies are safe as solid exterior bodies.
            # Keep legacy envelopes unchanged if a realized solid is missing.
            bodies=[p for p in by_owner.get(building.id,[]) if p.semantic_class=='exterior_wall'
                    and p.metadata.get('visual_proxy') and p.size.z>1]
            if not bodies:continue
            owners={building.id,*(f.id for f in building.floors)}
            proxies=[p for owner in owners for p in by_owner.get(owner,[]) if p.semantic_class=='collision_envelope']
            for p,enabled in [(p,False) for p in proxies]+[(p,True) for p in bodies]:
                if p.collision_enabled==enabled:continue
                originals[p.id]={'collision_enabled':p.collision_enabled,'metadata':p.metadata}
                p.collision_enabled=enabled
                p.metadata={**p.metadata,'courtyard_collision_override':True,
                            'collision_representation':'realized_exterior_solid' if enabled else 'superseded_planning_envelope'}
    if originals:scene.metadata[KEY]=originals
    return originals
