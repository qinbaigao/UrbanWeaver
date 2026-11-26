"""Read-only audit of fixed generation targets and an optional edit chain.

PYTHONPATH=src python scripts/verify_unified_acceptance.py RUN --output REPORT
This never calls an LLM, repairs a scene, lowers targets, or substitutes USD
structure validation for a separately supplied ovphysx runtime report.
"""
import argparse
import hashlib
import json
from pathlib import Path

from cityg.serialization import load_city, save_json
from cityg.transactions import descendants, snapshots
from cityg.validation import CityValidator


def read(path):
    return json.loads(Path(path).read_text())


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(run, *, buildings=10, rooms=10, edit_paths=(), physics_report=None, pipeline_exit_code=None):
    root = Path(run).resolve(); checks = []
    def check(name, ok, **details):
        checks.append({'name':name,'ok':bool(ok),**details})
    generation = read(root/'run.json')
    check('main_script_exit', pipeline_exit_code == 0, exit_code=pipeline_exit_code,
          note='Caller supplies the observed shell exit code; absent is unverified')
    source = load_city(root/'final/city.json')
    prototype = read(root/'programs/prototype_adaptation.json')
    check('generation_complete', generation['status']=='success', status=generation['status'])
    check('building_count', len(list(source.iter_buildings()))==buildings, expected=buildings)
    check('fine_room_target', prototype['summary']['accepted_rooms']==rooms,
          expected=rooms, actual=prototype['summary']['accepted_rooms'])
    checks_root = root/'final/openusd'
    for filename in ('geometry_validation_report.json','interaction_smoke_report.json','usd_validation_report.json'):
        check(filename, read(checks_root/filename).get('ok') is True)
    review_path = root/'visual_review/adaptive_review_report.json'
    check('visual_review_completed', review_path.is_file())
    review = read(review_path) if review_path.is_file() else {}
    if review:
        check('review_mesh_bindings', review['rendered_inventory_acceptance']['ok'])
        final = load_city(review['city_refined'])
        check('final_semantic_validation', CityValidator().validate(final).ok)
        fine_ids = {o.room_id for o in final.iter_objects()}
        check('final_fine_room_count', len(fine_ids)==rooms, actual=len(fine_ids), expected=rooms)
        check('review_all_batches_available', all(r.get('available_batches')==r.get('batch_count')
            and r.get('batch_count',0)>0 for r in (review['review'],review['review_after'])))
        if 'independent_issue_checks' in review:
            from cityg.validation.visual_grounding import resolution_proofs
            proofs=resolution_proofs(source,final,review['review'])
            check('independent_proofs_reproducible',proofs==review['independent_issue_checks'])
            for phase in ('review','review_after'):
                findings=review[phase].get('aggregated_issues',[])
                check('only_grounded_automatic_repairs_'+phase,all(
                    i.get('independent_verification',{}).get('status')=='confirmed'
                    for i in findings if i.get('automatic_repair_allowed')))
            for row in review.get('bounded_outcome',{}).get('issue_followup',[]):
                if row.get('verified_resolved'):
                    check('resolved_issue_has_independent_proof',
                        proofs.get(row['issue_key'],{}).get('ok') is True,issue_key=row['issue_key'])
        for phase in ('before', 'after'):
            observations = root/'visual_review'/('observations_'+phase)
            states = read(observations/'asset_load_status.json').get('views', {})
            plan = read(root/'visual_review'/('observation_plan_'+phase+'.json'))
            expected = {view['view_id'] for view in plan['selected_views']}
            ready = {key for key, state in states.items()
                if state.get('ready') is True and state.get('signal_available') is True
                and not state.get('timed_out') and not state.get('failed', 0)
                and not state.get('fallback', 0) and not state.get('pending', 0)
                and not state.get('material_textures_failed', 0)
                and not state.get('material_textures_pending', 0)
                and state.get('geometry_streaming', {}).get('ready') is True
                and not state.get('geometry_streaming', {}).get('failed', 0)
                and (observations/(key+'.png')).is_file()}
            check('captured_assets_ready_'+phase, bool(expected) and expected<=ready,
                  expected=len(expected), ready=len(expected & ready))
        check('portable_viewer', (root/'visual_review/viewer_after/serve.py').is_file())
    edits = []
    for folder in edit_paths:
        folder = Path(folder).resolve(); result = read(folder/'edit_result.json')
        reference = read(folder/'base_scene_ref.json'); request = read(folder/'edit_request.json')
        source_path = Path(reference['canonical_path'])
        unchanged = digest(source_path)==request['source_city_hash']
        check('edit_source_unchanged', unchanged, output=str(folder))
        row = {'output':str(folder),'status':result['status'],'source_unchanged':unchanged}
        if result['status']=='applied':
            before = load_city(source_path); after = load_city(folder/'final/city.json')
            left,right = snapshots(before),snapshots(after)
            changed = {table[k][0] for k in left.keys()|right.keys()
                if k.startswith('entity:') and left.get(k)!=right.get(k)
                for table in (left,right) if k in table}
            plan = read(folder/'edit_plan_effective.json')
            scope = [entity for target in plan['targets'] for entity in target['resolved_ids']]
            allowed = descendants(before,scope)|descendants(after,scope)
            check('edit_exact_scope', changed<=allowed, output=str(folder), outside=sorted(changed-allowed))
            row['changed_entity_ids'] = sorted(changed)
            check('edit_semantics', CityValidator().validate(after).ok, output=str(folder))
            check('edit_geometry', read(folder/'final/openusd/geometry_validation_report.json')['ok'], output=str(folder))
        elif result['status']=='needs_clarification':
            check('ambiguous_edit_zero_publication', not (folder/'final').exists()
                and not result.get('touched_entity_ids'), output=str(folder))
        edits.append(row)
    physics = read(physics_report) if physics_report else None
    if physics:
        check('actual_cpu_physics', physics.get('ok') is True and physics.get('cpu_only_forced') is True
              and physics.get('physics_steps',0)>0, tested_stage=physics.get('stage'))
    fingerprints = {str(path.relative_to(root)):digest(path) for path in
        (root/'run.json',root/'programs/prototype_adaptation.json',root/'final/city.json',
         root/'final/openusd/assets/asset_registry.json') if path.is_file()}
    return {'schema_version':1, 'ok':all(c['ok'] for c in checks), 'checks':checks,
        'fixed_targets':{'buildings':buildings,'fine_rooms':rooms}, 'edits':edits,
        'generation_cost':generation.get('metrics',{}), 'artifact_fingerprints':fingerprints,
        'visual_outcome':review.get('bounded_outcome'),
        'physics':physics, 'physics_runtime_tested':physics is not None,
        'claims':{'all_visual_issues_resolved':False, 'generalization_proven':False,
                  'all_roadmap_rounds_complete':False}}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run',type=Path); parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--buildings',type=int,default=10); parser.add_argument('--rooms',type=int,default=10)
    parser.add_argument('--edit',type=Path,action='append',default=[])
    parser.add_argument('--physics-report',type=Path)
    parser.add_argument('--pipeline-exit-code',type=int)
    args=parser.parse_args()
    report=audit(args.run, buildings=args.buildings,rooms=args.rooms,edit_paths=args.edit,
                 physics_report=args.physics_report, pipeline_exit_code=args.pipeline_exit_code)
    save_json(report,args.output)
    print(json.dumps({'ok':report['ok'],'report':str(args.output),
                      'failed_checks':[c for c in report['checks'] if not c['ok']]},ensure_ascii=False))
    return 0 if report['ok'] else 3


if __name__=='__main__': raise SystemExit(main())
