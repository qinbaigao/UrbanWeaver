"""Common candidate acceptance for exact-scope edits and automatic repairs.

The callback edits a detached City and supplies its CCWP (PatchEngine and
subtree planners already do this). We check both canonical and overlay diffs,
never rebuild away user-authored CCWP intent/state/relations. File publication
is a separate, staged operation after compilation.
"""
from copy import deepcopy
from dataclasses import dataclass, asdict
import hashlib
import json

from cityg.ccwp import entity_index, expected_hierarchy
from cityg.schemas import City, Room
from cityg.serialization import to_primitive
from cityg.validation import CityValidator
from cityg.repair import PatchRejected
from cityg.planning.furnishing_gate import furnishing_non_degradation_check


def fingerprint(city):
    return hashlib.sha256(json.dumps(to_primitive(city), sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def descendants(city, roots):
    parents = {key: row[1] for key, row in expected_hierarchy(city).items()}
    result = set(roots)
    while True:
        extra = {k for k, parent in parents.items() if parent in result} - result
        if not extra: return result
        result.update(extra)


def ancestors(city, roots):
    parents = {key: row[1] for key, row in expected_hierarchy(city).items()}
    result = set()
    for key in roots:
        while key in parents and parents[key] is not None:
            key = parents[key]
            result.add(key)
    return result


def snapshots(city):
    """Flat canonical entities + meaningful CCWP state, keyed by owning scope."""
    result = {}; hierarchy = expected_hierarchy(city)
    containers = {'districts', 'parcels', 'buildings', 'floors', 'rooms', 'doors',
        'objects', 'vertical_connectors', 'road_network', 'rivers', 'bridges', 'world_program'}
    for key, entity in entity_index(city).items():
        row = {k: v for k, v in to_primitive(entity).items() if k not in containers}
        if isinstance(entity, City):
            row['metadata'] = {k: v for k, v in row.get('metadata', {}).items()
                               if k not in {'identity_registry', 'street_network_program'}}
        row['_parent'] = hierarchy[key][1]
        result['entity:'+key] = (key, row)
    # Storage lives on City for serialization, but each segment is owned by
    # its exact road. This does not authorize arbitrary city metadata writes.
    street = city.metadata.get('street_network_program') or {'version': 'street_network_program.v1'}
    result['street_header'] = (city.id, {k:v for k,v in street.items() if k != 'segments'})
    for segment in street.get('segments', []):
        key = 'street_segment:' + segment['road_id']
        if key in result:
            raise ValueError('Duplicate street program segment')
        result[key] = (segment['road_id'], to_primitive(segment))
    for node in city.world_program.nodes:
        row = {k: v for k, v in to_primitive(node).items()
               if k not in {'version', 'provenance_ids', 'artifact_ids'}}
        result['node:'+node.entity_id] = (node.entity_id, row)
    for name, owner in [('contracts', 'scope_id'), ('relations', 'source_id'), ('artifacts', 'owner_id')]:
        for row in getattr(city.world_program, name):
            result[name+':'+row.id] = (getattr(row, owner), to_primitive(row))
    return result


def refresh_local_overlay(before, candidate, scope_ids):
    """Refresh derived CCWP inside a room/subtree without erasing user overlays.

    Modified/custom contracts and relations survive; dangling custom references
    are intentionally left for validation to reject, never silently discarded.
    Cross-boundary structural edits need their own ancestor dependency handling.
    """
    from cityg.ccwp import build_world_program
    baseline = build_world_program(deepcopy(before), producer='overlay_baseline', seed=None)
    fresh = build_world_program(candidate, producer='local_overlay_refresh', seed=None)
    scope = descendants(before, scope_ids) | descendants(candidate, scope_ids)
    dependencies = scope | ancestors(before, scope_ids) | ancestors(candidate, scope_ids)
    old_nodes = {n.entity_id: n for n in before.world_program.nodes}
    derived_nodes = {n.entity_id: n for n in baseline.nodes}
    program = deepcopy(before.world_program)
    program.nodes = []
    for node in fresh.nodes:
        old = old_nodes.get(node.entity_id)
        if old is not None:
            if node.entity_id not in scope:
                node = deepcopy(old)
            else:
                derived = derived_nodes[node.entity_id]
                for field in ('description', 'function', 'tags'):
                    if getattr(old.intent, field) != getattr(derived.intent, field):
                        setattr(node.intent, field, deepcopy(getattr(old.intent, field)))
                for field in vars(old.geometry):
                    if getattr(old.geometry, field) != getattr(derived.geometry, field):
                        setattr(node.geometry, field, deepcopy(getattr(old.geometry, field)))
                node.state = deepcopy(old.state)
                node.locked = old.locked
                node.version = old.version
                node.provenance_ids = list(old.provenance_ids)
                node.artifact_ids = list(old.artifact_ids)
        program.nodes.append(node)
    for name, owner in [('contracts', 'scope_id'), ('relations', 'source_id')]:
        old = {r.id: deepcopy(r) for r in getattr(before.world_program, name)}
        automatic = {r.id: r for r in getattr(baseline, name)}
        updated = {r.id: r for r in getattr(fresh, name)}
        for key, record in list(old.items()):
            if getattr(record, owner) in dependencies and key in automatic and record == automatic[key]:
                old.pop(key)
        for key, record in updated.items():
            if getattr(record, owner) in dependencies and key not in old:
                old[key] = record
        setattr(program, name, list(old.values()))
    live = {n.entity_id for n in program.nodes}
    program.artifacts = [a for a in program.artifacts if a.owner_id in live]
    for node in program.nodes:
        for name, wanted in (
            ('contract_ids', [r.id for r in program.contracts if node.entity_id == r.scope_id or node.entity_id in r.subject_ids]),
            ('relation_ids', [r.id for r in program.relations if r.source_id == node.entity_id])):
            previous = getattr(old_nodes.get(node.entity_id), name, [])
            setattr(node, name, [key for key in previous if key in wanted] + [key for key in wanted if key not in previous])
    program.provenance = [p for p in program.provenance if p.entity_id in live]
    history = {p.id for p in program.provenance}
    for p in program.provenance:
        p.parent_record_ids = [key for key in p.parent_record_ids if key in history]
    for node in program.nodes:
        node.provenance_ids = [key for key in node.provenance_ids if key in history]
    candidate.world_program = program
    return candidate


def _derived_dependency_changes(city, candidate, before, after, keys, allowed, roots):
    """Only compiler-derived ancestor bindings may change outside edit roots.

    Both sides must match independently reconstructed canonical contracts;
    custom intent/state/limits and arbitrary outside entity changes are never
    covered by this exception.
    """
    from cityg.ccwp import build_world_program
    old = deepcopy(city); old.world_program = build_world_program(old, producer='derived_check', seed=None)
    new = deepcopy(candidate); new.world_program = build_world_program(new, producer='derived_check', seed=None)
    old_auto, new_auto = snapshots(old), snapshots(new)
    parents = ancestors(city, roots) | ancestors(candidate, roots)
    approved = set()
    for key in keys:
        owner = (after.get(key) or before[key])[0]
        if owner not in parents or not key.startswith(('contracts:', 'relations:')):
            continue
        if before.get(key) != old_auto.get(key) or after.get(key) != new_auto.get(key):
            continue
        left = (before.get(key) or (None, {}))[1]
        right = (after.get(key) or (None, {}))[1]
        field = 'subject_ids' if key.startswith('contracts:') else 'target_ids'
        if (set(left.get(field, [])) ^ set(right.get(field, []))) - (allowed | {owner}):
            continue
        # Structural room changes should only alter endpoint membership here,
        # never parameters such as a protected entrance's maximum distance.
        if left and right and ({k:v for k,v in left.items() if k != field}
                              != {k:v for k,v in right.items() if k != field}):
            continue
        approved.add(key)
    approved_ids = {key.split(':', 1)[1] for key in approved}
    for key in keys:
        if not key.startswith('node:') or key not in before or key not in after:
            continue
        owner, left = before[key]; _, right = after[key]
        if owner not in parents:
            continue
        fields = {'contract_ids', 'relation_ids'}
        if {k:v for k,v in left.items() if k not in fields} != {k:v for k,v in right.items() if k not in fields}:
            continue
        diff = set().union(*(set(left[f]) ^ set(right[f]) for f in fields))
        if diff <= approved_ids:
            approved.add(key)
    return approved


@dataclass(frozen=True)
class MutationProposal:
    proposal_id: str
    source: str
    kind: str
    scope_ids: tuple[str, ...]
    base_fingerprint: str
    expected_versions: dict[str, int]
    protected_ids: tuple[str, ...] = ()
    requirement_ids: tuple[str, ...] = ()
    preserve_inventory: bool = True

    @classmethod
    def bind(cls, city, scope_ids, *, source, kind, proposal_id,
             protected_ids=(), requirement_ids=(), preserve_inventory=True):
        nodes = {n.entity_id: n for n in city.world_program.nodes}
        ids = tuple(dict.fromkeys(scope_ids))
        if not ids or set(ids)-nodes.keys() or set(protected_ids)-nodes.keys():
            raise PatchRejected('unknown_scope', 'Proposal needs exact existing scope/protection IDs')
        if source not in {'generation', 'user_edit', 'visual_repair', 'validation_repair'}:
            raise ValueError('Unknown proposal source')
        if not preserve_inventory and source != 'user_edit':
            raise ValueError('Automatic repair cannot waive inventory protection')
        return cls(proposal_id, source, kind, ids, fingerprint(city),
                   {i: nodes[i].version for i in ids}, tuple(protected_ids),
                   tuple(requirement_ids), preserve_inventory)


@dataclass
class MutationResult:
    city: City
    report: dict


def accept_candidate(city, proposal, propose, *, compiled_gate=None, memory_store=None):
    nodes = {n.entity_id: n for n in city.world_program.nodes}
    if proposal.source not in {'generation', 'user_edit', 'visual_repair', 'validation_repair'}:
        raise ValueError('Unknown proposal source')
    if not proposal.preserve_inventory and proposal.source != 'user_edit':
        raise ValueError('Automatic repair cannot waive inventory protection')
    if (not proposal.scope_ids or set(proposal.scope_ids)-nodes.keys()
            or set(proposal.protected_ids)-nodes.keys()
            or set(proposal.expected_versions) != set(proposal.scope_ids)):
        raise PatchRejected('unknown_scope', 'Proposal needs exact existing scope/protection versions')
    if fingerprint(city) != proposal.base_fingerprint or any(
            i not in nodes or nodes[i].version != v for i, v in proposal.expected_versions.items()):
        raise PatchRejected('stale_proposal', 'Scene changed after proposal binding')
    candidate = propose(deepcopy(city))
    if not isinstance(candidate, City): raise TypeError('Proposal callback must return a City')
    before, after = snapshots(city), snapshots(candidate)
    keys = {k for k in before.keys() | after.keys() if before.get(k) != after.get(k)}
    changed = {table[k][0] for k in keys for table in (before, after) if k in table}
    allowed = descendants(city, proposal.scope_ids) | descendants(candidate, proposal.scope_ids)
    outside_keys = {key for key in keys if (after.get(key) or before[key])[0] not in allowed}
    derived = (_derived_dependency_changes(city, candidate, before, after, outside_keys, allowed, proposal.scope_ids)
               if outside_keys else set())
    if outside_keys-derived:
        raise PatchRejected('scope_violation', 'Actual out-of-scope changes: '+str(sorted(outside_keys-derived)))
    locked = [n.entity_id for n in nodes.values() if n.locked]
    protected_roots = [*proposal.protected_ids, *locked]
    protected = descendants(city, protected_roots) | descendants(candidate, protected_roots)
    if changed & protected:
        raise PatchRejected('locked_node', 'Protected entities changed: '+str(sorted(changed & protected)))
    if not changed:
        return MutationResult(deepcopy(city), {'status': 'no_change', 'proposal': asdict(proposal),
                              'changed_entity_ids': [], 'before_fingerprint': proposal.base_fingerprint,
                              'after_fingerprint': proposal.base_fingerprint})
    inventory = []
    if proposal.preserve_inventory:
        new_entities = entity_index(candidate)
        previous_objects = {}; proposed_objects = {}
        for obj in city.iter_objects(): previous_objects.setdefault(obj.room_id, []).append(obj)
        for obj in candidate.iter_objects(): proposed_objects.setdefault(obj.room_id, []).append(obj)
        for room in city.iter_rooms():
            old = previous_objects.get(room.id, [])
            if not old: continue
            if not isinstance(new_entities.get(room.id), Room):
                raise PatchRejected('furnishing_non_degradation', 'Furnished room removed: '+room.id)
            check = furnishing_non_degradation_check(old, proposed_objects.get(room.id, []), room)
            if not check['ok']: raise PatchRejected('furnishing_non_degradation', check['reason'])
            inventory.append(check)
    dependencies = set(changed)
    for current in (city, candidate):
        parents = {key: row[1] for key, row in expected_hierarchy(current).items()}
        for key in changed:
            while key in parents and parents[key] is not None:
                key = parents[key]; dependencies.add(key)
    for node in candidate.world_program.nodes:
        old = nodes.get(node.entity_id)
        if old is not None:
            node.version = old.version + int(node.entity_id in dependencies)
    # A planner may rebuild derived CCWP nodes, but it may not replace stable
    # entities' recorded history with a new synthetic "initial generation".
    live = set(entity_index(candidate))
    history = {p.id: deepcopy(p) for p in candidate.world_program.provenance}
    history.update({p.id: deepcopy(p) for p in city.world_program.provenance if p.entity_id in live})
    history = {key: p for key, p in history.items() if p.entity_id in live}
    for p in history.values():
        p.parent_record_ids = [key for key in p.parent_record_ids if key in history]
    candidate.world_program.provenance = list(history.values())
    for node in candidate.world_program.nodes:
        old = nodes.get(node.entity_id)
        previous = old.provenance_ids if old else []
        node.provenance_ids = list(dict.fromkeys(key for key in [*previous, *node.provenance_ids] if key in history))
    validation = CityValidator().validate(candidate)
    if not validation.ok:
        raise PatchRejected('post_validation_failed', 'Candidate failed canonical/CCWP validation', validation)
    compiled = compiled_gate(deepcopy(candidate)) if compiled_gate is not None else None
    if compiled_gate is not None and (not isinstance(compiled, dict) or compiled.get('ok') is not True):
        raise PatchRejected('compiled_validation_failed', 'Candidate failed compiled acceptance')
    from cityg.geometry.incremental import entity_building_index
    owners = {**entity_building_index(city), **entity_building_index(candidate)}
    evidence_ids = dependencies | descendants(city, changed) | descendants(candidate, changed)
    report = {'schema_version': 1, 'status': 'accepted', 'proposal': asdict(proposal),
        'before_fingerprint': proposal.base_fingerprint, 'after_fingerprint': fingerprint(candidate),
        'changed_entity_ids': sorted(changed), 'unrelated_entities_preserved': True,
        'derived_dependency_changes': sorted(derived),
        'compile_building_ids': sorted({owners[k] for k in changed if owners.get(k)}),
        'invalidated_evidence_scope_ids': sorted(evidence_ids), 'inventory_checks': inventory,
        'semantic_validation': validation.to_dict(), 'compiled_gate': compiled,
        'export_publication_verified': False, 'physics_runtime_tested': False}
    if memory_store:
        from cityg.memory import MemoryRecord
        memory_store.record_mutation(MemoryRecord(memory_id=proposal.proposal_id, kind='mutation_decision',
            scope_type='city', scope_id=city.id, content=report, producer=proposal.source,
            validation_status='accepted'), evidence_ids)
    return MutationResult(candidate, report)
