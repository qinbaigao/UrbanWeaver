import {test} from 'node:test';
import assert from 'node:assert/strict';
import {robotLinkMatrices} from './articulated_robot.js';
const identity=[[1,0,0,1],[0,1,0,0],[0,0,1,0],[0,0,0,1]];
test('URDF row-major origin and revolute axis agree with Z-up FK',()=>{
  const spec={root:'base',joints:[{name:'joint',parent:'base',child:'arm',origin:identity,type:'revolute',axis:[0,0,1]}]};
  const poses=robotLinkMatrices(spec,{joint:Math.PI/2},[2,3,4],Math.PI/2);
  const e=poses.get('arm').elements;
  assert.ok(Math.abs(e[12]-2)<1e-12);assert.ok(Math.abs(e[13]-4)<1e-12);assert.equal(e[14],4);
  assert.ok(Math.abs(e[0]+1)<1e-12);
});
test('prismatic motion follows joint axis after origin rotation',()=>{
  const spec={root:'base',joints:[{name:'lift',parent:'base',child:'torso',origin:identity,type:'prismatic',axis:[0,0,1]}]};
  const pose=robotLinkMatrices(spec,{lift:.3}).get('torso');
  assert.equal(pose.elements[12],1);assert.equal(pose.elements[14],.3);
});
test('disconnected joint topology is rejected',()=>{
  const spec={root:'base',joints:[{name:'bad',parent:'missing',child:'arm',origin:identity,type:'fixed',axis:[1,0,0]}]};
  assert.throws(()=>robotLinkMatrices(spec,{}),/Unresolved robot joint/);
});
