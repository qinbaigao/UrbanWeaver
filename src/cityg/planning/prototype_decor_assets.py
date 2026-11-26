"""Detached, hash-pinned decoration assets for the opt-in prototype review lab."""
from dataclasses import replace
from hashlib import sha256
import json
import math
from pathlib import Path

from cityg.assets import AssetRegistry


def add_review_decorations(registry, annotations, *, project_root, asset_ids=None):
    """Mutate only a caller-owned detached registry, never a file-backed one."""
    if registry.manifest_path is not None:
        raise ValueError('Decoration trials require a detached registry')
    root = Path(project_root)
    payload = json.loads(Path(annotations).read_text())
    if payload.get('schema_version') != 1:
        raise ValueError('Unsupported decoration annotation schema')
    seen = set()
    for item in payload['assets']:
        if asset_ids is not None and item['id'] not in asset_ids:
            continue
        if item['id'] in seen or registry.get(item['id']) is not None:
            raise ValueError('Decoration trial IDs must not overwrite other assets')
        seen.add(item['id'])
        source = AssetRegistry(root/item['registry'])
        record = source.get(item['source_id'])
        path = source.resolve_path(record.geometry_path).resolve() if record and record.geometry_path else None
        if not path or not path.is_file() or sha256(path.read_bytes()).hexdigest() != item['sha256']:
            raise ValueError(f'Decoration geometry changed or missing: {item["id"]}')
        scale = item.get('scale', 1)
        if type(scale) not in (float,int) or not math.isfinite(scale) or not .4 <= scale <= 3:
            raise ValueError('Unsafe curated physical scale')
        if item['front_axis'] not in {'+X','-X','+Y','-Y'} or not item.get('evidence'):
            raise ValueError('Decoration needs explicit orientation evidence')
        metrics = record.metadata.get('mesh_validation', {})
        if metrics.get('triangle_count', metrics.get('face_count', float('inf'))) > 120000:
            raise ValueError('Decoration exceeds mesh budget')
        size = tuple(v*scale for v in record.dimensions_m)
        meta = {**record.metadata, 'runtime_enabled':True, 'decoration_review_version':1,
                'indoor_annotation_version':1, 'prototype_review_only':True,
                'placement_kind':item['placement_kind'], 'physical_dimensions_m':list(size),
                'curation_evidence':item['evidence'], 'source_geometry_sha256':item['sha256'],
                'curated_uniform_scale':scale,
                'orientation':{**record.metadata.get('orientation',{}),
                    'canonical_forward_axis':item['front_axis'], 'orientation_confidence':'reviewed'}}
        registry.register(replace(record, asset_id=item['id'], category=item['category'],
            geometry_path=str(path), dimensions_m=size, environment='indoor',
            room_types=tuple(item['room_types']), metadata=meta))
