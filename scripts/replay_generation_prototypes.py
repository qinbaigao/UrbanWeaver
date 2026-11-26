"""Replay prototype commits on an actual saved, unfurnished planning checkpoint.

This is a deterministic integration regression, NOT a new LLM/VLM generation.
It never modifies the source run or publishes a replacement for its final scene.
"""
import argparse
import hashlib
from pathlib import Path

from cityg.assets import AssetRegistry
from cityg.geometry import GeometryCompiler
from cityg.memory import MemoryStore
from cityg.planning.generation_prototypes import GenerationPrototypes, load_options
from cityg.serialization import load_city, save_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--config', type=Path, default=Path('configs/generation_prototypes.json'))
    parser.add_argument('--asset-registry', type=Path, default=Path('assets/asset_registry.json'))
    args = parser.parse_args()
    source = (args.run/'checkpoints/unfurnished_city.json').resolve()
    if args.output.exists():
        parser.error('Use a new output directory; replay never overwrites a run')
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    city = load_city(source)
    runtime = GenerationPrototypes(load_options(args.config))
    # The final package already contains trial aliases. Start from the source
    # library just as generation does; prepare_resources binds its references.
    registry = AssetRegistry(args.asset_registry)
    compiler = GeometryCompiler(asset_registry=registry)
    registry = runtime.prepare_resources(registry, compiler)
    with MemoryStore(args.output/'memory.sqlite') as memory:
        result, report = runtime.populate(city, registry, compiler, memory_store=memory)
    assert hashlib.sha256(source.read_bytes()).hexdigest() == digest, 'Source changed'
    save_json(result, args.output/'city.json')
    save_json({'mode': 'saved_checkpoint_deterministic_replay', 'new_model_calls': 0,
               'source': str(source), 'source_sha256': digest, 'source_unchanged': True,
               'prototype_report': report}, args.output/'replay_report.json')
    print({'status': report['status'], 'summary': report['summary'],
           'transaction_status': report['transaction']['status'], 'output': str(args.output)})
    return 0 if report['status'] == 'adapted' else 3


if __name__ == '__main__':
    raise SystemExit(main())
