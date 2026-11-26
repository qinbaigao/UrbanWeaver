import test from 'node:test';
import assert from 'node:assert/strict';
import {FloatType, Vector3, Matrix4, Euler} from 'three';
import {skyAllowed,pixelDirection,analyzeSky,skyOrientation,horizonGeometry,
  createHorizonGround,configureHorizonGround} from './sky.js';
test('outskirts stay opaque and blend radiance by horizontal distance, not camera altitude',()=>{
  const mesh=createHorizonGround();
  assert.equal(mesh.material.transparent,false);
  assert.equal(mesh.material.depthWrite,true);
  assert.equal(mesh.material.fog,false);
  assert.equal(mesh.children[0].frustumCulled,false);
  assert.equal(mesh.children[0].material.depthWrite,false);
  assert.equal(mesh.children[0].material.depthTest,true);
  assert.equal(mesh.children[0].renderOrder,-1000);
  const shader={uniforms:{},vertexShader:'#include <project_vertex>\n#include <worldpos_vertex>',
    fragmentShader:'#include <opaque_fragment>\n#include <tonemapping_fragment>'};
  mesh.material.onBeforeCompile(shader);
  assert.match(shader.fragmentShader,/vCitygHorizonWorld\.xy-cameraPosition\.xy/);
  assert.doesNotMatch(shader.fragmentShader,/diffuseColor\.a/);
  assert.ok(shader.fragmentShader.indexOf('outgoingLight=mix')<shader.fragmentShader.indexOf('tonemapping_fragment'));
  assert.doesNotMatch(shader.vertexShader,/gl_Position.z=min/);
  assert.match(mesh.children[0].material.fragmentShader,/smoothstep\(0.0,0.07,worldRay.z\)/);
  const ground={center:{x:50,y:40,z:-.1},size:{x:100,y:80,z:.2},rotation_z_deg:30};
  configureHorizonGround(mesh,ground,null,1000,[.6,.7,.8],.65);
  assert.equal(shader.uniforms.citygHorizonStart.value,800);
  assert.equal(shader.uniforms.citygHorizonEnd.value,2500);
  assert.ok(Math.abs(shader.uniforms.citygHorizonColor.value.r-.39)<1e-8);
  assert.ok(Math.abs(mesh.position.z+.025)<1e-8);
  const geometry=mesh.geometry;
  configureHorizonGround(mesh,ground,null,1000,[.6,.7,.8],.5);
  assert.equal(mesh.geometry,geometry,'theme updates do not rebuild the skirt');
  mesh.geometry.dispose();mesh.material.dispose();
  mesh.children[0].geometry.dispose();mesh.children[0].material.dispose();
});
test('horizon is an exterior skirt, not a plane occluding rivers inside the city',()=>{
  const g=horizonGeometry(100,80,1000),p=g.getAttribute('position'),indices=g.getIndex();
  assert.equal(indices.count,24);
  for(let i=0;i<indices.count;i+=3) {
    const ids=[indices.getX(i),indices.getX(i+1),indices.getX(i+2)];
    assert.ok(ids.every(j=>p.getX(j)<=-50)||ids.every(j=>p.getX(j)>=50)
      ||ids.every(j=>p.getY(j)<=-40)||ids.every(j=>p.getY(j)>=40));
  }
  g.dispose();
});
test('sky appears only in outdoor daytime high-quality scopes',()=>{
  const presets={clear:{}};
  for(const mode of ['room','floor','floor_plan']) assert.equal(skyAllowed(mode,true,{environment:true},'clear',presets),false);
  assert.equal(skyAllowed('overview',true,{environment:true},'clear',presets),true);
  assert.equal(skyAllowed('overview',false,{environment:true},'clear',presets),false);
  assert.equal(skyAllowed('overview',true,{environment:false},'clear',presets),false);
  assert.equal(skyAllowed('overview',true,{environment:true},'clear',{}),false);
});
test('HDR bright point maps to Z-up sunlight and shared background/environment rotation',()=>{
  const width=32,height=16,data=new Float32Array(width*height*4).fill(.2);
  const offset=(4*width+8)*4;data[offset]=data[offset+1]=data[offset+2]=100;
  // An even brighter lower hemisphere must not change sunlight direction.
  data[(14*width+8)*4]=1000;
  const analysis=analyzeSky({type:FloatType,image:{data,width,height}});
  assert.ok(analysis.sun.distanceTo(pixelDirection(8,4,width,height))<1e-6);
  const pose=skyOrientation(analysis,90,30);
  assert.ok(Math.abs(Math.atan2(pose.sun.y,pose.sun.x)*180/Math.PI-120)<1e-6);
  const r=pose.rotation;
  // Match WebGLBackground/WebGLMaterials' actual inverse Euler convention.
  const lookup=pose.sun.clone().applyMatrix4(new Matrix4().makeRotationFromEuler(new Euler(-r.x,-r.y,-r.z,r.order)));
  const local=analysis.sun.clone().applyAxisAngle(new Vector3(1,0,0),-Math.PI/2);
  assert.ok(lookup.distanceTo(local)<1e-6);
});
