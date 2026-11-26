// Presentation-only, metre-scaled parcel surfacing. The original clipped mesh
// remains the boundary: no generated overlay can spill onto a road or river.
import {Vector2, Vector4} from 'three';

// Use realized ground-floor slab boundaries, never the (often much larger)
// planning rectangle. For a T/L/courtyard building the empty part of that
// rectangle is NOT building apron. Data is already available at city LOD.
export function indexGroundEdges(primitives, entities) {
  const candidates = new Map();
  for (const p of primitives) {
    if (p.semantic_class !== 'floor_slab') continue;
    const owner = entities.get(p.owner_id);
    const bid = p.metadata?.building_id || owner?.buildingId;
    const floor = owner?.type === 'floor' ? owner.entity : null;
    if (!bid || (floor ? floor.level !== 0 : Math.abs(p.center.z) > 0.3)) continue;
    if (!candidates.has(bid)) candidates.set(bid, []);
    candidates.get(bid).push(p);
  }
  const result = new Map();
  for (const [bid, slabs] of candidates) {
    const segments = [];
    for (const p of slabs) {
      const a = (p.rotation_z_deg || 0)*Math.PI/180, c=Math.cos(a),s=Math.sin(a);
      const world = v => [p.center.x+c*v[0]*p.size.x-s*v[1]*p.size.y,
        p.center.y+s*v[0]*p.size.x+c*v[1]*p.size.y];
      if (p.primitive_type === 'box') {
        const q=[[-.5,-.5],[.5,-.5],[.5,.5],[-.5,.5]].map(world);
        q.forEach((v,i)=>segments.push([...v,...q[(i+1)%4]]));
      } else if (p.primitive_type === 'path_mesh') {
        const vertices=p.metadata?.mesh_vertices || [], edges=new Map();
        const top=Math.max(...vertices.map(v=>v[2]));
        for (const t of p.metadata?.mesh_triangles || []) {
          if (!t.every(i=>Math.abs(vertices[i][2]-top)<1e-5)) continue;
          for(let i=0;i<3;i++) {
            const u=t[i],v=t[(i+1)%3],key=[u,v].sort((x,y)=>x-y).join(',');
            const edge=edges.get(key) || {u,v,count:0};edge.count++;edges.set(key,edge);
          }
        }
        for(const {u,v,count} of edges.values()) if(count===1) segments.push([...world(vertices[u]),...world(vertices[v])]);
      }
    }
    result.set(bid,segments);
  }
  return result;
}

export function groundSurfacePlan(parcel, materialId = '', groundEdges = new Map()) {
  const b = parcel?.bounds;
  if (!b || ![b.min_x,b.min_y,b.max_x,b.max_y].every(Number.isFinite)) return null;
  const buildings = (parcel.buildings || []).filter(v => v.footprint).slice(0,8);
  const green = materialId.includes('lawn');
  let seed = 0;
  for (const c of String(parcel.id)) seed = (Math.imul(seed,31)+c.charCodeAt(0)) >>> 0;
  return {green, seed: (seed % 10000)/37,
    bounds: [b.min_x,b.min_y,b.max_x,b.max_y],
    // Drop excess edges conservatively: omitted aprons remain grass. Never
    // replace complex outlines with a filled bounding rectangle.
    edges: buildings.flatMap(v=>groundEdges.get(v.id) || []).slice(0,64),
    buildings: buildings.map(v => {
      const f=v.footprint,cx=(f.min_x+f.max_x)/2,cy=(f.min_y+f.max_y)/2;
      const angle=Number(v.metadata?.orientation_deg || 0)*Math.PI/180;
      // City entrances are in the same unrotated planning frame as footprint.
      const e=v.entrance || {x:cx,y:f.min_y};
      const ex=e.x-cx,ey=e.y-cy;
      return {box:[cx,cy,(f.max_x-f.min_x)/2,(f.max_y-f.min_y)/2],
        pose:[Math.cos(angle),Math.sin(angle),0,0],
        entrance:[cx+ex*Math.cos(angle)-ey*Math.sin(angle),cy+ex*Math.sin(angle)+ey*Math.cos(angle),0,0]};
    })};
}

