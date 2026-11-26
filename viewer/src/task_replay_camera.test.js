import {test} from 'node:test';
import assert from 'node:assert/strict';
import {replayCameraPose} from './task_replay_camera.js';

test('rear follow is close, above and behind the robot at any floor and yaw',()=>{
  for(const yaw of [0,45,90,180,-90,270,360]) {
    const base=[17,-22,24.75],a=yaw*Math.PI/180,c=Math.cos(a),s=Math.sin(a);
    const pose=replayCameraPose(base,yaw);
    const delta=pose.position.map((x,i)=>x-base[i]);
    assert.ok(Math.abs(delta[0]*c+delta[1]*s+.8)<1e-10);
    assert.ok(Math.abs(-delta[0]*s+delta[1]*c)<1e-10);
    assert.ok(Math.abs(delta[2]-1.35)<1e-10);
    assert.ok(Math.abs((pose.target[0]-base[0])*c+(pose.target[1]-base[1])*s-1.5)<1e-10);
    assert.ok(pose.position[2]>pose.target[2]);
    assert.deepEqual(base,[17,-22,24.75]);
  }
});

test('legacy side close-up and context presets remain available',()=>{
  assert.deepEqual(replayCameraPose([0,0,0],0,'robot'),{position:[2.4,-2.4,2.2],target:[.3,0,.15]});
  assert.deepEqual(replayCameraPose([0,0,0],0,'context',true),{position:[1.8,-2.4,7],target:[0,0,0]});
  assert.deepEqual(replayCameraPose([0,0,0],0,'context',false),{position:[8,-10,9],target:[0,0,0]});
});
