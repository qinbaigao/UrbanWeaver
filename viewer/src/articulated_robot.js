import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';

// URDF uses row-major matrices and radians; Three uses column-major storage.
export function robotLinkMatrices(spec, joints, root=[0,0,0], yaw=0) {
  const base=new THREE.Matrix4().makeRotationZ(yaw);
  base.setPosition(...root);
  const poses=new Map([[spec.root,base]]);
  for (const j of spec.joints) {
    const origin=new THREE.Matrix4().fromArray(j.origin.flat()).transpose();
    const motion=new THREE.Matrix4(), q=joints[j.name]??0;
    if (j.type==='prismatic') motion.makeTranslation(...j.axis.map(v=>v*q));
    else if (j.type==='revolute'||j.type==='continuous') motion.makeRotationAxis(new THREE.Vector3(...j.axis).normalize(),q);
    if (!poses.has(j.parent)) throw new Error(`Unresolved robot joint ${j.name}`);
    poses.set(j.child,poses.get(j.parent).clone().multiply(origin).multiply(motion));
  }
  return poses;
}

export async function loadArticulatedRobot(spec,url) {
  const response=await fetch(url,{cache:'no-store'});
  if (!response.ok) throw new Error('Robot mesh missing from portable package');
  const bytes=await response.arrayBuffer();
  const digest=await crypto.subtle.digest('SHA-256',bytes);
  const hex=[...new Uint8Array(digest)].map(v=>v.toString(16).padStart(2,'0')).join('');
  if (hex!==spec.glb_sha256) throw new Error('Robot mesh hash mismatch');
  const {scene}=await new GLTFLoader().parseAsync(bytes,'');
  const nodes=new Map();
  for (const name of Object.keys(spec.links)) {
    const node=scene.getObjectByName(name);
    if (!node) throw new Error(`Robot mesh has no link ${name}`);
    node.matrixAutoUpdate=false;nodes.set(name,node);
  }
  let meshCount=0;
  scene.traverse(n=>{if(n.isMesh){meshCount++;n.castShadow=true;n.receiveShadow=true;}});
  return {scene,meshCount,linkCount:nodes.size,
    effectorPosition(){
      scene.updateMatrixWorld(true);
      return new THREE.Vector3(...spec.grasp_offset).applyMatrix4(nodes.get(spec.end_effector_link).matrixWorld).toArray();
    },
    apply(frame) {
      for (const [name,matrix] of robotLinkMatrices(spec,frame.robot_joints,frame.robot_root,frame.robot_yaw_deg*Math.PI/180)) {
        nodes.get(name).matrix.copy(matrix);nodes.get(name).matrixWorldNeedsUpdate=true;
      }
    },
    dispose() {
      const geometries=new Set(),materials=new Set(),textures=new Set();
      scene.traverse(n=>{if(n.isMesh){geometries.add(n.geometry);for(const m of (Array.isArray(n.material)?n.material:[n.material]))materials.add(m);}});
      for(const material of materials){for(const value of Object.values(material))if(value?.isTexture)textures.add(value);material.dispose();}
      for(const texture of textures)texture.dispose();for(const geometry of geometries)geometry.dispose();
      scene.removeFromParent();
    }};
}