const field = /* glsl */`
varying vec2 uwGroundXY;
uniform vec4 uwParcel;
uniform vec4 uwBuildings[8];
uniform vec4 uwPoses[8];
uniform vec4 uwEntrances[8];
uniform vec4 uwEdges[64];
uniform int uwEdgeCount;
uniform int uwBuildingCount;
uniform float uwGreenBase, uwSeed, uwStrength, uwOtherReady, uwOtherScale;
uniform sampler2D uwOtherColor, uwOtherNormal, uwOtherRoughness;
uniform vec2 uwOtherChannels;
float uwHash(vec2 p) { return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453); }
float uwNoise(vec2 p) {
  vec2 i=floor(p),f=fract(p); f=f*f*(3.0-2.0*f);
  return mix(mix(uwHash(i),uwHash(i+vec2(1,0)),f.x),
             mix(uwHash(i+vec2(0,1)),uwHash(i+vec2(1,1)),f.x),f.y);
}
float uwHardscape(vec2 p) {
  float apron=0.0,entry=0.0;
  for (int i=0;i<64;i++) {
    if(i>=uwEdgeCount) break;
    vec2 a=uwEdges[i].xy,b=uwEdges[i].zw,ab=b-a;
    float t=clamp(dot(p-a,ab)/max(dot(ab,ab),0.0001),0.0,1.0);
    float d=length(p-a-t*ab);
    apron=max(apron,1.0-smoothstep(1.3,1.6,d));
  }
  for (int i=0;i<8;i++) {
    if (i>=uwBuildingCount) break;
    vec4 b=uwBuildings[i];vec2 cs=uwPoses[i].xy;
    vec2 outward=uwEntrances[i].xy-b.xy;
    outward/=max(length(outward),0.001);
    vec2 rel=p-uwEntrances[i].xy;
    float along=dot(rel,outward),across=abs(dot(rel,vec2(-outward.y,outward.x)));
    // A forecourt, not a claimed navigable connection to a road. Existing
    // compiled access paths remain above this material and are untouched.
    entry=max(entry,(1.0-smoothstep(6.0,6.3,across))*
      (1.0-smoothstep(9.0,9.3,along))*smoothstep(-2.0,-1.7,along));
  }
  vec2 edge=min(p-uwParcel.xy,uwParcel.zw-p);
  float border=min(edge.x,edge.y);
  float plantedWidth=3.5+1.2*uwNoise(p/12.0+uwSeed);
  float greenEdge=1.0-smoothstep(plantedWidth-0.15,plantedWidth+0.15,border);
  float hard=mix(1.0-greenEdge,0.0,uwGreenBase);
  return max(hard,max(apron,entry));
}
`;

