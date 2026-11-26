// Static, deterministic water shading: no simulation, extra reflection pass,
// displacement or animation loop. Environment and sunlight remain Three PBR.
import {DataTexture, RGBAFormat, UnsignedByteType, LinearFilter, Vector4} from 'three';

export function riverSegments(river) {
  const points=river?.centerline || [], segments=[];
  for(let i=1;i<points.length;i++) {
    const a=points[i-1], b=points[i], dx=b.x-a.x,dy=b.y-a.y;
    const length=Math.hypot(dx,dy);
    if([a.x,a.y,b.x,b.y,length].every(Number.isFinite) && length>1e-6)
      segments.push({x:a.x,y:a.y,dx,dy,length});
  }
  return segments;
}

export function riverSample(segments,x,y,halfWidth) {
  let distance=Infinity,tx=0,ty=1;
  for(const s of segments) {
    const t=Math.max(0,Math.min(1,((x-s.x)*s.dx+(y-s.y)*s.dy)/(s.length*s.length)));
    const d=(x-s.x-t*s.dx)**2+(y-s.y-t*s.dy)**2;
    if(d<distance){distance=d;tx=s.dx/s.length;ty=s.dy/s.length;}
  }
  return [tx,ty,Math.min(1,Math.sqrt(distance)/halfWidth)];
}

export function buildRiverField(river,maxEdge=512) {
  const segments=riverSegments(river),halfWidth=Number(river?.width_m)/2;
  if(!segments.length || !Number.isFinite(halfWidth) || halfWidth<=0)return null;
  const points=segments.flatMap(s=>[[s.x,s.y],[s.x+s.dx,s.y+s.dy]]);
  const x0=Math.min(...points.map(p=>p[0]))-halfWidth-2;
  const y0=Math.min(...points.map(p=>p[1]))-halfWidth-2;
  const sx=Math.max(...points.map(p=>p[0]))+halfWidth+2-x0;
  const sy=Math.max(...points.map(p=>p[1]))+halfWidth+2-y0;
  const limit=Math.max(32,Math.min(1024,Math.floor(maxEdge)));
  const nx=Math.max(32,Math.ceil(limit*sx/Math.max(sx,sy)));
  const ny=Math.max(32,Math.ceil(limit*sy/Math.max(sx,sy)));
  const data=new Uint8Array(nx*ny*4);
  for(let j=0;j<ny;j++)for(let i=0;i<nx;i++) {
    const [tx,ty,d]=riverSample(segments,x0+(i+.5)*sx/nx,y0+(j+.5)*sy/ny,halfWidth);
    const index=(j*nx+i)*4;
    data[index]=Math.round((tx*.5+.5)*255);data[index+1]=Math.round((ty*.5+.5)*255);
    data[index+2]=Math.round(d*255);data[index+3]=255;
  }
  const texture=new DataTexture(data,nx,ny,RGBAFormat,UnsignedByteType);
  texture.minFilter=texture.magFilter=LinearFilter;
  texture.generateMipmaps=false;texture.needsUpdate=true;
  return {texture,bounds:new Vector4(x0,y0,sx,sy)};
}

const field=/* glsl */`
varying vec2 uwWaterXY;
uniform sampler2D uwRiverField;
uniform vec4 uwRiverBounds;
uniform float uwWaterStrength;
float uwWaterHash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
float uwWaterNoise(vec2 p){
  vec2 i=floor(p),f=fract(p);f=f*f*(3.0-2.0*f);
  return mix(mix(uwWaterHash(i),uwWaterHash(i+vec2(1,0)),f.x),
    mix(uwWaterHash(i+vec2(0,1)),uwWaterHash(i+vec2(1,1)),f.x),f.y);
}
vec3 uwRiverAt(vec2 p){return texture2D(uwRiverField,(p-uwRiverBounds.xy)/uwRiverBounds.zw).rgb;}
vec2 uwRipple(vec2 p,vec2 direction,float k,float slope,float phase){
  float warp=uwWaterNoise(p/3.0+vec2(phase,phase*1.7));
  float a=dot(p,direction)*k+phase+warp*5.0;
  // Do not replace subpixel waves with shimmering moire at city scale.
  float visible=1.0-smoothstep(0.6,2.8,fwidth(a));
  return direction*(cos(a)*slope*visible*(.45+.55*warp));
}
`;

