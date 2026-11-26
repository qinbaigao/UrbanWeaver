"""Deterministic structural validation for canonical CityG manifests."""

from __future__ import annotations

import math
from collections import defaultdict, deque

from cityg.ccwp import DependencyGraph, closest_point_on_segment, point_segment_distance
from cityg.planning.highrise import HIGHRISE_MASSING_VARIANTS
from cityg.schemas import Bounds2D, City, Floor, Point2D
from cityg.validation.ccwp import CCWPValidator
from cityg.validation.model import ValidationReport


class CityValidator:
    def validate(self, city: City) -> ValidationReport:
        report = ValidationReport()
        self._validate_positive_bounds(city.bounds, city.id, report)
        self._validate_unique_ids(city, report)
        from cityg.urban_requirements import evaluate as evaluate_urban
        try:
            results = evaluate_urban(city)
            report.metrics['urban_requirements'] = results
            for row in results:
                if row['status'] != 'satisfied':
                    report.add('error' if row['strength']=='hard' else 'warning',
                        'urban_spatial_requirement', f"{row['id']}: {row['relation']} unmet",
                        city.id, constraint_id=row['id'], responsible_ancestor=city.id,
                        observed_value=row['checks'], required_value=row['threshold'])
        except (ValueError, KeyError, TypeError) as exc:
            report.add('error', 'invalid_urban_requirements', str(exc), city.id)
        from cityg.morphology import contract_issues
        try:
            for entity, message in contract_issues(city):
                report.add('error', 'morphology_intent_not_realized', message, entity)
        except (ValueError, IndexError, TypeError, KeyError) as error:
            report.add('error', 'invalid_morphology_contract', str(error), city.id)
        if city.rivers or city.bridges or any(p.boundary for p in city.iter_parcels()):
            from cityg.validation.geography import validate_geography
            validate_geography(city, report)
        self._validate_roads(city, report)
        from cityg.planning.road_paths import road_path_issues
        for code, entity, message in road_path_issues(city.road_network.segments, city.iter_buildings()):
            report.add("error", code, message, entity)
        if any(issue.code == "invalid_road_path" for issue in report.issues):
            return report
        self._validate_hierarchy(city, report)
        from cityg.validation.floor_access_contracts import validate_floor_access_contracts
        validate_floor_access_contracts(city, report)
        self._validate_building_access_relations(city, report)
        self._validate_end_to_end_paths(city, report)
        CCWPValidator().validate_into(city, report)
        return report

    @staticmethod
    def _validate_positive_bounds(
        bounds: Bounds2D, entity_id: str, report: ValidationReport
    ) -> None:
        if bounds.width <= 0 or bounds.depth <= 0:
            report.add("error", "invalid_bounds", "Bounds must have positive area", entity_id)

    def _validate_unique_ids(self, city: City, report: ValidationReport) -> None:
        seen: set[str] = set()

        def add(entity_id: str) -> None:
            if entity_id in seen:
                report.add("error", "duplicate_id", f"Duplicate ID: {entity_id}", entity_id)
            seen.add(entity_id)

        add(city.id)
        for item in (*city.rivers, *city.bridges):
            add(item.id)
        for junction in city.road_network.junctions:
            add(junction.id)
        for segment in city.road_network.segments:
            add(segment.id)
        for district in city.districts:
            add(district.id)
            for parcel in district.parcels:
                add(parcel.id)
                for building in parcel.buildings:
                    add(building.id)
                    for connector in building.vertical_connectors:
                        add(connector.id)
                    for floor in building.floors:
                        add(floor.id)
                        for room in floor.rooms:
                            add(room.id)
                        for obj in floor.objects:
                            add(obj.id)
                        for door in floor.doors:
                            add(door.id)

    def _validate_roads(self, city: City, report: ValidationReport) -> None:
        junctions = {item.id: item for item in city.road_network.junctions}
        adjacency: dict[str, set[str]] = defaultdict(set)
        if not junctions:
            report.add("error", "empty_road_network", "Road network has no junctions", city.id)
            return

        for junction in junctions.values():
            if not city.bounds.contains_point(junction.position):
                report.add(
                    "error",
                    "junction_outside_city",
                    "Road junction lies outside city bounds",
                    junction.id,
                )

        for segment in city.road_network.segments:
            if segment.width_m <= 0 or segment.lane_count < 1:
                report.add(
                    "error", "invalid_road", "Road width and lane count must be positive", segment.id
                )
            from cityg.paths import PlanarPath2D
            try:
                path = PlanarPath2D(segment.centerline)
            except ValueError as exc:
                report.add("error", "invalid_road_path", str(exc), segment.id)
                continue
            if any(not city.bounds.contains_point(p) for p in path.points):
                report.add("error", "road_path_outside_city", "Road path leaves city bounds", segment.id)
            if segment.start_junction_id not in junctions or segment.end_junction_id not in junctions:
                report.add(
                    "error", "dangling_road", "Road references a missing junction", segment.id
                )
                continue
            adjacency[segment.start_junction_id].add(segment.end_junction_id)
            adjacency[segment.end_junction_id].add(segment.start_junction_id)

            expected_start = junctions[segment.start_junction_id].position
            expected_end = junctions[segment.end_junction_id].position
            if not self._same_point(segment.centerline[0], expected_start) or not self._same_point(
                segment.centerline[-1], expected_end
            ):
                report.add(
                    "error",
                    "road_endpoint_mismatch",
                    "Road centerline endpoints do not match referenced junctions",
                    segment.id,
                )

        start = next(iter(junctions))
        reached = {start}
        queue = deque([start])
        while queue:
            current = queue.popleft()
            for neighbor in adjacency[current] - reached:
                reached.add(neighbor)
                queue.append(neighbor)
        if len(reached) != len(junctions):
            report.add(
                "error",
                "disconnected_road_network",
                f"Only {len(reached)} of {len(junctions)} junctions are connected",
                city.id,
            )

    def _validate_hierarchy(self, city: City, report: ValidationReport) -> None:
        building_count = 0
        for district in city.districts:
            self._validate_positive_bounds(district.bounds, district.id, report)
            if not city.bounds.contains_bounds(district.bounds):
                report.add(
                    "error", "district_outside_city", "District exceeds city bounds", district.id
                )
            for parcel in district.parcels:
                self._validate_positive_bounds(parcel.bounds, parcel.id, report)
                if not district.bounds.contains_bounds(parcel.bounds):
                    report.add(
                        "error",
                        "parcel_outside_district",
                        "Parcel exceeds district bounds",
                        parcel.id,
                    )
                for building in parcel.buildings:
                    building_count += 1
                    self._validate_positive_bounds(building.footprint, building.id, report)
                    if not parcel.bounds.contains_bounds(building.footprint):
                        report.add(
                            "error",
                            "building_outside_parcel",
                            "Building footprint exceeds parcel bounds",
                            building.id,
                        )
                    if not building.footprint.contains_point(building.entrance):
                        report.add(
                            "error",
                            "invalid_entrance",
                            "Building entrance is not on or inside the footprint",
                            building.id,
                        )
                    self._validate_building(building, report)

        if building_count == 0:
            report.add("error", "empty_city", "City contains no buildings", city.id)

    def _validate_building(self, building, report: ValidationReport) -> None:
        from cityg.architecture import appearance_for_building
        try:
            appearance_for_building(building)
            from cityg.envelopes import envelope_contract
            envelope_contract(building)
        except (ValueError, TypeError) as error:
            report.add("error", "invalid_appearance_plan", str(error), building.id)
        levels = sorted(floor.level for floor in building.floors)
        if levels != list(range(len(building.floors))):
            report.add(
                "error",
                "non_contiguous_floors",
                "Building floor levels must start at zero and be contiguous",
                building.id,
            )

        height_contract = building.metadata.get("height_contract")
        if isinstance(height_contract, dict):
            try:
                minimum = int(height_contract["min_floors"])
                maximum = int(height_contract["max_floors"])
                realized = int(height_contract["realized_floors"])
            except (KeyError, TypeError, ValueError):
                report.add(
                    "error",
                    "invalid_height_contract",
                    "Building height contract is incomplete or malformed",
                    building.id,
                )
            else:
                if not minimum <= len(building.floors) <= maximum:
                    report.add(
                        "error",
                        "height_contract_violation",
                        "Realized building floors exceed the planned height band",
                        building.id,
                    )
                if realized != len(building.floors):
                    report.add(
                        "error",
                        "stale_height_contract",
                        "Height contract realized_floors does not match the building",
                        building.id,
                    )
                if height_contract.get("landmark") and len(building.floors) != int(
                    height_contract.get("recommended_floors", realized)
                ):
                    report.add(
                        "error",
                        "landmark_height_mismatch",
                        "Landmark building must realize its recommended height",
                        building.id,
                    )

        for connector in building.vertical_connectors:
            if connector.connector_type not in {"stairs", "elevator"}:
                report.add(
                    "error",
                    "invalid_connector_type",
                    "Vertical connector must be stairs or elevator",
                    connector.id,
                )
            if connector.connector_type == "elevator" and not connector.interactive:
                report.add(
                    "error",
                    "noninteractive_elevator",
                    "Elevator requires an interactive controller contract",
                    connector.id,
                )
            if not building.footprint.contains_bounds(connector.bounds):
                report.add(
                    "error",
                    "connector_outside_building",
                    "Vertical connector exceeds the building footprint",
                    connector.id,
                )
            if connector.from_level < 0 or connector.to_level >= len(building.floors):
                report.add(
                    "error",
                    "invalid_connector_range",
                    "Vertical connector references invalid floor levels",
                    connector.id,
                )
            corridors = {
                floor.level: next(
                    (room for room in floor.rooms if room.function == "corridor"
                     and room.bounds.contains_bounds(connector.bounds)), None
                )
                for floor in building.floors
                if connector.from_level <= floor.level <= connector.to_level
            }
            misaligned = [
                level
                for level, corridor in corridors.items()
                if corridor is None
                or not corridor.bounds.contains_bounds(connector.bounds)
            ]
            if misaligned:
                report.add(
                    "error",
                    "connector_floor_misalignment",
                    "Vertical connector is not contained by the corridor on every served floor",
                    connector.id,
                    constraint_id=f"contract_vertical_circulation__{building.id}",
                    violating_entities=(connector.id,),
                    responsible_ancestor=building.id,
                    dependency_path=(building.id, connector.id),
                    observed_value={"misaligned_levels": misaligned},
                    required_value="connector bounds contained by every served corridor",
                    allowed_patch_scope=building.id,
                    suggested_operations=("replace_connector_bounds",),
                )

        highrise = building.metadata.get("highrise", {})
        if isinstance(highrise, dict) and highrise.get("enabled"):
            variant = highrise.get("massing_variant")
            if variant not in HIGHRISE_MASSING_VARIANTS:
                report.add(
                    "error",
                    "invalid_highrise_massing_variant",
                    "High-rise massing variant is missing or unsupported",
                    building.id,
                    observed_value=variant,
                    required_value=sorted(HIGHRISE_MASSING_VARIANTS),
                )
            if highrise.get("massing_constraint") != "single_continuous_core":
                report.add(
                    "error",
                    "invalid_highrise_massing_constraint",
                    "High-rise silhouette must preserve one continuous core",
                    building.id,
                )
            stairs = [
                item
                for item in building.vertical_connectors
                if item.connector_type == "stairs"
            ]
            elevators = [
                item
                for item in building.vertical_connectors
                if item.connector_type == "elevator"
            ]
            required_stairs = int(highrise.get("required_stair_count", 2))
            required_elevators = int(highrise.get("required_elevator_count", 1))
            if len(stairs) < required_stairs or len(elevators) < required_elevators:
                report.add(
                    "error",
                    "insufficient_highrise_core",
                    "High-rise core lacks required stairs or elevators",
                    building.id,
                    observed_value={
                        "stairs": len(stairs),
                        "elevators": len(elevators),
                    },
                    required_value={
                        "stairs": required_stairs,
                        "elevators": required_elevators,
                    },
                )
            templates = highrise.get("typical_floor_reuse", [])
            if not templates or any(
                not floor.metadata.get("template_id") for floor in building.floors
            ):
                report.add(
                    "error",
                    "missing_highrise_floor_templates",
                    "High-rise floors require explicit semantic reuse templates",
                    building.id,
                )
        orientation = building.metadata.get("orientation_contract")
        if isinstance(orientation, dict):
            try:
                realized = float(building.metadata["orientation_deg"])
                declared = float(orientation["orientation_deg"])
                street_axis = float(orientation["street_axis_deg"])
                local_axis = float(orientation["local_facade_axis_deg"])
                offset = float(orientation["offset_deg"])
            except (KeyError, TypeError, ValueError):
                report.add(
                    "error",
                    "invalid_orientation_contract",
                    "Building orientation contract is incomplete or malformed",
                    building.id,
                )
            else:
                facade_delta = (
                    local_axis + realized - street_axis + 90.0
                ) % 180.0 - 90.0
                if abs(realized - declared) > 1e-6 or abs(facade_delta - offset) > 1e-5:
                    report.add(
                        "error",
                        "orientation_contract_mismatch",
                        "Building rotation does not realize its frontage contract",
                        building.id,
                    )
                if abs(offset) > 14.0 + 1e-6:
                    report.add(
                        "error",
                        "excessive_contextual_rotation",
                        "Contextual building rotation exceeds the declared bound",
                        building.id,
                    )
                if orientation.get("strict_alignment") and abs(offset) > 1e-6:
                    report.add(
                        "error",
                        "strict_street_alignment_violation",
                        "Core/high-rise building facade must remain street-parallel",
                        building.id,
                    )
                if abs(offset) > 1e-6 and (
                    orientation.get("urban_context") == "urban_core"
                    or building.function
                    not in {"residential", "mixed_use", "public_service"}
                ):
                    report.add(
                        "error",
                        "invalid_contextual_rotation",
                        "Only peripheral living-area buildings may rotate contextually",
                        building.id,
                    )
        if building.floors and building.vertical_connectors:
            max_level = max(floor.level for floor in building.floors)
            covered = set()
            for connector in building.vertical_connectors:
                covered.update(range(connector.from_level, connector.to_level + 1))
            required = set(range(max_level + 1))
            if not required.issubset(covered):
                report.add(
                    "error",
                    "incomplete_vertical_circulation",
                    "Vertical connectors do not cover every building level",
                    building.id,
                    constraint_id=f"contract_vertical_circulation__{building.id}",
                    violating_entities=(building.id,),
                    responsible_ancestor=building.id,
                    dependency_path=(building.id,),
                    observed_value=sorted(covered),
                    required_value=sorted(required),
                    allowed_patch_scope=building.id,
                    suggested_operations=("replace_connector_range", "add_vertical_connector"),
                )

        if len(building.floors) > 1 and not building.vertical_connectors:
            report.add(
                "error",
                "missing_vertical_circulation",
                "Multi-floor building has no stairs or elevator",
                building.id,
            )

        has_exterior_entrance = False
        for floor in building.floors:
            self._validate_floor(building.footprint, floor, report)
            if floor.level == 0:
                has_exterior_entrance = any(door.room_b_id is None for door in floor.doors)
        if not has_exterior_entrance:
            report.add(
                "error", "missing_building_entrance", "Ground floor has no exterior door", building.id
            )

    def _validate_floor(
        self, footprint: Bounds2D, floor: Floor, report: ValidationReport
    ) -> None:
        rooms_by_id = {room.id: room for room in floor.rooms}
        room_ids = set(rooms_by_id)
        if not room_ids:
            report.add("error", "empty_floor", "Floor contains no rooms", floor.id)
            return

        for room in floor.rooms:
            self._validate_positive_bounds(room.bounds, room.id, report)
            if not footprint.contains_bounds(room.bounds):
                report.add(
                    "error", "room_outside_floor", "Room exceeds building footprint", room.id
                )

        objects_by_room: dict[str, list] = defaultdict(list)
        for obj in floor.objects:
            if obj.room_id not in room_ids:
                report.add(
                    "error",
                    "invalid_object_room",
                    "Interior object references a missing room",
                    obj.id,
                )
                continue
            if min(obj.width_m, obj.depth_m, obj.height_m) <= 0:
                report.add(
                    "error",
                    "invalid_object_size",
                    "Interior object dimensions must be positive",
                    obj.id,
                )
            room = rooms_by_id[obj.room_id]
            if not room.bounds.contains_bounds(obj.bounds):
                report.add(
                    "error",
                    "object_outside_room",
                    "Interior object footprint exceeds its room",
                    obj.id,
                    constraint_id=f"contract_furnishing_clearance__{floor.id}",
                    violating_entities=(obj.id, room.id),
                    responsible_ancestor=floor.id,
                    dependency_path=(floor.id, room.id, obj.id),
                    observed_value={
                        "bounds": {
                            "min_x": obj.bounds.min_x,
                            "min_y": obj.bounds.min_y,
                            "max_x": obj.bounds.max_x,
                            "max_y": obj.bounds.max_y,
                        }
                    },
                    required_value="object bounds contained by room bounds",
                    allowed_patch_scope=floor.id,
                    suggested_operations=("move_interior_object", "resize_interior_object"),
                )
            objects_by_room[obj.room_id].append(obj)

        for room in floor.rooms:
            actual = [obj.id for obj in objects_by_room.get(room.id, [])]
            if len(room.object_ids) != len(set(room.object_ids)) or set(room.object_ids) != set(actual):
                report.add(
                    "error",
                    "stale_room_object_index",
                    "Room object_ids do not match the floor object registry",
                    room.id,
                )
            room_objects = objects_by_room.get(room.id, [])
            for index, obj in enumerate(room_objects):
                for other in room_objects[index + 1 :]:
                    if obj.bounds.overlaps_area(other.bounds):
                        report.add(
                            "error",
                            "interior_object_overlap",
                            f"Objects {obj.id} and {other.id} overlap",
                            room.id,
                            constraint_id=f"contract_furnishing_clearance__{floor.id}",
                            violating_entities=(obj.id, other.id),
                            responsible_ancestor=floor.id,
                            dependency_path=(floor.id, room.id),
                            observed_value="overlapping footprints",
                            required_value="non-overlapping object footprints",
                            allowed_patch_scope=floor.id,
                            suggested_operations=("move_interior_object",),
                        )
            for door in floor.doors:
                if room.id not in {door.room_a_id, door.room_b_id}:
                    continue
                distances = {
                    "min_y": abs(door.position.y - room.bounds.min_y),
                    "max_y": abs(door.position.y - room.bounds.max_y),
                    "min_x": abs(door.position.x - room.bounds.min_x),
                    "max_x": abs(door.position.x - room.bounds.max_x),
                }
                side = min(distances, key=distances.get)
                half = door.width_m / 2 + 0.35
                depth = 1.35
                if side == "min_y":
                    clearance = Bounds2D(
                        door.position.x - half,
                        room.bounds.min_y,
                        door.position.x + half,
                        min(room.bounds.max_y, room.bounds.min_y + depth),
                    )
                elif side == "max_y":
                    clearance = Bounds2D(
                        door.position.x - half,
                        max(room.bounds.min_y, room.bounds.max_y - depth),
                        door.position.x + half,
                        room.bounds.max_y,
                    )
                elif side == "min_x":
                    clearance = Bounds2D(
                        room.bounds.min_x,
                        door.position.y - half,
                        min(room.bounds.max_x, room.bounds.min_x + depth),
                        door.position.y + half,
                    )
                else:
                    clearance = Bounds2D(
                        max(room.bounds.min_x, room.bounds.max_x - depth),
                        door.position.y - half,
                        room.bounds.max_x,
                        door.position.y + half,
                    )
                for obj in room_objects:
                    if obj.bounds.overlaps_area(clearance):
                        report.add(
                            "error",
                            "object_blocks_door_clearance",
                            f"Object {obj.id} obstructs the clearance of door {door.id}",
                            obj.id,
                            constraint_id=f"contract_furnishing_clearance__{floor.id}",
                            violating_entities=(obj.id, door.id),
                            responsible_ancestor=floor.id,
                            dependency_path=(floor.id, room.id, obj.id),
                            observed_value="object footprint intersects door clearance",
                            required_value={
                                "door_depth_clearance_m": depth,
                                "door_side_clearance_m": 0.35,
                            },
                            allowed_patch_scope=floor.id,
                            suggested_operations=("move_interior_object",),
                        )

        for index, room in enumerate(floor.rooms):
            for other in floor.rooms[index + 1 :]:
                if room.bounds.overlaps_area(other.bounds):
                    report.add(
                        "error",
                        "room_overlap",
                        f"Rooms {room.id} and {other.id} overlap",
                        floor.id,
                    )

        adjacency: dict[str, set[str]] = defaultdict(set)
        for door in floor.doors:
            if door.room_a_id not in room_ids:
                report.add(
                    "error", "invalid_door_reference", "Door room_a does not exist", door.id
                )
            if door.room_b_id is not None and door.room_b_id not in room_ids:
                report.add(
                    "error", "invalid_door_reference", "Door room_b does not exist", door.id
                )
            if not footprint.contains_point(door.position):
                report.add(
                    "error", "door_outside_floor", "Door lies outside building footprint", door.id
                )
            if door.room_a_id in room_ids and door.room_b_id in room_ids:
                adjacency[door.room_a_id].add(door.room_b_id)
                adjacency[door.room_b_id].add(door.room_a_id)

        start = next((r.id for r in floor.rooms if r.function == 'corridor'), min(room_ids))
        reached = {start}
        queue = deque([start])
        while queue:
            current = queue.popleft()
            for neighbor in adjacency[current] - reached:
                reached.add(neighbor)
                queue.append(neighbor)
        if reached != room_ids:
            report.add(
                "error",
                "disconnected_floor",
                f"{len(room_ids) - len(reached)} rooms are unreachable through doors",
                floor.id,
                violating_entities=tuple(sorted(room_ids - reached)),
                responsible_ancestor=floor.id,
                dependency_path=(floor.id, *sorted(room_ids - reached)),
                observed_value={'unreachable_room_ids':sorted(room_ids - reached)},
                required_value='all floor rooms connected through canonical door endpoints',
                allowed_patch_scope=floor.id,
                suggested_operations=('repair_floor_door_graph',),
            )

    def _validate_building_access_relations(
        self, city: City, report: ValidationReport
    ) -> None:
        roads = {road.id: road for road in city.road_network.segments}
        road_ids = set(roads)
        contracts = {item.id: item for item in city.world_program.contracts}
        for building in city.iter_buildings():
            relations = [
                relation
                for relation in city.world_program.relations
                if relation.relation_type == "accessible_from"
                and relation.source_id == building.id
            ]
            valid = [
                relation
                for relation in relations
                if len(relation.target_ids) == 1 and relation.target_ids[0] in road_ids
            ]
            if len(valid) != 1:
                self._add_counterexample(
                    city,
                    report,
                    code="entrance_not_connected",
                    message="Building requires exactly one valid pedestrian access relation",
                    entity_id=building.id,
                    constraint_id=f"contract_entrance_access__{building.id}",
                    violating=(building.id,),
                    responsible=building.id,
                    observed={"valid_access_relations": len(valid)},
                    required={"valid_access_relations": 1},
                    operations=("add_building_access_relation", "replace_access_road"),
                )
                continue
            relation = valid[0]
            recorded = relation.properties.get("entrance")
            current = {"x": building.entrance.x, "y": building.entrance.y}
            if recorded != current:
                self._add_counterexample(
                    city,
                    report,
                    code="stale_entrance_relation",
                    message="Access relation entrance does not match building geometry",
                    entity_id=building.id,
                    constraint_id=f"contract_entrance_access__{building.id}",
                    violating=(building.id, relation.target_ids[0]),
                    responsible=building.id,
                    observed=recorded,
                    required=current,
                    operations=("update_access_relation", "restore_building_entrance"),
                )

            target_road = roads[relation.target_ids[0]]
            nearest_road = min(
                roads.values(),
                key=lambda road: point_segment_distance(
                    building.entrance, road.centerline
                ),
            )
            actual_distance = point_segment_distance(
                building.entrance, target_road.centerline
            )
            recorded_distance = relation.properties.get("distance_m")
            contract = contracts.get(f"contract_entrance_access__{building.id}")
            max_distance = contract.parameters.get("max_distance_m", 25.0) if contract else 25.0
            closest = closest_point_on_segment(
                building.entrance, target_road.centerline
            )
            outward_normals = self._entrance_outward_normals(
                building.footprint, building.entrance
            )
            direction = (
                closest.x - building.entrance.x,
                closest.y - building.entrance.y,
            )
            faces_road = any(
                normal_x * direction[0] + normal_y * direction[1] > 1e-6
                for normal_x, normal_y in outward_normals
            )
            access_geometry_ok = (
                target_road.id == nearest_road.id
                and actual_distance <= float(max_distance) + 1e-6
                and isinstance(recorded_distance, (int, float))
                and abs(float(recorded_distance) - actual_distance) <= 1e-5
                and faces_road
            )
            if building.metadata.get('group_access'):
                from cityg.planning.group_access import group_access_valid
                access = building.metadata['group_access']
                access_geometry_ok = (group_access_valid(city, building)
                    and relation.properties.get('mode') == 'parcel_pedestrian_route'
                    and target_road.id == access['road_id']
                    and isinstance(recorded_distance, (int,float))
                    and abs(recorded_distance-access['length_m']) < 1e-5)
            if not access_geometry_ok:
                self._add_counterexample(
                    city,
                    report,
                    code="invalid_entrance_access_geometry",
                    message="Entrance access must use the nearest road, face outward, and satisfy distance budget",
                    entity_id=building.id,
                    constraint_id=f"contract_entrance_access__{building.id}",
                    violating=(building.id, target_road.id),
                    responsible=building.id,
                    observed={
                        "target_road": target_road.id,
                        "nearest_road": nearest_road.id,
                        "distance_m": actual_distance,
                        "recorded_distance_m": recorded_distance,
                        "faces_road": faces_road,
                    },
                    required={
                        "target_road": nearest_road.id,
                        "max_distance_m": max_distance,
                        "faces_road": True,
                    },
                    operations=("update_access_relation", "replace_building_entrance"),
                )

            orientation = building.metadata.get("orientation_contract", {})
            if isinstance(orientation, dict) and orientation:
                from cityg.paths import PlanarPath2D
                path = PlanarPath2D(target_road.centerline)
                actual_street_axis = path.heading(path.project(building.entrance).distance) % 180.0
                recorded_axis = float(
                    orientation.get("street_axis_deg", float("nan"))
                )
                axis_delta = (
                    recorded_axis - actual_street_axis + 90.0
                ) % 180.0 - 90.0
                if (
                    orientation.get("frontage_road_id") != target_road.id
                    or not math.isfinite(recorded_axis)
                    or abs(axis_delta) > 1e-5
                ):
                    report.add(
                        "error",
                        "stale_street_orientation",
                        "Orientation contract does not match the actual frontage road",
                        building.id,
                        observed_value={
                            "frontage_road_id": orientation.get(
                                "frontage_road_id"
                            ),
                            "street_axis_deg": orientation.get(
                                "street_axis_deg"
                            ),
                        },
                        required_value={
                            "frontage_road_id": target_road.id,
                            "street_axis_deg": actual_street_axis,
                        },
                    )

            ground = next((floor for floor in building.floors if floor.level == 0), None)
            exterior = (
                [door for door in ground.doors if door.room_b_id is None] if ground else []
            )
            if not any(self._same_point(door.position, building.entrance) for door in exterior):
                self._add_counterexample(
                    city,
                    report,
                    code="entrance_door_mismatch",
                    message="Building entrance and exterior door positions are inconsistent",
                    entity_id=building.id,
                    constraint_id=f"contract_entrance_access__{building.id}",
                    violating=(building.id,) + tuple(door.id for door in exterior),
                    responsible=building.id,
                    observed=[{"x": door.position.x, "y": door.position.y} for door in exterior],
                    required=current,
                    operations=("replace_exterior_door_position", "replace_building_entrance"),
                )

    def _validate_end_to_end_paths(self, city: City, report: ValidationReport) -> None:
        access_by_building = {
            relation.source_id: relation
            for relation in city.world_program.relations
            if relation.relation_type == "accessible_from" and len(relation.target_ids) == 1
        }
        road_ids = {road.id for road in city.road_network.segments}
        for building in city.iter_buildings():
            adjacency: dict[str, set[str]] = defaultdict(set)
            access = access_by_building.get(building.id)
            start = access.target_ids[0] if access and access.target_ids[0] in road_ids else None
            ground = next((floor for floor in building.floors if floor.level == 0), None)
            if start and ground:
                for door in ground.doors:
                    if door.room_b_id is None and self._same_point(
                        door.position, building.entrance
                    ):
                        adjacency[start].add(door.room_a_id)
                        adjacency[door.room_a_id].add(start)

            for floor in building.floors:
                for door in floor.doors:
                    if door.room_b_id is not None:
                        adjacency[door.room_a_id].add(door.room_b_id)
                        adjacency[door.room_b_id].add(door.room_a_id)

            for connector in building.vertical_connectors:
                served_corridors = []
                for floor in building.floors:
                    if connector.from_level <= floor.level <= connector.to_level:
                        corridor = next(
                            (
                                room
                                for room in floor.rooms
                                if room.function == "corridor"
                                and room.bounds.contains_bounds(connector.bounds)
                            ),
                            None,
                        )
                        if corridor:
                            served_corridors.append(corridor.id)
                for first, second in zip(served_corridors, served_corridors[1:]):
                    adjacency[first].add(second)
                    adjacency[second].add(first)

            reached: set[str] = set()
            if start:
                reached.add(start)
                queue = deque([start])
                while queue:
                    current = queue.popleft()
                    for neighbor in adjacency[current] - reached:
                        reached.add(neighbor)
                        queue.append(neighbor)
            room_ids = {room.id for floor in building.floors for room in floor.rooms}
            missing = sorted(room_ids - reached)
            if missing:
                self._add_counterexample(
                    city,
                    report,
                    code="end_to_end_access_failed",
                    message="Some rooms are unreachable from the outdoor road network",
                    entity_id=building.id,
                    constraint_id=f"contract_end_to_end_access__{building.id}",
                    violating=(building.id, *missing),
                    responsible=building.id,
                    observed={"reachable_rooms": len(room_ids) - len(missing)},
                    required={"reachable_rooms": len(room_ids)},
                    operations=(
                        "add_building_access_relation",
                        "repair_floor_door_graph",
                        "repair_vertical_connector",
                    ),
                )

    @staticmethod
    def _add_counterexample(
        city,
        report,
        *,
        code,
        message,
        entity_id,
        constraint_id,
        violating,
        responsible,
        observed,
        required,
        operations,
    ):
        graph = DependencyGraph(city)
        path = graph.hierarchy_path(city.id, responsible) or [city.id, responsible]
        report.add(
            "error",
            code,
            message,
            entity_id,
            constraint_id=constraint_id,
            violating_entities=tuple(violating),
            responsible_ancestor=responsible,
            dependency_path=tuple(path),
            observed_value=observed,
            required_value=required,
            allowed_patch_scope=responsible,
            suggested_operations=tuple(operations),
        )

    @staticmethod
    def _entrance_outward_normals(
        bounds: Bounds2D, point: Point2D, tolerance: float = 1e-6
    ) -> list[tuple[float, float]]:
        normals = []
        if abs(point.x - bounds.min_x) <= tolerance:
            normals.append((-1.0, 0.0))
        if abs(point.x - bounds.max_x) <= tolerance:
            normals.append((1.0, 0.0))
        if abs(point.y - bounds.min_y) <= tolerance:
            normals.append((0.0, -1.0))
        if abs(point.y - bounds.max_y) <= tolerance:
            normals.append((0.0, 1.0))
        return normals

    @staticmethod
    def _same_point(a: Point2D, b: Point2D, tolerance: float = 1e-6) -> bool:
        return abs(a.x - b.x) <= tolerance and abs(a.y - b.y) <= tolerance
