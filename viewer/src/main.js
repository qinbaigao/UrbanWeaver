import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { RGBELoader } from "three/addons/loaders/RGBELoader.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { ProgressiveGeometry, selectDetailChunks } from "./streaming.js";
import { instanceAsset, matchesLocalAssetTarget } from "./asset_instances.js";
import { hasRoomBoundaries } from "./room_visibility.js";
import { doorPose } from "./door_kinematics.js";
import {validateHierarchyDisplay, hierarchyShell, hierarchyVisible} from './hierarchy_display.js';
import {installTaskReplay} from './task_replay.js';
import {replayCameraPose} from './task_replay_camera.js';
import {snapshotSize, canvasPng} from './snapshot.js';
import {renderViewDocument, renderViewFilename} from './render_view.js';
import {skyAllowed, analyzeSky, skyOrientation, createHorizonGround, configureHorizonGround} from './sky.js';
import {groundSurfacePlan, installGroundSurface, indexGroundEdges} from './ground_surface.js';
import {installRiverSurface} from './river_surface.js';
import {aerialNearPlane} from './depth_precision.js';
import {bindSharedTexture, disposeOwnedMap} from './texture_bindings.js';
import {AssetTemplatePool, disposeInstances, runAssetBatches, displayPixelRatio,
  textureEdgeForPixels, resizeTemplateTextures, canPresent} from './render_resources.js';
import {screenQuality, screenContext, primitiveBounds, chunkBounds, chooseAssetLod, spatialBatch, fitDirectionalShadow, aimDirectionalLight} from './screen_lod.js';
import "./style.css";

const REQUIRED_FILES = ["geometry_manifest.json", "city.json"];
const OPTIONAL_FILES = [
  "navigation.json",
  "interactions.json",
  "activation_manifest.json",
  "validation_report.json",
  "geometry_validation_report.json",
  "interaction_smoke_report.json",
  "usd_validation_report.json",
  "compile_metrics.json",
];
const LARGE_SCENE_OVERVIEW_THRESHOLD = 7000;
import {selectPrototypeCaptureAssets, outdoorCaptureCandidate} from './prototype_capture.js';

const RENDER_PROFILES = Object.freeze({
  snapshot: {
    // Full shading; only geometry precision is screen-space adaptive.
    pixelRatio: () => 1,
    shadows: true, materialTextures: true, environment: true, physicalGlass: true,
  },
  paper_capture: {
    // Full real-asset inventory, explicit frames, no costly multipass shadows.
    pixelRatio: () => 1,
    shadows: false, materialTextures: true, environment: false, physicalGlass: false,
  },
  prototype_capture: {
    // Headless prototype audit only; intentionally not exposed as a UI mode.
    // Preserve real GLBs and texture maps without multi-pass transmission.
    pixelRatio: () => 1,
    shadows: false, materialTextures: true, environment: false, physicalGlass: false,
  },
  interactive: {
    pixelRatio: () => Math.min(window.devicePixelRatio || 1, 1.5),
    shadows: true, materialTextures: true, environment: true, physicalGlass: true,
  },
  review: {
    pixelRatio: () => 1,
    shadows: false, materialTextures: false, environment: false, physicalGlass: false,
  },
  navigation: {
    // Camera-navigation profile: keep only proxy geometry and road/building
    // context.  No GLB cloning, texture IO, HDR environment, or shadows.
    pixelRatio: () => Math.min(window.devicePixelRatio || 1, 0.72),
    shadows: false, materialTextures: false, environment: false, physicalGlass: false,
  },
  presentation: {
    pixelRatio: () => Math.min(window.devicePixelRatio || 1, 2),
    shadows: true, materialTextures: true, environment: true, physicalGlass: true,
  },
  high_fidelity: {
    // Real outdoor GLBs with textured materials, but no expensive shadow map;
    // this is the balanced profile used by the opt-in overview mode.  The
    // HDR environment is intentionally disabled: its PMREM build is costly
    // in SwiftShader and does not improve the silhouette-focused overview.
    pixelRatio: () => Math.min(window.devicePixelRatio || 1, 1.35),
    shadows: false, materialTextures: true, environment: false, physicalGlass: true,
  },
});

const semanticPalette = {
  river_water: 0x287f98,
  river_bed: 0x424c37,
  river_bank: 0x809071,
  river_promenade: 0xaca795,
  riparian_green: 0x66854e,
  bridge_deck: 0x888e92,
  bridge_parapet: 0xa0a6a4,
  bridge_railing: 0x4b6468,
  bridge_abutment: 0x777d7c,
  road_surface: 0x3f5359,
  road_median: 0x8a8f87,
  bicycle_lane_surface: 0x527c73,
  median_planter: 0x6e5437,
  median_shrub: 0x4f8a4b,
  stop_line: 0xf5f0d0,
  traffic_signal: 0x253139,
  traffic_signal_red: 0xd94c3d,
  traffic_signal_green: 0x49b879,
  road_marking: 0xf3e7b2,
  curb: 0x9da5a3,
  lane_marking: 0xf3e7b2,
  crosswalk: 0xf3e7b2,
  sidewalk: 0xa8b8b2,
  floor_slab: 0xc2cac5,
  exterior_wall: 0x83d6b1,
  facade_window: 0x4e9fc2,
  curtain_wall_glass: 0x6b9eae,
  storefront_window: 0x2d7391,
  facade_frame: 0xe0d5bf,
  facade_fin: 0x3a4c55,
  facade_ground_band: 0xb16f45,
  facade_spandrel_band: 0x8c725d,
  facade_zone_band: 0x796a5c,
  mechanical_louver: 0x344044,
  window_backing: 0x263039,
  entrance_portal: 0xd08a45,
  balcony_slab: 0x9f7655,
  balcony_rail: 0x39484c,
  interior_wall: 0xf0e8d7,
  door: 0xf1a75f,
  stair_tread: 0xc0a8f2,
  elevator_shaft: 0x87969d,
  elevator_cabin: 0xe8bd69,
  elevator_landing_door: 0x6fb3d1,
  roof: 0x5b9a89,
  roof_monitor: 0x71b4a1,
  roof_parapet: 0x82948d,
  roof_equipment: 0x5f6e73,
  roof_auxiliary: 0x59656a,
  landmark_crown: 0xd08a45,
  landmark_spire: 0xd08a45,
  entrance_canopy: 0xf0d37c,
  grass: 0x65a95b,
  plaza: 0xd6c8aa,
  landscape_path: 0xb79a70,
  tree_trunk: 0x765033,
  tree_canopy: 0x3f8f4b,
  bench: 0x765c48,
  street_light: 0x57656a,
  street_tree_trunk: 0x765033,
  street_tree_canopy: 0x3f8f4b,
  street_bin: 0x39484c,
  vehicle_body: 0x4d6570,
  vehicle_glass: 0x29434e,
  pedestrian_body: 0x926c74,
  pedestrian_head: 0xd6a985,
  street_asset: 0x83948d,
  street_tree_asset: 0x4f9461,
  park_tree_asset: 0x3f8251,
  landscape_shrub_asset: 0x3f733a,
  street_light_asset: 0x59646b,
  vehicle_asset: 0x547f9f,
  pedestrian_asset: 0xb9856e,
  plaza_feature: 0x65b9d0,
  mechanical_roof: 0x70838a,
  furniture_table: 0xd69a5d,
  furniture_seating: 0x6298d2,
  furniture_storage: 0xb47648,
  furniture_bed: 0xb48ec9,
  furniture_fixture: 0xd9e5e2,
  furniture_equipment: 0x75858b,
};

const state = {
  data: null,
  streaming: null,
  geometryRevision: 0,
  mode: "full",
  districtId: "all",
  buildingId: "",
  floorId: "",
  roomId: "",
  floorCameraPreset: "perspective",
  roomCameraPreset: "eye",
  roomLighting: "soft",
  // When a run contains an explicit detail budget, keep room inspection
  // focused on rooms that actually received the expensive Room Agent pass.
  heroRoomOnly: true,
  heroRoomIds: new Set(),
  enabledSemantics: new Set(),
  daylight: true,
  skyPreset: 'clear',
  skyRotation: 0,
  appearanceMode: "presentation",
  renderProfile: "interactive",
  geometryRenderSignature: "",
  geometryRebuildCount: 0,
  standardGeometryContentSignature: "",
  navigationGeometryContentSignature: "",
  standardVisiblePrimitives: [],
  standardRenderStatusText: "",
  autoCutaway: true,
  // Keep the overview readable by default.  Both overlays remain available
  // as explicit inspection toggles for users who need them.
  showOutlines: false,
  showLabels: false,
  // Keep the default overview visually clean; road markings remain available
  // as an explicit inspection toggle.
  showRoadMarkings: false,
  // Overview defaults to a lightweight, proxy-friendly representation.  The
  // opt-in high-fidelity mode loads real outdoor GLBs while keeping building
  // interiors and repeated facade modules out of the city-wide view.
  highFidelityOverview: false,
  highFidelityPreviousProfile: null,
  highFidelityOverviewAssetIds: new Set(),
  prototypeCaptureAssetIds: new Set(),
  xray: false,
  hierarchyDisplay: null,
  captureExposure: null,
  presentationFocusId: null,
  showNavigation: false,
  showValidation: true,
  selectedPrimitive: null,
  doorStates: new Map(),
  visiblePrimitives: [],
  assetObjectCache: new Map(),
  contextLost: false,
  contextLosses: 0,
  presentationPreparing: false,
  assetRenderGeneration: 0,
  assetLoadState: {
    generation: 0, expected: 0, pending: 0, loaded: 0,
    fallback: 0, failed: 0, cached: 0, ready: true,
  },
  assetReadyPromise: Promise.resolve(),
  materialTextureUrls: new Set(),
  navigationKeys: new Set(),
  keyboardNavigationActive: false,
  cameraInteracting: false,
  cameraDirty: false,
  lastNavigationRenderTime: 0,
  // Populated by the renderer-facing observation API.  Interactive selection
  // remains unchanged, while review mode can retain more detail for the
  // entity a VLM is actually inspecting.
  observationTargetIds: new Set(),
  observationKind: "",
};
let taskReplay = null;
let snapshotActive = false;
let snapshotHeight = null;
let assetLodIds = new Map();
let assetTexturePixels = new Map();
let assetShadowIds = new Set();
let screenLodStats = {};

const elements = Object.fromEntries(
  [
    "scene-title", "folder-input", "reload-button", "screenshot-button", "hq-screenshot-button", "export-render-view-button", "mode-buttons",
    "mode-hint", "appearance-select", "quality-select", "sky-select", "sky-rotation", "sky-status", "daylight-toggle", "cutaway-toggle", "outline-toggle", "labels-toggle", "markings-toggle", "high-fidelity-toggle",
    "district-select", "building-select", "floor-select", "room-select", "hero-room-toggle", "focus-button", "floor-plan-button", "room-view-button", "floor-camera-presets", "floor-camera-buttons", "room-camera-presets", "room-camera-buttons", "room-lighting",
    "xray-toggle", "hierarchy-display-button", "paper-view-select", "navigation-toggle", "validation-toggle", "grid-toggle", "semantic-filters",
    "viewport", "scene-canvas", "loading", "toast", "legend", "render-status", "metric-buildings",
    "metric-floors", "metric-rooms", "metric-primitives", "empty-inspector", "inspector",
    "entity-type", "entity-id", "entity-properties", "door-button", "route-button",
    "validation-summary", "validation-list", "camera-iso", "camera-high-fidelity", "camera-top", "camera-street", "camera-reset",
  ].map((id) => [id, document.getElementById(id)])
);

const renderer = new THREE.WebGLRenderer({
  canvas: elements["scene-canvas"],
  antialias: true,
  preserveDrawingBuffer: true,
});
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.12;

const scene = new THREE.Scene();
scene.background = new THREE.Color(0xb9cdd1);
scene.fog = new THREE.FogExp2(0xb9cdd1, 0.00045);

const camera = new THREE.PerspectiveCamera(46, 1, 0.1, 10000);
camera.up.set(0, 0, 1);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.075;
controls.screenSpacePanning = false;
controls.zoomToCursor = true;
controls.maxPolarAngle = Math.PI * 0.495;
controls.addEventListener("change", () => {
  state.cameraDirty = true;
  if (state.streaming || screenQuality(state.renderProfile)) {
    clearTimeout(state.streamCameraTimer);
    state.streamCameraTimer = setTimeout(() => refreshCameraDetail(), 250);
  }
});
controls.addEventListener("end", () => refreshCameraDetail());

const hemisphere = new THREE.HemisphereLight(0xf4ffff, 0x71827c, 2.5);
const ambient = new THREE.AmbientLight(0xffffff, 0.92);
scene.add(hemisphere, ambient);
const sun = new THREE.DirectionalLight(0xfff3d6, 2.8);
sun.position.set(-250, -180, 420);
sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
sun.shadow.camera.left = -700;
sun.shadow.camera.right = 700;
sun.shadow.camera.top = 700;
sun.shadow.camera.bottom = -700;
sun.shadow.camera.near = 1;
sun.shadow.camera.far = 1400;
sun.shadow.bias = -0.00012;
scene.add(sun, sun.target);

const geometryGroup = new THREE.Group();
const assetGroup = new THREE.Group();
const navigationPreviewGroup = new THREE.Group();
const overlayGroup = new THREE.Group();
const navigationGroup = new THREE.Group();
const pathGroup = new THREE.Group();
const streetOverlayGroup = new THREE.Group();
const buildingOutlineGroup = new THREE.Group();
const labelGroup = new THREE.Group();
const roomBoundaryGroup = new THREE.Group();
const floorAnnotationGroup = new THREE.Group();
const presentationFocusGroup = new THREE.Group();
scene.add(presentationFocusGroup);
scene.add(
  geometryGroup,
  assetGroup,
  navigationPreviewGroup,
  streetOverlayGroup,
  buildingOutlineGroup,
  overlayGroup,
  navigationGroup,
  pathGroup,
  labelGroup,
  roomBoundaryGroup,
  floorAnnotationGroup
);

const unitBox = new THREE.BoxGeometry(1, 1, 1);
unitBox.setAttribute("uv1", unitBox.getAttribute("uv"));
unitBox.setAttribute("uv2", unitBox.getAttribute("uv"));
const gltfLoader = new GLTFLoader();
const assetTemplates = new AssetTemplatePool(async key => {
  const [url, edge] = JSON.parse(key);
  const root = (await gltfLoader.loadAsync(url)).scene;
  return resizeTemplateTextures(root, edge, async (image, width, height) => {
    const canvas = document.createElement('canvas'); canvas.width=width; canvas.height=height;
    const context = canvas.getContext('2d');
    context.drawImage(image,0,0,width,height);
    return canvas;
  });
});
const textureLoader = new THREE.TextureLoader();
const rgbeLoader = new RGBELoader();
let pmremGenerator = new THREE.PMREMGenerator(renderer);
pmremGenerator.compileEquirectangularShader();
const textureCache = new Map();
const readyMaterialTextures = new Map();
const sharedMaterialTextures = new Set();
const textureLoadStates = new Map();
const texturedBoxCache = new Map();
let environmentTarget = null;
let indoorStudioTarget = null;
let currentEnvironmentUrl = "";
const environmentCache = new Map();
const environmentLoads = new Map();
// Presentation-only horizon extension; never part of picking, compilation or physics.
const horizonGround = createHorizonGround();
scene.add(horizonGround);
const highlight = new THREE.LineSegments(
  new THREE.EdgesGeometry(unitBox),
  new THREE.LineBasicMaterial({ color: 0xf4ff85, linewidth: 2, depthTest: false })
);
highlight.renderOrder = 20;
highlight.visible = false;
overlayGroup.add(highlight);

const grid = makeGrid(1000, 50);
scene.add(grid);
applyTheme();

const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();
let pointerStart = null;
let toastTimer = null;

const modeHints = {
  overview: "Overview: roads and building shells only.",
  building: "Building: selected interior shown with an automatic shell cutaway.",
  floor: "Floor: selected level isolated; its roof is hidden automatically.",
  floor_plan: "Floor plan: only the selected floor is visible from a top-down view.",
  room: "Room: only the selected room, its boundary, door, and furnishings are visible.",
  full: "Full scene: all compiled geometry is visible.",
};

const HIGH_FIDELITY_OVERVIEW_LAYERS = new Set(["roads", "district", "root"]);

function highFidelityOverviewAsset(primitive) {
  if (!state.highFidelityOverview || state.mode !== "overview") return false;
  if (!primitive.metadata?.resolved_asset || !primitive.metadata?.asset_id) return false;
  const layerType = state.data?.layerMap.get(primitive.layer_id)?.layer_type || "unknown";
  // Restrict the expensive GLB pass to outdoor/global layers.  Building-shell
  // facade modules remain procedural/LOD geometry so a city-wide screenshot
  // does not clone thousands of window meshes.
  return HIGH_FIDELITY_OVERVIEW_LAYERS.has(layerType)
    && state.highFidelityOverviewAssetIds.has(primitive.id);
}

function selectHighFidelityOverviewAssets(primitives) {
  const quotas = new Map([
    ["tree", 6], ["shrub", 4], ["street_light_asset", 5],
    ["street_furniture", 5], ["vehicle_asset", 3], ["pedestrian_asset", 2],
    ["flower_cluster", 4], ["playground_equipment", 1],
  ]);
  const candidates = primitives.filter((primitive) => {
    if (!primitive.metadata?.resolved_asset || !primitive.metadata?.asset_id) return false;
    const layerType = state.data?.layerMap.get(primitive.layer_id)?.layer_type || "unknown";
    if (!HIGH_FIDELITY_OVERVIEW_LAYERS.has(layerType)) return false;
    const semantic = primitive.semantic_class;
    return [
      "street_tree_asset", "park_tree_asset", "parcel_tree_asset",
      "parcel_shrub_asset", "landscape_shrub_asset", "street_light_asset",
      "bench", "street_bench", "street_planter", "vehicle_asset",
      "pedestrian_asset", "person_asset", "flower_cluster", "playground_equipment",
    ].includes(semantic);
  });
  const groupFor = (primitive) => {
    const semantic = primitive.semantic_class;
    if (["street_tree_asset", "park_tree_asset", "parcel_tree_asset"].includes(semantic)) return "tree";
    if (["parcel_shrub_asset", "landscape_shrub_asset"].includes(semantic)) return "shrub";
    if (["bench", "street_bench", "street_planter"].includes(semantic)) return "street_furniture";
    return semantic;
  };
  const selected = new Set();
  for (const [group, quota] of quotas) {
    const groupItems = candidates
      .filter((primitive) => groupFor(primitive) === group)
      .sort((a, b) => String(a.id).localeCompare(String(b.id)));
    // Select one representative per asset ID first, then fill remaining slots
    // from deterministic instance order. This preserves species diversity.
    const diverse = [];
    const seenAssets = new Set();
    for (const primitive of groupItems) {
      const assetId = primitive.metadata.asset_id;
      if (seenAssets.has(assetId)) continue;
      seenAssets.add(assetId);
      diverse.push(primitive);
      if (diverse.length >= quota) break;
    }
    if (diverse.length < quota) {
      for (const primitive of groupItems) {
        if (!diverse.includes(primitive)) diverse.push(primitive);
        if (diverse.length >= quota) break;
      }
    }
    diverse.forEach((primitive) => selected.add(primitive.id));
  }
  return selected;
}

const floorCameraLabels = {
  perspective: "Floor 3D",
  top: "Floor top",
  corridor: "Corridor",
  core: "Stair / lift",
};

