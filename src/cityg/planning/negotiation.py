"""Bounded smallest-scope negotiation over explicitly authorized strategies.

Agents supply candidate planners; this coordinator supplies no implicit editing
authority and never treats a rejected candidate as a resolved conflict.
"""
from copy import deepcopy
from dataclasses import asdict

from cityg.ccwp import entity_index, expected_hierarchy
from cityg.repair import PatchRejected
from cityg.schemas import Building, Floor, Room
from cityg.transactions import MutationProposal, accept_candidate, descendants, fingerprint


def scope_chain(city, entity_id):
    hierarchy=expected_hierarchy(city); entities=entity_index(city)
    if entity_id not in hierarchy: raise ValueError('Conflict target must resolve to an existing entity')
    chain=[]; current=entity_id
    while current is not None:
        entity=entities[current]
        kind=('room' if isinstance(entity,Room) else 'floor' if isinstance(entity,Floor)
              else 'building' if isinstance(entity,Building) else None)
        if kind: chain.append((kind,current))
        current=hierarchy[current][1]
    return chain


def negotiate(city, conflict, *, authorized_roots, strategies, compiled_gate,
              resolution_gate, protected_ids=(), max_attempts=3,
              source='validation_repair', memory_store=None, scope_requirements=None):
    """Try room -> floor -> building, publishing at most one verified candidate.

    Each strategy is a callable(detached_city, scope_id, conflict) -> City.
    Both gates must raise on failure. resolution_gate must return True to prove
    this specific conflict was resolved, independent of general scene validity.
    A missing strategy is not replaced by an unbounded planner. Trusted executor
    requirements may skip provably incapable scopes without consuming proposal
    budget. They never grant authority or bypass candidate acceptance checks.
    """
    if type(max_attempts) is not int or not 1<=max_attempts<=6:
        raise ValueError('Negotiation budget must be 1..6 attempts')
    if not callable(compiled_gate) or not callable(resolution_gate):
        raise ValueError('Negotiation requires compiled and conflict-specific gates')
    entities=entity_index(city)
    if not authorized_roots or set(authorized_roots)-entities.keys():
        raise ValueError('Authority must name existing explicit roots')
    base=fingerprint(city); attempts=[]
    report={'conflict_id':conflict['conflict_id'],'entity_id':conflict['entity_id'],
        'base_fingerprint':base,'authorized_roots':list(authorized_roots),
        'attempt_limit':max_attempts,'attempts':attempts,'verified_resolved':False,
        'scope_policy':'minimal_capable' if scope_requirements is not None else 'smallest_first',
        'scope_preflight':[],
        'automatic_scope_expansion':False,
        'interface_contract': {
            'schema_version':'cityg.negotiation_interface.v1',
            'base_fingerprint':base, 'subject_id':conflict['entity_id'],
            'authorized_roots':list(authorized_roots),
            'required_obligations':['protected_geometry','compiled_feasibility','specific_conflict_resolution'],
            'note':'Operational acceptance contract, not complete hierarchical design-interface propagation'}}
    if conflict.get('base_fingerprint',base)!=base:
        return deepcopy(city),{**report,'status':'stale_conflict','requires_user_approval':False}
    if scope_requirements is not None:
        scope_requirements.validate(city)
        report['scope_requirements']=asdict(scope_requirements)
        if scope_requirements.unsupported_reason is not None:
            return deepcopy(city),{**report,'status':'unsupported_capability',
                'reason':scope_requirements.unsupported_reason,'requires_user_approval':False}
    allowed=descendants(city,authorized_roots)
    # Even building-level authority does not imply permission to move a locked
    # shell, entrance or core. A separate user-authorized editor owns that work.
    geometry={b.id:(deepcopy(b.footprint),deepcopy(b.entrance),deepcopy(b.vertical_connectors))
              for b in city.iter_buildings()}
    for kind,scope_id in scope_chain(city,conflict['entity_id']):
        strategy=strategies.get(kind)
        if strategy is None: continue
        if scope_requirements is not None:
            exclusion=scope_requirements.exclusion(city,kind,scope_id)
            report['scope_preflight'].append({'scope_id':scope_id,'scope_type':kind,
                'status':'skipped' if exclusion else 'eligible','reason':exclusion})
            if exclusion: continue
        if scope_id not in allowed:
            return deepcopy(city),{**report,'status':'needs_authorization','requested_scope':scope_id,
                'requested_scope_type':kind,'requires_user_approval':True}
        if len(attempts)>=max_attempts:
            return deepcopy(city),{**report,'status':'budget_exhausted','requires_user_approval':False}
        proposal=MutationProposal.bind(city,[scope_id],source=source,kind='bounded_negotiation',
            proposal_id=f'negotiate_{base[:12]}_{len(attempts)}',protected_ids=protected_ids)
        receipt={'scope_id':scope_id,'base_fingerprint':base,
                 'obligations':{key:'not_run' for key in report['interface_contract']['required_obligations']}}
        def gate(candidate):
            receipt['candidate_fingerprint']=fingerprint(candidate)
            current={b.id:(b.footprint,b.entrance,b.vertical_connectors) for b in candidate.iter_buildings()}
            receipt['obligations']['protected_geometry']='passed' if current==geometry else 'failed'
            if current!=geometry: raise PatchRejected('protected_geometry','Shell/entry/core changed')
            # Compilation may enrich its private input. It must not change the
            # state observed by the independent conflict checker or the commit.
            compiled=compiled_gate(deepcopy(candidate))
            compile_ok=isinstance(compiled,dict) and compiled.get('ok') is True
            receipt['obligations']['compiled_feasibility']='passed' if compile_ok else 'failed'
            if not compile_ok:
                raise PatchRejected('compiled_validation_failed','Candidate failed compiled acceptance')
            resolved=resolution_gate(deepcopy(candidate),deepcopy(conflict)) is True
            receipt['obligations']['specific_conflict_resolution']='passed' if resolved else 'failed'
            if not resolved:
                raise PatchRejected('conflict_unresolved','Candidate did not resolve the specific conflict')
            return compiled
        try:
            result=accept_candidate(city,proposal,
                lambda draft:strategy(draft,scope_id,deepcopy(conflict)),
                compiled_gate=gate,memory_store=memory_store)
            # No-op commits bypass compilation in the shared engine. They
            # therefore cannot be credited with solving a reported conflict.
            if result.report['status']!='accepted':
                raise PatchRejected('no_effect','No verified state change')
            attempts.append({'scope_id':scope_id,'scope_type':kind,'status':'accepted',
                             'transaction':result.report,'implementation_receipt':receipt})
            return result.city,{**report,'status':'resolved','verified_resolved':True,
                'requires_user_approval':False,'after_fingerprint':fingerprint(result.city),
                'child_proposals_require_rebinding':kind!='room'}
        except (PatchRejected,ValueError) as exc:
            attempts.append({'scope_id':scope_id,'scope_type':kind,'status':'rejected',
                'error':str(exc),'code':getattr(exc,'code',type(exc).__name__),
                'proposal':asdict(proposal),'implementation_receipt':receipt})
        except RuntimeError as exc:
            # A service outage is not evidence that a larger edit is needed.
            attempts.append({'scope_id':scope_id,'scope_type':kind,'status':'service_failed','error':str(exc),
                             'implementation_receipt':receipt})
            return deepcopy(city),{**report,'status':'service_unavailable','requires_user_approval':False}
    return deepcopy(city),{**report,'status':'unresolved','requires_user_approval':False}
