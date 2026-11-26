"""Shortest-path queries over the simulator-neutral navigation graph."""

from __future__ import annotations

import heapq
from collections import defaultdict

from cityg.geometry.model import NavigationGraph
from cityg.runtime.interaction import InteractionRuntime


class NavigationQuery:
    def __init__(self, graph: NavigationGraph) -> None:
        self.graph = graph
        self.nodes = {node.id: node for node in graph.nodes}
        self.adjacency = defaultdict(list)
        for edge in graph.edges:
            self.adjacency[edge.start_node_id].append((edge.end_node_id, edge))
            self.adjacency[edge.end_node_id].append((edge.start_node_id, edge))

    def shortest_path(
        self,
        start_node_id: str,
        end_node_id: str,
        *,
        runtime: InteractionRuntime | None = None,
        allow_interaction: bool = True,
    ) -> tuple[float, tuple[str, ...]] | None:
        if start_node_id not in self.nodes or end_node_id not in self.nodes:
            raise ValueError("Unknown navigation node")
        queue = [(0.0, start_node_id, ())]
        best = {start_node_id: 0.0}
        while queue:
            cost, current, prefix = heapq.heappop(queue)
            if cost != best.get(current):
                continue
            path = prefix + (current,)
            if current == end_node_id:
                return cost, path
            for neighbor, edge in self.adjacency[current]:
                condition = edge.condition_state_machine_id
                if condition and runtime is not None and not allow_interaction:
                    state = runtime.current_states[condition]
                    if not runtime.machines[condition].states[state].get("nav_passable", False):
                        continue
                next_cost = cost + edge.distance_m
                if next_cost < best.get(neighbor, float("inf")):
                    best[neighbor] = next_cost
                    heapq.heappush(queue, (next_cost, neighbor, path))
        return None
