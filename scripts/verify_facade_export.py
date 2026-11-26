"""Recompile a frozen scene through the prototype resource binding path."""
import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path

from cityg.assets import AssetRegistry, MaterialLibrary
from cityg.geometry import GeometryCompiler
from cityg.planning.generation_prototypes import GenerationPrototypes, load_options
from cityg.run_provenance import record_stage_start
from cityg.serialization import load_city, save_json
from cityg.services import OpenUSDBackend


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('package',type=Path);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--prototype-config',type=Path,default=Path('configs/generation_prototypes.json'))
    args=p.parse_args()
    if args.output.exists(): p.error('Use a fresh output directory')
    project=Path(__file__).resolve().parents[1]
    source=args.package/'city.json';digest=hashlib.sha256(source.read_bytes()).hexdigest()
    pinned=AssetRegistry(args.package/'assets/asset_registry.json')
    registry=AssetRegistry(project/'assets/asset_registry.json')
    materials_path=args.package/'assets/material_library.json'
    materials=MaterialLibrary(materials_path) if materials_path.is_file() else None
    compiler=GeometryCompiler(asset_registry=registry,material_library=materials,
        facade_asset_index_path=str(project/'assets/facades/asset_annotations_reviewed.json'),
        facade_asset_project_root=str(project),facade_asset_cache_root=str(args.output/'facade_cache'))
    runtime=GenerationPrototypes(load_options(args.prototype_config))
    detached=runtime.prepare_resources(registry,compiler)
    # Restore original scene bindings after the normal preparation step. This
    # includes the missing historical facade cache path that triggered failure.
    for record in pinned.list_all():
        if record.geometry_path:
            record=replace(record,geometry_path=str(pinned.resolve_path(record.geometry_path).resolve()))
        detached.register(record,overwrite=detached.get(record.asset_id) is not None)
    record_stage_start(args.output)
    package=args.output/'final/openusd'
    OpenUSDBackend(compiler).compile(load_city(source),package)
    manifest=json.loads((package/'geometry_manifest.json').read_text())
    exported=AssetRegistry(package/'assets/asset_registry.json')
    ids={p['metadata']['asset_id'] for p in manifest['primitives'] if p.get('metadata',{}).get('resolved_asset')}
    missing=[key for key in sorted(ids) if exported.get(key) is None or not exported.get(key).geometry_path
             or not exported.resolve_path(exported.get(key).geometry_path).is_file()]
    unchanged=hashlib.sha256(source.read_bytes()).hexdigest()==digest
    report={'ok':unchanged and not missing,'source_unchanged':unchanged,'source_sha256':digest,
            'resolved_asset_count':len(ids),'missing_assets':missing,
            'registry_shared':compiler.facade_asset_runtime.asset_registry is compiler.asset_registry}
    save_json(report,args.output/'report.json');print(report)
    return 0 if report['ok'] else 3


if __name__=='__main__': raise SystemExit(main())
