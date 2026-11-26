// Same explicit/legacy hinge convention as geometry/door_kinematics.py.
export function doorPose(primitive, openDegrees) {
  const {size, center, metadata = {}} = primitive;
  const hinge = metadata.hinge_local_m ?? (size.x >= size.y
    ? [-size.x / 2, 0, 0] : [0, -size.y / 2, 0]);
  if (hinge.length !== 3 || !hinge.every(Number.isFinite)
      || Math.abs(hinge[2]) > 1e-9 || Math.abs(hinge[0]) > size.x / 2 + 1e-9
      || Math.abs(hinge[1]) > size.y / 2 + 1e-9) throw new Error('Invalid door hinge');
  const yaw = (primitive.rotation_z_deg || 0) * Math.PI / 180;
  const angle = yaw + openDegrees * Math.PI / 180;
  const hx = center.x + Math.cos(yaw) * hinge[0] - Math.sin(yaw) * hinge[1];
  const hy = center.y + Math.sin(yaw) * hinge[0] + Math.cos(yaw) * hinge[1];
  return {x: hx - Math.cos(angle) * hinge[0] + Math.sin(angle) * hinge[1],
    y: hy - Math.sin(angle) * hinge[0] - Math.cos(angle) * hinge[1], z: center.z, angle};
}
