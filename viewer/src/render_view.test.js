import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from 'three';
import {renderViewDocument, renderViewFilename} from './render_view.js';

function fixture(aspect = 1.5) {
  const camera = new THREE.PerspectiveCamera(62, aspect, .03, 400);
  camera.position.set(68.18, 919.91, 4.7); camera.up.set(0, 0, 1);
  const target = new THREE.Vector3(64.58, 923.16, 4);
  camera.lookAt(target); camera.zoom = 1.2; camera.updateProjectionMatrix();
  return {camera, target, viewport: {width:1200, height:1200/aspect, bufferWidth:2400, bufferHeight:2400/aspect},
    sceneRef: {city_id:'city', original_source:'/outputs/v03/scene'},
    selection: {building_id:'b', floor_id:'f', room_id:'r'},
    visibility: {mode:'room', room_camera_preset:'cutaway', enabled_semantics:['door']},
    lighting: {room_lighting:'soft'}, createdAt:'2026-10-19T12:00:00.000Z'};
}
test('preserves exact world orientation, vertical FOV, clipping and portrait aspect', () => {
  for (const aspect of [1.5, .75]) {
    const input=fixture(aspect), before=input.camera.position.clone();
    const doc=renderViewDocument(input);
    assert.equal(doc.camera.aspect, aspect);
    assert.equal(doc.camera.vertical_fov_deg, input.camera.getEffectiveFOV());
    assert.deepEqual(doc.camera.quaternion_xyzw, input.camera.quaternion.toArray());
    assert.deepEqual(doc.camera.matrix_world, input.camera.matrixWorld.toArray());
    assert.equal(doc.camera.near_clip_m, .03);
    assert.deepEqual(input.camera.position, before);
    assert.equal(doc.coordinate_system.up_axis, 'Z');
    assert.equal(doc.scene_ref.original_source, '/outputs/v03/scene');
  }
});
test('export is detached from later filters and carries the selected scope', () => {
  const input=fixture(), doc=renderViewDocument(input);
  input.visibility.enabled_semantics.push('wall');
  assert.deepEqual(doc.visibility.enabled_semantics,['door']);
  assert.equal(doc.selection.room_id,'r');
  assert.equal(doc.visibility.room_camera_preset,'cutaway');
  assert.match(renderViewFilename(doc), /city_r_.*_render_view.json$/);
  doc.scene_ref.city_id='../bad/name';
  assert.ok(!renderViewFilename(doc).includes('/'));
});
test('rejects missing canvas dimensions and unsupported cameras', () => {
  const input=fixture();input.viewport.width=0;
  assert.throws(()=>renderViewDocument(input), /zero-sized/);
  input.camera=new THREE.OrthographicCamera();
  assert.throws(()=>renderViewDocument(input), /perspective/);
});
test('city aerial export preserves large-scale framing and ignores stale room selection in filename', () => {
  for (const mode of ['overview', 'full']) {
    const input=fixture(16/9);
    input.camera.position.set(1400,-800,1200);
    input.target.set(600,500,0);
    input.camera.far=10000;
    input.camera.lookAt(input.target);input.camera.updateProjectionMatrix();
    input.visibility.mode=mode;
    input.lighting.sky_preset='daylight';input.lighting.sky_rotation_deg=37;
    input.camera.updateMatrixWorld(true);
    const position=input.camera.position.clone();
    const doc=renderViewDocument(input);
    assert.deepEqual(doc.camera.camera_position,[1400,-800,1200]);
    assert.deepEqual(doc.camera.look_at,[600,500,0]);
    assert.equal(doc.camera.far_clip_m,10000);
    assert.equal(doc.camera.aspect,16/9);
    assert.equal(doc.lighting.sky_rotation_deg,37);
    assert.deepEqual(input.camera.position,position);
    assert.match(renderViewFilename(doc),new RegExp(`city_${mode}_.*_render_view.json$`));
  }
});