function makeGrid(size, step) {
  const positions = [];
  const half = size / 2;
  for (let value = -half; value <= half; value += step) {
    positions.push(-half, value, -0.19, half, value, -0.19);
    positions.push(value, -half, -0.19, value, half, -0.19);
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  return new THREE.LineSegments(
    geometry,
    new THREE.LineBasicMaterial({ color: 0x29413b, transparent: true, opacity: 0.34 })
  );
}

function applyTheme() {
  const hints = scene.userData.renderingHints || {};
  const fogScale = Number.isFinite(hints.fog_density_scale) ? hints.fog_density_scale : 1;
  const exposureScale = Number.isFinite(hints.exposure_scale) ? hints.exposure_scale : 1;
  const sunScale = Number.isFinite(hints.sun_intensity_scale) ? hints.sun_intensity_scale : 1;
  const background = state.daylight ? 0xb9cdd1 : 0x101c1b;
  scene.background = new THREE.Color(background);
  scene.backgroundRotation.set(0,0,0);
  scene.environmentRotation.set(0,0,0);
  scene.backgroundIntensity = 1;
  scene.environmentIntensity = 1;
  horizonGround.visible=false;
  scene.fog.color.setHex(background);
  const bounds = state.data?.city?.bounds;
  const extent = bounds ? Math.hypot(bounds.max_x-bounds.min_x, bounds.max_y-bounds.min_y) : 800;
  scene.fog.density = (state.daylight ? 0.00045 : 0.0009) * fogScale * Math.min(1, 800/Math.max(800, extent));
  renderer.toneMappingExposure = state.captureExposure ?? (state.daylight ? 1.12 : 1.3) * exposureScale;
  hemisphere.color.setHex(state.daylight ? 0xf4ffff : 0xe8fff8);
  hemisphere.groundColor.setHex(state.daylight ? 0x71827c : 0x30403c);
  hemisphere.intensity = state.daylight ? 2.5 : 3.0;
  ambient.color.setHex(state.daylight ? 0xffffff : 0xd8eee8);
  ambient.intensity = state.daylight ? 0.92 : 0.72;
  sun.intensity = (state.daylight ? 2.8 : 3.4) * sunScale;
  sun.color.setHex(0xfff3d6);
  const wanted = desiredEnvironment(state.data?.raw.config);
  const entry = environmentCache.get(wanted.url);
  if (wanted.preset && entry && RENDER_PROFILES[state.renderProfile].environment) {
    const p = wanted.preset;
    const pose = skyOrientation(entry.analysis,
      Number.isFinite(hints.sun_azimuth_deg) ? hints.sun_azimuth_deg : 215, state.skyRotation);
    scene.background = entry.source;
    scene.backgroundRotation.copy(pose.rotation);
    scene.environmentRotation.copy(pose.rotation);
    scene.backgroundBlurriness = 0;
    scene.backgroundIntensity = p.background_intensity ?? .5;
    scene.environmentIntensity = p.environment_intensity ?? .65;
    scene.fog.color.setRGB(...entry.analysis.horizon).multiplyScalar(scene.backgroundIntensity);
    renderer.toneMappingExposure = state.captureExposure ?? (p.exposure ?? 1)*exposureScale;
    aimDirectionalLight(sun,pose.sun);
    sun.color.set(p.sun_color || '#fff3d6');
    sun.intensity = (p.sun_intensity ?? 2.8)*sunScale;
    hemisphere.intensity = .7;
    ambient.intensity = .25;
    const ground = state.data?.geometry.primitives.find(p=>p.metadata?.ground_plane);
    if (ground && ['overview','building','full'].includes(state.mode) && state.districtId === 'all') {
      const material = state.data.geometry.materials.find(m=>m.id===ground.material_id);
      configureHorizonGround(horizonGround,ground,material,extent,
        entry.analysis.horizon,scene.backgroundIntensity);
    }
  } else {
    const az=(Number.isFinite(hints.sun_azimuth_deg) ? hints.sun_azimuth_deg : 215)*Math.PI/180;
    const el=(Number.isFinite(hints.sun_elevation_deg) ? hints.sun_elevation_deg : 54)*Math.PI/180;
    aimDirectionalLight(sun,new THREE.Vector3(Math.cos(az)*Math.cos(el),Math.sin(az)*Math.cos(el),Math.sin(el)));
  }
  if (state.mode === "room" && state.roomLighting === "soft") {
    hemisphere.intensity = 2.8;
    ambient.intensity = 1.35;
    sun.intensity = 1.8;
    renderer.toneMappingExposure = 1.08;
    scene.fog.density = 0;
  }
  grid.material.color.setHex(state.daylight ? 0x6f8d89 : 0x29413b);
  grid.material.opacity = state.daylight ? 0.3 : 0.34;
  if (elements['sky-status']) {
    elements['sky-status'].textContent = wanted.preset
      ? entry ? `${wanted.preset.label} · HDR sky + lighting` : 'Loading sky…'
      : ['floor','floor_plan','room'].includes(state.mode) ? 'Plain background for indoor inspection'
      : !state.data?.raw.config?.sky_presets?.[state.skyPreset] && state.skyPreset !== 'none'
        ? 'Sky pack not installed in this export' : 'Sky disabled in this view / quality mode';
  }
}

function applySceneRenderingHints(profile) {
  if (!profile || typeof profile !== "object") return;
  scene.userData.renderingHints = profile;
  const azimuth = Number(profile.sun_azimuth_deg);
  const elevation = Number(profile.sun_elevation_deg);
  if (Number.isFinite(azimuth) && Number.isFinite(elevation)) {
    const az = azimuth * Math.PI / 180;
    const el = Math.max(8, Math.min(82, elevation)) * Math.PI / 180;
    const radius = 520;
    sun.position.set(
      Math.cos(az) * Math.cos(el) * radius,
      Math.sin(az) * Math.cos(el) * radius,
      Math.sin(el) * radius,
    ).add(sun.target.position);
  }
  applyTheme();
}

function requestedRenderProfile() {
  const injected = window.__CITYG_RENDER_PROFILE__;
  const query = new URLSearchParams(window.location.search).get("quality");
  const stored = window.localStorage?.getItem("cityg.renderProfile");
  return [injected, query, stored, "interactive"].find((value) => RENDER_PROFILES[value]);
}

function applyRenderProfile(name, { persist = false } = {}) {
  const profileName = RENDER_PROFILES[name] ? name : "interactive";
  const profile = RENDER_PROFILES[profileName];
  if (state.renderProfile === 'navigation' && ['presentation','interactive'].includes(profileName)
      && navigationPreviewGroup.children.length) state.presentationPreparing = true;
  if (!['presentation','interactive'].includes(profileName)) state.presentationPreparing = false;
  if (profileName === 'navigation' && state.renderProfile !== 'navigation') releaseStandardGeometry();
  state.renderProfile = profileName;
  // Set size and density atomically: an intermediate uncapped Retina buffer
  // (or a 2x enlargement of the previous HQ export) can itself exhaust VRAM.
  renderer.setDrawingBufferSize(elements.viewport.clientWidth, elements.viewport.clientHeight,
    displayPixelRatio(elements.viewport.clientWidth, elements.viewport.clientHeight, profile.pixelRatio()));
  renderer.shadowMap.enabled = profile.shadows;
  sun.castShadow = profile.shadows;
  const shadowSize = Math.min(renderer.capabilities.maxTextureSize,
    profileName === 'snapshot' ? 4096 : profileName === 'presentation' ? 2048 : 1024);
  if (sun.shadow.mapSize.x !== shadowSize) {
    sun.shadow.mapSize.set(shadowSize, shadowSize);
    sun.shadow.map?.dispose();
    sun.shadow.map = null;
  }
  controls.enableDamping = !["review", "navigation", "paper_capture", "snapshot"].includes(profileName);
  if (!profile.environment) scene.environment = null;
  else if (environmentTarget) scene.environment = environmentTarget.texture;
  if (profile.environment && state.data) loadEnvironment(state.data.raw.config);
  if (elements["quality-select"]) elements["quality-select"].value = profileName;
  if (persist) window.localStorage?.setItem("cityg.renderProfile", profileName);
  resize();
  return profile;
}

function resize() {
  if (snapshotActive) return;
  const { clientWidth, clientHeight } = elements.viewport;
  renderer.setDrawingBufferSize(clientWidth, clientHeight,
    displayPixelRatio(clientWidth, clientHeight, RENDER_PROFILES[state.renderProfile].pixelRatio()));
  camera.aspect = clientWidth / Math.max(1, clientHeight);
  camera.updateProjectionMatrix();
  state.cameraDirty = true;
  if (state.data && screenQuality(state.renderProfile)) {
    clearTimeout(state.streamCameraTimer);
    state.streamCameraTimer = setTimeout(() => refreshCameraDetail(), 250);
  }
}
new ResizeObserver(resize).observe(elements.viewport);

function updateKeyboardNavigation(deltaSeconds) {
  if (!state.navigationKeys.size) return;
  const speedMultiplier = state.navigationKeys.has("shift") ? 3.0 : 1.0;
  const offset = camera.position.clone().sub(controls.target);
  const distance = Math.max(1, offset.length());
  const step = Math.max(0.55, distance * 0.42) * deltaSeconds * speedMultiplier;
  const up = camera.up.clone().normalize();
  const forward = controls.target.clone().sub(camera.position);
  forward.z = 0;
  if (forward.lengthSq() < 1e-8) forward.set(0, 1, 0);
  forward.normalize();
  const right = forward.clone().cross(up).normalize();
  const translation = new THREE.Vector3();
  if (state.navigationKeys.has("w")) translation.addScaledVector(forward, step);
  if (state.navigationKeys.has("s")) translation.addScaledVector(forward, -step);
  if (state.navigationKeys.has("a")) translation.addScaledVector(right, -step);
  if (state.navigationKeys.has("d")) translation.addScaledVector(right, step);
  if (state.navigationKeys.has("q")) translation.addScaledVector(up, -step);
  if (state.navigationKeys.has("e")) translation.addScaledVector(up, step);
  camera.position.add(translation);
  controls.target.add(translation);

  // Arrow keys orbit around the current target. The explicit z-up rotation
  // keeps this usable with CityG's OpenUSD convention and the viewer's camera.
  const yaw = (state.navigationKeys.has("arrowleft") ? 1 : 0)
    - (state.navigationKeys.has("arrowright") ? 1 : 0);
  const pitch = (state.navigationKeys.has("arrowup") ? 1 : 0)
    - (state.navigationKeys.has("arrowdown") ? 1 : 0);
  if (yaw || pitch) {
    const orbitOffset = camera.position.clone().sub(controls.target);
    const angle = 0.95 * deltaSeconds * speedMultiplier;
    orbitOffset.applyAxisAngle(up, yaw * angle);
    if (pitch) {
      const orbitRight = up.clone().cross(orbitOffset).normalize();
      const candidate = orbitOffset.clone().applyAxisAngle(orbitRight, pitch * angle);
      const polar = candidate.angleTo(up);
      if (polar > 0.10 && polar < Math.PI * 0.49) orbitOffset.copy(candidate);
    }
    camera.position.copy(controls.target).add(orbitOffset);
  }
}

function updateDepthPrecision() {
  if (!state.data || state.renderProfile === 'prototype_capture') return;
  if (state.data.depthPrimitives !== state.data.geometry.primitives) {
    state.data.sceneTop = state.data.geometry.primitives.reduce((top,p)=>
      Math.max(top,p.center.z+p.size.z/2),0);
    state.data.depthPrimitives = state.data.geometry.primitives;
  }
  const near=aerialNearPlane(camera.position,controls.target,state.data.sceneTop,state.mode);
  if (near !== null && Math.abs(camera.near-near)>0.00001) {
    camera.near=near;
    camera.updateProjectionMatrix();
    state.cameraDirty=true;
  }
}

let previousFrameTime = performance.now();
function animate() {
  requestAnimationFrame(animate);
  if (snapshotActive || state.contextLost) return;
  // This private headless profile is drawn explicitly by setView/assets/capture.
  // Even OrbitControls' damping frames can queue expensive software GPU work.
  if (["prototype_capture", "paper_capture"].includes(state.renderProfile)) return;
  const now = performance.now();
  const deltaSeconds = Math.min(0.05, (now - previousFrameTime) / 1000);
  previousFrameTime = now;
  updateKeyboardNavigation(deltaSeconds);
  const controlsChanged = controls.update();
  updateDepthPrecision();
  if (state.presentationPreparing && !finishPresentationPreparation()) {
    const status = observationAssetStatus();
    elements['render-status'].textContent = `Preparing ${state.renderProfile} · ${status.loaded} models ready · ${status.pending} pending · Navigation preview retained`;
    if (state.cameraDirty || controlsChanged) {
      renderer.render(scene,camera); state.cameraDirty = false;
    }
    return;
  }
  if (state.streaming && !["review", "navigation", "prototype_capture"].includes(state.renderProfile)) {
    // Large static cities do not need a perpetual high-quality render loop.
    // Let asynchronous geometry/textures finish before the next expensive
    // stationary frame; interaction still redraws immediately.
    const moving = state.cameraInteracting || controlsChanged || state.navigationKeys.size > 0;
    const assetsPending = state.assetLoadState.pending > 0 || state.streaming.status.pending > 0
      || [...state.materialTextureUrls].some((url) => textureLoadStates.get(url) === "pending");
    if (moving || (state.cameraDirty && !assetsPending)) {
      renderer.render(scene, camera);
      state.cameraDirty = false;
    }
  } else if (!["review", "navigation", "prototype_capture"].includes(state.renderProfile)) {
    if (state.cameraDirty || controlsChanged || state.navigationKeys.size > 0) {
      renderer.render(scene, camera);
      state.cameraDirty = false;
    }
  } else if (state.renderProfile === "navigation") {
    // Software/WebGL implementations on laptops benefit substantially from a
    // bounded camera redraw rate.  The final pointer-up frame is rendered
    // immediately below, so this is a temporal throttle rather than a loss of
    // camera precision.
    // OrbitControls mutates the camera directly while pointer-dragging. With
    // damping disabled its update() return value can remain false, so the
    // explicit interaction state must also drive redraws.
    const moving = state.cameraInteracting || state.cameraDirty || controlsChanged || state.navigationKeys.size > 0;
    const interval = state.cameraInteracting ? 55 : 0;
    if (moving && now - state.lastNavigationRenderTime >= interval) {
      renderer.render(scene, camera);
      state.lastNavigationRenderTime = now;
      state.cameraDirty = false;
    }
  } else if (state.cameraDirty || controlsChanged || state.navigationKeys.size > 0) {
    renderer.render(scene, camera);
    state.cameraDirty = false;
  }
}
animate();

async function fetchJson(name, required = false) {
  const response = await fetch(`/scene/${name}`, { cache: "no-store" });
  if (!response.ok) {
    if (required) throw new Error(`Missing required scene file: ${name}`);
    return null;
  }
  return response.json();
}

async function loadServerScene() {
  if (state.data) taskReplay?.reset();
  setLoading(true, "Loading CityG manifests");
  let configResponse = await fetch("/api/config", { cache: "no-store" });
  if (!configResponse.ok) configResponse = await fetch("./viewer-config.json", { cache: "no-store" });
  if (!configResponse.ok) throw new Error("Viewer configuration is unavailable");
  const config = await configResponse.json();
  const scenePrefix = config.source === "portable_export" ? "./scene/" : "/scene/";
  const fetchSceneJson = async (name, required = false, signal) => {
    const response = await fetch(`${scenePrefix}${name}`, { cache: "no-store", signal });
    if (!response.ok) {
      if (required) throw new Error(`Missing required scene file: ${name}`);
      return null;
    }
    return response.json();
  };
  const values = await Promise.all([
    ...REQUIRED_FILES.map((name) => fetchSceneJson(name, true)),
    ...OPTIONAL_FILES.map((name) => fetchSceneJson(name, false)),
  ]);
  const names = [...REQUIRED_FILES, ...OPTIONAL_FILES];
  const data = Object.fromEntries(names.map((name, index) => [name, values[index]]));
  data.config = config;
  await loadOverview(data, fetchSceneJson);
  loadData(data);
  attachStreaming(data, fetchSceneJson);
}

async function loadFolder(fileList) {
  if (state.data) taskReplay?.reset();
  const files = [...fileList];
  const geometryCandidates = files.filter((file) => file.name === "geometry_manifest.json");
  if (!geometryCandidates.length) throw new Error("Selected folder has no geometry_manifest.json");
  geometryCandidates.sort((a, b) => a.webkitRelativePath.length - b.webkitRelativePath.length);
  const rootPath = geometryCandidates[0].webkitRelativePath.slice(0, -"geometry_manifest.json".length);
  const byName = new Map();
  for (const file of files) {
    if (file.webkitRelativePath.startsWith(rootPath)) {
      const relative = file.webkitRelativePath.slice(rootPath.length);
      if (!relative.includes("/")) byName.set(file.name, file);
    }
  }
  for (const name of REQUIRED_FILES) {
    if (!byName.has(name)) throw new Error(`Selected scene is missing ${name}`);
  }
  setLoading(true, "Reading local scene folder");
  const data = {};
  for (const name of [...REQUIRED_FILES, ...OPTIONAL_FILES]) {
    data[name] = byName.has(name) ? JSON.parse(await byName.get(name).text()) : null;
  }
  data.config = { label: rootPath.replace(/\/$/, "") || "Local folder", source: "browser" };
  const fetchLocal = async (name) => {
    if (!byName.has(name)) throw new Error(`Missing geometry chunk: ${name}`);
    return JSON.parse(await byName.get(name).text());
  };
  await loadOverview(data, fetchLocal);
  loadData(data);
  attachStreaming(data, fetchLocal);
}

async function loadOverview(raw, fetchJson) {
  const geometry = raw["geometry_manifest.json"];
  if (!geometry.streaming) return;
  if (geometry.streaming.version !== 1) throw new Error("Unsupported CityG geometry streaming version");
  geometry.primitives = [];
  for (const part of geometry.streaming.overview) {
    const data = await fetchJson(part.file, true);
    if (!Array.isArray(data?.primitives) || data.primitives.length !== part.count) {
      throw new Error(`Invalid overview chunk: ${part.file}`);
    }
    // Avoid argument-count limits on large arrays.
    geometry.primitives = geometry.primitives.concat(data.primitives);
  }
}

function attachStreaming(raw, fetchJson) {
  const geometry = raw["geometry_manifest.json"];
  if (!geometry.streaming) return;
  state.streaming = new ProgressiveGeometry(geometry.streaming, geometry.primitives, fetchJson,
    (primitives) => {
      state.data.geometry.primitives = primitives;
      state.geometryRevision += 1;
      refreshRoomWallIndex();
      // A startup room cannot pass the wall gate until its building chunks
      // arrive. Restore the explicit observation binding before repopulating
      // selectors, rather than silently selecting the first available room.
      if (state.mode === "room") {
        const target = [...state.observationTargetIds].map((id) => state.data.hierarchy.entities.get(id))
          .find((item) => item?.type === "room");
        if (target) {
          state.roomId = target.entity.id;
          state.floorId = target.floorId;
          state.buildingId = target.buildingId;
        }
      }
      // Objects belonging to evicted neighborhoods must not accumulate forever.
      const retained = new Set(primitives.map((p) => p.id));
      for (const [key, object] of state.assetObjectCache) {
        if (!retained.has(object.userData.entry?.id)) {
          object.removeFromParent();
          object.traverse((node) => node.userData.citygOwnedMaterials?.forEach((m) => m.dispose()));
          state.assetObjectCache.delete(key);
        }
      }
      updateRoomOptions();
      renderGeometry();
    }, (status) => {
      if (status.failed) showToast(`Geometry loading failed: ${status.error}`);
      updateStreamingStatus();
    });
  requestStreamDetail();
  updateModeHint();
}

function refreshRoomWallIndex() {
  const roomWalls = new Map();
  for (const p of state.data.geometry.primitives) {
    if (p.semantic_class !== "interior_wall") continue;
    const ids = p.metadata?.room_ids || (state.data.hierarchy.entities.get(p.owner_id)?.type === "room" ? [p.owner_id] : []);
    for (const id of ids) { if (!roomWalls.has(id)) roomWalls.set(id, []); roomWalls.get(id).push(p); }
  }
  state.data.roomWalls = roomWalls;
  state.data.roomWallIds = new Set(roomWalls.keys());
}

function currentScreenContext() {
  return screenContext(camera, snapshotHeight || elements.viewport.clientHeight * renderer.getPixelRatio(),
    sun.position.clone().sub(sun.target.position).toArray());
}

function refreshCameraDetail() {
  if (snapshotActive || !state.data) return;
  if (screenQuality(state.renderProfile)) renderGeometry();
  else requestStreamDetail();
}

function requestStreamDetail() {
  if (!state.streaming || !state.data) return Promise.resolve();
  const targets = new Set(state.observationTargetIds);
  for (const id of targets) {
    const bid = state.data.hierarchy.entities.get(id)?.buildingId;
    if (bid) targets.add(bid);
  }
  const screen = screenQuality(state.renderProfile) ? currentScreenContext() : null;
  const chunks = selectDetailChunks(state.data.geometry.streaming, {
    profile: state.renderProfile, mode: state.mode, buildingId: state.buildingId,
    kind: state.observationKind,
    targets: [...targets], camera: camera.position, focus: controls.target,
    screenMeasure: screen ? c => screen.measure(chunkBounds(c)) : null,
  });
  return state.streaming.request(chunks);
}

function updateStreamingStatus() {
  if (!state.streaming) return;
  const g = state.data.geometry, s = state.streaming.status;
  elements["render-status"].textContent = `${state.visiblePrimitives.length.toLocaleString()} visible · ${g.primitives.length.toLocaleString()} resident / ${g.streaming.total_primitives.toLocaleString()} total · ${s.failed ? "geometry error" : s.pending ? `loading ${s.pending} chunks` : s.loaded_chunks ? "local detail + city LOD" : "city LOD"} · ${state.renderProfile}`;
}

function loadData(raw) {
  state.streaming?.dispose();
  state.streaming = null;
  state.geometryRevision = 0;
  const geometry = raw["geometry_manifest.json"];
  const city = raw["city.json"];
  const navigation = raw["navigation.json"] || geometry.navigation || { nodes: [], edges: [] };
  const interactions = raw["interactions.json"] || { state_machines: geometry.state_machines || [] };
  const activation = raw["activation_manifest.json"] || {
    layers: geometry.layers || [], activation_tiers: geometry.activation_tiers || [], building_prototypes: {},
  };
  const hierarchy = indexCity(city);
  const layerMap = new Map(activation.layers.map((layer) => [layer.id, layer]));
  const validationReports = [
    raw["validation_report.json"], raw["geometry_validation_report.json"],
    raw["interaction_smoke_report.json"], raw["usd_validation_report.json"],
  ].filter(Boolean);
  const issues = validationReports.flatMap((report) => report.issues || []);
  const errorIds = new Set(
    issues.flatMap((issue) => [issue.entity_id, ...(issue.violating_entities || [])]).filter(Boolean)
  );
  // Build the room-to-wall index once while loading the manifest.  Calling a
  // full primitive scan from isVisiblePrimitive turns a room view into O(N²)
  // work on city-scale manifests (every candidate primitive re-scanned all
  // walls).  This index makes enclosure checks proportional to one room's
  // boundary only.
  const roomWalls = new Map();
  for (const primitive of geometry.primitives) {
    if (primitive.semantic_class !== "interior_wall") continue;
    const metadataRoomIds = Array.isArray(primitive.metadata?.room_ids)
      ? primitive.metadata.room_ids
      : [];
    const ownerIsRoom = hierarchy.entities.get(primitive.owner_id)?.type === "room";
    const roomIds = metadataRoomIds.length
      ? metadataRoomIds
      : ownerIsRoom ? [primitive.owner_id] : [];
    for (const roomId of roomIds) {
      if (!roomWalls.has(roomId)) roomWalls.set(roomId, []);
      roomWalls.get(roomId).push(primitive);
    }
  }
  const roomWallIds = new Set(roomWalls.keys());
  const heroRoomIds = new Set(
    [...hierarchy.entities.values()]
      .filter((item) => item.type === "room" && item.entity.metadata?.detail_tier === "hero")
      .map((item) => item.entity.id)
  );
  state.data = {
    raw, geometry, city, navigation, interactions, activation, hierarchy, layerMap,
    issues, errorIds, roomWallIds, roomWalls, heroRoomIds,
  };
  taskReplay?.available(raw.config?.source==='portable_export' && raw.config?.files?.includes('task_replay.json'));
  applySceneRenderingHints(
    geometry.metadata?.rendering_profile || city.metadata?.rendering_profile,
  );
  state.heroRoomIds = heroRoomIds;
  state.heroRoomOnly = heroRoomIds.size > 0;
  state.highFidelityOverview = false;
  state.highFidelityPreviousProfile = null;
  state.highFidelityOverviewAssetIds = new Set();
  elements["hero-room-toggle"].checked = state.heroRoomOnly;
  elements["high-fidelity-toggle"].checked = false;
  elements["camera-high-fidelity"].classList.remove("active");
  elements["hero-room-toggle"].disabled = heroRoomIds.size === 0;
  const explicitProfile = window.__CITYG_RENDER_PROFILE__ || new URLSearchParams(window.location.search).get("quality");
  applyRenderProfile(geometry.streaming && !explicitProfile ? "navigation" : requestedRenderProfile());
  // Full mode is useful for compact scenes, but eagerly drawing every room of
  // a high-rise district can create tens of thousands of visible primitives.
  // Start large scenes at city LOD and let the user opt into a building,
  // floor, or the complete compiled scene when that detail is needed.
  state.mode = (geometry.streaming?.total_primitives || geometry.primitives.length) >= LARGE_SCENE_OVERVIEW_THRESHOLD
    ? "overview"
    : "full";
  clearAssetGroup();
  assetTemplates.clear();
  state.assetRenderGeneration += 1;
  state.enabledSemantics = new Set(geometry.streaming?.semantics || geometry.primitives.map((primitive) => primitive.semantic_class));
  state.doorStates = new Map(interactions.state_machines.map((machine) => [machine.id, machine.initial_state]));
  state.selectedPrimitive = null;
  state.geometryRenderSignature = "";
  state.geometryRebuildCount = 0;
  state.standardGeometryContentSignature = "";
  state.navigationGeometryContentSignature = "";
  state.standardVisiblePrimitives = [];
  state.standardRenderStatusText = "";
  clearGroup(navigationPreviewGroup);
  const initialObservation = window.__CITYG_INITIAL_OBSERVATION_VIEW__ || null;
  const initialObservationHasCamera = Boolean(
    Array.isArray(initialObservation?.camera_position)
    && Array.isArray(initialObservation?.look_at)
  );
  if (initialObservation) applyObservationState(initialObservation);
  syncObservationControls();
  elements["scene-title"].textContent = `${city.name} · ${raw.config?.label || city.id}`;
  populateControls();
  loadEnvironment(raw.config);
  renderGeometry();
  renderValidation();
  updateInspector();
  // A mode-only startup hint still needs a useful default camera. Adaptive
  // plans provide both vectors and must retain their exact camera contract.
  if (!initialObservationHasCamera) fitCity("iso");
  setLoading(false);
  window.citygObservation.ready = true;
  installPaperViews(raw.config);
  showToast(`Loaded ${geometry.primitives.length.toLocaleString()} primitives`);
}

function indexCity(city) {
  const entities = new Map();
  const add = (entity, type, parentId, extra = {}) => entities.set(entity.id, { entity, type, parentId, ...extra });
  add(city, "city", null);
  for (const junction of city.road_network?.junctions || []) add(junction, "junction", city.id);
  for (const road of city.road_network?.segments || []) add(road, "road_segment", city.id);
  for (const river of city.rivers || []) add(river, "river", city.id);
  for (const bridge of city.bridges || []) add(bridge, "bridge", city.id);
  for (const district of city.districts || []) {
    add(district, "district", city.id, { districtId: district.id });
    for (const parcel of district.parcels || []) {
      add(parcel, "parcel", district.id, { districtId: district.id });
      for (const building of parcel.buildings || []) {
        add(building, "building", parcel.id, { districtId: district.id, buildingId: building.id });
        const floorByLevel = new Map((building.floors || []).map((floor) => [Number(floor.level), floor]));
        for (const connector of building.vertical_connectors || []) {
          const floorIds = [...floorByLevel.entries()]
            .filter(([level]) => level >= Number(connector.from_level) && level <= Number(connector.to_level))
            .map(([, floor]) => floor.id);
          add(connector, "vertical_connector", building.id, {
            districtId: district.id,
            buildingId: building.id,
            floorIds,
          });
        }
        for (const floor of building.floors || []) {
          add(floor, "floor", building.id, { districtId: district.id, buildingId: building.id, floorId: floor.id });
          for (const room of floor.rooms || []) {
            add(room, "room", floor.id, { districtId: district.id, buildingId: building.id, floorId: floor.id });
            for (const object of (floor.objects || []).filter((item) => item.room_id === room.id)) {
              add(object, "interior_object", room.id, { districtId: district.id, buildingId: building.id, floorId: floor.id });
            }
          }
          for (const door of floor.doors || []) {
            add(door, "door", floor.id, {
              districtId: district.id,
              buildingId: building.id,
              floorId: floor.id,
              roomIds: [door.room_a_id, door.room_b_id].filter(Boolean),
            });
          }
        }
      }
    }
  }
  function lineage(id) {
    const result = [];
    let current = entities.get(id);
    while (current) {
      result.push(current.entity.id);
      current = current.parentId ? entities.get(current.parentId) : null;
    }
    return result;
  }
  return { entities, lineage };
}

function populateControls() {
  const { city, hierarchy, geometry } = state.data;
  setOptions(elements["district-select"], [
    { value: "all", label: "All districts" },
    ...city.districts.map((district) => ({ value: district.id, label: `${district.name} · ${district.function}` })),
  ], state.districtId);
  if (!city.districts.some((district) => district.id === state.districtId)) state.districtId = "all";
  updateBuildingOptions();

  elements["semantic-filters"].replaceChildren();
  const semantics = [...new Set(geometry.streaming?.semantics || geometry.primitives.map((primitive) => primitive.semantic_class))].sort();
  for (const semantic of semantics) {
    const label = document.createElement("label");
    const input = document.createElement("input");
    input.type = "checkbox";
    input.checked = true;
    input.addEventListener("change", () => {
      if (input.checked) state.enabledSemantics.add(semantic); else state.enabledSemantics.delete(semantic);
      renderGeometry();
    });
    const swatch = document.createElement("span");
    swatch.className = "swatch";
    swatch.style.background = `#${(semanticPalette[semantic] || 0x8aa39c).toString(16).padStart(6, "0")}`;
    const text = document.createElement("span");
    text.textContent = semantic.replaceAll("_", " ");
    label.append(input, swatch, text);
    elements["semantic-filters"].append(label);
  }

  const buildings = [...hierarchy.entities.values()].filter((item) => item.type === "building");
  const floors = [...hierarchy.entities.values()].filter((item) => item.type === "floor");
  const rooms = [...hierarchy.entities.values()].filter((item) => item.type === "room");
  elements["metric-buildings"].textContent = buildings.length;
  elements["metric-floors"].textContent = floors.length;
  elements["metric-rooms"].textContent = rooms.length;
  updateModeHint();
  renderLegend();
}

function updateModeHint() {
  elements["mode-hint"].textContent = state.renderProfile === "navigation"
    ? "Navigation preview: lightweight building silhouettes and road context; switch to Presentation for final materials."
    : state.mode === "overview" && state.highFidelityOverview
    ? "High-fidelity overview: real outdoor GLB assets are loaded; interiors remain hidden."
    : modeHints[state.mode];
  if (state.streaming) elements["mode-hint"].textContent += " · Streamed scene: city LOD; select a building or approach the street in Presentation for local detail.";
  updateFloorCameraControls();
}

function setHighFidelityOverview(enabled, { focus = true, render = true } = {}) {
  const next = Boolean(enabled);
  if (next === state.highFidelityOverview && (!next || state.mode === "overview")) {
    if (focus && next) fitCity("iso");
    return;
  }
  if (next) {
    state.highFidelityPreviousProfile = state.renderProfile;
    state.highFidelityOverview = true;
    state.mode = "overview";
    // Always use the dedicated profile while this mode is active.  This keeps
    // the expensive presentation HDR/shadow path from being selected by
    // accident, while still enabling textured GLBs over the fast review mode.
    applyRenderProfile("high_fidelity");
    if (focus) fitCity("iso");
    showToast("High-fidelity overview enabled; loading outdoor assets…");
  } else {
    state.highFidelityOverview = false;
    const previous = state.highFidelityPreviousProfile;
    state.highFidelityPreviousProfile = null;
    if (previous && RENDER_PROFILES[previous]) applyRenderProfile(previous);
    showToast("High-fidelity overview disabled");
  }
  if (elements["high-fidelity-toggle"]) elements["high-fidelity-toggle"].checked = next;
  if (elements["camera-high-fidelity"]) elements["camera-high-fidelity"].classList.toggle("active", next);
  elements["mode-buttons"].querySelectorAll("button").forEach((item) => {
    item.classList.toggle("active", item.dataset.mode === state.mode);
  });
  updateModeHint();
  if (render) renderGeometry();
}

function updateFloorCameraControls() {
  if (elements["room-camera-presets"]) {
    elements["room-camera-presets"].hidden = state.mode !== "room" || !state.roomId;
    elements["room-camera-buttons"].querySelectorAll("button[data-room-camera]").forEach((b) => {
      b.classList.toggle("active", b.dataset.roomCamera === state.roomCameraPreset);
    });
  }
  if (!elements["floor-camera-presets"]) return;
  const enabled = Boolean(state.buildingId && state.floorId);
  elements["floor-camera-presets"].hidden = !enabled;
  elements["floor-camera-buttons"]?.querySelectorAll("button[data-floor-camera]").forEach((button) => {
    button.classList.toggle("active", button.dataset.floorCamera === state.floorCameraPreset);
  });
}

function setOptions(select, options, selected) {
  select.replaceChildren(...options.map(({ value, label }) => {
    const option = document.createElement("option");
    option.value = value; option.textContent = label; option.selected = value === selected;
    return option;
  }));
  if (options.length && !options.some((option) => option.value === selected)) select.value = options[0].value;
}

function updateBuildingOptions() {
  const items = [...state.data.hierarchy.entities.values()].filter(
    (item) => item.type === "building" && (state.districtId === "all" || item.districtId === state.districtId)
  );
  if (!items.some((item) => item.entity.id === state.buildingId)) state.buildingId = items[0]?.entity.id || "";
  setOptions(elements["building-select"], items.map((item) => ({
    value: item.entity.id, label: `${item.entity.name} · ${item.entity.function}`,
  })), state.buildingId);
  updateFloorOptions();
}

function updateFloorOptions() {
  const items = [...state.data.hierarchy.entities.values()].filter(
    (item) => item.type === "floor" && item.buildingId === state.buildingId
  ).sort((a, b) => a.entity.level - b.entity.level);
  if (!items.some((item) => item.entity.id === state.floorId)) state.floorId = items[0]?.entity.id || "";
  setOptions(elements["floor-select"], items.map((item) => ({
    value: item.entity.id, label: `Level ${item.entity.level} · ${item.entity.id}`,
  })), state.floorId);
  updateRoomOptions();
}

function updateRoomOptions() {
  const useHeroFilter = state.heroRoomOnly && state.heroRoomIds.size > 0;
  const items = [...state.data.hierarchy.entities.values()]
    .filter((item) => (
      item.type === "room"
      && item.floorId === state.floorId
      && (!useHeroFilter || state.heroRoomIds.has(item.entity.id))
      // A setback tower can clip an entire planned room outside its realized
      // footprint. Do not offer such a non-renderable room as a valid Room
      // inspection target.
      && roomHasRealizedWalls(item.entity.id)
    ))
    .sort((a, b) => {
      if (a.entity.function === "corridor" && b.entity.function !== "corridor") return -1;
      if (a.entity.function !== "corridor" && b.entity.function === "corridor") return 1;
      return a.entity.id.localeCompare(b.entity.id);
    });
  if (!items.some((item) => item.entity.id === state.roomId)) {
    state.roomId = items.find((item) => item.entity.function !== "corridor")?.entity.id
      || items[0]?.entity.id || "";
  }
  setOptions(elements["room-select"], items.map((item) => ({
    value: item.entity.id,
    label: `${item.entity.name || item.entity.id} · ${item.entity.function}`,
  })), state.roomId);
}

function roomHasRealizedWalls(roomId) {
  if (!state.data?.roomWallIds?.has(roomId)) return false;
  const indexed = state.data.hierarchy.entities.get(roomId);
  const room = indexed?.entity;
  if (!room) return false;
  const walls = state.data.roomWalls.get(roomId) || [];
  if (!walls.length) return false;
  return hasRoomBoundaries(room, walls);
}

function renderGeometry() {
  if (!state.data || state.contextLost) return;
  updateDepthPrecision();
  applyTheme();
  loadEnvironment(state.data.raw.config);
  state.cameraDirty = true;
  requestStreamDetail();
  // A floor plan is a strict local inspection mode: no city-wide grid or
  // overlay should leak into the selected floor view.
  grid.visible = !["floor_plan", "room"].includes(state.mode) && elements["grid-toggle"].checked;
  if (state.renderProfile === "navigation") {
    renderNavigationPreview();
    updateStreamingStatus();
    return;
  }
  navigationPreviewGroup.visible = state.presentationPreparing;
  setStandardGroupsVisible(!state.presentationPreparing);
  const contentSignature = geometryContentSignature();
  if (
    state.standardGeometryContentSignature === contentSignature
    && geometryGroup.children.length > 0
  ) {
    state.visiblePrimitives = state.standardVisiblePrimitives;
    state.geometryRenderSignature = geometryVisibilitySignature();
    elements["metric-primitives"].textContent = state.visiblePrimitives.length.toLocaleString();
    elements["render-status"].textContent = state.standardRenderStatusText;
    restoreHighlight();
    // The animation loop draws after the asset barrier. Do not repeatedly
    // queue full-city GPU work while a transition is still loading.
    updateStreamingStatus();
    return;
  }
  state.materialTextureUrls = new Set();
  clearGroup(geometryGroup);
  clearAssetGroup();
  clearGroup(navigationGroup);
  clearGroup(pathGroup);
  clearGroup(streetOverlayGroup);
  clearGroup(buildingOutlineGroup);
  clearGroup(labelGroup);
  clearGroup(roomBoundaryGroup);
  clearGroup(floorAnnotationGroup);
  clearGroup(presentationFocusGroup);
  state.highFidelityOverviewAssetIds = state.highFidelityOverview && state.mode === "overview"
    ? selectHighFidelityOverviewAssets(state.data.geometry.primitives)
    : new Set();
  // Discover scope-visible candidates before applying the capture subset.
  // Reusing the previous (initially empty) subset here filters everything out.
  state.prototypeCaptureAssetIds = null;
  state.prototypeCaptureAssetIds = state.renderProfile === "prototype_capture"
    ? selectPrototypeCaptureAssets(state.data.geometry.primitives.filter(isVisiblePrimitive), camera.position, state.observationKind)
    : new Set();
  const groups = new Map();
  const batchSize = renderBatchSize();
  const glassDetail = new Map();
  const materials = new Map(state.data.geometry.materials.map((material) => [material.id, material]));
  let visible = state.data.geometry.primitives.filter(isVisiblePrimitive);
  assetLodIds = new Map();
  assetTexturePixels = new Map();
  assetShadowIds = new Set();
  screenLodStats = {candidates: visible.length, culled: 0, reduced_assets: 0, original_assets: 0, shadow_only: 0};
  if (screenQuality(state.renderProfile)) {
    const screen = currentScreenContext();
    const catalog = state.data.raw.config?.asset_lods || {};
    visible = visible.filter(p => {
      const m = screen.measure(primitiveBounds(p));
      if ((!m.visible && !m.shadow) || m.pixels < 0.75) {screenLodStats.culled++; return false;}
      if (!m.visible) screenLodStats.shadow_only++;
      if (['facade_window','storefront_window','curtain_wall_glass'].includes(p.semantic_class))
        glassDetail.set(p.id, m.visible && m.pixels >= 64);
      if (isResolvedAsset(p)) {
        const original = p.metadata.asset_id;
        const id = chooseAssetLod(original, m.pixels, catalog);
        assetLodIds.set(p.id, id);
        assetTexturePixels.set(id, Math.max(assetTexturePixels.get(id) || 0,m.pixels));
        if (m.pixels >= 8) assetShadowIds.add(p.id);
        screenLodStats[id === original ? 'original_assets' : 'reduced_assets']++;
      }
      return true;
    });
  }
  if (screenQuality(state.renderProfile)) {
    const shadowBounds = new THREE.Box3();
    for (const p of visible) {
      if (isResolvedAsset(p) || ['exterior_wall','interior_wall','roof','roof_parapet','floor_slab',
        'balcony_slab','tree_canopy','street_tree_canopy','vehicle_body','pedestrian_body'].includes(p.semantic_class))
        shadowBounds.union(primitiveBounds(p));
    }
    fitDirectionalShadow(sun, shadowBounds);
  }
  const assetPrimitives = visible.filter(isResolvedAsset);
  if (state.data.groundEdgePrimitives !== state.data.geometry.primitives) {
    state.data.groundEdges = indexGroundEdges(state.data.geometry.primitives, state.data.hierarchy.entities);
    state.data.groundEdgePrimitives = state.data.geometry.primitives;
  }
  state.visiblePrimitives = visible;
  state.geometryRenderSignature = geometryVisibilitySignature();
  state.geometryRebuildCount += 1;

  for (const primitive of visible) {
    if (isResolvedAsset(primitive)) continue;
    const layerType = state.data.layerMap.get(primitive.layer_id)?.layer_type || "unknown";
    const indexed = state.data.hierarchy.entities.get(primitive.owner_id);
    const selectedShell = layerType === "building_shell"
      && indexed?.buildingId === state.buildingId
      && ["building", "floor"].includes(state.mode);
    const scopedShell = hierarchyShell(state.hierarchyDisplay, indexed, layerType);
    const xray = scopedShell || layerType === "building_shell"
      && (state.xray || (state.autoCutaway && selectedShell));
    const error = state.showValidation && primitiveHasError(primitive);
    const sourceMaterial = materials.get(primitive.material_id);
    const uvBucket = materialUvBucket(primitive, sourceMaterial);
    const parcelSurfaceKey = primitive.semantic_class === 'parcel_ground' ? primitive.metadata?.parcel_id || primitive.owner_id : '';
    const detailedGlass = !screenQuality(state.renderProfile) || glassDetail.get(primitive.id) === true;
    const key = `${primitive.primitive_type}|${primitive.material_id}|${primitive.semantic_class}|${scopedShell ? "scoped" : xray ? "xray" : "solid"}|${error ? "error" : "normal"}|${uvBucket || "default_uv"}|${primitive.primitive_type === "path_mesh" ? primitive.id : ""}|${spatialBatch(primitive, batchSize)}|${parcelSurfaceKey}|glass:${detailedGlass}`;
    if (!groups.has(key)) groups.set(key, {
      entries: [], material: sourceMaterial,
      primitiveType: primitive.primitive_type, semantic: primitive.semantic_class, xray, scopedShell, error, facade: false, uvBucket, detailedGlass,
    });
    groups.get(key).entries.push(primitive);
    groups.get(key).facade ||= String(primitive.metadata?.facade_system || "").startsWith("grammar_");
  }

  for (const group of groups.values()) {
    const source = group.material || {};
    const sourceColor = source.display_color
      ? new THREE.Color(...source.display_color)
      : new THREE.Color(0x8aa39c);
    const useSemanticInstanceColors = state.appearanceMode === "semantic";
    const useClayMaterial = state.appearanceMode === "clay";
    const useInstanceColors = useSemanticInstanceColors || group.error;
    const facadeGlass = ["facade_window", "storefront_window", "curtain_wall_glass"].includes(group.semantic);
    const clayColor = facadeGlass
      ? new THREE.Color(0x7895a0)
      : new THREE.Color(group.facade ? 0xd5cfc2 : 0xbcc2bd);
    const materialOptions = {
      color: useInstanceColors ? 0xffffff : useClayMaterial ? clayColor : sourceColor,
      roughness: useClayMaterial ? (facadeGlass ? 0.28 : 0.82) : source.roughness ?? 0.75,
      metalness: useClayMaterial ? 0 : source.metallic ?? 0,
      transparent: group.xray || (source.opacity ?? 1) < 1 || (facadeGlass && !useClayMaterial && !useSemanticInstanceColors),
      opacity: group.xray ? (group.scopedShell ? state.hierarchyDisplay.shell_opacity : 0.16) : facadeGlass && !useClayMaterial && !useSemanticInstanceColors ? 0.88 : source.opacity ?? 1,
      depthWrite: !group.xray,
      clippingPlanes: group.scopedShell ? hierarchyClipPlanes() : [],
      vertexColors: useInstanceColors,
      // Use actual surface elevations and the adaptive aerial near plane.
      // A slope-scaled negative offset on parcel ground pulls it in front of
      // raised paths, planting beds and low furniture at oblique viewpoints.
      polygonOffset: false,
    };
    const physicalGlass = RENDER_PROFILES[state.renderProfile].physicalGlass
      && group.detailedGlass && facadeGlass && !useClayMaterial && !useSemanticInstanceColors && !group.xray;
    const riverConfig=state.data.raw.config.river_surface || {};
    const river=group.semantic==='river_water' && !group.error && !group.xray
      && !useClayMaterial && !useSemanticInstanceColors && RENDER_PROFILES[state.renderProfile].materialTextures
      && riverConfig.enabled!==false
      ? (state.data.city.rivers || []).find(r=>r.id===(group.entries[0].metadata?.river_id || group.entries[0].owner_id)) : null;
    const material = physicalGlass
      ? new THREE.MeshPhysicalMaterial({
          ...materialOptions,
          transmission: group.semantic === "curtain_wall_glass" ? 0.42 : 0.28,
          thickness: 0.08,
          ior: 1.46,
          clearcoat: 0.16,
          clearcoatRoughness: 0.22,
          envMapIntensity: 1.35,
        })
      : river ? new THREE.MeshPhysicalMaterial({...materialOptions, metalness:0,
          roughness:.34, ior:1.333, clearcoat:0,
          envMapIntensity:.65, transparent:false, opacity:1})
        : new THREE.MeshStandardMaterial(materialOptions);
    if(river)installRiverSurface(material,river,riverConfig);
    if (group.error) {
      material.emissive.setHex(0x6b1010);
      material.emissiveIntensity = 0.65;
    } else if (useSemanticInstanceColors && !group.xray) {
      material.emissive.setHex(semanticPalette[group.semantic] || 0x8aa39c);
      material.emissiveIntensity = state.daylight ? 0.13 : 0.2;
    } else if (!useClayMaterial && facadeGlass && !group.xray) {
      material.emissive.copy(sourceColor).multiplyScalar(0.10);
      material.emissiveIntensity = state.daylight ? 0.32 : 0.45;
    }
    if (
      (RENDER_PROFILES[state.renderProfile].materialTextures
        || (state.renderProfile === "review" && state.observationKind === "building_exterior"
          && group.entries.some((entry) => state.observationTargetIds.has(
            state.data.hierarchy.entities.get(entry.owner_id)?.buildingId))))
      && !useSemanticInstanceColors && !useClayMaterial && !group.xray
    ) {
      loadMaterialTextures(material, group.material?.id, source);
      const surfaceConfig = state.data.raw.config.ground_surface || {};
      if (group.semantic === 'parcel_ground' && !group.error && surfaceConfig.enabled !== false) {
        const first = group.entries[0];
        const parcel = state.data.hierarchy.entities.get(first.metadata?.parcel_id || first.owner_id)?.entity;
        const plan = groundSurfacePlan(parcel, source.id, state.data.groundEdges);
        if (plan) {
          const otherId = plan.green ? 'courtyard_paving' : 'parcel_lawn';
          // Ground shader applies each surface's tint after mixing; the old
          // base colour must not tint the secondary surface as well.
          if (state.data.raw.config.material_textures?.[source.id]?.base_color) material.color.setHex(0xffffff);
          const receive = installGroundSurface(material, plan, {
            strength: surfaceConfig.strength ?? 1,
            otherScale: materials.get(otherId)?.texture_scale_m || 4,
          });
          loadMaterialTextures(material, otherId, materials.get(otherId), receive);
        }
      }
    }
    const mesh = new THREE.InstancedMesh(
      primitiveGeometry(group.primitiveType, group.uvBucket, group.entries[0], source), material, group.entries.length
    );
    mesh.userData.entries = group.entries;
    mesh.castShadow = [
      "exterior_wall", "roof", "roof_parapet", "balcony_slab",
      "tree_canopy", "street_tree_canopy", "vehicle_body", "pedestrian_body",
      "bridge_deck", "bridge_parapet", "bridge_abutment", "river_bank",
    ].includes(group.semantic);
    mesh.receiveShadow = true;
    group.entries.forEach((primitive, index) => {
      mesh.setMatrixAt(index, primitiveMatrix(primitive));
      if (useInstanceColors) {
        const color = group.error
          ? new THREE.Color(0xff4242)
          : useSemanticInstanceColors
            ? new THREE.Color(semanticPalette[primitive.semantic_class] || 0x8aa39c)
            : sourceColor;
        mesh.setColorAt(index, color);
      }
    });
    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
    mesh.computeBoundingSphere();
    geometryGroup.add(mesh);
  }
  elements["metric-primitives"].textContent = visible.length.toLocaleString();
  elements["render-status"].textContent = `${visible.length.toLocaleString()} / ${state.data.geometry.primitives.length.toLocaleString()} primitives · ${groups.size} groups · ${assetPrimitives.length} GLB · ${state.renderProfile}`;
  state.standardGeometryContentSignature = contentSignature;
  state.standardVisiblePrimitives = visible;
  state.standardRenderStatusText = elements["render-status"].textContent;
  renderResolvedAssets(assetPrimitives);
  if (state.mode !== "floor_plan") {
    if (state.showRoadMarkings) renderRoadMarkings();
    if (state.showOutlines) renderBuildingOutlines();
    if (state.showLabels) renderBuildingLabels();
    if (state.showNavigation) renderNavigation();
  }
  if (state.mode === "room") renderRoomBoundary();
  if (["floor", "floor_plan"].includes(state.mode)) renderFloorAnnotations();
  renderPresentationFocus();
  restoreHighlight();
  updateStreamingStatus();
}

function setStandardGroupsVisible(visible) {
  for (const group of [
    geometryGroup, assetGroup, streetOverlayGroup, buildingOutlineGroup,
    overlayGroup, navigationGroup, pathGroup, labelGroup, roomBoundaryGroup,
    floorAnnotationGroup, presentationFocusGroup,
  ]) group.visible = visible;
}

function finishPresentationPreparation() {
  if (!state.presentationPreparing) return true;
  const status = observationAssetStatus();
  if (!canPresent(status)) return false;
  state.presentationPreparing = false;
  navigationPreviewGroup.visible = false;
  setStandardGroupsVisible(true);
  elements['render-status'].textContent = state.standardRenderStatusText;
  state.cameraDirty = true;
  return true;
}

function renderNavigationPreview() {
  setStandardGroupsVisible(false);
  navigationPreviewGroup.visible = true;
  const contentSignature = geometryContentSignature();
  if (
    state.navigationGeometryContentSignature === contentSignature
    && navigationPreviewGroup.children.length > 0
  ) {
    state.geometryRenderSignature = geometryVisibilitySignature();
    renderer.render(scene, camera);
    state.cameraDirty = false;
    return;
  }
  clearGroup(navigationPreviewGroup);
  const visible = state.data.geometry.primitives.filter(isVisiblePrimitive);
  const groups = new Map();
  for (const primitive of visible) {
    const proxyType = primitive.primitive_type === "mesh" ? "box" : primitive.primitive_type;
    const key = `${proxyType}|${primitive.semantic_class}|${proxyType === "path_mesh" ? primitive.id : ""}`;
    if (!groups.has(key)) groups.set(key, {
      entries: [], primitiveType: proxyType, semantic: primitive.semantic_class,
    });
    groups.get(key).entries.push(primitive);
  }
  for (const group of groups.values()) {
    const material = new THREE.MeshBasicMaterial({
      color: semanticPalette[group.semantic] || 0x8aa39c,
      fog: true,
    });
    const mesh = new THREE.InstancedMesh(
      primitiveGeometry(group.primitiveType, "", group.entries[0]), material, group.entries.length,
    );
    mesh.userData.entries = group.entries;
    group.entries.forEach((primitive, index) => mesh.setMatrixAt(index, primitiveMatrix(primitive)));
    mesh.instanceMatrix.needsUpdate = true;
    mesh.computeBoundingSphere();
    navigationPreviewGroup.add(mesh);
  }
  state.visiblePrimitives = visible;
  state.navigationGeometryContentSignature = contentSignature;
  state.geometryRenderSignature = geometryVisibilitySignature();
  state.geometryRebuildCount += 1;
  elements["metric-primitives"].textContent = visible.length.toLocaleString();
  elements["render-status"].textContent = `${visible.length.toLocaleString()} / ${state.data.geometry.primitives.length.toLocaleString()} primitives · ${groups.size} proxy groups · navigation`;
  renderer.render(scene, camera);
  state.cameraDirty = false;
}

const unitCylinder = new THREE.CylinderGeometry(0.5, 0.5, 1, 12, 1, false);
unitCylinder.rotateX(Math.PI / 2);
const unitSphere = new THREE.IcosahedronGeometry(0.5, 1);

function primitiveGeometry(type, uvBucket = "", primitive = null, material = {}) {
  if (type === "path_mesh" && primitive) {
    const geometry = new THREE.BufferGeometry();
    const vertices = primitive.metadata.mesh_vertices;
    geometry.setAttribute("position", new THREE.Float32BufferAttribute(vertices.flat(), 3));
    geometry.setIndex(primitive.metadata.mesh_triangles.flat());
    const scale = Number(material.texture_scale_m || 4);
    const uv = vertices.flatMap(([x, y]) => [
      (x * primitive.size.x + primitive.center.x) / scale,
      (y * primitive.size.y + primitive.center.y) / scale,
    ]);
    geometry.setAttribute("uv", new THREE.Float32BufferAttribute(uv, 2));
    geometry.setAttribute("uv1", geometry.getAttribute("uv"));
    geometry.setAttribute("uv2", geometry.getAttribute("uv"));
    geometry.computeVertexNormals();
    return geometry;
  }
  if (type === "cylinder") return unitCylinder;
  if (type === "sphere") return unitSphere;
  if (uvBucket) return texturedBoxGeometry(uvBucket);
  return unitBox;
}

function materialUvBucket(primitive, material) {
  const scale = Number(material?.texture_scale_m || 0);
  if (primitive.primitive_type !== "box" || scale <= 0) return "";
  const quantize = (value) => Math.max(0.5, Math.round((value / scale) * 2) / 2);
  return [quantize(primitive.size.x), quantize(primitive.size.y), quantize(primitive.size.z)].join(",");
}

function texturedBoxGeometry(bucket) {
  if (texturedBoxCache.has(bucket)) return texturedBoxCache.get(bucket);
  const [x, y, z] = bucket.split(",").map(Number);
  const geometry = unitBox.clone();
  const uv = geometry.getAttribute("uv");
  const faceScales = [[y, z], [y, z], [x, z], [x, z], [x, y], [x, y]];
  faceScales.forEach(([uScale, vScale], face) => {
    for (let vertex = face * 4; vertex < face * 4 + 4; vertex += 1) {
      uv.setXY(vertex, uv.getX(vertex) * uScale, uv.getY(vertex) * vScale);
    }
  });
  uv.needsUpdate = true;
  geometry.setAttribute("uv1", uv);
  geometry.setAttribute("uv2", uv);
  texturedBoxCache.set(bucket, geometry);
  geometry.userData.citygSharedGeometry = true;
  return geometry;
}

function loadMaterialTextures(material, materialId, source, receive = null) {
  const mapping = state.data?.raw?.config?.material_textures?.[materialId];
  if (!mapping) return;
  const base = state.data?.raw?.config?.texture_base || "/texture/";
  const load = (channel, assign) => {
    const filename = mapping[channel];
    if (!filename) return;
    const url = `${base.endsWith("/") ? base : `${base}/`}${encodeURIComponent(filename)}`;
    state.materialTextureUrls.add(url);
    bindSharedTexture({promises:textureCache,ready:readyMaterialTextures,
      owned:sharedMaterialTextures,states:textureLoadStates,load:u=>textureLoader.loadAsync(u)},url,(texture) => {
      if (material.userData.citygDisposed) return;
      texture.wrapS = THREE.RepeatWrapping;
      texture.wrapT = THREE.RepeatWrapping;
      if (channel === "base_color") texture.colorSpace = THREE.SRGBColorSpace;
      if (receive) receive(channel, texture);
      else assign(texture);
      material.needsUpdate = true;
      state.cameraDirty = true;
    });
  };
  load("base_color", (texture) => { material.map = texture; });
  load("normal", (texture) => { material.normalMap = texture; });
  load("roughness", (texture) => { material.roughnessMap = texture; });
  load("ambient_occlusion", (texture) => { material.aoMap = texture; material.aoMapIntensity = 0.72; });
}

let environmentPromise = Promise.resolve();
let environmentState = 'idle';
let environmentGeneration = 0;
function desiredEnvironment(config) {
  const preset = skyAllowed(state.mode,state.daylight,RENDER_PROFILES[state.renderProfile],state.skyPreset,config?.sky_presets)
    ? config.sky_presets[state.skyPreset] : null;
  const filename = preset?.file || config?.environment_file;
  const base = config?.environment_base || '/environment/';
  return {preset,filename,url:filename ? `${base.endsWith('/') ? base : `${base}/`}${encodeURIComponent(filename)}` : ''};
}

function loadEnvironment(config) {
  if (state.contextLost) return;
  if (!RENDER_PROFILES[state.renderProfile].environment) {
    scene.environment = null;
    return;
  }
  // Opt-in only for isolated interior showcase packages. A neutral reflection
  // probe keeps metallic/varnished assets readable without changing city skies.
  if (state.mode === 'room' && state.data?.geometry.metadata?.room_studio_environment === true) {
    if (!indoorStudioTarget) {
      const studio = new RoomEnvironment();
      indoorStudioTarget = pmremGenerator.fromScene(studio, .04);
      studio.dispose();
    }
    scene.environment = indoorStudioTarget.texture;
    scene.environmentIntensity = .65;
    environmentState = 'ready';
    return;
  }
  const {url} = desiredEnvironment(config);
  if (!url) {scene.environment=null;environmentState='idle';return;}
  if (environmentCache.has(url)) {
    currentEnvironmentUrl=url;
    environmentTarget=environmentCache.get(url).target;
    environmentState='ready';
    scene.environment=environmentTarget.texture;
    return;
  }
  if (url === currentEnvironmentUrl && environmentState === 'pending') return environmentPromise;
  currentEnvironmentUrl = url;
  environmentState = 'pending';
  const generation = environmentGeneration;
  scene.environment = null;
  environmentPromise = (async () => {
  try {
    if (!environmentLoads.has(url)) environmentLoads.set(url, (async () => {
      const source = await rgbeLoader.loadAsync(url);
      if (state.contextLost || generation !== environmentGeneration) { source.dispose(); throw new Error('WebGL context unavailable'); }
      source.mapping = THREE.EquirectangularReflectionMapping;
      const analysis = analyzeSky(source);
      const target = pmremGenerator.fromEquirectangular(source);
      const entry={source,target,analysis};
      environmentCache.set(url,entry);
      return entry;
    })());
    const entry=await environmentLoads.get(url);
    if (url !== desiredEnvironment(state.data?.raw.config).url || !RENDER_PROFILES[state.renderProfile].environment) return;
    environmentTarget = entry.target;
    environmentState = 'ready';
    scene.environment = entry.target.texture;
    applyTheme();
    state.cameraDirty = true;
    // Environment is a scene binding, not a geometry change. Rebuilding here
    // used to cancel/restart every GLB load as soon as the HDR completed.
  } catch (error) {
    if (generation !== environmentGeneration) return;
    environmentLoads.delete(url);
    if (url !== currentEnvironmentUrl) return;
    environmentState = 'failed';
    console.warn("CityG: failed to load HDR environment", error);
  }
  })();
  return environmentPromise;
}

function isResolvedAsset(primitive) {
  if (state.renderProfile === "navigation") return false;
  const resolved = primitive.primitive_type === "mesh"
    && primitive.metadata?.resolved_asset
    && Boolean(primitive.metadata?.asset_id);
  if (highFidelityOverviewAsset(primitive)) return true;
  if (!resolved || state.renderProfile !== "review") return resolved;
  // Local inspections need true silhouettes and front directions.  City-wide
  // views instead render repeated assets as instanced semantic proxy boxes;
  // this keeps spatial density visible while avoiding thousands of cloned GLB
  // scene graphs in software-rendered Chromium.
  if (["room", "floor", "floor_plan"].includes(state.mode)) return true;
  if (!["road", "landscape", "building_exterior"].includes(state.observationKind)) {
    return false;
  }
  const indexed = state.data.hierarchy.entities.get(primitive.owner_id);
  const lineage = new Set([
    primitive.owner_id,
    ...(indexed ? state.data.hierarchy.lineage(primitive.owner_id) : []),
  ]);
  if (matchesLocalAssetTarget(lineage, state.observationTargetIds, state.data.hierarchy.entities, primitive.metadata)) return true;
  if (state.observationKind === "building_exterior") {
    const targetBuilding = [...state.observationTargetIds].find(
      (id) => state.data.hierarchy.entities.get(id)?.type === "building"
    );
    return Boolean(targetBuilding && indexed?.buildingId === targetBuilding);
  }
  return false;
}

function stableReviewBucket(value, modulo) {
  // FNV-1a gives stable sampling across browsers and repeated review rounds;
  // unlike array-index sampling it does not change when unrelated geometry is
  // inserted earlier in the manifest.
  let hash = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0) % modulo;
}

