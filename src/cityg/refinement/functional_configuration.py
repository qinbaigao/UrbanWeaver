"""Bounded optional service-capacity improvement after hard inventory completion."""
from copy import deepcopy
from dataclasses import asdict

from cityg.agents import AgentGenerationError
from cityg.assets import AssetResolver
from cityg.interior_requirements import evaluate_requirements, requirements_for
from cityg.planning.functional_configuration import (
    PROFILES, options, propose_configuration, evaluate_configuration, target_inventory,
)
from cityg.progress import progress
from cityg.repair import PatchRejected
from cityg.refinement.room import RoomProgramAgent
from cityg.refinement.room_commit import commit_room_program, prepare_room_program
from cityg.refinement.room_preflight import prepare_preflight
from cityg.refinement.functional_completion import completion_certificates


def improve_functional_configuration(city, service, compiler, registry, *, config=None,
                                     target_levels=None, seed=17, memory_store=None, on_attempts=None):
    config = options(config)
    report = {'policy': 'functional_configuration_v1', 'options': config,
              'attempts': [], 'compiled_rooms': [], 'floor_feedback': [],
              'authority': 'advisory_targets_separate_from_user_requirements'}
    if not config['enabled'] or service is None: return city, report
    original = city; city = deepcopy(city)
    target_levels = (city.metadata.get('interior_scope', {}).get('building_levels', {})
                     if target_levels is None else target_levels)
    resolver = AssetResolver(registry, (), max_provider_calls=0)
    agent = RoomProgramAgent(service, asset_resolver=resolver,
                             max_attempts=config['placement_calls'], review_sufficiency=False,
                             placement_seed=seed)
    jobs = [(b.id, f.id, r.id) for b in city.iter_buildings() for f in b.floors
            if f.level in target_levels.get(b.id, []) for r in f.rooms
            if r.function in PROFILES and not any(r.metadata.get(k) for k in ('locked', 'protected'))]
    # Round-robin floors prevents one large building from consuming the budget.
    grouped = {}
    for job in jobs: grouped.setdefault(job[1], []).append(job)
    jobs = [grouped[k][i] for i in range(max(map(len, grouped.values()), default=0))
            for k in grouped if i < len(grouped[k])][:config['max_rooms']]
    for _, fid, rid in jobs:
        b, f, r = next((b, f, r) for b in city.iter_buildings() for f in b.floors for r in f.rooms if r.id == rid)
        row = {'room_id': rid, 'floor_id': fid, 'status': 'planning'}; report['attempts'].append(row)
        requirements = requirements_for(b, f.level)
        if any(q['status'] != 'satisfied' for q in evaluate_requirements(city, requirements)):
            row['status'] = 'skipped_hard_requirements_unmet'; continue
        progress('功能配置', '规划合理容量与辅助功能', room=rid, function=r.function)
        try:
            plan, traces = propose_configuration(service, b, f, r, resolver, max_calls=config['plan_calls'])
            row['planning_attempts'] = [asdict(t) for t in traces]
            if on_attempts: on_attempts(traces)
        except (ValueError, AgentGenerationError) as exc:
            traces = getattr(exc, 'attempts', ())
            row.update(status='planning_failed_previous_room_preserved', error=str(exc),
                       planning_attempts=[asdict(t) for t in traces])
            if on_attempts: on_attempts(traces)
            continue
        before = evaluate_configuration(r, f.objects, plan); row.update(plan=plan, before=before, after=before)
        if before['recommendation_met']:
            row['status'] = 'already_configured'
        else:
            compiled_gate = None
            def quality_gate(candidate):
                cr = next(q for q in candidate.iter_rooms() if q.id == rid)
                measured = evaluate_configuration(cr, list(candidate.iter_objects()), plan)
                incumbent = row['after']
                old_counts = {v['recipe']: min(v['complete_groups'], v['recommended']) for v in incumbent['bundles']}
                if any(min(v['complete_groups'], v['recommended']) < old_counts[v['recipe']] for v in measured['bundles']):
                    raise ValueError('Functional configuration would lose an existing complete activity group')
                old_seats = {v['recipe']: v['paired_seats'] for v in incumbent['bundles']}
                if any(v['paired_seats'] < old_seats[v['recipe']] for v in measured['bundles']):
                    raise ValueError('Functional configuration would lose existing usable paired seats')
                seat_gaps = {v['recipe']: v['seat_gap'] for v in incumbent['bundles']}
                if any(v['seat_gap'] > seat_gaps[v['recipe']] for v in measured['bundles']):
                    raise ValueError('Functional configuration would concentrate seats at fewer usable anchors')
                if measured['fulfilled_group_targets'] <= incumbent['fulfilled_group_targets']:
                    raise ValueError('No improvement in complete activity groups; revise grouping/placement or retain previous room')
                if any(q['status'] != 'satisfied' for q in evaluate_requirements(candidate, requirements)):
                    raise ValueError('Functional configuration violates original hard requirements')
                return measured
            try:
                context, preflight, compiled_gate = prepare_preflight(city, rid, compiler, registry, seed=seed)
                def preview(program):
                    candidate, _ = prepare_room_program(city, rid, program, asset_resolver=resolver, seed=seed)
                    quality_gate(candidate)
                    return preflight(program)
                result = agent.propose(city, b, f, r, use_cache=False, compiled_preflight=preview,
                    visual_feedback={'source': 'functional_configuration', 'functional_configuration': plan,
                        'recommended_inventory': target_inventory(plan),
                        'lower_design_inventory': target_inventory(plan, 'minimum'),
                        'before': before, 'compiled_context': context,
                        'instruction': 'Realize the recommended COMPLETE activity groups and supporting functions. '
                            'Recommendations are not new user minima; if fit fails reduce optional groups or soft '
                            'capacity with a reason, retaining original hard requirements and ALL existing furniture. '
                            'Use one group per activity anchor with its seats as face_anchor=true members. '
                            'Keep normal asset dimensions, all support items and decor; preserve circulation. '
                            'This stage configures major furniture only. Do not add NEW surface_items or decorations. '
                            'Copy existing surface_items with their support identities; if none exist use surface_items=[]. '
                            'Never satisfy seat capacity with detached chairs. No wall/floor/door changes. '
                            'First try recommended counts, then a lower justified soft target on bounded retry.'})
                row['placement_attempts'] = [asdict(t) for t in result.attempts]
                if on_attempts: on_attempts(result.attempts)
                def final_gate(candidate):
                    quality_gate(candidate)
                    return compiled_gate(candidate)
                committed, stats = commit_room_program(city, rid, result.program, asset_resolver=resolver,
                    seed=seed, source='generation', compiled_gate=final_gate, memory_store=memory_store)
                city = committed.city
                room = next(q for q in city.iter_rooms() if q.id == rid)
                row.update(status='accepted', after=evaluate_configuration(room, list(city.iter_objects()), plan),
                           placement=stats, transaction=committed.report, proposal=result.raw)
            except (ValueError, AgentGenerationError, PatchRejected) as exc:
                traces = getattr(exc, 'attempts', ())
                # Successful proposal accounting already occurred before a commit error.
                if traces and on_attempts: on_attempts(traces)
                row.update(status='not_improved_previous_room_preserved', error=str(exc))
                if traces: row['placement_attempts'] = [asdict(t) for t in traces]
            if not row['after']['recommendation_met'] and compiled_gate is not None and config['reference_attempts']:
                # A partial model improvement is an incumbent. Bind subsequent
                # proposals and their protection gates to that committed scene.
                if row['status'] == 'accepted':
                    row['agent_assessment'] = row['after']
                    b, f, r = next((b, f, r) for b in city.iter_buildings() for f in b.floors
                                   for r in f.rooms if r.id == rid)
                    compiled_gate = None
                from itertools import islice
                from cityg.planning.functional_configuration_references import configuration_references
                row['reference_attempts'] = []
                for reason, program in islice(configuration_references(r, f.objects, plan), config['reference_attempts']):
                    trial = {'strategy': reason}
                    row['reference_attempts'].append(trial)
                    try:
                        if compiled_gate is None:
                            from cityg.validation.local_room import room_compilation_gate
                            compiled_gate = room_compilation_gate(city, rid, compiler)
                        def reference_gate(candidate):
                            quality_gate(candidate)
                            return compiled_gate(candidate)
                        committed, stats = commit_room_program(city, rid, program, asset_resolver=resolver,
                            seed=seed, source='generation', compiled_gate=reference_gate, memory_store=memory_store)
                        city = committed.city
                        room = next(q for q in city.iter_rooms() if q.id == rid)
                        trial['status'] = 'accepted'
                        row.update(status='accepted', proposal_source='metric_configuration_fallback',
                            after=evaluate_configuration(room, list(city.iter_objects()), plan),
                            placement=stats, transaction=committed.report, proposal={'design': program.design.to_dict()})
                        break
                    except (ValueError, PatchRejected) as exc:
                        trial.update(status='rejected', error=str(exc))
        room = next(q for q in city.iter_rooms() if q.id == rid)
        room.metadata['functional_configuration'] = {'plan': plan, 'assessment': row['after'],
            'status': row['status'], 'compiled_change_verified': row['status'] == 'accepted'}
        if not row['after']['recommendation_met']:
            report['floor_feedback'].append({'floor_id': fid, 'room_id': rid,
                'code': 'recommended_functional_capacity_unrealized', 'authority': 'advisory',
                'missing_groups': [q for q in row['after']['bundles'] if q['gap'] or q['seat_gap']],
                'reason': row.get('error', 'Partial improvement; recommended configuration still not fully realized'),
                'not_a_proof_of_infeasibility': True,
                'action': 'Review room allocation at next authorized floor planning; no automatic furnished-wall edits'})
        progress('功能配置', '房间处理完成', room=rid, status=row['status'])
    report['compiled_rooms'] = completion_certificates(city, report['attempts'])
    for certificate in report['compiled_rooms']: certificate['source'] = 'functional_configuration'
    for floor in city.iter_floors():
        processed = {a['room_id'] for a in report['attempts'] if a['floor_id'] == floor.id and 'plan' in a}
        if not processed: continue
        retained = [r for r in floor.metadata.get('functional_configuration_feedback', [])
                    if r['room_id'] not in processed]
        floor.metadata['functional_configuration_feedback'] = retained + [
            r for r in report['floor_feedback'] if r['floor_id'] == floor.id]
    from cityg.transactions import refresh_local_overlay
    annotated = [a['room_id'] for a in report['attempts'] if 'plan' in a]
    if annotated: refresh_local_overlay(original, city, annotated)
    return city, report
