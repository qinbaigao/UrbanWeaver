"""Flat parking outlines; no filled surface or raised parking platform."""
from math import hypot


def outline_mesh(corners, *, line_width=0.10, z=0.002):
    """Return vertices/triangles for an inset outline of a CCW rectangle.

    The open middle leaves the underlying asphalt visible. Coordinates may be
    local or world-space; all paint is 2 mm above the road by default.
    """
    if len(corners) != 4:
        raise ValueError('Parking outline requires four rectangle corners')
    outer = [(float(x), float(y), z) for x, y in corners]
    inner = []
    for i, (x, y) in enumerate(corners):
        dx = dy = 0.0
        for j in ((i - 1) % 4, (i + 1) % 4):
            vx, vy = corners[j][0] - x, corners[j][1] - y
            length = hypot(vx, vy)
            if not 0 < line_width < length / 2:
                raise ValueError('Paint width must be smaller than half each edge')
            dx += vx / length * line_width
            dy += vy / length * line_width
        inner.append((x + dx, y + dy, z))
    faces = []
    for i in range(4):
        j = (i + 1) % 4
        faces.extend(((i, j, j + 4), (i, j + 4, i + 4)))
    return outer + inner, faces
