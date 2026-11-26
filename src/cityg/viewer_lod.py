"""Optional, hash-verified render derivatives. Never used for physics or editing."""
from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path


def collect_viewer_lods(assets: dict[str, bytes], cache_dir=None):
    cache = Path(cache_dir or os.environ.get('CITYG_VIEWER_LOD_CACHE') or
                 Path(__file__).resolve().parents[2] / 'assets' / 'viewer_lods')
    manifest = cache / 'manifest.json'
    if not manifest.is_file():
        return {}
    try:
        records = json.loads(manifest.read_text())['assets']
    except (OSError, ValueError, KeyError):
        logging.warning('Ignoring invalid viewer LOD manifest: %s', manifest)
        return {}
    mapping = {}
    additions = {}
    for asset_id, payload in list(assets.items()):
        record = records.get(asset_id, {})
        if record.get('source_sha256') != hashlib.sha256(payload).hexdigest():
            continue  # changed source: never apply stale derivatives
        levels = []
        for variant in record.get('variants', []):
            try:
                file = (cache / variant['file']).resolve()
                if not file.is_relative_to(cache.resolve()):
                    continue
                data = file.read_bytes()
                if hashlib.sha256(data).hexdigest() != variant['sha256']:
                    continue
                if variant['triangles'] >= record['original_triangles'] or variant['max_pixels'] <= 0:
                    continue
                additions[variant['asset_id']] = data
                levels.append({k: variant[k] for k in ('asset_id', 'max_pixels', 'triangles', 'relative_error_limit')})
            except (OSError, KeyError, TypeError, ValueError):
                continue
        if levels:
            mapping[asset_id] = sorted(levels, key=lambda v: v['max_pixels'])
    assets.update(additions)
    return mapping
