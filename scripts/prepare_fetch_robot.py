"""Fetch pinned official URDF/meshes and convert to a portable, articulated GLB.

Run conversion in .venv-assets (trimesh + pycollada). No ROS runtime required.
The original URDF, package license declaration, textures and hashes are retained.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import time
from urllib.request import urlopen
import xml.etree.ElementTree as ET

REVISION = 'd22b98f6c21577895f4d2e3a8bd54e329083732b'
BASE = f'https://raw.githubusercontent.com/fetchrobotics/fetch_ros/{REVISION}/'


def download(root):
    def get(relative):
        path = root / relative
        if path.is_file() and path.stat().st_size:
            return path
        for attempt in range(4):
            try:
                with urlopen(BASE + relative, timeout=60) as response:
                    data = response.read()
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
                print('downloaded', relative, len(data), flush=True)
                return path
            except Exception:
                if attempt == 3:
                    raise
                time.sleep(attempt + 1)
    get('fetch_description/package.xml')
    get('fetch_moveit_config/config/fetch.srdf')
    urdf = get('fetch_description/robots/fetch.urdf')
    tree = ET.parse(urdf)
    meshes = sorted({n.get('filename').removeprefix('package://') for n in tree.findall('.//mesh')})
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(get, meshes))
    textures = set()
    for name in meshes:
        if name.endswith('.dae'):
            doc = ET.parse(root / name)
            for node in doc.findall('.//{*}library_images/{*}image/{*}init_from'):
                relative = Path(name).parent / node.text
                if '..' in relative.parts or relative.is_absolute():
                    raise ValueError('Unexpected texture reference')
                textures.add(relative.as_posix())
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(get, sorted(textures)))


def convert(root, output):
    import numpy as np
    import trimesh
    from scipy.spatial import ConvexHull
    from cityg.runtime.articulated_robot import parse_urdf, origin_matrix
    urdf = root / 'fetch_description/robots/fetch.urdf'
    model = parse_urdf(urdf)
    tree = ET.parse(urdf)
    glb = trimesh.Scene(base_frame='robot_model')
    for node in tree.findall('link'):
        name = node.get('name')
        glb.graph.update(frame_to=name, frame_from='robot_model', matrix=np.eye(4))
        for visual in node.findall('visual'):
            mesh = visual.find('geometry/mesh')
            if mesh is None:
                raise ValueError('Unsupported non-mesh visual')
            path = root / mesh.get('filename').removeprefix('package://')
            scene = trimesh.load(path, force='scene', process=False)
            scene.apply_transform(origin_matrix(visual.find('origin')))
            scale = [float(x) for x in mesh.get('scale', '1 1 1').split()]
            if scale != [1., 1., 1.]:
                raise ValueError('Unexpected mesh scaling')
            # Keep Collada textured material. STL has no material; use URDF RGBA.
            color = visual.find('material/color')
            for i, geom_name in enumerate(scene.graph.nodes_geometry):
                transform, geometry = scene.graph[geom_name]
                geom = scene.geometry[geometry].copy()
                geom.apply_transform(transform)
                if path.suffix.lower() == '.stl' and color is not None:
                    geom.visual = trimesh.visual.TextureVisuals(material=trimesh.visual.material.PBRMaterial(
                        baseColorFactor=np.array([float(v) for v in color.get('rgba').split()]),
                        metallicFactor=.1, roughnessFactor=.55))
                glb.add_geometry(geom, node_name=f'{name}__visual_{i}', geom_name=f'{name}__mesh_{i}', parent_node_name=name)
        bounds = []
        hulls = []
        for collision in node.findall('collision'):
            mesh = collision.find('geometry/mesh')
            if mesh is None:
                raise ValueError('Unsupported non-mesh collision')
            geom = trimesh.load(root / mesh.get('filename').removeprefix('package://'), force='mesh', process=False)
            geom.apply_transform(origin_matrix(collision.find('origin')))
            bounds.append(geom.bounds)
            hulls.append(ConvexHull(geom.vertices).equations.tolist())
        model['links'][name]['collision_bounds'] = [b.tolist() for b in bounds]
        model['links'][name]['collision_hulls'] = hulls
    output.mkdir(parents=True, exist_ok=True)
    glb.export(output / 'fetch.glb')
    package = ET.parse(root / 'fetch_description/package.xml')
    model.update({'schema_version': 'cityg.articulated_robot.v1', 'name': 'Fetch',
        'source_url': 'https://github.com/fetchrobotics/fetch_ros', 'revision': REVISION,
        'license_declaration': package.findtext('license'), 'glb': 'fetch.glb',
        'glb_sha256': hashlib.sha256((output / 'fetch.glb').read_bytes()).hexdigest(),
        'coordinate_system': 'right_handed_z_up_meters', 'mesh_scale': 1.0,
        # Contact the upper side of the 110 mm cup: fingertips stay below its
        # rim while the forearm clears tabletop clutter. No mesh scaling.
        'end_effector_link': 'gripper_link', 'grasp_offset': [.015, 0., -.035],
        'source_hashes': {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in sorted((root / 'fetch_description').rglob('*')) if p.is_file()}})
    srdf = root / 'fetch_moveit_config/config/fetch.srdf'
    if srdf.is_file():
        model['disabled_self_collisions'] = [dict(n.attrib) for n in ET.parse(srdf).findall('disable_collisions')]
        model['source_hashes']['fetch_moveit_config/config/fetch.srdf'] = hashlib.sha256(srdf.read_bytes()).hexdigest()
    (output / 'robot.json').write_text(json.dumps(model, indent=2) + '\n')
    (output / 'fetch.urdf').write_bytes(urdf.read_bytes())
    (output / 'package.xml').write_bytes((root / 'fetch_description/package.xml').read_bytes())
    print(json.dumps({'links': len(model['links']), 'joints': len(model['joints']),
                      'glb_bytes': (output / 'fetch.glb').stat().st_size, 'license': model['license_declaration']}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('assets/robots/fetch/official'))
    parser.add_argument('--output', type=Path, default=Path('assets/robots/fetch/prepared'))
    parser.add_argument('--download', action='store_true')
    parser.add_argument('--download-only', action='store_true')
    args = parser.parse_args()
    if args.download or args.download_only:
        download(args.root)
    if not args.download_only:
        convert(args.root, args.output)


if __name__ == '__main__':
    main()
