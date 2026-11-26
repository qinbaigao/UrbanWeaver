import {Box3, Frustum, Matrix4, Vector3} from 'three';

export const screenQuality = profile => ['interactive', 'presentation', 'snapshot'].includes(profile);

export function primitiveBounds(p) {
  const a = (p.rotation_z_deg || 0) * Math.PI / 180;
  const x = (Math.abs(Math.cos(a))*p.size.x + Math.abs(Math.sin(a))*p.size.y)/2;
  const y = (Math.abs(Math.sin(a))*p.size.x + Math.abs(Math.cos(a))*p.size.y)/2;
  return new Box3(new Vector3(p.center.x-x, p.center.y-y, p.center.z-p.size.z/2),
    new Vector3(p.center.x+x, p.center.y+y, p.center.z+p.size.z/2));
}

export function chunkBounds(chunk) {
  if (chunk.bounds3d) return new Box3(new Vector3(...chunk.bounds3d.slice(0,3)), new Vector3(...chunk.bounds3d.slice(3)));
  // Old portable exports did not record height. Conservative, never assume z=0.
  const [x,y,X,Y] = chunk.bounds;
  return new Box3(new Vector3(x,y,-100), new Vector3(X,Y,1000));
}

// Conservative screen-space estimate, including near-plane crossings. No
// occlusion guesses: an AABB behind a building is not proof it is invisible.
export function screenContext(camera, height, sunDirection = [-250,-180,420]) {
  camera.updateMatrixWorld();
  const view = camera.matrixWorldInverse.clone();
  const frustum = new Frustum().setFromProjectionMatrix(new Matrix4().multiplyMatrices(camera.projectionMatrix, view));
  const focal = height * camera.projectionMatrix.elements[5] / 2;
  const pixels = box => {
    const radius = box.getSize(new Vector3()).length()/2;
    const depth = -box.getCenter(new Vector3()).applyMatrix4(view).z;
    if (depth-radius <= camera.near) return Infinity;
    return 2*radius*focal/(depth-radius);
  };
  return {height, measure(box) {
    const visible = frustum.intersectsBox(box);
    let shadow = false, shadowPixels = 0;
    // Retain off-screen casters whose sun projection can reach visible ground.
    // Conservative swept volume also covers intermediate-height receivers.
    if (!visible && sunDirection[2] > 0 && box.max.z > 0) {
      const sweep = box.clone();
      const h = Math.max(0, box.max.z);
      const shift = new Vector3(-sunDirection[0]*h/sunDirection[2], -sunDirection[1]*h/sunDirection[2], -h);
      sweep.union(box.clone().translate(shift));
      shadow = frustum.intersectsBox(sweep);
      if (shadow) shadowPixels = pixels(sweep);
    }
    return {visible, shadow, pixels: visible ? pixels(box) : shadowPixels};
  }};
}

export function chooseAssetLod(assetId, pixels, catalog = {}) {
  // A missing derivative always falls back to the original textured asset.
  // max_pixels is an upper bound, so large/near objects always use originals.
  const levels = [...(catalog[assetId] || [])].sort((a,b) => a.max_pixels-b.max_pixels);
  return levels.find(level => pixels <= level.max_pixels)?.asset_id || assetId;
}

export function spatialBatch(p, tileSize = 40) {
  return `${Math.floor(p.center.x/tileSize)},${Math.floor(p.center.y/tileSize)}`;
}

// A fitted shadow camera depends on BOTH target and light distance. Reapplying
// a sky/theme must not reset that distance to 520m on the geometry-cache path,
// otherwise its old near/far range no longer contains the receivers/casters.
export function aimDirectionalLight(light, direction) {
  const distance=Math.max(1,light.position.distanceTo(light.target.position));
  light.position.copy(light.target.position).addScaledVector(direction.clone().normalize(),distance);
}

// Allocate shadow texels to the retained geometry rather than a fixed 1400m
// square around the world origin. Include the groundward shadow sweep so
// near-view sharpness does not clip the shadows of off-screen casters.
export function fitDirectionalShadow(light, bounds) {
  if (bounds.isEmpty()) return;
  const direction = light.position.clone().sub(light.target.position).normalize();
  if (direction.z <= 0) return;
  const fitted = bounds.clone();
  const height = Math.max(0, bounds.max.z);
  fitted.union(bounds.clone().translate(new Vector3(-direction.x*height/direction.z,
    -direction.y*height/direction.z, -height)));
  const center = fitted.getCenter(new Vector3());
  const radius = Math.max(5, fitted.getSize(new Vector3()).length()/2);
  light.target.position.copy(center);
  light.position.copy(center).addScaledVector(direction, radius*2+10);
  light.updateMatrixWorld();light.target.updateMatrixWorld();
  const c = light.shadow.camera;
  c.position.copy(light.position);c.lookAt(center);c.updateMatrixWorld();
  const local = fitted.clone().applyMatrix4(c.matrixWorldInverse);
  const pad = Math.max(1,radius*.03);
  c.left=local.min.x-pad;c.right=local.max.x+pad;
  c.bottom=local.min.y-pad;c.top=local.max.y+pad;
  c.near=Math.max(.1,-local.max.z-pad);c.far=-local.min.z+pad;
  c.updateProjectionMatrix();
}
