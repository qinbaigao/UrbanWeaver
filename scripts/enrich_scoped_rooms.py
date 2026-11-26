"""Bounded room enrichment replay. Offline by default; never starts a model.

Replay existing semantic designs through metric placement and support-aware
asset selection, or explicitly --use-llm for bounded semantic supplementation.
Per-room failures preserve the original room, and all outcomes are reported.
"""
import argparse
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path

from cityg.assets import AssetRegistry, AssetResolver, MaterialLibrary
from cityg.ccwp import build_world_program
from cityg.geometry import GeometryCompiler
from cityg.planning.interiors import FloorDetailAgent, FurnishingProgram
from cityg.planning.room_design import RoomDesign
from cityg.planning.room_envelope import metric_envelope, envelope_context
from cityg.refinement.room import RoomProgramAgent
from cityg.serialization import load_city, save_json
from cityg.services import OpenUSDBackend, OpenAICompatibleService
from cityg.services.interfaces import ModelEndpoint
from cityg.viewer import export_portable_viewer


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('scene',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--registry',type=Path,default=Path('assets/asset_registry.json'))
    parser.add_argument('--use-llm',action='store_true')
    parser.add_argument('--base-url',default='http://127.0.0.1:8000/v1')
    parser.add_argument('--model',default='cityg-llm')
    parser.add_argument('--max-rooms',type=int,default=10)
    args=parser.parse_args()
    if args.max_rooms<1: parser.error('max-rooms must be positive')
    if args.output.exists() and any(args.output.iterdir()): parser.error('Use a fresh output directory')
    args.output.mkdir(parents=True,exist_ok=True)
    city=load_city(args.scene/'city.json')
    registry=AssetRegistry(args.registry)
    resolver=AssetResolver(registry,(),max_provider_calls=0)
    agent=None
    if args.use_llm:
        service=OpenAICompatibleService(ModelEndpoint(args.base_url,args.model,timeout_s=240,max_tokens=8192,seed=17))
        agent=RoomProgramAgent(service,model_id=args.model,asset_resolver=resolver,max_attempts=4,placement_seed=17)
    traces=[]
    for b in city.iter_buildings():
        for f in b.floors:
            for r in f.rooms:
                if r.metadata.get('detail_tier')!='hero' or len(traces)>=args.max_rooms: continue
                trace={'room_id':r.id,'function':r.function,'before_count':len(r.object_ids)}
                traces.append(trace)
                print('room_start',r.id,flush=True)
                before=deepcopy(r.metadata)
                try:
                    envelope=metric_envelope(b,f,r)
                    trace['envelope']=envelope_context(envelope)
                    if envelope['status']!='supported': raise ValueError(envelope['reason'])
                    if agent:
                        proposal=agent.propose(city,b,f,r,use_cache=False)
                        program=proposal.program
                        save_json(proposal.raw,args.output/'programs'/f'{r.id}.json')
                        save_json([asdict(a) for a in proposal.attempts],args.output/'attempts'/f'{r.id}.json')
                    else:
                        old=r.metadata['room_design']
                        design=RoomDesign.from_dict({k:old[k] for k in RoomDesign.__dataclass_fields__ if k in old},FloorDetailAgent().catalog)
                        program=FurnishingProgram(r.id,r.function,old['style'],old['density'],(),design=design)
                    detail=FloorDetailAgent(asset_resolver=resolver,program_overrides={r.id:program})
                    stats=detail.populate_rooms(city,{r.id},seed=17)
                    if stats['furnishing_non_degradation_gate_rejected_room_count']:
                        r.metadata=before
                        raise ValueError('furnishing_non_degradation_gate_rejected')
                    actual_objects=[o for o in f.objects if o.room_id==r.id]
                    trace.update(status='accepted',after_count=len(r.object_ids),stats=stats,
                        metric_object_count=sum(bool(o.metadata.get('metric_room_placement')) for o in actual_objects))
                except (ValueError,RuntimeError,KeyError) as exc:
                    trace.update(status='preserved_needs_replanning',after_count=len(r.object_ids),error=str(exc))
                save_json({'mode':'llm' if agent else 'offline_replay','rooms':traces},args.output/'enrichment_report.json')
                save_json(city,args.output/'city_checkpoint.json')
                print('room_end',r.id,trace['status'],trace.get('error',''),flush=True)
    city.world_program=build_world_program(city,producer='bounded_room_enrichment',seed=17)
    compiler=GeometryCompiler(asset_registry=registry,material_library=MaterialLibrary('assets/material_library.json'),
        include_interiors=True,facade_asset_index_path='assets/facades/asset_annotations_reviewed.json')
    OpenUSDBackend(compiler).compile(city,args.output/'openusd')
    export_portable_viewer(args.output/'openusd',args.output/'viewer')
    geometry=json.loads((args.output/'openusd/geometry_manifest.json').read_text())
    summary=[]
    for t in traces:
        s=geometry['metadata'].get('room_surface_items',{}).get(t['room_id'],{})
        q=geometry['metadata'].get('room_furnishing_sufficiency',{}).get(t['room_id'],{})
        summary.append({**t,'surface_requested':s.get('requested',0),'surface_placed':s.get('placed',0),'sufficiency':q})
    save_json({'mode':'llm' if agent else 'offline_replay','rooms':summary,
               'major_count':sum(t['after_count'] for t in traces),
               'surface_count':sum(t['surface_placed'] for t in summary),
               'viewer':str((args.output/'viewer').resolve())},args.output/'enrichment_report.json')
    print('viewer',args.output/'viewer',flush=True)


if __name__=='__main__':main()
