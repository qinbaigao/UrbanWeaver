"""Navigation graph compilation for the deterministic geometry backend."""

from __future__ import annotations

import math

from cityg.ccwp import closest_point_on_segment
from cityg.geometry.model import (
    GeometryScene,
    NavigationEdge,
    NavigationGraph,
    NavigationNode,
    Vec3,
)
from cityg.schemas import City, Point2D
from cityg.paths import PlanarPath2D


class NavigationCompilerMixin:
    """Build the walkable room/building/outdoor navigation graph."""

    def _compile_navigation(self, city: City, scene: GeometryScene) -> NavigationGraph:
        graph = NavigationGraph()
        node_ids: set[str] = set()

        def add_node(node: NavigationNode) -> None:
            if node.id not in node_ids:
                graph.nodes.append(node)
                node_ids.add(node.id)

        junction_nav = {}
        for junction in city.road_network.junctions:
            nav_id = f"nav_{junction.id}"
            junction_nav[junction.id] = nav_id
            add_node(
                NavigationNode(
                    nav_id,
                    junction.id,
                    Vec3(junction.position.x, junction.position.y, 0.05),
                    "outdoor_junction",
                )
            )
        access_relations = {
            relation.source_id: relation
            for relation in city.world_program.relations
            if relation.relation_type == "accessible_from"
        }
        path_access_nodes = {}
        for road in city.road_network.segments:
            bridges = [b for b in city.bridges if b.road_id == road.id]
            if len(road.centerline) > 2 or bridges or any(b.metadata.get('group_access',{}).get('road_id') == road.id for b in city.iter_buildings()):
                path = PlanarPath2D(road.centerline)
                stations = [(0.0, junction_nav[road.start_junction_id]),
                            (path.length, junction_nav[road.end_junction_id])]
                for index, (p, distance) in enumerate(zip(path.points[1:-1], path.stations[1:-1])):
                    node_id = f"nav_{road.id}_path_{index:04d}"
                    add_node(NavigationNode(node_id, road.id, Vec3(p.x, p.y, .05), "outdoor_path"))
                    stations.append((distance, node_id))
                for bridge in bridges:
                    for side, distance in (("start", bridge.start_m), ("end", bridge.end_m)):
                        if any(abs(distance-value) < 1e-6 for value, _ in stations):
                            continue
                        point = path.point(distance)
                        node_id = f"nav_{bridge.id}_{side}"
                        add_node(NavigationNode(node_id, bridge.id, Vec3(point.x, point.y, .05), "bridge_endpoint"))
                        stations.append((distance, node_id))
                for building in city.iter_buildings():
                    relation = access_relations.get(building.id)
                    if relation is None or road.id != relation.target_ids[0]:
                        continue
                    group_access = building.metadata.get('group_access')
                    projected = path.project(Point2D(*group_access['points'][0]) if group_access else building.entrance)
                    # Reuse an existing sampled node when the station matches.
                    node_id = next((node for distance, node in stations
                                    if abs(distance - projected.distance) < 1e-6), None)
                    if node_id is None:
                        node_id = f"nav_{road.id}_access_{building.id}"
                        add_node(NavigationNode(node_id, road.id,
                            Vec3(projected.point.x, projected.point.y, .05), "outdoor_access"))
                        stations.append((projected.distance, node_id))
                    path_access_nodes[building.id] = (node_id, projected.separation)
                stations.sort()
                for index, ((a, na), (b, nb)) in enumerate(zip(stations, stations[1:])):
                    bridge = next((item for item in bridges if item.start_m-1e-6 <= (a+b)/2 <= item.end_m+1e-6), None)
                    graph.edges.append(NavigationEdge(f"nav_edge_{road.id}_{index:04d}", na, nb,
                        b - a, max(.8, road.sidewalk_width_m), "bridge" if bridge else "walk",
                        bridge_id=bridge.id if bridge else None))
                continue
            graph.edges.append(
                NavigationEdge(
                    f"nav_edge_{road.id}",
                    junction_nav[road.start_junction_id],
                    junction_nav[road.end_junction_id],
                    math.hypot(
                        road.centerline[1].x - road.centerline[0].x,
                        road.centerline[1].y - road.centerline[0].y,
                    ),
                    max(0.8, road.sidewalk_width_m),
                    "walk",
                )
            )

        access_relations = {
            relation.source_id: relation
            for relation in city.world_program.relations
            if relation.relation_type == "accessible_from"
        }
        roads = {road.id: road for road in city.road_network.segments}
        for building in city.iter_buildings():
            massing_frame = (
                self._massing_frame(building)
                if building.metadata.get("massing_style")
                else None
            )
            building_top = max(
                floor.elevation_m + floor.height_m for floor in building.floors
            )
            entrance_id = f"nav_entrance_{building.id}"
            add_node(
                NavigationNode(
                    entrance_id,
                    building.id,
                    Vec3(building.entrance.x, building.entrance.y, 0.05),
                    "building_entrance",
                    0,
                )
            )
            relation = access_relations[building.id]
            road = roads[relation.target_ids[0]]
            projection = closest_point_on_segment(building.entrance, road.centerline)
            group_access = building.metadata.get('group_access')
            if group_access:
                previous, _ = path_access_nodes[building.id]
                previous_point = next(n.position for n in graph.nodes if n.id == previous)
                for i, (x,y) in enumerate(group_access['points']):
                    node_id = entrance_id if i == len(group_access['points'])-1 else f'nav_group_{building.id}_{i:03d}'
                    point = Vec3(x,y,.05)
                    if node_id != entrance_id:
                        add_node(NavigationNode(node_id,building.id,point,'outdoor_path'))
                    graph.edges.append(NavigationEdge(f'nav_group_access_{building.id}_{i:03d}',previous,node_id,
                        math.hypot(x-previous_point.x,y-previous_point.y),group_access['width_m'],'walk'))
                    previous, previous_point = node_id, point
            elif building.id in path_access_nodes:
                access_node, distance = path_access_nodes[building.id]
                graph.edges.append(NavigationEdge(f"nav_access_{building.id}_path", access_node,
                                                  entrance_id, distance, 1.2, "walk"))
            for junction_id in (() if building.id in path_access_nodes else (road.start_junction_id, road.end_junction_id)):
                junction = next(
                    item for item in city.road_network.junctions if item.id == junction_id
                )
                distance = math.hypot(
                    building.entrance.x - projection.x,
                    building.entrance.y - projection.y,
                ) + math.hypot(
                    junction.position.x - projection.x,
                    junction.position.y - projection.y,
                )
                graph.edges.append(
                    NavigationEdge(
                        f"nav_access_{building.id}_{junction_id}",
                        junction_nav[junction_id],
                        entrance_id,
                        distance,
                        1.2,
                        "walk",
                    )
                )

            from cityg.envelopes import envelope_config, envelope_contract
            if envelope_config(building):
                contract = envelope_contract(building)
                if contract and contract.get("entrance"):
                    point = contract["entrance"]["point"]
                    endpoint = f"nav_envelope_entrance_{building.id}"
                    add_node(NavigationNode(endpoint, building.id, Vec3(*point), "exterior_door", 0))
                    graph.edges.append(NavigationEdge(f"nav_envelope_access_{building.id}", entrance_id,
                        endpoint, math.hypot(point[0]-building.entrance.x,point[1]-building.entrance.y),1.2,"walk"))
                continue
            room_nodes = {}
            for floor in building.floors:
                from cityg.planning.interior_scope import floor_enabled
                if not floor_enabled(city,building,floor):continue
                for room in floor.rooms:
                    nav_id = f"nav_{room.id}"
                    room_nodes[room.id] = nav_id
                    if massing_frame is not None:
                        floor_frame = self._frame_at_height(
                            massing_frame,
                            floor.elevation_m + 0.05,
                            building_top,
                        )
                        room_x, room_y = self._map_to_massing(
                            building,
                            room.bounds.center.x,
                            room.bounds.center.y,
                            floor_frame,
                            project=True,
                        )
                    else:
                        room_x, room_y = room.bounds.center.x, room.bounds.center.y
                    add_node(
                        NavigationNode(
                            nav_id,
                            room.id,
                            Vec3(room_x, room_y, floor.elevation_m + 0.05),
                            "corridor" if room.function == "corridor" else "room",
                            floor.level,
                        )
                    )
                for door in floor.doors:
                    state = f"state_machine__{door.id}" if door.interactive else None
                    if door.room_b_id is None:
                        start = entrance_id
                        end = room_nodes[door.room_a_id]
                    else:
                        start = room_nodes[door.room_a_id]
                        end = room_nodes[door.room_b_id]
                    graph.edges.append(
                        NavigationEdge(
                            f"nav_door_{door.id}",
                            start,
                            end,
                            self._nav_distance(graph, start, end),
                            self._door_effective_width(floor, door),
                            "door",
                            state,
                        )
                    )

            for connector in building.vertical_connectors:
                served = []
                for floor in building.floors:
                    if connector.from_level <= floor.level <= connector.to_level and floor_enabled(city,building,floor):
                        corridor = next(
                            room for room in floor.rooms if room.function == "corridor"
                            and room.bounds.contains_bounds(connector.bounds)
                        )
                        served.append((floor.level, room_nodes[corridor.id]))
                for (start_level, start), (end_level, end) in zip(served, served[1:]):
                    is_elevator = connector.connector_type == "elevator"
                    if not is_elevator and end_level != start_level + 1:
                        # Stair geometry is compiled only between adjacent
                        # enabled landings; sparse selection is not a shortcut.
                        continue
                    graph.edges.append(
                        NavigationEdge(
                            f"nav_{connector.connector_type}_{connector.id}_{start_level:02d}_{end_level:02d}",
                            start,
                            end,
                            self._nav_distance(graph, start, end),
                            connector.bounds.width,
                            "elevator" if is_elevator else "stairs",
                            f"state_machine__{connector.id}" if is_elevator else None,
                        )
                    )
        return graph

    @staticmethod
    def _nav_distance(graph: NavigationGraph, start_id: str, end_id: str) -> float:
        positions = {node.id: node.position for node in graph.nodes}
        start = positions[start_id]
        end = positions[end_id]
        return math.sqrt(
            (start.x - end.x) ** 2
            + (start.y - end.y) ** 2
            + (start.z - end.z) ** 2
        )
