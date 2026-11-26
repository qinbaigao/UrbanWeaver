"""Prototype integration for new cities, retaining bounded review provenance.

The runtime never calls the standalone review scripts or clears an existing
inventory. Urban recipes are context priors; floor/room proposals are compiled
transactions. Their review status is not promoted by successful execution.
"""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

from cityg.assets import MaterialLibrary
from cityg.ccwp import build_world_program
from cityg.planning.city_prototype_adapter import adapt_city_rooms, validate_options, verify_room
from cityg.planning.floor_prototypes import FloorPrototypeLibrary
from cityg.planning.floor_repartition import repartition_city
from cityg.planning.interior_scope import select_scope
from cityg.planning.prototype_decor_assets import add_review_decorations
from cityg.planning.prototype_lab import detached_registry
from cityg.planning.urban_prototypes import UrbanPrototypeLibrary
from cityg.serialization import to_primitive


class DeferredFurniture:
    def populate(self, city, *, seed):
        return {"planner": "deferred_until_partition", "placed_object_count": 0}


def load_options(path):
    path = Path(path).resolve()
    value = json.loads(path.read_text())
    allowed = {"schema_version", "library_root", "selection_attempts", "adaptation"}
    if not allowed <= set(value) or set(value) - (allowed | {'generation_seed','coordination_policy','capacity_search','room_selection','shared_goals','floor_coordination','functional_configuration'}) or value["schema_version"] != 1:
        raise ValueError("Invalid generation prototype configuration")
    from cityg.planning.generation_coordination import POLICIES
    if value.setdefault('coordination_policy','agent_feedback') not in (*POLICIES, 'local_only'):
        raise ValueError('Unknown generation coordination policy')
    if 'generation_seed' in value and type(value['generation_seed']) is not int:
        raise ValueError('generation_seed must be an integer')
    capacity = {'enabled':True, 'max_candidates_per_building':36, **value.get('capacity_search', {})}
    if (set(capacity) != {'enabled','max_candidates_per_building'} or type(capacity['enabled']) is not bool
            or type(capacity['max_candidates_per_building']) is not int
            or not 1 <= capacity['max_candidates_per_building'] <= 100):
        raise ValueError('Invalid new-scene capacity search configuration')
    value['capacity_search'] = capacity
    room_selection={'enabled':False,'max_calls':2,**value.get('room_selection',{})}
    if (set(room_selection)!={'enabled','max_calls'} or type(room_selection['enabled']) is not bool
            or type(room_selection['max_calls']) is not int or not 1<=room_selection['max_calls']<=3):
        raise ValueError('Invalid room reference Agent configuration')
    value['room_selection']=room_selection
    goals={'enabled':False,'max_calls':2,**value.get('shared_goals',{})}
    if set(goals)!={'enabled','max_calls'} or type(goals['enabled']) is not bool or type(goals['max_calls']) is not int or not 1<=goals['max_calls']<=2:
        raise ValueError('Invalid shared design goals configuration')
    value['shared_goals']=goals
    from cityg.planning.floor_coordination import options as coordination_options
    value['floor_coordination']=coordination_options(value.get('floor_coordination'))
    from cityg.planning.functional_configuration import options as functional_options
    value['functional_configuration']=functional_options(value.get('functional_configuration'))
    if type(value["selection_attempts"]) is not int or not 1 <= value["selection_attempts"] <= 3:
        raise ValueError("selection_attempts must be 1..3")
    root = Path(value["library_root"])
    value["library_root"] = str((path.parent/root).resolve() if not root.is_absolute() else root)
    value["adaptation"] = validate_options(value["adaptation"])
    return value


