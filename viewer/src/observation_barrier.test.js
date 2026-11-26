import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

// Exercise the actual browser functions with renderer-independent stubs.
const source=readFileSync(new URL('./main.js',import.meta.url),'utf8');
const functions=source.slice(source.indexOf('function observationAssetStatus()'),
  source.indexOf('function captureObservationFrame()'));
function context() {
  const direction={sub(){return this;},normalize(){return this;},toArray(){return [0,0,1];}};
  const value={Promise,setTimeout,performance,Map,Set,
    state:{renderProfile:'navigation',assetRenderGeneration:7,
      assetLoadState:{generation:0,ready:true,pending:0,failed:0},assetReadyPromise:Promise.resolve(),
      materialTextureUrls:new Set(),visiblePrimitives:[],skyPreset:'none',skyRotation:0},
    RENDER_PROFILES:{navigation:{environment:false,materialTextures:false,physicalGlass:false}},
    scene:{},renderer:{shadowMap:{enabled:false},info:{memory:{},render:{}}},screenLodStats:{},
    assetTemplates:{stats:()=>({})},
    sun:{position:{clone:()=>direction},target:{position:{}}},desiredEnvironment:()=>({}),
    textureLoadStates:new Map(),textureCache:new Map(),environmentPromise:Promise.resolve()};
  vm.createContext(value);vm.runInContext(functions,value);return value;
}

test('navigation barrier uses current render generation without a GLB batch',async()=>{
  const c=context();assert.equal(c.observationAssetStatus().generation,7);
  const status=await c.waitForObservationAssets({quiet_ms:0,timeout_ms:100});
  assert.equal(status.ready,true);assert.equal(status.timed_out,false);
});

test('stale completed promises yield to timers instead of spinning microtasks',async()=>{
  const c=context();let timerRan=false;
  c.observationAssetStatus=()=>({generation:0,ready:false,pending:0,failed:0});
  setTimeout(()=>{timerRan=true;},1);
  const status=await c.waitForObservationAssets({quiet_ms:0,timeout_ms:100});
  assert.equal(status.timed_out,true);assert.equal(timerRan,true);
});
