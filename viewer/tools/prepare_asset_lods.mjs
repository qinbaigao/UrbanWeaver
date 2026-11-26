// Offline derivatives only. Canonical assets, collision shapes and IDs are unchanged.
// Usage: node viewer/tools/prepare_asset_lods.mjs PORTABLE_VIEWER CACHE_DIR [ASSET_ID...]
import fs from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {NodeIO} from '@gltf-transform/core';
import {ALL_EXTENSIONS} from '@gltf-transform/extensions';
import {simplify, weld} from '@gltf-transform/functions';
import {MeshoptSimplifier, MeshoptDecoder} from 'meshoptimizer';

const [viewer, output, ...only] = process.argv.slice(2);
if (!viewer || !output) throw Error('Expected PORTABLE_VIEWER CACHE_DIR [ASSET_ID...]');
const config = JSON.parse(await fs.readFile(path.join(viewer,'viewer-config.json')));
const derivativeIds = new Set(Object.values(config.asset_lods || {}).flat().map(v => v.asset_id));
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({'meshopt.decoder': MeshoptDecoder});
const hash = bytes => createHash('sha256').update(bytes).digest('hex');
const triangles = doc => doc.getRoot().listMeshes().reduce((sum,m) => sum+m.listPrimitives().reduce((n,p) =>
  n+(p.getMode() === 4 ? (p.getIndices()?.getCount() || p.getAttribute('POSITION')?.getCount() || 0)/3 : 0),0),0);
const textures = doc => doc.getRoot().listTextures().map(t => hash(t.getImage())).sort();
const levels = [{name:'mid', max_pixels:192, ratio:0.15, error:0.0025},
  {name:'far', max_pixels:48, ratio:0.03, error:0.01}];
await fs.mkdir(output,{recursive:true});
const manifestPath = path.join(output,'manifest.json');
let manifest;
try {manifest = JSON.parse(await fs.readFile(manifestPath));}
catch (e) {if(e.code !== 'ENOENT') throw e; manifest = {version:1, assets:{}};}
for (const [id,file] of Object.entries(config.asset_files || {})) {
  if (derivativeIds.has(id)) continue;
  if (only.length && !only.includes(id)) continue;
  const source = path.resolve(viewer,config.asset_base,file);
  const bytes = await fs.readFile(source);
  const sha256 = hash(bytes);
  if (manifest.assets[id]?.source_sha256 === sha256) continue;
  const original = await io.readBinary(bytes);
  const root = original.getRoot();
  if (root.listSkins().length || root.listAnimations().length || root.listMeshes().some(m => m.listPrimitives().some(p => p.listTargets().length))) continue;
  const count = triangles(original);
  // Repeated 1k-face facade modules also matter at city scale; do not restrict
  // LOD preparation to individually huge meshes such as trees.
  if (count < 1000) continue;
  const textureHashes = textures(original);
  const materials = root.listMaterials().length;
  const variants = [];
  for (const level of levels) {
    const doc = await io.readBinary(bytes);
    // Weld only identical vertex attributes; UV/normal seams are retained.
    await doc.transform(weld(), simplify({simplifier:MeshoptSimplifier,ratio:level.ratio,error:level.error}));
    const reduced = triangles(doc);
    if (reduced >= count*0.9) continue; // no misleading level that did not reduce geometry
    if (JSON.stringify(textures(doc)) !== JSON.stringify(textureHashes) || doc.getRoot().listMaterials().length !== materials)
      throw Error(`Material/texture loss: ${id}`);
    const asset_id = `${id}__viewer_${level.name}_${sha256.slice(0,12)}`;
    const filename = `${asset_id}.glb`;
    const data = await io.writeBinary(doc);
    // Round-trip validation, not just the in-memory document.
    const checked = await io.readBinary(data);
    if (JSON.stringify(textures(checked)) !== JSON.stringify(textureHashes)) throw Error(`Texture round-trip failed: ${id}`);
    await fs.writeFile(path.join(output, filename), data, {flag:'wx'}).catch(async e => {
      if(e.code !== 'EEXIST') throw e;
      if(hash(await fs.readFile(path.join(output,filename))) !== hash(data))
        throw Error(`Existing derivative differs; use a new cache directory: ${filename}`);
    });
    variants.push({asset_id,file:filename,max_pixels:level.max_pixels,triangles:reduced,
      relative_error_limit:level.error,sha256:hash(data)});
    console.log(JSON.stringify({id,level:level.name,original_triangles:count,triangles:reduced,materials,textures:textureHashes.length}));
  }
  manifest.assets[id] = {source_sha256:sha256,original_triangles:count,variants};
  await fs.writeFile(`${manifestPath}.tmp`, JSON.stringify(manifest,null,2)+'\n');
  await fs.rename(`${manifestPath}.tmp`,manifestPath);
}
