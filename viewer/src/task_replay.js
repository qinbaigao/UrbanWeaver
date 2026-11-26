import * as THREE from 'three';
import {doorPose} from './door_kinematics.js';
import {loadArticulatedRobot} from './articulated_robot.js';

export function frameAt(frames, seconds) {
  let lo = 0, hi = frames.length - 1;
  while (lo < hi) {
    const mid = Math.ceil((lo + hi) / 2);
    if (frames[mid].time_s <= seconds) lo = mid; else hi = mid - 1;
  }
  return frames[lo];
}

export function installTaskReplay(host) {
  const section = document.createElement('section');
  section.hidden=true;
  section.innerHTML = `<div class="section-label">Scripted task replay</div>
    <button class="button wide" data-load>Load A403 → B716</button>
    <div data-controls hidden><button class="button" data-play>Play</button>
    <button class="button" data-stop>Exit replay</button>
    <label class="field-label">Speed <select data-speed><option>1</option><option>5</option><option selected>20</option><option>50</option></select></label>
    <input data-seek type="range" min="0" max="1" step="0.05" value="0" style="width:100%" />
    <label><input data-follow type="checkbox" checked /> Follow robot / floor</label>
    <label class="field-label">Replay camera <select data-camera><option value="chase">Robot rear follow</option><option value="robot">Robot close-up (side)</option><option value="context">Route context</option></select></label>
    <label data-proxy-label hidden><input data-proxy type="checkbox" /> Debug occupancy proxy</label>
    <p data-status></p><small data-scope>Kinematic proxy replay · no learned policy or arm IK.</small></div>`;
  document.querySelector('.left-panel').prepend(section);
  const el = (s) => section.querySelector(s);
  const group = new THREE.Group(); host.scene.add(group);
  let bundle = null, playing = false, seconds = 0, suppressed = new Set(), meshes = new Map();
  let articulated=null, loadGeneration=0;
  let lastTime = performance.now(), lastScope = null;
  const unit = new THREE.BoxGeometry(1, 1, 1);
  function mesh(id, color, cylinder = false) {
    if (!meshes.has(id)) {
      const geometry = cylinder ? new THREE.CylinderGeometry(.5,.5,1,16) : unit;
      if (cylinder) geometry.rotateX(Math.PI/2);
      const m = new THREE.Mesh(geometry,new THREE.MeshStandardMaterial({color,roughness:.65}));
      group.add(m); meshes.set(id,m);
    }
    return meshes.get(id);
  }
  function box(id, center, size, yaw=0, color=0x8c9da4, cylinder=false) {
    const m=mesh(id,color,cylinder);m.visible=true;m.position.set(...center);m.scale.set(...size);m.rotation.set(0,0,yaw*Math.PI/180);
  }
  function apply() {
    if (!bundle) return;
    const {task, trace}=bundle, frame=frameAt(trace.frames,seconds), base=frame.robot_base;
    for (const m of meshes.values()) m.visible=false;
    if(articulated){
      articulated.apply(frame);
      if(el('[data-proxy]').checked){
        box('robot',base,task.robot.size,frame.robot_yaw_deg,0x3789cf);
        const material=meshes.get('robot').material;material.wireframe=true;
      }
    } else {
      box('robot',base,task.robot.size,frame.robot_yaw_deg??task.robot.yaw,0x3789cf);
      meshes.get('robot').material.wireframe=false;
    }
    box('payload',frame.objects[task.object_id].position,task.object.size,task.object.yaw,0xf2c458,true);
    const quaternion=frame.objects[task.object_id].quaternion;
    if(quaternion)meshes.get('payload').quaternion.fromArray(quaternion);
    const near=(p)=>Math.hypot(p[0]-base[0],p[1]-base[1])<35 && Math.abs(p[2]-base[2])<4;
    for (const [id,v] of Object.entries(task.doors)) {
      const p={center:{x:v.box.center[0],y:v.box.center[1],z:v.box.center[2]},
        size:{x:v.box.size[0],y:v.box.size[1],z:v.box.size[2]},rotation_z_deg:v.box.yaw,
        metadata:{hinge_local_m:v.hinge}};
      const posed=doorPose(p,frame.doors[id]);
      if (near([posed.x,posed.y,posed.z])) box(id,[posed.x,posed.y,posed.z],v.box.size,posed.angle*180/Math.PI,0xb58854);
    }
    for (const [id,lift] of Object.entries(task.lifts)) {
      const s=frame.lifts[id],dz=s.z-lift.initial_floor_z;
      for (const p of lift.cabin_parts) {
        // Follow mode is a visual cutaway only. The checked roof collider and
        // task contract are unchanged; an opaque roof would conceal the rider.
        if (el('[data-follow]').checked && p.id.includes('roof')) continue;
        const c=[p.center[0],p.center[1],p.center[2]+dz];
        if (near(c)) box(p.id,c,p.size,p.yaw);
      }
      for (const p of lift.panels) {
        const opened=p.level_z===null || p.level_z===s.landing_z ? s.opening : 0;
        const c=p.box.center.map((x,i)=>x+p.offset[i]*opened+(i===2&&p.level_z===null?dz:0));
        if (near(c)) box(p.box.id,c,p.box.size,p.box.yaw);
      }
    }
    if (el('[data-follow]').checked) {
      lastScope=host.follow(base,lastScope,{mode:el('[data-camera]').value,yaw:frame.robot_yaw_deg??0});
    }
    el('[data-seek]').value=seconds;
    el('[data-status]').textContent=`${seconds.toFixed(1)} / ${trace.frames.at(-1).time_s.toFixed(1)} s · ${frame.action}`;
    host.draw();
  }
  function exit() {
    loadGeneration++;articulated?.dispose();articulated=null;
    playing=false;bundle=null;suppressed.clear();group.visible=false;lastScope=null;
    el('[data-play]').textContent='Play';
    el('[data-controls]').hidden=true;el('[data-load]').disabled=false;host.rebuild();
  }
  async function load() {
    const generation=++loadGeneration;
    const response=await fetch('./scene/task_replay.json',{cache:'no-store'});
    if (!response.ok) throw new Error('No task replay in this scene package');
    const candidate=await response.json();
    const geometry=await fetch('./scene/geometry_manifest.json',{cache:'no-store'});
    if (!geometry.ok) throw new Error('Scene manifest unavailable');
    const digest=await crypto.subtle.digest('SHA-256',await geometry.arrayBuffer());
    const hex=[...new Uint8Array(digest)].map(v=>v.toString(16).padStart(2,'0')).join('');
    if (candidate.scene_sha256!==hex || !candidate.acceptance?.ok) throw new Error('Stale or unaccepted task replay');
    if (!candidate.trace?.frames?.length) throw new Error('Empty task replay');
    let robot=null;
    if(candidate.robot_model){
      robot=await loadArticulatedRobot(candidate.robot_model,'./scene/robot_model.glb');
      if(!candidate.trace.frames.every(f=>f.robot_root&&f.robot_joints)) {robot.dispose();throw new Error('Missing articulated robot states');}
    }
    if(generation!==loadGeneration){robot?.dispose();return;}
    articulated?.dispose();articulated=robot;if(robot)group.add(robot.scene);
    el('[data-proxy-label]').hidden=!robot;
    el('[data-camera]').value=robot?'chase':'context';
    el('[data-scope]').textContent=robot?'Fetch · scripted drive + arm IK · sampled link collision checks · no grasp dynamics':'Kinematic proxy replay · no learned policy or arm IK.';
    bundle=candidate;playing=false;seconds=0;lastScope=null;suppressed=new Set(bundle.task.source_primitive_ids);
    el('[data-play]').textContent='Play';
    for (const id of Object.keys(bundle.task.doors)) suppressed.add(id);
    for (const lift of Object.values(bundle.task.lifts)) {
      for (const p of lift.cabin_parts) suppressed.add(p.id);
      for (const p of lift.panels) suppressed.add(p.box.id);
    }
    group.visible=true;el('[data-controls]').hidden=false;el('[data-load]').disabled=true;
    el('[data-seek]').max=bundle.trace.frames.at(-1).time_s;
    host.begin?.();host.rebuild();apply();
  }
  el('[data-load]').onclick=()=>load().catch(e=>host.error(e.message));
  el('[data-play]').onclick=()=>{
    if (!bundle) return;
    if (seconds>=bundle.trace.frames.at(-1).time_s) seconds=0;
    playing=!playing;el('[data-play]').textContent=playing?'Pause':'Play';
  };
  el('[data-stop]').onclick=exit;
  el('[data-proxy]').onchange=apply;
  el('[data-camera]').onchange=apply;
  el('[data-follow]').onchange=apply;
  el('[data-seek]').oninput=()=>{seconds=Number(el('[data-seek]').value);apply();};
  function tick(now) {
    if (bundle && playing) {
      seconds=Math.min(bundle.trace.frames.at(-1).time_s,seconds+Math.min((now-lastTime)/1000,.1)*Number(el('[data-speed]').value));
      apply();if (seconds>=bundle.trace.frames.at(-1).time_s) {playing=false;el('[data-play]').textContent='Play';}
    }
    lastTime=now;requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
  const api={load,exit,reset:exit,available:(value)=>{section.hidden=!value;},suppressed:(id)=>suppressed.has(id),
    milestones:()=>bundle?Object.fromEntries(['attach','stow_object','door','transit:enter','transit:ride','place_object','release'].map(action=>[action,bundle.trace.frames.find(f=>f.action===action)?.time_s]).filter(([,time])=>time!==undefined)):{},
    seek:(t)=>{if (!bundle) throw new Error('Replay not loaded');seconds=Math.max(0,Math.min(t,bundle.trace.frames.at(-1).time_s));apply();},
    status:()=>({loaded:!!bundle,playing,seconds,suppressed_count:suppressed.size,
      camera_mode:el('[data-camera]').value,following:el('[data-follow]').checked,camera:host.cameraState?.(),
      robot:articulated?{name:'Fetch',loaded:true,links:articulated.linkCount,meshes:articulated.meshCount,effector_position:articulated.effectorPosition()}:null,
      frame:bundle?frameAt(bundle.trace.frames,seconds):null})};
  window.citygTaskReplay=api;return api;
}
