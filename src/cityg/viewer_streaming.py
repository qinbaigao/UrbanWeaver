"""Viewer-only spatial packaging. Canonical/physics outputs remain untouched.

Every original primitive occurs once in the detail partitions. The overview is
an explicitly labelled LOD subset, not a replacement for the compiled scene.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import json
import math
import zlib

STREAM_THRESHOLD_BYTES = 64 * 1024 * 1024
CHUNK_BYTES = 4 * 1024 * 1024
CHUNK_ITEMS = 2048


def _encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-8')


def _hierarchy(city, exterior):
    """Strip simulation bookkeeping, not identities needed by the renderer."""
    result = {k: v for k, v in city.items() if k != 'world_program'}
    result['districts'] = []
    owners = {}
    for district in city.get('districts', []):
        d = {**district, 'parcels': []}
        result['districts'].append(d)
        for parcel in district.get('parcels', []):
            p = {**parcel, 'buildings': []}
            d['parcels'].append(p)
            for building in parcel.get('buildings', []):
                bid = building['id']
                owners[bid] = bid
                b = {**building, 'floors': []}
                p['buildings'].append(b)
                for connector in building.get('vertical_connectors', []):
                    owners[connector['id']] = bid
                for floor in building.get('floors', []):
                    owners[floor['id']] = bid
                    for kind in ('rooms', 'objects', 'doors'):
                        for item in floor.get(kind, []):
                            owners[item['id']] = bid
                    if exterior:
                        # Preserve floor owners of shell slabs, but don't load
                        # nonexistent interiors into an exterior-only Viewer.
                        b['floors'].append({k: v for k, v in floor.items()
                                           if k not in {'rooms', 'objects', 'doors', 'metadata'}})
                    else:
                        b['floors'].append(floor)
    # Identity lookup is agent/editor bookkeeping; entities already carry IDs
    # and UI metadata. The 200-building registry alone exceeds 60 MB.
    result['metadata'] = {k: v for k, v in result.get('metadata', {}).items()
                          if k != 'identity_registry'}
    result['metadata']['viewer_projection'] = True
    return result, owners


GROUND_CONTEXT = {
    'road_surface', 'junction_surface', 'sidewalk', 'curb', 'road_median',
    'city_ground', 'parcel_ground', 'parcel_edge', 'parcel_surface_patch',
    'river_water', 'river_bank', 'river_promenade', 'riparian_green',
    'bridge_deck', 'bridge_parapet', 'bridge_railing', 'bridge_abutment',
    'landscape_path', 'plaza', 'grass', 'landscape_patch',
}
SHELL_CONTEXT = {
    'exterior_wall', 'roof', 'roof_parapet', 'roof_monitor', 'floor_slab',
    'facade_ground_band', 'entrance_portal', 'entrance_door', 'curtain_wall_glass',
}


def partition_viewer_files(files, *, force=False):
    payload = files.get('geometry_manifest.json', b'')
    if not force and len(payload) < STREAM_THRESHOLD_BYTES:
        return files
    geometry = json.loads(payload)
    if geometry.get('streaming'):
        return files
    primitives = geometry.get('primitives', [])
    city, owners = _hierarchy(json.loads(files['city.json']),
                              geometry.get('metadata', {}).get('interiors_compiled') is False)
    layers = {item['id']: item.get('layer_type') for item in geometry.get('layers', [])}
    categories = Counter(p.get('metadata', {}).get('asset_category') for p in primitives
                         if p.get('metadata', {}).get('resolved_asset'))
    overview, buckets = [], defaultdict(list)
    for primitive in primitives:
        bid = owners.get(primitive.get('owner_id'))
        c = primitive['center']
        scope = ('building', bid) if bid else ('tile', f'{math.floor(c["x"]/160)}_{math.floor(c["y"]/160)}')
        buckets[scope].append(primitive)
        semantic = primitive.get('semantic_class', '')
        metadata = primitive.get('metadata', {})
        layer = layers.get(primitive.get('layer_id'))
        bucket = zlib.crc32(primitive['id'].encode('utf-8'))
        keep = False
        if metadata.get('resolved_asset'):
            category = metadata.get('asset_category')
            if category != 'facade_module':
                keep = bucket % max(1, math.ceil(categories[category] / 100)) == 0
        elif layer == 'building_shell':
            keep = (semantic in SHELL_CONTEXT or
                    (semantic == 'facade_window' and bucket % 16 == 0) or
                    (semantic == 'facade_language_detail' and bucket % 24 == 0))
        elif layer in {'roads', 'district', 'root'}:
            keep = semantic in GROUND_CONTEXT
        if keep:
            overview.append(primitive)

    result = {k: v for k, v in files.items() if k != 'geometry_manifest.json'}
    result['city.json'] = _encode(city)
    details, previews = [], []

    def emit(items, prefix, scope=None):
        descriptors, batch, encoded, size = [], [], [], 0

        def flush():
            nonlocal batch, encoded, size
            if not batch:
                return
            filename = f'{prefix}_{len(descriptors):04d}.json'
            data = b'{"primitives":[' + b','.join(encoded) + b']}'
            result[filename] = data
            # Rotation-safe bounds; oversized meshes are never clipped here.
            bounds = [float('inf'), float('inf'), -float('inf'), -float('inf')]
            zmin, zmax = float('inf'), -float('inf')
            for p in batch:
                radius = math.hypot(p['size']['x'], p['size']['y']) / 2
                x, y = p['center']['x'], p['center']['y']
                bounds = [min(bounds[0], x-radius), min(bounds[1], y-radius),
                          max(bounds[2], x+radius), max(bounds[3], y+radius)]
                zmin = min(zmin, p['center']['z'] - p['size']['z']/2)
                zmax = max(zmax, p['center']['z'] + p['size']['z']/2)
            descriptors.append({'file': filename, 'count': len(batch), 'bytes': len(data),
                                'bounds': bounds, 'scope': scope[0] if scope else 'overview',
                                'bounds3d': [bounds[0], bounds[1], zmin, bounds[2], bounds[3], zmax],
                                'scope_id': scope[1] if scope else None,
                                'owner_ids': sorted({p['owner_id'] for p in batch}) if scope else []})
            batch, encoded, size = [], [], 0

        for p in items:
            data = _encode(p)
            if batch and (size+len(data) > CHUNK_BYTES or len(batch) >= CHUNK_ITEMS):
                flush()
            # A single authored inline mesh is indivisible; fail explicitly
            # before making a resource too large for a browser to decode.
            if len(data) > STREAM_THRESHOLD_BYTES:
                raise ValueError(f'Viewer primitive {p["id"]} exceeds 64 MiB; mesh partitioning required')
            batch.append(p)
            encoded.append(data)
            size += len(data)+1
        flush()
        return descriptors

    previews = emit(overview, 'overview')
    for index, (scope, items) in enumerate(sorted(buckets.items())):
        details.extend(emit(items, f'detail_{index:05d}', scope))
    header = {k: v for k, v in geometry.items() if k != 'primitives'}
    # Standalone manifests are already loaded separately by both viewer modes.
    for key, filename in [('navigation', 'navigation.json'), ('state_machines', 'interactions.json')]:
        if filename in result:
            header.pop(key, None)
    header['primitives'] = []
    header['streaming'] = {
        'version': 1, 'total_primitives': len(primitives), 'overview_primitives': len(overview),
        'overview': previews, 'chunks': details,
        'semantics': sorted({p['semantic_class'] for p in primitives}),
        'policy': 'overview_lod_with_lossless_local_detail',
    }
    result['geometry_manifest.json'] = _encode(header)
    return result
