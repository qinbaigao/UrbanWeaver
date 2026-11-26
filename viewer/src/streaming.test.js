import test from 'node:test';
import assert from 'node:assert/strict';
import { ProgressiveGeometry, selectDetailChunks } from './streaming.js';

const chunk = (file, scope = 'building', scope_id = file) => ({file, scope, scope_id, count: 1,
  bytes: 32, bounds: [-10, -10, 10, 10], owner_ids: [scope_id]});

test('HQ viewport snapshots keep aerial LOD and only request the selected local scope', () => {
  const manifest = {chunks:[chunk('a'), chunk('b')]};
  const base = {profile:'snapshot', mode:'overview', camera:{x:0,y:0,z:1000}, focus:{x:0,y:0,z:0}};
  assert.deepEqual(selectDetailChunks(manifest, base), []);
  assert.deepEqual(selectDetailChunks(manifest, {...base, mode:'room', buildingId:'a'}), [manifest.chunks[0]]);
});

test('details replace overview IDs, navigation retains overview, cached revisit', async () => {
  const commits = [], calls = [];
  const overview = [{id: 'a', lod: true}, {id: 'b'}];
  const stream = new ProgressiveGeometry({}, overview, async (file) => {
    calls.push(file); return {primitives: [{id: 'a', detail: true}]};
  }, (p) => commits.push(p));
  await stream.request([chunk('one')]);
  assert.deepEqual(commits.at(-1), [{id:'b'}, {id:'a', detail:true}]);
  await stream.request([]);
  assert.deepEqual(commits.at(-1), overview);
  await stream.request([chunk('one')]);
  assert.equal(calls.length, 1);
  assert.equal(stream.status.ready, true);
});

test('stale responses never overwrite a newer view, even if fetch ignores abort', async () => {
  let resolveOld;
  const commits = [];
  const stream = new ProgressiveGeometry({}, [], (file) => file === 'old'
    ? new Promise((resolve) => { resolveOld = resolve; })
    : Promise.resolve({primitives: [{id: 'new'}]}), (p) => commits.push(p));
  const old = stream.request([chunk('old')]);
  await stream.request([chunk('new')]);
  resolveOld({primitives: [{id: 'old'}]});
  await old;
  assert.deepEqual(commits, [[{id:'new'}]]);
  assert.equal(stream.status.ready, true);
});

test('failure is explicit, not an asset-ready success or partial commit', async () => {
  let commits = 0;
  const stream = new ProgressiveGeometry({}, [], async () => { throw Error('404'); }, () => commits++);
  await stream.request([chunk('missing')]);
  assert.equal(stream.status.ready, false);
  assert.equal(stream.status.failed, 1);
  assert.equal(commits, 0);
  await stream.request([]);
  assert.equal(stream.status.ready, true);
});

test('chunk count mismatch cannot pass barrier', async () => {
  const stream = new ProgressiveGeometry({}, [], async () => ({primitives:[]}), () => {});
  await stream.request([chunk('bad')]);
  assert.equal(stream.status.failed, 1);
});

test('aerial is overview, explicit building gets all chunks, navigation fetches none', () => {
  const manifest = {chunks: [chunk('part1','building','b'), chunk('part2','building','b'), chunk('tile','tile','t')]};
  const options = {profile:'presentation', mode:'overview', camera:{x:0,y:0,z:1000}, focus:{x:0,y:0}};
  assert.equal(selectDetailChunks(manifest, options).length, 0);
  assert.equal(selectDetailChunks(manifest, {...options, targets:['b']}).length, 2);
  assert.equal(selectDetailChunks(manifest, {...options, kind:'global', targets:['b','t']}).length, 0);
  assert.equal(selectDetailChunks(manifest, {...options, kind:'global', mode:'building', buildingId:'b'}).length, 2);
  assert.equal(selectDetailChunks(manifest, {...options, profile:'navigation', targets:['b']}).length, 0);
  assert.equal(selectDetailChunks(manifest, {...options, camera:{x:0,y:0,z:2}}).length, 3);
  assert.equal(selectDetailChunks(manifest, {...options, profile:'paper_capture', kind:'global'}).length, 3);
  assert.equal(selectDetailChunks(manifest, {...options, profile:'paper_capture', mode:'floor_plan', buildingId:'b'}).length, 2);
});
