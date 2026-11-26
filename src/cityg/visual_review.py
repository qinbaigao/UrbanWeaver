"""Optional VLM review gate for rendered CityG views.

Rendering is intentionally supplied by a backend (Viewer screenshots,
OpenUSD renderer, or an external headless browser).  The review layer only
parses typed issues and never lets a vision model mutate CCWP directly.
"""

from __future__ import annotations

import json
import re
import time
import math
from copy import deepcopy
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Sequence

from cityg.agents.requirement import _parse_json_object
from cityg.services.interfaces import ChatMessage, VisionReviewService


VISUAL_ISSUE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "issues": {
            "type": "array",
            "maxItems": 16,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "issue_id": {"type": "string"},
                    "severity": {"type": "string", "enum": ["info", "warning", "error"]},
                    "category": {"type": "string", "enum": ["layout", "building", "facade", "room", "road", "landscape", "population", "lighting", "unknown"]},
                    "issue_code": {
                        "type": "string",
                        "enum": [
                            "unspecified", "street_underfurnished", "street_overcrowded",
                            "frontage_disconnect", "cross_section_conflict",
                            "street_asset_repetition", "vegetation_overdensity",
                            "traffic_implausible", "road_intrusion",
                            "room_function_incomplete", "room_group_misaligned",
                            "room_access_blocked", "room_style_incoherent", "room_object_outside"
                        ],
                    },
                    "entity_id": {"type": ["string", "null"]},
                    "entity_type": {"type": "string", "enum": ["city", "road", "junction", "landscape_site", "building", "floor", "room", "unknown"]},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "binding_confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "binding_basis": {"type": "string", "enum": ["exact_view_target", "visible_label", "view_context", "inferred", "none"]},
                    "candidate_entity_ids": {"type": "array", "maxItems": 4, "items": {"type": "string"}},
                    "candidate_archetype_ids": {"type": "array", "maxItems": 4, "items": {"type": "string"}},
                    "target_group_ids": {"type":"array", "maxItems":8, "items":{"type":"string"}},
                    "target_object_ids": {"type":"array", "maxItems":16, "items":{"type":"string"}},
                    "description": {"type": "string", "maxLength": 600},
                    "suggested_action": {"type": "string", "maxLength": 400},
                    "asset_requests": {
                        "type": "array",
                        "maxItems": 4,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "category": {"type": "string"},
                                "count": {"type": "integer", "minimum": 1, "maximum": 4},
                                "description": {"type": "string", "maxLength": 400},
                            },
                            "required": ["category", "count", "description"],
                        },
                    },
                },
                "required": [
                    "issue_id", "severity", "category", "issue_code", "entity_id", "entity_type",
                    "confidence", "binding_confidence", "binding_basis",
                    "candidate_entity_ids", "description", "suggested_action", "target_group_ids",
                ],
            },
        },
        "summary": {"type": "string", "maxLength": 800},
    },
    "required": ["issues", "summary"],
}


