"""Recover a planned city without repeating LLM calls; keep all backend checks.

Instrumentation only: wrappers delegate unchanged arguments to the real compiler.
Periodic in-process stack dumps do not require ptrace/sudo.
"""
from __future__ import annotations

import argparse
import faulthandler
import functools
import hashlib
import json
import time
from pathlib import Path

from cityg.assets import AssetRegistry, MaterialLibrary
from cityg.geometry import GeometryCompiler, GeometryValidator
from cityg.serialization import load_city, save_json
from cityg.services import OpenUSDBackend
from cityg.usd import UsdaWriter
from cityg.viewer import export_portable_viewer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        parser.error('Recovery output must be absent or empty')
    output.mkdir(parents=True, exist_ok=True)
    project = Path(__file__).resolve().parents[1]
    started = time.monotonic()
    with (output/'progress.jsonl').open('a', encoding='utf-8') as log, \
         (output/'stacks.log').open('w', encoding='utf-8') as stacks:
        def event(stage, **data):
            record = {'elapsed_s': round(time.monotonic()-started, 3), 'stage': stage, **data}
            text = json.dumps(record, ensure_ascii=False)
            print(text, flush=True)
            log.write(text+'\n')
            log.flush()

        def instrument(instance, name, *, road=False):
            original = getattr(instance, name)
            @functools.wraps(original)
            def wrapped(*a, **kw):
                detail = {'road_id': a[1].id} if road else {}
                event(name+'_start', **detail)
                start = time.monotonic()
                result = original(*a, **kw)
                event(name+'_end', duration_s=round(time.monotonic()-start, 3), **detail)
                return result
            setattr(instance, name, wrapped)

        faulthandler.dump_traceback_later(120, repeat=True, file=stacks)
        try:
            event('loading_checkpoint')
            checkpoint = args.checkpoint.resolve()
            with checkpoint.open('rb') as source:
                digest = hashlib.sha256()
                for chunk in iter(lambda: source.read(1024*1024), b''):
                    digest.update(chunk)
            city = load_city(checkpoint)
            save_json({'source': str(checkpoint), 'sha256': digest.hexdigest(),
                       'interiors_compiled': False, 'llm_repeated': False}, output/'recovery.json')
            registry = AssetRegistry(project/'assets/asset_registry.json')
            materials = MaterialLibrary(project/'assets/material_library.json')
            compiler = GeometryCompiler(asset_registry=registry, material_library=materials,
                include_interiors=False,
                facade_asset_index_path=str(project/'assets/facades/asset_annotations_reviewed.json'))
            for name in ('_compile_roads', '_compile_landscape', '_compile_parcel_landscape',
                         '_compile_buildings', '_compile_navigation'):
                instrument(compiler, name)
            instrument(compiler.streetscape_compiler, 'compile')
            instrument(compiler.streetscape_compiler, '_compile_cross_section', road=True)
            validator, writer = GeometryValidator(), UsdaWriter()
            instrument(validator, 'validate')
            instrument(writer, 'write')
            scene = compiler.compile(city)
            event('saving_geometry_checkpoint', primitive_count=len(scene.primitives))
            save_json(scene, output/'geometry_checkpoint.json')
            backend = OpenUSDBackend(compiler, validator, writer)
            backend.compile(city, output/'openusd', _scene_override=scene)
            event('backend_complete')
            export_portable_viewer(output/'openusd', output/'viewer')
            event('viewer_complete', path=str(output/'viewer'))
        except BaseException as error:
            event('failed', error=f'{type(error).__name__}: {error}')
            raise
        finally:
            faulthandler.cancel_dump_traceback_later()


if __name__ == '__main__':
    main()
