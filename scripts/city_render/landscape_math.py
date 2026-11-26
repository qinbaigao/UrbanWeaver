"""Pure helpers for bounded offline backdrop geometry."""
import math


def top_ray_vertical(camera):
    # Column-major Viewer matrix; top-centre local ray is (0, tan(vfov/2), -1).
    tangent = math.tan(math.radians(camera['vertical_fov_deg']) / 2)
    matrix = camera['matrix_world']
    return (matrix[6]*tangent-matrix[10]) / math.sqrt(1+tangent*tangent)


def outside_distance(x, y, bounds):
    x0, x1, y0, y1 = bounds
    return math.hypot(max(x0-x, 0, x-x1), max(y0-y, 0, y-y1))


def backdrop_height(x, y, bounds):
    distance = outside_distance(x, y, bounds)
    blend = min(1, max(0, (distance-120)/550))
    blend = blend*blend*(3-2*blend)
    hills = 22 + 15*math.sin(x/330)*math.cos(y/410) + 9*math.sin((x+y)/180)
    return -8 + blend*hills
