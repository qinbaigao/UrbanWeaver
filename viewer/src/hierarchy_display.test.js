import test from 'node:test';
import assert from 'node:assert/strict';
import {validateHierarchyDisplay, hierarchyShell, hierarchyVisible} from './hierarchy_display.js';
const entities = new Map([['b', {type:'building'}], ['f', {type:'floor', buildingId:'b'}],
  ['g', {type:'floor', buildingId:'other'}]]);
const display = validateHierarchyDisplay({building_id:'b', floor_id:'f'}, entities);
test('rejects absent and cross-building bindings and invalid display parameters', () => {
  for (const value of [{building_id:'b', floor_id:'g'}, {building_id:'missing', floor_id:'f'},
    {building_id:'b', floor_id:'f', shell_opacity:2}, {building_id:'b', floor_id:'f', cut_above_m:NaN}]) {
    assert.throws(() => validateHierarchyDisplay(value, entities));
  }
  assert.equal(validateHierarchyDisplay(null, entities), null);
});
test('only selected shell becomes transparent; furniture stays opaque', () => {
  assert.equal(hierarchyShell(display, {buildingId:'b'}, 'building_shell'), true);
  assert.equal(hierarchyShell(display, {buildingId:'other'}, 'building_shell'), false);
  assert.equal(hierarchyShell(display, {buildingId:'b'}, 'floor'), false);
});
test('retains whole city context but only requested floor interiors', () => {
  assert.equal(hierarchyVisible(display, {buildingId:'other'}, 'building_shell', false), true);
  assert.equal(hierarchyVisible(display, null, 'roads', false), true);
  assert.equal(hierarchyVisible(display, {buildingId:'b'}, 'floor', true), true);
  assert.equal(hierarchyVisible(display, {buildingId:'b'}, 'floor', false), false);
  assert.equal(hierarchyVisible(display, {buildingId:'other'}, 'floor', true), false);
});
