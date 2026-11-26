import {test} from 'node:test';
import assert from 'node:assert/strict';
import {frameAt} from './task_replay.js';
test('replay seeks the preceding actual checked frame, never invented interpolation',()=>{
  const frames=[{time_s:0},{time_s:.1},{time_s:.2}];
  assert.equal(frameAt(frames,-1),frames[0]);
  assert.equal(frameAt(frames,.15),frames[1]);
  assert.equal(frameAt(frames,10),frames[2]);
});
