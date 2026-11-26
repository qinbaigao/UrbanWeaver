"""Upgrade an existing portable Viewer in place; preserve scene/camera configuration.

Updates frontend, adds optional render LODs and derives chunk AABBs. Does not
regenerate the city or change any primitive, material, camera or simulation file.
"""
import argparse
import json
from pathlib import Path
import shutil
from cityg.viewer import viewer_static_dir
from cityg.viewer_lod import collect_viewer_lods
from cityg.viewer_sky import collect_viewer_skies


def update(root, *, frontend_only=False):
    root = Path(root).resolve()
    config_path = root/'viewer-config.json'
    config = json.loads(config_path.read_text())
    if config.get('source') != 'portable_export':
        raise ValueError('Expected an existing portable export')
    if frontend_only:
        # UI-only upgrades must not rewrite configuration, scene chunks, LODs,
        # user cameras or materials. Retain old bundles for already open tabs.
        static = viewer_static_dir()
        if not (static/'index.html').is_file():
            raise ValueError('Viewer frontend is not built')
        shutil.copyfile(static/'index.html', root/'index.html')
        shutil.copytree(static/'assets', root/'assets', dirs_exist_ok=True,
                        copy_function=shutil.copyfile)
        return {'viewer':str(root),'frontend_only':True,'scene_modified':False}
    assets_dir = (root/config.get('asset_base','assets')).resolve()
    if not assets_dir.is_relative_to(root):
        raise ValueError('Asset directory must be inside portable export')
    assets = {}
    for aid, filename in config.get('asset_files',{}).items():
        if '__viewer_' in aid:
            continue
        file = (assets_dir/filename).resolve()
        if not file.is_relative_to(assets_dir):
            raise ValueError('Invalid asset path')
        assets[aid] = file.read_bytes()
    originals = set(assets)
    lods = collect_viewer_lods(assets)
    for aid in set(assets)-originals:
        filename = f'{aid}.glb'
        file = assets_dir/filename
        if not file.exists():
            file.write_bytes(assets[aid])
        elif file.read_bytes() != assets[aid]:
            raise ValueError(f'Existing LOD differs: {file}')
        config['asset_files'][aid] = filename
    config['asset_lods'] = lods
    environments = {}
    skies = collect_viewer_skies(environments)
    if skies:
        environment_dir = (root/config.get('environment_base','environment')).resolve()
        if not environment_dir.is_relative_to(root):
            raise ValueError('Environment directory must be inside export')
        environment_dir.mkdir(exist_ok=True)
        for filename, data in environments.items():
            file = environment_dir/filename
            if not file.is_file() or file.read_bytes() != data:
                file.write_bytes(data)
        config['sky_presets'] = skies
    geometry_path = root/'scene/geometry_manifest.json'
    geometry = json.loads(geometry_path.read_text())
    for c in geometry.get('streaming',{}).get('chunks',[]):
        if 'bounds3d' in c:
            continue
        chunk_path = (root/'scene'/c['file']).resolve()
        if not chunk_path.is_relative_to(root/'scene'):
            raise ValueError('Invalid chunk path')
        primitives = json.loads(chunk_path.read_text())['primitives']
        zmin = min(p['center']['z']-p['size']['z']/2 for p in primitives)
        zmax = max(p['center']['z']+p['size']['z']/2 for p in primitives)
        c['bounds3d'] = [*c['bounds'][:2],zmin,*c['bounds'][2:],zmax]
    # Generated files only, atomic replacements; retain old JS bundles/bookmarks.
    for file, value in [(geometry_path,geometry),(config_path,config)]:
        temporary = file.with_suffix(file.suffix+'.tmp')
        temporary.write_text(json.dumps(value,ensure_ascii=False,separators=(',',':'))+'\n')
        temporary.replace(file)
    shutil.copytree(viewer_static_dir(),root,dirs_exist_ok=True,copy_function=shutil.copyfile)
    return {'viewer':str(root),'lod_sources':len(lods),'lod_files':len(set(assets)-originals),'sky_presets':list(skies)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('viewer',type=Path)
    parser.add_argument('--frontend-only',action='store_true',
                        help='Update UI only; preserve all scene/configuration/asset data')
    args = parser.parse_args()
    print(json.dumps(update(args.viewer,frontend_only=args.frontend_only),indent=2))
