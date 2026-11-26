// Cached maps must be bound synchronously during camera-triggered rebuilds.
// A resolved Promise still defers callbacks: drawing immediately after the
// rebuild otherwise flashes untextured (often white) facade materials.
export function bindSharedTexture(cache, url, assign) {
  if (cache.ready.has(url)) {assign(cache.ready.get(url));return;}
  if (!cache.promises.has(url)) {
    cache.states.set(url,'pending');
    cache.promises.set(url,cache.load(url).then(texture=>{
      cache.ready.set(url,texture);cache.owned.add(texture);
      cache.states.set(url,'loaded');return texture;
    },error=>{cache.states.set(url,'failed');throw error;}));
  }
  cache.promises.get(url).then(assign).catch(()=>{});
}

export function disposeOwnedMap(material, sharedTextures) {
  if (material?.map && !sharedTextures.has(material.map)) material.map.dispose();
}
