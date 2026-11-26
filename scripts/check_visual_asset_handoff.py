"""VLM-suggested asset inspection, deterministic provenance check, local rebuild.

Only experiment-local registries may be changed. VLM descriptions never select
an arbitrary replacement asset: the accepted original registry is authoritative.
"""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path

from cityg.assets import AssetRegistry
from cityg.serialization import load_city,save_json
from cityg.adaptive_review import _render_plan,_start_server
from run_visual_input_ablation import target


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--fixtures',type=Path,required=True)
    p.add_argument('--reviews',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    original=AssetRegistry('assets/asset_registry.json');reports=[]
    for case in ['case_01','case_02']:
        fixture=args.fixtures/case;city=load_city(fixture/'scene/city.json');b,f,r=target(city)
        objects={o.id:o for o in f.objects if o.room_id==r.id}
        reviews=[json.loads(path.read_text()) for path in (args.reviews/case).glob('seed_*/result.json')]
        requested={oid for review in reviews for issue in review.get('issues',[])
                   if issue['kind']=='appearance' for oid in issue['object_ids'] if oid in objects}
        local=AssetRegistry(fixture/'scene/assets/asset_registry.json');checks=[];fixes=[]
        for oid in sorted(requested):
            asset_id=objects[oid].asset_id;expected=original.get(asset_id);actual=local.get(asset_id)
            correct=original.resolve_path(expected.geometry_path).resolve()
            current=local.resolve_path(actual.geometry_path).resolve()
            expected_sha=hashlib.sha256(correct.read_bytes()).hexdigest()
            current_sha=hashlib.sha256(current.read_bytes()).hexdigest()
            checks.append({'object_id':oid,'asset_id':asset_id,'expected_sha256':expected_sha,
                'actual_sha256':current_sha,'same_payload':expected_sha==current_sha})
            if expected_sha!=current_sha:fixes.append((asset_id,str(correct)))
        report={'case':case,'requested_object_ids':sorted(requested),'checks':checks,
                'repair_count':len(fixes),'basis':'VLM candidate IDs followed by accepted-registry payload hashes'}
        if fixes:
            root=args.output/case
            for name in ('city.json','geometry_manifest.json','navigation.json','interactions.json','activation_manifest.json'):
                save_json(json.loads((fixture/'scene'/name).read_text()),root/'scene'/name)
            registry=json.loads((fixture/'scene/assets/asset_registry.json').read_text())
            rows=registry if isinstance(registry,list) else registry['assets']
            for aid,path in fixes:next(row for row in rows if row['asset_id']==aid)['geometry_path']=path
            save_json(registry,root/'scene/assets/asset_registry.json')
            plan=json.loads((fixture/'render_plan.json').read_text())
            server,thread,url=_start_server(root/'scene',0)
            try:asyncio.run(_render_plan(url,plan,root/'images',asset_timeout_ms=180000))
            finally:server.shutdown();server.server_close();thread.join(timeout=10)
            final=AssetRegistry(root/'scene/assets/asset_registry.json')
            report['repaired_hashes_match']=all(hashlib.sha256(final.resolve_path(final.get(aid).geometry_path).read_bytes()).hexdigest()
                ==hashlib.sha256(Path(path).read_bytes()).hexdigest() for aid,path in fixes)
            report['canonical_city_unchanged']=(root/'scene/city.json').read_bytes()==(fixture/'scene/city.json').read_bytes()
        reports.append(report)
    save_json(reports,args.output/'results.json')
    print(json.dumps(reports,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
