"""Blender-only static source converter. Run with --background --disable-autoexec.

Reads an explicit JSON job, never executes content in source assets. Keeps
originals untouched. SDF import supports visual geometry, not physics/plugins.
"""
import json
import math
import sys
from pathlib import Path
import xml.etree.ElementTree as ET

import bpy
import bmesh
from mathutils import Matrix, Euler, Vector


def restore_collada_materials(path, objects):
    tree = ET.parse(path).getroot()
    for node in tree.iter():
        node.tag = node.tag.split('}')[-1]
    images = {n.get('id'): n.findtext('init_from') for n in tree.findall('library_images/image')}
    effects = {n.get('id'): n for n in tree.findall('library_effects/effect')}
    for material in tree.findall('library_materials/material'):
        effect = effects.get(material.find('instance_effect').get('url', '').lstrip('#'))
        if effect is None:
            continue
        texture = effect.find('.//diffuse/texture')
        if texture is None:
            continue
        params = {n.get('sid'): n for n in effect.findall('.//newparam')}
        sampler = params.get(texture.get('texture'))
        surface = params.get(sampler.findtext('sampler2D/source')) if sampler is not None else None
        uri = images.get(surface.findtext('surface/init_from')) if surface is not None else None
        if not uri:
            raise ValueError('Unresolved Collada diffuse texture')
        matches = list(path.parent.parent.rglob(Path(uri.replace('\\', '/')).name))
        if len(matches) != 1:
            raise ValueError(f'Missing/ambiguous Collada diffuse: {uri}')
        for obj in objects:
            if obj.type != 'MESH':
                continue
            for mat in obj.data.materials:
                if mat.name.split('.')[0] not in {material.get('name'), material.get('id')}:
                    continue
                mat.use_nodes = True
                shader = mat.node_tree.nodes.get('Principled BSDF')
                tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
                tex.image = bpy.data.images.load(str(matches[0]), check_existing=True)
                mat.node_tree.links.new(tex.outputs['Color'], shader.inputs['Base Color'])
                shader.inputs['Roughness'].default_value = .7


def pose(element):
    if element is None:
        return Matrix.Identity(4)
    if element.get('relative_to'):
        raise ValueError('SDF relative_to frames require a dedicated resolver')
    values = [float(x) for x in element.text.split()]
    if len(values) != 6:
        raise ValueError('Expected six-value SDF pose')
    return Matrix.Translation(values[:3]) @ Euler(values[3:], 'XYZ').to_matrix().to_4x4()


def import_mesh(path):
    before = set(bpy.data.objects)
    suffix = path.suffix.lower()
    if suffix == '.fbx':
        bpy.ops.import_scene.fbx(filepath=str(path), use_anim=True)
    elif suffix in {'.glb', '.gltf'}:
        bpy.ops.import_scene.gltf(filepath=str(path))
    elif suffix == '.obj':
        # SDF coordinates are Z-up; OBJ importer must not rotate into Y-up.
        bpy.ops.wm.obj_import(filepath=str(path), forward_axis='Y', up_axis='Z', use_split_groups=True)
    elif suffix == '.dae':
        bpy.ops.wm.collada_import(filepath=str(path))
    elif suffix == '.stl':
        bpy.ops.wm.stl_import(filepath=str(path))
    else:
        raise ValueError(f'Unsupported mesh: {path}')
    objects = [o for o in bpy.data.objects if o not in before]
    if suffix == '.obj':
        # Legacy MTL Tf=1 is a transmission *filter*, not full glass weight.
        # Blender's OBJ conversion can otherwise make opaque painted cars
        # and rubber transmit the background and render almost black.
        for obj in objects:
            if obj.type != 'MESH':
                continue
            for material in obj.data.materials:
                if material and material.use_nodes:
                    shader = material.node_tree.nodes.get('Principled BSDF')
                    if shader and shader.inputs['Alpha'].default_value >= .99:
                        shader.inputs['Transmission Weight'].default_value = 0
    if suffix == '.dae':
        restore_collada_materials(path, objects)
    return objects


