"""CPU-only structural, navigation, collision and interaction checks."""

from __future__ import annotations

import math
from collections import Counter, defaultdict, deque

from cityg.ccwp import entity_index, point_segment_distance
from cityg.geometry.model import GeometryScene
from cityg.schemas import City, Point2D
from cityg.validation import ValidationReport


class GeometryValidator:
    """Validate the neutral geometry before any simulator-specific compilation."""

    def validate(self, city: City, scene: GeometryScene) -> ValidationReport:
        report = ValidationReport()
        entities = entity_index(city)
        materials = {material.id for material in scene.materials}
        layers = {layer.id: layer for layer in scene.layers}
        state_machines = {machine.id: machine for machine in scene.state_machines}

        self._check_unique_ids(
            report, "geometry_primitive", [item.id for item in scene.primitives]
        )
        self._check_unique_ids(report, "material", [item.id for item in scene.materials])
        self._check_unique_ids(report, "layer", [item.id for item in scene.layers])
        self._check_unique_ids(
            report, "navigation_node", [item.id for item in scene.navigation.nodes]
        )
        self._check_unique_ids(
            report, "navigation_edge", [item.id for item in scene.navigation.edges]
        )
        self._check_unique_ids(
            report, "state_machine", [item.id for item in scene.state_machines]
        )

        for primitive in scene.primitives:
            if primitive.primitive_type == "path_mesh":
                vertices = primitive.metadata.get("mesh_vertices", [])
                faces = primitive.metadata.get("mesh_triangles", [])
                valid = bool(vertices and faces) and all(
                    isinstance(p, (list, tuple)) and len(p) == 3
                    and all(isinstance(v, (int, float)) and math.isfinite(v) for v in p)
                    for p in vertices
                ) and all(
                    isinstance(face, (list, tuple)) and len(face) == 3
                    and all(isinstance(i, int) and 0 <= i < len(vertices) for i in face)
                    and len(set(face)) == 3 for face in faces
                )
                if not valid:
                    report.add("error", "invalid_path_mesh", "Path mesh has invalid vertices or triangles", primitive.id)
            values = (
                primitive.center.x,
                primitive.center.y,
                primitive.center.z,
                primitive.size.x,
                primitive.size.y,
                primitive.size.z,
                primitive.rotation_z_deg,
            )
            if not all(math.isfinite(value) for value in values):
                report.add(
                    "error", "non_finite_geometry", "Primitive contains non-finite values", primitive.id
                )
            if min(primitive.size.x, primitive.size.y, primitive.size.z) <= 0:
                report.add(
                    "error", "invalid_primitive_size", "Primitive size must be positive", primitive.id
                )
            if primitive.owner_id not in entities:
                report.add(
                    "error", "invalid_geometry_owner", "Primitive owner does not exist", primitive.id
                )
            if primitive.material_id not in materials:
                report.add(
                    "error", "missing_material", "Primitive material is not registered", primitive.id
                )
            if primitive.layer_id not in layers:
                report.add(
                    "error", "missing_geometry_layer", "Primitive layer is not registered", primitive.id
                )
            if primitive.body_type not in {"static", "articulated", "dynamic", "kinematic"}:
                report.add(
                    "error", "invalid_body_type", "Unknown physics body type", primitive.id
                )
            if primitive.body_type == "articulated":
                machine_id = primitive.metadata.get("state_machine_id")
                if machine_id not in state_machines:
                    report.add(
                        "error",
                        "missing_interaction_state",
                        "Articulated primitive requires a state machine",
                        primitive.id,
                    )
                if float(primitive.metadata.get("mass_kg", 0.0)) <= 0:
                    report.add(
                        "error",
                        "invalid_articulated_mass",
                        "Articulated primitive requires positive mass",
                        primitive.id,
                    )

        self._validate_layers(scene, report)
        self._validate_state_machines(scene, entities, report)
        path_ratio = self._validate_navigation(city, scene, entities, state_machines, report)
        self._validate_required_geometry(city, scene, report)
        from cityg.geometry.envelopes import validate_envelope_geometry
        validate_envelope_geometry(city, scene, report)
        self._validate_streetscape(city, scene, report)
        if city.rivers or city.bridges:
            from cityg.validation.geography import validate_geography_geometry
            validate_geography_geometry(city, scene, report)

        layer_types = {layer.id: layer.layer_type for layer in scene.layers}
        overview_types = {"roads", "building_shell"}
        overview_count = sum(
            layer_types.get(primitive.layer_id) in overview_types
            for primitive in scene.primitives
        )
        full_count = len(scene.primitives)
        report.metrics = {
            "primitive_count": full_count,
            "collision_primitive_count": sum(
                primitive.collision_enabled for primitive in scene.primitives
            ),
            "articulated_body_count": sum(
                primitive.body_type == "articulated" for primitive in scene.primitives
            ),
            "state_machine_count": len(scene.state_machines),
            "elevator_controller_count": sum(
                machine.state_type == "elevator_controller"
                for machine in scene.state_machines
            ),
            "navigation_node_count": len(scene.navigation.nodes),
            "navigation_edge_count": len(scene.navigation.edges),
            "outdoor_to_room_path_ratio": path_ratio,
            "exterior_only_building_count": len(scene.metadata.get("exterior_only_building_ids", [])),
            "indoor_navigation_evaluated_room_count": sum(n.node_type in {"room", "corridor"} for n in scene.navigation.nodes),
            "curtain_wall_panel_count": sum(p.metadata.get("panel_count",1) for p in scene.primitives if p.semantic_class == "curtain_wall_glass"),
            "overview_primitive_count": overview_count,
            "full_to_overview_primitive_ratio": (
                full_count / overview_count if overview_count else None
            ),
            "building_prototype_count": len(set(scene.building_prototypes.values())),
            "massing_clipped_interior_wall_count": sum(
                primitive.semantic_class == "interior_wall"
                and bool(primitive.metadata.get("massing_clipped"))
                for primitive in scene.primitives
            ),
            "massing_conformed_detail_count": sum(
                primitive.semantic_class
                in {
                    "door",
                    "stair_tread",
                    "elevator_shaft",
                    "elevator_cabin",
                    "elevator_landing_door",
                }
                and bool(primitive.metadata.get("massing_conformed"))
                for primitive in scene.primitives
            ),
            "furnishing_object_count": sum(1 for _ in city.iter_objects()),
            "furnishing_primitive_count": sum(
                primitive.semantic_class.startswith("furniture_")
                for primitive in scene.primitives
            ),
            "facade_primitive_count": sum(
                primitive.semantic_class.startswith(("facade_", "storefront_", "balcony_"))
                or primitive.semantic_class == "entrance_portal"
                for primitive in scene.primitives
            ),
            "facade_window_count": sum(
                primitive.semantic_class in {"facade_window", "storefront_window"}
                for primitive in scene.primitives
            ),
            "balcony_count": sum(
                primitive.semantic_class == "balcony_slab"
                for primitive in scene.primitives
            ),
            "massing_fitted_furnishing_primitive_count": sum(
                primitive.semantic_class.startswith("furniture_")
                and bool(primitive.metadata.get("massing_fitted"))
                for primitive in scene.primitives
            ),
            "furnished_room_ratio": (
                sum(bool(room.object_ids) for room in city.iter_rooms() if room.function != "corridor")
                / max(1, sum(room.function != "corridor" for room in city.iter_rooms()))
            ),
            "max_building_floor_count": max(
                (len(building.floors) for building in city.iter_buildings()),
                default=0,
            ),
            "highrise_building_count": sum(
                bool(building.metadata.get("highrise", {}).get("enabled"))
                for building in city.iter_buildings()
            ),
            "planned_highrise_building_count": sum(
                bool(building.metadata.get("height_contract", {}).get("highrise"))
                for building in city.iter_buildings()
            ),
            "highrise_massing_variant_histogram": dict(
                sorted(
                    Counter(
                        building.metadata.get("highrise", {}).get("massing_variant")
                        for building in city.iter_buildings()
                        if building.metadata.get("highrise", {}).get("enabled")
                    ).items()
                )
            ),
            "typical_floor_count": sum(
                bool(floor.metadata.get("is_typical_floor"))
                for floor in city.iter_floors()
            ),
            "floor_template_count": len(
                {
                    floor.metadata.get("template_id")
                    for floor in city.iter_floors()
                    if floor.metadata.get("template_id")
                }
            ),
            "landmark_building_count": sum(
                bool(building.metadata.get("height_contract", {}).get("landmark"))
                for building in city.iter_buildings()
            ),
            "street_tree_count": sum(
                item.semantic_class in {"street_tree_trunk", "street_tree_asset"}
                for item in scene.primitives
            ),
            "vehicle_snapshot_count": sum(
                item.semantic_class in {"vehicle_body", "vehicle_asset", "street_asset"}
                and item.metadata.get("population_role") == "vehicle"
                for item in scene.primitives
            ),
            "pedestrian_snapshot_count": sum(
                item.semantic_class in {"pedestrian_body", "pedestrian_asset", "street_asset"}
                and item.metadata.get("population_role") == "pedestrian"
                for item in scene.primitives
            ),
            "crosswalk_stripe_count": sum(
                item.semantic_class == "crosswalk" for item in scene.primitives
            ),
            "landscape_shrub_count": sum(
                item.semantic_class == "landscape_shrub" for item in scene.primitives
            ),
            "resolved_outdoor_asset_instance_count": sum(
                bool(item.metadata.get("resolved_asset"))
                and bool(item.metadata.get("outdoor_slot"))
                for item in scene.primitives
            ),
            "resolved_outdoor_asset_unique_count": len(
                {
                    item.metadata.get("asset_id")
                    for item in scene.primitives
                    if item.metadata.get("resolved_asset")
                    and item.metadata.get("outdoor_slot")
                    and item.metadata.get("asset_id")
                }
            ),
            "procedural_streetscape_fallback_count": int(
                scene.metadata.get("streetscape_stats", {}).get(
                    "procedural_outdoor_fallback_count", 0
                )
            ),
        }
        return report

    @staticmethod
    def _validate_streetscape(city: City, scene: GeometryScene, report: ValidationReport) -> None:
        roads = {item.id: item for item in city.road_network.segments}
        roadside_parcels = {p.id:p for p in city.iter_parcels()}
        planting_beds = {p.id:p for p in scene.primitives if p.semantic_class == "street_planting_bed"}
        for primitive in scene.primitives:
            road_id = primitive.metadata.get("road_id")
            if not road_id:
                continue
            road = roads.get(str(road_id))
            if road is None:
                report.add(
                    "error", "streetscape_missing_road",
                    "A streetscape primitive references a missing road", primitive.id,
                )
                continue
            distance = point_segment_distance(
                Point2D(primitive.center.x, primitive.center.y), road.centerline
            )
            role = primitive.metadata.get("population_role")
            if role == "vehicle" and distance > road.width_m / 2 + 0.25:
                report.add(
                    "error", "vehicle_outside_road",
                    "A vehicle snapshot must remain bound to its road lanes", primitive.id,
                )
            cycle_bound = bool(primitive.metadata.get("cycle_lane_bound"))
            pedestrian_in_sidewalk = (
                road.width_m / 2 - 0.25
                <= distance
                <= road.width_m / 2 + road.sidewalk_width_m + 0.35
            )
            pedestrian_in_cycle_lane = cycle_bound and distance <= road.width_m / 2 + 0.35
            if role == "pedestrian" and not (pedestrian_in_sidewalk or pedestrian_in_cycle_lane):
                report.add(
                    "error", "pedestrian_outside_sidewalk",
                    "A pedestrian snapshot must remain on a sidewalk or declared cycle lane", primitive.id,
                )
            if (primitive.metadata.get("street_asset") == "tree"
                    and primitive.metadata.get("placement_domain") == "parcel_roadside"):
                # Street-facing green belts are not sidewalk furniture strips.
                # Require a real parcel owner and the whole canopy to stay out
                # of the road corridor; a metadata flag alone is insufficient.
                from cityg.polygons import parcel_shape, road_shape
                from cityg.geometry.geography import primitive_footprint
                parcel = roadside_parcels.get(primitive.owner_id)
                footprint = primitive_footprint(primitive)
                outer = road.width_m/2 + road.sidewalk_width_m
                if (parcel is None or not parcel.buildings
                        or not outer + .65 <= distance <= outer + 9 + 1e-6
                        or not parcel_shape(parcel).buffer(1e-7).covers(footprint)
                        or footprint.intersects(road_shape(road, .65))):
                    report.add(
                        "error", "roadside_tree_outside_greenbelt",
                        "A roadside tree must fit its occupied parcel within 9 m outside the street/sidewalk corridor",
                        primitive.id,
                    )
            elif primitive.metadata.get("placement_domain") == "street_planting_verge":
                bed = planting_beds.get(primitive.metadata.get("planting_bed_id"))
                outer = road.width_m / 2 + road.sidewalk_width_m
                if (bed is None or bed.owner_id != road.id or primitive.owner_id != road.id
                        or not outer <= distance <= outer + 3.1
                        or math.hypot(primitive.center.x-bed.center.x,
                                      primitive.center.y-bed.center.y) > bed.size.x/2
                        or not city.bounds.contains_point(Point2D(bed.center.x, bed.center.y))):
                    report.add("error", "invalid_street_planting_verge",
                               "Roadside planting needs an adjacent, matching ground bed", primitive.id)
            elif primitive.metadata.get("street_asset") == "tree" and not (
                road.width_m / 2 - 0.25
                <= distance
                <= road.width_m / 2 + road.sidewalk_width_m + 0.35
            ):
                report.add(
                    "error", "street_tree_outside_furniture_strip",
                    "A street tree must remain inside the sidewalk furniture strip", primitive.id,
                )

    @staticmethod
    def _check_unique_ids(report, label, ids):
        for item_id, count in Counter(ids).items():
            if count > 1:
                report.add(
                    "error",
                    f"duplicate_{label}_id",
                    f"Duplicate {label} ID appears {count} times",
                    item_id,
                )

    @staticmethod
    def _validate_layers(scene, report):
        layers = {layer.id: layer for layer in scene.layers}
        for layer in scene.layers:
            if layer.parent_layer_id is not None and layer.parent_layer_id not in layers:
                report.add(
                    "error", "missing_parent_layer", "Layer parent does not exist", layer.id
                )
            if not layer.relative_path.endswith(".usda"):
                report.add(
                    "error", "invalid_layer_path", "Phase 2 layer must be ASCII USDA", layer.id
                )
        for layer in scene.layers:
            seen = set()
            current = layer.id
            while current is not None:
                if current in seen:
                    report.add(
                        "error", "layer_cycle", "Layer parent graph contains a cycle", layer.id
                    )
                    break
                seen.add(current)
                current = layers[current].parent_layer_id if current in layers else None

    @staticmethod
    def _validate_state_machines(scene, entities, report):
        for machine in scene.state_machines:
            if machine.owner_id not in entities:
                report.add(
                    "error", "invalid_state_owner", "State machine owner does not exist", machine.id
                )
            if machine.initial_state not in machine.states:
                report.add(
                    "error", "invalid_initial_state", "Initial state is not declared", machine.id
                )
            for transition in machine.transitions:
                if (
                    transition.from_state not in machine.states
                    or transition.to_state not in machine.states
                    or transition.duration_s <= 0
                ):
                    report.add(
                        "error",
                        "invalid_state_transition",
                        "Transition references invalid states or duration",
                        machine.id,
                    )

    @staticmethod
    def _validate_navigation(city, scene, entities, state_machines, report):
        interiors_compiled = bool(scene.metadata.get("interiors_compiled", True))
        nodes = {node.id: node for node in scene.navigation.nodes}
        adjacency: dict[str, set[str]] = defaultdict(set)
        for node in nodes.values():
            if node.owner_id not in entities:
                report.add(
                    "error", "invalid_navigation_owner", "Navigation owner does not exist", node.id
                )
        for edge in scene.navigation.edges:
            if edge.start_node_id not in nodes or edge.end_node_id not in nodes:
                report.add(
                    "error", "dangling_navigation_edge", "Navigation edge endpoint is missing", edge.id
                )
                continue
            if edge.distance_m < 0 or edge.width_m <= 0:
                report.add(
                    "error", "invalid_navigation_edge", "Navigation cost/width is invalid", edge.id
                )
            if (
                edge.condition_state_machine_id is not None
                and edge.condition_state_machine_id not in state_machines
            ):
                if interiors_compiled:
                    report.add(
                        "error",
                        "missing_navigation_condition",
                        "Navigation edge state machine is missing",
                        edge.id,
                    )
            adjacency[edge.start_node_id].add(edge.end_node_id)
            adjacency[edge.end_node_id].add(edge.start_node_id)

        outdoors = [node.id for node in nodes.values() if node.node_type == "outdoor_junction"]
        rooms = [node.id for node in nodes.values() if node.node_type in {"room", "corridor"}]
        from cityg.envelopes import envelope_config
        exterior_ids = {b.id for b in city.iter_buildings() if envelope_config(b)}
        from cityg.planning.interior_scope import floor_enabled
        expected_room_owners = {r.id for b in city.iter_buildings() if b.id not in exterior_ids
                                for f in b.floors if floor_enabled(city,b,f) for r in f.rooms}
        actual_room_owners = {nodes[node_id].owner_id for node_id in rooms}
        if expected_room_owners != actual_room_owners:
            report.add(
                "error",
                "navigation_room_coverage",
                "Navigation graph does not cover every room exactly",
                city.id,
            )
        exterior_targets = [n.id for n in nodes.values() if n.node_type == "exterior_door"]
        if exterior_ids != {nodes[n].owner_id for n in exterior_targets}:
            report.add("error", "exterior_entrance_coverage", "Exterior-only buildings require realized entrance nodes", city.id)
        shell_ids = {b.id for b in city.iter_buildings()
                     if not any(floor_enabled(city,b,f) for f in b.floors)}
        shell_targets = [n.id for n in nodes.values()
                         if n.node_type == 'building_entrance' and n.owner_id in shell_ids]
        if shell_ids != {nodes[key].owner_id for key in shell_targets}:
            report.add('error','missing_shell_entrance','Inactive interiors require a building entrance',city.id)
        if not outdoors or not (rooms or exterior_targets or shell_targets):
            report.add('error','empty_navigation_graph','Navigation requires streets and building destinations',city.id)
            return 0.0

        reached = {outdoors[0]}
        queue = deque([outdoors[0]])
        while queue:
            current = queue.popleft()
            for neighbor in adjacency[current] - reached:
                reached.add(neighbor)
                queue.append(neighbor)
        if any(n not in reached for n in [*exterior_targets, *shell_targets]):
            report.add("error", "unreachable_exterior_entrance", "Exterior entrance disconnected from streets", city.id)
        report.metrics["exterior_only_building_count"] = len(exterior_ids)
        report.metrics["indoor_navigation_evaluated_room_count"] = len(rooms)
        reachable_rooms = sum(room in reached for room in rooms)
        ratio = reachable_rooms / len(rooms) if rooms else None
        if ratio is not None and ratio < 0.95:
            report.add(
                "error",
                "insufficient_outdoor_room_paths",
                f"Only {ratio:.3f} of rooms are reachable from outdoors",
                city.id,
            )
        return ratio

    @staticmethod
    def _validate_required_geometry(city, scene, report):
        interiors_compiled = bool(scene.metadata.get("interiors_compiled", True))
        semantics_by_owner: dict[str, set[str]] = defaultdict(set)
        for primitive in scene.primitives:
            semantics_by_owner[primitive.owner_id].add(primitive.semantic_class)
        for road in city.road_network.segments:
            if "road_surface" not in semantics_by_owner[road.id]:
                report.add(
                    "error", "missing_road_geometry", "Road has no surface geometry", road.id
                )
        for building in city.iter_buildings():
            # Whole-height visual massing belongs to the Building entity;
            # per-floor shell slices and slabs belong to Floor entities.
            building_semantics = set(semantics_by_owner[building.id])
            for floor in building.floors:
                building_semantics.update(semantics_by_owner[floor.id])
                from cityg.planning.interior_scope import floor_enabled
                if not floor_enabled(city,building,floor):
                    continue
                if interiors_compiled and "floor_slab" not in semantics_by_owner[floor.id]:
                    report.add(
                        "error", "missing_floor_slab", "Floor has no slab geometry", floor.id
                    )
                for door in floor.doors if interiors_compiled else ():
                    open_pairs = {frozenset(pair) for pair in floor.metadata.get('spatial_layout', {}).get('open_boundaries', [])}
                    expected = ('open_passage' if not door.interactive and
                                frozenset((door.room_a_id, door.room_b_id)) in open_pairs else 'door')
                    if expected not in semantics_by_owner[door.id]:
                        report.add(
                            "error", "missing_door_geometry", "Door has no geometry", door.id
                        )
                rooms_with_doors = {
                    room_id
                    for door in floor.doors
                    for room_id in (door.room_a_id, door.room_b_id)
                    if room_id
                }
                for room in floor.rooms if interiors_compiled else ():
                    if room.function != "corridor" and room.id not in rooms_with_doors:
                        report.add(
                            "error",
                            "room_without_door",
                            "Non-corridor room has no planned door connection",
                            room.id,
                        )
                for obj in floor.objects if interiors_compiled else ():
                    if not any(
                        semantic.startswith("furniture_")
                        for semantic in semantics_by_owner[obj.id]
                    ):
                        report.add(
                            "error",
                            "missing_furnishing_geometry",
                            "Interior object has no procedural or resolved asset geometry",
                            obj.id,
                        )
            if "exterior_wall" not in building_semantics:
                report.add(
                    "error", "missing_building_shell", "Building has no exterior walls", building.id
                )
            if interiors_compiled and sum(floor_enabled(city,building,f) for f in building.floors) > 1:
                for connector in building.vertical_connectors:
                    required_semantic = (
                        "elevator_cabin"
                        if connector.connector_type == "elevator"
                        else "stair_tread"
                    )
                    if required_semantic not in semantics_by_owner[connector.id]:
                        report.add(
                            "error",
                            "missing_connector_geometry",
                            f"Connector has no {required_semantic} geometry",
                            connector.id,
                        )
