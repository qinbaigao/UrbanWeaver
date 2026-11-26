"""Door leaf fit and hinge convention shared by compiler, USD and runtime.

The opening is not the moving leaf. Fit only after massing conformance; keep
the original opening for navigation and leave its walls/header untouched.
Legacy manifests without an explicit hinge retain their original motion.
"""
from dataclasses import replace
import math

from cityg.geometry.model import Vec3


def local_hinge(size, metadata=None):
    explicit = (metadata or {}).get('hinge_local_m')
    if explicit is None:
        return (-size[0]/2, 0., 0.) if size[0] >= size[1] else (0., -size[1]/2, 0.)
    if (len(explicit) != 3 or not all(math.isfinite(v) for v in explicit)
            or abs(explicit[2]) > 1e-9
            or any(abs(explicit[i]) > size[i]/2+1e-9 for i in range(2))):
        raise ValueError('Door hinge must lie on/in the leaf XY bounds at local Z=0')
    return tuple(explicit)


def fit_door_leaf(primitive, *, gap_m=.008, thickness_m=.04):
    """Return a new leaf, preserving identity and the realized opening.

    Positive-Z swing pivots at the swing-side corner of the near leaf edge.
    Clearance covers the far-corner sweep as well as the closed pose. This is
    a fit policy, not certification: nearby obstacles still require auditing.
    """
    if primitive.semantic_class != 'door' or primitive.primitive_type != 'box':
        raise ValueError('Only rectangular door leaves can be fitted')
    if primitive.metadata.get('door_fit_version') == 'corner_hinge_v1':
        return primitive
    size = (primitive.size.x, primitive.size.y, primitive.size.z)
    if (not all(math.isfinite(v) and v > 0 for v in (*size, gap_m, thickness_m))
            or 2*gap_m >= min(max(size[:2]), size[2])):
        raise ValueError('Invalid door fit dimensions')
    horizontal = size[0] >= size[1]
    width = max(size[:2])-2*gap_m
    thickness = min(min(size[:2]), thickness_m)
    fitted = (width, thickness, size[2]-2*gap_m) if horizontal else (thickness, width, size[2]-2*gap_m)
    hinge = (-width/2, thickness/2, 0.) if horizontal else (-thickness/2, -width/2, 0.)
    return replace(primitive, size=Vec3(*fitted), metadata={**primitive.metadata,
        'door_fit_version': 'corner_hinge_v1', 'hinge_local_m': list(hinge),
        'aperture_size_m': list(size), 'leaf_clearance_m': gap_m,
        'leaf_thickness_m': thickness})
