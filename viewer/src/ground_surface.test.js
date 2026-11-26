import test from 'node:test';
import assert from 'node:assert/strict';
import {MeshStandardMaterial, ShaderLib, Texture} from 'three';
import {groundSurfacePlan,installGroundSurface,indexGroundEdges} from './ground_surface.js';

const parcel={id:'parcel_17',bounds:{min_x:0,min_y:0,max_x:100,max_y:80},buildings:[{
  footprint:{min_x:20,min_y:20,max_x:60,max_y:50},entrance:{x:40,y:20},metadata:{orientation_deg:90},
}]};
test('ground contract is deterministic, bounded and rotates planning entrances with buildings',()=>{
  const p=groundSurfacePlan(parcel,'parcel_lawn');
  assert.deepEqual(p,groundSurfacePlan(parcel,'parcel_lawn'));
  assert.equal(p.green,true);assert.deepEqual(p.bounds,[0,0,100,80]);
  assert.deepEqual(p.buildings[0].box,[40,35,20,15]);
  assert.ok(Math.abs(p.buildings[0].entrance[0]-55)<1e-8);
  assert.ok(Math.abs(p.buildings[0].entrance[1]-35)<1e-8);
  assert.equal(groundSurfacePlan(parcel,'courtyard_paving').green,false);
  assert.equal(groundSurfacePlan(null),null);
  assert.equal(groundSurfacePlan({...parcel,bounds:{min_x:NaN}}),null);
  assert.equal(groundSurfacePlan({...parcel,buildings:Array(15).fill(parcel.buildings[0])}).buildings.length,8);
});
test('shader preserves standard lighting and original mesh, with async secondary PBR bindings',()=>{
  const m=new MeshStandardMaterial(),plan=groundSurfacePlan(parcel,'parcel_lawn');
  const receive=installGroundSurface(m,plan);
  const shader={uniforms:{},vertexShader:ShaderLib.standard.vertexShader,fragmentShader:ShaderLib.standard.fragmentShader};
  m.onBeforeCompile(shader);
  assert.match(shader.vertexShader,/instanceMatrix\*uwWorld/);
  assert.match(shader.fragmentShader,/#include <lights_fragment_begin>/);
  assert.match(shader.fragmentShader,/#include <map_fragment>/);
  assert.match(shader.fragmentShader,/tbn\*uwN/);
  assert.equal(shader.uniforms.uwOtherReady.value,0);
  const texture=new Texture();receive('base_color',texture);receive('normal',texture);receive('roughness',texture);
  assert.equal(shader.uniforms.uwOtherColor.value,texture);
  assert.equal(shader.uniforms.uwOtherReady.value,1);
  assert.deepEqual(shader.uniforms.uwOtherChannels.value.toArray(),[1,1]);
  const second=new MeshStandardMaterial();installGroundSurface(second,groundSurfacePlan({...parcel,id:'other'}));
  assert.equal(second.customProgramCacheKey(),m.customProgramCacheKey());
  assert.equal(m.displacementMap,null);
});
test('paving has independent broad tonal wear while retaining grass and physical PBR sampling',()=>{
  const material=new MeshStandardMaterial();
  installGroundSurface(material,groundSurfacePlan(parcel,'courtyard_paving'),{strength:0,otherScale:4});
  const shader={uniforms:{},vertexShader:ShaderLib.standard.vertexShader,fragmentShader:ShaderLib.standard.fragmentShader};
  material.onBeforeCompile(shader);
  assert.equal(shader.uniforms.uwStrength.value,0);
  assert.equal(shader.uniforms.uwOtherScale.value,4);
  assert.match(shader.fragmentShader,/uwGroundXY\/32\.0/);
  assert.match(shader.fragmentShader,/mix\(uwGrassTint,uwPavingTint,uwHard\)/);
  assert.match(shader.fragmentShader,/mix\(vec3\(1\.0\),uwTint,uwStrength\)/);
  assert.match(shader.fragmentShader,/uwGroundXY\/uwOtherScale/);
  // Grass keeps its existing 7/24 m variation, not the paving-specific field.
  assert.match(shader.fragmentShader,/uwGrassTint\*=0\.88\+0\.22\*uwMedium/);
});
test('T-shaped building apron follows realized slabs, not its enclosing planning rectangle',()=>{
  const entities=new Map([['floor0',{type:'floor',buildingId:'b',entity:{level:0}}],
    ['floor1',{type:'floor',buildingId:'b',entity:{level:1}}]]);
  const slab=(owner,x,y,sx,sy,z=0)=>({owner_id:owner,semantic_class:'floor_slab',primitive_type:'box',
    center:{x,y,z},size:{x:sx,y:sy,z:.2},rotation_z_deg:0});
  const edges=indexGroundEdges([slab('floor0',50,65,60,10),slab('floor0',50,40,10,40),
    slab('floor1',50,40,90,70,3)],entities);
  assert.equal(edges.get('b').length,8);
  // Open corner inside the planning bounds is far from every actual wall.
  const d=([ax,ay,bx,by])=>{
    const dx=bx-ax,dy=by-ay,t=Math.max(0,Math.min(1,((25-ax)*dx+(25-ay)*dy)/(dx*dx+dy*dy)));
    return Math.hypot(25-ax-t*dx,25-ay-t*dy);
  };
  assert.ok(Math.min(...edges.get('b').map(d))>15);
  assert.deepEqual(groundSurfacePlan({...parcel,buildings:[{...parcel.buildings[0],id:'b'}]},'parcel_lawn',edges).edges,edges.get('b'));
  assert.deepEqual(groundSurfacePlan(parcel,'parcel_lawn').edges,[]);
});
