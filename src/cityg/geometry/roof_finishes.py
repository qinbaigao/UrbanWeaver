"""Building-scoped flat-roof finishes, independent of wall and equipment colours."""
from collections import Counter
from dataclasses import replace
import hashlib

from cityg.geometry.facade_colorways import material_color, owner_buildings
from cityg.geometry.model import MaterialSpec

VERSION = 'roof_finish_v1'
FINISHES = {'concrete_gray', 'cool_membrane', 'graphite', 'silver_metal'}


def assign_roof_finishes(city):
    """A stable first palette for an existing scene; explicit choices win."""
    for b in city.iter_buildings():
        if 'roof_finish' in b.metadata:
            continue
        seed = int.from_bytes(hashlib.blake2b(b.id.encode(),digest_size=4).digest(),'big')
        if b.function in {'commercial','industrial','mixed_use'}:
            choices = ['concrete_gray','cool_membrane','graphite','silver_metal','cool_membrane']
        else:
            choices = ['concrete_gray','concrete_gray','cool_membrane','graphite','cool_membrane']
        # Cool wall schemes can use a brighter roof, but do not force every
        # building with the same wall colour into an identical roof treatment.
        if b.metadata.get('facade_colorway')=='slate_blue':
            choices = ['cool_membrane','concrete_gray','silver_metal']
        b.metadata['roof_finish'] = choices[seed % len(choices)]


def finish_materials(materials):
    concrete = materials.get('facade_frame_stone', MaterialSpec('facade_frame_stone',(.6,.6,.6)))
    metal = materials.get('industrial_light', MaterialSpec('industrial_light',(.6,.65,.68)))
    gray = material_color(concrete, (.92,.97,1.0))
    return {
        'concrete_gray': replace(concrete,id='roof_finish_concrete_gray',display_color=gray,
            metallic=0,roughness=.94,texture_scale_m=4.0),
        # Painted finishes use uniform pigment, while retaining surface relief,
        # roughness and AO. The source metal's rusty albedo is intentionally not used.
        'cool_membrane': replace(concrete,id='roof_finish_cool_membrane',
            base_color_path=None,display_color=(.55,.59,.62),metallic=0,roughness=.88,texture_scale_m=5.0),
        'graphite': replace(concrete,id='roof_finish_graphite',
            display_color=tuple(a*b for a,b in zip(gray,(.26,.30,.34))),
            metallic=0,roughness=.96,texture_scale_m=4.0),
        'silver_metal': replace(metal,id='roof_finish_silver_metal',base_color_path=None,
            display_color=(.36,.42,.46),metallic=.45,roughness=.52,texture_scale_m=3.0),
    }


def apply_roof_finishes(city, scene):
    requests = {b.id:b.metadata['roof_finish'] for b in city.iter_buildings() if b.metadata.get('roof_finish')}
    for bid,name in requests.items():
        if name not in FINISHES:
            raise ValueError(f'Unknown roof finish for {bid}: {name}')
    owners = owner_buildings(city)
    variants = finish_materials({m.id:m for m in scene.materials})
    used = {}; counts = Counter(); equipment = 0
    for p in scene.primitives:
        prior = p.metadata.pop(VERSION,None)
        if prior:
            p.material_id = prior['original_material_id']
        bid = owners.get(p.owner_id)
        name = requests.get(bid)
        if not name or p.metadata.get('resolved_asset'):
            continue
        original = p.material_id
        if p.semantic_class == 'roof':
            # Do not reinterpret explicitly pitched/tiled architectural roofs.
            if p.metadata.get('roof_style') in {'pitched','gable','hip','tiled'}:
                continue
            target = variants[name]; counts[bid] += 1
        elif p.semantic_class == 'roof_auxiliary' and original == 'roof':
            target = variants['silver_metal']; equipment += 1
        else:
            continue
        used[target.id] = target
        p.material_id = target.id
        p.metadata[VERSION] = {'original_material_id':original,'building_id':bid,
                              'finish':target.id.removeprefix('roof_finish_')}
    scene.materials = [m for m in scene.materials if not m.id.startswith('roof_finish_')] + list(used.values())
    report = {'version':VERSION,'building_count':len(counts),'roof_count':sum(counts.values()),
        'equipment_corrected':equipment,'geometry_changed':False,
        'finish_counts':dict(Counter(requests[bid] for bid in counts)),
        'buildings':[{'id':bid,'finish':requests[bid],'roof_count':count} for bid,count in sorted(counts.items())]}
    scene.metadata['roof_finishes'] = report
    return report
