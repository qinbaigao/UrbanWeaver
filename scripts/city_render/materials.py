"""Offline PBR adaptation for the compiled city; source materials stay untouched."""
import math
from pathlib import Path
import bpy


def multiply(nodes,links,value,factor):
    node=nodes.new('ShaderNodeMixRGB');node.blend_type='MULTIPLY';node.inputs[0].default_value=1
    links.new(value,node.inputs[1]);node.inputs[2].default_value=(*factor,1)
    return node.outputs[0]


def city_material(spec, semantic, source):
    mat=bpy.data.materials.new(spec['id']+'_'+semantic);mat.use_nodes=True
    n=mat.node_tree.nodes;l=mat.node_tree.links;bs=n.get('Principled BSDF')
    color=spec['display_color'];bs.inputs['Base Color'].default_value=(*color,1)
    bs.inputs['Roughness'].default_value=spec['roughness'];bs.inputs['Metallic'].default_value=spec.get('metallic',0)
    for field,socket in [('base_color_path','Base Color'),('normal_path','Normal'),('roughness_path','Roughness')]:
        if not spec.get(field):continue
        file=Path(spec[field]);file=file if file.is_absolute() else source/file
        if not file.is_file():raise FileNotFoundError(file)
        tex=n.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(file),check_existing=True)
        if field!='base_color_path':tex.image.colorspace_settings.name='Non-Color'
        value=tex.outputs['Color']
        if field=='normal_path':
            normal=n.new('ShaderNodeNormalMap');normal.inputs['Strength'].default_value=.45
            l.new(value,normal.inputs['Color']);value=normal.outputs[0]
        elif field=='base_color_path':
            tint=(.32,.48,.23) if semantic=='parcel_ground' and 'lawn' in spec['id'] else (.80,.78,.73) if semantic=='parcel_ground' else color
            value=multiply(n,l,value,tint)
        l.new(value,bs.inputs[socket])
    if semantic in ('facade_window','storefront_window','curtain_wall_glass'):
        bs.inputs['Transmission Weight'].default_value=.32
        bs.inputs['IOR'].default_value=1.46
        bs.inputs['Coat Weight'].default_value=.2
        bs.inputs['Coat Roughness'].default_value=.16
        bs.inputs['Roughness'].default_value=max(.12,spec['roughness'])
    if semantic in ('parcel_ground','city_ground','roof','roof_surface_detail','road_surface'):
        geo=n.new('ShaderNodeNewGeometry');noise=n.new('ShaderNodeTexNoise')
        noise.inputs['Scale'].default_value=1/24 if semantic in ('parcel_ground','city_ground') else 1/10
        noise.inputs['Detail'].default_value=2;l.new(geo.outputs['Position'],noise.inputs['Vector'])
        ramp=n.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].position=.15;ramp.color_ramp.elements[1].position=.85
        ramp.color_ramp.elements[0].color=(.64,.70,.60,1);ramp.color_ramp.elements[1].color=(1.08,1.04,.93,1)
        l.new(noise.outputs['Fac'],ramp.inputs[0])
        mix=n.new('ShaderNodeMixRGB');mix.blend_type='MULTIPLY';mix.inputs[0].default_value=1
        if bs.inputs['Base Color'].is_linked:l.new(bs.inputs['Base Color'].links[0].from_socket,mix.inputs[1])
        else:mix.inputs[1].default_value=(*color,1)
        l.new(ramp.outputs[0],mix.inputs[2]);l.new(mix.outputs[0],bs.inputs['Base Color'])
    if semantic=='river_water':
        bs.inputs['Base Color'].default_value=(.025,.105,.125,1)
        bs.inputs['Metallic'].default_value=0;bs.inputs['IOR'].default_value=1.333
        bs.inputs['Roughness'].default_value=.25
        bs.inputs['Coat Weight'].default_value=.32;bs.inputs['Coat Roughness'].default_value=.2
        geo=n.new('ShaderNodeNewGeometry');noise=n.new('ShaderNodeTexNoise')
        noise.inputs['Scale'].default_value=1.6;noise.inputs['Detail'].default_value=2
        l.new(geo.outputs['Position'],noise.inputs['Vector']);bump=n.new('ShaderNodeBump')
        bump.inputs['Strength'].default_value=.28;bump.inputs['Distance'].default_value=.035
        l.new(noise.outputs['Fac'],bump.inputs['Height']);l.new(bump.outputs[0],bs.inputs['Normal'])
    return mat


