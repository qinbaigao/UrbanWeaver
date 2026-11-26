"""No-download compiled feasibility before a visual repair consumes assets."""
from cityg.assets import AssetResolver
from cityg.geometry.surface_dressing import surfaces
from cityg.refinement.room_commit import prepare_room_program
from cityg.validation.local_room import room_compilation_gate


def prepare_preflight(city, room_id, compiler, registry, *, seed=17, repair_guard=None):
    b,f,r=next((b,f,r) for b in city.iter_buildings() for f in b.floors
               for r in f.rooms if r.id==room_id)
    scene=compiler.compile(city,building_ids={b.id})
    objects={o.id:o for o in f.objects if o.room_id==room_id}
    supports=[]
    for kind in ('top','shelves'):
        for s in surfaces([p for p in scene.primitives if p.owner_id in objects],kind):
            obj=next(p.owner_id for p in scene.primitives if p.id==s.primitive_id)
            supports.append({'object_id':obj,'group_id':objects[obj].metadata.get('group_key'),
                'support_surface_id':s.id,'kind':kind,'width_m':s.width,'depth_m':s.depth,
                'clearance_m':s.clearance_m,'reviewed_mesh':s.reviewed_mesh})
    context={'supports':supports[:64],'support_count':len(supports),
        'supports_truncated':len(supports)>64,
        'current_surface_inventory':scene.metadata.get('room_surface_items',{}).get(room_id,{}),
        'current_decoration_inventory':scene.metadata.get('room_decorations',{}).get(room_id,{}),
        'policy':'Preserve accepted inventory and untouched groups. Existing supports are not free capacity. '
                 'Do not add items without compiled placement; proposals are dry-run before asset generation.'}
    compiled_gate=room_compilation_gate(city,room_id,compiler)
    def gate(candidate):
        if repair_guard is not None:
            protected=repair_guard(candidate)
            if not protected['ok']: return protected
        return compiled_gate(candidate)
    # Preview uses the same real local registry with providers explicitly absent.
    resolver=AssetResolver(registry,(),max_provider_calls=0)
    def check(program):
        if repair_guard is not None: repair_guard.check_program(program)
        candidate,stats=prepare_room_program(city,room_id,program,asset_resolver=resolver,seed=seed)
        report=gate(candidate)
        if not report['ok']: raise ValueError('Compiled preflight rejected: '+str(report))
        return {'ok':True,'asset_generation_used':False,'report':report,'placement_stats':stats}
    return context,check,gate
