import test from 'node:test';
import assert from 'node:assert/strict';
import {snapshotSize, canvasPng} from './snapshot.js';

test('snapshot preserves landscape and portrait composition', () => {
  assert.deepEqual(snapshotSize(1200, 800), {width:2560, height:1707});
  assert.deepEqual(snapshotSize(800, 1200), {width:1707, height:2560});
  assert.deepEqual(snapshotSize(800, 800, 3840), {width:2896, height:2896});
  assert.deepEqual(snapshotSize(1200, 800, 2560, 1024), {width:1024, height:683});
  assert.throws(() => snapshotSize(0, 800));
  assert.throws(() => snapshotSize(1200, 800, Infinity));
});
test('PNG encoder rejects a missing output instead of reporting a successful save', async () => {
  await assert.rejects(canvasPng({toBlob: callback => callback(null)}), /encoding failed/);
  const blob = new Blob(['png'], {type:'image/png'});
  assert.equal(await canvasPng({toBlob: callback => callback(blob)}), blob);
});
