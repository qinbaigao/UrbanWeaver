import test from 'node:test';
import assert from 'node:assert/strict';
import {aerialNearPlane} from './depth_precision.js';
test('aerial depth precision follows orbit height and returns to close clipping at street level',()=>{
  const target={x:500,y:500,z:20};
  const high=aerialNearPlane({x:1700,y:-850,z:1250},target,100,'overview');
  assert.ok(high>30 && high<=64);
  const low=aerialNearPlane({x:500,y:400,z:105},target,100,'overview');
  assert.equal(low,.625);
  assert.equal(aerialNearPlane({x:500,y:400,z:2},target,100,'overview'),.03);
  assert.equal(aerialNearPlane({x:500,y:400,z:2},target,100,'room'),null);
  // Near clipping stays far below vertical clearance, so no building top
  // (including a tall tower below the camera) can be removed by this policy.
  assert.ok(aerialNearPlane({x:500,y:400,z:101},target,100,'full')<1);
});
