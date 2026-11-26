import {DataUtils, HalfFloatType, Euler, Vector3, BufferGeometry, Float32BufferAttribute,
  Mesh, MeshStandardMaterial, Color, ShaderMaterial, PlaneGeometry, Matrix4} from 'three';

// Visual backdrop only. The central hole preserves the city's real terrain and
// river; opaque outskirts hide the lower hemisphere of a pure-sky HDRI.
export function createHorizonGround() {
  const mesh = new Mesh(new BufferGeometry(), new MeshStandardMaterial({
    color:0xa5ada2, roughness:1, fog:false,
  }));
  const haze = {
    start:{value:800}, end:{value:2400}, color:{value:new Color()},
  };
  mesh.userData.haze = haze;
  mesh.material.onBeforeCompile = shader => {
    Object.assign(shader.uniforms, {
      citygHorizonStart:haze.start, citygHorizonEnd:haze.end, citygHorizonColor:haze.color,
    });
    shader.vertexShader = 'varying vec3 vCitygHorizonWorld;\n' + shader.vertexShader
      .replace('#include <worldpos_vertex>',
        '#include <worldpos_vertex>\nvCitygHorizonWorld=(modelMatrix*vec4(transformed,1.0)).xyz;');
    shader.fragmentShader = `varying vec3 vCitygHorizonWorld;
uniform float citygHorizonStart;
uniform float citygHorizonEnd;
uniform vec3 citygHorizonColor;
` + shader.fragmentShader.replace('#include <opaque_fragment>', `
float horizonDistance=length(vCitygHorizonWorld.xy-cameraPosition.xy);
float horizonHaze=smoothstep(citygHorizonStart,citygHorizonEnd,horizonDistance);
outgoingLight=mix(outgoingLight,citygHorizonColor,horizonHaze);
#include <opaque_fragment>`);
  };
  mesh.material.customProgramCacheKey = () => 'opaque-horizontal-horizon-v1';
  mesh.visible = false;
  mesh.receiveShadow = true;
  // Beyond the finite skirt / far plane, the lower hemisphere is haze, NOT
  // another blue sky. A screen-space backdrop avoids enormous ground triangles
  // and keeps the city's near/far planes and depth precision unchanged.
  const backdrop = new Mesh(new PlaneGeometry(2,2), new ShaderMaterial({
    // Render at background depth: a narrow horizon veil must never wash out
    // foreground buildings. Transparent ordering also precedes water/glass.
    transparent:true, depthTest:true, depthWrite:false, uniforms:{
      hazeColor:haze.color, inverseProjection:{value:new Matrix4()},
      cameraWorld:{value:new Matrix4()}, aboveGround:{value:1},
    },
    vertexShader:`varying vec2 skyNdc;
void main() { skyNdc=position.xy; gl_Position=vec4(position.xy,1.0,1.0); }`,
    fragmentShader:`varying vec2 skyNdc;
uniform mat4 inverseProjection;
uniform mat4 cameraWorld;
uniform vec3 hazeColor;
uniform float aboveGround;
void main() {
  vec4 viewRay=inverseProjection*vec4(skyNdc,1.0,1.0);
  vec3 worldRay=normalize((cameraWorld*vec4(viewRay.xyz,0.0)).xyz);
  // About four degrees of atmospheric transition above the true horizon,
  // retaining the original HDR everywhere else (no sharp backdrop seam).
  float veil=1.0-smoothstep(0.0,0.07,worldRay.z);
  if (veil<=0.0 || aboveGround<0.5) discard;
  gl_FragColor=vec4(hazeColor,veil);
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`,
  }));
  backdrop.renderOrder=-1000;
  backdrop.frustumCulled=false;
  backdrop.onBeforeRender=(_renderer,_scene,camera)=>{
    backdrop.material.uniforms.inverseProjection.value.copy(camera.projectionMatrixInverse);
    backdrop.material.uniforms.cameraWorld.value.copy(camera.matrixWorld);
    backdrop.material.uniforms.aboveGround.value=camera.matrixWorld.elements[14]>=mesh.position.z ? 1 : 0;
  };
  mesh.add(backdrop);
  return mesh;
}

