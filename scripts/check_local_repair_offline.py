"""Exercise real local repair transactions with injected defects.

Default: authored candidates. --base-url opts into real model patch proposals.
Neither mode is a VLM detection test or a natural-defect success rate.
"""
import argparse
import json
from pathlib import Path

from cityg.assets import AssetRegistry, AssetResolver, MaterialLibrary
from cityg.ccwp import build_world_program
from cityg.geometry import GeometryCompiler
from cityg.planning.prototypes import LayoutPrototypeLibrary, reference_registry
from cityg.planning.prototype_lab import make_lab, populate_reference, detached_registry
from cityg.planning.prototype_decor_assets import add_review_decorations
from cityg.refinement.room import RoomProgramAgent
from cityg.refinement.room_preflight import prepare_preflight
from cityg.refinement.room_commit import commit_room_program
from cityg.validation.visual_grounding import ground_review, resolution_proofs
from cityg.serialization import save_json
from cityg.schemas import Point2D, Bounds2D
from cityg.transactions import fingerprint


class AuthoredCandidateService:
    def __init__(self, response): self.response=response; self.calls=0
    def complete(self, messages, response_schema=None):
        self.calls+=1
        return json.dumps(self.response)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--base-url',help='Use real model proposals instead of authored candidates')
    parser.add_argument('--model',default='cityg-llm')
    parser.add_argument('--max-attempts',type=int,default=3)
    args=parser.parse_args()
    if args.output.exists():parser.error('Use a new evidence filename')
    root=Path('configs/layout_prototypes/v1');library=LayoutPrototypeLibrary(root)
    registry=detached_registry(AssetRegistry('assets/asset_registry.json'))
    for path in sorted(root.glob('reference_assets_*.json')):
        add_review_decorations(registry,path,project_root=Path.cwd(),
            asset_ids=set(library.materialize('office_focus_compact_v1').asset_bindings.values()))
    report={'provenance':('real_model_patch_controlled_defect_not_vlm_detection' if args.base_url
                         else 'assistant_authored_patch_controlled_defect_not_vlm_detection'),
            'endpoint':args.base_url,'model':args.model if args.base_url else None,
            'model_calls':0,'cases':[]}
    for rotation in (0,27):
        row={'building_rotation_deg':rotation,'defect':'storage_translated_outside_room','ok':False}
        service=None
        try:
            city,targets=make_lab(library,['office_focus_compact_v1'])
            key,b,f,r=targets[0]
            b.metadata['orientation_deg']=rotation
            if rotation:
                # Rotated massing is inscribed in its parcel; enlarge the test
                # shell, not furniture, to retain a viable metric office.
                center=b.footprint.center
                def point(p):return Point2D(center.x+(p.x-center.x)*2.2,center.y+(p.y-center.y)*2.2)
                def bounds(bb):
                    lo=point(Point2D(bb.min_x,bb.min_y));hi=point(Point2D(bb.max_x,bb.max_y))
                    return Bounds2D(lo.x,lo.y,hi.x,hi.y)
                b.footprint=bounds(b.footprint);b.entrance=point(b.entrance)
                for rr in f.rooms:rr.bounds=bounds(rr.bounds)
                for door in f.doors:door.position=point(door.position);door.width_m*=2.2
                def union(a,bb):return Bounds2D(min(a.min_x,bb.min_x),min(a.min_y,bb.min_y),
                                               max(a.max_x,bb.max_x),max(a.max_y,bb.max_y))
                parcel=city.districts[0].parcels[0]
                parcel.bounds=union(parcel.bounds,b.footprint.inset(-.2))
                city.districts[0].bounds=union(city.districts[0].bounds,parcel.bounds)
                city.bounds=union(city.bounds,city.districts[0].bounds)
            populate_reference(city,targets[0],library,registry)
            # Move the physical metric pose and its canonical representation
            # together: the defect must reach the compiler, not be stale metadata.
            for obj in f.objects:
                if obj.room_id!=r.id or obj.metadata.get('group_key')!='storage':continue
                pose=obj.metadata['metric_room_placement'];sx=pose['canonical_scale'][0]
                obj.position=Point2D(obj.position.x-10/sx,obj.position.y)
                pose['center'][0]-=10
                pose['canonical_binding'][0]=obj.position.x
            city.world_program=build_world_program(city,producer='controlled_defect',seed=17)
            original=fingerprint(city)
            issue={'entity_id':r.id,'category':'room','issue_code':'room_object_outside',
                'description':'Controlled storage group outside its physical room',
                'target_group_ids':['storage'],'confidence':1.,'binding_confidence':1.,
                'automatic_repair_allowed':True}
            review=ground_review(city,{'aggregated_issues':[issue]})
            row['before_verification']=review['aggregated_issues'][0]['independent_verification']
            patch={'room_id':r.id,'reason':'Restore original east-wall storage; keep work group fixed',
                'group_updates':[{'group_id':'storage','placement':{
                    'mode':'wall','wall':'east','contact':'back','max_gap_m':.2}}]}
            if args.base_url:
                from cityg.services.interfaces import ModelEndpoint
                from cityg.services.openai_compatible import OpenAICompatibleService
                from run_edit_method_pilot import RecordedService
                service=RecordedService(OpenAICompatibleService(ModelEndpoint(
                    base_url=args.base_url,model=args.model,timeout_s=180,max_tokens=4096,
                    seed=611,enable_thinking=False)),
                    args.output.parent/(args.output.stem+f'_rotation{rotation}_calls.json'))
            else:
                service=AuthoredCandidateService(patch)
            pinned=reference_registry(registry,library.materialize(key))
            resolver=AssetResolver(pinned,(),max_provider_calls=0)
            compiler=GeometryCompiler(asset_registry=registry,
                material_library=MaterialLibrary('assets/incoming/interior_materials/material_library.json'))
            support,preflight,gate=prepare_preflight(city,r.id,compiler,pinned,seed=17)
            result=RoomProgramAgent(service,asset_resolver=resolver,
                max_attempts=args.max_attempts if args.base_url else 1,
                review_sufficiency=False).propose(city,b,f,r,use_cache=False,
                visual_feedback={**issue,'compiled_support_context':support},compiled_preflight=preflight)
            committed,stats=commit_room_program(city,r.id,result.program,asset_resolver=resolver,
                seed=17,compiled_gate=gate,source='visual_repair')
            proofs=resolution_proofs(city,committed.city,review)
            old=[o for o in f.objects if o.metadata.get('group_key')=='work']
            new=[o for bb in committed.city.iter_buildings() for ff in bb.floors for o in ff.objects
                 if o.room_id==r.id and o.metadata.get('group_key')=='work']
            row.update(transaction=committed.report,proofs=proofs,unchanged_work_group=old==new,
                       source_unchanged=fingerprint(city)==original)
            row['ok']=(committed.report['status']=='accepted' and bool(proofs) and
                       all(p['ok'] for p in proofs.values()) and old==new and row['source_unchanged'])
        except Exception as error:
            row['error']=f'{type(error).__name__}: {error}'
            if getattr(error,'validation',None) is not None:
                row['validation_failure']=error.validation.to_dict()
        if args.base_url and service is not None:
            row['model_calls']=len(service.calls)
            row['usage']={k:sum(c.get('completion',{}).get('usage',{}).get(k,0)
                               for c in service.calls) for k in ('prompt_tokens','completion_tokens')}
            report['model_calls']+=row['model_calls']
        elif service is not None:
            row['authored_candidate_calls']=service.calls
        report['cases'].append(row);save_json(report,args.output)
        print(rotation,row['ok'],row.get('error',''),flush=True)
    report['ok']=all(c['ok'] for c in report['cases']);save_json(report,args.output)
    return 0 if report['ok'] else 1


if __name__=='__main__':raise SystemExit(main())