def sdf_import(path, root):
    model = ET.parse(path).getroot().find('model')
    if model is None or model.find('include') is not None or model.find('model') is not None:
        raise ValueError('Nested/included SDF model requires explicit assembly')
    for link in model.findall('link'):
        for visual in link.findall('visual'):
            transform = pose(model.find('pose')) @ pose(link.find('pose')) @ pose(visual.find('pose'))
            geometry = visual.find('geometry')
            mesh = geometry.find('mesh')
            if mesh is not None:
                uri = mesh.findtext('uri', '')
                if not uri.startswith('model://'):
                    raise ValueError(f'Unsupported SDF URI: {uri}')
                source = (root / uri[8:]).resolve()
                if not source.is_relative_to(root.resolve()):
                    raise ValueError('SDF dependency escaped source root')
                objects = import_mesh(source)
                submesh = mesh.findtext('submesh/name')
                if submesh:
                    selected = [o for o in objects if o.type == 'MESH' and o.name.split('.')[0] == submesh]
                    if not selected:
                        raise ValueError(f'Unresolved SDF submesh: {submesh}')
                    for obj in objects:
                        if obj not in selected:
                            bpy.data.objects.remove(obj, do_unlink=True)
                    objects = selected
                    if mesh.findtext('submesh/center', 'false') == 'true':
                        bpy.context.view_layer.update()
                        points = [o.matrix_world @ Vector(c) for o in objects for c in o.bound_box]
                        center = Vector([(min(v[i] for v in points)+max(v[i] for v in points))/2 for i in range(3)])
                        for obj in objects:
                            obj.location -= center
                scale = [float(x) for x in mesh.findtext('scale', '1 1 1').split()]
                transform = transform @ Matrix.Diagonal((*scale, 1))
            elif geometry.find('box') is not None:
                bpy.ops.mesh.primitive_cube_add(size=1)
                obj = bpy.context.object
                obj.scale = tuple(float(x) for x in geometry.findtext('box/size').split())
                objects = [obj]
            elif geometry.find('cylinder') is not None:
                bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=float(geometry.findtext('cylinder/radius')),
                                                    depth=float(geometry.findtext('cylinder/length')))
                objects = [bpy.context.object]
            elif geometry.find('sphere') is not None:
                bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=float(geometry.findtext('sphere/radius')))
                objects = [bpy.context.object]
            else:
                raise ValueError('Unsupported SDF visual geometry')
            bpy.context.view_layer.update()
            for obj in objects:
                if obj.parent not in objects:
                    obj.matrix_world = transform @ obj.matrix_world
            diffuse = visual.findtext('material/diffuse')
            transparency = float(visual.findtext('transparency', '0'))
            if diffuse or transparency:
                material = bpy.data.materials.new(visual.get('name', 'sdf'))
                color = list(float(x) for x in diffuse.split()) if diffuse else [.65,.75,.8,1]
                color[3] *= 1-transparency
                material.diffuse_color = color
                material.use_nodes = True
                shader = material.node_tree.nodes.get('Principled BSDF')
                shader.inputs['Base Color'].default_value = color
                shader.inputs['Alpha'].default_value = color[3]
                shader.inputs['Roughness'].default_value = .2 if transparency else .7
                if transparency:
                    material.surface_render_method = 'DITHERED'
                for obj in objects:
                    if obj.type == 'MESH':
                        obj.data.materials.clear()
                        obj.data.materials.append(material)


def repair_images(search_root, limit, output_root):
    by_name = {}
    for p in search_root.rglob('*'):
        if p.is_file() and p.suffix.lower() in {'.png', '.jpg', '.jpeg', '.tga'}:
            by_name.setdefault(p.name.lower(), []).append(p)
    missing = []
    for image in list(bpy.data.images):
        if image.source != 'FILE':
            continue
        original = Path(bpy.path.abspath(image.filepath))
        if not original.is_file() and not image.packed_file:
            matches = by_name.get(original.name.lower(), [])
            if '/meshes/' in str(original):
                local = Path(str(original).split('/meshes/', 1)[0])
                local_matches = [p for p in matches if p.is_relative_to(local)]
                if len(local_matches) == 1:
                    matches = local_matches
            if 'model:/' in str(original):
                explicit = search_root / str(original).split('model:/', 1)[1].lstrip('/')
                if explicit.is_file():
                    matches = [explicit]
            if len(matches) != 1:
                missing.append(str(original))
                continue
            replacement = bpy.data.images.load(str(matches[0]), check_existing=False)
            replacement.colorspace_settings.name = image.colorspace_settings.name
            image.user_remap(replacement)
            bpy.data.images.remove(image)
            image = replacement
        if image.size[0] == 0:
            missing.append(f'{image.name} -> {image.filepath} ({image.source})')
            continue
        factor = min(1, limit / max(image.size))
        if factor < 1:
            image.scale(max(1, round(image.size[0]*factor)), max(1, round(image.size[1]*factor)))
        # Persist resized pixels before glTF export. Repacking an embedded
        # source image directly can leave Blender's exporter with a stale
        # packed buffer and no image data when it makes a temporary copy.
        import hashlib
        output_root.mkdir(parents=True, exist_ok=True)
        destination = output_root / (hashlib.sha256(image.name.encode()).hexdigest()[:16] + '.png')
        image.filepath_raw = str(destination)
        image.file_format = 'PNG'
        image.save()
        if image.packed_file:
            image.unpack(method='REMOVE')
        image.filepath = str(destination)
        image.reload()
    return missing


def bake_meshes():
    deps = bpy.context.evaluated_depsgraph_get()
    meshes = []
    for obj in list(bpy.context.scene.objects):
        if obj.type != 'MESH' or obj.hide_render:
            continue
        evaluated = obj.evaluated_get(deps)
        mesh = bpy.data.meshes.new_from_object(evaluated, preserve_all_data_layers=True, depsgraph=deps)
        mesh.transform(obj.matrix_world)
        baked = bpy.data.objects.new(obj.name + '_static', mesh)
        bpy.context.collection.objects.link(baked)
        meshes.append(baked)
    for obj in list(bpy.context.scene.objects):
        if obj not in meshes:
            bpy.data.objects.remove(obj, do_unlink=True)
    return meshes


