import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { DRACOLoader } from "three/addons/loaders/DRACOLoader.js";
import { KTX2Loader } from "three/addons/loaders/KTX2Loader.js";
import { MeshoptDecoder } from "three/addons/libs/meshopt_decoder.module.js";

const params = new URLSearchParams(location.search);
const assetUrl = params.get("asset");
const assetId = params.get("id") || "unknown_asset";
const category = params.get("category") || "unknown";
const source = params.get("source") || "unknown";
const frontAxis = params.get("front") || "+Y";
const upAxis = params.get("up") || "+Z";
const viewMode = params.get("view") || "four_view";
const dimensions = params.get("dimensions") || "unscaled";

const canvas = document.querySelector("#preview");
const frame = document.querySelector("#frame");
const errorBox = document.querySelector("#error");
const planar = viewMode === "four_view_planar";
const viewLabels = planar
  ? ["FRONT OBLIQUE", "RIGHT OBLIQUE", "REAR OBLIQUE", "TOP"]
  : ["FRONT", "RIGHT", "REAR", "LEFT"];
for (const [id, label] of ["front", "right", "rear", "left"].entries()) {
  document.querySelector(`#${label}-label`).textContent = `${viewLabels[id]} · FRONT ${frontAxis}`;
}
document.querySelector("#meta").textContent = `${assetId} · ${category} · ${source} · target ${dimensions}`;
window.citygAssetPreview = { ready: false, error: null };

function axisVector(axis) {
  const sign = String(axis).startsWith("-") ? -1 : 1;
  const name = String(axis).slice(-1).toUpperCase();
  if (name === "X") return new THREE.Vector3(sign, 0, 0);
  if (name === "Y") return new THREE.Vector3(0, sign, 0);
  return new THREE.Vector3(0, 0, sign);
}

function disposeMaterial(material) {
  if (!material) return;
  for (const key of ["map", "normalMap", "roughnessMap", "metalnessMap", "aoMap", "emissiveMap"]) {
    if (material[key]) {
      material[key].wrapS = THREE.RepeatWrapping;
      material[key].wrapT = THREE.RepeatWrapping;
    }
  }
}

