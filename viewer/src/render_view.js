// Small, renderer-independent handoff; no scene serialization or image capture.
export function renderViewDocument({camera, target, viewport, sceneRef, selection,
  visibility, lighting, replay = null, assetStatus = null, createdAt = new Date().toISOString()}) {
  if (!camera.isPerspectiveCamera) throw new Error('Render view export requires a perspective camera');
  if (![viewport.width, viewport.height, camera.aspect].every(v => Number.isFinite(v) && v > 0)) {
    throw new Error('Cannot export a hidden or zero-sized viewport');
  }
  camera.updateMatrixWorld(true);
  const forward = [0, 0, -1];
  // Matrix/quaternion preserve orientation even if an orbit target is stale.
  const result = {
    schema: 'cityg.render_view', schema_version: 1, created_at: createdAt,
    coordinate_system: {space: 'scene_world', up_axis: 'Z', units: 'meters',
      handedness: 'right', camera_forward_local: forward, camera_up_local: [0, 1, 0],
      matrix_layout: 'column_major', quaternion_order: 'xyzw'},
    scene_ref: sceneRef,
    camera: {projection: 'perspective', camera_position: camera.position.toArray(),
      look_at: target.toArray(), up: camera.up.toArray(),
      quaternion_xyzw: camera.quaternion.toArray(), matrix_world: camera.matrixWorld.toArray(),
      projection_matrix: camera.projectionMatrix.toArray(),
      vertical_fov_deg: camera.getEffectiveFOV(), nominal_vertical_fov_deg: camera.fov,
      zoom: camera.zoom, aspect: camera.aspect, near_clip_m: camera.near, far_clip_m: camera.far,
      film_gauge_mm: camera.filmGauge, film_offset_mm: camera.filmOffset, view_offset: camera.view},
    viewport: {width_css_px: viewport.width, height_css_px: viewport.height,
      drawing_buffer_width_px: viewport.bufferWidth, drawing_buffer_height_px: viewport.bufferHeight},
    selection, visibility, lighting, replay, asset_status: assetStatus,
    render_contract: {preserve_aspect: true, preserve_camera_orientation: true,
      fov_convention: 'vertical; effective FOV already includes zoom',
      scope: 'Camera and display-state handoff, not a scene package or an automatic Cycles render',
      note: 'Use the matching scene package. Do not replace the saved aspect with the output window aspect.'},
  };
  // Freeze the click-time state; later UI changes must not mutate this record.
  return JSON.parse(JSON.stringify(result));
}

export function renderViewFilename(doc) {
  const safe = value => String(value || 'scene').replace(/[^a-zA-Z0-9_-]/g, '_').slice(0, 100);
  // Hierarchy selectors may retain a previous room while viewing the whole city.
  // Name the handoff after the actual display scope, not that stale selection.
  const mode = doc.visibility.mode;
  const scope = {room:doc.selection.room_id, floor:doc.selection.floor_id,
    building:doc.selection.building_id, district:doc.selection.district_id}[mode] || mode;
  return `${safe(doc.scene_ref.city_id)}_${safe(scope)}_${safe(doc.created_at)}_render_view.json`;
}