function reviewLodVisible(primitive) {
  if (state.renderProfile === "prototype_capture" && outdoorCaptureCandidate(primitive)
      && state.prototypeCaptureAssetIds && !state.prototypeCaptureAssetIds.has(primitive.id)) return false;
  if (
    state.mode === "overview"
    && state.highFidelityOverview
    && !screenQuality(state.renderProfile)
    && primitive.metadata?.resolved_asset
    && !highFidelityOverviewAsset(primitive)
  ) return false;
  if (state.renderProfile !== "review") return true;
  // Floor and room observations are already strictly localized by
  // isVisiblePrimitive.  They are precisely the views where every wall,
  // doorway and furniture item matters, so no further thinning is allowed.
  if (["room", "floor", "floor_plan"].includes(state.mode)) return true;

  const indexed = state.data.hierarchy.entities.get(primitive.owner_id);
  const layerType = state.data.layerMap.get(primitive.layer_id)?.layer_type || "unknown";
  const targetBuildings = [...state.observationTargetIds].filter(
    (id) => state.data.hierarchy.entities.get(id)?.type === "building"
  );
  const inspectedBuilding = targetBuildings.length === 1 ? targetBuildings[0] : null;
  const isInspectedBuilding = Boolean(
    inspectedBuilding && indexed?.buildingId === inspectedBuilding
  );

  // A legacy observation plan may still contain full-mode facade views.  In
  // review mode, make those equivalent to a shell/street view instead of
  // materializing the entire city's interiors.
  if (!["roads", "building_shell", "district", "root"].includes(layerType)) {
    return false;
  }

  const semantic = primitive.semantic_class;
  if (layerType !== "building_shell") return true;

  // Preserve the entire facade rhythm of an explicitly inspected building.
  // Randomly dropping half its windows makes paired/ribbon grammars look
  // broken and gives the VLM false evidence. Only background shells are thinned.
  if (semantic === "facade_asset_window") return isInspectedBuilding;
  if (semantic === "window_backing") return isInspectedBuilding;

  if (["facade_window", "curtain_wall_glass"].includes(semantic)) {
    if (semantic === "curtain_wall_glass") return true;
    return Boolean(state.streaming) || isInspectedBuilding || stableReviewBucket(primitive.id, 8) === 0;
  }
  if ([
    "facade_frame", "facade_fin", "facade_spandrel_band",
    "facade_zone_band", "mechanical_louver", "balcony_rail",
  ].includes(semantic)) {
    return isInspectedBuilding || stableReviewBucket(primitive.id, 5) === 0;
  }
  return true;
}