def daylight(scene, hdr, rotation_deg=110, exposure=.4, sun_azimuth=225, sun_elevation=42,
             sun_energy=3.5, world_strength=.4):
    for obj in list(bpy.data.objects):
        if obj.type=='LIGHT' and obj.name.startswith('Soft warm afternoon sunlight'):
            bpy.data.objects.remove(obj,do_unlink=True)
    world=bpy.data.worlds.new('Curated city daylight');world.use_nodes=True;scene.world=world
    n=world.node_tree.nodes;l=world.node_tree.links
    tex=n.new('ShaderNodeTexEnvironment');tex.image=bpy.data.images.load(str(hdr),check_existing=True)
    coordinates=n.new('ShaderNodeTexCoord');mapping=n.new('ShaderNodeMapping')
    mapping.inputs['Rotation'].default_value[2]=math.radians(rotation_deg)
    l.new(coordinates.outputs['Generated'],mapping.inputs['Vector']);l.new(mapping.outputs[0],tex.inputs[0])
    background=n.get('Background');l.new(tex.outputs[0],background.inputs['Color']);background.inputs['Strength'].default_value=world_strength
    # Finite city bounds expose below-horizon rays. Pure-sky HDRs often contain
    # nadir seams/poles there; show their upper hemisphere to camera rays only,
    # while preserving the original HDR for illumination and reflections.
    split=n.new('ShaderNodeSeparateXYZ');l.new(mapping.outputs[0],split.inputs[0])
    z=n.new('ShaderNodeMath');z.operation='ABSOLUTE';l.new(split.outputs['Z'],z.inputs[0])
    combine=n.new('ShaderNodeCombineXYZ');l.new(split.outputs['X'],combine.inputs['X']);l.new(split.outputs['Y'],combine.inputs['Y']);l.new(z.outputs[0],combine.inputs['Z'])
    sky=n.new('ShaderNodeTexEnvironment');sky.image=tex.image;l.new(combine.outputs[0],sky.inputs[0])
    camera_background=n.new('ShaderNodeBackground');camera_background.inputs['Strength'].default_value=.7;l.new(sky.outputs[0],camera_background.inputs['Color'])
    path=n.new('ShaderNodeLightPath');mix=n.new('ShaderNodeMixShader')
    l.new(path.outputs['Is Camera Ray'],mix.inputs[0]);l.new(background.outputs[0],mix.inputs[1]);l.new(camera_background.outputs[0],mix.inputs[2]);l.new(mix.outputs[0],n.get('World Output').inputs['Surface'])
    sun=bpy.data.lights.new('Soft warm afternoon sunlight','SUN');sun.energy=sun_energy;sun.angle=math.radians(2)
    sun.color=(1,.94,.84);obj=bpy.data.objects.new('Soft warm afternoon sunlight',sun);scene.collection.objects.link(obj)
    from mathutils import Vector
    az=math.radians(sun_azimuth);el=math.radians(sun_elevation)
    direction=Vector((math.cos(az)*math.cos(el),math.sin(az)*math.cos(el),math.sin(el)))
    obj.rotation_euler=(-direction).to_track_quat('-Z','Y').to_euler()
    scene.view_settings.view_transform='AgX';scene.view_settings.look='AgX - Medium High Contrast';scene.view_settings.exposure=exposure