export function installGroundSurface(material, plan, {strength=1, otherScale=4}={}) {
  const uniforms={
    uwParcel:{value:new Vector4(...plan.bounds)},uwSeed:{value:plan.seed},
    uwGreenBase:{value:plan.green?1:0},uwStrength:{value:Math.max(0,Math.min(1.5,strength))},
    uwBuildingCount:{value:plan.buildings.length},
    uwEdgeCount:{value:plan.edges.length},
    uwEdges:{value:Array.from({length:64},(_,i)=>new Vector4(...(plan.edges[i] || [0,0,0,0])))},
    uwBuildings:{value:Array.from({length:8},(_,i)=>new Vector4(...(plan.buildings[i]?.box || [0,0,0,0])))},
    uwPoses:{value:Array.from({length:8},(_,i)=>new Vector4(...(plan.buildings[i]?.pose || [1,0,0,0])))},
    uwEntrances:{value:Array.from({length:8},(_,i)=>new Vector4(...(plan.buildings[i]?.entrance || [0,0,0,0])))},
    uwOtherColor:{value:null},uwOtherNormal:{value:null},uwOtherRoughness:{value:null},
    uwOtherReady:{value:0},uwOtherScale:{value:otherScale},uwOtherChannels:{value:new Vector2(0,0)},
  };
  material.onBeforeCompile=shader=>{
    Object.assign(shader.uniforms,uniforms);
    shader.vertexShader='varying vec2 uwGroundXY;\n'+shader.vertexShader;
    shader.vertexShader=shader.vertexShader.replace('#include <project_vertex>',`#include <project_vertex>
      vec4 uwWorld=vec4(transformed,1.0);
      #ifdef USE_INSTANCING
        uwWorld=instanceMatrix*uwWorld;
      #endif
      uwGroundXY=(modelMatrix*uwWorld).xy;`);
    shader.fragmentShader=field+shader.fragmentShader;
    shader.fragmentShader=shader.fragmentShader.replace('#include <map_fragment>',`#include <map_fragment>
      float uwHard=uwHardscape(uwGroundXY);
      float uwMix=uwOtherReady*mix(1.0-uwHard,uwHard,uwGreenBase);
      vec2 uwUV=uwGroundXY/uwOtherScale;
      diffuseColor.rgb=mix(diffuseColor.rgb,texture2D(uwOtherColor,uwUV).rgb,uwMix);
      // The installed grass scan contains dry yellow blades. Use a restrained
      // maintained-lawn tint for BOTH samplers, instead of inheriting whichever
      // semantic green/grey happened to be on the original whole-parcel base.
      float uwActualHard=mix(1.0-uwGreenBase,uwHard,uwOtherReady);
      diffuseColor.rgb*=mix(vec3(0.32,0.48,0.23),vec3(0.80,0.78,0.73),uwActualHard);
      float uwBroad=uwNoise(uwGroundXY/24.0+uwSeed);
      float uwMedium=uwNoise(uwGroundXY/7.0+uwSeed);
      vec3 uwGrassTint=mix(vec3(0.67,0.78,0.57),vec3(1.18,1.09,0.82),uwBroad);
      uwGrassTint*=0.88+0.22*uwMedium;
      // Meter-scale PBR alone averages to flat grey in aerial views. A separate
      // broad field supplies paving wear without enlarging joints/grain or
      // changing the established grass treatment and hardscape boundaries.
      float uwPavingField=uwNoise(uwGroundXY/32.0+uwSeed+vec2(19.3,7.1));
      float uwPavingTone=smoothstep(0.18,0.82,uwPavingField);
      float uwWear=0.60+0.68*uwPavingTone+0.10*uwMedium;
      vec3 uwPavingTint=mix(vec3(0.90,0.96,1.04),vec3(1.06,1.015,0.94),uwPavingTone)*uwWear;
      vec3 uwTint=mix(uwGrassTint,uwPavingTint,uwHard);
      diffuseColor.rgb*=mix(vec3(1.0),uwTint,uwStrength);
      float uwDry=smoothstep(0.56,0.85,uwBroad)*0.22*(1.0-uwHard)*uwStrength;
      diffuseColor.rgb=mix(diffuseColor.rgb,vec3(0.24,0.18,0.075),uwDry);
    `);
    shader.fragmentShader=shader.fragmentShader.replace('#include <roughnessmap_fragment>',`#include <roughnessmap_fragment>
      if (uwOtherChannels.y>0.5) roughnessFactor=mix(roughnessFactor,
        roughness*texture2D(uwOtherRoughness,uwUV).g,uwMix);
      roughnessFactor=clamp(roughnessFactor+(uwBroad-0.5)*0.09*uwStrength,0.3,1.0);`);
    shader.fragmentShader=shader.fragmentShader.replace('#include <normal_fragment_maps>',`#include <normal_fragment_maps>
      #ifdef USE_NORMALMAP_TANGENTSPACE
        if (uwOtherChannels.x>0.5) {
          vec3 uwN=texture2D(uwOtherNormal,uwUV).xyz*2.0-1.0;
          uwN.xy*=normalScale;
          normal=normalize(mix(normal,normalize(tbn*uwN),uwMix));
        }
      #endif
    `);
  };
  material.customProgramCacheKey=()=> 'cityg-parcel-ground-v3';
  return (channel,texture)=>{
    if(channel==='base_color') {uniforms.uwOtherColor.value=texture;uniforms.uwOtherReady.value=1;}
    if(channel==='normal') {uniforms.uwOtherNormal.value=texture;uniforms.uwOtherChannels.value.x=1;}
    if(channel==='roughness') {uniforms.uwOtherRoughness.value=texture;uniforms.uwOtherChannels.value.y=1;}
  };
}
