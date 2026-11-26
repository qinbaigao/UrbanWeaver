"""Render-only river surface/shore materials and distant-land continuation.

The exported camera looks below the horizon: distant land, not a mirrored sky,
must occupy rays escaping the finite city. No atmosphere or facade edits here.
"""
import hashlib
import json
from pathlib import Path
import random

import bpy
import numpy as np
from mathutils import Vector
from landscape_math import backdrop_height, outside_distance, top_ray_vertical
from realism import _noise, _ramp, _replace

VERSION = 'waterfront_v2'

WATER_TONES = {
    'original': ((.009, .033, .038), (.022, .066, .064)),
    'lighter_teal': ((.012, .046, .052), (.029, .089, .088)),
}


def apply_water_tone(tone):
    """Set only body-color ramp endpoints; keep waves and reflection unchanged.

    Absolute palettes make repeated use of cached scenes idempotent and allow
    restoring the original palette without accumulating brightness adjustments.
    """
    palette = WATER_TONES[tone]
    materials = [m for m in bpy.data.materials if m.name.endswith('_river_water')]
    if len(materials) != 1:
        raise ValueError('Water tone requires exactly one waterfront water material')
    mat = materials[0]
    shaders = [n for n in mat.node_tree.nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled']
    if len(shaders) != 1:
        raise ValueError('Unexpected water shader structure')
    links = list(shaders[0].inputs['Base Color'].links)
    if len(links) != 1 or links[0].from_node.bl_idname != 'ShaderNodeValToRGB':
        raise ValueError('Water body color is not driven by its expected ramp')
    ramp = links[0].from_node.color_ramp
    if len(ramp.elements) != 2:
        raise ValueError('Expected two water body color endpoints')
    for element, color in zip(ramp.elements, palette):
        element.color = (*color, 1)
    return {'tone': tone, 'linear_rgb_endpoints': palette,
            'changed_meshes': [], 'new_meshes': [],
            'changed_materials': [mat.name], 'new_materials': [],
            'scope': 'Only water body color ramp; geometry, wave normals, IOR, roughness, lighting and background unchanged'}


def _texture(nodes, links, path, position, scale, noncolor=False):
    mapping=nodes.new('ShaderNodeVectorMath');mapping.operation='SCALE'
    mapping.inputs['Scale'].default_value=scale;links.new(position,mapping.inputs[0])
    tex=nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(path),check_existing=True)
    if noncolor:tex.image.colorspace_settings.name='Non-Color'
    tex.projection='BOX';tex.projection_blend=.2;links.new(mapping.outputs[0],tex.inputs['Vector'])
    return tex.outputs['Color']


def _mix(nodes, links, a, b, factor=1, mode='MULTIPLY'):
    mix=nodes.new('ShaderNodeMixRGB');mix.blend_type=mode
    mix.inputs[0].default_value=factor
    for value,socket in ((a,mix.inputs[1]),(b,mix.inputs[2])):
        if hasattr(value,'is_output'):links.new(value,socket)
        else:socket.default_value=(*value,1)
    return mix.outputs[0]


