"""Optional sky resources for offline/portable rendering, not scene geometry."""
import hashlib
import json
import os
from pathlib import Path


def collect_viewer_skies(environments, cache_dir=None):
    root = Path(cache_dir or os.environ.get('CITYG_VIEWER_SKY_CACHE') or
                Path(__file__).resolve().parents[2]/'assets/incoming/hdri/skies')
    if not (root/'manifest.json').is_file():
        return {}
    manifest = json.loads((root/'manifest.json').read_text())
    config_path = Path(__file__).resolve().parents[2]/'configs/viewer_skies.json'
    settings = json.loads(config_path.read_text()).get('presets',{}) if config_path.is_file() else {}
    presets = {}
    for key, record in manifest['presets'].items():
        file = (root/record['file']).resolve()
        if not file.is_relative_to(root.resolve()) or not file.is_file():
            continue
        data = file.read_bytes()
        if hashlib.sha256(data).hexdigest() != record['sha256']:
            continue
        environments[file.name] = data
        tuning = settings.get(key,{})
        if tuning.get('asset') != record.get('asset'):
            tuning = {}
        presets[key] = {**record, **tuning, 'file':file.name}
    return presets


def default_environment_file(environments, presets):
    sky_files = {p['file'] for p in presets.values()}
    return next((name for name in sorted(environments) if name not in sky_files), None)