const NAVIGATION_ROAD_CONTEXT = new Set([
  "river_water", "river_bank", "river_promenade", "riparian_green",
  "bridge_deck", "bridge_parapet", "bridge_railing", "bridge_abutment", "parcel_ground",
  "road_surface", "junction_surface", "sidewalk", "curb", "lane_marking",
  "crosswalk", "road_median", "bicycle_lane_surface", "stop_line",
  "city_ground", "parcel_surface_patch", "parcel_edge", "landscape_path",
  "plaza", "grass", "landscape_patch",
]);
const NAVIGATION_SHELL_CONTEXT = new Set([
  "exterior_wall", "roof", "roof_parapet", "roof_monitor", "floor_slab",
  "facade_ground_band", "entrance_portal",
  "curtain_wall_glass",
]);
const NAVIGATION_LOCAL_INTERIOR = new Set(["floor_slab", "interior_wall", "door"]);
const NAVIGATION_PROXY_ASSETS = new Map([
  ["street_tree_asset", 5], ["park_tree_asset", 5], ["parcel_tree_asset", 6],
  ["street_light_asset", 5], ["vehicle_asset", 10], ["pedestrian_asset", 18],
  ["street_bench", 8], ["bench", 10],
]);

function navigationPreviewVisible(primitive, layerType) {
  if (state.renderProfile !== "navigation") return true;
  // Resolved GLBs and repeated street props are the main source of camera
  // hitching.  Navigation mode intentionally uses only lightweight proxy
  // primitives until the user switches back to Presentation.
  const semantic = primitive.semantic_class;
  if (primitive.metadata?.resolved_asset || primitive.primitive_type === "mesh") {
    const modulo = NAVIGATION_PROXY_ASSETS.get(semantic);
    return Boolean(modulo && stableReviewBucket(primitive.id, modulo) === 0);
  }
  if (layerType === "roads" || layerType === "district" || layerType === "root") {
    if (!NAVIGATION_ROAD_CONTEXT.has(semantic)) return false;
    // Keep road hierarchy legible while sampling repetitive paint strips and
    // paving patches.  Surfaces/curbs/medians are retained in full.
    if (["lane_marking", "crosswalk", "bicycle_lane_surface", "parcel_surface_patch"].includes(semantic)) {
      return stableReviewBucket(primitive.id, semantic === "parcel_surface_patch" ? 2 : 3) === 0;
    }
    return true;
  }
  if (layerType === "building_shell") {
    if (NAVIGATION_SHELL_CONTEXT.has(semantic)) return true;
    if (semantic === "facade_window") return Boolean(state.streaming) || stableReviewBucket(primitive.id, 10) === 0;
    if (["facade_frame", "facade_fin", "balcony_rail"].includes(semantic)) {
      return stableReviewBucket(primitive.id, 18) === 0;
    }
    return false;
  }
  if (layerType === "floor") return NAVIGATION_LOCAL_INTERIOR.has(semantic);
  return false;
}

function primitiveBelongsToSelectedFloor(primitive, indexed = state.data?.hierarchy.entities.get(primitive.owner_id)) {
  if (!indexed || !state.floorId) return false;
  if (indexed.floorId === state.floorId) return true;
  if (indexed.type === "vertical_connector") {
    const selectedFloor = state.data?.hierarchy.entities.get(state.floorId)?.entity;
    const selectedFloorIndexed = state.data?.hierarchy.entities.get(state.floorId);
    // Connector geometry is shared across all served levels, but never across
    // buildings.  Level-only matching would make every building's level-0
    // stair run appear in the selected building's floor view.
    if (!selectedFloorIndexed?.buildingId || indexed.buildingId !== selectedFloorIndexed.buildingId) {
      return false;
    }
    if (primitive.semantic_class === "stair_tread" && primitive.metadata?.from_level !== undefined) {
      return Number(selectedFloor?.level) === Number(primitive.metadata.from_level);
    }
    if (primitive.metadata?.served_level !== undefined) {
      return Number(selectedFloor?.level) === Number(primitive.metadata.served_level);
    }
    if (primitive.semantic_class === "elevator_cabin" || primitive.semantic_class === "elevator_cabin_door") {
      const machineId = primitive.metadata?.state_machine_id;
      const currentState = machineId ? state.doorStates.get(machineId) : null;
      const level = String(currentState || "").replace("level_", "");
      return Number(selectedFloor?.level) === Number(level);
    }
    return indexed.floorIds?.includes(state.floorId) || false;
  }
  const servedLevel = primitive.metadata?.served_level;
  if (servedLevel === undefined || !indexed.buildingId) return false;
  const building = state.data?.hierarchy.entities.get(indexed.buildingId)?.entity;
  const servedFloor = (building?.floors || []).find((floor) => Number(floor.level) === Number(servedLevel));
  return servedFloor?.id === state.floorId;
}

function assetUrl(assetId) {
  const config = state.data?.raw?.config || {};
  const base = config.asset_base || "/asset/";
  const filename = config.asset_files?.[assetId] || `${assetId}.glb`;
  return `${base.endsWith("/") ? base : `${base}/`}${encodeURIComponent(filename)}`;
}

async function loadAssetTemplate(key) {
  return assetTemplates.get(key);
}

function renderBatchSize() {
  // At city altitude the candidate list has already been screen-culled. Batch
  // the visible copies together instead of submitting each tiny spatial tile.
  // Local views retain spatial batches for inexpensive camera-motion culling.
  return screenQuality(state.renderProfile) && ['overview','full'].includes(state.mode)
    && camera.position.z - controls.target.z > 500 ? Infinity : 160;
}

function renderResolvedAssets(primitives) {
  const generation = state.assetRenderGeneration;
  // Capture the LOD mapping before any await: a newer camera can replace it.
  const lodIds = new Map(assetLodIds);
  const shadowIds = new Set(assetShadowIds);
  const useScreenShadows = screenQuality(state.renderProfile);
  const templateKeys = new Map();
  for (const p of primitives) {
    const id=lodIds.get(p.id) || p.metadata.asset_id;
    templateKeys.set(id,JSON.stringify([assetUrl(id),textureEdgeForPixels(assetTexturePixels.get(id) ?? Infinity)]));
  }
  assetTemplates.retain(templateKeys.values());
  const status = {
    generation,
    expected: primitives.length,
    pending: primitives.length,
    loaded: 0,
    cached: 0,
    fallback: 0,
    failed: 0,
    errors: [],
    ready: primitives.length === 0,
  };
  state.assetLoadState = status;
  if (!primitives.length) {
    state.assetReadyPromise = Promise.resolve({ ...status });
    return;
  }
  const byAsset = new Map();
  const batchSize = renderBatchSize();
  for (const primitive of primitives) {
    const id = `${lodIds.get(primitive.id) || primitive.metadata.asset_id}|scoped:${primitiveScopedShell(primitive)}|${spatialBatch(primitive, batchSize)}|shadow:${!useScreenShadows || shadowIds.has(primitive.id)}`;
    if (!byAsset.has(id)) byAsset.set(id, []);
    byAsset.get(id).push(primitive);
  }
  const renderSingle = async (primitive) => {
    const assetId = lodIds.get(primitive.id) || primitive.metadata.asset_id;
    const scoped = primitiveScopedShell(primitive);
    const objectCacheKey = `${primitive.id}|${assetId}|xray:${state.xray ? 1 : 0}|scope:${scoped ? JSON.stringify(state.hierarchyDisplay) : "none"}`;
    try {
      if (state.assetObjectCache.has(objectCacheKey)) {
        if (generation !== state.assetRenderGeneration || !state.data) return;
        assetGroup.add(state.assetObjectCache.get(objectCacheKey));
        status.loaded += 1;
        status.cached += 1;
        return;
      }
      const template = await loadAssetTemplate(templateKeys.get(assetId));
      if (generation !== state.assetRenderGeneration || !state.data) return;
      const object = template.clone(true);
      object.position.set(primitive.center.x, primitive.center.y, primitive.center.z);
      object.rotation.z = THREE.MathUtils.degToRad(primitive.rotation_z_deg || 0);
      object.scale.set(primitive.size.x, primitive.size.y, primitive.size.z);
      object.userData.entry = primitive;
      object.traverse((node) => {
        if (!node.isMesh) return;
        node.userData.entry = primitive;
        node.castShadow = !useScreenShadows || shadowIds.has(primitive.id);
        node.receiveShadow = true;
        if (state.xray || scoped) {
          const owned = Array.isArray(node.material)
            ? node.material.map((material) => makeXrayMaterial(material, scoped))
            : [makeXrayMaterial(node.material, scoped)];
          node.material = Array.isArray(node.material) ? owned : owned[0];
          node.userData.citygOwnedMaterials = owned;
        }
      });
      state.assetObjectCache.set(objectCacheKey, object);
      assetGroup.add(object);
      if (generation === state.assetRenderGeneration) status.loaded += 1;
    } catch (error) {
      if (generation === state.assetRenderGeneration) {
        console.warn(`CityG: failed to load GLB asset ${assetId}`, error);
        if (status.errors.length < 32) status.errors.push({
          asset_id: assetId, primitive_id: primitive.id,
          reason: String(error?.message || error).slice(0, 500),
        });
        try {
          addAssetFallback(primitive);
          status.fallback += 1;
        } catch (fallbackError) {
          console.warn(`CityG: failed to create fallback for ${assetId}`, fallbackError);
          status.failed += 1;
        }
      }
    } finally {
      if (generation === state.assetRenderGeneration) {
        status.pending = Math.max(0, status.pending - 1);
      }
    }
  };
  const tasks = runAssetBatches([...byAsset.values()], async (entries) => {
    const assetId = lodIds.get(entries[0].id) || entries[0].metadata.asset_id;
    if (!state.xray && !primitiveScopedShell(entries[0])) {
      try {
        const template = await loadAssetTemplate(templateKeys.get(assetId));
        if (generation !== state.assetRenderGeneration || !state.data) return;
        const batches = instanceAsset(template, entries, primitiveMatrix);
        if (batches) {
          const castShadow = !useScreenShadows || entries.some(p => shadowIds.has(p.id));
          for (const mesh of batches) { mesh.castShadow = castShadow; assetGroup.add(mesh); }
          status.loaded += entries.length;
          status.pending -= entries.length;
          return;
        }
      } catch (error) {
        // Retain the existing per-object fallback/error accounting below.
      }
    }
    for (const entry of entries) {
      if (generation !== state.assetRenderGeneration) return;
      await renderSingle(entry);
    }
  }, () => generation === state.assetRenderGeneration && !state.contextLost);
  state.assetReadyPromise = tasks.then(() => {
    if (generation === state.assetRenderGeneration) {
      status.pending = 0;
      status.ready = status.failed === 0;
      restoreHighlight();
      // Review mode does not run an unconditional animation loop. Draw once
      // when the asynchronous GLB barrier opens so interactive and automated
      // consumers both see the completed scene without requiring camera input.
      state.cameraDirty = true;
    }
    return { ...status, ready: generation === state.assetRenderGeneration && status.ready };
  });
}

