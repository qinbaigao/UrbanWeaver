"""Issue-specific observation queue with explicit comparable-view provenance."""
from copy import deepcopy
import hashlib
import json

from cityg.transactions import ancestors, descendants

CAMERA_FIELDS=('camera_position','look_at','up','fov_deg','mode','appearance','auto_cutaway')


def issue_key(issue):
    # Model-local issue_001 identifiers collide across batches; preserve both
    # the original label and a stable content/entity key in the queue.
    values={k:issue.get(k) for k in ('entity_id','category','issue_code','description')}
    for field in ('target_object_ids', 'target_group_ids'):
        if issue.get(field):
            values[field] = sorted(set(issue[field]))
    return 'issue_'+hashlib.sha256(json.dumps(values,sort_keys=True).encode()).hexdigest()[:24]


def plan_issue_rechecks(city, before_plan, review, after_plan, *, max_views, touched=()):
    if type(max_views) is not int or max_views<1: raise ValueError('Recheck view budget must be positive')
    original={v['view_id']:v for v in before_plan.get('selected_views',[])}
    fresh={v['view_id']:v for v in [*after_plan.get('candidates',[]),*after_plan.get('selected_views',[])]}
    nodes={n.entity_id:n for n in city.world_program.nodes}
    affected=descendants(city,touched)|ancestors(city,touched) if touched else set()
    issues=sorted(review.get('aggregated_issues',[]),key=lambda i:(
        i.get('entity_id') not in affected, {'error':0,'warning':1,'info':2}.get(i.get('severity'),3),
        -float(i.get('confidence',0)),issue_key(i)))
    rows=[]; views={}
    for issue in issues:
        key=issue_key(issue); target=issue.get('entity_id')
        row={'issue_key':key,'original_issue_id':issue.get('issue_id'),'entity_id':target,
            'category':issue.get('category'),'issue_code':issue.get('issue_code'),
            'target_group_ids':list(issue.get('target_group_ids',[])),
            'target_object_ids':list(issue.get('target_object_ids',[])),
            'description':issue.get('description'),'source_view_ids':list(issue.get('evidence_view_ids',[])),
            'expected_entity_version':nodes[target].version if target in nodes else None,
            'candidates':[], 'assigned_view_ids':[], 'verified_resolved':False}
        if target not in nodes:
            row['status']='target_unavailable';rows.append(row);continue
        for vid in row['source_view_ids']:
            old=original.get(vid); new=fresh.get(vid)
            if old is None or new is None or target not in new.get('target_entity_ids',[]): continue
            comparable=all(old.get(k)==new.get(k) for k in CAMERA_FIELDS)
            views[vid]=deepcopy(new)
            row['candidates'].append({'view_id':vid,'source_view_id':vid,
                'source_capture_signature':review.get('capture_signatures',{}).get(vid),
                'comparable_camera':comparable,'relation':'same_camera' if comparable else 'recomputed_camera'})
        if not row['candidates']:
            replacements=sorted((v for v in fresh.values() if target in v.get('target_entity_ids',[])),
                                key=lambda v:(v.get('kind')=='global',v['view_id']))
            if replacements:
                new=replacements[0];views[new['view_id']]=deepcopy(new)
                row['candidates'].append({'view_id':new['view_id'],'source_view_id':None,
                    'comparable_camera':False,'relation':'replacement_view'})
        # One complementary question-directed view, under the SAME total cap.
        # It supplements original evidence, never masquerades as a comparable
        # before/after camera or proof that the issue was resolved.
        code=issue.get('issue_code')
        wanted=('perspective' if code=='room_group_misaligned' else 'top'
                if code in {'room_access_blocked','room_object_outside','room_function_incomplete'} else None)
        if wanted and row['candidates']:
            used={c['view_id'] for c in row['candidates']}
            existing=[views[c['view_id']] for c in row['candidates']]
            alternatives=sorted((v for v in fresh.values() if
                target in v.get('target_entity_ids',[]) and v.get('mode')=='room'
                and v['view_id'] not in used
                and any(wanted in str(v.get(k,'')) for k in ('view_id','novelty_key'))
                and not any(all(v.get(k)==old.get(k) for k in CAMERA_FIELDS) for old in existing)),
                key=lambda v:v['view_id'])
            if alternatives:
                view=alternatives[0];views[view['view_id']]=deepcopy(view)
                row['candidates'].append({'view_id':view['view_id'],'source_view_id':None,
                    'comparable_camera':False,'relation':'question_directed_supplement',
                    'question':code})
        row['status']='pending' if row['candidates'] else 'view_unavailable'
        rows.append(row)
    selected={}
    # One view per issue before supplementary angles; shared views cost once.
    for slot in range(max((len(r['candidates']) for r in rows),default=0)):
        for row in rows:
            if slot>=len(row['candidates']): continue
            vid=row['candidates'][slot]['view_id']
            if vid in selected or len(selected)<max_views:
                selected[vid]=views[vid]
                if vid not in row['assigned_view_ids']: row['assigned_view_ids'].append(vid)
    for row in rows:
        if row['status']=='pending': row['status']='queued' if row['assigned_view_ids'] else 'view_budget_exhausted'
    for view in after_plan.get('selected_views',[]):
        if len(selected)>=max_views: break
        selected.setdefault(view['view_id'],deepcopy(view))
    result=deepcopy(after_plan)
    result.update(selected_views=list(selected.values()),max_views=max_views,issue_recheck_queue=rows,
        recheck_policy='modified_issues_then_original_evidence_then_question_directed_context',
        issue_recheck_summary={'issues':len(rows),'queued':sum(r['status']=='queued' for r in rows),
                              'uncovered':sum(r['status']!='queued' for r in rows),
                              'resolution_proven_by_queue':False})
    return result
