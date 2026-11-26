"""Blender-side check that art direction preserved all city mesh placements.

Run with Blender --background --python check_variant.py -- BASE.blend NEW.blend
REPORT.json [APPROVED_FACADE_REPORT.json]. No scene file is saved or modified.
An optional facade report permits only its listed batch mesh replacements.
"""
import hashlib
import json
from pathlib import Path
import sys

import bpy
import numpy as np


def material_signature(mat):
    if not mat.use_nodes:return str(tuple(mat.diffuse_color))
    nodes=[]
    for node in mat.node_tree.nodes:
        defaults={}
        for socket in node.inputs:
            if not hasattr(socket,'default_value'):continue
            value=socket.default_value
            if not isinstance(value,(str,int,float,bool,type(None))):
                try:value=list(value)
                except TypeError:value=getattr(value,'name',str(value))
            defaults[socket.identifier]=value
        props={key:getattr(node,key) for key in ('operation','blend_type','projection','projection_blend','interpolation','extension') if hasattr(node,key)}
        if getattr(node,'image',None):props['image']=[node.image.filepath,node.image.colorspace_settings.name]
        if hasattr(node,'color_ramp'):
            ramp=node.color_ramp
            props['color_ramp']={'interpolation':ramp.interpolation,'color_mode':ramp.color_mode,
                                 'hue_interpolation':ramp.hue_interpolation,
                                 'elements':[(e.position,list(e.color)) for e in ramp.elements]}
        nodes.append([node.name,node.bl_idname,defaults,props])
    links=sorted((link.from_node.name,link.from_socket.identifier,link.to_node.name,link.to_socket.identifier) for link in mat.node_tree.links)
    return hashlib.sha256(json.dumps([nodes,links],sort_keys=True).encode()).hexdigest()


def snapshot(path):
    bpy.ops.wm.open_mainfile(filepath=str(path.resolve()))
    objects = {}
    for obj in bpy.context.scene.objects:
        if obj.type != 'MESH':
            continue
        mesh = obj.data
        h = hashlib.sha256()
        for rows, field, dtype, components in (
            (mesh.vertices, 'co', np.float32, 3),
            (mesh.loops, 'vertex_index', np.int32, 1),
            (mesh.polygons, 'loop_total', np.int32, 1),
        ):
            values = np.empty(len(rows) * components, dtype=dtype)
            rows.foreach_get(field, values); h.update(values.tobytes())
        h.update(np.asarray(obj.matrix_world, dtype=np.float64).tobytes())
        h.update(bytes([obj.hide_render]))
        for key in ('size', 'rotation'):
            attr = mesh.attributes.get(key)
            if attr:
                values = np.empty(len(attr.data) * 3, dtype=np.float32)
                attr.data.foreach_get('vector', values); h.update(values.tobytes())
        objects[obj.name] = h.hexdigest()
    scene = bpy.context.scene
    camera = scene.camera
    return {
        'meshes': objects,
        'camera_matrix': list(np.asarray(camera.matrix_world).reshape(-1)),
        'lens': camera.data.lens,
        'sensor_height': camera.data.sensor_height,
        'resolution': [scene.render.resolution_x, scene.render.resolution_y],
        'look': scene.get('cityg_render_look', 'base'),
        'materials':{m.name:material_signature(m) for m in bpy.data.materials},
    }


if __name__ == '__main__':
    args = list(map(Path, sys.argv[sys.argv.index('--') + 1:]))
    base_path, variant_path, output = args[:3]
    allowed = set(); allowed_materials=None
    if len(args) == 4:
        approval = json.loads(args[3].read_text())
        allowed = set(approval['changed_meshes']) | set(approval['new_meshes'])
        if 'changed_materials' in approval:
            allowed_materials=set(approval['changed_materials'])|set(approval.get('new_materials',[]))
    elif len(args) != 3:
        raise ValueError('Expected base, variant, report and optional facade plan')
    base, variant = snapshot(base_path), snapshot(variant_path)
    keys = set(base['meshes']) | set(variant['meshes'])
    changed = sorted(k for k in keys if base['meshes'].get(k) != variant['meshes'].get(k))
    camera_ok = all(base[k] == variant[k] for k in ('camera_matrix', 'lens', 'sensor_height', 'resolution'))
    unexpected = sorted(set(changed) - allowed)
    changed_materials=sorted(k for k in set(base['materials'])|set(variant['materials']) if base['materials'].get(k)!=variant['materials'].get(k))
    unexpected_materials=sorted(set(changed_materials)-allowed_materials) if allowed_materials is not None else []
    result = {'ok': not unexpected and not unexpected_materials and camera_ok, 'meshes_checked': len(keys),
              'changed_meshes_or_transforms': changed, 'camera_and_resolution_equal': camera_ok,
              'allowed_facade_mesh_changes': sorted(allowed), 'unexpected_geometry_changes': unexpected,
              'material_scope_checked':allowed_materials is not None,
              'changed_materials':changed_materials,'unexpected_material_changes':unexpected_materials,
              'base': str(base_path), 'variant': str(variant_path), 'look': variant['look'],
              'scope': 'Mesh vertices/topology, world transforms, render visibility, instance scales/rotations and camera; optional explicitly listed facade batches may differ; shader appearance may differ'}
    output.write_text(json.dumps(result, indent=2) + '\n')
    print('CITYG variant check', json.dumps(result))
    if not result['ok']:
        raise ValueError('Variant changed city geometry or camera')
