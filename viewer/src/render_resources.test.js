import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from 'three';
import {AssetTemplatePool, disposeInstances, disposeTemplate, runAssetBatches, displayPixelRatio,
  textureEdgeForPixels, resizeTemplateTextures, canPresent} from './render_resources.js';

const model = () => new THREE.Mesh(new THREE.BoxGeometry(),new THREE.MeshStandardMaterial());
test('instance disposal releases per-batch buffers but not shared GLB data', () => {
  const root = new THREE.Group(), source = model();
  const batch = new THREE.InstancedMesh(source.geometry, source.material, 10); root.add(batch);
  let disposed = 0, geometry = 0, material = 0;
  batch.addEventListener('dispose',()=>disposed++);
  source.geometry.addEventListener('dispose',()=>geometry++);
  source.material.addEventListener('dispose',()=>material++);
  disposeInstances(root);
  assert.deepEqual([disposed,geometry,material],[1,0,0]);
  disposeTemplate(source); assert.deepEqual([geometry,material],[1,1]);
});
test('template pool deduplicates loading, limits decoding, and evicts idle resources', async () => {
  let running=0, maximum=0, loads=0, disposed=0;
  const pool = new AssetTemplatePool(async () => {
    running++; maximum=Math.max(maximum,running); loads++;
    await new Promise(resolve=>setTimeout(resolve,4)); running--;
    const root=model(); root.geometry.addEventListener('dispose',()=>disposed++); return root;
  },{concurrency:2,idleBytes:0});
  pool.retain(['a','b','c']);
  const a=pool.get('a'); assert.equal(a,pool.get('a'));
  await Promise.all([a,pool.get('b'),pool.get('c')]);
  assert.equal(loads,3); assert.equal(maximum,2);
  pool.retain(['b']); assert.equal(disposed,2); assert.equal(pool.entries.size,1);
  pool.clear(); assert.equal(disposed,3);
});
test('queued obsolete loads never decode and failed loads can retry', async () => {
  const loaded=[];
  const pool=new AssetTemplatePool(async key=>{
    loaded.push(key); await new Promise(resolve=>setTimeout(resolve,4));
    if(key==='bad') throw new Error('bad'); return model();
  },{concurrency:1});
  pool.retain(['a','stale']);
  const a=pool.get('a'), stale=assert.rejects(pool.get('stale'),/Obsolete/);
  pool.retain(['a']); await Promise.all([a,stale]); assert.deepEqual(loaded,['a']);
  pool.retain(['bad']); await assert.rejects(pool.get('bad'),/bad/);
  await assert.rejects(pool.get('bad'),/bad/); assert.equal(loaded.filter(k=>k==='bad').length,2);
});
test('batch scheduling yields and stops obsolete camera work', async () => {
  let current=true, timer=false, done=0;
  setTimeout(()=>{timer=true;current=false;},0);
  await runAssetBatches(Array(100).fill(0),async()=>{done++;},()=>current,2);
  assert.ok(timer); assert.equal(done,2);
});
test('Retina framebuffer is bounded without lowering ordinary viewport resolution',()=>{
  assert.equal(displayPixelRatio(1000,700,1),1);
  assert.ok(3000*2000*displayPixelRatio(3000,2000,2)**2<=3_000_001);
});

test('a zero pending counter does not publish an unsettled batch or lost context',()=>{
  assert.equal(canPresent({pending:0,ready:false,failed:0}),false);
  assert.equal(canPresent({pending:0,ready:true,failed:0}),true);
  assert.equal(canPresent({pending:0,ready:true,failed:0,gpu:{context_lost:true}}),false);
});

test('texture LOD preserves close maps and resizes shared images once, retaining material settings',async()=>{
  assert.equal(textureEdgeForPixels(Infinity),0); assert.equal(textureEdgeForPixels(600),0);
  assert.equal(textureEdgeForPixels(300),1024); assert.equal(textureEdgeForPixels(40),256);
  const root=model(); let closed=0, resized=0;
  const image={width:2048,height:1024,close:()=>closed++};
  root.material.map=new THREE.Texture(image); root.material.map.colorSpace=THREE.SRGBColorSpace;
  root.material.normalMap=root.material.map.clone();
  await resizeTemplateTextures(root,256,async(i,w,h)=>{resized++;return {width:w,height:h};});
  assert.equal(resized,1);assert.equal(closed,1);
  assert.equal(root.material.map.image.width,256);assert.equal(root.material.normalMap.image.height,128);
  assert.equal(root.material.map.colorSpace,THREE.SRGBColorSpace);
  await resizeTemplateTextures(root,0,()=>{throw Error('must retain originals');});
});