function primitiveScopedShell(primitive) {
  return hierarchyShell(state.hierarchyDisplay,
    state.data.hierarchy.entities.get(primitive.owner_id),
    state.data.layerMap.get(primitive.layer_id)?.layer_type);
}

function renderPresentationFocus() {
  if (!state.presentationFocusId) return;
  const id = state.presentationFocusId;
  const box = new THREE.Box3();
  for (const p of state.visiblePrimitives) {
    const indexed = state.data.hierarchy.entities.get(p.owner_id);
    if (p.owner_id === id || indexed?.floorId === id || indexed?.roomId === id
        || p.metadata?.room_ids?.includes(id)) expandBoxByPrimitive(box, p);
  }
  if (box.isEmpty()) return;
  const helper = new THREE.Box3Helper(box, 0xd97028);
  helper.material.depthTest = false;
  helper.material.toneMapped = false;
  helper.renderOrder = 100;
  presentationFocusGroup.add(helper);
}

function hierarchyClipPlanes() {
  const z = state.hierarchyDisplay?.cut_above_m;
  return Number.isFinite(z) ? [new THREE.Plane(new THREE.Vector3(0, 0, -1), z)] : [];
}

function makeXrayMaterial(source, scoped = false) {
  const material = source.clone();
  material.transparent = true;
  material.opacity = scoped ? state.hierarchyDisplay.shell_opacity : Math.min(material.opacity ?? 1, 0.24);
  material.clippingPlanes = scoped ? hierarchyClipPlanes() : [];
  material.depthWrite = false;
  return material;
}

function addAssetFallback(primitive) {
  const material = new THREE.MeshStandardMaterial({
    color: semanticPalette[primitive.semantic_class] || 0x8aa39c,
    roughness: 0.78,
    transparent: state.xray,
    opacity: state.xray ? 0.2 : 1,
  });
  const mesh = new THREE.Mesh(unitBox, material);
  mesh.matrixAutoUpdate = false;
  mesh.matrix.copy(primitiveMatrix(primitive));
  mesh.userData.entry = primitive;
  mesh.userData.citygOwnedMaterials = [material];
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  assetGroup.add(mesh);
}

function isVisiblePrimitive(primitive) {
  if (taskReplay?.suppressed(primitive.id)) return false;
  if (primitive.semantic_class === "collision_envelope") return false;
  if (primitive.metadata?.viewer_room_only && state.mode !== "room") return false;
  if (!state.enabledSemantics.has(primitive.semantic_class)) return false;
  const indexed = state.data.hierarchy.entities.get(primitive.owner_id);
  if (state.districtId !== "all" && indexed?.districtId && indexed.districtId !== state.districtId) return false;
  const layerType = state.data.layerMap.get(primitive.layer_id)?.layer_type || "unknown";
  if (!navigationPreviewVisible(primitive, layerType)) return false;
  if (state.hierarchyDisplay && ["overview", "building", "full"].includes(state.mode)) {
    return hierarchyVisible(state.hierarchyDisplay, indexed, layerType,
      primitiveBelongsToSelectedFloor(primitive, indexed)) && reviewLodVisible(primitive);
  }
  if (state.mode === "room") {
    if (!roomHasRealizedWalls(state.roomId)) return false;
    // Explicit showcase ceilings remain in eye-level shots, not plan/cutaway views.
    if (primitive.metadata?.room_ceiling && state.roomCameraPreset !== "eye") return false;
    if (state.roomCameraPreset === "cutaway" &&
        (["interior_wall", "door"].includes(primitive.semantic_class)
         || primitive.metadata?.support_kind === "wall")) {
      const frame = roomDisplayFrame(state.roomId);
      if (frame) {
        const dx = primitive.center.x-frame.centerX, dy = primitive.center.y-frame.centerY;
        const x = dx*Math.cos(frame.rotation)+dy*Math.sin(frame.rotation);
        const y = -dx*Math.sin(frame.rotation)+dy*Math.cos(frame.rotation);
        if (x > frame.width*.32 || y < -frame.depth*.32) return false;
      }
    }
    if (indexed?.roomId === state.roomId || state.data.hierarchy.lineage(primitive.owner_id).includes(state.roomId)) return reviewLodVisible(primitive);
    if (Array.isArray(primitive.metadata?.room_ids) && primitive.metadata.room_ids.includes(state.roomId)) return reviewLodVisible(primitive);
    if (indexed?.type === "door" && indexed.roomIds?.includes(state.roomId)) return reviewLodVisible(primitive);
    return false;
  }
  if (state.mode === "overview") return ["roads", "building_shell", "district", "root"].includes(layerType) && reviewLodVisible(primitive);
  if (state.mode === "building") {
    if (
      state.autoCutaway
      && indexed?.buildingId === state.buildingId
      && layerType === "building_shell"
      && (["roof", "roof_monitor"].includes(primitive.semantic_class) || primitive.metadata?.roof_system)
    ) return false;
    return (["roads", "building_shell", "district", "root"].includes(layerType) || indexed?.buildingId === state.buildingId) && reviewLodVisible(primitive);
  }
  if (state.mode === "floor") {
    if (
      state.autoCutaway
      && indexed?.buildingId === state.buildingId
      && layerType === "building_shell"
      && (["roof", "roof_monitor"].includes(primitive.semantic_class) || primitive.metadata?.roof_system)
    ) return false;
    if (layerType === "building_shell") {
      // Keep the selected building's silhouette as a transparent context, but
      // do not leave every other city building/road in a floor inspection.
      // Building-owned rooftop/entry decorations are not floor geometry.  If
      // they are kept here, a floor camera can show small floating objects
      // well above or outside the selected level (for example a rooftop
      // planter or an entrance canopy).  Floor-owned facade bays remain
      // visible, while the building-level silhouette is reduced to its
      // exterior wall massing only.
      const sameBuilding = indexed?.buildingId === state.buildingId;
      const shellOwnerIsSelectedFloor = indexed?.floorId === state.floorId;
      const shellOwnerIsBuilding = indexed?.type === "building";
      if (!sameBuilding) return false;
      if (shellOwnerIsSelectedFloor) return reviewLodVisible(primitive);
      if (shellOwnerIsBuilding && primitive.semantic_class === "exterior_wall") {
        return reviewLodVisible(primitive);
      }
      return false;
    }
    return primitiveBelongsToSelectedFloor(primitive, indexed) && reviewLodVisible(primitive);
  }
  if (state.mode === "floor_plan") {
    return primitiveBelongsToSelectedFloor(primitive, indexed) && reviewLodVisible(primitive);
  }
  return reviewLodVisible(primitive);
}

function buildingBounds() {
  const result = new Map();
  for (const primitive of state.data.geometry.primitives) {
    if (primitive.semantic_class === "collision_envelope") continue;
    const indexed = state.data.hierarchy.entities.get(primitive.owner_id);
    const layerType = state.data.layerMap.get(primitive.layer_id)?.layer_type;
    if (indexed?.type !== "building" || layerType !== "building_shell") continue;
    if (state.districtId !== "all" && indexed.districtId !== state.districtId) continue;
    if (!result.has(primitive.owner_id)) result.set(primitive.owner_id, new THREE.Box3());
    expandBoxByPrimitive(result.get(primitive.owner_id), primitive);
  }
  return result;
}

function expandBoxByPrimitive(box, primitive) {
  const angle = THREE.MathUtils.degToRad(primitive.rotation_z_deg || 0);
  const halfX = (
    Math.abs(Math.cos(angle)) * primitive.size.x
    + Math.abs(Math.sin(angle)) * primitive.size.y
  ) / 2;
  const halfY = (
    Math.abs(Math.sin(angle)) * primitive.size.x
    + Math.abs(Math.cos(angle)) * primitive.size.y
  ) / 2;
  box.expandByPoint(new THREE.Vector3(
    primitive.center.x - halfX,
    primitive.center.y - halfY,
    primitive.center.z - primitive.size.z / 2
  ));
  box.expandByPoint(new THREE.Vector3(
    primitive.center.x + halfX,
    primitive.center.y + halfY,
    primitive.center.z + primitive.size.z / 2
  ));
}

function hierarchyBounds(predicate) {
  const box = new THREE.Box3();
  for (const primitive of state.data.geometry.primitives) {
    if (primitive.semantic_class === "collision_envelope") continue;
    const indexed = state.data.hierarchy.entities.get(primitive.owner_id);
    if (predicate(indexed, primitive)) expandBoxByPrimitive(box, primitive);
  }
  return box;
}

function roomDisplayFrame(roomId) {
  const indexed = state.data?.hierarchy.entities.get(roomId);
  const room = indexed?.entity;
  const floor = state.data?.hierarchy.entities.get(indexed?.floorId)?.entity;
  if (!room?.bounds || !floor) return null;

  // Interior walls are conformed to the realized building massing, while the
  // canonical room bounds intentionally remain in planning coordinates.  Use
  // the room-owned wall fragments to reconstruct the realized display frame
  // so the room overlay and camera do not drift away from its walls.
  const building = state.data.hierarchy.entities.get(indexed.buildingId)?.entity;
  const rotationDeg = Number(building?.metadata?.orientation_deg || 0);
  const rotation = THREE.MathUtils.degToRad(rotationDeg);
  const frameCos = Math.cos(rotation);
  const frameSin = Math.sin(rotation);
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  let wallCount = 0;
  for (const primitive of state.data.geometry.primitives) {
    if (
      primitive.semantic_class !== "interior_wall"
      || !Array.isArray(primitive.metadata?.room_ids)
      || !primitive.metadata.room_ids.includes(roomId)
    ) continue;
    wallCount += 1;
    const primitiveRotation = THREE.MathUtils.degToRad(Number(primitive.rotation_z_deg || 0));
    const primitiveCos = Math.cos(primitiveRotation);
    const primitiveSin = Math.sin(primitiveRotation);
    for (const sx of [-0.5, 0.5]) {
      for (const sy of [-0.5, 0.5]) {
        const offsetX = primitiveCos * sx * primitive.size.x - primitiveSin * sy * primitive.size.y;
        const offsetY = primitiveSin * sx * primitive.size.x + primitiveCos * sy * primitive.size.y;
        const worldX = primitive.center.x + offsetX;
        const worldY = primitive.center.y + offsetY;
        const localX = worldX * frameCos + worldY * frameSin;
        const localY = -worldX * frameSin + worldY * frameCos;
        minX = Math.min(minX, localX); maxX = Math.max(maxX, localX);
        minY = Math.min(minY, localY); maxY = Math.max(maxY, localY);
      }
    }
  }
  if (wallCount === 0) return null;
  if (maxX - minX > 0.5 && maxY - minY > 0.5) {
    const localCenterX = (minX + maxX) / 2;
    const localCenterY = (minY + maxY) / 2;
    return {
      centerX: localCenterX * frameCos - localCenterY * frameSin,
      centerY: localCenterX * frameSin + localCenterY * frameCos,
      width: maxX - minX,
      depth: maxY - minY,
      rotation,
      elevation: Number(floor.elevation_m || 0),
      height: Math.max(0.06, Number(room.height_m || floor.height_m || 3.0)),
      source: "realized_walls",
    };
  }
  // A room with only a thin clipped fragment is not a realizable enclosed
  // space. Returning null prevents the old canonical rectangle from being
  // drawn as a misleading wall-less room.
  return null;
}

function renderRoomBoundary() {
  if (!state.data || !state.roomId) return;
  const indexed = state.data.hierarchy.entities.get(state.roomId);
  if (!indexed || indexed.type !== "room") return;
  const room = indexed.entity;
  const floorIndexed = state.data.hierarchy.entities.get(indexed.floorId);
  const floor = floorIndexed?.entity;
  if (!room.bounds || !floor) return;
  const frame = roomDisplayFrame(state.roomId);
  if (!frame) return;
  const hasAuthoredFloor = state.data.geometry.primitives.some((p) =>
    p.metadata?.room_floor_finish && p.metadata?.room_ids?.includes(state.roomId));
  // A compiled, textured room surface is authoritative. Keep the old overlay
  // only for legacy scenes and semantic inspection, not on top of PBR floors.
  if (!(hasAuthoredFloor && state.appearanceMode === "presentation")) {
    const floorMaterial = new THREE.MeshStandardMaterial({
      color: state.appearanceMode === "presentation"
        ? ({warm: 0x85603d, minimal: 0xa6a399, industrial: 0x626466}[room.metadata?.room_design?.palette] || 0xb8b3a7)
        : 0x6cc5a4,
      transparent: state.appearanceMode !== "presentation",
      opacity: state.appearanceMode === "presentation" ? 1 : 0.14,
      depthWrite: state.appearanceMode === "presentation",
      side: THREE.DoubleSide,
    });
    const floorMesh = new THREE.Mesh(unitBox, floorMaterial);
    floorMesh.position.set(
      frame.centerX,
      frame.centerY,
      frame.elevation + 0.025,
    );
    floorMesh.rotation.z = frame.rotation;
    floorMesh.scale.set(frame.width, frame.depth, 0.05);
    floorMesh.renderOrder = 8;
    roomBoundaryGroup.add(floorMesh);
  }

  // A room's inspection boundary is an overlay, not architectural geometry.
  // Honour the outline switch in presentation/HQ captures as for buildings.
  if (state.appearanceMode === "presentation" && !state.showOutlines) return;
  const halfWidth = frame.width / 2;
  const halfDepth = frame.depth / 2;
  const localCorners = [
    [-halfWidth, -halfDepth], [halfWidth, -halfDepth],
    [halfWidth, -halfDepth], [halfWidth, halfDepth],
    [halfWidth, halfDepth], [-halfWidth, halfDepth],
    [-halfWidth, halfDepth], [-halfWidth, -halfDepth],
  ];
  const cos = Math.cos(frame.rotation), sin = Math.sin(frame.rotation);
  const z = frame.elevation + Math.min(0.12, frame.height * 0.08);
  const vertices = [];
  for (const [localX, localY] of localCorners) {
    vertices.push(
      frame.centerX + localX * cos - localY * sin,
      frame.centerY + localX * sin + localY * cos,
      z,
    );
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(vertices, 3));
  const outline = new THREE.LineSegments(
    geometry,
    new THREE.LineBasicMaterial({ color: 0x8af2c6, transparent: true, opacity: 0.95, depthTest: false }),
  );
  outline.renderOrder = 18;
  roomBoundaryGroup.add(outline);
}

const floorFunctionColors = {
  corridor: 0x93a7aa,
  lobby: 0x5fb8c8,
  reception: 0x6fc6a0,
  office: 0x7c9be6,
  open_office: 0x86a9ec,
  meeting_room: 0xa98bd6,
  living_room: 0xd99a65,
  bedroom: 0xd4869a,
  kitchen: 0xe0bd63,
  bathroom: 0x6dbbd4,
  shop: 0xe18a61,
  storage: 0x9d9b8d,
  service_room: 0x8d9c86,
};

function floorOverlayMaterial(color, opacity) {
  return new THREE.MeshBasicMaterial({
    color,
    transparent: true,
    opacity,
    depthWrite: false,
    side: THREE.DoubleSide,
  });
}

function renderFloorAnnotations() {
  if (!state.data || !state.floorId || !["floor", "floor_plan"].includes(state.mode)) return;
  const floorIndexed = state.data.hierarchy.entities.get(state.floorId);
  const buildingIndexed = state.data.hierarchy.entities.get(state.buildingId);
  const floor = floorIndexed?.entity;
  const building = buildingIndexed?.entity;
  if (!floor || !building) return;

  // Functional room plates make a floor plan legible even when all materials
  // are switched to presentation/clay mode. They are intentionally subtle so
  // the authored walls and furniture remain the visual authority.
  for (const room of floor.rooms || []) {
    const frame = roomDisplayFrame(room.id);
    if (!frame) continue;
    const color = floorFunctionColors[room.function] || 0x7d9f98;
    const plate = new THREE.Mesh(
      unitBox,
      floorOverlayMaterial(color, state.mode === "floor_plan" ? 0.16 : 0.07),
    );
    plate.position.set(frame.centerX, frame.centerY, frame.elevation + 0.055);
    plate.rotation.z = frame.rotation;
    plate.scale.set(frame.width * 0.96, frame.depth * 0.96, 0.025);
    plate.renderOrder = 7;
    floorAnnotationGroup.add(plate);

    if (state.showLabels) {
      const label = makeLabelSprite(
        room.name || room.id,
        String(room.function || "room").replaceAll("_", " "),
      );
      const labelSize = Math.max(2.8, Math.min(6.5, Math.min(frame.width, frame.depth) * 0.42));
      label.scale.set(labelSize, labelSize * 0.29, 1);
      label.position.set(frame.centerX, frame.centerY, frame.elevation + Math.max(0.18, frame.height * 0.08));
      label.renderOrder = 26;
      floorAnnotationGroup.add(label);
    }
  }

  const selectedLevel = Number(floor.level);
  for (const connector of building.vertical_connectors || []) {
    if (selectedLevel < Number(connector.from_level) || selectedLevel > Number(connector.to_level)) continue;
    const bounds = connector.bounds;
    if (!bounds) continue;
    const connectorWidth = Number(bounds.max_x) - Number(bounds.min_x);
    const connectorDepth = Number(bounds.max_y) - Number(bounds.min_y);
    const isElevator = connector.connector_type === "elevator";
    const color = isElevator ? 0xe9b85b : 0x8f7be1;
    const core = new THREE.Mesh(
      unitBox,
      floorOverlayMaterial(color, state.mode === "floor_plan" ? 0.22 : 0.12),
    );
    core.position.set(bounds.min_x + connectorWidth / 2, bounds.min_y + connectorDepth / 2, floor.elevation_m + 0.11);
    core.scale.set(connectorWidth, connectorDepth, 0.06);
    core.renderOrder = 11;
    floorAnnotationGroup.add(core);
    const outline = new THREE.LineSegments(
      new THREE.EdgesGeometry(unitBox),
      new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.95, depthTest: false }),
    );
    outline.position.copy(core.position);
    outline.scale.set(connectorWidth, connectorDepth, 0.06);
    outline.renderOrder = 24;
    floorAnnotationGroup.add(outline);
    if (state.showLabels) {
      const label = makeLabelSprite(
        isElevator ? "Vertical core" : "Fire stairs",
        isElevator ? "elevator" : "stairs",
      );
      const labelSize = Math.max(3.2, Math.min(6.2, Math.max(connectorWidth, connectorDepth) * 1.5));
      label.scale.set(labelSize, labelSize * 0.29, 1);
      label.position.set(core.position.x, core.position.y, floor.elevation_m + Math.max(0.3, floor.height_m * 0.15));
      label.renderOrder = 27;
      floorAnnotationGroup.add(label);
    }
  }
}

function renderRoadMarkings() {
  if (!state.enabledSemantics.has("road_surface")) return;
  const positions = [];
  for (const primitive of state.data.geometry.primitives) {
    if (primitive.semantic_class !== "road_surface") continue;
    const angle = THREE.MathUtils.degToRad(primitive.rotation_z_deg || 0);
    const half = primitive.size.x * 0.47;
    const dx = Math.cos(angle) * half, dy = Math.sin(angle) * half;
    const z = primitive.center.z + primitive.size.z / 2 + 0.07;
    positions.push(
      primitive.center.x - dx, primitive.center.y - dy, z,
      primitive.center.x + dx, primitive.center.y + dy, z
    );
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  const lines = new THREE.LineSegments(
    geometry,
    new THREE.LineDashedMaterial({
      color: state.daylight ? 0xfff3b0 : 0xffe58a,
      dashSize: 4.5,
      gapSize: 3.0,
      transparent: true,
      opacity: state.daylight ? 0.9 : 0.72,
      depthTest: false,
    })
  );
  lines.computeLineDistances();
  lines.renderOrder = 12;
  streetOverlayGroup.add(lines);
}

function renderBuildingOutlines() {
  for (const [buildingId, bounds] of buildingBounds()) {
    if (bounds.isEmpty()) continue;
    const selected = buildingId === state.buildingId
      && ["building", "floor"].includes(state.mode);
    const helper = new THREE.Box3Helper(
      bounds,
      selected
        ? 0xffd86b
        : state.daylight
          ? 0x315f5a
          : 0x83d6b1
    );
    helper.material.transparent = true;
    helper.material.opacity = selected ? 0.95 : 0.56;
    helper.material.depthTest = false;
    helper.renderOrder = 14;
    buildingOutlineGroup.add(helper);
  }
}

function renderBuildingLabels() {
  for (const [buildingId, bounds] of buildingBounds()) {
    if (
      ["building", "floor"].includes(state.mode)
      && buildingId !== state.buildingId
    ) continue;
    const indexed = state.data.hierarchy.entities.get(buildingId);
    if (!indexed || bounds.isEmpty()) continue;
    const sprite = makeLabelSprite(
      indexed.entity.name || buildingId,
      `${indexed.entity.function || "building"} · ${(indexed.entity.floors || []).length}F`
    );
    const center = bounds.getCenter(new THREE.Vector3());
    const size = bounds.getSize(new THREE.Vector3());
    const width = Math.max(15, Math.min(28, Math.max(size.x, size.y) * 0.72));
    sprite.scale.set(width, width * 0.29, 1);
    sprite.position.set(center.x, center.y, bounds.max.z + Math.max(3.5, size.z * 0.12));
    sprite.renderOrder = 30;
    labelGroup.add(sprite);
  }
}

function makeLabelSprite(title, subtitle) {
  const canvas = document.createElement("canvas");
  canvas.width = 512; canvas.height = 144;
  const context = canvas.getContext("2d");
  context.fillStyle = state.daylight ? "rgba(9, 30, 28, 0.86)" : "rgba(4, 15, 14, 0.9)";
  context.fillRect(6, 6, 500, 132);
  context.fillStyle = "#72e3b2";
  context.fillRect(6, 6, 10, 132);
  context.fillStyle = "#f2faf7";
  context.font = "600 42px system-ui, sans-serif";
  context.textBaseline = "middle";
  context.fillText(String(title).slice(0, 23), 36, 59);
  context.fillStyle = "#a7c0b9";
  context.font = "600 24px system-ui, sans-serif";
  context.fillText(String(subtitle).replaceAll("_", " ").toUpperCase().slice(0, 32), 36, 105);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.minFilter = THREE.LinearFilter;
  const material = new THREE.SpriteMaterial({
    map: texture,
    transparent: true,
    depthTest: false,
    depthWrite: false,
  });
  return new THREE.Sprite(material);
}

function primitiveHasError(primitive) {
  if (state.data.errorIds.has(primitive.owner_id)) return true;
  return state.data.hierarchy.lineage(primitive.owner_id).some((id) => state.data.errorIds.has(id));
}

function primitiveMatrix(primitive) {
  let angle = THREE.MathUtils.degToRad(primitive.rotation_z_deg || 0);
  let x = primitive.center.x, y = primitive.center.y, z = primitive.center.z;
  const machineId = primitive.metadata?.state_machine_id;
  const machine = state.data?.interactions?.state_machines?.find((item) => item.id === machineId);
  const currentState = machineId ? state.doorStates.get(machineId) : null;
  if (machine?.state_type === "elevator_controller") {
    const cabinZ = machine.states?.[currentState]?.cabin_z_m;
    if (cabinZ !== undefined) {
      z = primitive.metadata?.transport_elevator_version === 1
        ? z + cabinZ - primitive.metadata.cabin_initial_floor_z_m : cabinZ;
    }
  } else if (machineId && currentState === "open") {
    ({x, y, z, angle} = doorPose(primitive, primitive.metadata.upper_limit_deg ?? 90));
  }
  const matrix = new THREE.Matrix4();
  matrix.compose(
    new THREE.Vector3(x, y, z),
    new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 0, 1), angle),
    new THREE.Vector3(primitive.size.x, primitive.size.y, primitive.size.z)
  );
  return matrix;
}