export function configureHorizonGround(mesh, ground, material, extent, horizon, intensity) {
  mesh.material.color.setRGB(...(material?.display_color || [.4,.45,.4]));
  mesh.material.roughness=material?.roughness ?? 1;
  mesh.material.metalness=material?.metallic ?? 0;
  const haze=mesh.userData.haze;
  haze.start.value=Math.max(400,extent*.8);
  haze.end.value=Math.max(1200,extent*2.5);
  // Linear HDR color: blend before tone mapping, using the same exposure as sky.
  haze.color.value.setRGB(...horizon).multiplyScalar(intensity);
  mesh.position.set(ground.center.x,ground.center.y,ground.center.z+ground.size.z/2-.025);
  const reach=Math.max(10000,extent*40), key=`${ground.size.x},${ground.size.y},${reach}`;
  if (mesh.userData.key !== key) {
    mesh.geometry.dispose();
    mesh.geometry=horizonGeometry(ground.size.x,ground.size.y,reach);
    mesh.userData.key=key;
  }
  mesh.rotation.z=(ground.rotation_z_deg || 0)*Math.PI/180;
  mesh.visible=true;
}

export function horizonGeometry(width, depth, reach) {
  const x=width/2,y=depth/2,r=reach;
  const rectangles=[[-x-r,-y-r,-x,y+r],[x,-y-r,x+r,y+r],[-x,-y-r,x,-y],[-x,y,x,y+r]];
  const vertices=[],indices=[];
  for (const [a,b,c,d] of rectangles) {
    const n=vertices.length/3;
    vertices.push(a,b,0,c,b,0,c,d,0,a,d,0);
    indices.push(n,n+1,n+2,n,n+2,n+3);
  }
  const geometry=new BufferGeometry();
  geometry.setAttribute('position',new Float32BufferAttribute(vertices,3));
  geometry.setIndex(indices);geometry.computeVertexNormals();
  return geometry;
}

export function skyAllowed(mode, daylight, profile, selected, presets) {
  return daylight && !['floor','floor_plan','room'].includes(mode)
    && profile.environment && selected !== 'none' && Boolean(presets?.[selected]);
}

// RGBE images are stored top-to-bottom, flipped vertically on texture upload.
// Three's equirectangular convention is Y-up; CityG's scene is Z-up.
export function pixelDirection(x, y, width, height) {
  const longitude=((x+.5)/width-.5)*Math.PI*2;
  const latitude=(.5-(y+.5)/height)*Math.PI;
  return new Vector3(Math.cos(latitude)*Math.cos(longitude),
    -Math.cos(latitude)*Math.sin(longitude), Math.sin(latitude));
}

export function analyzeSky(texture) {
  const {data,width,height}=texture.image;
  const stride=data.length/(width*height);
  const value=i=>texture.type===HalfFloatType ? DataUtils.fromHalfFloat(data[i]) : data[i];
  let brightest=-1, sun=pixelDirection(width/2,height/4,width,height);
  // Upper hemisphere only: never mistake the mirrored lower sky for the sun.
  for(let y=0;y<height*.48;y+=2) for(let x=0;x<width;x+=2) {
    const i=(y*width+x)*stride;
    const l=value(i)*.2126+value(i+1)*.7152+value(i+2)*.0722;
    if(l>brightest) {brightest=l;sun=pixelDirection(x,y,width,height);}
  }
  const horizon=[0,0,0];let n=0;
  for(let y=Math.floor(height*.46);y<height*.49;y+=4) for(let x=0;x<width;x+=16) {
    const i=(y*width+x)*stride;
    for(let c=0;c<3;c++) horizon[c]+=value(i+c);
    n++;
  }
  return {sun, horizon:horizon.map(v=>v/Math.max(1,n))};
}

export function skyOrientation(analysis, azimuthDeg=215, offsetDeg=0) {
  const yaw=(azimuthDeg+offsetDeg)*Math.PI/180-Math.atan2(analysis.sun.y,analysis.sun.x);
  return {rotation:new Euler(Math.PI/2,0,yaw,'XYZ'),
    sun:analysis.sun.clone().applyAxisAngle(new Vector3(0,0,1),yaw)};
}