def _river_materials(project):
    changed=[];files=set()
    for mat in bpy.data.materials:
        kind=next((s for s in ('river_water','river_bank','river_promenade','riparian_green') if mat.name.endswith('_'+s)),None)
        if not kind or not mat.use_nodes:continue
        n=mat.node_tree.nodes;l=mat.node_tree.links;n.clear()
        bs=n.new('ShaderNodeBsdfPrincipled');out=n.new('ShaderNodeOutputMaterial');l.new(bs.outputs[0],out.inputs['Surface'])
        geo=n.new('ShaderNodeNewGeometry');pos=geo.outputs['Position']
        if kind=='river_water':
            stretch=n.new('ShaderNodeVectorMath');stretch.operation='MULTIPLY'
            stretch.inputs[1].default_value=(1.8,.55,1);l.new(pos,stretch.inputs[0])
            broad=_noise(n,l,stretch.outputs[0],.46,3);fine=_noise(n,l,stretch.outputs[0],2.6,2)
            bump=n.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.7;bump.inputs['Distance'].default_value=.16
            l.new(broad,bump.inputs['Height'])
            ripple=n.new('ShaderNodeBump');ripple.inputs['Strength'].default_value=.4;ripple.inputs['Distance'].default_value=.035
            l.new(fine,ripple.inputs['Height']);l.new(bump.outputs[0],ripple.inputs['Normal'])
            l.new(ripple.outputs[0],bs.inputs['Normal'])
            color=_ramp(n,l,_noise(n,l,pos,.038,2),(.009,.033,.038),(.022,.066,.064))
            l.new(color,bs.inputs['Base Color'])
            bs.inputs['IOR'].default_value=1.333;bs.inputs['Roughness'].default_value=.075
            bs.inputs['Coat Weight'].default_value=.4;bs.inputs['Coat Roughness'].default_value=.06
            bs.inputs['Coat IOR'].default_value=1.333
        else:
            if kind=='river_bank':
                folder=project/'assets/incoming/facade_materials/granite_wall';stem='granite_wall';tint=(.56,.54,.45);scale=.35
            elif kind=='river_promenade':
                folder=project/'assets/incoming/ground_materials/concrete_pavement';stem='concrete_pavement';tint=(.60,.57,.51);scale=.4
            else:
                folder=project/'assets/incoming/ground_materials/grass_path_2';stem='grass_path_2';tint=(.45,.55,.31);scale=.2
            albedo=folder/(stem+'_base_color_2k.jpg');rough=folder/(stem+'_roughness_2k.jpg')
            for path in (albedo,rough):
                if not path.is_file():raise FileNotFoundError(path)
                files.add(str(path))
            tex=_texture(n,l,albedo,pos,scale);color=_mix(n,l,tex,tint)
            macro=_ramp(n,l,_noise(n,l,pos,.065,2),(.61,.66,.56),(1.04,1.02,.96))
            color=_mix(n,l,color,macro)
            if kind=='river_bank':
                split=n.new('ShaderNodeSeparateXYZ');l.new(pos,split.inputs[0])
                wet=n.new('ShaderNodeMapRange');wet.clamp=True
                wet.inputs['From Min'].default_value=-3.45;wet.inputs['From Max'].default_value=-2.25
                wet.inputs['To Min'].default_value=.40;wet.inputs['To Max'].default_value=1
                l.new(split.outputs['Z'],wet.inputs['Value']);color=_mix(n,l,color,wet.outputs[0])
            l.new(color,bs.inputs['Base Color'])
            l.new(_texture(n,l,rough,pos,scale,True),bs.inputs['Roughness'])
            bump=n.new('ShaderNodeBump');bump.inputs['Distance'].default_value=.045;bump.inputs['Strength'].default_value=.28
            l.new(tex,bump.inputs['Height']);l.new(bump.outputs[0],bs.inputs['Normal'])
        changed.append(mat.name)
    if len(changed)!=4:raise ValueError(f'Expected four distinct waterfront materials, found {changed}')
    return changed,{p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in sorted(files)}


