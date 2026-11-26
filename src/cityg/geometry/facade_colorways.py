"""Opt-in building colourways: retain geometry and the original PBR channels."""
from collections import Counter
from dataclasses import replace

VERSION = 'facade_colorway_v1'
PALETTES = {
    'pearl_gray': (1.0, 1.0, 1.0),
    'cool_gray': (.79, .91, 1.0),
    'muted_sage': (.78, .94, .80),
    'slate_blue': (.46, .65, .84),
}
# Representative sRGB means of the installed facade maps. Compensation is
# applied in linear space; it does not erase brick joints or create new maps.
TEXTURE_MEANS = {
    'residential_facade': (.535, .489, .445),
    'residential_brick': (.628, .516, .441),
    'civic_limestone': (.345, .336, .310),
    'civic_stone': (.446, .374, .286),
    'civic_brick': (.588, .488, .401),
    'facade_frame_stone': (.552, .523, .437),
    'facade_frame_limestone': (.543, .510, .431),
}
WARM_WALLS = {'residential_facade', 'residential_brick', 'civic_limestone', 'civic_stone', 'civic_brick'}
SURFACES = {'exterior_wall', 'facade_ground_band', 'facade_zone_band',
            'facade_language_detail', 'facade_frame', 'roof_parapet', 'balcony_slab'}


def owner_buildings(city):
    return {owner: b.id for b in city.iter_buildings() for owner in [b.id, *(f.id for f in b.floors)]}


def select_warm_buildings(city, scene, count):
    """Choose a spatially spread subset; never recolour the shared base material."""
    owners = owner_buildings(city)
    eligible = {owners[p.owner_id] for p in scene.primitives
                if p.owner_id in owners and p.semantic_class == 'exterior_wall'
                and p.material_id in WARM_WALLS}
    buildings = {b.id: b for b in city.iter_buildings()}
    centers = {bid: ((buildings[bid].footprint.min_x + buildings[bid].footprint.max_x)/2,
                     (buildings[bid].footprint.min_y + buildings[bid].footprint.max_y)/2) for bid in eligible}
    if not centers:
        return []
    centroid = tuple(sum(v[i] for v in centers.values())/len(centers) for i in (0, 1))
    def dist(a, b): return sum((x-y)**2 for x,y in zip(a,b))
    selected = [min(centers, key=lambda bid: (dist(centers[bid], centroid), bid))]
    while len(selected) < min(count, len(eligible)):
        selected.append(max(sorted(eligible-set(selected)), key=lambda bid:
            min(dist(centers[bid], centers[other]) for other in selected)))
    return selected if count > 0 else []


def material_color(material, palette):
    if not material.base_color_path:
        return tuple(.82*c for c in palette)
    # Unknown/custom maps are only tinted, never neutralized using unrelated
    # statistics. Known library maps retain their luminance/texture variation.
    mean = TEXTURE_MEANS.get(material.id)
    if mean is None:
        return tuple(a*b for a,b in zip(material.display_color, palette))
    linear = [c/12.92 if c <= .04045 else ((c+.055)/1.055)**2.4 for c in mean]
    return tuple(min(linear)/v*c for v,c in zip(linear,palette))


def apply_facade_colorways(city, scene):
    owners = owner_buildings(city)
    requests = {b.id: b.metadata['facade_colorway'] for b in city.iter_buildings()
                if b.metadata.get('facade_colorway')}
    for bid, name in requests.items():
        if name not in PALETTES:
            raise ValueError(f'Unknown facade colorway for {bid}: {name}')
    materials = {m.id:m for m in scene.materials}
    additions = {}; changed = Counter()
    for p in scene.primitives:
        previous = p.metadata.get(VERSION)
        original = previous['original_material_id'] if previous else p.material_id
        bid = owners.get(p.owner_id)
        name = requests.get(bid)
        if previous:
            p.material_id = original
            p.metadata.pop(VERSION)
        if not name or p.semantic_class not in SURFACES or p.metadata.get('resolved_asset'):
            continue
        # Protect glass/metal and non-facade materials even within a selected building.
        if original not in WARM_WALLS and not original.startswith(('facade_accent_', 'facade_frame_')):
            continue
        source = materials[original]
        key = f'{original}__colorway_{name}'
        additions[key] = replace(source, id=key, display_color=material_color(source, PALETTES[name]))
        p.material_id = key
        p.metadata[VERSION] = {'original_material_id': original, 'palette': name, 'building_id': bid}
        changed[bid] += 1
    scene.materials = [m for m in scene.materials if '__colorway_' not in m.id] + list(additions.values())
    report = {'version': VERSION, 'building_count': len(changed), 'primitive_count': sum(changed.values()),
              'buildings': [{'id':bid, 'palette':requests[bid], 'primitive_count':n} for bid,n in sorted(changed.items())],
              'geometry_changed': False, 'glb_assets_changed': False}
    scene.metadata['facade_colorways'] = report
    return report
