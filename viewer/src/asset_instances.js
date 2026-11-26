import * as THREE from 'three';

// City/district IDs in observation requests provide context, not a request
// to decode every descendant GLB during a local inspection.
export function matchesLocalAssetTarget(lineage, targetIds, entities, metadata = {}) {
  const bindings = new Set([...lineage, metadata.landscape_site].filter(Boolean));
  return [...targetIds].some((id) => !['city', 'district'].includes(entities.get(id)?.type)
    && bindings.has(id));
}

// Static repeated GLBs share mesh geometry/materials and retain picking IDs.
// Skins, morph targets and authored instancing keep the existing clone path.
export function instanceAsset(template, entries, matrixForPrimitive) {
  // The legacy clone path preserves an authored root X/Y rotation while
  // replacing translation/scale/Z. Don't approximate that unusual contract.
  if (Math.abs(template.rotation.x) > 1e-8 || Math.abs(template.rotation.y) > 1e-8
      || template.matrixAutoUpdate === false) return null;
  const nodes = [];
  let unsupported = false;
  template.updateMatrixWorld(true);
  template.traverseVisible((node) => {
    if (node.isSkinnedMesh || node.isInstancedMesh || node.morphTargetInfluences?.length) unsupported = true;
    if (node.isMesh) nodes.push(node);
  });
  if (unsupported || !nodes.length) return null;
  const inverseRoot = template.matrixWorld.clone().invert();
  return nodes.map((node) => {
    const mesh = new THREE.InstancedMesh(node.geometry, node.material, entries.length);
    const local = new THREE.Matrix4().multiplyMatrices(inverseRoot, node.matrixWorld);
    entries.forEach((entry, i) => mesh.setMatrixAt(i, matrixForPrimitive(entry).multiply(local)));
    mesh.instanceMatrix.needsUpdate = true;
    mesh.computeBoundingSphere();
    mesh.userData.entries = entries;
    mesh.userData.citygAssetBatch = true;
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    return mesh;
  });
}
