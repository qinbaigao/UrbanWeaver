// Extra, textured vegetation tiers for aerial cities. Source assets never change.
// Usage: node viewer/tools/prepare_city_vegetation_lods.mjs PORTABLE_VIEWER CACHE_DIR
import fs from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {NodeIO, getBounds} from '@gltf-transform/core';
import {ALL_EXTENSIONS} from '@gltf-transform/extensions';
import {simplify, weld} from '@gltf-transform/functions';
import {MeshoptSimplifier, MeshoptDecoder} from 'meshoptimizer';

const [viewer, cache] = process.argv.slice(2);
if (!viewer || !cache) throw Error('Expected PORTABLE_VIEWER CACHE_DIR');
const config=JSON.parse(await fs.readFile(path.join(viewer,'viewer-config.json')));
await fs.mkdir(cache,{recursive:true});
const file=path.join(cache,'manifest.json');
let manifest;
try { manifest=JSON.parse(await fs.readFile(file)); }
catch(e) { if(e.code!=='ENOENT')throw e; manifest={version:1,assets:{}}; }
const io=new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({'meshopt.decoder':MeshoptDecoder});
const hash=b=>createHash('sha256').update(b).digest('hex');
const triangles=d=>d.getRoot().listMeshes().reduce((n,m)=>n+m.listPrimitives().reduce((s,p)=>
  s+(p.getIndices()?.getCount() || p.getAttribute('POSITION')?.getCount() || 0)/3,0),0);
const textures=d=>d.getRoot().listTextures().map(t=>hash(t.getImage())).sort();
// Prune permits removing subpixel disconnected leaf components, which ordinary
// edge collapse cannot eliminate. UVs, normals, original images and materials
// remain on the surviving mesh. Restrict to vegetation and small projected sizes.
const pruning={...MeshoptSimplifier,simplify:(a,b,c,d,e,f)=>MeshoptSimplifier.simplify(a,b,c,d,e,[...f,'Prune'])};
const vegetation=id=>/(^|_)(tree|sapling|searsia|flower|periwinkle|fern|palm|hedge|quiver)(_|[0-9]|$)/i.test(id);
// Reconcile the initial broad matcher: "street" must not match "tree".
for(const [id,record] of Object.entries(manifest.assets)) {
  if(record.city_vegetation_lod_version===1 && !vegetation(id)) {
    record.variants=record.variants.filter(v=>!/__viewer_(city|compact)_v1_/.test(v.asset_id))
      .map(v=>({...v,max_pixels:v.max_pixels===96?48:v.max_pixels}));
    delete record.city_vegetation_lod_version;
  }
}
await fs.writeFile(file+'.tmp',JSON.stringify(manifest,null,2)+'\n');await fs.rename(file+'.tmp',file);
for (const [id,filename] of Object.entries(config.asset_files || {})) {
  if (id.includes('__viewer_') || !vegetation(id)) continue;
  const originalBytes=await fs.readFile(path.join(viewer,config.asset_base,filename));
  const sha=hash(originalBytes), old=manifest.assets[id];
  if (old?.source_sha256===sha && old.city_vegetation_lod_version===1) continue;
  const original=await io.readBinary(originalBytes), originalCount=triangles(original);
  if (originalCount<20000 || original.getRoot().listSkins().length || original.getRoot().listAnimations().length
    || original.getRoot().listMeshes().some(m=>m.listPrimitives().some(p=>p.listTargets().length))) continue;
  const textureHashes=textures(original), bounds=getBounds(original.getRoot().listScenes()[0]);
  // Start with a validated existing derivative to avoid repeatedly processing
  // millions of original leaf vertices. Preserve its accumulated error in the report.
  const record=old?.source_sha256===sha ? old : {source_sha256:sha,original_triangles:originalCount,variants:[]};
  const prior=[...record.variants].filter(v=>v.relative_error_limit<=.01).sort((a,b)=>a.triangles-b.triangles)[0];
  let input=originalBytes, inputCount=originalCount;
  if(prior) {
    const candidate=await fs.readFile(path.join(cache,prior.file));
    if(hash(candidate)!==prior.sha256)throw Error(`Corrupt prior LOD ${id}`);
    input=candidate; inputCount=prior.triangles;
  }
  const variants=[];
  for(const level of [{name:'city',max_pixels:24,budget:2000,error:.06},
                      {name:'compact',max_pixels:48,budget:8000,error:.025}]) {
    const d=await io.readBinary(input);
    await d.transform(weld(),simplify({simplifier:pruning,ratio:Math.min(.5,level.budget/inputCount),error:level.error}));
    const count=triangles(d), actual=getBounds(d.getRoot().listScenes()[0]);
    const retainedExtent=actual.min.map((v,i)=>(actual.max[i]-v)/(bounds.max[i]-bounds.min[i]));
    if(count<24 || count>=inputCount*.8 || retainedExtent.some(v=>!Number.isFinite(v)||v<.75||v>1.05)) {
      console.log(JSON.stringify({id,level:level.name,skipped:true,triangles:count,retainedExtent}));continue;
    }
    const data=await io.writeBinary(d), checked=await io.readBinary(data);
    if(JSON.stringify(textures(checked))!==JSON.stringify(textureHashes))throw Error(`Texture loss: ${id}`);
    const asset_id=`${id}__viewer_${level.name}_v1_${sha.slice(0,12)}`, name=`${asset_id}.glb`;
    await fs.writeFile(path.join(cache,name),data,{flag:'wx'}).catch(async e=>{
      if(e.code!=='EEXIST'||hash(await fs.readFile(path.join(cache,name)))!==hash(data))throw e;
    });
    variants.push({asset_id,file:name,max_pixels:level.max_pixels,triangles:count,
      relative_error_limit:level.error+(prior?.relative_error_limit || 0),sha256:hash(data),
      disconnected_component_pruning:true,retained_extent:retainedExtent});
    console.log(JSON.stringify({id,level:level.name,original_triangles:originalCount,triangles:count,retainedExtent}));
  }
  if(!variants.length)continue;
  // Keep the former far mesh as an intermediate rather than deleting it.
  record.variants=record.variants.map(v=>({...v,max_pixels:v.max_pixels===48?96:v.max_pixels})).concat(variants);
  record.city_vegetation_lod_version=1; manifest.assets[id]=record;
  await fs.writeFile(file+'.tmp',JSON.stringify(manifest,null,2)+'\n');await fs.rename(file+'.tmp',file);
}