@dataclass(frozen=True)
class VisualIssue:
    issue_id: str
    severity: str
    category: str
    entity_id: str | None
    description: str
    suggested_action: str
    issue_code: str = "unspecified"
    entity_type: str = "unknown"
    confidence: float = 0.0
    binding_confidence: float = 0.0
    binding_basis: str = "none"
    candidate_entity_ids: tuple[str, ...] = ()
    candidate_archetype_ids: tuple[str, ...] = ()
    asset_requests: tuple[dict[str, Any], ...] = ()
    target_group_ids: tuple[str, ...] = ()
    target_object_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class VisualReviewResult:
    available: bool
    summary: str = ""
    issues: tuple[VisualIssue, ...] = ()
    image_paths: tuple[str, ...] = ()
    error: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)
    deferred_issues: tuple[dict[str, Any], ...] = ()
    duplicate_issues_removed: int = 0
    attempts: tuple[dict[str, Any], ...] = ()
    retryable_response_error: bool = False
    issue_followups: tuple[dict[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "summary": self.summary,
            "issues": [
                {
                    **issue.__dict__,
                    "candidate_entity_ids": list(issue.candidate_entity_ids),
                    "candidate_archetype_ids": list(issue.candidate_archetype_ids),
                    "target_group_ids": list(issue.target_group_ids),
                    "target_object_ids": list(issue.target_object_ids),
                    "asset_requests": [dict(item) for item in issue.asset_requests],
                }
                for issue in self.issues
            ],
            "image_paths": list(self.image_paths),
            "error": self.error,
            "deferred_issues": list(self.deferred_issues),
            "duplicate_issues_removed": self.duplicate_issues_removed,
            "attempts": list(self.attempts),
            "model_calls": len(self.attempts),
            "issue_followups": list(self.issue_followups),
        }


class VisualReviewAgent:
    """Graceful VLM gate; unavailable vision must not fail city generation."""

    def __init__(self, service: VisionReviewService, *, max_images: int = 4, max_attempts: int = 2) -> None:
        if type(max_attempts) is not int or not 1<=max_attempts<=3:
            raise ValueError('Visual review max_attempts must be 1..3')
        self.service = service
        self.max_images = max(1, max_images)
        self.max_attempts = max_attempts

    def review(self, prompt, image_paths, *, context=None):
        attempts=[]; correction=''
        for _ in range(self.max_attempts):
            result=self._review_once(prompt+correction,image_paths,context=context)
            attempts.extend(result.attempts)
            if result.available or not result.retryable_response_error:
                return replace(result,attempts=tuple(attempts))
            from cityg.progress import progress
            progress('VLM 核对', '回复不完整或有矛盾；预算内同图重试，否则报告不可用', attempts=len(attempts))
            correction=('\nThe previous response was rejected: '+str(result.error)+
                '\nRe-examine the SAME images. Return a concise, complete JSON object; '
                'do not copy the previous malformed text. Summarize briefly and avoid repeated issues.')
        return replace(result,attempts=tuple(attempts))

    def _review_once(
        self,
        prompt: str,
        image_paths: Sequence[str | Path],
        *,
        context: dict[str, Any] | None = None,
    ) -> VisualReviewResult:
        selected = tuple(Path(path) for path in image_paths[: self.max_images])
        missing = [str(path) for path in selected if not path.is_file()]
        if missing:
            return VisualReviewResult(False, image_paths=tuple(str(path) for path in selected), error=f"missing image(s): {', '.join(missing)}")
        full_prompt = (
            prompt.rstrip()
            + "\nReturn only the JSON schema. Identify observable issues, do not invent hidden geometry.\n"
            + "Image evidence is target-local. Do not infer a room function from its appearance or from a prototype name. "
            "For adapted rooms, room_design.zones[].position and groups[].placement.wall/facing "
            "are authoritative over compass words in the free-text intent, which may describe the unrotated reference. "
            "Zone/group/member IDs are opaque identifiers: an ID such as 'west' or 'north_shelf' "
            "is NOT a placement direction. Do not diagnose a rotation mismatch from IDs or old prose alone. "
            "For room_group_misaligned, supply exact target_group_ids and identify the accepted "
            "wall/facing relation that visibly fails. Without this binding the claim cannot trigger repair. "
            "If furnishing_expected is false, an empty room is intentional. Shadows and triangulated shading are not walls. "
            "Floor-plan and room cutaways deliberately hide walls, facades, roofs and other floors: "
            "do not diagnose missing exterior walls or frontage discontinuity from such images. "
            "Single-view floor geometry concerns require a second unshadowed/orthogonal view before repair. "
            "Do not repeat the same issue.\n"
            + json.dumps({"context": context or {}}, ensure_ascii=False, sort_keys=True)
        )
        pending=(context or {}).get('pending_issue_checks',[])
        schema=deepcopy(VISUAL_ISSUE_SCHEMA)
        bindings=(context or {}).get('room_group_bindings',{})
        group_ids=sorted({g['group_id'] for groups in bindings.values() for g in groups})
        if group_ids:
            schema['properties']['issues']['items']['properties']['target_group_ids']['items']['enum']=group_ids
            full_prompt+=('\nroom_group_bindings is the authoritative per-room ID/placement table. '
                          'For alignment defects copy the affected group_id into target_group_ids, '
                          'compare accepted_placement, and do not infer a direction from group_id. '
                          'For object-local issues also bind affected groups and target_object_ids. '
                          'Reporting an affected group does not authorize modifying it. Never borrow IDs from another room.')
        if pending:
            entries=[]
            for check in pending:
                legal_views=sorted(set(check['assigned_view_ids']) & set((context or {}).get('view_ids',[])))
                if not legal_views:
                    raise ValueError('Pending issue has no assigned view in this batch')
                fields={'target_visibility':{'type':'string','enum':['clear','occluded','too_small','unknown']},
                    'issue_key':{'type':'string','const':check['issue_key']},
                    'verdict':{'type':'string','enum':['present','not_observed','uncertain']},
                    'confidence':{'type':'number','minimum':0,'maximum':1},
                    'reason':{'type':'string','maxLength':300},
                    'evidence_view_ids':{'type':'array','minItems':1,'maxItems':self.max_images,
                        'items':{'type':'string','enum':legal_views}}}
                entries.append({'type':'object','additionalProperties':False,'properties':fields,'required':list(fields)})
            schema['properties']['issue_followups']={'type':'array','minItems':len(entries),
                                                     'maxItems':len(entries),'prefixItems':entries}
            schema['required'].append('issue_followups')
            full_prompt+='\nExplicitly revisit EACH pending_issue_checks item in issue_followups. '
            full_prompt+=('Choose the verdict about the DEFECT, not about whether a repair was observed: '
                          'present = the defect is visible or still remains; '
                          'not_observed = the defect is not visible despite adequate evidence; '
                          'uncertain = the evidence cannot decide. '
                          'Report target_visibility for the bound object and its relevant clearance or interface. '
                          'Use clear only when their relationship is legible in the cited view. '
                          'For example, "the facade mismatch is confirmed and not repaired" means present, '
                          'never not_observed. A proxy-only or occluded view means uncertain, '
                          'not not_observed. not_observed is NOT proof of repair. If occluded, '
                          'too small or assets are not ready, choose uncertain. For EACH issue cite ONLY '
                          'its assigned_view_ids intersected with the current view_ids, not all batch images. '
                          'The issues array is for NEW observations, not a copy of pending_issue_checks. '
                          'Report each pending problem in issue_followups; do not both repeat it as an '
                          'observed issue and declare not_observed. Conflicting evidence is not a pass.')
        started=time.monotonic(); raw=''; usage={}; finish=None; received=False
        def attempt(error=None):
            return {'raw_output':raw,'usage':usage,'finish_reason':finish,
                    'elapsed_s':round(time.monotonic()-started,6),'error':error}
        try:
            method = getattr(self.service, "complete_with_metadata", None)
            if callable(method):
                completion = method(
                    [ChatMessage(role="user", content=full_prompt, image_paths=selected)],
                    schema,
                )
                raw = completion.content
                usage=getattr(completion,'usage',{}); finish=getattr(completion,'finish_reason',None)
            else:
                # Custom test services can implement the small VisionReviewService
                # protocol without knowing about structured output.
                raw = self.service.review(full_prompt, selected)
            received=True
            if finish=='length': raise ValueError('VLM response reached max_tokens; complete JSON required')
            data = _parse_json_object(raw)
            if not isinstance(data.get('issues'),list) or not isinstance(data.get('summary'),str):
                raise ValueError('VLM response requires issues array and summary string')
            followups=validate_issue_followups(data.get('issue_followups',[]),context or {})
            validate_review_bindings(data['issues'],bindings)
            validate_followup_consistency(data['issues'],followups,context or {})
            issues = tuple(
                VisualIssue(
                    issue_id=str(item["issue_id"]),
                    severity=str(item["severity"]),
                    category=str(item["category"]),
                    issue_code=str(item.get("issue_code", "unspecified")),
                    # Keep uniqueness local: some vLLM grammar backends reject
                    # JSON Schema's uniqueItems before even running the model.
                    target_group_ids=tuple(dict.fromkeys(str(g) for g in item.get("target_group_ids", [])))[:8],
                    target_object_ids=tuple(dict.fromkeys(str(g) for g in item.get("target_object_ids", [])))[:16],
                    entity_id=(str(item["entity_id"]) if item.get("entity_id") is not None else None),
                    entity_type=str(item.get("entity_type", "unknown")),
                    confidence=_confidence(item.get("confidence", 0.0)),
                    binding_confidence=_confidence(item.get("binding_confidence", 0.0)),
                    binding_basis=str(item.get("binding_basis", "none")),
                    candidate_entity_ids=tuple(
                        str(value) for value in item.get("candidate_entity_ids", []) if str(value)
                    ),
                    candidate_archetype_ids=tuple(
                        str(value)
                        for value in item.get("candidate_archetype_ids", [])
                        if str(value)
                    ),
                    description=str(item["description"]),
                    suggested_action=str(item["suggested_action"]),
                    asset_requests=tuple(
                        {
                            "category": str(request.get("category", "")),
                            "count": max(1, min(4, int(request.get("count", 1)))),
                            "description": str(request.get("description", "")),
                        }
                        for request in item.get("asset_requests", [])
                        if isinstance(request, dict) and request.get("category")
                    ),
                )
                for item in data.get("issues", [])
            )
            issues, deferred, duplicates = filter_review_issues(issues, context or {})
            return VisualReviewResult(
                True,
                summary=str(data.get("summary", "")),
                issues=issues,
                image_paths=tuple(str(path) for path in selected),
                raw=data,
                deferred_issues=tuple(deferred), duplicate_issues_removed=duplicates,
                attempts=(attempt(),),
                issue_followups=tuple(followups),
            )
        except Exception as exc:  # optional gate: never block the canonical pipeline
            return VisualReviewResult(
                False,
                image_paths=tuple(str(path) for path in selected),
                error=f"{type(exc).__name__}: {exc}",
                attempts=(attempt(f'{type(exc).__name__}: {exc}'),),
                retryable_response_error=received,
            )


def _confidence(value):
    # Missing evidence is unknown, not certain. Never clamp malformed model
    # output into a trustworthy score (notably NaN, booleans or values > 1).
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError('Confidence must be a finite number between 0 and 1')
    return float(value)


def validate_issue_followups(rows, context):
    expected={r['issue_key']:r for r in context.get('pending_issue_checks',[])}
    if not isinstance(rows,list) or len(rows)!=len(expected):
        raise ValueError('Every requested issue needs exactly one explicit followup')
    seen=set()
    for row in rows:
        fields = {'issue_key','verdict','confidence','reason','evidence_view_ids'}
        if not isinstance(row,dict) or set(row) not in (fields, fields | {'target_visibility'}):
            raise ValueError('Invalid issue followup fields')
        if row.get('target_visibility', 'unknown') not in ('clear','occluded','too_small','unknown'):
            raise ValueError('Invalid target visibility')
        key=row['issue_key']; confidence=row['confidence'];ids=row['evidence_view_ids']
        if key not in expected or key in seen: raise ValueError('Unknown or duplicate followup issue')
        seen.add(key)
        if (row['verdict'] not in {'present','not_observed','uncertain'} or not isinstance(row['reason'],str)
                or type(confidence) not in (int,float) or not math.isfinite(confidence) or not 0<=confidence<=1):
            raise ValueError('Invalid followup verdict/confidence')
        if (not isinstance(ids,list) or not ids or any(not isinstance(v,str) for v in ids)
                or not set(ids)<=set(expected[key]['assigned_view_ids']) & set(context.get('view_ids',[]))):
            raise ValueError('Followup evidence must target this issue in the current batch')
    return rows


def validate_review_bindings(issues, bindings):
    for issue in issues:
        groups=issue.get('target_group_ids',[])
        if not isinstance(groups,list) or any(not isinstance(g,str) for g in groups):
            raise ValueError('target_group_ids must be an array of exact group ID strings')
        if issue.get('issue_code')=='room_group_misaligned' and not groups:
            raise ValueError('room_group_misaligned requires exact target_group_ids from '
                             'room_group_bindings; otherwise omit the ungrounded diagnosis')
        if groups and bindings:
            known={g['group_id'] for g in bindings.get(issue.get('entity_id'),[])}
            if not set(groups)<=known:
                raise ValueError('Group binding is unknown for this room; use its exact group IDs')


def validate_followup_consistency(issues, followups, context):
    """Catch explicit contradictions, not a general natural-language judge.

    Never flip a verdict from prose. Retry with the same evidence; persistent
    inconsistency remains unavailable, not resolved. Geometric proof is still
    required downstream even for a consistent not_observed response.
    """
    pending={r['issue_key']:r for r in context.get('pending_issue_checks',[])}
    for row in followups:
        reason=row['reason'].strip().lower()
        asserted_present=bool(re.search(
            r'^(?:the |this )?(?:pending )?(?:issue|problem|defect)\b[^.!?]{0,180}?'
            r'\b(?:persists|is (?:still )?(?:present|confirmed)|still (?:exists|remains))\b'
            r'|^(?:该|此)?问题(?:仍然|依然|仍旧|仍)存在',reason))
        asserted_absent=bool(re.search(
            r'^(?:the |this )?(?:issue|problem|defect) (?:is (?:not observed|absent)|no longer (?:exists|persists))\b'
            r'|^(?:该|此)?问题(?:已不存在|未观察到|不存在)',reason))
        if ((row['verdict']=='not_observed' and asserted_present) or
                (row['verdict']=='present' and asserted_absent)):
            raise ValueError(f"Contradictory verdict/reason for {row['issue_key']}; "
                             'present means the defect remains, not_observed means not seen, '
                             'uncertain means evidence cannot decide. Reinspect the same images.')
        if row['verdict']!='not_observed': continue
        old=pending[row['issue_key']]
        for issue in issues:
            same_group=(old.get('target_group_ids') and
                        set(old['target_group_ids'])==set(issue.get('target_group_ids',[])) and
                        old.get('issue_code')==issue.get('issue_code'))
            if issue.get('entity_id')==old.get('entity_id') and (
                    issue.get('description')==old.get('description') or same_group):
                raise ValueError('A pending issue is simultaneously reported present and not_observed; '
                                 'if the defect remains, use verdict=present in issue_followups and '
                                 'remove it from the NEW issues array. If the view is insufficient, '
                                 'use uncertain. Reinspect the same images; do not infer repair success.')


def filter_review_issues(issues, context):
    """Quarantine unsupported bindings/scope, retain raw evidence for inspection.

    Compiled validation never vetoes a genuine visual issue. Single-view
    structural claims are deferred for more evidence, not declared false.
    """
    from cityg.visual_evidence import proxy_detail_issue
    allowed=set(context['allowed_entity_ids']) if 'allowed_entity_ids' in context else None
    expected=context.get('furnishing_expected_by_entity',{})
    single=set(context.get('single_view_floor_ids',[]))
    cutaway=set(context.get('cutaway_entity_ids',[]))
    unready=set(context.get('unready_entity_ids',[]))
    seen=set(); accepted=[]; deferred=[]; duplicates=0
    for issue in issues:
        key=(issue.entity_id,issue.category,issue.issue_code,re.sub(r'\s+','',issue.description).casefold())
        if key in seen:
            duplicates+=1; continue
        seen.add(key); reason=None
        if issue.entity_id and allowed is not None and issue.entity_id not in allowed:
            reason='entity_not_in_current_evidence'
        elif issue.entity_id in unready:
            reason='render_evidence_not_ready'
        elif proxy_detail_issue(issue,context):
            reason='proxy_overview_requires_local_detail_evidence'
        elif expected.get(issue.entity_id) is False and issue.issue_code=='room_function_incomplete':
            reason='furnishing_not_in_scope'
        elif issue.entity_id in cutaway and (issue.category=='facade' or issue.issue_code=='frontage_disconnect'):
            reason='cutaway_is_not_exterior_facade_evidence'
        elif issue.entity_id in single and issue.category in {'room','layout','building','facade'}:
            reason='single_view_floor_requires_corroboration'
        if reason:
            deferred.append({**issue.__dict__,'deferred_reason':reason,'automatic_repair_allowed':False})
        else:
            accepted.append(issue)
    return tuple(accepted),deferred,duplicates


__all__ = ["VISUAL_ISSUE_SCHEMA", "VisualIssue", "VisualReviewAgent", "VisualReviewResult"]
