"""Opt-in room finish surfaces in realized geometry; no architectural changes."""
from dataclasses import replace
import math

from cityg.geometry.model import MaterialSpec, Vec3
from cityg.planning.room_envelope import metric_envelope


def apply_room_finishes(compiler, building, floor, room, scene, walls):
    spec = room.metadata.get('room_finishes')
    if not spec:
        return
    if set(spec) != {'floor', 'wall'}:
        raise ValueError('Room finishes require floor and wall material IDs')
    library = getattr(compiler, 'material_library', None)
    for material_id in spec.values():
        record = library.get(material_id) if library else None
        if record is None:
            raise ValueError(f'Missing room finish material: {material_id}')
        paths = {}
        for channel in ('base_color','normal','roughness','ambient_occlusion'):
            path = getattr(record,channel+'_path')
            if path:
                path = library.resolve_path(path).resolve()
                if not path.is_file():raise ValueError(f'Missing room finish texture: {path}')
                paths[channel+'_path'] = str(path)
        if not paths.get('base_color_path') or not record.texture_scale_m or record.texture_scale_m <= 0:
            raise ValueError('Room finish needs base color and positive real-world tiling scale')
        if material_id not in {m.id for m in scene.materials}:
            scene.materials.append(MaterialSpec(material_id,record.display_color,roughness=record.roughness,
                metallic=record.metallic,texture_scale_m=record.texture_scale_m,
                source=record.source,license_id=record.license_id,**paths))
    envelope = metric_envelope(building,floor,room)
    if envelope['status'] != 'supported':
        raise ValueError('Room finishes require a supported realized room envelope')
    bounds = envelope['bounds']; rotation = float(building.metadata.get('orientation_deg',0))
    angle = math.radians(rotation); c,s=math.cos(angle),math.sin(angle)
    bx,by=building.footprint.center.x,building.footprint.center.y
    dx,dy=bounds.center.x-bx,bounds.center.y-by
    cx,cy=bx+c*dx-s*dy,by+s*dx+c*dy
    # Top at the furniture's physical zero plane, not above its legs.
    scene.primitives.append(compiler._box(f'{room.id}_floor_finish',room.id,
        Vec3(cx,cy,floor.elevation_m-.004),Vec3(bounds.width,bounds.depth,.008),rotation,
        'room_decoration',spec['floor'],f'floor:{floor.id}',collision_enabled=False,
        metadata={'room_ids':[room.id],'room_floor_finish':True,'visual_only':True}))
    for wall in walls:
        if wall.metadata.get('room_ids') == [room.id]:
            wall.material_id = spec['wall']
            continue
        # Shared wall: texture only this room's side, never recolor its neighbor.
        a=math.radians(wall.rotation_z_deg)
        horizontal=wall.size.x>wall.size.y
        nx,ny=(-math.sin(a),math.cos(a)) if horizontal else (math.cos(a),math.sin(a))
        sign=1 if (cx-wall.center.x)*nx+(cy-wall.center.y)*ny>=0 else -1
        offset=min(wall.size.x,wall.size.y)/2+.0015
        panel=replace(wall,id=f'{wall.id}_{room.id}_finish',owner_id=room.id,
            center=Vec3(wall.center.x+sign*nx*offset,wall.center.y+sign*ny*offset,wall.center.z),
            size=Vec3(wall.size.x,.003,wall.size.z) if horizontal else Vec3(.003,wall.size.y,wall.size.z),
            material_id=spec['wall'],collision_enabled=False,
            metadata={**wall.metadata,'room_ids':[room.id],'visual_only':True,'room_wall_finish':True})
        scene.primitives.append(panel)
    scene.metadata.setdefault('room_finishes',{})[room.id] = dict(spec)
