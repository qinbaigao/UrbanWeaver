"""Height-dependent XY bounds baked from reviewed, canonical GLBs."""
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path


PEDESTRIAN_RADIUS = 0.25
# CityG street surfaces are flat and may sit up to 0.25 m above ground.
PEDESTRIAN_HEAD_Z = 0.25 + 1.80


@lru_cache(maxsize=1)
def _profiles():
    return json.loads(Path(__file__).with_name("pedestrian_tree_profiles.json").read_text())


@lru_cache(maxsize=128)
def _digest(path, size, mtime_ns, ctime_ns):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_bounds(path, center_z, height, head_z=PEDESTRIAN_HEAD_Z):
    """Return canonical XY bounds, or None to retain the full asset envelope."""
    path = Path(path or "")
    if not path.is_file() or height <= 0:
        return None
    try:
        stat = path.stat()
        digest = _digest(path, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
    except OSError:
        return None
    profile = next((p for p in _profiles().values() if p["sha256"] == digest), None)
    if profile is None:
        return None
    fraction = (head_z - center_z) / height + .5
    bands = profile["bounds"]
    index = max(0, min(len(bands) - 1, math.ceil(fraction * len(bands)) - 1))
    return bands[index]


def tree_placement_radius(parts, anchor):
    """Enclose the planted instance at walking height, including off-center trunks."""
    radius = 0.
    for p in parts:
        if p.center.z - p.size.z / 2 > PEDESTRIAN_HEAD_Z:
            continue
        bounds = tree_bounds(p.metadata.get("asset_geometry_path"), p.center.z, p.size.z)
        x0, y0, x1, y1 = bounds or (-.5, -.5, .5, .5)
        extent = math.hypot(max(abs(x0), abs(x1)) * p.size.x,
                            max(abs(y0), abs(y1)) * p.size.y)
        radius = max(radius, extent + math.hypot(p.center.x - anchor.x, p.center.y - anchor.y))
    return radius
