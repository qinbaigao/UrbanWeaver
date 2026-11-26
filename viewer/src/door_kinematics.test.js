import test from 'node:test';
import assert from 'node:assert/strict';
import {doorPose} from './door_kinematics.js';

const near = (a, b) => assert.ok(Math.abs(a - b) < 1e-10, `${a} != ${b}`);
test('legacy long Y and long X doors use their actual width axis', () => {
  const p = {center: {x: 0, y: 0, z: 1.075}, size: {x: .08, y: .9, z: 2.15}};
  let pose = doorPose(p, 90);
  near(pose.x, -.45); near(pose.y, -.45);
  pose = doorPose({...p, size: {x: .9, y: .08, z: 2.15}}, 90);
  near(pose.x, -.45); near(pose.y, .45);
});
test('explicit corner hinge stays fixed throughout the swing in rotated buildings', () => {
  for (const horizontal of [false, true]) for (const yaw of [0, 37, 90, 180]) {
    const h = horizontal ? [-.442, .02, 0] : [-.02, -.442, 0];
    const p = {center: {x: 10, y: 20, z: 1.075}, rotation_z_deg: yaw,
      size: horizontal ? {x: .884, y: .04, z: 2.134} : {x: .04, y: .884, z: 2.134},
      metadata: {hinge_local_m: h}};
    const a = yaw * Math.PI / 180;
    for (let degrees = 0; degrees <= 90; degrees++) {
      const pose = doorPose(p, degrees);
      near(pose.x + Math.cos(pose.angle) * h[0] - Math.sin(pose.angle) * h[1],
        10 + Math.cos(a) * h[0] - Math.sin(a) * h[1]);
      near(pose.y + Math.sin(pose.angle) * h[0] + Math.cos(pose.angle) * h[1],
        20 + Math.sin(a) * h[0] + Math.cos(a) * h[1]);
    }
  }
});
test('invalid hinge does not silently render a different motion', () => {
  assert.throws(() => doorPose({center: {x: 0, y: 0, z: 0}, size: {x: .04, y: .9, z: 2},
    metadata: {hinge_local_m: [-.5, 0, 0]}}, 90));
});
