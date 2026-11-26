import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const source=readFileSync(new URL('./main.js',import.meta.url),'utf8');
const begin=source.indexOf('  const roomTarget = [...targetIds]');
const code=source.slice(begin,source.indexOf('  if (state.hierarchyDisplay)',begin));
test('explicit non-hero target survives the dropdown filter',()=>{
  const state={heroRoomIds:new Set(['hero']),heroRoomOnly:true,
    data:{hierarchy:{entities:new Map([['plain',{type:'room',floorId:'f',buildingId:'b'}]])}}};
  vm.runInNewContext(code,{state,targetIds:new Set(['plain']),roomHasRealizedWalls:()=>true});
  assert.equal(state.heroRoomOnly,false);
  assert.equal(state.roomId,'plain');
  assert.equal(state.floorId,'f');
});
test('unrenderable targets fail explicitly rather than substituting a room',()=>{
  const state={heroRoomIds:new Set(),data:{hierarchy:{entities:new Map([['bad',{type:'room'}]])}}};
  assert.throws(()=>vm.runInNewContext(code,{state,targetIds:new Set(['bad']),
    roomHasRealizedWalls:()=>false}),/no realizable room boundaries/);
  assert.equal(state.roomId,undefined);
});