def _backdrop(scene, report, asset_instances):
    ground=[o for o in scene.objects if o.type=='MESH' and any(m and m.name.endswith('_city_ground') for m in o.data.materials)]
    if not ground:raise ValueError('No city ground boundary to protect')
    points=[o.matrix_world@Vector(v) for o in ground for v in o.bound_box]
    bounds=(min(p.x for p in points),max(p.x for p in points),min(p.y for p in points),max(p.y for p in points))
    # No terrain displacement inside the original city rectangle; -8 m is
    # below the river bed (-5.3 m), so the backdrop cannot cover the river.
    x0,x1,y0,y1=bounds;step=80
    xs=np.arange(x0-3200,x1+3201,step);ys=np.arange(y0-3200,y1+3201,step)
    vertices=[(float(x),float(y),backdrop_height(float(x),float(y),bounds)) for y in ys for x in xs]
    width=len(xs)
    faces=[(j*width+i,j*width+i+1,(j+1)*width+i+1,(j+1)*width+i) for j in range(len(ys)-1) for i in range(width-1)]
    mesh=bpy.data.meshes.new('distant_land_mesh');mesh.from_pydata(vertices,[],faces);mesh.update()
    for p in mesh.polygons:p.use_smooth=True
    obj=bpy.data.objects.new('distant_land_backdrop',mesh);scene.collection.objects.link(obj)
    mat=bpy.data.materials.new('Distant vegetation soil mosaic');mat.use_nodes=True
    n=mat.node_tree.nodes;l=mat.node_tree.links;bs=n.get('Principled BSDF');geo=n.new('ShaderNodeNewGeometry')
    coarse=_noise(n,l,geo.outputs['Position'],.013,3)
    color=_ramp(n,l,coarse,(.045,.075,.028),(.14,.19,.075))
    detail=_ramp(n,l,_noise(n,l,geo.outputs['Position'],.2,2),(.65,.72,.60),(1.12,1.10,.92))
    l.new(_mix(n,l,color,detail),bs.inputs['Base Color']);bs.inputs['Roughness'].default_value=.95
    mesh.materials.append(mat)
    # Reuse one already imported real tree, with the authored instance scales.
    unique={};chosen=None
    for path,key in report['asset_hashes'].items():
        if key not in unique:unique[key]=len(unique)
        if 'island_tree_02' in path:chosen=unique[key];break
    if chosen is None:raise ValueError('No existing Island Tree available for backdrop')
    template=bpy.data.objects[f'asset_template_{chosen}'];sample=None
    for obj in list(scene.objects):
        for modifier in obj.modifiers:
            if modifier.type!='NODES':continue
            if any(node.bl_idname=='GeometryNodeObjectInfo' and node.inputs['Object'].default_value==template for node in modifier.node_group.nodes):
                sample=obj;break
        if sample:break
    scale=tuple(sample.data.attributes['size'].data[0].vector)
    bottom=min(v.co.z for v in template.data.vertices);top=max(v.co.z for v in template.data.vertices)
    authored_height=(top-bottom)*scale[2]
    camera_inverse=scene.camera.matrix_world.inverted()
    half_y=scene.camera.data.sensor_height/(2*scene.camera.data.lens)
    half_x=half_y*scene.render.resolution_x*scene.render.pixel_aspect_x/scene.render.resolution_y
    rng=random.Random(219);entries=[]
    for _ in range(160000):
        x=rng.uniform(x0-1800,x1+1800);y=rng.uniform(y0-1800,y1+1800)
        distance=outside_distance(x,y,bounds)
        if not 60<distance<1800:continue
        height=backdrop_height(x,y,bounds)
        local=camera_inverse@Vector((x,y,height+8))
        if local.z>=0:continue
        nx=local.x/(-local.z*half_x);ny=local.y/(-local.z*half_y)
        if not (-1.08<nx<1.08 and -.05<ny<1.08):continue
        # Loose clumps, no new regular plantation rows.
        import math
        if math.sin(x/83)*math.cos(y/117)+math.sin((x-y)/69)<-.5:continue
        factor=rng.uniform(10,18)/authored_height;size=dict(zip('xyz',(v*factor for v in scale)))
        entries.append({'center':dict(x=x,y=y,z=height-bottom*size['z']),
                        'size':size,'rotation_z_deg':rng.uniform(0,360)})
        if len(entries)==3500:break
    asset_instances(entries,template,'distant_land')
    return ['distant_land_backdrop','asset_instances_distant_land'],bounds,len(entries)


def apply_waterfront(scene, doc, report, project, asset_instances):
    if scene.get('cityg_waterfront'):
        if scene['cityg_waterfront']!=VERSION:raise ValueError('Use prior clean facade cache for new waterfront revision')
        result=json.loads(scene['cityg_waterfront_report'])
        result.setdefault('new_materials',['Distant vegetation soil mosaic'])
        return result
    materials,textures=_river_materials(project)
    objects,bounds,count=_backdrop(scene,report,asset_instances)
    result={'version':VERSION,'changed_meshes':[],'new_meshes':objects,'changed_materials':materials,
            'new_materials':['Distant vegetation soil mosaic'],
            'texture_sha256':textures,'protected_city_bounds':list(bounds),'distant_tree_instances':count,
            'top_centre_ray_z':top_ray_vertical(doc['camera']),
            'scope':'Only waterfront materials and decorative land outside city bounds. Approved facades/camera/light unchanged; no haze or fluid simulation.',
            'background_is_generated_city':False}
    scene['cityg_waterfront']=VERSION;scene['cityg_waterfront_report']=json.dumps(result)
    return result