function clearGroup(group) {
  for (const child of [...group.children]) {
    disposeInstances(child);
    for (const material of [child.material].flat().filter(Boolean)) {
      material.userData.citygDisposed = true;
      disposeOwnedMap(material, sharedMaterialTextures);
      material.dispose();
    }
    if (child.geometry && !child.geometry.userData.citygSharedGeometry
      && ![unitBox, unitCylinder, unitSphere].includes(child.geometry) && child !== highlight) child.geometry.dispose();
    group.remove(child);
  }
}

function clearAssetGroup() {
  state.assetRenderGeneration += 1;
  state.assetLoadState = {
    generation: state.assetRenderGeneration,
    expected: 0,
    pending: 0,
    loaded: 0,
    fallback: 0,
    cached: 0,
    failed: 0,
    ready: true,
  };
  state.assetReadyPromise = Promise.resolve({ ...state.assetLoadState });
  for (const child of [...assetGroup.children]) {
    disposeInstances(child);
    child.traverse(node => {
      for (const material of node.userData.citygOwnedMaterials || []) material.dispose();
      delete node.userData.citygOwnedMaterials;
    });
    assetGroup.remove(child);
  }
  // Clones are cheap to rebuild; retaining them pins invisible templates and
  // textures indefinitely, defeating the template pool's memory budget.
  state.assetObjectCache.clear();
}

function releaseStandardGeometry() {
  clearAssetGroup();
  for (const group of [geometryGroup, navigationGroup, pathGroup, streetOverlayGroup,
    buildingOutlineGroup, labelGroup, roomBoundaryGroup, floorAnnotationGroup, presentationFocusGroup]) clearGroup(group);
  state.standardGeometryContentSignature = '';
  state.standardVisiblePrimitives = [];
  if (state.data) {
    // Equality sentinels must not pin an evicted, hundreds-of-MB detail array.
    state.data.groundEdgePrimitives = null;
    state.data.depthPrimitives = null;
  }
  assetTemplates.retain([]);
  renderer.renderLists.dispose();
}

function disposeAssetObjectCache() {
  for (const object of state.assetObjectCache.values()) {
    object.traverse((node) => {
      for (const material of node.userData.citygOwnedMaterials || []) material.dispose();
      delete node.userData.citygOwnedMaterials;
    });
    object.parent?.remove(object);
  }
  state.assetObjectCache.clear();
}

function renderNavigation() {
  const graph = state.data.navigation;
  const nodes = new Map(graph.nodes.map((node) => [node.id, node]));
  const edgePositions = [];
  for (const edge of graph.edges) {
    const a = nodes.get(edge.start_node_id), b = nodes.get(edge.end_node_id);
    if (!a || !b) continue;
    edgePositions.push(a.position.x, a.position.y, a.position.z + 0.18, b.position.x, b.position.y, b.position.z + 0.18);
  }
  const edgeGeometry = new THREE.BufferGeometry();
  edgeGeometry.setAttribute("position", new THREE.Float32BufferAttribute(edgePositions, 3));
  navigationGroup.add(new THREE.LineSegments(edgeGeometry, new THREE.LineBasicMaterial({ color: 0x46cda1, transparent: true, opacity: 0.5, depthTest: false })));
  const nodePositions = graph.nodes.flatMap((node) => [node.position.x, node.position.y, node.position.z + 0.22]);
  const nodeGeometry = new THREE.BufferGeometry();
  nodeGeometry.setAttribute("position", new THREE.Float32BufferAttribute(nodePositions, 3));
  navigationGroup.add(new THREE.Points(nodeGeometry, new THREE.PointsMaterial({ color: 0xc1ffe9, size: 2.2, sizeAttenuation: true, depthTest: false })));
}

function routeToSelection() {
  if (!state.selectedPrimitive) return;
  const graph = state.data.navigation;
  const nodes = new Map(graph.nodes.map((node) => [node.id, node]));
  const sources = graph.nodes.filter((node) => node.node_type === "outdoor_junction");
  const lineageTarget = new Set(state.data.hierarchy.lineage(state.selectedPrimitive.owner_id));
  const target = graph.nodes.find((node) => node.owner_id === state.selectedPrimitive.owner_id)
    || graph.nodes.find((node) => lineageTarget.has(node.owner_id))
    || graph.nodes.find((node) => state.data.hierarchy.lineage(node.owner_id).includes(state.selectedPrimitive.owner_id));
  if (!sources.length || !target) return showToast("No navigation node belongs to this selection");
  const adjacency = new Map();
  for (const edge of graph.edges) {
    if (!adjacency.has(edge.start_node_id)) adjacency.set(edge.start_node_id, []);
    if (!adjacency.has(edge.end_node_id)) adjacency.set(edge.end_node_id, []);
    adjacency.get(edge.start_node_id).push({ id: edge.end_node_id, edge });
    adjacency.get(edge.end_node_id).push({ id: edge.start_node_id, edge });
  }
  const source = sources[0].id;
  const queue = [source], parent = new Map([[source, null]]);
  while (queue.length && !parent.has(target.id)) {
    const current = queue.shift();
    for (const next of adjacency.get(current) || []) {
      if (!parent.has(next.id)) { parent.set(next.id, { node: current, edge: next.edge }); queue.push(next.id); }
    }
  }
  if (!parent.has(target.id)) return showToast("No route found");
  const path = [];
  let current = target.id;
  while (current) { path.push(current); current = parent.get(current)?.node || null; }
  path.reverse();
  const positions = [];
  for (let index = 0; index < path.length - 1; index++) {
    const a = nodes.get(path[index]).position, b = nodes.get(path[index + 1]).position;
    positions.push(a.x, a.y, a.z + 0.5, b.x, b.y, b.z + 0.5);
  }
  clearGroup(pathGroup);
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  pathGroup.add(new THREE.LineSegments(geometry, new THREE.LineBasicMaterial({ color: 0xffe66d, linewidth: 3, depthTest: false })));
  showToast(`Route: ${path.length} nodes · interactive doors allowed`);
}

function restoreHighlight() {
  if (!state.selectedPrimitive || !state.visiblePrimitives.some((item) => item.id === state.selectedPrimitive.id)) {
    highlight.visible = false;
    return;
  }
  const primitive = state.selectedPrimitive;
  const matrix = primitiveMatrix(primitive);
  matrix.decompose(highlight.position, highlight.quaternion, highlight.scale);
  highlight.scale.multiplyScalar(1.035);
  highlight.visible = true;
}

function selectPrimitive(primitive, focus = false) {
  state.cameraDirty = true;
  state.selectedPrimitive = primitive;
  updateInspector();
  restoreHighlight();
  if (focus) focusPrimitive(primitive);
}

function updateInspector() {
  const primitive = state.selectedPrimitive;
  elements["empty-inspector"].hidden = Boolean(primitive);
  elements.inspector.hidden = !primitive;
  if (!primitive) return;
  const indexed = state.data.hierarchy.entities.get(primitive.owner_id);
  elements["entity-type"].textContent = indexed?.type || primitive.semantic_class;
  elements["entity-id"].textContent = primitive.owner_id;
  const values = {
    primitive: primitive.id,
    semantic: primitive.semantic_class,
    layer: primitive.layer_id,
    material: primitive.material_id,
    body: primitive.body_type,
    size: `${format(primitive.size.x)} × ${format(primitive.size.y)} × ${format(primitive.size.z)} m`,
    position: `${format(primitive.center.x)}, ${format(primitive.center.y)}, ${format(primitive.center.z)}`,
    district: indexed?.districtId,
    building: indexed?.buildingId,
    floor: indexed?.floorId,
    function: indexed?.entity?.function,
  };
  elements["entity-properties"].replaceChildren(...Object.entries(values).filter(([, value]) => value !== undefined).map(([key, value]) => {
    const row = document.createElement("div");
    const dt = document.createElement("dt"); dt.textContent = key;
    const dd = document.createElement("dd"); dd.textContent = value;
    row.append(dt, dd); return row;
  }));
  const machineId = primitive.metadata?.state_machine_id;
  elements["door-button"].hidden = !machineId;
  if (machineId) {
    const machine = state.data.interactions.state_machines.find((item) => item.id === machineId);
    elements["door-button"].textContent = machine?.state_type === "elevator_controller"
      ? `Move elevator · ${state.doorStates.get(machineId)?.replace("level_", "L")}`
      : (state.doorStates.get(machineId) === "open" ? "Close door" : "Open door");
  }
  elements["route-button"].hidden = !hasNavigationTarget(primitive.owner_id);
}

function hasNavigationTarget(ownerId) {
  if (!state.data.navigation.nodes.length) return false;
  return state.data.navigation.nodes.some((node) => node.owner_id === ownerId || state.data.hierarchy.lineage(node.owner_id).includes(ownerId));
}

function renderValidation() {
  const issues = state.data.issues;
  const errors = issues.filter((issue) => issue.severity === "error");
  elements["validation-summary"].className = `validation-summary ${errors.length ? "fail" : "ok"}`;
  elements["validation-summary"].textContent = errors.length ? `${errors.length} errors · ${issues.length - errors.length} warnings` : `All ${issues.length ? "loaded reports" : "checks"} passed`;
  elements["validation-list"].replaceChildren(...issues.slice(0, 40).map((issue) => {
    const card = document.createElement("div"); card.className = `issue ${issue.severity}`;
    const title = document.createElement("strong"); title.textContent = issue.code;
    const message = document.createElement("span"); message.textContent = issue.message;
    card.append(title, message);
    card.addEventListener("click", () => focusEntity(issue.entity_id));
    return card;
  }));
}

function focusEntity(entityId) {
  const primitive = state.data.geometry.primitives.find((item) => item.owner_id === entityId)
    || state.data.geometry.primitives.find((item) => state.data.hierarchy.lineage(item.owner_id).includes(entityId));
  if (!primitive) return showToast(`No geometry found for ${entityId}`);
  selectPrimitive(primitive, true);
}

function focusPrimitive(primitive) {
  const distance = Math.max(primitive.size.x, primitive.size.y, primitive.size.z) * 4 + 10;
  const target = new THREE.Vector3(primitive.center.x, primitive.center.y, primitive.center.z);
  controls.target.copy(target);
  camera.up.set(0, 0, 1);
  camera.position.copy(target).add(new THREE.Vector3(distance, -distance, distance * 0.8));
  controls.update();
}

function focusBounds(bounds) {
  if (!bounds || bounds.isEmpty()) return false;
  const target = bounds.getCenter(new THREE.Vector3());
  const size = bounds.getSize(new THREE.Vector3());
  const distance = Math.max(size.x, size.y, size.z * 2.2) * 1.35 + 8;
  controls.target.copy(target);
  camera.up.set(0, 0, 1);
  camera.position.copy(target).add(
    new THREE.Vector3(distance * 0.72, -distance * 0.8, distance * 0.62)
  );
  camera.near = Math.max(0.05, distance / 1000);
  camera.far = Math.max(1000, distance * 20);
  camera.updateProjectionMatrix();
  controls.update();
  return true;
}

function fitCity(view = "iso") {
  if (!state.data) return;
  const primitives = state.data.geometry.primitives;
  const min = new THREE.Vector3(Infinity, Infinity, Infinity), max = new THREE.Vector3(-Infinity, -Infinity, -Infinity);
  for (const primitive of primitives) {
    min.x = Math.min(min.x, primitive.center.x - primitive.size.x / 2);
    min.y = Math.min(min.y, primitive.center.y - primitive.size.y / 2);
    min.z = Math.min(min.z, primitive.center.z - primitive.size.z / 2);
    max.x = Math.max(max.x, primitive.center.x + primitive.size.x / 2);
    max.y = Math.max(max.y, primitive.center.y + primitive.size.y / 2);
    max.z = Math.max(max.z, primitive.center.z + primitive.size.z / 2);
  }
  const target = min.clone().add(max).multiplyScalar(0.5);
  const extent = max.clone().sub(min);
  const distance = Math.max(extent.x, extent.y, extent.z * 4) * 1.15;
  const previousDirection = camera.position.clone().sub(controls.target);
  controls.target.copy(target);
  // A Z-up camera cannot use Z as its screen-up vector while looking straight
  // down the Z axis. Switch to Y-up only for the orthographic-like top view.
  if (view === "top") {
    camera.up.set(0, 1, 0);
    camera.position.copy(target).add(new THREE.Vector3(0, 0, distance * 1.35));
  } else if (view === "fit") {
    // FIT preserves the user's current heading/elevation and only changes
    // the target and distance.  This makes it useful after street-level or
    // free-navigation inspection, unlike ISO's fixed presentation angle.
    const direction = previousDirection;
    if (direction.lengthSq() < 1e-6) direction.set(distance * 0.75, -distance * 0.8, distance * 0.68);
    direction.normalize().multiplyScalar(distance);
    camera.position.copy(target).add(direction);
  } else {
    camera.up.set(0, 0, 1);
    camera.position.copy(target).add(new THREE.Vector3(distance * 0.75, -distance * 0.8, distance * 0.68));
  }
  camera.near = Math.max(0.1, distance / 1000); camera.far = distance * 10;
  camera.updateProjectionMatrix(); controls.update();
}

function fitFloorPlan() {
  if (!state.data || !state.floorId) return;
  const bounds = hierarchyBounds((indexed, primitive) => primitiveBelongsToSelectedFloor(primitive, indexed));
  if (bounds.isEmpty()) {
    showToast("Selected floor has no visible geometry");
    return;
  }
  const target = bounds.getCenter(new THREE.Vector3());
  const size = bounds.getSize(new THREE.Vector3());
  const horizontalExtent = Math.max(size.x / Math.max(camera.aspect, 0.1), size.y);
  const halfFov = THREE.MathUtils.degToRad(camera.fov * 0.5);
  const distance = Math.max(8, horizontalExtent / (2 * Math.tan(halfFov)) * 1.22);
  controls.target.copy(target);
  // Z-up world, Y-up screen: this keeps north/south readable in a true plan.
  camera.up.set(0, 1, 0);
  camera.position.set(target.x, target.y, target.z + distance);
  camera.near = Math.max(0.05, distance / 1000);
  camera.far = Math.max(1000, distance * 20);
  camera.updateProjectionMatrix();
  controls.update();
}

function fitFloorPerspective() {
  if (!state.data || !state.floorId) return false;
  const bounds = hierarchyBounds((indexed, primitive) => primitiveBelongsToSelectedFloor(primitive, indexed));
  if (bounds.isEmpty()) return false;
  const target = bounds.getCenter(new THREE.Vector3());
  const size = bounds.getSize(new THREE.Vector3());
  const distance = Math.max(size.x, size.y, size.z * 2.2) * 1.18 + 5;
  controls.target.copy(target);
  camera.up.set(0, 0, 1);
  camera.position.copy(target).add(
    new THREE.Vector3(distance * 0.78, -distance * 0.86, Math.max(5.0, distance * 0.92))
  );
  camera.near = Math.max(0.05, distance / 1000);
  camera.far = Math.max(1000, distance * 20);
  camera.fov = 52;
  camera.updateProjectionMatrix();
  controls.update();
  return true;
}

function fitFloorCorridor() {
  if (!state.data || !state.floorId) return false;
  const floor = state.data.hierarchy.entities.get(state.floorId)?.entity;
  if (!floor) return false;
  const corridors = (floor.rooms || [])
    .filter((room) => room.function === "corridor")
    .map((room) => ({ room, frame: roomDisplayFrame(room.id) }))
    .filter((item) => item.frame)
    .sort((a, b) => {
      const areaA = a.frame.width * a.frame.depth;
      const areaB = b.frame.width * b.frame.depth;
      return areaB - areaA;
    });
  const selected = corridors[0];
  if (!selected) return fitFloorPerspective();
  const frame = selected.frame;
  const majorIsX = frame.width >= frame.depth;
  const axis = majorIsX
    ? new THREE.Vector3(Math.cos(frame.rotation), Math.sin(frame.rotation), 0)
    : new THREE.Vector3(-Math.sin(frame.rotation), Math.cos(frame.rotation), 0);
  const distance = Math.max(2.4, Math.min(7.0, Math.max(frame.width, frame.depth) * 0.28));
  const target = new THREE.Vector3(frame.centerX, frame.centerY, frame.elevation + Math.min(1.65, frame.height * 0.58));
  controls.target.copy(target).add(axis.clone().multiplyScalar(Math.min(7, Math.max(2, distance * 1.8))));
  camera.up.set(0, 0, 1);
  camera.position.copy(target).add(axis.clone().multiplyScalar(-distance));
  camera.position.z = target.z;
  camera.fov = 68;
  camera.near = 0.03;
  camera.far = Math.max(250, Math.max(frame.width, frame.depth) * 30);
  camera.updateProjectionMatrix();
  controls.update();
  return true;
}

function fitFloorCore() {
  if (!state.data || !state.floorId || !state.buildingId) return false;
  const floor = state.data.hierarchy.entities.get(state.floorId)?.entity;
  const building = state.data.hierarchy.entities.get(state.buildingId)?.entity;
  if (!floor || !building) return false;
  const level = Number(floor.level);
  const connectors = (building.vertical_connectors || [])
    .filter((connector) => level >= Number(connector.from_level) && level <= Number(connector.to_level))
    .sort((a, b) => Number(b.connector_type === "elevator") - Number(a.connector_type === "elevator"));
  const connector = connectors[0];
  if (!connector?.bounds) return fitFloorPerspective();
  const width = Number(connector.bounds.max_x) - Number(connector.bounds.min_x);
  const depth = Number(connector.bounds.max_y) - Number(connector.bounds.min_y);
  const center = new THREE.Vector3(
    Number(connector.bounds.min_x) + width / 2,
    Number(connector.bounds.min_y) + depth / 2,
    Number(floor.elevation_m || 0) + Math.max(0.8, Number(floor.height_m || 3) * 0.42),
  );
  const distance = Math.max(4.0, Math.max(width, depth) * 4.2);
  controls.target.copy(center);
  camera.up.set(0, 0, 1);
  camera.position.copy(center).add(new THREE.Vector3(distance * 0.82, -distance * 0.92, Math.max(3.2, distance * 0.74)));
  camera.fov = 52;
  camera.near = 0.03;
  camera.far = Math.max(250, distance * 18);
  camera.updateProjectionMatrix();
  controls.update();
  return true;
}

function fitFloorCameraPreset(preset = state.floorCameraPreset) {
  if (preset === "top") return fitFloorPlan();
  if (preset === "corridor") return fitFloorCorridor();
  if (preset === "core") return fitFloorCore();
  return fitFloorPerspective();
}

function setFloorCameraPreset(preset, { render = true } = {}) {
  state.hierarchyDisplay = null;
  state.presentationFocusId = null;
  if (!state.buildingId || !state.floorId) {
    showToast("Select a building and floor first");
    return false;
  }
  if (!Object.prototype.hasOwnProperty.call(floorCameraLabels, preset)) return false;
  state.floorCameraPreset = preset;
  const targetMode = preset === "top" ? "floor_plan" : "floor";
  const modeChanged = state.mode !== targetMode;
  state.mode = targetMode;
  if (elements["mode-buttons"]) {
    elements["mode-buttons"].querySelectorAll("button").forEach((item) => {
      item.classList.toggle("active", item.dataset.mode === state.mode);
    });
  }
  updateModeHint();
  clearSelection();
  if (render && modeChanged) renderGeometry();
  return Boolean(fitFloorCameraPreset(preset));
}

function fitStreet() {
  if (!state.data) return;
  const roads = state.data.city.road_network?.segments || [];
  if (!roads.length) return;
  const ranked = [...roads].sort((a, b) => {
    const priority = (road) => road.road_class === "collector" ? 2 : road.road_class === "local" ? 1 : 0;
    const length = (road) => road.centerline.slice(1).reduce((sum, p, i) =>
      sum + Math.hypot(p.x - road.centerline[i].x, p.y - road.centerline[i].y), 0);
    return priority(b) - priority(a) || length(b) - length(a) || a.id.localeCompare(b.id);
  });
  const road = ranked[0];
  const lengths = road.centerline.slice(1).map((p, i) =>
    Math.hypot(p.x - road.centerline[i].x, p.y - road.centerline[i].y));
  const length = lengths.reduce((sum, value) => sum + value, 0);
  const pointAt = (distance, offset) => {
    let remaining = Math.max(0, Math.min(length, distance));
    for (let i = 0; i < lengths.length; i++) {
      if (remaining > lengths[i] && i < lengths.length - 1) {
        remaining -= lengths[i]; continue;
      }
      const a = road.centerline[i], b = road.centerline[i + 1];
      const ux = (b.x - a.x) / Math.max(1e-8, lengths[i]);
      const uy = (b.y - a.y) / Math.max(1e-8, lengths[i]);
      return {x: a.x + ux * remaining - uy * offset, y: a.y + uy * remaining + ux * offset};
    }
    return road.centerline[0];
  };
  const along = Math.min(Math.max(8, length * 0.18), length - 4);
  const laneOffset = Number(road.width_m || 10) * 0.22;
  const position = pointAt(along, laneOffset);
  const target = pointAt(along + Math.min(28, length * 0.35), laneOffset);
  camera.position.set(position.x, position.y, 1.70);
  controls.target.set(target.x, target.y, 1.58);
  camera.up.set(0, 0, 1);
  camera.fov = 62;
  camera.near = 0.05;
  camera.far = Math.max(1000, length * 20);
  state.mode = "overview";
  state.showOutlines = false;
  state.showLabels = false;
  elements["outline-toggle"].checked = false;
  elements["labels-toggle"].checked = false;
  camera.updateProjectionMatrix();
  controls.update();
  renderGeometry();
}

