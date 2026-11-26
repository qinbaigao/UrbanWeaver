"""Integrity validation for the CCWP registry and its dependency graph."""

from __future__ import annotations

from collections import Counter, defaultdict

from cityg.ccwp import DependencyGraph, expected_hierarchy
from cityg.schemas import CCWP_SCHEMA_VERSION, NODE_STATUSES, City
from cityg.validation.model import ValidationReport


class CCWPValidator:
    def validate_into(self, city: City, report: ValidationReport) -> None:
        if city.schema_version != CCWP_SCHEMA_VERSION:
            report.add(
                "error",
                "unsupported_in_memory_schema",
                f"Expected in-memory schema {CCWP_SCHEMA_VERSION}",
                city.id,
                constraint_id="ccwp.schema_version",
                violating_entities=(city.id,),
                responsible_ancestor=city.id,
                dependency_path=(city.id,),
                observed_value=city.schema_version,
                required_value=CCWP_SCHEMA_VERSION,
                allowed_patch_scope=city.id,
                suggested_operations=("migrate_manifest",),
            )

        expected = expected_hierarchy(city)
        nodes = city.world_program.nodes
        node_counts = Counter(node.entity_id for node in nodes)
        node_by_id = {node.entity_id: node for node in nodes}
        for node_id, count in sorted(node_counts.items()):
            if count > 1:
                self._registry_error(
                    report,
                    city,
                    "duplicate_world_node",
                    f"CCWP contains {count} nodes for entity {node_id}",
                    node_id,
                    "ccwp.node_identity",
                    count,
                    1,
                    ("remove_duplicate_node",),
                )

        for entity_id, (entity_type, parent_id) in expected.items():
            node = node_by_id.get(entity_id)
            if node is None:
                self._registry_error(
                    report,
                    city,
                    "missing_world_node",
                    "Canonical entity has no CCWP node",
                    entity_id,
                    "ccwp.node_coverage",
                    None,
                    {"entity_type": entity_type, "parent_id": parent_id},
                    ("add_world_node",),
                )
                continue
            if (node.entity_type, node.parent_id) != (entity_type, parent_id):
                self._registry_error(
                    report,
                    city,
                    "world_node_hierarchy_mismatch",
                    "CCWP type or parent does not match the canonical hierarchy",
                    entity_id,
                    "ccwp.hierarchy",
                    {"entity_type": node.entity_type, "parent_id": node.parent_id},
                    {"entity_type": entity_type, "parent_id": parent_id},
                    ("replace_node_parent", "replace_node_type"),
                )
            if node.status not in NODE_STATUSES:
                self._registry_error(
                    report,
                    city,
                    "invalid_node_status",
                    "CCWP node status is not recognized",
                    entity_id,
                    "ccwp.node_status",
                    node.status,
                    sorted(NODE_STATUSES),
                    ("replace_node_status",),
                )
            if node.version < 1:
                self._registry_error(
                    report,
                    city,
                    "invalid_node_version",
                    "CCWP node version must be positive",
                    entity_id,
                    "ccwp.node_version",
                    node.version,
                    ">= 1",
                    ("replace_node_version",),
                )

        for extra_id in sorted(set(node_by_id) - set(expected)):
            self._registry_error(
                report,
                city,
                "orphan_world_node",
                "CCWP node has no canonical entity",
                extra_id,
                "ccwp.node_coverage",
                extra_id,
                None,
                ("remove_world_node",),
            )

        self._validate_registry_references(city, report, node_by_id)
        self._validate_hierarchy_relations(city, report, expected, node_by_id)
        for cycle in DependencyGraph(city).parent_cycles():
            self._registry_error(
                report,
                city,
                "hierarchy_cycle",
                "CCWP parent hierarchy contains a cycle",
                cycle[0],
                "ccwp.acyclic_hierarchy",
                cycle,
                "acyclic parent graph",
                ("replace_node_parent",),
            )

    def _validate_registry_references(self, city, report, nodes) -> None:
        contracts = self._unique_registry(
            city, report, city.world_program.contracts, "contract", "ccwp.contract_identity"
        )
        relations = self._unique_registry(
            city, report, city.world_program.relations, "relation", "ccwp.relation_identity"
        )
        artifacts = self._unique_registry(
            city, report, city.world_program.artifacts, "artifact", "ccwp.artifact_identity"
        )
        provenance = self._unique_registry(
            city,
            report,
            city.world_program.provenance,
            "provenance",
            "ccwp.provenance_identity",
        )

        node_ids = set(nodes)
        # Registries do not change during validation. Materialize these once,
        # rather than copying the entire city registry for every world node.
        contract_ids = set(contracts)
        relation_ids = set(relations)
        artifact_ids = set(artifacts)
        provenance_ids = set(provenance)
        for contract in contracts.values():
            references = {contract.scope_id, *contract.subject_ids}
            missing = sorted(references - node_ids)
            if contract.inherited_from and contract.inherited_from not in contracts:
                missing.append(contract.inherited_from)
            if missing:
                self._registry_error(
                    report,
                    city,
                    "invalid_contract_reference",
                    "Contract references missing nodes or parent contract",
                    contract.scope_id,
                    contract.id,
                    missing,
                    "existing CCWP references",
                    ("replace_contract_reference", "remove_contract"),
                )
            relation_id = contract.parameters.get("relation_id")
            if relation_id is not None and relation_id not in relations:
                self._registry_error(
                    report,
                    city,
                    "missing_contract_relation",
                    "Contract references a relation that is not present",
                    contract.scope_id,
                    contract.id,
                    relation_id,
                    "existing relation ID",
                    ("add_relation", "replace_contract_parameter"),
                )

        for relation in relations.values():
            missing = sorted({relation.source_id, *relation.target_ids} - node_ids)
            if missing:
                self._registry_error(
                    report,
                    city,
                    "invalid_relation_reference",
                    "Relation references missing CCWP nodes",
                    relation.source_id,
                    relation.id,
                    missing,
                    "existing CCWP nodes",
                    ("replace_relation_reference", "remove_relation"),
                )

        for artifact in artifacts.values():
            if artifact.owner_id not in node_ids:
                self._registry_error(
                    report,
                    city,
                    "invalid_artifact_owner",
                    "Artifact owner does not exist",
                    artifact.owner_id,
                    artifact.id,
                    artifact.owner_id,
                    "existing CCWP node",
                    ("replace_artifact_owner", "remove_artifact"),
                )

        for record in provenance.values():
            missing_parents = sorted(set(record.parent_record_ids) - provenance_ids)
            if record.entity_id not in node_ids or missing_parents:
                self._registry_error(
                    report,
                    city,
                    "invalid_provenance_reference",
                    "Provenance references a missing entity or parent record",
                    record.entity_id,
                    record.id,
                    {"entity": record.entity_id, "missing_parents": missing_parents},
                    "existing entity and provenance records",
                    ("replace_provenance_reference", "remove_provenance"),
                )

        for node in nodes.values():
            missing = {
                "contracts": sorted(set(node.contract_ids) - contract_ids),
                "relations": sorted(set(node.relation_ids) - relation_ids),
                "artifacts": sorted(set(node.artifact_ids) - artifact_ids),
                "provenance": sorted(set(node.provenance_ids) - provenance_ids),
            }
            missing = {kind: ids for kind, ids in missing.items() if ids}
            if missing:
                self._registry_error(
                    report,
                    city,
                    "invalid_node_reference",
                    "CCWP node references missing registry entries",
                    node.entity_id,
                    "ccwp.node_references",
                    missing,
                    "existing registry IDs",
                    ("remove_dangling_node_reference",),
                )

        relations_by_source: dict[str, set[str]] = defaultdict(set)
        for relation in relations.values():
            relations_by_source[relation.source_id].add(relation.id)
        contracts_by_entity: dict[str, set[str]] = defaultdict(set)
        for contract in contracts.values():
            for entity_id in {contract.scope_id, *contract.subject_ids}:
                contracts_by_entity[entity_id].add(contract.id)
        artifacts_by_owner: dict[str, set[str]] = defaultdict(set)
        for artifact in artifacts.values():
            artifacts_by_owner[artifact.owner_id].add(artifact.id)

        for node in nodes.values():
            observed = {
                "relations": set(node.relation_ids),
                "contracts": set(node.contract_ids),
                "artifacts": set(node.artifact_ids),
            }
            required = {
                "relations": relations_by_source[node.entity_id],
                "contracts": contracts_by_entity[node.entity_id],
                "artifacts": artifacts_by_owner[node.entity_id],
            }
            if observed != required:
                self._registry_error(
                    report,
                    city,
                    "node_back_reference_mismatch",
                    "CCWP node registry references are not bidirectionally consistent",
                    node.entity_id,
                    "ccwp.bidirectional_references",
                    {key: sorted(value) for key, value in observed.items()},
                    {key: sorted(value) for key, value in required.items()},
                    ("synchronize_node_references",),
                )

    def _validate_hierarchy_relations(self, city, report, expected, nodes) -> None:
        observed: dict[tuple[str, str], int] = Counter()
        for relation in city.world_program.relations:
            if relation.relation_type == "contains" and len(relation.target_ids) == 1:
                observed[(relation.source_id, relation.target_ids[0])] += 1
        required = {
            (parent_id, entity_id)
            for entity_id, (_, parent_id) in expected.items()
            if parent_id is not None
        }
        for edge in sorted(required):
            if observed[edge] != 1:
                parent_id, entity_id = edge
                self._registry_error(
                    report,
                    city,
                    "missing_hierarchy_relation",
                    "Canonical parent-child edge requires exactly one contains relation",
                    entity_id,
                    "ccwp.hierarchy_relations",
                    observed[edge],
                    1,
                    ("add_contains_relation",),
                )
        for edge, count in sorted(observed.items()):
            if edge not in required:
                self._registry_error(
                    report,
                    city,
                    "invalid_hierarchy_relation",
                    "Contains relation does not match canonical hierarchy",
                    edge[1],
                    "ccwp.hierarchy_relations",
                    {"edge": edge, "count": count},
                    "canonical parent-child edge",
                    ("remove_contains_relation", "replace_node_parent"),
                )

    def _unique_registry(self, city, report, items, label, constraint_id):
        counts = Counter(item.id for item in items)
        for item_id, count in sorted(counts.items()):
            if count > 1:
                self._registry_error(
                    report,
                    city,
                    f"duplicate_{label}_id",
                    f"Duplicate {label} ID",
                    city.id,
                    constraint_id,
                    {item_id: count},
                    "unique IDs",
                    (f"rename_{label}", f"remove_{label}"),
                )
        return {item.id: item for item in items}

    @staticmethod
    def _registry_error(
        report,
        city,
        code,
        message,
        entity_id,
        constraint_id,
        observed,
        required,
        operations,
    ):
        graph = DependencyGraph(city)
        responsible = entity_id if entity_id in graph.nodes else city.id
        path = graph.hierarchy_path(city.id, responsible) or [city.id]
        report.add(
            "error",
            code,
            message,
            entity_id,
            constraint_id=constraint_id,
            violating_entities=(entity_id,),
            responsible_ancestor=responsible,
            dependency_path=tuple(path),
            observed_value=observed,
            required_value=required,
            allowed_patch_scope=responsible,
            suggested_operations=tuple(operations),
        )
