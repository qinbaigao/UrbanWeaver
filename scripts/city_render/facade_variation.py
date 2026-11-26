"""Deterministic identity-bound variations for private render materials."""
import hashlib

FACADE_SEMANTICS = frozenset({
    'exterior_wall', 'facade_window', 'curtain_wall_glass', 'storefront_window',
    'window_backing', 'facade_frame', 'roof_parapet', 'facade_ground_band',
    'facade_zone_band', 'facade_language_detail',
})


def stable_fraction(key):
    return int.from_bytes(hashlib.sha256(key.encode()).digest()[:4], 'big') / 2**32


def facade_seeds(primitive):
    building = primitive['layer_id'].removeprefix('shell:')
    panel = primitive['id'].removesuffix('_frame').removesuffix('_backing')
    return stable_fraction(panel), stable_fraction(building)
