import test from 'node:test';
import assert from 'node:assert/strict';
import {PerspectiveCamera, Box3, Vector3, DirectionalLight} from 'three';
import {screenContext, primitiveBounds, chooseAssetLod, chunkBounds, fitDirectionalShadow, aimDirectionalLight} from './screen_lod.js';
import {selectDetailChunks} from './streaming.js';
const box = (x,y,z,size=1) => new Box3(new Vector3(x-size/2,y-size/2,z-size/2),new Vector3(x+size/2,y+size/2,z+size/2));
const camera = () => {const c=new PerspectiveCamera(50,1,0.1,10000);c.position.set(0,-30,10);c.up.set(0,0,1);c.lookAt(0,0,3);return c;};
test('reapplying sky direction preserves fitted shadow position and clip range',()=>{
  const sun=new DirectionalLight();sun.position.set(-250,-180,420);
  fitDirectionalShadow(sun,new Box3(new Vector3(0,0,0),new Vector3(1400,1100,80)));
  const position=sun.position.clone(),target=sun.target.position.clone();
  const c=sun.shadow.camera,clip=[c.near,c.far,c.left,c.right,c.top,c.bottom];
  const direction=position.clone().sub(target).normalize();
  for(let i=0;i<10;i++) aimDirectionalLight(sun,direction);
  assert.ok(sun.position.distanceTo(position)<1e-8);
  assert.deepEqual([c.near,c.far,c.left,c.right,c.top,c.bottom],clip);
  assert.ok(sun.position.distanceTo(target)>520);
});
test('pixel coverage grows with image resolution and proximity; near plane is conservative', () => {
  const c=camera(); const b=box(0,0,3,2);
  const low=screenContext(c,500).measure(b), high=screenContext(c,2000).measure(b);
  assert.ok(low.visible); assert.equal(high.pixels,low.pixels*4);
  c.position.set(0,-5,3); c.lookAt(0,0,3);
  assert.ok(screenContext(c,500).measure(b).pixels>low.pixels);
  assert.equal(screenContext(c,500).measure(box(0,-5,3,2)).pixels,Infinity);
});
test('behind-camera object excluded, but off-screen sun caster retained', () => {
  const c=new PerspectiveCamera(45,1,0.1,1000);c.position.set(0,0,10);c.lookAt(0,0,0);
  const s=screenContext(c,1000,[-1,0,1]);
  assert.equal(s.measure(box(0,0,20)).visible,false);
  const caster=s.measure(box(-8,0,8));
  assert.equal(caster.visible,false); assert.equal(caster.shadow,true);
  const outside=s.measure(box(-80,0,8)); assert.equal(outside.visible || outside.shadow,false);
});
test('LOD uses pixels, not object category; near/unknown assets retain originals', () => {
  const levels={tree:[{asset_id:'far',max_pixels:48},{asset_id:'mid',max_pixels:192}]};
  assert.equal(chooseAssetLod('tree',30,levels),'far');
  assert.equal(chooseAssetLod('tree',90,levels),'mid');
  assert.equal(chooseAssetLod('tree',193,levels),'tree');
  assert.equal(chooseAssetLod('tree',Infinity,levels),'tree');
  assert.equal(chooseAssetLod('chair',30,levels),'chair');
});
test('rotated bounds and old streaming manifests remain conservative', () => {
  const b=primitiveBounds({center:{x:0,y:0,z:3},size:{x:10,y:2,z:6},rotation_z_deg:90});
  assert.ok(Math.abs(b.max.x-1)<1e-8);assert.equal(b.max.y,5);
  assert.equal(chunkBounds({bounds:[0,0,10,10]}).max.z,1000);
});
test('quality streaming restores all visible buildings, even high-altitude global view', () => {
  const chunks=Array.from({length:8},(_,i)=>({file:`${i}`,scope:'building',scope_id:`b${i}`,owner_ids:[]}));
  const args={profile:'snapshot',mode:'overview',kind:'global',camera:{z:2000},screenMeasure:()=>({visible:true,pixels:20})};
  assert.equal(selectDetailChunks({chunks},args).length,8);
  assert.equal(selectDetailChunks({chunks},{...args,screenMeasure:()=>({visible:false,shadow:false,pixels:0})}).length,0);
  assert.equal(selectDetailChunks({chunks},{...args,mode:'room',buildingId:'b0'}).length,1);
});
test('shadow camera follows retained geometry without changing sunlight direction', () => {
  const light = new DirectionalLight(); light.position.set(-250,-180,420);
  const direction=light.position.clone().normalize();
  const bounds=box(1000,1000,4,8);
  fitDirectionalShadow(light,bounds);
  assert.ok(light.position.clone().sub(light.target.position).normalize().distanceTo(direction)<1e-8);
  assert.ok(light.shadow.camera.right-light.shadow.camera.left<100);
  for(const x of [bounds.min.x,bounds.max.x]) for(const y of [bounds.min.y,bounds.max.y]) for(const z of [bounds.min.z,bounds.max.z]) {
    const p=new Vector3(x,y,z).project(light.shadow.camera);
    assert.ok(Math.max(Math.abs(p.x),Math.abs(p.y),Math.abs(p.z))<=1);
  }
});
