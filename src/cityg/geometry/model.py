"""Typed intermediate representation for Phase 2 geometry and simulation data."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Vec3:
    x: float
    y: float
    z: float


@dataclass(frozen=True)
class MaterialSpec:
    id: str
    display_color: tuple[float, float, float]
    roughness: float = 0.7
    metallic: float = 0.0
    opacity: float = 1.0
    base_color_path: str | None = None
    normal_path: str | None = None
    roughness_path: str | None = None
    ambient_occlusion_path: str | None = None
    source: str = "internal"
    license_id: str = "internal"
    texture_scale_m: float | None = None


@dataclass
class GeometryPrimitive:
    id: str
    owner_id: str
    primitive_type: str
    center: Vec3
    size: Vec3
    rotation_z_deg: float
    semantic_class: str
    material_id: str
    layer_id: str
    lod: int = 0
    collision_enabled: bool = True
    body_type: str = "static"
    instance_key: str = "unit_box"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NavigationNode:
    id: str
    owner_id: str
    position: Vec3
    node_type: str
    level: int | None = None


@dataclass(frozen=True)
class NavigationEdge:
    id: str
    start_node_id: str
    end_node_id: str
    distance_m: float
    width_m: float
    traversal: str = "walk"
    condition_state_machine_id: str | None = None
    bridge_id: str | None = None


@dataclass
class NavigationGraph:
    nodes: list[NavigationNode] = field(default_factory=list)
    edges: list[NavigationEdge] = field(default_factory=list)


@dataclass(frozen=True)
class StateTransition:
    action: str
    from_state: str
    to_state: str
    duration_s: float


@dataclass
class InteractionStateMachine:
    id: str
    owner_id: str
    state_type: str
    initial_state: str
    states: dict[str, dict[str, Any]]
    transitions: list[StateTransition]
    persistent: bool = True


@dataclass(frozen=True)
class LayerDefinition:
    id: str
    owner_id: str
    layer_type: str
    relative_path: str
    load_policy: str
    parent_layer_id: str | None = None


@dataclass(frozen=True)
class ActivationTier:
    name: str
    description: str
    loaded_layer_types: tuple[str, ...]
    physics_body_types: tuple[str, ...]


@dataclass
class GeometryScene:
    city_id: str
    coordinate_system: str
    materials: list[MaterialSpec] = field(default_factory=list)
    primitives: list[GeometryPrimitive] = field(default_factory=list)
    navigation: NavigationGraph = field(default_factory=NavigationGraph)
    state_machines: list[InteractionStateMachine] = field(default_factory=list)
    layers: list[LayerDefinition] = field(default_factory=list)
    activation_tiers: list[ActivationTier] = field(default_factory=list)
    building_prototypes: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
