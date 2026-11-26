"""Optional, reversible art direction for paper renders, not scene generation.

Works on the private Blender copy only. Coordinates are world-space metres;
no geometry, placements or camera parameters are changed.
"""
import bpy


VERSION = 'realism_v1_facades'


def _noise(nodes, links, vector, scale, detail=2):
    noise = nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = scale
    noise.inputs['Detail'].default_value = detail
    links.new(vector, noise.inputs['Vector'])
    return noise.outputs['Fac']


def _ramp(nodes, links, value, low, high):
    ramp = nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = (*low, 1)
    ramp.color_ramp.elements[1].color = (*high, 1)
    links.new(value, ramp.inputs[0])
    return ramp.outputs[0]


def _replace(links, socket, value):
    for link in list(socket.links):
        links.remove(link)
    if hasattr(value, 'is_output'):
        links.new(value, socket)
    else:
        socket.default_value = value


def enhance(scene):
    """Apply exactly once; loading an enhanced cache is also supported."""
    if scene.get('cityg_render_look') == VERSION:
        return dict(scene['cityg_look_report'])
    if scene.get('cityg_render_look'):
        raise ValueError('Different look revision: rebuild from the unmodified base cache')
    changed = {'water': 0, 'glass': 0, 'mineral_surfaces': 0, 'weathered_facades': 0, 'window_backing': 0}
    for mat in bpy.data.materials:
        if not mat.use_nodes:
            continue
        n, l = mat.node_tree.nodes, mat.node_tree.links
        bs = n.get('Principled BSDF')
        if not bs:
            continue
        # Only procedural CityG materials; imported asset PBR is left intact.
        name = mat.name
        if name.endswith('_river_water'):
            changed['water'] += 1
            geo = n.new('ShaderNodeNewGeometry')
            mapping = n.new('ShaderNodeVectorMath'); mapping.operation = 'MULTIPLY'
            mapping.inputs[1].default_value = (.65, 1.8, 1)
            l.new(geo.outputs['Position'], mapping.inputs[0])
            broad = _noise(n, l, mapping.outputs[0], .55, 3)
            fine = _noise(n, l, mapping.outputs[0], 3.2, 2)
            bump = n.new('ShaderNodeBump')
            bump.inputs['Strength'].default_value = .7
            bump.inputs['Distance'].default_value = .14
            l.new(broad, bump.inputs['Height'])
            ripple = n.new('ShaderNodeBump')
            ripple.inputs['Strength'].default_value = .45
            ripple.inputs['Distance'].default_value = .025
            l.new(fine, ripple.inputs['Height']); l.new(bump.outputs[0], ripple.inputs['Normal'])
            _replace(l, bs.inputs['Normal'], ripple.outputs[0])
            body = _noise(n, l, geo.outputs['Position'], .045, 2)
            color = _ramp(n, l, body, (.010, .029, .032), (.029, .068, .059))
            _replace(l, bs.inputs['Base Color'], color)
            _replace(l, bs.inputs['Roughness'], .085)
            bs.inputs['Metallic'].default_value = 0
            bs.inputs['IOR'].default_value = 1.333
            # Opaque tinted body represents turbid river water, with dielectric
            # surface reflection; not a claim of volumetric water simulation.
            bs.inputs['Transmission Weight'].default_value = 0
            bs.inputs['Coat Weight'].default_value = .35
            bs.inputs['Coat Roughness'].default_value = .065
            bs.inputs['Coat IOR'].default_value = 1.333
        elif name.endswith(('_facade_window', '_curtain_wall_glass', '_storefront_window')):
            changed['glass'] += 1
            panel = n.new('ShaderNodeAttribute'); panel.attribute_name = 'cityg_panel_seed'
            rough = n.new('ShaderNodeMapRange')
            rough.inputs['To Min'].default_value = .075
            rough.inputs['To Max'].default_value = .16
            l.new(panel.outputs['Fac'], rough.inputs['Value'])
            _replace(l, bs.inputs['Roughness'], rough.outputs[0])
            base = tuple(bs.inputs['Base Color'].default_value)[:3]
            tint = tuple(max(.018, min(.24, c * .48)) for c in base)
            color = _ramp(n, l, panel.outputs['Fac'], tuple(c * .58 for c in tint), tuple(c * 1.40 for c in tint))
            _replace(l, bs.inputs['Base Color'], color)
            bs.inputs['Metallic'].default_value = .12
            bs.inputs['Transmission Weight'].default_value = .1
            bs.inputs['IOR'].default_value = 1.5
            bs.inputs['Coat Weight'].default_value = .35
            bs.inputs['Coat Roughness'].default_value = .095
        elif name.endswith('_window_backing'):
            changed['window_backing'] += 1
            panel = n.new('ShaderNodeAttribute'); panel.attribute_name = 'cityg_panel_seed'
            ramp = n.new('ShaderNodeValToRGB'); ramp.color_ramp.interpolation = 'CONSTANT'
            ramp.color_ramp.elements[0].color = (.016, .022, .028, 1)
            ramp.color_ramp.elements[1].position = .76
            ramp.color_ramp.elements[1].color = (.28, .26, .22, 1)
            middle = ramp.color_ramp.elements.new(.45); middle.color = (.065, .075, .082, 1)
            l.new(panel.outputs['Fac'], ramp.inputs[0]); _replace(l, bs.inputs['Base Color'], ramp.outputs[0])
        elif name.endswith(('_exterior_wall', '_roof_parapet', '_sidewalk', '_road_surface', '_roof')):
            changed['mineral_surfaces'] += 1
            geo = n.new('ShaderNodeNewGeometry')
            noise = _noise(n, l, geo.outputs['Position'], 2.5, 2)
            bump = n.new('ShaderNodeBump')
            bump.inputs['Strength'].default_value = .18
            bump.inputs['Distance'].default_value = .012
            l.new(noise, bump.inputs['Height'])
            if bs.inputs['Normal'].is_linked:
                l.new(bs.inputs['Normal'].links[0].from_socket, bump.inputs['Normal'])
            _replace(l, bs.inputs['Normal'], bump.outputs[0])
        if (name.endswith(('_exterior_wall', '_roof_parapet', '_facade_ground_band', '_facade_zone_band', '_facade_frame'))
                and not any(word in name.lower() for word in ('glass', 'metal', 'aluminum'))):
            changed['weathered_facades'] += 1
            geo = n.new('ShaderNodeNewGeometry')
            stretch = n.new('ShaderNodeVectorMath'); stretch.operation = 'MULTIPLY'
            stretch.inputs[1].default_value = (1.1, 1.1, .065)
            l.new(geo.outputs['Position'], stretch.inputs[0])
            streaks = _noise(n, l, stretch.outputs[0], 1, 3)
            stain = _ramp(n, l, streaks, (.55, .55, .50), (1.03, 1.01, .98))
            age = n.new('ShaderNodeAttribute'); age.attribute_name = 'cityg_building_age'
            strength = n.new('ShaderNodeMapRange')
            strength.inputs['To Min'].default_value = .12
            strength.inputs['To Max'].default_value = .62
            l.new(age.outputs['Fac'], strength.inputs['Value'])
            mix = n.new('ShaderNodeMixRGB'); mix.blend_type = 'MULTIPLY'
            if bs.inputs['Base Color'].is_linked:
                l.new(bs.inputs['Base Color'].links[0].from_socket, mix.inputs[1])
            else:mix.inputs[1].default_value = bs.inputs['Base Color'].default_value
            l.new(strength.outputs[0], mix.inputs[0]); l.new(stain, mix.inputs[2])
            _replace(l, bs.inputs['Base Color'], mix.outputs[0])
    scene['cityg_render_look'] = VERSION
    scene['cityg_look_report'] = changed
    return changed


def atmosphere(scene):
    """Low-cost depth-based aerial perspective, not physical participating media."""
    scene.view_layers[0].use_pass_mist = True
    scene.world.mist_settings.start = 250
    scene.world.mist_settings.depth = 2000
    scene.world.mist_settings.falloff = 'LINEAR'
    scene.use_nodes = True
    n, l = scene.node_tree.nodes, scene.node_tree.links
    n.clear()
    render = n.new('CompositorNodeRLayers')
    factor = n.new('CompositorNodeMath'); factor.operation = 'MULTIPLY'
    factor.inputs[1].default_value = .07
    l.new(render.outputs['Mist'], factor.inputs[0])
    mix = n.new('CompositorNodeMixRGB'); mix.blend_type = 'MIX'
    mix.inputs[2].default_value = (.52, .63, .73, 1)
    l.new(factor.outputs[0], mix.inputs[0]); l.new(render.outputs['Image'], mix.inputs[1])
    out = n.new('CompositorNodeComposite'); l.new(mix.outputs[0], out.inputs[0])