async function main() {
  if (!assetUrl) throw new Error("Missing asset URL");
  const renderer = new THREE.WebGLRenderer({
    canvas,
    antialias: true,
    alpha: false,
    preserveDrawingBuffer: true,
  });
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.setPixelRatio(1);
  renderer.setScissorTest(true);

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0xe8eeeb);
  scene.add(new THREE.HemisphereLight(0xffffff, 0x66756f, 2.25));
  const key = new THREE.DirectionalLight(0xfff7e8, 3.4);
  key.position.set(4, -5, 8);
  key.castShadow = true;
  key.shadow.mapSize.set(1024, 1024);
  scene.add(key);
  const fill = new THREE.DirectionalLight(0xc9ddff, 1.15);
  fill.position.set(-5, 4, 3);
  scene.add(fill);

  // Review compressed upstream assets without installing converters or fetching
  // decoder code from a CDN. These decoders come from the existing Three package.
  const draco = new DRACOLoader().setDecoderPath("/viewer/node_modules/three/examples/jsm/libs/draco/gltf/");
  const ktx2 = new KTX2Loader().setTranscoderPath("/viewer/node_modules/three/examples/jsm/libs/basis/").detectSupport(renderer);
  let gltf;
  try {
    gltf = await new GLTFLoader().setDRACOLoader(draco).setKTX2Loader(ktx2)
      .setMeshoptDecoder(MeshoptDecoder).loadAsync(assetUrl);
  } finally {
    draco.dispose();
    ktx2.dispose();
  }
  const asset = gltf.scene;
  // Registry GLBs use independently normalized unit bounds. Restore physical
  // proportions, just as the scene Viewer does, before framing the four views.
  // Otherwise a long bench, a thin lamp and a tree all appear cube-shaped.
  const physicalDimensions = JSON.parse(params.get("dimensions_m") || "null");
  if (Array.isArray(physicalDimensions) && physicalDimensions.length === 3 &&
      physicalDimensions.every((value) => Number.isFinite(value) && value > 0)) {
    const sourceExtent = new THREE.Box3().setFromObject(asset).getSize(new THREE.Vector3());
    if (Math.min(sourceExtent.x, sourceExtent.y, sourceExtent.z) <= 0) {
      throw new Error("Asset has degenerate bounds");
    }
    asset.scale.multiply(new THREE.Vector3(
      physicalDimensions[0] / sourceExtent.x,
      physicalDimensions[1] / sourceExtent.y,
      physicalDimensions[2] / sourceExtent.z,
    ));
    asset.updateMatrixWorld(true);
  }
  asset.traverse((node) => {
    if (!node.isMesh) return;
    node.castShadow = true;
    node.receiveShadow = true;
    if (Array.isArray(node.material)) node.material.forEach(disposeMaterial);
    else disposeMaterial(node.material);
  });
  scene.add(asset);

  const up = axisVector(upAxis).normalize();
  const front = axisVector(frontAxis).normalize();
  if (Math.abs(up.dot(front)) > 0.5) throw new Error("Front axis cannot match up axis");
  const right = new THREE.Vector3().crossVectors(up, front).normalize();

  let bounds = new THREE.Box3().setFromObject(asset);
  if (bounds.isEmpty()) throw new Error("Asset has empty bounds");
  const center = bounds.getCenter(new THREE.Vector3());
  const lowAlongUp = Math.min(...[
    new THREE.Vector3(bounds.min.x, bounds.min.y, bounds.min.z),
    new THREE.Vector3(bounds.min.x, bounds.min.y, bounds.max.z),
    new THREE.Vector3(bounds.min.x, bounds.max.y, bounds.min.z),
    new THREE.Vector3(bounds.min.x, bounds.max.y, bounds.max.z),
    new THREE.Vector3(bounds.max.x, bounds.min.y, bounds.min.z),
    new THREE.Vector3(bounds.max.x, bounds.min.y, bounds.max.z),
    new THREE.Vector3(bounds.max.x, bounds.max.y, bounds.min.z),
    new THREE.Vector3(bounds.max.x, bounds.max.y, bounds.max.z),
  ].map((point) => point.dot(up)));
  const centered = center.clone().sub(up.clone().multiplyScalar(center.dot(up)));
  asset.position.sub(centered).sub(up.clone().multiplyScalar(lowAlongUp));
  const groundFraction = Number(params.get("ground_anchor_fraction") || 0);
  if (!Number.isFinite(groundFraction) || groundFraction < 0 || groundFraction > 1) {
    throw new Error("Invalid ground anchor");
  }
  const sourceSize = bounds.getSize(new THREE.Vector3());
  const upExtent = Math.abs(up.x) * sourceSize.x + Math.abs(up.y) * sourceSize.y + Math.abs(up.z) * sourceSize.z;
  asset.position.sub(up.clone().multiplyScalar(groundFraction * upExtent));
  asset.updateMatrixWorld(true);
  bounds = new THREE.Box3().setFromObject(asset);
  const size = bounds.getSize(new THREE.Vector3());
  const maxSize = Math.max(size.x, size.y, size.z, 0.2);
  // Source car paint showed self-shadow acne at grazing angles. Scale the
  // review-only bias to the physical bounds, without editing source materials.
  key.shadow.normalBias = maxSize * 0.002;
  key.shadow.bias = -0.0001;

  const ground = new THREE.Mesh(
    new THREE.PlaneGeometry(maxSize * 5.5, maxSize * 5.5),
    new THREE.MeshStandardMaterial({ color: 0xcbd5d1, roughness: 0.96 })
  );
  ground.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), up);
  ground.position.copy(up).multiplyScalar(-0.006 * maxSize);
  ground.receiveShadow = true;
  scene.add(ground);

  const grid = new THREE.GridHelper(maxSize * 5.5, 18, 0x91a29c, 0xb9c6c1);
  grid.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), up);
  grid.position.copy(up).multiplyScalar(0.002 * maxSize);
  scene.add(grid);

  const target = bounds.getCenter(new THREE.Vector3());
  const elevation = planar ? 0.58 : 0.08;
  const viewDirections = planar
    ? [
        front.clone().add(up.clone().multiplyScalar(elevation)),
        right.clone().add(up.clone().multiplyScalar(elevation)),
        front.clone().negate().add(up.clone().multiplyScalar(elevation)),
        up.clone().add(front.clone().multiplyScalar(0.08)),
      ]
    : [
        front.clone().add(up.clone().multiplyScalar(elevation)),
        right.clone().add(up.clone().multiplyScalar(elevation)),
        front.clone().negate().add(up.clone().multiplyScalar(elevation)),
        right.clone().negate().add(up.clone().multiplyScalar(elevation)),
      ];
  const distance = maxSize * (planar ? 3.10 : 2.82);
  const cameras = viewDirections.map((direction) => {
    const camera = new THREE.PerspectiveCamera(
      34,
      1,
      Math.max(0.001, maxSize / 1000),
      maxSize * 100
    );
    camera.position.copy(target).add(direction.normalize().multiplyScalar(distance));
    camera.up.copy(planar && direction === viewDirections[3] ? front : up);
    camera.lookAt(target);
    return camera;
  });

  function render() {
    const width = Math.max(2, frame.clientWidth);
    const height = Math.max(2, frame.clientHeight);
    renderer.setSize(width, height, false);
    const halfWidth = Math.floor(width / 2);
    const halfHeight = Math.floor(height / 2);
    const cells = [
      [0, halfHeight, halfWidth, height - halfHeight],
      [halfWidth, halfHeight, width - halfWidth, height - halfHeight],
      [0, 0, halfWidth, halfHeight],
      [halfWidth, 0, width - halfWidth, halfHeight],
    ];
    for (let index = 0; index < cameras.length; index += 1) {
      const [x, y, cellWidth, cellHeight] = cells[index];
      const camera = cameras[index];
      camera.aspect = cellWidth / cellHeight;
      camera.updateProjectionMatrix();
      renderer.setViewport(x, y, cellWidth, cellHeight);
      renderer.setScissor(x, y, cellWidth, cellHeight);
      renderer.render(scene, camera);
    }
  }
  render();
  await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  render();
  window.citygAssetPreview = {
    ready: true,
    error: null,
    front_axis: frontAxis,
    up_axis: upAxis,
    view_mode: viewMode,
    rendered_extent: [size.x, size.y, size.z],
  };
}

main().catch((error) => {
  console.error(error);
  errorBox.style.display = "grid";
  errorBox.textContent = error.message || String(error);
  window.citygAssetPreview = { ready: false, error: error.message || String(error) };
});
