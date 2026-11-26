"""Optional material-only flat-roof variety using the existing PBR library."""
from collections import Counter
from dataclasses import replace

from cityg.geometry.facade_colorways import owner_buildings
from cityg.geometry.roof_programs import roof_profile, roof_seed

VERSION = 'roof_texture_v1'
# Library ID, pigment multiplier, repeat size in metres. No displacement or
# geometry changes: aggregate remains a texture, not thousands of loose stones.
PRESETS = {
    'fine_concrete': ('facade_frame_stone', (.75,.80,.84), 2.7),
    'gravel_gray': ('gravel_warm', (.57,.64,.69), 2.2),
    'gravel_warm': ('gravel_warm', (.68,.62,.51), 2.6),
    'bitumen': ('gravel_warm', (.17,.19,.22), 1.3),
    'pavers': ('paving_light', (.70,.72,.71), 3.2),
}


def texture_choice(building):
    explicit = building.metadata.get('roof_texture')
    if explicit is not None:
        if explicit not in {'original', *PRESETS}:
            raise ValueError('Unknown roof texture: '+str(explicit))
        return explicit
    # Do not reinterpret an authored metallic finish as loose ballast.
    if building.metadata.get('roof_finish') == 'silver_metal': return 'original'
    choices = ['original','fine_concrete','gravel_gray','gravel_warm','bitumen']
    if roof_profile(building) == 'garden':
        choices = ['original','pavers','pavers','fine_concrete','gravel_gray']
    return choices[roof_seed(building.id+':roof_texture') % len(choices)]


def apply_roof_textures(city, scene):
    enabled = city.metadata.get('roof_textures', {}).get('enabled', False)
    requests = {b.id:texture_choice(b) for b in city.iter_buildings()
                if enabled or 'roof_texture' in b.metadata}
    owners = owner_buildings(city)
    materials = {m.id:m for m in scene.materials}
    additions = {}; changed = Counter(); skipped = Counter()
    for p in scene.primitives:
        p.metadata = dict(p.metadata)  # authored primitives may share a dictionary
        previous = p.metadata.pop(VERSION, None)
        if previous: p.material_id = previous['original_material_id']
        bid = owners.get(p.owner_id); choice = requests.get(bid, 'original')
        if choice == 'original' or p.metadata.get('resolved_asset'): continue
        if p.metadata.get('roof_style') in {'pitched','gable','hip','tiled'}: continue
        # Rebind only roofs and their thin tonal overlays, not solar panels,
        # plants, service paths, equipment pads, façades or rooftop furniture.
        tone = None
        if p.metadata.get('roof_system') and p.material_id.startswith('roofscape_tone_'):
            tone = int(p.material_id.rsplit('_', 1)[1])
        elif p.semantic_class != 'roof': continue
        base, color, scale = PRESETS[choice]
        source = materials.get(base)
        if source is None or not source.base_color_path:
            skipped[choice] += 1; continue  # no texture: retain original finish
        factor = (0.88,.96,1.025)[tone] if tone is not None else 1.
        mid = f'{VERSION}_{choice}_{tone if tone is not None else "base"}'
        additions[mid] = replace(source, id=mid,
            display_color=tuple(c*factor for c in color), metallic=0,
            roughness=.96 if choice in {'bitumen','gravel_gray','gravel_warm'} else .88,
            texture_scale_m=scale)
        p.metadata[VERSION] = {'original_material_id':p.material_id,'preset':choice,'building_id':bid}
        p.material_id = mid; changed[bid] += 1
    scene.materials = [m for m in scene.materials if not m.id.startswith(VERSION+'_')] + list(additions.values())
    report = {'version':VERSION,'building_count':len(changed),'rebound_primitives':sum(changed.values()),
              'preset_counts':dict(Counter(requests[b] for b in changed)),
              'unchanged_building_count':len(requests)-len(changed),
              'missing_texture_primitives':dict(skipped),'geometry_changed':False}
    scene.metadata['roof_textures'] = report
    return report
