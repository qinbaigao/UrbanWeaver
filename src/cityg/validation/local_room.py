"""Compiled-room acceptance shared by visual reprogramming and local edits."""
from copy import deepcopy

from cityg.planning.city_prototype_adapter import verify_room
from cityg.serialization import to_primitive
from cityg.validation.rendered_inventory import rendered_inventory_preserved


def room_mesh_retention(before_objects, after_objects, before_scene, after_scene):
    """A complete Room Agent rewrite must not hide GLB loss behind new IDs."""
    from collections import Counter
    def counts(objects, scene):
        bindings={(p.owner_id,p.metadata.get('asset_id')) for p in scene.primitives
                  if p.primitive_type=='mesh'}
        return Counter(o.category for o in objects if (o.id,o.asset_id) in bindings)
    old,new=counts(before_objects,before_scene),counts(after_objects,after_scene)
    lost={key:count-new.get(key,0) for key,count in old.items() if new.get(key,0)<count}
    return {'ok':not lost,'before':dict(old),'after':dict(new),'lost_mesh_categories':lost}


def room_compilation_gate(before, room_id, compiler):
    """Capture an immutable baseline; recompile only the containing building."""
    source = deepcopy(before)
    def target(city):
        return next((b, f, r) for b in city.iter_buildings() for f in b.floors
                    for r in f.rooms if r.id == room_id)
    building, source_floor, _ = target(source)
    baseline = compiler.compile(source, building_ids={building.id})
    def check(candidate):
        b, floor, room = target(candidate)
        scene = compiler.compile(candidate, building_ids={b.id})
        counts = {}
        retention = []
        for kind in ('room_surface_items', 'room_decorations'):
            old = baseline.metadata.get(kind, {}).get(room_id, {})
            current = scene.metadata.get(kind, {}).get(room_id, {})
            counts[kind] = current.get('requested', 0)
            retention.append({'kind': kind, 'before_placed': old.get('placed', 0),
                'after_placed': current.get('placed', 0),
                'ok': current.get('placed', 0) >= old.get('placed', 0)})
        checks = verify_room(scene, b, floor, room, {
            'major_count': sum(o.room_id == room_id for o in floor.objects),
            'expected_inventory': counts})
        meshes = rendered_inventory_preserved(source, candidate,
            to_primitive(baseline), to_primitive(scene))
        mesh_retention=room_mesh_retention(
            [o for o in source_floor.objects if o.room_id==room_id],
            [o for o in floor.objects if o.room_id==room_id],baseline,scene)
        return {'ok': all(row['ok'] for row in retention) and meshes['ok'] and mesh_retention['ok'],
                'room_id': room_id, 'compiled_building_ids': [b.id],
                'room_checks': checks, 'decoration_retention': retention,
                'mesh_bindings': meshes, 'major_mesh_retention':mesh_retention, 'physics_runtime_tested': False}
    return check


def building_compilation_gate(before, building_id, compiler):
    """Appearance/massing refinements must preserve every furnished interior."""
    source = deepcopy(before)
    baseline = compiler.compile(source, building_ids={building_id})
    def check(candidate):
        building = next(b for b in candidate.iter_buildings() if b.id == building_id)
        scene = compiler.compile(candidate, building_ids={building_id})
        rows = []
        for floor in building.floors:
            for room in floor.rooms:
                objects = [o for o in floor.objects if o.room_id == room.id]
                if not objects:
                    continue
                counts = {kind: scene.metadata.get(kind, {}).get(room.id, {}).get('requested', 0)
                          for kind in ('room_surface_items', 'room_decorations')}
                checks = verify_room(scene, building, floor, room,
                    {'major_count': len(objects), 'expected_inventory': counts})
                retained = all(scene.metadata.get(kind, {}).get(room.id, {}).get('placed', 0)
                               >= baseline.metadata.get(kind, {}).get(room.id, {}).get('placed', 0)
                               for kind in counts)
                rows.append({'room_id': room.id, 'ok': retained, 'checks': checks})
        meshes = rendered_inventory_preserved(source, candidate, to_primitive(baseline), to_primitive(scene))
        return {'ok': meshes['ok'] and all(r['ok'] for r in rows), 'rooms': rows,
                'mesh_bindings': meshes, 'compiled_building_ids': [building_id],
                'physics_runtime_tested': False}
    return check
