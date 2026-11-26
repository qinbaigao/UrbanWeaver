import test from 'node:test';
import assert from 'node:assert/strict';
import {bindSharedTexture,disposeOwnedMap} from './texture_bindings.js';
test('rebuilding a material binds cached PBR maps before its first render',async()=>{
  let loads=0,disposals=0;
  const texture={dispose:()=>disposals++};
  const cache={promises:new Map(),ready:new Map(),states:new Map(),owned:new Set(),load:async()=>{loads++;return texture;}};
  const first={map:null},second={map:null};
  bindSharedTexture(cache,'wall.jpg',t=>first.map=t);
  await cache.promises.get('wall.jpg');await Promise.resolve();
  assert.equal(first.map,texture);
  disposeOwnedMap(first,cache.owned);assert.equal(disposals,0);
  bindSharedTexture(cache,'wall.jpg',t=>second.map=t);
  assert.equal(second.map,texture,'no await: the very first draw is already textured');
  assert.equal(loads,1);
  disposeOwnedMap({map:{dispose:()=>disposals++}},cache.owned);assert.equal(disposals,1);
});
