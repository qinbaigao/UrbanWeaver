"""Spatially bounded merge of an authorized canonical core retrofit.

Retain frozen assets and exterior geometry instead of re-resolving their
registries. Recompile changed partitions, door positions, cores and slabs.
"""
from copy import deepcopy
from dataclasses import asdict,replace

from cityg.geometry.compiler import GeometryCompiler
from cityg.geometry.door_kinematics import fit_door_leaf
from cityg.geometry.model import GeometryScene,Vec3
from cityg.geometry.slab_openings import subtract_openings,transport_slab_holes
from cityg.runtime.transport_planning import primitive_box
from cityg.runtime.mobile_geometry import rect_overlap,xy_bounds
from cityg.schemas import Bounds2D


def compile_transport_retrofit(city,previous,receipt):
    compiler=GeometryCompiler();ids={r['building_id'] for r in receipt['buildings']}
    # Architecture-only pass: frozen room finishes and assets are reused,
    # never regenerated with a different material/asset configuration.
    fresh=GeometryScene(city.id,city.coordinate_system,materials=compiler._materials())
    compiler._define_layers(city,fresh)
    compiler._compile_buildings(city,fresh,building_ids=ids)
    bands={r['building_id']:Bounds2D(**r['band']) for r in receipt['buildings']}
    changed_rooms={r['room_id'] for b in receipt['buildings'] for r in b['changed_rooms']}
    changed_doors={d for b in receipt['buildings'] for d in b['changed_door_ids']}
    buildings={b.id:b for b in city.iter_buildings() if b.id in ids}
    floors={f.id:(b,f) for b in buildings.values() for f in b.floors}
    connectors={c.id for b in buildings.values() for c in b.vertical_connectors}
    def changed(p):
        if p.owner_id in connectors:return True
        if p.layer_id.startswith('shell:') and p.owner_id in floors:
            return p.semantic_class=='floor_slab' or (p.semantic_class=='collision_envelope' and p.size.z<.5)
        if not p.layer_id.startswith('floor:') or p.layer_id[6:] not in floors:return False
        b,f=floors[p.layer_id[6:]];band=bands[b.id]
        if p.owner_id in changed_rooms|changed_doors:return True
        if set(p.metadata.get('room_ids',[]))&changed_rooms:return True
        return rect_overlap(xy_bounds(primitive_box(p)),
            (band.min_x-.11,band.min_y-.11,band.max_x+.11,band.max_y+.11))
    removed=[p for p in previous.primitives if changed(p)]
    kept=[deepcopy(p) for p in previous.primitives if not changed(p)]
    additions=[]
    # The visual slab is independently cut too; it must not hide a shaft hole.
    for p in fresh.primitives:
        if not changed(p):continue
        if p.semantic_class=='floor_slab' and p.layer_id.startswith('shell:'):
            if abs(p.rotation_z_deg%360)>1e-7:raise ValueError('Visual shaft clipping requires axis-aligned slab')
            b,f=floors[p.owner_id];outer=Bounds2D(p.center.x-p.size.x/2,p.center.y-p.size.y/2,
                p.center.x+p.size.x/2,p.center.y+p.size.y/2)
            for i,part in enumerate(subtract_openings(outer,transport_slab_holes(b,f))):
                additions.append(replace(p,id=f'{p.id}__transport_{i}',
                    center=Vec3(part.center.x,part.center.y,f.elevation_m-p.size.z/2-.001),
                    size=Vec3(part.width,part.depth,p.size.z)))
        else:
            # Shared-edge ordinals change after room insertion. Namespacing
            # prevents aliasing an unchanged wall with a new, unrelated wall.
            additions.append(replace(p,id=p.id if p.semantic_class=='door' else p.id+'__transport_core'))
    scene=deepcopy(previous);scene.primitives=kept+additions
    fitted=[]
    for i,p in enumerate(scene.primitives):
        if p.semantic_class=='door' and p.layer_id[6:] in floors:
            q=fit_door_leaf(p)
            if q!=p:fitted.append(p.id)
            scene.primitives[i]=q
    all_ids=[p.id for p in scene.primitives]
    if len(all_ids)!=len(set(all_ids)):raise ValueError('Retrofit produced duplicate primitive IDs')
    changed_machines={f'state_machine__{x}' for x in (*changed_doors,*connectors)}
    scene.state_machines=[m for m in scene.state_machines if m.id not in changed_machines]
    scene.state_machines.extend(m for m in fresh.state_machines if m.id in changed_machines)
    scene.navigation=compiler._compile_navigation(city,scene)
    scene.materials=list({**{m.id:m for m in fresh.materials},**{m.id:m for m in previous.materials}}.values())
    scene.metadata['transport_core_retrofit']={'scope':'bounded_core_walls_connectors_slabs',
        'building_ids':sorted(ids),'removed_primitive_ids':[p.id for p in removed],
        'added_primitive_ids':[p.id for p in additions],'door_fit_ids':fitted,
        'reused_primitive_count':len(kept),'preserved_asset_registry':True}
    # Fail if any fine room furnishing or owned decoration was changed.
    fine={r.id for b in buildings.values() for f in b.floors for r in f.rooms if r.metadata.get('room_design')}
    objects={o.id for b in buildings.values() for f in b.floors for o in f.objects if o.room_id in fine}
    def locked(p):
        return p.semantic_class!='door' and (p.owner_id in fine|objects or bool(set(p.metadata.get('room_ids',[]))&fine))
    old={p.id:asdict(p) for p in previous.primitives if locked(p)}
    new={p.id:asdict(p) for p in scene.primitives if locked(p)}
    if old!=new:raise ValueError('Retrofit changed locked fine-room geometry')
    scene.metadata['transport_core_retrofit']['locked_fine_primitives_unchanged']=len(old)
    return scene
