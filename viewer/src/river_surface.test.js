import test from 'node:test';
import assert from 'node:assert/strict';
import {MeshPhysicalMaterial, ShaderLib} from 'three';
import {riverSegments, riverSample, buildRiverField, installRiverSurface} from './river_surface.js';

const river={width_m:20,centerline:[{x:0,y:0},{x:100,y:0},{x:100,y:100}]};
test('river field follows curved centreline, including bank distance',()=>{
  const segments=riverSegments(river);
  assert.deepEqual(riverSample(segments,50,0,10),[1,0,0]);
  assert.deepEqual(riverSample(segments,50,5,10),[1,0,.5]);
  assert.deepEqual(riverSample(segments,95,50,10),[0,1,.5]);
  assert.deepEqual(riverSample(segments,50,50,10),[1,0,1]);
});
test('invalid or degenerate rivers retain ordinary material',()=>{
  for(const value of [null,{}, {...river,width_m:0},{...river,centerline:[{x:0,y:0},{x:0,y:0}]}]){
    assert.equal(buildRiverField(value),null);
    assert.equal(installRiverSurface(new MeshPhysicalMaterial(),value),false);
  }
});
test('field is bounded, deterministic, independent of geometry UVs',()=>{
  const a=buildRiverField(river,64),b=buildRiverField(river,64);
  assert.deepEqual(a.texture.image.data,b.texture.image.data);
  assert.equal(a.texture.image.width,64);
  assert.equal(a.texture.image.height,64);
  assert.deepEqual(a.bounds.toArray(),[-12,-12,124,124]);
  assert.equal(a.texture.generateMipmaps,false);
  a.texture.dispose();b.texture.dispose();
});
test('physical shader hooks preserve ordering, instancing and private texture disposal',()=>{
  const material=new MeshPhysicalMaterial();
  assert.equal(installRiverSurface(material,river),true);
  const shader={uniforms:{},vertexShader:ShaderLib.physical.vertexShader,fragmentShader:ShaderLib.physical.fragmentShader};
  material.onBeforeCompile(shader);
  assert.match(shader.vertexShader,/instanceMatrix\*uwWaterWorld/);
  assert.match(shader.fragmentShader,/fwidth\(a\)/);
  assert.ok(shader.fragmentShader.indexOf('float uwShallow=')<shader.fragmentShader.indexOf('roughnessFactor=mix'));
  assert.ok(shader.fragmentShader.indexOf('#include <clearcoat_normal_fragment_begin>')<shader.fragmentShader.indexOf('clearcoatNormal=normal'));
  assert.equal(Object.keys(shader.uniforms).some(k=>/time/i.test(k)),false);
  let disposed=0;
  shader.uniforms.uwRiverField.value.addEventListener('dispose',()=>disposed++);
  material.dispose();assert.equal(disposed,1);
});
