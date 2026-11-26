"""Bake cumulative XY bounds from canonical tree triangles for pedestrian checks."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

import numpy as np
import trimesh


def bake(path):
    with path.open("rb") as f:
        magic, version, _, size, kind = struct.unpack("<4sIIII", f.read(20))
        if (magic, version, kind) != (b"glTF", 2, 0x4E4F534A):
            raise ValueError(f"Expected GLB 2.0: {path}")
        doc = json.loads(f.read(size))
        if not doc["asset"].get("extras", {}).get("cityg_canonicalized"):
            raise ValueError(f"Expected CityG canonical coordinates: {path}")
        f.seek(0)
        digest = hashlib.sha256()
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    scene = trimesh.load(path, force="scene", process=False, skip_materials=True)
    # Clip crossing edges at each height so long diagonal branches do not
    # contribute their elevated tips to a lower pedestrian footprint.
    cuts = np.arange(1, 17) / 16
    lo = np.full((16, 2), np.inf)
    hi = -lo.copy()
    z_low, z_high = np.inf, -np.inf
    for node in scene.graph.nodes_geometry:
        transform, key = scene.graph[node]
        mesh = scene.geometry[key]
        xyz = trimesh.transform_points(mesh.vertices, transform)
        for begin in range(0, len(mesh.faces), 65536):
            tri = xyz[mesh.faces[begin:begin + 65536]]
            base = tri.min(axis=1)[:, 2]
            top = tri.max(axis=1)[:, 2]
            z_low = min(z_low, base.min())
            z_high = max(z_high, top.max())
            for i, cut in enumerate(cuts - .5):
                contained = tri[top <= cut, :, :2].reshape(-1, 2)
                crossing = tri[(base <= cut) & (cut < top)]
                points = [contained, crossing[:, :, :2][crossing[:, :, 2] <= cut]]
                for j in range(3):
                    a, b = crossing[:, j], crossing[:, (j + 1) % 3]
                    hit = (a[:, 2] <= cut) != (b[:, 2] <= cut)
                    a, b = a[hit], b[hit]
                    t = (cut - a[:, 2]) / (b[:, 2] - a[:, 2])
                    points.append(a[:, :2] + t[:, None] * (b[:, :2] - a[:, :2]))
                for xy in points:
                    if len(xy):
                        lo[i] = np.minimum(lo[i], xy.min(axis=0))
                        hi[i] = np.maximum(hi[i], xy.max(axis=0))
    lo = np.floor(np.minimum.accumulate(lo, axis=0) * 1e5) / 1e5
    hi = np.ceil(np.maximum.accumulate(hi, axis=0) * 1e5) / 1e5
    if not np.isfinite(lo[0]).all() or not np.isfinite(hi[0]).all():
        raise ValueError(f"No triangles near normalized base: {path}")
    if z_low < -.501 or z_high > .501 or lo[-1].min() < -.501 or hi[-1].max() > .501:
        raise ValueError(f"Rendered triangles exceed the canonical unit envelope: {path}")
    return {"sha256": digest.hexdigest(), "bounds": np.column_stack((lo, hi)).tolist()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("assets", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    data = {path.name: bake(path) for path in sorted(args.assets)}
    args.output.write_text(json.dumps(data, separators=(",", ":")) + "\n")
