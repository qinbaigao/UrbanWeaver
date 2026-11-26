import assert from 'node:assert/strict';
import {selectPrototypeCaptureAssets,outdoorCaptureCandidate} from './prototype_capture.js';
const items=Array.from({length:160},(_,i)=>({id:`p${i}`,center:{x:i*10,y:i%3*100},semantic_class:'tree',metadata:{resolved_asset:true,asset_id:'tree',asset_category:'tree'}}));
assert.equal(selectPrototypeCaptureAssets(items,{x:0,y:0},'global').size,64);
assert.deepEqual(selectPrototypeCaptureAssets(items,{x:0,y:0},'global'),selectPrototypeCaptureAssets([...items].reverse(),{x:0,y:0},'global'));
assert.equal(selectPrototypeCaptureAssets(items.slice(0,3),{x:0,y:0},'road').size,3);
assert.equal(outdoorCaptureCandidate({...items[0],metadata:{resolved_asset:true,asset_id:'facade_window'}}),false);
assert.equal(items.length,160);
