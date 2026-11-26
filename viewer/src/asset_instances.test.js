import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from 'three';
import { instanceAsset, matchesLocalAssetTarget } from './asset_instances.js';

test('context ancestors do not expand a local review to every city GLB', () => {
  const entities = new Map([['city', {type:'city'}], ['district', {type:'district'}], ['building', {type:'building'}]]);
  const lineage = new Set(['city', 'district', 'building', 'asset']);
  assert.equal(matchesLocalAssetTarget(lineage, ['park', 'city'], entities), false);
  assert.equal(matchesLocalAssetTarget(lineage, ['district'], entities), false);
  assert.equal(matchesLocalAssetTarget(lineage, ['building', 'city'], entities), true);
  assert.equal(matchesLocalAssetTarget(new Set(['park']), ['park', 'city'], entities), true);
  assert.equal(matchesLocalAssetTarget(new Set(['city']), ['park', 'city'], entities, {landscape_site:'park'}), true);
  assert.equal(matchesLocalAssetTarget(new Set(['city']), ['park', 'city'], entities, {landscape_site:'other_park'}), false);
});

test('GLB child transforms, materials and picking identities survive batching', () => {
  const root = new THREE.Group();
  root.position.set(100, 20, 30);
  const parent = new THREE.Group(); parent.rotation.z = Math.PI/2; root.add(parent);
  const node = new THREE.Mesh(new THREE.BoxGeometry(), new THREE.MeshStandardMaterial());
  node.position.set(2, 0, 0); parent.add(node);
  const entries = [{id:'a'}, {id:'b'}];
  const meshes = instanceAsset(root, entries, () => new THREE.Matrix4().makeTranslation(10, 0, 0));
  const matrix = new THREE.Matrix4(); meshes[0].getMatrixAt(0, matrix);
  const p = new THREE.Vector3().setFromMatrixPosition(matrix);
  assert.ok(p.distanceTo(new THREE.Vector3(10, 2, 0)) < 1e-6);
  assert.equal(meshes[0].geometry, node.geometry);
  assert.equal(meshes[0].material, node.material);
  assert.equal(meshes[0].userData.entries, entries);
  assert.equal(meshes[0].count, 2);
});

test('skinned assets retain clone fallback', () => {
  const root = new THREE.Group(); root.add(new THREE.SkinnedMesh());
  assert.equal(instanceAsset(root, [{id:'a'}], () => new THREE.Matrix4()), null);
});

test('authored root tilt is not lost and hidden child meshes stay hidden', () => {
  const root = new THREE.Group();
  const visible = new THREE.Mesh(new THREE.BoxGeometry(), new THREE.MeshBasicMaterial());
  const hidden = visible.clone(); hidden.visible = false; root.add(visible, hidden);
  assert.equal(instanceAsset(root, [{id:'a'}], () => new THREE.Matrix4()).length, 1);
  root.rotation.x = Math.PI/2;
  assert.equal(instanceAsset(root, [{id:'a'}], () => new THREE.Matrix4()), null);
});
