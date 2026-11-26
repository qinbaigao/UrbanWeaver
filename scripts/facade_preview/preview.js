import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

const params = new URLSearchParams(location.search);
const assetUrl = params.get('asset');
const selectedNode = params.get('node');
const frontAxis = params.get('front') || '+Z';
const alignmentMode = params.get('mode') || 'front_normal';
const canvas = document.querySelector('#preview');
const frame = document.querySelector('#preview-frame');
const errorBox = document.querySelector('#error');
document.querySelector('#front-label').textContent = `${alignmentMode.replaceAll('_', ' ').toUpperCase()} · ${frontAxis}`;

window.facadePreview = { ready: false, error: null };

function directionForAxis(axis) {
  const sign = axis.startsWith('-') ? -1 : 1;
  const value = axis.slice(-1).toUpperCase();
  if (value === 'X') return new THREE.Vector3(sign, 0, 0);
  if (value === 'Y') return new THREE.Vector3(0, sign, 0);
  return new THREE.Vector3(0, 0, sign);
}

function findNode(root, name) {
  let match = null;
  root.traverse((node) => {
    if (!match && String(node.name || '').trim() === String(name || '').trim()) match = node;
  });
  return match;
}

function humanReference() {
  const group = new THREE.Group();
  const material = new THREE.MeshStandardMaterial({ color: 0x63756f, roughness: .85 });
  const body = new THREE.Mesh(new THREE.CapsuleGeometry(.18, 1.05, 5, 10), material);
  body.position.y = .87;
  const head = new THREE.Mesh(new THREE.SphereGeometry(.13, 16, 10), material);
  head.position.y = 1.62;
  group.add(body, head);
  group.userData.heightM = 1.75;
  return group;
}

function cameraFor(direction, right, target, distance, oblique = false) {
  const camera = new THREE.PerspectiveCamera(38, 1, .01, Math.max(1000, distance * 20));
  const vector = oblique
    ? direction.clone().add(right.clone().multiplyScalar(.72)).normalize()
    : direction.clone();
  camera.position.copy(target).add(vector.multiplyScalar(distance));
  camera.position.y += distance * (oblique ? .30 : .08);
  camera.up.set(0, 1, 0);
  camera.lookAt(target);
  return camera;
}

async function main() {
  if (!assetUrl) throw new Error('Missing asset query parameter');
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false, preserveDrawingBuffer: true });
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.12;
  renderer.setPixelRatio(1);
  renderer.setScissorTest(true);

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0xdfe7e3);
  scene.add(new THREE.HemisphereLight(0xffffff, 0x607169, 2.5));
  const key = new THREE.DirectionalLight(0xffffff, 3.0);
  key.position.set(4, 8, 5);
  scene.add(key);
  const fill = new THREE.DirectionalLight(0xbad9ff, 1.2);
  fill.position.set(-5, 3, -4);
  scene.add(fill);

  const gltf = await new GLTFLoader().loadAsync(assetUrl);
  const selected = selectedNode ? findNode(gltf.scene, selectedNode) : gltf.scene;
  if (!selected) throw new Error(`Node not found: ${selectedNode}`);
  const asset = selected.clone(true);
  scene.add(asset);

  let bounds = new THREE.Box3().setFromObject(asset);
  if (bounds.isEmpty()) throw new Error('Selected asset has empty bounds');
  const center = bounds.getCenter(new THREE.Vector3());
  asset.position.x -= center.x;
  asset.position.z -= center.z;
  asset.position.y -= bounds.min.y;
  asset.updateMatrixWorld(true);
  bounds = new THREE.Box3().setFromObject(asset);
  const size = bounds.getSize(new THREE.Vector3());

  const front = directionForAxis(frontAxis);
  if (Math.abs(front.y) > .5) throw new Error('Facade front axis cannot be vertical');
  const right = new THREE.Vector3(front.z, 0, -front.x).normalize();
  const figure = humanReference();
  const horizontalExtent = Math.abs(right.x) * size.x + Math.abs(right.z) * size.z;
  figure.position.copy(right).multiplyScalar(horizontalExtent * .5 + .55);
  scene.add(figure);

  const fullBounds = new THREE.Box3().setFromObject(asset).expandByObject(figure);
  const fullSize = fullBounds.getSize(new THREE.Vector3());
  const maxSize = Math.max(fullSize.x, fullSize.y, fullSize.z, 1.75);
  const target = new THREE.Vector3(0, Math.max(.75, fullBounds.max.y * .48), 0);
  const distance = Math.max(3.5, maxSize * 2.5);
  const frontCamera = cameraFor(front, right, target, distance, false);
  const obliqueCamera = cameraFor(front, right, target, distance, true);

  const gridSize = Math.max(6, Math.ceil(maxSize * 2.2));
  const grid = new THREE.GridHelper(gridSize, gridSize, 0x73857f, 0xaebbb7);
  scene.add(grid);
  const axes = new THREE.AxesHelper(Math.max(.8, maxSize * .28));
  axes.position.y = .015;
  scene.add(axes);
  const arrow = new THREE.ArrowHelper(front, new THREE.Vector3(0, .06, 0), Math.max(.8, maxSize * .35), 0xe23b35, .22, .13);
  scene.add(arrow);

  function render() {
    const width = Math.max(2, frame.clientWidth);
    const height = Math.max(2, frame.clientHeight);
    renderer.setSize(width, height, false);
    const half = Math.floor(width / 2);
    for (const [camera, left, viewportWidth] of [[frontCamera, 0, half], [obliqueCamera, half, width - half]]) {
      camera.aspect = viewportWidth / height;
      camera.updateProjectionMatrix();
      renderer.setViewport(left, 0, viewportWidth, height);
      renderer.setScissor(left, 0, viewportWidth, height);
      renderer.render(scene, camera);
    }
  }
  render();
  window.addEventListener('resize', render);
  await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  render();
  window.facadePreview = {
    ready: true,
    error: null,
    selected_node: selectedNode,
    source_front_axis: frontAxis,
    alignment_mode: alignmentMode,
    source_extent: [size.x, size.y, size.z],
  };
}

main().catch((error) => {
  console.error(error);
  errorBox.style.display = 'grid';
  errorBox.textContent = error.message || String(error);
  window.facadePreview = { ready: false, error: error.message || String(error) };
});