function focusRoom() {
  if (!state.data || !state.roomId) return false;
  const indexed = state.data.hierarchy.entities.get(state.roomId);
  if (!indexed || indexed.type !== "room") return false;
  const frame = roomDisplayFrame(state.roomId);
  if (!frame) return false;
  if (state.roomCameraPreset !== "eye") {
    const span = Math.max(frame.width, frame.depth, 3);
    controls.target.set(frame.centerX, frame.centerY, frame.elevation+.1);
    camera.up.set(0, 0, 1);
    if (state.roomCameraPreset === "top") {
      const height = frame.height + Math.max(frame.width/Math.max(.1,camera.aspect),frame.depth)
        /(2*Math.tan(THREE.MathUtils.degToRad(24)))*1.12;
      camera.position.set(frame.centerX, frame.centerY-.001, frame.elevation+height);
      camera.up.set(-Math.sin(frame.rotation), Math.cos(frame.rotation), 0);
    } else {
      controls.target.z = frame.elevation+frame.height/2;
      const direction = new THREE.Vector3(1,-1,1.16).normalize()
        .applyAxisAngle(new THREE.Vector3(0,0,1),frame.rotation);
      const right = new THREE.Vector3().crossVectors(new THREE.Vector3(0,0,1),direction).normalize();
      const up = new THREE.Vector3().crossVectors(direction,right).normalize();
      const tan = Math.tan(THREE.MathUtils.degToRad(24));
      let distance = 2;
      for (const x of [-frame.width/2,frame.width/2]) {
        for (const y of [-frame.depth/2,frame.depth/2]) {
          for (const z of [-frame.height/2,frame.height/2]) {
            const corner = new THREE.Vector3(x,y,z).applyAxisAngle(new THREE.Vector3(0,0,1),frame.rotation);
            distance = Math.max(distance,corner.dot(direction)+Math.max(
              Math.abs(corner.dot(right))/(tan*Math.max(.1,camera.aspect)),
              Math.abs(corner.dot(up))/tan));
          }
        }
      }
      camera.position.copy(controls.target).addScaledVector(direction,distance*1.12);
    }
    camera.fov=48; camera.near=.03; camera.far=Math.max(200,span*20);
    camera.updateProjectionMatrix(); controls.update();
    return true;
  }
  const furniture = state.data.geometry.primitives.filter((primitive) => (
    primitive.semantic_class.startsWith("furniture_")
    && state.data.hierarchy.lineage(primitive.owner_id).includes(state.roomId)
  ));
  const target = new THREE.Vector3(
    furniture.length
      ? furniture.reduce((sum, item) => sum + item.center.x, 0) / furniture.length
      : frame.centerX,
    furniture.length
      ? furniture.reduce((sum, item) => sum + item.center.y, 0) / furniture.length
      : frame.centerY,
    frame.elevation + Math.min(1.15, frame.height * 0.38),
  );
  const inset = Math.max(0.55, Math.min(1.35, Math.min(frame.width, frame.depth) * 0.14));
  const localCorners = [
    [-frame.width / 2 + inset, -frame.depth / 2 + inset],
    [frame.width / 2 - inset, -frame.depth / 2 + inset],
    [frame.width / 2 - inset, frame.depth / 2 - inset],
    [-frame.width / 2 + inset, frame.depth / 2 - inset],
  ];
  const cos = Math.cos(frame.rotation), sin = Math.sin(frame.rotation);
  const corners = localCorners.map(([x, y]) => new THREE.Vector3(
    frame.centerX + x * cos - y * sin,
    frame.centerY + x * sin + y * cos,
    frame.elevation + Math.max(1.65, frame.height * 0.76),
  ));
  const clearance = (corner) => furniture.length
    ? Math.min(...furniture.map((item) => Math.hypot(
      corner.x - item.center.x, corner.y - item.center.y,
    )))
    : corner.distanceToSquared(target);
  const cameraCorner = corners.reduce((best, item) => (
    clearance(item) > clearance(best) ? item : best
  ), corners[0]);
  controls.target.copy(target);
  camera.up.set(0, 0, 1);
  camera.position.copy(cameraCorner);
  camera.fov = 64;
  camera.near = 0.03;
  camera.far = Math.max(200, Math.max(frame.width, frame.depth) * 20);
  camera.updateProjectionMatrix();
  controls.update();
  return true;
}

// Headless observation plans use this small renderer-facing API instead of
// injecting arbitrary JavaScript into the Viewer. Camera coordinates still
// come from the deterministic AdaptiveObservationPlanner.
async function installPaperViews(config) {
  const select = elements['paper-view-select'];
  select.hidden = true;
  select.onchange = null;
  if (!config?.paper_views) return;
  try {
    const response = await fetch(config.paper_views);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const plan = await response.json();
    setOptions(select, [{value: '', label: 'Saved hierarchy views…'},
      ...plan.selected_views.map((view) => ({value: view.view_id, label: view.view_id}))], '');
    select.hidden = false;
    select.onchange = async () => {
      const spec = plan.selected_views.find((view) => view.view_id === select.value);
      if (!spec) return;
      // Interactive replay preserves fixed cameras but never disables orbit controls.
      await setObservationView({...spec, render_profile: 'interactive'});
      await waitForObservationAssets({timeout_ms: 120000});
    };
  } catch (error) { showToast(`Saved views unavailable: ${error.message}`); }
}

function applyObservationState(spec = {}) {
  if (spec.reset_visibility === true) {
    state.districtId = 'all';
    state.enabledSemantics = new Set(state.data.geometry.streaming?.semantics
      || state.data.geometry.primitives.map((p) => p.semantic_class));
    clearSelection();
    setHighFidelityOverview(false, {focus: false, render: false});
  }
  // View-local state must not leak from the city cutaway into floor/room views.
  state.hierarchyDisplay = validateHierarchyDisplay(spec.hierarchy_display, state.data.hierarchy.entities);
  state.presentationFocusId = spec.highlight_entity_id || null;
  if (state.presentationFocusId && !state.data.hierarchy.entities.has(state.presentationFocusId)) {
    throw new Error('Unknown presentation highlight entity');
  }
  renderer.localClippingEnabled = Boolean(state.hierarchyDisplay);
  state.xray = false;
  state.captureExposure = Number.isFinite(spec.exposure) && spec.exposure > 0 ? spec.exposure : null;
  if (typeof spec.daylight === 'boolean') state.daylight = spec.daylight;
  if (['none','clear','cloudy','sunset'].includes(spec.sky_preset)) state.skyPreset=spec.sky_preset;
  if (Number.isFinite(spec.sky_rotation_deg)) state.skyRotation=Math.max(-180,Math.min(180,spec.sky_rotation_deg));
  if (typeof spec.show_grid === 'boolean') elements['grid-toggle'].checked = spec.show_grid;
  if (typeof spec.show_validation === 'boolean') state.showValidation = spec.show_validation;
  if (typeof spec.show_navigation === 'boolean') state.showNavigation = spec.show_navigation;
  const targetIds = new Set(spec.target_entity_ids || []);
  state.observationTargetIds = targetIds;
  state.observationKind = String(spec.kind || "");
  const floorTarget = [...targetIds].find((id) => state.data.hierarchy.entities.get(id)?.type === "floor");
  const buildingTarget = [...targetIds].find((id) => state.data.hierarchy.entities.get(id)?.type === "building");
  if (floorTarget) state.floorId = floorTarget;
  if (buildingTarget) state.buildingId = buildingTarget;
  const roomTarget = [...targetIds].find((id) => state.data.hierarchy.entities.get(id)?.type === "room");
  if (roomTarget) {
    // Explicit inspection targets must not be silently replaced by the UI's
    // hero-only dropdown filter during syncObservationControls().
    if (!roomHasRealizedWalls(roomTarget)) {
      throw new Error(`Observation target has no realizable room boundaries: ${roomTarget}`);
    }
    if (!state.heroRoomIds.has(roomTarget)) state.heroRoomOnly = false;
    const indexedRoom = state.data.hierarchy.entities.get(roomTarget);
    state.roomId = roomTarget;
    state.floorId = indexedRoom.floorId;
    state.buildingId = indexedRoom.buildingId;
  }
  if (state.hierarchyDisplay) {
    state.buildingId = state.hierarchyDisplay.building_id;
    state.floorId = state.hierarchyDisplay.floor_id;
  }
  if (["overview", "building", "floor", "floor_plan", "room", "full"].includes(spec.mode)) state.mode = spec.mode;
  if (state.highFidelityOverview) state.mode = "overview";
  if (Object.prototype.hasOwnProperty.call(floorCameraLabels, spec.floor_camera_preset)) {
    state.floorCameraPreset = spec.floor_camera_preset;
  }
  if (typeof spec.auto_cutaway === "boolean") state.autoCutaway = spec.auto_cutaway;
  // An explicit camera must not inherit hidden walls from a previous UI cutaway.
  state.roomCameraPreset = ["top", "cutaway", "eye"].includes(spec.room_camera_preset)
    ? spec.room_camera_preset : "eye";
  if (["soft", "daylight"].includes(spec.room_lighting)) state.roomLighting = spec.room_lighting;
  if (typeof spec.show_outlines === "boolean") state.showOutlines = spec.show_outlines;
  if (typeof spec.show_labels === "boolean") state.showLabels = spec.show_labels;
  if (typeof spec.show_road_markings === "boolean") state.showRoadMarkings = spec.show_road_markings;
  if (typeof spec.high_fidelity_overview === "boolean") {
    // Observation plans may request the same presentation mode as the UI,
    // without relying on DOM events.
    setHighFidelityOverview(spec.high_fidelity_overview, { focus: false, render: false });
  }
  if (spec.appearance && ["presentation", "semantic", "clay"].includes(spec.appearance)) {
    state.appearanceMode = spec.appearance;
  }
  if (spec.render_profile && RENDER_PROFILES[spec.render_profile]) {
    applyRenderProfile(spec.render_profile);
  }
  if (Array.isArray(spec.camera_position)) camera.position.fromArray(spec.camera_position);
  if (Array.isArray(spec.look_at)) controls.target.fromArray(spec.look_at);
  if (Array.isArray(spec.up)) camera.up.fromArray(spec.up);
  if (Number.isFinite(spec.fov_deg)) camera.fov = spec.fov_deg;
  if (Array.isArray(spec.camera_position)) {
    const distance = camera.position.distanceTo(controls.target);
    // Observation cameras bypass the interactive fit helpers. Keeping a room's
    // 3 cm near plane in a city-wide aerial view loses centimetre-scale depth
    // precision, producing apparent overlaps in road and parcel paving.
    camera.near = ["overview", "full"].includes(state.mode)
      ? Math.max(0.03, Math.min(distance / 100, Math.max(0.3, camera.position.z) / 10))
      : 0.03;
    camera.far = Math.max(1000, distance * 20);
    if (state.renderProfile === "prototype_capture" && Number.isFinite(spec.near_clip_m)
        && spec.near_clip_m > 0 && spec.near_clip_m < distance * .25) {
      camera.near = spec.near_clip_m;
    }
  }
  camera.updateProjectionMatrix();
  controls.update();
}

function syncObservationControls() {
  elements['hero-room-toggle'].checked = state.heroRoomOnly;
  elements["mode-buttons"].querySelectorAll("button").forEach((button) => {
    button.classList.toggle("active", button.dataset.mode === state.mode);
  });
  elements["appearance-select"].value = state.appearanceMode;
  elements["room-lighting"].value = state.roomLighting;
  elements["quality-select"].value = state.renderProfile;
  elements["cutaway-toggle"].checked = state.autoCutaway;
  elements['xray-toggle'].checked = state.xray;
  elements['validation-toggle'].checked = state.showValidation;
  elements['navigation-toggle'].checked = state.showNavigation;
  elements['daylight-toggle'].checked = state.daylight;
  elements['sky-select'].value = state.skyPreset;
  elements['sky-rotation'].value = state.skyRotation;
  elements['district-select'].value = state.districtId;
  elements['building-select'].value = state.buildingId;
  updateFloorOptions();
  elements["outline-toggle"].checked = state.showOutlines;
  elements["labels-toggle"].checked = state.showLabels;
  elements["markings-toggle"].checked = state.showRoadMarkings;
  elements["high-fidelity-toggle"].checked = state.highFidelityOverview;
  elements["camera-high-fidelity"].classList.toggle("active", state.highFidelityOverview);
  updateModeHint();
}

function geometryVisibilitySignature() {
  const selection = state.mode === "room"
    ? [state.roomId]
    : ["floor", "floor_plan"].includes(state.mode)
      ? [state.buildingId, state.floorId]
      : state.mode === "building"
        ? [state.buildingId]
        : [];
  return JSON.stringify({
    geometryRevision: state.geometryRevision,
    mode: state.mode,
    selection,
    district: state.districtId,
    appearance: state.appearanceMode,
    profile: state.renderProfile,
    daylight: state.daylight,
    skyPreset: state.skyPreset,
    skyRotation: state.skyRotation,
    cutaway: state.autoCutaway,
    roomCamera: state.roomCameraPreset,
    roomLighting: state.roomLighting,
    outlines: state.showOutlines,
    labels: state.showLabels,
    markings: state.showRoadMarkings,
    xray: state.xray,
    hierarchyDisplay: state.hierarchyDisplay,
    presentationFocusId: state.presentationFocusId,
    exposure: state.captureExposure,
    navigation: state.showNavigation,
    validation: state.showValidation,
    heroRoomOnly: state.heroRoomOnly,
    observationTargets: [...state.observationTargetIds].sort(),
    observationKind: state.observationKind,
    highFidelityOverview: state.highFidelityOverview,
    semantics: [...state.enabledSemantics].sort(),
  });
}

function geometryContentSignature() {
  const content = JSON.parse(geometryVisibilitySignature());
  // Standard profiles differ in textures, glass and GLB/proxy policy. Only
  // the independent navigation cache can ignore the shading profile.
  if (state.renderProfile === "navigation") delete content.profile;
  if (screenQuality(state.renderProfile)) {
    camera.updateMatrixWorld();
    content.screen = [snapshotHeight || elements.viewport.clientHeight * renderer.getPixelRatio(),
      ...camera.matrixWorld.elements, ...camera.projectionMatrix.elements].map(x => Math.round(x*10000)/10000);
  }
  return JSON.stringify(content);
}

async function setObservationView(spec) {
  if (!state.data) throw new Error("CityG scene is not loaded yet");
  applyObservationState(spec);
  if (!Array.isArray(spec.camera_position) && state.mode === "room") focusRoom();
  if (!Array.isArray(spec.camera_position) && ["floor", "floor_plan"].includes(state.mode)) {
    fitFloorCameraPreset(state.mode === "floor_plan" ? "top" : state.floorCameraPreset);
  }
  syncObservationControls();
  const nextSignature = geometryVisibilitySignature();
  const geometryRebuilt = nextSignature !== state.geometryRenderSignature;
  if (geometryRebuilt || screenQuality(state.renderProfile)) renderGeometry();
  else if (state.renderProfile !== 'paper_capture') renderer.render(scene, camera);
  await requestStreamDetail();
  return {
    view_id: spec.view_id || null,
    ready: !state.streaming || state.streaming.status.ready,
    floor_camera_preset: state.floorCameraPreset,
    room_camera_preset: state.roomCameraPreset,
    geometry_rebuilt: geometryRebuilt,
    geometry_rebuild_count: state.geometryRebuildCount,
    render_profile: state.renderProfile,
    high_fidelity_overview: state.highFidelityOverview,
    visible_primitive_count: state.visiblePrimitives.length,
    selected_entities: { building_id: state.buildingId, floor_id: state.floorId, room_id: state.roomId },
    hierarchy_display: state.hierarchyDisplay,
    camera: {camera_position: camera.position.toArray(), look_at: controls.target.toArray(),
      up: camera.up.toArray(), fov_deg: camera.fov, near_clip_m: camera.near},
    shell_building_ids: [...new Set(state.visiblePrimitives.filter((p) =>
      state.data.layerMap.get(p.layer_id)?.layer_type === 'building_shell')
      .map((p) => state.data.hierarchy.entities.get(p.owner_id)?.buildingId).filter(Boolean))].sort(),
    transparent_building_ids: [...new Set(state.visiblePrimitives.filter(primitiveScopedShell)
      .map((p) => state.data.hierarchy.entities.get(p.owner_id)?.buildingId))],
    interior_floor_ids: [...new Set(state.visiblePrimitives.filter((p) =>
      state.data.layerMap.get(p.layer_id)?.layer_type === 'floor')
      .map((p) => state.data.hierarchy.entities.get(p.owner_id)?.floorId).filter(Boolean))].sort(),
    asset_status: { ...state.assetLoadState },
  };
}

function observationAssetStatus() {
  const geometryStatus = state.streaming?.status || { ready: true, pending: 0, failed: 0, generation: 0 };
  const assets = state.renderProfile === "navigation"
    // Navigation invalidates asset work without starting another GLB batch.
    // Its completed barrier therefore belongs to the current render generation,
    // not the last (possibly never started) asset-loading generation.
    ? { ...state.assetLoadState, generation: state.assetRenderGeneration, ready: true, pending: 0, failed: 0 }
    : state.assetLoadState;
  const textureStates = state.renderProfile === "navigation" ? []
    : [...state.materialTextureUrls].map((url) => textureLoadStates.get(url));
  const texturesPending = textureStates.filter((value) => value === "pending").length;
  const texturesFailed = textureStates.filter((value) => value === "failed").length;
  const needsEnvironment = RENDER_PROFILES[state.renderProfile].environment && Boolean(desiredEnvironment(state.data?.raw.config).filename);
  const envPending = needsEnvironment && environmentState !== 'ready' && environmentState !== 'failed' ? 1 : 0;
  const envFailed = needsEnvironment && environmentState === 'failed' ? 1 : 0;
  return {
    ...assets,
    ready: !state.contextLost && assets.ready && geometryStatus.ready && texturesPending === 0 && texturesFailed === 0 && !envPending && !envFailed,
    gpu: {context_lost: state.contextLost, context_losses: state.contextLosses,
      geometries: renderer.info.memory.geometries, textures: renderer.info.memory.textures,
      draw_calls: renderer.info.render.calls, triangles: renderer.info.render.triangles,
      ...assetTemplates.stats()},
    pending: assets.pending + texturesPending + geometryStatus.pending + envPending,
    failed: assets.failed + texturesFailed + geometryStatus.failed + envFailed,
    environment_state: needsEnvironment ? environmentState : 'not_requested',
    sky: {selected:state.skyPreset, active:Boolean(desiredEnvironment(state.data?.raw.config).preset && scene.background?.isTexture),
      rotation_deg:state.skyRotation, sun_direction:sun.position.clone().sub(sun.target.position).normalize().toArray()},
    screen_lod: {...screenLodStats},
    shading: {shadows: renderer.shadowMap.enabled, environment: Boolean(scene.environment),
      physical_glass: RENDER_PROFILES[state.renderProfile].physicalGlass, textures: RENDER_PROFILES[state.renderProfile].materialTextures},
    geometry_streaming: { ...geometryStatus,
      city_lod: Boolean(state.streaming),
      total_primitives: state.data?.geometry.streaming?.total_primitives || state.data?.geometry.primitives.length || 0,
      resident_primitives: state.data?.geometry.primitives.length || 0,
    },
    material_textures_expected: textureStates.length,
    material_textures_pending: texturesPending,
    material_textures_failed: texturesFailed,
    render_profile: state.renderProfile,
    geometry_rebuild_count: state.geometryRebuildCount,
    capture_sampling: state.renderProfile === "prototype_capture"
      ? {outdoor_asset_budget: 64, selected: state.prototypeCaptureAssetIds.size, original_scene_unchanged: true} : null,
    visible_primitive_count: state.visiblePrimitives.length,
  };
}

async function waitForObservationAssets(options = {}) {
  const timeoutMs = Math.max(100, Number(options.timeout_ms ?? 60000));
  const quietMs = Math.max(0, Number(options.quiet_ms ?? 160));
  const deadline = performance.now() + timeoutMs;
  while (performance.now() < deadline) {
    const generation = state.assetRenderGeneration;
    const pendingPromise = state.assetReadyPromise;
    const texturePromises = [...state.materialTextureUrls].map((url) => textureCache.get(url));
    const remaining = Math.max(1, deadline - performance.now());
    await Promise.race([
      Promise.allSettled([pendingPromise, state.streaming?.promise, environmentPromise, ...texturePromises]),
      new Promise((resolve) => setTimeout(resolve, Math.min(500, remaining))),
    ]);
    const status = observationAssetStatus();
    if (
      status.generation === generation
      && status.pending === 0
      && status.failed > 0
    ) return { ...status, ready: false, timed_out: false };
    if (status.generation === generation && status.ready && status.pending === 0) {
      if (quietMs) await new Promise((resolve) => setTimeout(resolve, quietMs));
      const stable = observationAssetStatus();
      if (
        stable.generation === generation
        && stable.ready
        && stable.pending === 0
      ) return { ...stable, timed_out: false };
    }
    // Already-resolved promises must not create an unbounded microtask loop
    // while a newer geometry/render generation has yet to settle.
    await new Promise((resolve) => setTimeout(resolve, Math.min(16, Math.max(1, deadline-performance.now()))));
  }
  return { ...observationAssetStatus(), ready: false, timed_out: true };
}

function captureObservationFrame() {
  if (state.contextLost) throw new Error('Graphics context is lost; wait for recovery before capturing');
  finishPresentationPreparation();
  // Read back the completed frame when possible; capturing an already settled
  // Presentation must not submit another full city + shadow render.
  if (state.cameraDirty || ['paper_capture','prototype_capture'].includes(state.renderProfile)) {
    renderer.render(scene, camera);
    state.cameraDirty = false;
  }
  return renderer.domElement.toDataURL("image/png");
}

