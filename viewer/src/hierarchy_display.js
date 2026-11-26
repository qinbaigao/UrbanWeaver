// Display-only scope. Never edits canonical geometry or shared asset materials.
export function validateHierarchyDisplay(value, entities) {
  if (!value) return null;
  const building = entities.get(value.building_id);
  const floor = entities.get(value.floor_id);
  if (building?.type !== 'building' || floor?.type !== 'floor'
      || floor.buildingId !== value.building_id) {
    throw new Error('Hierarchy display requires a real building and one of its floors');
  }
  const opacity = value.shell_opacity ?? 0.12;
  if (!Number.isFinite(opacity) || opacity < 0 || opacity > 1) throw new Error('Invalid shell opacity');
  if (value.cut_above_m != null && !Number.isFinite(value.cut_above_m)) throw new Error('Invalid cut elevation');
  return {building_id: value.building_id, floor_id: value.floor_id,
    shell_opacity: opacity, cut_above_m: value.cut_above_m ?? null};
}

export function hierarchyShell(display, indexed, layerType) {
  return Boolean(display && layerType === 'building_shell'
    && indexed?.buildingId === display.building_id);
}

export function hierarchyVisible(display, indexed, layerType, belongsToFloor) {
  if (!display) return null;
  if (['roads', 'building_shell', 'district', 'root'].includes(layerType)) return true;
  return indexed?.buildingId === display.building_id && belongsToFloor;
}
