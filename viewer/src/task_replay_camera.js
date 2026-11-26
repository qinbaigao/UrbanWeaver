// Trace coordinates are Z-up; robot_base is the occupancy center, 0.75 m
// above the floor, and yaw points along the robot's local +X (not its velocity).
export function replayCameraPose(base, yawDeg = 0, mode = 'chase', indoors = false) {
  const angle = yawDeg * Math.PI / 180, c = Math.cos(angle), s = Math.sin(angle);
  if (mode === 'chase') {
    return {
      position: [base[0] - .8*c, base[1] - .8*s, base[2] + 1.35],
      target: [base[0] + 1.5*c, base[1] + 1.5*s, base[2] + .35],
    };
  }
  if (mode === 'robot') {
    return {
      position: [base[0] + 2.4*c + 2.4*s, base[1] + 2.4*s - 2.4*c, base[2] + 2.2],
      target: [base[0] + .3*c, base[1] + .3*s, base[2] + .15],
    };
  }
  return {
    position: [base[0] + (indoors ? 1.8 : 8), base[1] - (indoors ? 2.4 : 10), base[2] + (indoors ? 7 : 9)],
    target: [...base],
  };
}
