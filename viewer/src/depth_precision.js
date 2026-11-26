// A street/room near plane carried into an aerial orbit wastes most depth
// precision. Keep the entire skyline in front of the near plane, and tighten
// it continuously as the camera rises; never use a fixed city-wide cutoff.
export function aerialNearPlane(position, target, sceneTop, mode) {
  if (!['overview','full','building'].includes(mode)) return null;
  const distance=Math.hypot(position.x-target.x,position.y-target.y,position.z-target.z);
  const clearance=Math.max(0,position.z-sceneTop);
  return Math.max(0.03,Math.min(64,distance/50,clearance/8));
}
