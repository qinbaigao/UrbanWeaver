"""Shared detached commit for accepted Room Agent furnishing programs."""
from copy import deepcopy

from cityg.planning.interiors import FloorDetailAgent
from cityg.refinement.selection import mark_room_detail
from cityg.repair import PatchRejected
from cityg.transactions import MutationProposal, accept_candidate, fingerprint, refresh_local_overlay


def commit_room_program(city, room_id, program, *, asset_resolver=None, seed=17,
                        source='visual_repair', compiled_gate=None, memory_store=None):
    proposal = MutationProposal.bind(city, [room_id], source=source, kind='room_program',
        proposal_id=f'room_program__{room_id}__{fingerprint(city)[:16]}')
    candidate,stats = prepare_room_program(city,room_id,program,asset_resolver=asset_resolver,seed=seed)
    accepted = accept_candidate(city, proposal, lambda _: candidate,
                                compiled_gate=compiled_gate, memory_store=memory_store)
    return accepted, stats


def prepare_room_program(city, room_id, program, *, asset_resolver=None, seed=17):
    """Build a detached proposal; this does not grant acceptance or publication."""
    candidate = deepcopy(city)
    stats = FloorDetailAgent(asset_resolver=asset_resolver,
        program_overrides={room_id: program}).populate_rooms(candidate, {room_id}, seed=seed)
    if stats['matched_room_count'] != 1 or stats['furnishing_non_degradation_gate_rejected_room_count']:
        raise PatchRejected('furnishing_non_degradation', 'Room program rejected; previous room retained')
    mark_room_detail(candidate, {room_id}, status='accepted')
    refresh_local_overlay(city, candidate, [room_id])
    return candidate, stats


def negotiate_room_program(city, room_id, program_provider, *, failure,
                           asset_resolver=None, seed=17, compiled_gate, memory_store=None):
    """One additional room-only proposal after a concrete compiled conflict.

    Resolves proposal feasibility, not the original visual complaint. Parent
    changes remain unauthorized in the automatic visual-repair path.
    """
    from cityg.planning.negotiation import negotiate
    conflict={'conflict_id':f'room_program_conflict__{room_id}__{fingerprint(city)[:12]}',
        'entity_id':room_id,'base_fingerprint':fingerprint(city),
        'code':'room_program_unrealizable','reason':str(failure)}
    stats={}
    def propose(draft,scope,feedback):
        program=program_provider(draft,feedback)
        candidate,detail=prepare_room_program(draft,scope,program,asset_resolver=asset_resolver,seed=seed)
        stats.update(detail)
        return candidate
    def feasible(candidate, _):
        room=next(r for r in candidate.iter_rooms() if r.id==room_id)
        return room.metadata.get('room_design',{}).get('status')=='accepted'
    result,report=negotiate(city,conflict,authorized_roots=[room_id],strategies={'room':propose},
        compiled_gate=compiled_gate,resolution_gate=feasible,max_attempts=1,
        source='visual_repair',memory_store=memory_store)
    report['resolution_scope']='new_room_proposal_feasibility_only'
    report['visual_issue_resolution_proven']=False
    return result,report,stats
