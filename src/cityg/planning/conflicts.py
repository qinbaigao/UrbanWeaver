"""Structured upward reports; escalation is not permission to expand scope."""
import hashlib

from cityg.ccwp import expected_hierarchy


def planning_conflict(city, entity_id, *, code, reason, stage,
                      fallback_used=False, attempts_used=0, attempt_limit=0):
    hierarchy = expected_hierarchy(city)
    known = entity_id in hierarchy
    ancestor = hierarchy[entity_id][1] if known else None
    identity = f'{city.id}:{entity_id}:{stage}:{code}:{reason}'
    return {
        'schema_version': 'cityg.planning_conflict.v1',
        'conflict_id': 'conflict_'+hashlib.sha256(identity.encode()).hexdigest()[:20],
        'entity_id': entity_id, 'entity_binding_verified': known,
        'responsible_ancestor': ancestor, 'stage': stage, 'code': code,
        'reason': str(reason),
        'status': 'handled_by_validated_fallback' if fallback_used else 'deferred',
        'original_proposal_accepted': False,
        'budget': {'attempts_used': attempts_used, 'attempt_limit': attempt_limit,
                   'remaining': max(0, attempt_limit-attempts_used)},
        'options': [
            {'action': 'preserve_last_valid_state', 'automatic': True},
            {'action': 'replan_same_scope', 'automatic': False,
             'precondition': 'Explicit remaining budget and new constraint-compatible proposal'},
            {'action': 'change_parent_geometry_or_requirement', 'automatic': False,
             'requires_user_approval': True, 'target_id': ancestor},
        ],
        'automatic_scope_expansion': False, 'automatic_retry': False,
        'constraints_preserved': ['entrance', 'vertical_core', 'scope', 'inventory', 'physical_asset_scale'],
    }


def review_conflicts(city, traces):
    return [planning_conflict(city, row.get('room_id') or row.get('building_id') or row.get('road_id'),
        code='refinement_rejected', reason=row['error'], stage=kind,
        attempts_used=1, attempt_limit=1)
        for kind, rows in traces.items() for row in rows
        if isinstance(row, dict) and row.get('error')]