export function installRiverSurface(material,river,{strength=1}={}) {
  const plan=buildRiverField(river);
  if(!plan)return false;
  const amount=Number.isFinite(strength)?Math.max(0,Math.min(1.5,strength)):1;
  const uniforms={uwRiverField:{value:plan.texture},uwRiverBounds:{value:plan.bounds},uwWaterStrength:{value:amount}};
  material.onBeforeCompile=shader=>{
    Object.assign(shader.uniforms,uniforms);
    shader.vertexShader='varying vec2 uwWaterXY;\n'+shader.vertexShader;
    shader.vertexShader=shader.vertexShader.replace('#include <project_vertex>',`#include <project_vertex>
      vec4 uwWaterWorld=vec4(transformed,1.0);
      #ifdef USE_INSTANCING
        uwWaterWorld=instanceMatrix*uwWaterWorld;
      #endif
      uwWaterXY=(modelMatrix*uwWaterWorld).xy;`);
    shader.fragmentShader=field+shader.fragmentShader;
    shader.fragmentShader=shader.fragmentShader.replace('#include <map_fragment>',`#include <map_fragment>
      vec3 uwRiver=uwRiverAt(uwWaterXY);
      vec2 uwFlow=uwRiver.rg*2.0-1.0;uwFlow/=max(length(uwFlow),0.01);
      vec2 uwCross=vec2(-uwFlow.y,uwFlow.x);
      float uwShallow=smoothstep(0.58,1.0,uwRiver.b);
      float uwCloud=uwWaterNoise(uwWaterXY/22.0);
      // Turbid urban river: depth-colour approximation, not transparent ocean.
      vec3 uwColour=mix(vec3(.025,.105,.125),vec3(.095,.19,.155),uwShallow);
      uwColour*=.88+.24*uwCloud;
      float uwStreak=uwWaterNoise(vec2(dot(uwWaterXY,uwCross)/2.8,dot(uwWaterXY,uwFlow)/24.0));
      uwColour*=.94+.12*uwStreak;
      // Sparse near-bank disturbance, never a continuous white foam border.
      float uwEdge=smoothstep(.94,1.0,uwRiver.b)*smoothstep(.68,.88,uwWaterNoise(uwWaterXY/3.0));
      uwColour=mix(uwColour,vec3(.24,.30,.24),uwEdge*.20);
      diffuseColor.rgb=mix(diffuseColor.rgb,uwColour,clamp(uwWaterStrength,0.0,1.0));`);
    shader.fragmentShader=shader.fragmentShader.replace('#include <normal_fragment_maps>',`#include <normal_fragment_maps>
      vec2 uwSlope=uwRipple(uwWaterXY,uwFlow,.9,.012,1.2)
        +uwRipple(uwWaterXY,normalize(uwFlow+uwCross*.4),6.7,.035,2.7)
        +uwRipple(uwWaterXY,normalize(uwFlow-uwCross*.3),17.3,.04,.3);
      if(dot(normal,mat3(viewMatrix)*vec3(0,0,1))>.5)
        normal=normalize(mat3(viewMatrix)*vec3(-uwSlope*uwWaterStrength,1.0));`);
    shader.fragmentShader=shader.fragmentShader.replace('#include <clearcoat_normal_fragment_maps>',`#include <clearcoat_normal_fragment_maps>
      #ifdef USE_CLEARCOAT
        clearcoatNormal=normal;
      #endif`);
    shader.fragmentShader=shader.fragmentShader.replace('#include <roughnessmap_fragment>',`#include <roughnessmap_fragment>
      roughnessFactor=mix(roughnessFactor,.30+.09*uwShallow+.045*uwCloud,clamp(uwWaterStrength,0.0,1.0));`);
  };
  material.customProgramCacheKey=()=> 'cityg-river-surface-v1';
  // clearGroup/context-loss dispose the material: release its private sampler
  // too. No global texture cache is populated by this procedural field.
  material.addEventListener('dispose',()=>plan.texture.dispose());
  material.userData.riverSurface=true;
  return true;
}
