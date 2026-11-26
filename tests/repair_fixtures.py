"""Deterministic structural error injection for validator regression tests."""

from __future__ import annotations

from copy import deepcopy

from cityg.schemas import Bounds2D, City


ERROR_CASES = {
    "disconnected_entrance": {"entrance_not_connected", "end_to_end_access_failed"},
    "stair_misalignment": {"connector_floor_misalignment", "end_to_end_access_failed"},
    "disconnected_room": {"disconnected_floor", "end_to_end_access_failed"},
    "dangling_relation": {"invalid_relation_reference"},
    "duplicate_entity_id": {"duplicate_id", "orphan_world_node"},
}
ERROR_VARIANTS_PER_CASE = 6


def inject_error(city: City, case: str, variant: int = 0) -> City:
    """Return an invalid copy with exactly one named mutation family injected."""

    if case not in ERROR_CASES:
        raise ValueError(f"Unknown error case: {case}")
    result = deepcopy(city)

    if case == "disconnected_entrance":
        buildings = list(result.iter_buildings())
        building = buildings[variant % len(buildings)]
        relation = next(
            item
            for item in result.world_program.relations
            if item.relation_type == "accessible_from" and item.source_id == building.id
        )
        result.world_program.relations.remove(relation)
        node = next(
            item for item in result.world_program.nodes if item.entity_id == building.id
        )
        node.relation_ids.remove(relation.id)
        return result

    if case == "stair_misalignment":
        buildings = [item for item in result.iter_buildings() if item.vertical_connectors]
        building = buildings[variant % len(buildings)]
        connector = building.vertical_connectors[0]
        width = min(1.0, building.footprint.width / 4)
        depth = min(1.0, building.footprint.depth / 8)
        connector.bounds = Bounds2D(
            building.footprint.center.x - width / 2,
            building.footprint.max_y - 2 * depth,
            building.footprint.center.x + width / 2,
            building.footprint.max_y - depth,
        )
        return result

    if case == "disconnected_room":
        floors = [floor for floor in result.iter_floors() if any(
            door.room_b_id is not None for door in floor.doors
        )]
        floor = floors[variant % len(floors)]
        door = next(item for item in floor.doors if item.room_b_id is not None)
        door.room_b_id = None
        return result

    if case == "dangling_relation":
        relation = result.world_program.relations[
            variant % len(result.world_program.relations)
        ]
        relation.target_ids[0] = "missing_entity_for_regression"
        return result

    floors = [floor for floor in result.iter_floors() if len(floor.rooms) > 1]
    floor = floors[variant % len(floors)]
    floor.rooms[1].id = floor.rooms[0].id
    return result


def error_regression_suite(city: City):
    """Yield 30 stable ``(name, expected_codes, invalid_city)`` regression cases."""

    for case, expected_codes in ERROR_CASES.items():
        for variant in range(ERROR_VARIANTS_PER_CASE):
            yield (
                f"{case}_{variant:02d}",
                expected_codes,
                inject_error(city, case, variant),
            )
