"""Check that unchanged canonical asset bindings keep their compiled meshes.

Canonical object counts alone miss a GLB silently replaced by procedural boxes.
This is a representation-preservation gate, not a visual-quality/physics score.
"""


def rendered_inventory_preserved(before_city, after_city, before_manifest, after_manifest):
    before = {o.id: o for o in before_city.iter_objects()}
    after = {o.id: o for o in after_city.iter_objects()}
    def bindings(manifest):
        return {(p['owner_id'], p.get('metadata', {}).get('asset_id'))
                for p in manifest.get('primitives', []) if p.get('primitive_type') == 'mesh'}
    previous = bindings(before_manifest)
    current = bindings(after_manifest)
    checked = []; failures = []
    for oid, old in before.items():
        new = after.get(oid)
        # Removal/replacement permission belongs to the semantic transaction
        # gate. Here we test unchanged bindings only, without blocking genuine
        # intentional furniture replacements.
        if new is None or old.asset_id != new.asset_id or (oid, old.asset_id) not in previous:
            continue
        checked.append(oid)
        if (oid, new.asset_id) not in current:
            failures.append({'object_id': oid, 'asset_id': new.asset_id,
                             'code': 'mesh_binding_lost'})
    return {'ok': not failures, 'checked_object_ids': checked, 'failures': failures,
            'physics_runtime_tested': False, 'visual_quality_verified': False}
