// Keep the room selector aligned with the backend's realized observation frame.
export function hasRoomBoundaries(room, walls) {
  if (!walls.length) return false;
  if (room.function === 'corridor' || room.metadata?.open_plan === true
      || room.metadata?.space_kind === 'open_plan') return true;
  if (!room.bounds) return false;
  const has = (value, horizontal, side) => walls.some((wall) => {
    const meta = wall.metadata || {};
    if (meta.wall_role === 'room_view_cap' && meta.room_isolation_cap === true
        && meta.wall_side === side) return true;
    return typeof meta.canonical_boundary === 'number'
      && Math.abs(meta.canonical_boundary - value) <= 1e-3
      && (horizontal ? wall.size.x >= wall.size.y : wall.size.y >= wall.size.x);
  });
  const b = room.bounds;
  return has(b.min_y, true, 'south') && has(b.max_y, true, 'north')
    && has(b.min_x, false, 'west') && has(b.max_x, false, 'east');
}
