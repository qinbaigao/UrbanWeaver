"""Multi-resolution layer activation policy."""

from __future__ import annotations

from cityg.geometry.model import GeometryScene, LayerDefinition


class ActivationManager:
    def __init__(self, scene: GeometryScene) -> None:
        self.scene = scene
        self.layers = {layer.id: layer for layer in scene.layers}

    def select(
        self,
        tier: str,
        *,
        building_id: str | None = None,
        floor_id: str | None = None,
    ) -> tuple[LayerDefinition, ...]:
        if tier not in {"overview", "active_building", "active_floor"}:
            raise ValueError(f"Unknown activation tier: {tier}")
        selected = {
            layer.id
            for layer in self.layers.values()
            if layer.layer_type in {"root", "assets", "roads", "district", "building_shell"}
        }
        if tier in {"active_building", "active_floor"}:
            if building_id is None or f"interior:{building_id}" not in self.layers:
                raise ValueError("A known building_id is required for this activation tier")
            selected.add(f"interior:{building_id}")
        if tier == "active_floor":
            if floor_id is None or f"floor:{floor_id}" not in self.layers:
                raise ValueError("A known floor_id is required for active_floor")
            floor_layer = self.layers[f"floor:{floor_id}"]
            if floor_layer.parent_layer_id != f"interior:{building_id}":
                raise ValueError("floor_id does not belong to building_id")
            selected.add(f"floor:{floor_id}")
        return tuple(self.layers[layer_id] for layer_id in sorted(selected))

    def primitive_count(self, selected_layers: tuple[LayerDefinition, ...]) -> int:
        selected_ids = {layer.id for layer in selected_layers}
        return sum(
            primitive.layer_id in selected_ids for primitive in self.scene.primitives
        )
