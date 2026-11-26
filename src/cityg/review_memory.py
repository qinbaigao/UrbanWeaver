"""Versioned observation evidence and conservative bounded-review outcomes."""
import hashlib
import json
from pathlib import Path

from cityg.memory import MemoryRecord
from cityg.visual_evidence import render_evidence_ready


def record_observations(store, city, plan, image_dir, *, stage):
    image_dir = Path(image_dir)
    status_file = image_dir/'asset_load_status.json'
    statuses = json.loads(status_file.read_text()).get('views', {}) if status_file.is_file() else {}
    nodes = {n.entity_id:n for n in city.world_program.nodes}
    rows = []
    for view in plan.get('selected_views', []):
        path = image_dir/(view['view_id']+'.png')
        renderer = statuses.get(view['view_id'], {})
        targets = view.get('target_entity_ids', []) or [city.id]
        ready = (path.is_file() and render_evidence_ready(renderer)
                 and all(key in nodes for key in targets))
        content = {'view_id':view['view_id'], 'stage':stage, 'image':str(path.resolve()),
            'image_sha256':hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None,
            'camera':{k:view.get(k) for k in ('mode','kind','camera_position','look_at','auto_cutaway')},
            'viewer_applied_state':renderer.get('view_status'),
            'dependency_entity_ids':list(targets),
            'entity_versions':{key:nodes[key].version for key in targets if key in nodes},
            'renderer_status':renderer, 'ready':ready}
        token = hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()[:24]
        memory_id = 'view__'+token
        if store.get(memory_id) is None:
            store.put(MemoryRecord(memory_id, 'visual_evidence', 'entity', targets[0], content,
                world_version=nodes[targets[0]].version if targets[0] in nodes else None,
                producer='adaptive_review', validation_status='accepted' if ready else 'rejected'))
        rows.append({'memory_id':memory_id, 'view_id':view['view_id'], 'ready':ready})
    return rows


def bounded_review_outcome(before, after, after_plan, traces, *, current_versions=None, deterministic_checks=None):
    """Different observation coverage is never turned into a repair percentage."""
    def key(issue): return str(issue.get('entity_id')), str(issue.get('category'))
    later = {key(i) for i in after.get('aggregated_issues', [])}
    covered = {str(entity) for view in after_plan.get('selected_views', [])
               for entity in view.get('target_entity_ids', [])}
    complete = all(r.get('batch_count', 0)>0 and r.get('available_batches') == r.get('batch_count')
                   for r in (before, after))
    rows = []
    from cityg.issue_rechecks import issue_key
    queued={r['issue_key']:r for r in after_plan.get('issue_recheck_queue',[])}
    exact_later={issue_key(r) for r in after.get('aggregated_issues',[])}
    committed = set()
    for stage in ('room', 'room_layout'):
        for trace in traces.get(stage, []):
            records = [trace.get('transaction') or {}]
            negotiation = trace.get('negotiation', {})
            if negotiation.get('status') == 'resolved':
                records.extend(a.get('transaction', {}) for a in negotiation.get('attempts', []))
            if any(t.get('status') == 'accepted' for t in records):
                committed.update((trace.get('room_id'), k) for k in trace.get('repair_issue_keys', []))
    for issue in before.get('aggregated_issues', []):
        entity, category = key(issue)
        status = ('review_unavailable' if not complete else 'observed_again' if key(issue) in later
                  else 'not_rechecked' if entity not in covered else 'not_observed_in_recheck')
        row={'entity_id':entity, 'category':category, 'status':status,'verified_resolved':False}
        token=issue_key(issue)
        version = (current_versions or {}).get(entity)
        proof = (deterministic_checks or {}).get(token, {})
        structural = bool(version is not None and proof.get('ok') is True and proof.get('before_failed') is True
                          and proof.get('entity_id') == entity and proof.get('entity_version') == version
                          and proof.get('check_id') and proof.get('source') == 'deterministic_checker')
        row.update(issue_key=token, repair_committed=(entity, token) in committed,
                   structural_resolution_verified=structural, visual_absence_confirmed=False)
        if structural:
            row['deterministic_check'] = proof
        if token in queued:
            task=queued[token]
            evidence=[r for r in after.get('issue_followups',[]) if r.get('issue_key')==token]
            comparable_rows = [r for r in evidence if r.get('comparable_loaded_evidence') is True]
            comparable = bool(comparable_rows)
            current = bool(evidence) and version is not None and all(
                r.get('expected_entity_version') == version for r in evidence)
            row.update(issue_key=token,queue_status=task['status'],explicit_followups=evidence,
                       comparable_loaded_evidence=comparable,current_version_verified=current)
            # Entity/category alone is not issue identity. A different chair
            # problem must not be reported as the old door blockage recurring.
            related=[r for r in after.get('aggregated_issues',[]) if key(r)==key(issue)
                     and r.get('issue_code')==issue.get('issue_code')
                     and r.get('issue_code') not in (None,'unspecified')]
            if not complete: row['status']='review_unavailable'
            elif not evidence: row['status']='not_rechecked'
            elif not current: row['status']='stale_or_unverified_evidence'
            elif not comparable: row['status']='noncomparable_or_unready_evidence'
            elif any(r['verdict']=='present' for r in evidence):
                row['status']=('contradictory_evidence' if any(r['verdict']=='not_observed' for r in evidence)
                               else 'observed_again')
            elif token in exact_later:
                row['status']=('contradictory_evidence' if any(r['verdict']=='not_observed' for r in evidence)
                               else 'observed_again')
            elif related:
                row['status']='related_issue_requires_disambiguation'
                row['related_issues']=related
            elif any(r['verdict']=='not_observed' and r['confidence']>=.85
                     and r.get('target_visibility')=='clear' for r in comparable_rows):
                row['visual_absence_confirmed'] = True
                if not structural:
                    row['status'] = 'visual_absence_requires_independent_check'
                elif not row['repair_committed']:
                    row['status'] = 'no_accepted_issue_repair'
                else:
                    row.update(status='verified_resolved', verified_resolved=True)
            else: row['status']='inconclusive'
        rows.append(row)
    failures = [{'agent':kind, 'entity_id':row.get('room_id', row.get('building_id', row.get('road_id'))),
                 'reason':row['error']} for kind, records in traces.items()
                for row in records if isinstance(row, dict) and row.get('error')]
    pending = after.get('aggregated_issues', [])
    return {'status':'review_incomplete' if not complete else 'bounded_review_finished',
        'stop_reason': 'review_service_unavailable' if not complete else 'configured_repair_passes_exhausted',
        'issue_followup':rows, 'remaining_observed_issues':pending, 'rejected_or_deferred_proposals':failures,
        'unreviewed_issue_count':sum(r['status']=='not_rechecked' for r in rows),
        'explicit_rechecked_issue_count':sum(bool(r.get('explicit_followups')) for r in rows),
        'comparable_rechecked_issue_count':sum(bool(r.get('comparable_loaded_evidence')) for r in rows),
        'original_issue_count':len(rows),
        'accepted_issue_repair_count':sum(r['repair_committed'] for r in rows),
        'structurally_resolved_issue_count':sum(r['structural_resolution_verified'] for r in rows),
        'visual_absence_confirmed_issue_count':sum(r['visual_absence_confirmed'] for r in rows),
        'verified_resolved_issue_count':sum(r['verified_resolved'] for r in rows),
        'automatic_retry_allowed':False, 'repair_rate_computed':False,
        'note':'Absence in a different set of views is not verified resolution. No unbounded retries.'}