def main(job):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    source = Path(job['source']).resolve()
    details = {}
    if job['kind'] == 'sdf':
        sdf_import(source, Path(job['source_root']))
    else:
        import_mesh(source)
    if job.get('animation'):
        target = next(o for o in bpy.context.scene.objects if o.type == 'ARMATURE')
        imported = import_mesh(Path(job['animation']))
        rig = next(o for o in imported if o.type == 'ARMATURE')
        action = rig.animation_data.action if rig.animation_data else None
        if action is None:
            raise ValueError('Animation has no armature action')
        target.animation_data_clear()
        details['animation_frame_range'] = list(action.frame_range)
        details['target_bones'] = list(target.pose.bones.keys())
        details['animation_bones'] = list(rig.pose.bones.keys())
        # Same Rocketbox naming is necessary but not sufficient; four-view
        # inspection remains a separate gate after static baking.
        if (not set(target.pose.bones.keys()).issubset(rig.pose.bones.keys()) or
                any(not n.endswith('Nub') for n in set(rig.pose.bones.keys())-set(target.pose.bones.keys()))):
            raise ValueError('Animation skeleton mismatch: ' + json.dumps(details))
        # FBX bind poses differ (notably upper arms). Reusing local action
        # channels leaves A-pose offsets. Transfer evaluated WORLD rotations
        # while retaining the target's bone lengths and skinning.
        for bone in target.pose.bones:
            constraint = bone.constraints.new('COPY_ROTATION')
            constraint.target = rig
            constraint.subtarget = bone.name
            constraint.target_space = 'WORLD'
            constraint.owner_space = 'WORLD'
        for obj in imported:
            obj.hide_render = True
        bpy.context.scene.frame_set(job.get('frame', int(action.frame_range[0])+8))
    bpy.context.view_layer.update()
    missing = repair_images(Path(job.get('texture_root', source.parent)), job.get('texture_limit', 1024),
                            Path(job['output']).parent/'textures'/job['asset_id'])
    if missing:
        raise ValueError(f'Unresolved textures: {missing}')
    meshes = bake_meshes()
    if not meshes:
        raise ValueError('No visible meshes')
    # Canonical CityG +X forward, +Z up; source yaw is a reviewed parameter.
    yaw = math.radians(job.get('yaw_deg', 0))
    rotation = Matrix.Rotation(yaw, 4, 'Z')
    for obj in meshes:
        obj.data.transform(rotation)
    corners = [o.matrix_world @ v.co for o in meshes for v in o.data.vertices]
    low = Vector([min(c[i] for c in corners) for i in range(3)])
    high = Vector([max(c[i] for c in corners) for i in range(3)])
    extent = high-low
    if min(extent) <= 0:
        raise ValueError('Degenerate bounds')
    height = job.get('height_m', extent.z)
    physical = [v/extent.z*height for v in extent]
    before = sum(len(o.data.polygons) for o in meshes)
    budget = job.get('triangle_budget', 40000)
    for obj in meshes:
        bpy.context.view_layer.objects.active = obj
        triangulate = obj.modifiers.new('triangulate', 'TRIANGULATE')
        bpy.ops.object.modifier_apply(modifier=triangulate.name)
    triangles = sum(len(o.data.polygons) for o in meshes)
    if triangles > budget:
        for obj in meshes:
            bpy.context.view_layer.objects.active = obj
            modifier = obj.modifiers.new('review_lod', 'DECIMATE')
            modifier.ratio = budget / triangles
            bpy.ops.object.modifier_apply(modifier=modifier.name)
    # Simplify in physical coordinates, then normalize actual surviving
    # vertices. Decimation may change an extremum; stale bounds float assets.
    for obj in meshes:
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
        bm.to_mesh(obj.data)
        bm.free()
    corners = [v.co for o in meshes for v in o.data.vertices]
    low = Vector([min(c[i] for c in corners) for i in range(3)])
    high = Vector([max(c[i] for c in corners) for i in range(3)])
    extent = high-low
    physical = [v/extent.z*height for v in extent]
    center = (low+high)/2
    normalization = Matrix.Diagonal((1/extent.x, 1/extent.y, 1/extent.z, 1)) @ Matrix.Translation(-center)
    for obj in meshes:
        obj.data.transform(normalization)
    output = Path(job['output'])
    output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=str(output), export_format='GLB', export_yup=False,
                              export_animations=False, export_skins=False, export_cameras=False,
                              export_lights=False, export_image_format='AUTO')
    report = {**details, 'dimensions_m': physical, 'source_bounds': [list(low), list(high)],
              'triangles': sum(len(o.data.polygons) for o in meshes), 'source_triangles': triangles,
              'mesh_count': len(meshes), 'missing_textures': missing,
              'static_pose': bool(job.get('animation')), 'job': job}
    output.with_suffix('.json').write_text(json.dumps(report, indent=2))


if __name__ == '__main__':
    main(json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text()))
