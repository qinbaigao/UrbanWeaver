// Geometry paging is independent of Three.js: test races/failures without WebGL.
export class ProgressiveGeometry {
  constructor(manifest, overview, fetchJson, onCommit, onStatus = () => {}) {
    this.manifest = manifest;
    this.overview = overview;
    this.fetchJson = fetchJson;
    this.onCommit = onCommit;
    this.onStatus = onStatus;
    this.cache = new Map();
    this.generation = 0;
    this.key = null;
    this.status = { ready: true, pending: 0, failed: 0, generation: 0, loaded_chunks: 0 };
    this.promise = Promise.resolve();
  }

  request(chunks) {
    const key = chunks.map((c) => c.file).sort().join('|');
    if (key === this.key) return this.promise;
    this.key = key;
    this.controller?.abort();
    const controller = new AbortController();
    this.controller = controller;
    const generation = ++this.generation;
    this.status = { ready: false, pending: chunks.length, failed: 0, generation, loaded_chunks: 0 };
    this.onStatus(this.status);
    this.promise = (async () => {
      const loaded = new Map();
      try {
        // Bounded concurrency and atomic commit: never mix two camera requests.
        let cursor = 0;
        const worker = async () => {
          while (cursor < chunks.length && !controller.signal.aborted) {
            const descriptor = chunks[cursor++];
            const cached = this.cache.get(descriptor.file);
            const data = cached?.data || await this.fetchJson(descriptor.file, true, controller.signal);
            if (controller.signal.aborted || generation !== this.generation) return;
            if (!Array.isArray(data?.primitives) || data.primitives.length !== descriptor.count) {
              throw new Error(`Invalid geometry chunk: ${descriptor.file}`);
            }
            this.cache.delete(descriptor.file);
            this.cache.set(descriptor.file, { data, bytes: descriptor.bytes });
            loaded.set(descriptor.file, data.primitives);
            this.status.pending -= 1;
            this.status.loaded_chunks += 1;
          }
        };
        await Promise.all([worker(), worker()]);
        if (controller.signal.aborted || generation !== this.generation) return;
        const detail = chunks.flatMap((c) => loaded.get(c.file));
        const ids = new Set(detail.map((p) => p.id));
        const primitives = this.overview.filter((p) => !ids.has(p.id)).concat(detail);
        // Keep active chunks; evict old neighborhoods rather than growing with
        // every camera move. GLB template caching is handled by the renderer.
        const active = new Set(chunks.map((c) => c.file));
        let bytes = [...this.cache.values()].reduce((sum, item) => sum+item.bytes, 0);
        for (const [file, item] of this.cache) {
          if (bytes <= 48 * 1024 * 1024) break;
          if (!active.has(file)) { this.cache.delete(file); bytes -= item.bytes; }
        }
        this.onCommit(primitives);
        this.status.ready = true;
        this.onStatus(this.status);
      } catch (error) {
        if (generation !== this.generation || controller.signal.aborted) return;
        controller.abort();
        this.status = { ...this.status, ready: false, pending: 0, failed: 1, error: String(error) };
        this.onStatus(this.status);
      }
    })();
    return this.promise;
  }

  dispose() { this.generation += 1; this.controller?.abort(); this.cache.clear(); }
}

const distance = (bounds, point) => Math.hypot(
  Math.max(bounds[0]-point.x, 0, point.x-bounds[2]),
  Math.max(bounds[1]-point.y, 0, point.y-bounds[3]),
);

export function selectDetailChunks(manifest, { profile, mode, buildingId, targets = [], kind,
  camera, focus, localRadius = 180, screenMeasure }) {
  if (profile === 'navigation') return [];
  // Publication captures must not silently substitute the city LOD subset.
  if (profile === 'paper_capture' && ['overview', 'building', 'full'].includes(mode)) return manifest.chunks;
  // High-quality views recover *all* discernible detail, irrespective of
  // altitude or the previous three-building quota. Local scope still wins.
  if (screenMeasure && ['interactive', 'presentation', 'snapshot'].includes(profile)
      && ['overview', 'full', 'building'].includes(mode)) {
    return manifest.chunks.filter(c => {
      if (mode === 'building' && c.scope_id === buildingId) return true;
      const m = screenMeasure(c);
      return (m.visible || m.shadow) && m.pixels >= 0.75;
    });
  }
  // Global observation targets are semantic evidence bindings, not requests
  // to fetch every building/road at full detail. Keep the city-wide LOD.
  if (kind === 'global' && mode === 'overview') return [];
  const explicit = new Set(targets);
  if (['building', 'floor', 'floor_plan', 'room'].includes(mode) && buildingId) explicit.add(buildingId);
  const selected = manifest.chunks.filter((c) => explicit.has(c.scope_id)
    || c.owner_ids.some((id) => explicit.has(id)));
  const ids = new Set(selected.map((c) => c.file));
  // Aerial overview stays at city LOD. Street-level/close-up cameras bring in
  // a bounded neighborhood; explicitly requested entities are never budget-cut.
  if (camera.z < 180 && ['overview', 'full'].includes(mode)) {
    const candidates = manifest.chunks.map((c) => ({ c, d: Math.min(distance(c.bounds, camera), distance(c.bounds, focus)) }))
      .filter(({ c, d }) => !ids.has(c.file) && d < localRadius)
      .sort((a, b) => a.d-b.d || a.c.file.localeCompare(b.c.file));
    const buildings = new Set(selected.filter((c) => c.scope === 'building').map((c) => c.scope_id));
    let globalCount = 0;
    for (const { c } of candidates) {
      if (c.scope === 'building') {
        if (!buildings.has(c.scope_id) && buildings.size >= 3) continue;
        buildings.add(c.scope_id);
      } else {
        if (globalCount+c.count > 10000) continue;
        globalCount += c.count;
      }
      ids.add(c.file);
    }
    // Selecting a building means all of its chunks, even if their individual
    // AABBs are outside the neighborhood (e.g. a large podium).
    for (const c of manifest.chunks) if (buildings.has(c.scope_id) && c.scope === 'building') ids.add(c.file);
  }
  return manifest.chunks.filter((c) => ids.has(c.file));
}
