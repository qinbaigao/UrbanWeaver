// Bounded real-asset sampling for opt-in, headless layout review only.
// This never changes the dataset or normal interactive/Presentation rendering.
export function outdoorCaptureCandidate(p) {
  return Boolean(p.metadata?.resolved_asset && p.metadata?.asset_id)
    && !String(p.metadata.asset_id).startsWith("facade_");
}

export function selectPrototypeCaptureAssets(primitives, camera, kind, limit = 64) {
  const buckets = new Map();
  const candidates = primitives.filter(outdoorCaptureCandidate);
  const distance = (p) => Math.hypot(p.center.x - camera.x, p.center.y - camera.y);
  for (const p of [...candidates].sort((a,b) => kind === "global"
    ? String(a.id).localeCompare(String(b.id)) : distance(a)-distance(b) || String(a.id).localeCompare(String(b.id)))) {
    const key = kind === "global"
      ? `${Math.floor(p.center.x / 100)}:${Math.floor(p.center.y / 100)}`
      : p.metadata.asset_category || p.semantic_class;
    if (!buckets.has(key)) buckets.set(key, []);
    buckets.get(key).push(p);
  }
  const result = new Set();
  const lists = [...buckets.values()];
  // Round-robin sectors for aerials and categories for local views. Each
  // selected object remains its original GLB at its original pose/scale.
  for (let i=0; result.size<limit; i++) {
    let added=false;
    for (const list of lists) {
      if (i<list.length && result.size<limit) { result.add(list[i].id); added=true; }
    }
    if (!added) break;
  }
  return result;
}