async function saveHighQualityImage({longEdge = 2560, download = true, timeoutMs = 120000} = {}) {
  if (!state.data || !window.citygObservation.ready) throw new Error('Wait for the scene to finish loading');
  if (snapshotActive) throw new Error('An image export is already in progress');
  if (taskReplay?.status().playing) throw new Error('Pause the robot replay before saving an image');
  const saved = {profile: state.renderProfile, camera: camera.clone(), target: controls.target.clone(),
    enabled: controls.enabled, damping: controls.enableDamping};
  const size = snapshotSize(elements.viewport.clientWidth, elements.viewport.clientHeight, longEdge,
    Math.min(renderer.capabilities.maxTextureSize, renderer.getContext().getParameter(renderer.getContext().MAX_RENDERBUFFER_SIZE)));
  const started = performance.now();
  const locked = [...document.querySelectorAll('.topbar, .panel, #viewport')].map(el => [el, el.inert]);
  let progress;
  snapshotActive = true;
  snapshotHeight = size.height;
  state.navigationKeys.clear();
  clearTimeout(state.streamCameraTimer);
  controls.enabled = false;
  locked.forEach(([el]) => { el.inert = true; });
  elements['hq-screenshot-button'].disabled = true;
  try {
    setLoading(true, 'HQ PNG: preparing models and textures…');
    await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    applyRenderProfile('snapshot');
    renderGeometry();
    progress = setInterval(() => {
      const status = observationAssetStatus();
      setLoading(true, `HQ PNG: loading models/textures (${status.pending} pending)…`);
    }, 300);
    const assets = await waitForObservationAssets({timeout_ms: timeoutMs, quiet_ms: 180});
    clearInterval(progress);
    if (!assets.ready || assets.failed || assets.fallback) {
      throw new Error(assets.timed_out ? 'HQ export timed out loading assets; try again after loading, or use a smaller scene scope'
        : 'HQ export stopped: some assets or textures failed to load (no incomplete image saved)');
    }
    const prepared = performance.now();
    setLoading(true, `HQ PNG: rendering ${size.width} × ${size.height}…`);
    await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    // Do not change camera.aspect: the requested composition must be identical.
    renderer.setDrawingBufferSize(size.width, size.height, 1);
    renderer.render(scene, camera);
    const draw = {...renderer.info.render};
    const blob = await canvasPng(renderer.domElement);
    const filename = `${state.data.city.id}_${state.mode}_${new Date().toISOString().replace(/[:.]/g, '-')}_HQ.png`;
    if (download) {
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.download = filename; link.href = url;
      document.body.appendChild(link); link.click(); link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 30000);
    }
    const result = {filename, ...size, bytes: blob.size,
      prepare_ms: Math.round(prepared-started), render_encode_ms: Math.round(performance.now()-prepared),
      assets, draw, camera_position: camera.position.toArray(), look_at: controls.target.toArray(),
      city_lod: Boolean(state.streaming)};
    window.citygObservation.lastSnapshot = result;
    showToast(`HQ PNG ${size.width} × ${size.height}${download ? ' sent to browser downloads' : ' rendered'}`);
    return result;
  } finally {
    clearInterval(progress);
    // Restore even on load/encode errors; screenshot quality is never persisted.
    try {
      snapshotHeight = null;
      camera.copy(saved.camera);
      controls.target.copy(saved.target);
      applyRenderProfile(saved.profile);
      // Avoid a restoration draw at the large export resolution (especially
      // when returning to a Retina presentation profile).
      renderer.setSize(elements.viewport.clientWidth, elements.viewport.clientHeight, false);
      renderGeometry();
    } finally {
      snapshotActive = false;
      controls.enabled = saved.enabled;
      controls.enableDamping = saved.damping;
      locked.forEach(([el, inert]) => { el.inert = inert; });
      elements['hq-screenshot-button'].disabled = false;
      setLoading(false);
      resize();
      state.cameraDirty = true;
    }
  }
}

function exportRenderView({download = true} = {}) {
  if (!state.data) throw new Error('Load a scene before exporting a render view');
  if (snapshotActive) throw new Error('Wait for the current image export to finish');
  const replay=taskReplay?.status() || null;
  if (replay?.playing) throw new Error('Pause robot playback before exporting the render view');
  const config=state.data.raw.config || {};
  const doc=renderViewDocument({camera, target:controls.target,
    viewport:{width:elements.viewport.clientWidth,height:elements.viewport.clientHeight,
      bufferWidth:renderer.domElement.width,bufferHeight:renderer.domElement.height},
    sceneRef:{city_id:state.data.city.id,label:config.label || '',source:config.source || '',
      original_source:config.original_source || null,
      geometry_revision:state.geometryRevision,
      total_primitives:state.data.geometry.streaming?.total_primitives || state.data.geometry.primitives.length},
    selection:{district_id:state.districtId,building_id:state.buildingId || null,
      floor_id:state.floorId || null,room_id:state.roomId || null,primitive_id:state.selectedPrimitive?.id || null},
    visibility:{mode:state.mode,room_camera_preset:state.roomCameraPreset,floor_camera_preset:state.floorCameraPreset,
      auto_cutaway:state.autoCutaway,xray_shells:state.xray,hierarchy_display:state.hierarchyDisplay,
      presentation_focus_id:state.presentationFocusId,hero_room_only:state.heroRoomOnly,
      enabled_semantics:[...state.enabledSemantics].sort(),show_grid:grid.visible,
      show_outlines:state.showOutlines,show_labels:state.showLabels,show_road_markings:state.showRoadMarkings,
      show_navigation:state.showNavigation,show_validation:state.showValidation,
      door_states:Object.fromEntries(state.doorStates),visible_primitive_count:state.visiblePrimitives.length},
    lighting:{render_profile:state.renderProfile,appearance:state.appearanceMode,room_lighting:state.roomLighting,
      daylight:state.daylight,sky_preset:state.skyPreset,sky_rotation_deg:state.skyRotation,
      tone_mapping:'ACESFilmic',tone_mapping_exposure:renderer.toneMappingExposure,
      environment_intensity:scene.environmentIntensity,shadows:renderer.shadowMap.enabled},
    replay,assetStatus:observationAssetStatus()});
  if (download) {
    const url=URL.createObjectURL(new Blob([JSON.stringify(doc,null,2)+'\n'],{type:'application/json'}));
    const link=document.createElement('a');link.download=renderViewFilename(doc);link.href=url;
    document.body.appendChild(link);link.click();link.remove();
    setTimeout(()=>URL.revokeObjectURL(url),30000);
    showToast('Render view JSON sent to browser downloads');
  }
  return doc;
}

window.citygObservation = {
  ready: false,
  setView: setObservationView,
  getAssetStatus: observationAssetStatus,
  waitForAssets: waitForObservationAssets,
  captureFrame: captureObservationFrame,
  saveHighQualityImage,
  exportRenderView,
  getViewState: () => ({camera_position: camera.position.toArray(), look_at: controls.target.toArray(),
    up: camera.up.toArray(), fov_deg: camera.fov, aspect: camera.aspect, mode: state.mode,
    near_clip_m:camera.near,far_clip_m:camera.far,
    render_profile: state.renderProfile, appearance: state.appearanceMode,
    sky_preset:state.skyPreset,sky_rotation_deg:state.skyRotation,daylight:state.daylight}),
};

function focusCurrentSelection() {
  if (state.selectedPrimitive) return focusPrimitive(state.selectedPrimitive);
  if (state.mode === "floor_plan") {
    fitFloorPlan();
    return;
  }
  if (state.mode === "room" && state.roomId) {
    if (focusRoom()) return;
  }
  if (state.mode === "floor" && state.floorId) {
    if (fitFloorCameraPreset(state.floorCameraPreset)) return;
  }
  if ((state.mode === "building" || state.mode === "floor") && state.buildingId) {
    if (focusBounds(buildingBounds().get(state.buildingId))) return;
  }
  if (state.districtId !== "all") return focusEntity(state.districtId);
  fitCity("iso");
}

function clearSelection() {
  state.cameraDirty = true;
  state.selectedPrimitive = null;
  highlight.visible = false;
  clearGroup(pathGroup);
  updateInspector();
}

function renderLegend() {
  const semantics = [...state.enabledSemantics].sort();
  elements.legend.replaceChildren(...semantics.map((semantic) => {
    const item = document.createElement("span");
    const swatch = document.createElement("i"); swatch.className = "swatch";
    swatch.style.background = `#${(semanticPalette[semantic] || 0x8aa39c).toString(16).padStart(6, "0")}`;
    item.append(swatch, document.createTextNode(semantic.replaceAll("_", " "))); return item;
  }));
  elements.legend.style.display = state.appearanceMode === "semantic" ? "flex" : "none";
}

function setLoading(show, text = "Preparing city geometry") {
  elements.loading.classList.toggle("hidden", !show);
  elements.loading.querySelector("span").textContent = text;
}

function showToast(message) {
  elements.toast.textContent = message;
  elements.toast.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => elements.toast.classList.remove("show"), 2400);
}

function format(value) { return Number(value).toFixed(Math.abs(value) >= 100 ? 1 : 2); }

function isFormElement(target) {
  return target instanceof HTMLInputElement
    || target instanceof HTMLSelectElement
    || target instanceof HTMLTextAreaElement
    || target?.isContentEditable;
}

const keyboardNavigationKeys = new Set([
  "w", "a", "s", "d", "q", "e",
  "arrowleft", "arrowright", "arrowup", "arrowdown", "shift",
]);
elements.viewport.addEventListener("pointerenter", () => {
  state.keyboardNavigationActive = true;
});
elements.viewport.addEventListener("pointerleave", () => {
  state.keyboardNavigationActive = false;
  state.navigationKeys.clear();
});
window.addEventListener("keydown", (event) => {
  if (snapshotActive) return;
  if (!state.keyboardNavigationActive || isFormElement(event.target)) return;
  const key = event.key.toLowerCase();
  if (!keyboardNavigationKeys.has(key)) return;
  state.navigationKeys.add(key);
  event.preventDefault();
});
window.addEventListener("keyup", (event) => {
  state.navigationKeys.delete(event.key.toLowerCase());
});
window.addEventListener("blur", () => state.navigationKeys.clear());

renderer.domElement.addEventListener("pointerdown", (event) => {
  pointerStart = [event.clientX, event.clientY];
  state.cameraInteracting = true;
});
renderer.domElement.addEventListener("pointerup", (event) => {
  const wasClick = pointerStart && Math.hypot(event.clientX - pointerStart[0], event.clientY - pointerStart[1]) <= 4;
  state.cameraInteracting = false;
  pointerStart = null;
  if (state.renderProfile === "navigation") {
    renderer.render(scene, camera);
    state.lastNavigationRenderTime = performance.now();
  }
  if (!wasClick) return;
  const rect = renderer.domElement.getBoundingClientRect();
  pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
  pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
  raycaster.setFromCamera(pointer, camera);
  const hit = raycaster.intersectObjects(
    [...geometryGroup.children, ...assetGroup.children, ...navigationPreviewGroup.children],
    true
  )[0];
  if (!hit) { state.selectedPrimitive = null; updateInspector(); highlight.visible = false; return; }
  if (hit.instanceId !== undefined) {
    selectPrimitive(hit.object.userData.entries[hit.instanceId]);
    return;
  }
  let node = hit.object;
  while (node && !node.userData.entry) node = node.parent;
  if (node?.userData.entry) selectPrimitive(node.userData.entry);
  else { state.selectedPrimitive = null; updateInspector(); highlight.visible = false; }
});
renderer.domElement.addEventListener("pointercancel", () => {
  pointerStart = null;
  state.cameraInteracting = false;
  if (state.renderProfile === "navigation") renderer.render(scene, camera);
});

elements["mode-buttons"].addEventListener("click", (event) => {
  const button = event.target.closest("button[data-mode]"); if (!button) return;
  state.mode = button.dataset.mode;
  state.hierarchyDisplay = null;
  state.presentationFocusId = null;
  if (state.mode === "floor") state.floorCameraPreset = "perspective";
  if (state.mode !== "floor" && state.mode !== "floor_plan") state.floorCameraPreset = "perspective";
  elements["mode-buttons"].querySelectorAll("button").forEach((item) => item.classList.toggle("active", item === button));
  updateModeHint();
  clearSelection();
  renderGeometry();
  if (["building", "floor", "floor_plan", "room"].includes(state.mode)) focusCurrentSelection();
});
elements["district-select"].addEventListener("change", (event) => {
  state.districtId = event.target.value; clearSelection(); updateBuildingOptions(); renderGeometry();
});
elements["building-select"].addEventListener("change", (event) => {
  state.hierarchyDisplay = null;
  state.presentationFocusId = null;
  state.buildingId = event.target.value; clearSelection(); updateFloorOptions(); renderGeometry();
  updateFloorCameraControls();
  if (["building", "floor", "floor_plan", "room"].includes(state.mode)) focusCurrentSelection();
});
elements["floor-select"].addEventListener("change", (event) => {
  state.hierarchyDisplay = null;
  state.presentationFocusId = null;
  state.floorId = event.target.value; state.roomId = ""; updateRoomOptions(); clearSelection(); renderGeometry();
  updateFloorCameraControls();
  if (["floor", "floor_plan", "room"].includes(state.mode)) focusCurrentSelection();
});
elements["room-select"].addEventListener("change", (event) => {
  state.roomId = event.target.value; clearSelection(); renderGeometry();
  if (state.mode === "room") focusCurrentSelection();
});
elements["hero-room-toggle"].addEventListener("change", (event) => {
  state.heroRoomOnly = event.target.checked;
  state.roomId = "";
  updateRoomOptions();
  clearSelection();
  renderGeometry();
});
elements["focus-button"].addEventListener("click", focusCurrentSelection);
elements["floor-plan-button"].addEventListener("click", () => {
  state.hierarchyDisplay = null;
  state.presentationFocusId = null;
  setFloorCameraPreset("top");
});
elements["floor-camera-buttons"]?.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-floor-camera]");
  if (!button) return;
  setFloorCameraPreset(button.dataset.floorCamera);
});
elements["room-view-button"].addEventListener("click", () => {
  state.hierarchyDisplay = null;
  state.presentationFocusId = null;
  if (!state.buildingId || !state.floorId || !state.roomId) {
    showToast("Select a building, floor, and room first");
    return;
  }
  if (!roomHasRealizedWalls(state.roomId)) {
    showToast("This planned room is outside the realized building massing");
    return;
  }
  state.mode = "room";
  elements["mode-buttons"].querySelectorAll("button").forEach((item) => {
    item.classList.toggle("active", item.dataset.mode === state.mode);
  });
  clearSelection();
  updateModeHint();
  renderGeometry();
  focusRoom();
});
elements["room-camera-buttons"].addEventListener("click", (event) => {
  const button = event.target.closest("button[data-room-camera]");
  if (!button || !state.roomId) return;
  state.roomCameraPreset = button.dataset.roomCamera;
  focusRoom(); updateFloorCameraControls(); renderGeometry();
});
elements["room-lighting"].addEventListener("change", (event) => {
  state.roomLighting = event.target.value;
  renderGeometry();
});
elements["appearance-select"].addEventListener("change", (event) => {
  state.appearanceMode = event.target.value;
  renderLegend();
  renderGeometry();
});
let qualityTransition = 0;
elements["quality-select"].addEventListener("change", async (event) => {
  const name = event.target.value, transition = ++qualityTransition;
  if (state.contextLost) return;
  elements['render-status'].textContent = name === 'navigation'
    ? 'Releasing high-quality resources…' : 'Preparing Presentation · loading models in batches…';
  // Paint feedback before the synchronous geometry build; keep the existing
  // canvas frame instead of clearing it to a white loading screen.
  await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  if (transition !== qualityTransition || state.contextLost) return;
  try {
    applyRenderProfile(name, { persist: true });
    renderGeometry();
    updateModeHint();
  } catch (error) {
    applyRenderProfile('navigation'); renderGeometry(); handleError(error);
  }
});

// Three.js restores its internal GL state. The application must additionally
// invalidate generated PMREM/shadow targets and avoid re-uploading the entire
// city immediately, or a memory-pressure loss can become an endless loop.
const gpuNotice = document.createElement('div');
gpuNotice.id = 'gpu-recovery-notice';
gpuNotice.style.cssText = 'display:none;position:absolute;top:16px;left:16px;right:16px;z-index:30;padding:16px;background:#21333a;color:white;border:1px solid #e4ac63;border-radius:8px';
elements.viewport.append(gpuNotice);
function showGpuNotice(message) {
  gpuNotice.replaceChildren(document.createTextNode(message + ' '));
  const dismiss = document.createElement('button'); dismiss.textContent = 'Dismiss';
  dismiss.onclick = () => { gpuNotice.style.display = 'none'; };
  const reload = document.createElement('button'); reload.textContent = 'Reload Viewer';
  reload.onclick = () => window.location.reload();
  gpuNotice.append(dismiss, reload); gpuNotice.style.display = 'block';
}
renderer.domElement.addEventListener('webglcontextlost', event => {
  event.preventDefault();
  state.contextLost = true; state.contextLosses++;
  qualityTransition++;
  clearTimeout(state.streamCameraTimer);
  releaseStandardGeometry();
  assetTemplates.clear();
  clearGroup(navigationPreviewGroup);
  // Dispose old-context handles while the context is lost, not after restoration.
  // CPU geometry/texture data stays available for Three.js to upload again.
  const geometries = new Set([unitBox,unitCylinder,unitSphere,...texturedBoxCache.values()]);
  const materials = new Set();
  scene.traverse(node => {
    if (node.geometry) geometries.add(node.geometry);
    for (const m of [node.material].flat().filter(Boolean)) materials.add(m);
  });
  geometries.forEach(g=>g.dispose()); materials.forEach(m=>m.dispose());
  sharedMaterialTextures.forEach(t=>t.dispose());
  environmentGeneration++;
  for (const entry of environmentCache.values()) { entry.target.dispose(); entry.source.dispose(); }
  environmentCache.clear(); environmentLoads.clear(); environmentTarget = null;
  indoorStudioTarget?.dispose(); indoorStudioTarget = null;
  currentEnvironmentUrl = ''; environmentState = 'idle'; scene.environment = null;
  sun.shadow.map?.dispose(); sun.shadow.map = null;
  pmremGenerator.dispose();
  setLoading(false);
  showGpuNotice('Graphics context lost. Waiting for the browser to restore it; your scene and camera are unchanged. If it does not recover, reload this Viewer.');
});
renderer.domElement.addEventListener('webglcontextrestored', () => {
  pmremGenerator = new THREE.PMREMGenerator(renderer);
  state.contextLost = false;
  applyRenderProfile('navigation', {persist:true});
  state.navigationGeometryContentSignature = '';
  renderGeometry();
  showGpuNotice('Graphics restored in Navigation preview. Your camera is preserved. You can retry Presentation, or move closer to a smaller area first.');
});
elements["daylight-toggle"].addEventListener("change", (event) => {
  state.daylight = event.target.checked; applyTheme(); renderGeometry();
});
elements['sky-select'].addEventListener('change', event => {
  state.skyPreset=event.target.value;
  renderGeometry();
});
elements['sky-rotation'].addEventListener('change', event => {
  state.skyRotation=Number(event.target.value);
  renderGeometry();
});
elements["cutaway-toggle"].addEventListener("change", (event) => { state.autoCutaway = event.target.checked; renderGeometry(); });
elements["outline-toggle"].addEventListener("change", (event) => { state.showOutlines = event.target.checked; renderGeometry(); });
elements["labels-toggle"].addEventListener("change", (event) => { state.showLabels = event.target.checked; renderGeometry(); });
elements["markings-toggle"].addEventListener("change", (event) => { state.showRoadMarkings = event.target.checked; renderGeometry(); });
elements["high-fidelity-toggle"].addEventListener("change", (event) => {
  setHighFidelityOverview(event.target.checked);
});
elements["xray-toggle"].addEventListener("change", (event) => { state.xray = event.target.checked; renderGeometry(); });
elements['hierarchy-display-button'].addEventListener('click', async () => {
  if (!state.buildingId || !state.floorId) return showToast('Select a building and floor first');
  const floor = state.data.hierarchy.entities.get(state.floorId)?.entity;
  await setObservationView({mode: 'overview', kind: 'hierarchy', auto_cutaway: false,
    target_entity_ids: [state.buildingId, state.floorId],
    hierarchy_display: {building_id: state.buildingId, floor_id: state.floorId,
      shell_opacity: 0.12, cut_above_m: floor.elevation_m + floor.height_m},
  });
  showToast('Only the selected shell is translucent. Scene mode exits hierarchy display.');
});
elements["navigation-toggle"].addEventListener("change", (event) => { state.showNavigation = event.target.checked; renderGeometry(); });
elements["validation-toggle"].addEventListener("change", (event) => { state.showValidation = event.target.checked; renderGeometry(); });
elements["grid-toggle"].addEventListener("change", (event) => {
  grid.visible = event.target.checked; state.cameraDirty = true;
});
elements["door-button"].addEventListener("click", () => {
  const machineId = state.selectedPrimitive?.metadata?.state_machine_id; if (!machineId) return;
  const machine = state.data.interactions.state_machines.find((item) => item.id === machineId);
  if (machine?.state_type === "elevator_controller") {
    const levels = Object.keys(machine.states).sort((a, b) => machine.states[a].current_level - machine.states[b].current_level);
    const current = levels.indexOf(state.doorStates.get(machineId));
    state.doorStates.set(machineId, levels[(current + 1) % levels.length]);
  } else {
    state.doorStates.set(machineId, state.doorStates.get(machineId) === "open" ? "closed" : "open");
  }
  renderGeometry(); updateInspector();
});
elements["route-button"].addEventListener("click", routeToSelection);
elements["camera-iso"].addEventListener("click", () => fitCity("iso"));
elements["camera-high-fidelity"].addEventListener("click", () => {
  setHighFidelityOverview(!state.highFidelityOverview);
});
elements["camera-top"].addEventListener("click", () => fitCity("top"));
elements["camera-street"].addEventListener("click", fitStreet);
elements["camera-reset"].addEventListener("click", () => fitCity("fit"));
elements["reload-button"].addEventListener("click", () => loadServerScene().catch(handleError));
elements["folder-input"].addEventListener("change", (event) => loadFolder(event.target.files).catch(handleError));
elements["screenshot-button"].addEventListener("click", () => {
  renderer.render(scene, camera);
  const link = document.createElement("a");
  link.download = `${state.data?.city?.id || "cityg"}.png`; link.href = renderer.domElement.toDataURL("image/png"); link.click();
});
elements['hq-screenshot-button'].addEventListener('click', () => saveHighQualityImage().catch(handleError));
elements['export-render-view-button'].addEventListener('click', () => {
  try { exportRenderView(); } catch (error) { handleError(error); }
});

function handleError(error) {
  console.error(error); setLoading(false); showToast(error.message || String(error));
}

taskReplay = installTaskReplay({scene,
  cameraState:()=>({position:camera.position.toArray(),target:controls.target.toArray(),up:camera.up.toArray()}),
  begin:()=>{if (state.renderProfile==='navigation') applyRenderProfile('review');},
  rebuild:()=>{state.geometryRevision+=1;state.geometryRenderSignature='';renderGeometry();},
  draw:()=>{renderer.render(scene,camera);state.cameraDirty=true;},
  error:showToast,
  follow:(base,previous,options={})=>{
    const buildings=state.data.city.districts.flatMap(d=>d.parcels.flatMap(p=>p.buildings));
    const building=buildings.find(b=>base[0]>=b.footprint.min_x && base[0]<=b.footprint.max_x
      && base[1]>=b.footprint.min_y && base[1]<=b.footprint.max_y);
    const floor=building?.floors.reduce((best,f)=>Math.abs(f.elevation_m-(base[2]-.75))<Math.abs(best.elevation_m-(base[2]-.75))?f:best,building.floors[0]);
    const key=floor?.id || 'outdoors';
    if (key!==previous) {
      state.mode=building?'floor_plan':'overview';state.buildingId=building?.id||'';state.floorId=floor?.id||'';
      state.autoCutaway=true;state.geometryRenderSignature='';
      updateBuildingOptions();updateFloorOptions();updateRoomOptions();updateModeHint();
      elements['mode-buttons'].querySelectorAll('button').forEach(button=>{
        button.classList.toggle('active',button.dataset.mode===(building?'floor':'overview'));
      });
      renderGeometry();
    }
    const pose=replayCameraPose(base,options.yaw,options.mode,!!building);
    // A previously selected top-down floor view may have changed the up axis.
    camera.up.set(0,0,1);
    camera.position.fromArray(pose.position);
    controls.target.fromArray(pose.target);
    controls.update();return key;
  },
});
loadServerScene().catch(handleError);
