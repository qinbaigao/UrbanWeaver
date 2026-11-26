"""Replay selected capture views, without an LLM, edits or asset substitution."""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path

from cityg.adaptive_review import _render_plan, _start_server
from cityg.run_provenance import record_stage_start
from cityg.serialization import save_json
from cityg.visual_evidence import render_evidence_ready


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run',type=Path)
    parser.add_argument('--phase',choices=('before','after'),default='before')
    parser.add_argument('--views',nargs='+',required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--package',type=Path,help='Optional fresh recompiled package; retain the original camera plan')
    parser.add_argument('--port',type=int,default=5517)
    args=parser.parse_args()
    if args.output.exists(): parser.error('Use a fresh output directory')
    review=args.run/'visual_review'
    plan=json.loads((review/f'observation_plan_{args.phase}.json').read_text())
    selected=[v for v in plan['selected_views'] if v['view_id'] in args.views]
    if {v['view_id'] for v in selected}!=set(args.views): parser.error('Unknown view ID')
    package=args.package or (args.run/'final/openusd' if args.phase=='before' else review/'openusd_after')
    source=package/'city.json';digest=hashlib.sha256(source.read_bytes()).hexdigest()
    record_stage_start(args.output)
    save_json({'selected_views':selected},args.output/'observation_plan.json')
    server,thread,url=_start_server(package,args.port)
    try:
        asyncio.run(_render_plan(url,{'selected_views':selected},args.output/'observations',asset_timeout_ms=180000))
    finally:
        server.shutdown();server.server_close();thread.join(timeout=5)
    states=json.loads((args.output/'observations/asset_load_status.json').read_text())['views']
    unchanged=hashlib.sha256(source.read_bytes()).hexdigest()==digest
    report={'mode':'read_only_capture_replay','source_unchanged':unchanged,'source_sha256':digest,
            'views':states,'ok':unchanged and all(render_evidence_ready(s) for s in states.values())}
    save_json(report,args.output/'report.json')
    print(json.dumps(report,ensure_ascii=False),flush=True)
    return 0 if report['ok'] else 3


if __name__=='__main__': raise SystemExit(main())
