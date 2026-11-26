"""Axis-aligned slab subtraction; keep support between separate shafts."""
from cityg.schemas import Bounds2D


def subtract_openings(outer,holes):
    pieces=[outer]
    for h in holes:
        result=[]
        for b in pieces:
            x0,x1=max(b.min_x,h.min_x),min(b.max_x,h.max_x)
            y0,y1=max(b.min_y,h.min_y),min(b.max_y,h.max_y)
            if x1<=x0 or y1<=y0:result.append(b);continue
            candidates=[(b.min_x,b.min_y,x0,b.max_y),(x1,b.min_y,b.max_x,b.max_y),
                (x0,b.min_y,x1,y0),(x0,y1,x1,b.max_y)]
            result.extend(Bounds2D(*r) for r in candidates if r[2]-r[0]>1e-7 and r[3]-r[1]>1e-7)
        pieces=result
    return pieces


def transport_slab_holes(building,floor):
    return [c.bounds for c in building.vertical_connectors
        if c.from_level<=floor.level<=c.to_level and (floor.level>c.from_level
            or c.metadata.get('transport_elevator_version')==1)]