class GenerationPrototypes:
    def __init__(self, options):
        self.options = deepcopy(options)
        self.urban = UrbanPrototypeLibrary(options["library_root"])
        self.floors = FloorPrototypeLibrary(options["library_root"])

    def select_scope(self, city, *, building_limit=0, floor_limit=2):
        opt = self.options['adaptation']
        nb = min(building_limit or opt['max_buildings'], opt['max_buildings'])
        nf = min(floor_limit, opt['max_floors_per_building'])
        cfg = opt.get('floor_repartition', {})
        ids = cfg.get('target_building_ids', [])
        buildings = {b.id: b for b in city.iter_buildings()}
        if set(ids)-set(buildings): raise ValueError('Unknown target building ID')
        if len(set(ids)) > nb: raise ValueError('Explicit target buildings exceed detail budget')
        scope = select_scope(city, nb, nf)
        reservation = city.metadata.get('interior_capability_reservation')
        chosen = (list(reservation['target_buildings']) if reservation is not None
                  else ids or list(scope['building_levels']))
        mapping = {bid: [f.level for f in sorted(buildings[bid].floors, key=lambda f: f.level)
                         if f.level in cfg.get('levels', [0, 1])][:nf] for bid in chosen}
        from cityg.interior_requirements import requirements_for
        for bid in chosen:
            requested=sorted({level for r in requirements_for(buildings[bid]) for level in r['levels']})
            if requested:
                if len(requested)>nf: raise ValueError(f'{bid}: requested floors exceed detail budget')
                mapping[bid]=requested
        scope['building_levels'] = {bid: levels for bid, levels in mapping.items() if levels}
        scope['policy'] = 'generation_prototype_budgeted_scope'
        return scope

    def context(self, selection):
        key = selection["prototype_id"]
        if key == "none":
            return None
        record = self.urban.records[key]
        # Remove sample counts and internal review fixed-room defaults. These
        # have no authority over the user's requested scale or floor capacity.
        hints = {k: v for k, v in record["spec"].items() if k not in
                 {"name", "seed", "building_count", "min_floors", "max_floors", "rooms_per_floor", "room_count_strategy"}}
        return {"id": key, "intent": record["intent"], "reference_defaults": hints,
                "adaptation": "Use only compatible defaults; user intent overrides every reference field. "
                              "Choose extents appropriate to the requested count. Do not inherit fixed room counts."}

    def attach_urban(self, city, spec, selection):
        key = selection["prototype_id"]
        if key == "none":
            return {**selection, "status": "no_reference", "applied": False}
        record = self.urban.records[key]
        values = to_primitive(spec)
        report = {**selection, "fingerprint": self.urban.content_fingerprint(key),
                  "status": "reference_conditioned_planning", "applied": True,
                  "whole_template_instantiated": False, "production_approved": False,
                  "review_status": record["review"]["status"],
                  "spec_differences": {k: {"reference": v, "planned": values.get(k)}
                                       for k, v in record["spec"].items() if v != values.get(k)}}
        city.metadata["urban_layout_prototype"] = {"id": key, "fingerprint": report["fingerprint"],
            "mode": report["status"], "production_enabled": True, "production_approved": False,
            "floor_reference_hints": record["floor_reference_hints"]}
        return report

    def floor_context(self, selection):
        if self.options.get('coordination_policy') == 'local_only':
            return {'local_only': True, 'detailed_levels': self.options['adaptation'].get('floor_repartition', {}).get('levels', [0, 1]),
                    'instruction': 'Plan from the explicit user requirements and the current floor geometry.'}
        import math
        record = self.urban.records.get(selection['prototype_id'], {})
        return {'floor_reference_ids': record.get('floor_reference_hints', []),
                'detailed_levels': self.options['adaptation'].get('floor_repartition',{}).get('levels',[0,1]),
                'minimum_compatible_rooms_per_detailed_floor': math.ceil(
                    self.options['adaptation']['max_rooms'] / (self.options['adaptation']['max_buildings'] *
                    self.options['adaptation']['max_floors_per_building'])),
                'room_dimensions': [{'id': key, 'function': row['room_type'],
                                     'reference': row['reference'], 'applicability': row['applicability']}
                                    for key, row in self.floors.room_library.rooms.items()],
                'instruction': 'Use compatible room sizes as priors for selected detailed floors. '
                    'Do not overpartition a small plate. Preserve explicit counts, entrance/core and '
                    'functional requirements even when no reference fits. References are not fixed coordinates.'}

    def prepare_resources(self, registry, compiler):
        if registry is None:
            raise ValueError("Prototype interiors require an asset registry")
        detached = detached_registry(registry)
        root = self.floors.root
        project = Path(__file__).resolve().parents[3]
        for file in [root/'decoration_assets.json', *sorted(root.glob('reference_assets_*.json'))]:
            add_review_decorations(detached, file, project_root=project)
        compiler.asset_registry = detached
        compiler.asset_registry_configured = True
        compiler.streetscape_compiler.asset_registry = detached
        if compiler.facade_asset_runtime is not None:
            compiler.facade_asset_runtime.bind_registry(detached)
        materials = MaterialLibrary()
        for source in (compiler.material_library,
                       MaterialLibrary(project/'assets/incoming/interior_materials/material_library.json')):
            if source is None: continue
            if source.environment_path and not materials.environment_path:
                materials.set_environment(source.resolve_path(source.environment_path))
            for record in source.list_all():
                if materials.get(record.material_id): continue
                paths = {k: str(source.resolve_path(getattr(record, k))) for k in
                         ('base_color_path', 'normal_path', 'roughness_path', 'ambient_occlusion_path') if getattr(record, k)}
                materials.register(replace(record, **paths))
        compiler.material_library = materials
        return detached

    def populate(self, city, registry, compiler, *, progress=None, building_limit=0, floor_limit=2,
                 preserve_partition=False, memory_store=None, reference_selector=None,floor_selector=None):
        if any(city.iter_objects()):
            raise ValueError("New-city prototype planning requires an unfurnished skeleton; inventory cannot be cleared")
        opt = deepcopy(self.options["adaptation"])
        if building_limit: opt["max_buildings"] = min(opt["max_buildings"], building_limit)
        opt["max_floors_per_building"] = min(opt["max_floors_per_building"], floor_limit)
        city = deepcopy(city)
        scope = self.select_scope(city, building_limit=building_limit, floor_limit=floor_limit)
        targets = deepcopy(scope['building_levels'])
        from cityg.planning.interior_scope import materialize_access_dependencies
        materialize_access_dependencies(city, targets)
        cfg = opt.get('floor_repartition', {})
        if city.metadata.get('urban_layout_prototype'):
            cfg = {**cfg, 'preferred_reference_ids': city.metadata['urban_layout_prototype']['floor_reference_hints']}
        policy = self.options.get('coordination_policy','agent_feedback')
        if policy in ('one_way', 'local_only'):
            cfg = {**cfg, 'joint_room_planning': False}
        if preserve_partition:
            cfg = {**cfg, 'enabled': False}
        # Empty mapping is intentional and must never become legacy []=all.
        partitioned, floor_report = repartition_city(city, self.floors, compiler, cfg,
            variation=opt['variation_limit'], progress=progress, target_levels=targets)
        coordination=[]
        coordination_config=self.options.get('floor_coordination',{})
        allow_feedback = policy in ('fixed_feedback', 'agent_feedback') and coordination_config.get('enabled') and not preserve_partition
        selector = floor_selector if policy == 'agent_feedback' else None
        if allow_feedback:
            from cityg.planning.floor_coordination import proposals, apply_proposal
            from cityg.planning.generation_coordination import ordered_offers
            remaining = coordination_config['max_proposals']
            while remaining:
                offered = proposals(partitioned,self.floors.room_library,targets,coordination_config)
                ordered, choice = ordered_offers(offered,partitioned,selector,remaining)
                for offer in ordered:
                    remaining -= 1
                    try:
                        candidate, outcome = apply_proposal(partitioned,offer,self.floors.room_library,compiler,
                            authorized_levels=targets,config=coordination_config,memory_store=memory_store)
                    except ValueError as error:
                        outcome = {'status':'rejected','error':str(error)}
                    coordination.append({'proposal':offer,'selection':choice,'outcome':outcome})
                    if outcome['status']=='resolved':
                        partitioned=candidate
                        break
                else:
                    break
        from cityg.planning.joint_inventory_capacity import repair_joint_capacity
        if policy == 'local_only':
            capacity_report = {'floors': [], 'status': 'no_cross_scale_capacity_evaluation'}
        else:
            partitioned, capacity_report = repair_joint_capacity(partitioned,compiler,registry,targets,
                selector=selector,preserve_partition=not allow_feedback,
                seed=int(city.metadata.get('seed',17)),
                max_floors=opt.get('floor_repartition',{}).get('max_floors',2))
        result, report = adapt_city_rooms(partitioned, self.floors, registry, compiler, opt,
            progress=progress, target_levels=targets,reference_selector=reference_selector)
        report['coordination_policy'] = policy
        report['joint_inventory_capacity'] = capacity_report
        report['floor_repartition'] = floor_report
        report['floor_coordination'] = coordination
        if preserve_partition:
            floor_report['skip_reason'] = 'explicit_fixed_room_count_preserved'
        report['authorized_levels'] = targets
        report['summary']['repartitioned_floors'] = len(floor_report['accepted'])
        report['status'] = ('adapted' if len(report['rooms']) == opt['max_rooms'] else
                            'partial_reuse' if report['rooms'] else 'no_compatible_rooms')
        report['selection_mode'] = ('llm_reference_proposals_with_compiled_gates_and_audited_fallback'
            if report.get('llm_used') else 'balanced_deterministic_feasibility_with_reference_priors')
        report['production_approved'] = False
        result.metadata['generation_prototypes'] = {
            'status': report['status'], 'summary': report['summary'],
            'authorized_levels': targets, 'detailed_room_ids': [r['room_id'] for r in report['rooms']],
            'max_rooms': opt['max_rooms'], 'production_approved': False}
        result.metadata['interior_detail'] = {'planner': 'joint_prototype_transactions', **report['summary']}
        result.world_program = build_world_program(result, producer='generation_prototypes', seed=city.metadata.get('seed', 17))
        from cityg.transactions import MutationProposal, accept_candidate, fingerprint
        protected = [b.id for b in city.iter_buildings() if b.id not in targets]
        protected += [c.id for b in city.iter_buildings() for c in b.vertical_connectors]
        # Only a compiled, newly generated empty-floor replan authorizes new
        # INTERNAL door topology. All exterior doors and every other floor's
        # doors retain the original lock. Fixed/occupied floors cannot qualify.
        replanned={row['floor_id'] for row in capacity_report['floors']
                   if row['status']=='accepted' and row.get('compiled_floor_verified') is True
                   and row.get('exterior_entry_core_preserved') is True}
        if preserve_partition and replanned:
            raise ValueError('Fixed room counts cannot authorize floor topology replanning')
        for b in city.iter_buildings():
            for f in b.floors:
                if f.id in replanned and (f.level not in targets.get(b.id,[]) or f.objects or
                                         any(r.object_ids for r in f.rooms)):
                    raise ValueError('Internal door replan outside an empty authorized floor')
        protected += [d.id for f in city.iter_floors() for d in f.doors
                      if f.id not in replanned or d.room_b_id is None]
        report['authorized_internal_door_replans']=sorted(replanned)
        proposal = MutationProposal.bind(city, [city.id], source='generation',
            kind='prototype_generation', proposal_id='prototype_generation_'+fingerprint(city)[:20],
            protected_ids=protected)
        committed = accept_candidate(city, proposal, lambda _:result, memory_store=memory_store,
            compiled_gate=lambda _: {'ok':all(r.get('compiled_verified') is True for r in report['rooms'])
                and all(r.get('compiled_floor_verified') is True for r in capacity_report['floors'] if r['status']=='accepted'),
                'source':'per_room_compiled_transactions', 'rooms':[r['room_id'] for r in report['rooms']],
                'joint_capacity_floors':sorted(replanned),
                'physics_runtime_tested':False})
        result = committed.city
        report['transaction'] = committed.report
        if memory_store is not None:
            from cityg.memory import MemoryRecord
            versions={n.entity_id:n.version for n in result.world_program.nodes}
            revision=fingerprint(result)[:16]
            for row in report['rooms']:
                key=f'room_reference__{revision}__{row["room_id"]}'
                if memory_store.get(key) is not None: continue
                memory_store.put(MemoryRecord(key,'room_reference_execution','room',row['room_id'],
                    {k:deepcopy(row.get(k)) for k in ('prototype_id','content_fingerprint','room_function',
                        'coverage_group','selection_source','selection_reason','requirement_quote',
                        'spacing_adjustments','design_adjustments','effective_fingerprint','reference_effective_fingerprint',
                        'design_changed','goal_ids','major_count','expected_inventory','asset_bindings','compiled_verified')},
                    world_version=versions[row['room_id']],producer='RoomReferenceAgent+compiled_gate',
                    validation_status='accepted'))
        return result, report

    @staticmethod
    def verify_final(city, manifest_path, report, *, after_review=False):
        from cityg.geometry.incremental import scene_from_manifest
        manifest = manifest_path if isinstance(manifest_path, dict) else json.loads(Path(manifest_path).read_text())
        scene = scene_from_manifest(manifest)
        index = {r.id: (b, f, r) for b in city.iter_buildings() for f in b.floors for r in f.rooms}
        rows = []
        latest={}
        for phase in ('functional_completion','functional_configuration'):
            completion=report.get(phase,{})
            records=completion.get('compiled_rooms',[])
            if len(records)>completion.get('max_rooms',0) or len({r['room_id'] for r in records})!=len(records):
                raise ValueError('Functional completion exceeds its independent room budget')
            if any(not r.get('compiled_verified') or r.get('source')!=phase for r in records):
                raise ValueError('Functional completion missing compiled acceptance evidence')
            latest.update({r['room_id']:r for r in records})
        supplements=list(latest.values())
        updated={r['room_id'] for r in supplements}
        final_rows=[r for r in report['rooms'] if r['room_id'] not in updated]+supplements
        from cityg.planning.furnishing_acceptance import coverage, room_service
        has_target = 'max_rooms' in report.get('options', {})
        targets = {r['room_id']: r.get('allocated_inventory', []) for r in report['rooms']}
        if len(targets) != len(report['rooms']):
            raise ValueError('Duplicate prototype room in final acceptance')
        for row in final_rows:
            b, f, room = index[row['room_id']]
            if f.level not in report['authorized_levels'].get(b.id, []):
                raise ValueError('Prototype room outside authorized scope')
            if after_review:
                # A local edit may add furnishings. Preserve the prior minima
                # and check that every currently requested item was compiled.
                expected = {kind: max(minimum, scene.metadata.get(kind, {}).get(room.id, {}).get('requested', 0))
                            for kind, minimum in row['expected_inventory'].items()}
                row = {**row, 'major_count': max(row['major_count'], len(room.object_ids)),
                       'expected_inventory': expected}
            checks = verify_room(scene, b, f, room, row)
            evidence = {'room_id': room.id, 'building_id': b.id, 'function': room.function, 'checks': checks,
                        'source': row.get('source', 'prototype')}
            if has_target:
                evidence['service'] = room_service(b, f, room, targets.get(room.id, []))
            rows.append(evidence)
        detailed = {row['room_id'] for row in rows}
        if any(o.room_id not in detailed for o in city.iter_objects()):
            raise ValueError('Unplanned furniture outside detailed room budget')
        return {'ok': True, 'rooms': rows, 'furnishing_coverage': coverage(report, rows, city) if has_target else None, 'physics_runtime_tested': False, 'vlm_reviewed': False}
