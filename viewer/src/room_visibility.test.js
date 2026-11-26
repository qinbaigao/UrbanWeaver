import test from 'node:test';
import assert from 'node:assert/strict';
import { hasRoomBoundaries } from './room_visibility.js';

test('realized room caps allow inspection without accepting stray door headers', () => {
  const room = { function:'bedroom', bounds:{min_x:10,min_y:20,max_x:16,max_y:26} };
  const walls = ['north','south','west','east'].map(side => ({size:{x:1,y:.1},
    metadata:{wall_role:'room_view_cap',room_isolation_cap:true,wall_side:side}}));
  assert.equal(hasRoomBoundaries(room, walls), true);
  assert.equal(hasRoomBoundaries(room, walls.slice(0,3)), false);
  walls[3].metadata.wall_role = 'door_header';
  assert.equal(hasRoomBoundaries(room, walls), false);
  assert.equal(hasRoomBoundaries({...room, metadata:{open_plan:true}}, walls), true);
  assert.equal(hasRoomBoundaries(room, []), false);
});
