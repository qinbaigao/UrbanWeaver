"""Axis-aligned interior planning frame, independent of exterior orientation.

For a north/south entry, local U follows world Y and local V follows world X.
The transpose is its own inverse. It is used only before furnishing; it is not
a rotation/mirroring API for existing furniture or arbitrary scene metadata.
"""
from copy import deepcopy
from dataclasses import dataclass

from cityg.schemas import Bounds2D, Point2D


def circulation_axis(building):
    return building.metadata.get('interior_layout_contract', {}).get('circulation_axis', 'x')


@dataclass(frozen=True)
class InteriorFrame:
    axis: str = 'x'

    def __post_init__(self):
        if self.axis not in ('x', 'y'):
            raise ValueError('Interior circulation axis must be x or y')

    @classmethod
    def for_entry(cls, side):
        if side not in ('west','east','south','north'):
            raise ValueError('Interior entry must have a cardinal frontage')
        return cls('y' if side in ('north','south') else 'x')

    def point(self, p):
        return Point2D(p.y,p.x) if self.axis=='y' else p

    def bounds(self, b):
        return Bounds2D(b.min_y,b.min_x,b.max_y,b.max_x) if self.axis=='y' else b

    def side(self, side):
        return {'north':'east','south':'west','east':'north','west':'south'}.get(side,side) if self.axis=='y' else side

    def metadata(self, value):
        """Transform typed coordinate records, never implicit numeric arrays."""
        if isinstance(value,dict):
            if set(value)=={'min_x','min_y','max_x','max_y'}:
                from dataclasses import asdict
                return asdict(self.bounds(Bounds2D(**value)))
            if set(value)=={'x','y'}:
                from dataclasses import asdict
                return asdict(self.point(Point2D(**value)))
            return {k:(self.side(v) if k=='corridor_side' else self.metadata(v)) for k,v in value.items()}
        if isinstance(value,list): return [self.metadata(v) for v in value]
        return value

    def floor(self, floor):
        if floor.objects or any(r.object_ids for r in floor.rooms):
            raise ValueError('Interior frame mapping is only for unfurnished planning')
        if self.axis=='x': return floor
        result=deepcopy(floor)
        for room in result.rooms:
            room.bounds=self.bounds(room.bounds)
            room.metadata=self.metadata(room.metadata)
        for door in result.doors: door.position=self.point(door.position)
        result.metadata=self.metadata(result.metadata)
        result.metadata['circulation_axis']=self.axis
        result.metadata['interior_coordinate_frame']='world_xy; solver_u=world_y, solver_v=world_x'
        return result
