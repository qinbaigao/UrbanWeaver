"""Prepare a small explicit HSSD fixture shortlist; never approve/promote assets.

Reuses the previously pinned local source index and metadata. Download requires
the user's existing authorized HSSD access; no credentials are read or printed.
"""
import argparse
import csv
import json
from dataclasses import replace
from pathlib import Path

from scripts.prepare_hssd_assets import download, prepare, sha256, validate_plan
from cityg.serialization import save_json
from cityg.assets import AssetRegistry


def make_plan(config, source):
    previous = json.loads((source/'download_plan.json').read_text())
    index = json.loads((source/'source_index.json').read_text())
    metadata = source/'upstream'/previous['metadata_file']
    if index['revision'] != previous['models_revision'] or sha256(metadata) != previous['metadata_sha256']:
        raise ValueError('Pinned source index/metadata mismatch')
    with metadata.open(newline='') as stream:
        rows = {r['id']: r for r in csv.DictReader(stream)}
    selected = []
    for spec in config['assets']:
        row = rows[spec['id']]
        if row.get('decomposedFrom') or row.get('hasMultipleObjects', '').lower() not in ('', 'false'):
            raise ValueError('Fixture needs a separate multi-object review')
        selected.append({**spec, 'metadata': row, 'file': index['files'][spec['id']]})
    plan = {**previous, 'assets': selected, 'gaps': [],
            'source_bytes': sum(e['file']['size'] for e in selected), 'metadata_bytes': 0,
            'max_download_bytes': config['max_download_bytes'],
            'selection_config': {**previous['selection_config'], 'explicit_shortlist': config}}
    validate_plan(plan)
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=Path('configs/prototype_facility_assets.json'))
    parser.add_argument('--source', type=Path, default=Path('assets/prepared/hssd_v1'))
    parser.add_argument('--staging', type=Path, default=Path('assets/prepared/prototype_facilities_v1'))
    parser.add_argument('--download', action='store_true')
    parser.add_argument('--prepare', action='store_true')
    args = parser.parse_args()
    plan = make_plan(json.loads(args.config.read_text()), args.source)
    save_json(plan, args.staging/'download_plan.json')
    print('Pinned shortlist:', len(plan['assets']), 'assets;', plan['source_bytes'], 'bytes', flush=True)
    if args.download:
        download(plan, args.staging)
    if args.prepare:
        prepare(plan, args.staging)
        # Only a worktop's horizontal support is eligible; never annotate the
        # rim of a basin or an appliance bounding box as a usable table.
        from scripts.annotate_interior_assets import triangles
        from scripts.annotate_hssd_assets import discover_supports
        registry = AssetRegistry(args.staging/'candidate_registry.json')
        for record in registry.list_all():
            if record.category != 'kitchen_counter':
                continue
            path = registry.resolve_path(record.geometry_path)
            patches, _ = discover_supports(triangles(path), record.dimensions_m, 'top', '+X')
            registry.register(replace(record, metadata={**record.metadata,
                'room_support_surfaces': patches}), overwrite=True)
        registry.save(args.staging/'candidate_registry.json')


if __name__ == '__main__':
    main()
