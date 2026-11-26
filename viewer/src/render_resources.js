// Explicit ownership: instance buffers belong to the displayed batch, whereas
// GLB meshes/materials/textures belong to a template, not to its clones.
export function disposeInstances(object) {
  object.traverse(node => { if (node.isInstancedMesh) node.dispose(); });
}

export function disposeTemplate(root) {
  const geometries = new Set(), materials = new Set(), textures = new Set(), images = new Set();
  root.traverse(node => {
    if (node.geometry) geometries.add(node.geometry);
    for (const m of [node.material].flat().filter(Boolean)) materials.add(m);
  });
  for (const m of materials) for (const value of Object.values(m)) {
    if (value?.isTexture) textures.add(value);
  }
  disposeInstances(root);
  for (const g of geometries) g.dispose();
  for (const m of materials) m.dispose();
  for (const t of textures) { t.dispose(); if (t.source?.data) images.add(t.source.data); }
  for (const image of images) image.close?.();
}

export function templateBytes(root) {
  const buffers = new Set(), textures = new Set();
  let bytes = 0;
  root.traverse(node => {
    for (const a of [...Object.values(node.geometry?.attributes || {}), node.geometry?.index]) {
      const b = (a?.array || a?.data?.array)?.buffer;
      if (b && !buffers.has(b)) { buffers.add(b); bytes += b.byteLength; }
    }
    for (const m of [node.material].flat().filter(Boolean)) for (const t of Object.values(m)) {
      if (!t?.isTexture || textures.has(t.source)) continue;
      textures.add(t.source);
      const image = t.source?.data;
      bytes += (image?.width || 0) * (image?.height || 0) * 4 * 4/3;
    }
  });
  return bytes;
}

// Bound concurrent GLB decoding (including requests from obsolete generations).
// A queued, obsolete request is discarded before doing any IO/decoding.
export class AssetTemplatePool {
  constructor(load, {concurrency = 3, idleBytes = 64 * 1024 * 1024} = {}) {
    this.load = load; this.concurrency = concurrency; this.idleBytes = idleBytes;
    this.entries = new Map(); this.active = new Set(); this.queue = []; this.running = 0;
  }
  retain(keys) { this.active = new Set(keys); this.trim(); }
  get(key) {
    let e = this.entries.get(key);
    if (e) { this.entries.delete(key); this.entries.set(key, e); return e.promise; }
    e = {root:null, bytes:0};
    e.promise = new Promise((resolve, reject) => { e.resolve = resolve; e.reject = reject; });
    this.entries.set(key,e); this.queue.push([key,e]); this.pump(); return e.promise;
  }
  pump() {
    while (this.running < this.concurrency && this.queue.length) {
      const [key,e] = this.queue.shift();
      if (this.entries.get(key) !== e || !this.active.has(key)) {
        if (this.entries.get(key) === e) this.entries.delete(key);
        e.reject(new Error('Obsolete asset request')); continue;
      }
      this.running++;
      Promise.resolve().then(() => this.load(key)).then(root => {
        if (this.entries.get(key) !== e) {
          disposeTemplate(root); e.reject(new Error('Obsolete asset cache')); return;
        }
        e.root = root; e.bytes = templateBytes(root); e.resolve(root);
      }, error => {
        if (this.entries.get(key) === e) this.entries.delete(key);
        e.reject(error);
      }).finally(() => { this.running--; this.trim(); this.pump(); });
    }
  }
  trim() {
    let idle = [...this.entries].reduce((n,[k,e]) => n + (this.active.has(k) ? 0 : e.bytes),0);
    for (const [key,e] of this.entries) {
      if (idle <= this.idleBytes) break;
      if (e.root && !this.active.has(key)) {
        this.entries.delete(key); idle -= e.bytes; disposeTemplate(e.root);
      }
    }
  }
  clear() {
    this.active.clear();
    for (const e of this.entries.values()) if (e.root) disposeTemplate(e.root);
    this.entries.clear(); this.pump();
  }
  stats() { return {templates:this.entries.size, loading:this.running, queued:this.queue.length,
    estimated_template_bytes:[...this.entries.values()].reduce((n,e)=>n+e.bytes,0)}; }
}

export async function runAssetBatches(items, run, current, concurrency = 3) {
  let cursor = 0;
  await Promise.all(Array.from({length:concurrency}, async () => {
    while (cursor < items.length && current()) {
      await run(items[cursor++]);
      // Even cached templates must yield a task, not an endless microtask chain.
      await new Promise(resolve => setTimeout(resolve,0));
    }
  }));
}

export function displayPixelRatio(width, height, requested) {
  // Limit Retina framebuffers, not texture quality or screenshot resolution.
  return Math.min(requested, Math.sqrt(3_000_000 / Math.max(1,width*height)));
}

export function canPresent(status) {
  // pending reaches zero in the last worker before the batch promise settles.
  // Publishing at that point draws twice: once now, again on its ready callback.
  return status.pending === 0 && (status.ready || status.failed > 0) && !status.gpu?.context_lost;
}

export function textureEdgeForPixels(pixels) {
  // At least 2x the projected object diameter. Close-up assets use their
  // original maps, including normal/roughness/alpha. This is not a proxy mode.
  if (pixels <= 128) return 256;
  if (pixels <= 512) return 1024;
  return 0;
}

export async function resizeTemplateTextures(root, maxEdge, resizeImage) {
  if (!maxEdge) return root;
  const textures = new Set(), replacements = new Map();
  root.traverse(node => {
    for (const m of [node.material].flat().filter(Boolean)) for (const t of Object.values(m))
      if (t?.isTexture) textures.add(t);
  });
  for (const t of textures) {
    const image = t.source?.data;
    // Compressed/data/cube maps require their own formats; never reinterpret.
    if (!image || image.data || Array.isArray(image) || t.isCompressedTexture
        || Math.max(image.width || 0,image.height || 0) <= maxEdge) continue;
    if (!replacements.has(image)) {
      const ratio = maxEdge / Math.max(image.width,image.height);
      replacements.set(image, await resizeImage(image,
        Math.max(1,Math.round(image.width*ratio)),Math.max(1,Math.round(image.height*ratio))));
    }
  }
  // Finish all resizing before mutating shared sources or closing bitmaps.
  const originals = new Map([...textures].map(t => [t,t.source?.data]));
  for (const t of textures) {
    const resized = replacements.get(originals.get(t));
    if (resized) { t.image = resized; t.needsUpdate = true; }
  }
  for (const image of replacements.keys()) image.close?.();
  return root;
}
