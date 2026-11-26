"""Compile a canonical CCWP city into deterministic Phase 2 geometry IR."""

from __future__ import annotations

import math
import hashlib
from collections import defaultdict
from dataclasses import replace
from typing import Any

from cityg.assets import AssetRecord, AssetRegistry, MaterialLibrary
from cityg.ccwp import point_segment_distance, segment_intersection
from cityg.geometry.model import (
    ActivationTier,
    GeometryPrimitive,
    GeometryScene,
    InteractionStateMachine,
    LayerDefinition,
    MaterialSpec,
    StateTransition,
    Vec3,
)
from cityg.geometry.primitives import PrimitiveFactoryMixin
from cityg.geometry.parcel_landscape import ParcelLandscapeCompilerMixin
from cityg.geometry.navigation import NavigationCompilerMixin
from cityg.geometry.facades import FacadeProfile, FacadeStyle, facade_profile_for_building
from cityg.geometry.appearance import (
    FacadeAppearanceCompilerMixin, facade_style_for_face, facade_material_style, bay_tangent, face_role,
)
from cityg.facade_runtime import FacadeAssetRuntime, FacadeBuildingAssetPlan, FacadeModuleSelection
from cityg.geometry.streetscape import StreetscapeCompiler
from cityg.geometry.prototypes import (
    BuildingPrototype,
    prototype_by_id,
    prototype_for_function,
)
from cityg.planning.interiors import ASSET_CATALOG, asset_spec
from cityg.planning.highrise import HighRisePolicy
from cityg.schemas import Bounds2D, Building, City, Door, Floor, Point2D
from cityg.planning.appearance import appearance_program_for_city


class GeometryCompiler(
    FacadeAppearanceCompilerMixin, ParcelLandscapeCompilerMixin, PrimitiveFactoryMixin, NavigationCompilerMixin
):
    """Pure-Python, deterministic geometry and navigation compiler."""

    door_height_m = 2.15
    door_thickness_m = 0.08
    stair_steps_per_floor = 10

    def __init__(
        self,
        asset_registry: AssetRegistry | None = None,
        material_library: MaterialLibrary | None = None,
        include_interiors: bool = True,
        facade_asset_index_path: str | None = None,
        facade_asset_project_root: str | None = None,
        facade_asset_cache_root: str | None = None,
        facade_asset_runtime: FacadeAssetRuntime | None = None,
    ) -> None:
        """Create a compiler with optional local asset/material registries.

        Registries are intentionally optional so existing procedural generation
        remains fully offline and backwards compatible.  A record is only used
        as visual geometry when it has a normalized ``geometry_path``; otherwise
        the existing procedural proxy is retained.
        """
        # Keep track of whether the caller explicitly selected an asset
        # registry.  ``self.asset_registry`` is always a usable registry (an
        # empty one is created for offline/procedural tests), so checking it
        # for ``None`` cannot distinguish production renders from legacy
        # proxy-only renders.
        self.asset_registry_configured = asset_registry is not None
        self.asset_registry = asset_registry or AssetRegistry()
        # Register the existing proxy catalog as the built-in, offline seed
        # library.  These records deliberately have no geometry path, so they
        # remain procedural fallbacks until a normalized mesh is curated.
        for spec in ASSET_CATALOG.values():
            if self.asset_registry.get(spec.id) is None:
                self.asset_registry.register(
                    AssetRecord(
                        asset_id=spec.id,
                        category=spec.category,
                        tags=(spec.category, spec.proxy_style, "procedural"),
                        dimensions_m=(spec.width_m, spec.depth_m, spec.height_m),
                        material_id=spec.material_id,
                        source="procedural",
                        license_id="cityg-internal",
                    )
                )
        self.material_library = material_library
        # City-scale previews can keep the canonical rooms in city.json while
        # omitting their geometry.  This avoids loading thousands of walls and
        # furniture instances during broad visual iteration; floor/room modes
        # remain available whenever the compiler is created with this enabled.
        self.include_interiors = bool(include_interiors)
        self.streetscape_compiler = StreetscapeCompiler(self.asset_registry)
        self.streetscape_compiler.asset_registry_configured = (
            self.asset_registry_configured
        )
        self.facade_asset_runtime = facade_asset_runtime
        if self.facade_asset_runtime is None and facade_asset_index_path:
            self.facade_asset_runtime = FacadeAssetRuntime.load(
                facade_asset_index_path,
                self.asset_registry,
                project_root=facade_asset_project_root,
                cache_root=facade_asset_cache_root,
            )

    def compile(
        self,
        city: City,
        *,
        building_ids: set[str] | None = None,
    ) -> GeometryScene:
        """Compile the city into the geometry IR.

        ``building_ids`` is the incremental-compilation hook.  The canonical
        layer graph and materials are emitted, while global road/landscape
        geometry is intentionally skipped and only the requested buildings are
        expanded.  The OpenUSD backend merges that subset with a previous
        self-contained scene.
        """
        scene = GeometryScene(
            city_id=city.id,
            coordinate_system=city.coordinate_system,
            materials=self._materials(),
            activation_tiers=self._activation_tiers(),
        )
        from cityg.envelopes import envelope_config
        exterior_ids = [b.id for b in city.iter_buildings() if envelope_config(b)]
        from cityg.planning.interior_scope import floor_enabled
        active_exterior_ids = [b.id for b in city.iter_buildings()
            if b.id in exterior_ids and (building_ids is None or b.id in building_ids)
            and any(floor_enabled(city,b,f) for f in b.floors)]
        if active_exterior_ids and self.include_interiors:
            raise ValueError("New exterior envelopes require include_interiors=False; polygonal interiors are not implemented")
        scene.metadata["exterior_only_building_ids"] = exterior_ids
        self._define_layers(city, scene)
        appearance = appearance_program_for_city(city)
        if building_ids is None:
            from cityg.geometry.pedestrian_network import complete_sidewalks, connect_actual_doors, network_components, reserve_walkways, sidewalk_plan
            self._compile_roads(city, scene)
            infill_count = complete_sidewalks(city, scene.primitives)
            walk_plan = sidewalk_plan(city, scene.primitives)
            streetscape_stats = self.streetscape_compiler.compile(city, scene, appearance)
            self._compile_landscape(city, scene)
            parcel_landscape_stats = self._compile_parcel_landscape(city, scene)
            if city.rivers or city.bridges or any(p.boundary for p in city.iter_parcels()):
                from cityg.geometry.geography import constrain_ground_geometry, compile_water_and_bridges
                # Reject unsafe input even when callers bypass the pipeline's
                # canonical validation (e.g. in-memory Viewer compilation).
                from cityg.validation.geography import validate_geography
                from cityg.validation import ValidationReport
                geography_report = ValidationReport()
                validate_geography(city, geography_report)
                if not geography_report.ok:
                    raise ValueError(f"Geography validation failed: {geography_report.errors[0].message}")
                constrain_ground_geometry(city, scene)
                compile_water_and_bridges(city, scene)
        else:
            # Global layers are reused by the incremental backend.  Avoid
            # expanding roads, vegetation and parcel dressing in the subset
            # worker; this is the main speedup for room/building edits.
            streetscape_stats = {"compile_scope": "reused_global_layers"}
            parcel_landscape_stats = {"compile_scope": "reused_global_layers"}
        self._compile_buildings(city, scene, building_ids=building_ids)
        from cityg.geometry.residential_groups import compile_attached_envelopes
        compile_attached_envelopes(city, scene)
        from cityg.geometry.facade_colorways import apply_facade_colorways
        apply_facade_colorways(city, scene)
        from cityg.geometry.roof_finishes import apply_roof_finishes
        apply_roof_finishes(city, scene)
        from cityg.geometry.roofscape import compile_roofscape
        compile_roofscape(self, city, scene, building_ids=building_ids)
        from cityg.geometry.roof_textures import apply_roof_textures
        apply_roof_textures(city, scene)
        if building_ids is None:
            from cityg.geometry.residential_groups import compile_group_paths
            if any(b.metadata.get('residential_group') for b in city.iter_buildings()):
                compile_group_paths(self, city, scene)
            from cityg.geometry.parcel_planting import enrich_paved_parcels
            enrich_paved_parcels(self, city, scene)
            from cityg.geometry.parcel_sites import compile_parcel_sites
            compile_parcel_sites(self, city, scene)
            from cityg.geometry.metro_sites import compile_metro_entrances
            compile_metro_entrances(self, city, scene)
            from cityg.geometry.edge_landscape import compile_edge_landscape
            compile_edge_landscape(self, city, scene)
            from cityg.geometry.construction_sites import compile_construction_sites
            compile_construction_sites(self, city, scene)
            from cityg.geometry.parcel_courtyards import compile_parcel_courtyards
            compile_parcel_courtyards(self, city, scene)
            from cityg.geometry.dense_greenery import compile_dense_greenery
            compile_dense_greenery(self, city, scene)
            from cityg.geometry.urban_greenbelts import compile_urban_greenbelts
            compile_urban_greenbelts(self, city, scene)
            from cityg.geometry.street_tree_infill import compile_street_tree_infill
            compile_street_tree_infill(self, city, scene)
        if self.include_interiors:
            from cityg.geometry.room_appearance import compile_room_appearance
            compile_room_appearance(self, city, scene)
            from cityg.geometry.room_decorations import compile_room_decorations
            from cityg.planning.interior_scope import floor_enabled
            for building in city.iter_buildings():
                if building_ids is not None and building.id not in building_ids:
                    continue
                for floor in building.floors:
                    if floor_enabled(city, building, floor):
                        for room in floor.rooms:
                            if room.metadata.get('room_design', {}).get('status') == 'accepted':
                                compile_room_decorations(self, building, floor, room, scene)
        # Size/rotation conformance is finished: fit moving leaves without
        # changing the already compiled openings, wall ends or door headers.
        from cityg.geometry.door_kinematics import fit_door_leaf
        scene.primitives = [fit_door_leaf(p) if p.semantic_class == 'door'
            and p.primitive_type == 'box' else p for p in scene.primitives]
        if building_ids is None:
            frontages = connect_actual_doors(city, scene.primitives)
            adjustments = reserve_walkways(city, scene.primitives, walk_plan)
            scene.metadata["pedestrian_network"] = {
                "sidewalk_infill_count": infill_count,
                "fixture_adjustments": adjustments,
                "entrance_connections": frontages,
                **network_components(scene.primitives, walk_plan[1]),
            }
            streetscape_stats["street_tree_count"] -= adjustments.get("tree_omitted", 0)
            streetscape_stats["street_light_count"] -= adjustments.get("street_light_omitted", 0)
        scene.navigation = self._compile_navigation(city, scene)
        # Facade and streetscape compilers may already have contributed
        # structured metadata; retain it while adding the global metrics.
        scene.metadata.update(self._metadata(scene))
        scene.metadata.update(
            {
                "compile_scope": "full" if building_ids is None else "building_subset",
                "compiled_building_ids": sorted(building_ids) if building_ids is not None else [
                    building.id for building in city.iter_buildings()
                ],
                "urban_appearance_program": appearance.to_dict(),
                "streetscape_stats": streetscape_stats,
                "parcel_landscape_stats": parcel_landscape_stats,
                "asset_registry_count": len(self.asset_registry.list_all()),
                "asset_registry_asset_ids": [
                    record.asset_id for record in self.asset_registry.list_all()
                ],
                "material_library_enabled": self.material_library is not None,
                "facade_asset_system_enabled": self.facade_asset_runtime is not None,
                "facade_asset_runtime_context": ({
                    "index": self.facade_asset_runtime.index.payload,
                    "project_root": str(self.facade_asset_runtime.project_root),
                } if self.facade_asset_runtime is not None else None),
                "environment_path": (
                    str(self.material_library.resolve_path(self.material_library.environment_path))
                    if self.material_library is not None and self.material_library.environment_path
                    else None
                ),
                "interiors_compiled": self.include_interiors,
                "rendering_profile": self._rendering_profile(city),
            }
        )
        return scene

    def _materials(self) -> list[MaterialSpec]:
        materials = [
            MaterialSpec("asphalt", (0.08, 0.09, 0.10), roughness=0.92),
            MaterialSpec("city_ground", (0.30, 0.34, 0.33), roughness=0.98),
            MaterialSpec("road_marking", (0.92, 0.90, 0.76), roughness=0.62),
            MaterialSpec("bike_lane", (0.20, 0.34, 0.30), roughness=0.86),
            MaterialSpec("parking_bay", (0.14, 0.16, 0.17), roughness=0.90),
            MaterialSpec("vehicle_paint", (0.16, 0.20, 0.23), roughness=0.28, metallic=0.45),
            MaterialSpec("sidewalk", (0.48, 0.50, 0.52), roughness=0.85),
            MaterialSpec("paving_furnishing", (0.37, 0.39, 0.39), roughness=0.91),
            MaterialSpec("frontage_retail", (0.57, 0.48, 0.37), roughness=0.82),
            MaterialSpec("frontage_residential", (0.55, 0.53, 0.48), roughness=0.88),
            MaterialSpec("frontage_civic", (0.64, 0.61, 0.54), roughness=0.84),
            MaterialSpec("frontage_industrial", (0.43, 0.45, 0.44), roughness=0.91),
            MaterialSpec("frontage_mixed", (0.51, 0.50, 0.46), roughness=0.88),
            MaterialSpec("concrete", (0.62, 0.63, 0.61), roughness=0.80),
            MaterialSpec("interior_wall", (0.86, 0.84, 0.78), roughness=0.82),
            MaterialSpec("residential_facade", (0.73, 0.55, 0.42), roughness=0.78),
            MaterialSpec(
                "commercial_glass", (0.18, 0.42, 0.58), roughness=0.18, metallic=0.05
            ),
            MaterialSpec("industrial_metal", (0.42, 0.46, 0.48), roughness=0.48),
            MaterialSpec("civic_stone", (0.72, 0.69, 0.62), roughness=0.76),
            MaterialSpec("residential_brick", (0.58, 0.32, 0.22), roughness=0.86),
            MaterialSpec("residential_sage", (0.48, 0.56, 0.48), roughness=0.82),
            MaterialSpec("commercial_teal", (0.13, 0.38, 0.40), roughness=0.24, metallic=0.08),
            MaterialSpec("commercial_smoke", (0.25, 0.31, 0.35), roughness=0.30, metallic=0.12),
            MaterialSpec("civic_limestone", (0.78, 0.72, 0.61), roughness=0.82),
            MaterialSpec("civic_brick", (0.55, 0.27, 0.19), roughness=0.88),
            MaterialSpec("industrial_light", (0.60, 0.64, 0.63), roughness=0.55, metallic=0.24),
            MaterialSpec("facade_glass_blue", (0.12, 0.38, 0.58), roughness=0.16, metallic=0.08),
            MaterialSpec("facade_glass_warm", (0.30, 0.48, 0.52), roughness=0.22, metallic=0.04),
            MaterialSpec("facade_glass_neutral", (0.34, 0.47, 0.50), roughness=0.24, metallic=0.02),
            MaterialSpec("facade_glass_sage", (0.25, 0.43, 0.39), roughness=0.24, metallic=0.03),
            MaterialSpec("facade_glass_teal", (0.05, 0.35, 0.40), roughness=0.14, metallic=0.10),
            MaterialSpec("facade_glass_smoke", (0.22, 0.29, 0.34), roughness=0.20, metallic=0.12),
            MaterialSpec("facade_frame_light", (0.76, 0.72, 0.64), roughness=0.42, metallic=0.12),
            MaterialSpec("facade_frame_dark", (0.12, 0.17, 0.21), roughness=0.35, metallic=0.36),
            MaterialSpec("facade_frame_stone", (0.54, 0.50, 0.43), roughness=0.62),
            MaterialSpec("facade_frame_cream", (0.82, 0.76, 0.65), roughness=0.60),
            MaterialSpec("facade_frame_sand", (0.67, 0.60, 0.49), roughness=0.64),
            MaterialSpec("facade_frame_graphite", (0.09, 0.13, 0.15), roughness=0.32, metallic=0.42),
            MaterialSpec("facade_frame_silver", (0.48, 0.54, 0.56), roughness=0.30, metallic=0.48),
            MaterialSpec("facade_frame_limestone", (0.73, 0.67, 0.56), roughness=0.72),
            MaterialSpec("facade_accent_warm", (0.66, 0.31, 0.16), roughness=0.55),
            MaterialSpec("facade_accent_blue", (0.10, 0.27, 0.42), roughness=0.34, metallic=0.18),
            MaterialSpec("facade_accent_stone", (0.42, 0.34, 0.25), roughness=0.70),
            MaterialSpec("facade_accent_metal", (0.27, 0.31, 0.33), roughness=0.42, metallic=0.42),
            MaterialSpec("facade_accent_brick", (0.50, 0.18, 0.11), roughness=0.78),
            MaterialSpec("facade_accent_terracotta", (0.69, 0.32, 0.18), roughness=0.72),
            MaterialSpec("facade_accent_copper", (0.56, 0.31, 0.18), roughness=0.42, metallic=0.46),
            MaterialSpec("facade_accent_navy", (0.08, 0.18, 0.30), roughness=0.38, metallic=0.20),
            MaterialSpec("facade_accent_bronze", (0.43, 0.30, 0.16), roughness=0.44, metallic=0.48),
            MaterialSpec("facade_accent_rust", (0.57, 0.25, 0.12), roughness=0.68, metallic=0.16),
            MaterialSpec("balcony_rail", (0.18, 0.22, 0.23), roughness=0.30, metallic=0.45),
            MaterialSpec("storefront_glass", (0.08, 0.26, 0.36), roughness=0.12, metallic=0.14),
            MaterialSpec("window_interior_dark", (0.035, 0.045, 0.055), roughness=0.90),
            MaterialSpec("window_interior_warm", (0.72, 0.42, 0.17), roughness=0.82),
            MaterialSpec("window_blind", (0.66, 0.64, 0.57), roughness=0.88),
            MaterialSpec("mechanical_louver", (0.16, 0.19, 0.20), roughness=0.48, metallic=0.40),
            MaterialSpec("door", (0.42, 0.22, 0.10), roughness=0.62),
            MaterialSpec("stairs", (0.50, 0.51, 0.53), roughness=0.72),
            MaterialSpec("roof", (0.20, 0.22, 0.24), roughness=0.78),
            MaterialSpec("grass", (0.24, 0.48, 0.22), roughness=0.96),
            MaterialSpec("grass_deep", (0.18, 0.38, 0.14), roughness=0.98),
            MaterialSpec("grass_dry", (0.40, 0.47, 0.22), roughness=0.97),
            MaterialSpec("parcel_lawn", (0.28, 0.46, 0.24), roughness=0.96),
            # Subtle surface variants used by parcel/site patching.  They are
            # intentionally close in hue so the city remains coherent while
            # avoiding the previous two-tone, single-material ground.
            MaterialSpec("parcel_lawn_deep", (0.18, 0.38, 0.14), roughness=0.98),
            MaterialSpec("parcel_lawn_dry", (0.40, 0.47, 0.22), roughness=0.97),
            MaterialSpec("mulch_warm", (0.20, 0.12, 0.065), roughness=0.99),
            MaterialSpec("flower_soil", (0.28, 0.16, 0.08), roughness=0.99),
            MaterialSpec("paving_light", (0.72, 0.70, 0.65), roughness=0.90),
            MaterialSpec("paving_dark", (0.45, 0.46, 0.45), roughness=0.92),
            MaterialSpec("permeable_paver", (0.39, 0.43, 0.39), roughness=0.94),
            MaterialSpec("brick_paving", (0.55, 0.28, 0.18), roughness=0.90),
            MaterialSpec("service_concrete_light", (0.52, 0.54, 0.53), roughness=0.86),
            MaterialSpec("service_concrete_dark", (0.34, 0.37, 0.37), roughness=0.92),
            MaterialSpec("gravel_warm", (0.49, 0.42, 0.32), roughness=0.98),
            MaterialSpec("parcel_edge_residential", (0.37, 0.42, 0.35), roughness=0.94),
            MaterialSpec("parcel_edge_commercial", (0.42, 0.41, 0.37), roughness=0.92),
            MaterialSpec("parcel_edge_civic", (0.50, 0.47, 0.40), roughness=0.90),
            MaterialSpec("parcel_edge_industrial", (0.31, 0.34, 0.34), roughness=0.95),
            MaterialSpec("courtyard_paving", (0.57, 0.55, 0.50), roughness=0.88),
            MaterialSpec("civic_forecourt", (0.69, 0.66, 0.59), roughness=0.84),
            MaterialSpec("service_yard", (0.38, 0.40, 0.40), roughness=0.92),
            MaterialSpec("planting_soil", (0.22, 0.13, 0.07), roughness=0.98),
            MaterialSpec("flower_accent", (0.72, 0.24, 0.34), roughness=0.90),
            MaterialSpec("landscape_shrub", (0.18, 0.36, 0.14), roughness=0.94),
            MaterialSpec("flower_bed", (0.48, 0.24, 0.30), roughness=0.90),
            MaterialSpec("playground_surface", (0.46, 0.24, 0.16), roughness=0.90),
            MaterialSpec("playground_accent", (0.86, 0.52, 0.16), roughness=0.72),
            MaterialSpec("water", (0.12, 0.43, 0.58), roughness=0.08, metallic=0.04, opacity=0.82),
            MaterialSpec("plaza_paving", (0.68, 0.64, 0.56), roughness=0.88),
            MaterialSpec("landscape_path", (0.58, 0.50, 0.39), roughness=0.90),
            MaterialSpec("tree_trunk", (0.30, 0.18, 0.09), roughness=0.94),
            MaterialSpec("tree_canopy", (0.16, 0.42, 0.18), roughness=0.92),
            MaterialSpec("street_furniture", (0.18, 0.21, 0.22), roughness=0.70),
            MaterialSpec("furniture_wood", (0.60, 0.38, 0.20), roughness=0.72),
            MaterialSpec("furniture_wood_dark", (0.28, 0.16, 0.09), roughness=0.70),
            MaterialSpec("furniture_blue", (0.19, 0.39, 0.62), roughness=0.76),
            MaterialSpec("furniture_fabric", (0.55, 0.38, 0.55), roughness=0.90),
            MaterialSpec("furniture_warm", (0.72, 0.42, 0.22), roughness=0.80),
            MaterialSpec("furniture_metal", (0.28, 0.32, 0.35), roughness=0.46, metallic=0.34),
            MaterialSpec("ceramic", (0.88, 0.91, 0.90), roughness=0.34),
            MaterialSpec("collision_proxy", (0.0, 0.0, 0.0), opacity=0.0),
        ]
        if self.material_library is None:
            return materials
        resolved: list[MaterialSpec] = []
        for material in materials:
            record = self.material_library.get(material.id)
            if record is None:
                resolved.append(material)
                continue
            resolved.append(
                replace(
                    material,
                    display_color=record.display_color,
                    roughness=record.roughness,
                    metallic=record.metallic,
                    opacity=record.opacity,
                    base_color_path=(
                        str(self.material_library.resolve_path(record.base_color_path))
                        if record.base_color_path else None
                    ),
                    normal_path=(
                        str(self.material_library.resolve_path(record.normal_path))
                        if record.normal_path else None
                    ),
                    roughness_path=(
                        str(self.material_library.resolve_path(record.roughness_path))
                        if record.roughness_path else None
                    ),
                    ambient_occlusion_path=(
                        str(self.material_library.resolve_path(record.ambient_occlusion_path))
                        if record.ambient_occlusion_path else None
                    ),
                    source=record.source,
                    license_id=record.license_id,
                    texture_scale_m=record.texture_scale_m,
                )
            )
        return resolved

    @staticmethod
    def _activation_tiers() -> list[ActivationTier]:
        return [
            ActivationTier(
                "overview",
                "Roads and all building shells; interiors remain unloaded",
                ("root", "roads", "district", "building_shell"),
                ("static",),
            ),
            ActivationTier(
                "active_building",
                "Load one building interior hierarchy with static collision",
                ("root", "roads", "district", "building_shell", "building_interior"),
                ("static",),
            ),
            ActivationTier(
                "active_floor",
                "Load one floor payload and activate articulated doors",
                (
                    "root",
                    "roads",
                    "district",
                    "building_shell",
                    "building_interior",
                    "floor",
                ),
                ("static", "articulated"),
            ),
        ]

    def _define_layers(self, city: City, scene: GeometryScene) -> None:
        scene.layers.extend(
            [
                LayerDefinition("root", city.id, "root", "city.usda", "always"),
                LayerDefinition(
                    "assets", city.id, "assets", "layers/assets.usda", "always", "root"
                ),
                LayerDefinition(
                    "roads", city.id, "roads", "layers/roads.usda", "always", "root"
                ),
            ]
        )
        for district in city.districts:
            district_layer = f"district:{district.id}"
            scene.layers.append(
                LayerDefinition(
                    district_layer,
                    district.id,
                    "district",
                    f"layers/districts/{district.id}.usda",
                    "always",
                    "root",
                )
            )
            for parcel in district.parcels:
                for building in parcel.buildings:
                    shell_layer = f"shell:{building.id}"
                    interior_layer = f"interior:{building.id}"
                    scene.layers.extend(
                        [
                            LayerDefinition(
                                shell_layer,
                                building.id,
                                "building_shell",
                                f"layers/buildings/{building.id}_shell.usda",
                                "always",
                                district_layer,
                            ),
                            LayerDefinition(
                                interior_layer,
                                building.id,
                                "building_interior",
                                f"layers/buildings/{building.id}_interior.usda",
                                "payload_on_proximity",
                                district_layer,
                            ),
                        ]
                    )
                    for floor in building.floors:
                        scene.layers.append(
                            LayerDefinition(
                                f"floor:{floor.id}",
                                floor.id,
                                "floor",
                                f"layers/floors/{floor.id}.usda",
                                "payload_on_activation",
                                interior_layer,
                            )
                        )

    def _compile_roads(self, city: City, scene: GeometryScene) -> None:
        # A city-scale base plane prevents the negative space between blocks
        # from reading as an unbounded white void in bird's-eye views.  It is
        # deliberately a thin, non-colliding presentation layer below roads,
        # sidewalks, parcels and landscape sites.
        ground_margin = max(18.0, min(city.bounds.width, city.bounds.depth) * 0.08)
        city_ground = Bounds2D(
            city.bounds.min_x - ground_margin,
            city.bounds.min_y - ground_margin,
            city.bounds.max_x + ground_margin,
            city.bounds.max_y + ground_margin,
        )
        scene.primitives.append(
            self._bounds_box(
                f"{city.id}_ground_plane",
                city.id,
                city_ground,
                -0.20,
                0.18,
                "city_ground",
                "city_ground",
                "roads",
                metadata={
                    "ground_plane": True,
                    "ground_margin_m": round(ground_margin, 3),
                    "presentation_layer": "macro_context",
                },
                collision_enabled=False,
            )
        )
        if any(len(road.centerline) > 2 for road in city.road_network.segments):
            from cityg.geometry.path_mesh import compile_path_roads
            compile_path_roads(city, scene)
            return
        connected: dict[str, list[Any]] = {}
        for item in city.road_network.segments:
            connected.setdefault(item.start_junction_id, []).append(item)
            connected.setdefault(item.end_junction_id, []).append(item)

        def junction_half_width(junction_id: str) -> float:
            roads = connected.get(junction_id, ())
            if len(roads) < 2:
                return 0.0
            return max(float(item.width_m) / 2 for item in roads)

        # Some generated diagonal roads cross the grid geometrically without
        # sharing a graph junction.  Record those proper crossings so road and
        # sidewalk slabs can be interrupted there as well.
        interior_crossings: dict[str, list[tuple[float, float, Point2D]]] = defaultdict(list)
        crossing_patches: list[tuple[str, Point2D, float, tuple[str, str]]] = []
        for index, first in enumerate(city.road_network.segments):
            first_start, first_end = first.centerline
            first_length = math.hypot(first_end.x - first_start.x, first_end.y - first_start.y)
            for second in city.road_network.segments[index + 1 :]:
                hit = segment_intersection(first.centerline, second.centerline)
                if hit is None:
                    continue
                t, u, point = hit
                second_start, second_end = second.centerline
                second_length = math.hypot(second_end.x - second_start.x, second_end.y - second_start.y)
                radius = max(first.width_m, second.width_m) / 2
                interior_crossings[first.id].append((t * first_length, radius, point))
                interior_crossings[second.id].append((u * second_length, radius, point))
                crossing_patches.append((f"crossing_{first.id}_{second.id}", point, radius, (first.id, second.id)))

        def intervals(
            length: float,
            start_trim: float,
            end_trim: float,
            blocked: list[tuple[float, float]],
        ) -> list[tuple[float, float]]:
            boundaries = [max(0.0, start_trim), min(length, length - end_trim)]
            for distance, radius in blocked:
                boundaries.extend((distance - radius, distance + radius))
            boundaries = sorted(max(0.0, min(length, value)) for value in boundaries)
            unique: list[float] = []
            for value in boundaries:
                if not unique or value - unique[-1] > 1e-4:
                    unique.append(value)
            return [(left, right) for left, right in zip(unique, unique[1:]) if right - left > 0.2]

        def sidewalk_corners(center: Vec3, length: float, width: float, angle_deg: float) -> list[Point2D]:
            """Return the four plan-view corners of a sidewalk slab.

            Sidewalks are deliberately treated as finite slabs rather than as
            infinitely thin road offsets.  This lets us reject a slab when
            any part of it would occupy another road's carriageway at a
            junction, which is the conservative block-side sidewalk policy.
            """
            angle = math.radians(angle_deg)
            ux, uy = math.cos(angle), math.sin(angle)
            nx, ny = -uy, ux
            half_length, half_width = length / 2, width / 2
            return [
                Point2D(center.x + ux * sx * half_length + nx * sy * half_width,
                        center.y + uy * sx * half_length + ny * sy * half_width)
                for sx, sy in ((-1.0, -1.0), (-1.0, 1.0), (1.0, -1.0), (1.0, 1.0))
            ]

        def sidewalk_intrudes(center: Vec3, slab_length: float, slab_width: float, angle_deg: float, owner_id: str) -> bool:
            """Check whether a candidate sidewalk slab enters another road.

            A small margin avoids coplanar-looking slivers at the edge of a
            carriageway.  Segments failing this check are omitted entirely;
            leaving a short open corner is preferable to rendering a sidewalk
            across an intersection.
            """
            corners = sidewalk_corners(center, slab_length, slab_width, angle_deg)
            margin = 0.08
            for other in city.road_network.segments:
                if other.id == owner_id:
                    continue
                half_width = float(other.width_m) / 2 + margin
                if any(point_segment_distance(corner, other.centerline) <= half_width for corner in corners):
                    return True
            return False

        for road in city.road_network.segments:
            start, end = road.centerline
            dx = end.x - start.x
            dy = end.y - start.y
            length = math.hypot(dx, dy)
            rotation = math.degrees(math.atan2(dy, dx))
            ux, uy = dx / length, dy / length
            start_trim = junction_half_width(road.start_junction_id)
            end_trim = junction_half_width(road.end_junction_id)
            blocked = [(distance, radius) for distance, radius, _point in interior_crossings.get(road.id, [])]
            road_intervals = intervals(length, start_trim, end_trim, blocked)
            for segment_index, (left, right) in enumerate(road_intervals):
                segment_length = right - left
                center_distance = (left + right) / 2
                center = Vec3(start.x + ux * center_distance, start.y + uy * center_distance, -0.10)
                scene.primitives.append(
                    self._box(
                        road.id if segment_index == 0 else f"{road.id}_segment_{segment_index:02d}",
                        road.id,
                        center,
                        Vec3(segment_length, road.width_m, 0.20),
                        rotation,
                        "road_surface",
                        "asphalt",
                        "roads",
                        metadata={
                            "road_class": road.road_class,
                            "lane_count": road.lane_count,
                            "speed_limit_kph": road.speed_limit_kph,
                            "directionality": road.directionality,
                            "median_width_m": road.median_width_m,
                            "parking_allowed": road.parking_allowed,
                            "bike_lane": road.bike_lane,
                            "bus_lane": road.bus_lane,
                            "turn_lane": road.turn_lane,
                            "segment_index": segment_index,
                        },
                    )
                )
            if road.median_width_m > 0.0:
                # Raised/contrasting central reservation.  It is clipped to
                # the same usable intervals as asphalt so intersections remain
                # open and do not accumulate overlapping slabs.
                median_width = min(float(road.median_width_m), max(0.0, float(road.width_m) - 1.0))
                for segment_index, (left, right) in enumerate(road_intervals):
                    if right - left <= 0.25 or median_width <= 0.0:
                        continue
                    center_distance = (left + right) / 2
                    median_center = Vec3(
                        start.x + ux * center_distance,
                        start.y + uy * center_distance,
                        0.015,
                    )
                    scene.primitives.append(
                        self._box(
                            f"{road.id}_median_{segment_index:02d}",
                            road.id,
                            median_center,
                            Vec3(right - left, median_width, 0.12),
                            rotation,
                            "road_median",
                            "concrete",
                            "roads",
                            metadata={
                                "road_class": road.road_class,
                                "median_width_m": median_width,
                                "intersection_clipped": True,
                            },
                        )
                    )
            if road.sidewalk_width_m > 0:
                normal_x = -dy / length
                normal_y = dx / length
                offset = road.width_m / 2 + road.sidewalk_width_m / 2
                sidewalk_start_trim = start_trim + (road.sidewalk_width_m if start_trim else 0.0)
                sidewalk_end_trim = end_trim + (road.sidewalk_width_m if end_trim else 0.0)
                sidewalk_blocked = [
                    (distance, radius + road.sidewalk_width_m)
                    for distance, radius, _point in interior_crossings.get(road.id, [])
                ]
                for side, sign in (("left", 1.0), ("right", -1.0)):
                    for segment_index, (left, right) in enumerate(
                        intervals(length, sidewalk_start_trim, sidewalk_end_trim, sidewalk_blocked)
                    ):
                        sidewalk_length = right - left
                        sidewalk_center_distance = (left + right) / 2
                        sidewalk_center = Vec3(
                            start.x + ux * sidewalk_center_distance + normal_x * offset * sign,
                            start.y + uy * sidewalk_center_distance + normal_y * offset * sign,
                            0.075,
                        )
                        if sidewalk_intrudes(
                            sidewalk_center,
                            sidewalk_length,
                            road.sidewalk_width_m,
                            rotation,
                            road.id,
                        ):
                            continue
                        scene.primitives.append(
                            self._box(
                                f"{road.id}_sidewalk_{side}_{segment_index:02d}",
                                road.id,
                                sidewalk_center,
                                Vec3(sidewalk_length, road.sidewalk_width_m, 0.15),
                                rotation,
                                "sidewalk",
                                "sidewalk",
                                "roads",
                                metadata={
                                    "pedestrian": True,
                                    "segment_index": segment_index,
                                    "block_constrained": True,
                                    "intersection_clipped": True,
                                },
                            )
                        )

        # One asphalt junction patch replaces the overlapping ends of every
        # incident road.  This prevents coplanar road slabs and leaves a clear
        # central vehicle area while sidewalks/curbs stop before the crossing.
        for junction in city.road_network.junctions:
            radius = junction_half_width(junction.id)
            if radius <= 0.0:
                continue
            scene.primitives.append(
                self._box(
                    f"{junction.id}_road_patch",
                    junction.id,
                    Vec3(junction.position.x, junction.position.y, -0.095),
                    Vec3(radius * 2, radius * 2, 0.19),
                    0.0,
                    "junction_surface",
                    "asphalt",
                    "roads",
                    metadata={
                        "junction_id": junction.id,
                        "incident_road_ids": sorted(item.id for item in connected.get(junction.id, ())),
                    },
                )
            )
        for patch_id, point, radius, road_ids in crossing_patches:
            scene.primitives.append(
                self._box(
                    f"{patch_id}_road_patch",
                    patch_id,
                    Vec3(point.x, point.y, -0.095),
                    Vec3(radius * 2, radius * 2, 0.19),
                    0.0,
                    "junction_surface",
                    "asphalt",
                    "roads",
                    metadata={"crossing": True, "incident_road_ids": list(road_ids)},
                )
            )

    def _compile_landscape(self, city: City, scene: GeometryScene) -> None:
        sites = city.metadata.get("landscape_sites", [])
        if not isinstance(sites, list):
            return
        appearance = appearance_program_for_city(city)

        def landscape_tree_query(site_id: str, site_style: str, index: int, site: dict[str, Any]) -> tuple[str, str]:
            """Return a deterministic botanical preference for a landscape site.

            Public green spaces and explicitly tagged city gateways receive
            more flowering/sculptural species, while the ordinary broadleaf
            query remains the safe fallback for sparse or unknown sites.
            """

            role = str(site.get("role", site.get("site_role", ""))).lower()
            gateway = role in {"city_entrance", "city_gateway", "gateway", "entrance"}
            roll = int.from_bytes(hashlib.sha256(f"{site_id}|{index}|tree_species".encode()).digest()[:2], "big") % 100
            if gateway or site_style in {"park", "plaza"}:
                if roll < 38:
                    return ("jacaranda", "jacaranda tree flowering public-space tree")
                if roll < 72:
                    return ("quiver", "quiver tree sculptural public-space tree")
            return ("broadleaf", "large broadleaf park tree")

        from cityg.paths import RoadClearanceQuery
        road_clearance = RoadClearanceQuery(city.road_network.segments)

        for site_index, site in enumerate(sites):
            raw_bounds = site.get("bounds", {})
            try:
                bounds = Bounds2D(
                    float(raw_bounds["min_x"]),
                    float(raw_bounds["min_y"]),
                    float(raw_bounds["max_x"]),
                    float(raw_bounds["max_y"]),
                )
            except (KeyError, TypeError, ValueError):
                continue
            site_id = str(site.get("id", f"landscape_{site_index:03d}"))
            style = str(site.get("style", "park"))
            requested_tier = site.get("density_tier", site.get("landscape_density_tier"))
            profile = appearance.profile_for_landscape(
                style,
                str(requested_tier) if requested_tier is not None else None,
            )
            layer = "roads"
            inset = min(1.5, bounds.width * 0.04, bounds.depth * 0.04)
            ground = bounds.inset(inset)
            ground_semantic = "plaza" if style == "plaza" else "grass"
            ground_material = "plaza_paving" if style == "plaza" else "grass"
            scene.primitives.append(
                self._bounds_box(
                    f"{site_id}_ground",
                    city.id,
                    ground,
                    0.025,
                    0.05,
                    ground_semantic,
                    ground_material,
                    layer,
                    metadata={"landscape_site": site_id, "style": style},
                    collision_enabled=False,
                )
            )

            path_width = max(2.0, min(4.0, min(bounds.width, bounds.depth) * 0.06))

            # Break up the site-wide ground material with a few shallow,
            # deterministic surface patches.  The base remains useful for
            # navigation and semantic selection; these presentation patches
            # provide realistic transitions between lawn, paving, mulch and
            # gravel without introducing extra collision geometry.
            if style in {"park", "garden"}:
                surface_specs = (
                    ("grass_deep", 0.30, 0.03),
                    ("grass_dry", 0.20, 0.03),
                    ("mulch_warm", 0.18, 0.02),
                    ("gravel_warm", 0.16, 0.02),
                    ("flower_soil", 0.16, 0.02),
                )
            elif style == "plaza":
                surface_specs = (
                    ("paving_light", 0.34, 0.025),
                    ("paving_dark", 0.26, 0.025),
                    ("permeable_paver", 0.22, 0.025),
                    ("brick_paving", 0.14, 0.025),
                    ("flower_soil", 0.10, 0.02),
                    ("mulch_warm", 0.06, 0.02),
                )
            else:
                surface_specs = (("grass_deep", 1.0, 0.03),)
            patch_count = min(12, max(2, round(bounds.area / 420.0)))
            patch_count = min(patch_count, max(0, round(min(ground.width, ground.depth) / 4.5)))
            patch_index = 0
            patch_attempt = 0
            placed_patch_specs: list[tuple[Point2D, float]] = []
            while patch_index < patch_count and patch_attempt < patch_count * 10 + 12:
                patch_attempt += 1
                x_ratio = 0.14 + 0.72 * ((patch_attempt * 0.61803398875 + site_index * 0.17) % 1.0)
                y_ratio = 0.14 + 0.72 * ((patch_attempt * 0.41421356237 + site_index * 0.29) % 1.0)
                point = Point2D(
                    ground.min_x + ground.width * x_ratio,
                    ground.min_y + ground.depth * y_ratio,
                )
                if road_clearance(point) < 1.8:
                    continue
                # Keep the principal park/plaza circulation spine readable.
                if style in {"park", "garden"} and (
                    abs(point.y - bounds.center.y) < path_width * 0.85
                    or abs(point.x - bounds.center.x) < path_width * 0.62
                ):
                    continue
                if style == "plaza":
                    fountain_radius = min(bounds.width, bounds.depth) * 0.13
                    if math.hypot(point.x - bounds.center.x, point.y - bounds.center.y) < fountain_radius:
                        continue
                roll = int.from_bytes(
                    hashlib.sha256(f"{site_id}|{patch_index}|surface".encode()).digest()[:2],
                    "big",
                ) / 65535.0
                cumulative = 0.0
                material_id = surface_specs[-1][0]
                height = surface_specs[-1][2]
                for candidate_material, weight, candidate_height in surface_specs:
                    cumulative += weight
                    if roll <= cumulative:
                        material_id, height = candidate_material, candidate_height
                        break
                width = min(11.0, max(2.4, ground.width * (0.13 + (patch_index % 3) * 0.025)))
                depth = min(7.0, max(1.8, ground.depth * (0.09 + ((patch_index + 1) % 3) * 0.02)))
                rotation = float((int.from_bytes(hashlib.sha256(f"{site_id}|{patch_index}|rotation".encode()).digest()[:2], "big") % 7) * 15 - 45)
                angle = math.radians(rotation)
                extent_x = abs(math.cos(angle)) * width / 2 + abs(math.sin(angle)) * depth / 2
                extent_y = abs(math.sin(angle)) * width / 2 + abs(math.cos(angle)) * depth / 2
                if not (
                    ground.min_x + 0.25 + extent_x <= point.x <= ground.max_x - 0.25 - extent_x
                    and ground.min_y + 0.25 + extent_y <= point.y <= ground.max_y - 0.25 - extent_y
                ):
                    continue
                corner_clear = True
                for local_x, local_y in (
                    (-width / 2, -depth / 2),
                    (-width / 2, depth / 2),
                    (width / 2, -depth / 2),
                    (width / 2, depth / 2),
                ):
                    sample = Point2D(
                        point.x + local_x * math.cos(angle) - local_y * math.sin(angle),
                        point.y + local_x * math.sin(angle) + local_y * math.cos(angle),
                    )
                    if road_clearance(sample) < 0.45:
                        corner_clear = False
                        break
                if not corner_clear:
                    continue
                patch_radius = math.hypot(width, depth) * 0.5
                if any(
                    math.hypot(point.x - other.x, point.y - other.y)
                    < (patch_radius + other_radius) * 0.62
                    for other, other_radius in placed_patch_specs
                ):
                    continue
                scene.primitives.append(
                    self._box(
                        f"{site_id}_surface_patch_{patch_index:02d}",
                        city.id,
                        Vec3(point.x, point.y, 0.057),
                        Vec3(width, depth, height),
                        rotation,
                        "landscape_surface_patch",
                        material_id,
                        layer,
                        collision_enabled=False,
                        metadata={
                            "landscape_site": site_id,
                            "feature": "surface_patch",
                            "surface_role": "internal_patch",
                            "surface_material_variant": material_id,
                            "surface_patch_index": patch_index,
                        },
                    )
                )
                placed_patch_specs.append((point, patch_radius))
                patch_index += 1

            if style in {"park", "garden"}:
                scene.primitives.extend(
                    [
                        self._box(
                            f"{site_id}_path_east_west",
                            city.id,
                            Vec3(bounds.center.x, bounds.center.y, 0.065),
                            Vec3(bounds.width * 0.78, path_width, 0.08),
                            0.0,
                            "landscape_path",
                            "landscape_path",
                            layer,
                            collision_enabled=False,
                            metadata={"landscape_site": site_id},
                        ),
                        self._box(
                            f"{site_id}_path_diagonal",
                            city.id,
                            Vec3(bounds.center.x, bounds.center.y, 0.07),
                            Vec3(
                                math.hypot(bounds.width, bounds.depth) * 0.62,
                                path_width * 0.72,
                                0.09,
                            ),
                            math.degrees(math.atan2(bounds.depth, bounds.width)),
                            "landscape_path",
                            "landscape_path",
                            layer,
                            collision_enabled=False,
                            metadata={"landscape_site": site_id},
                        ),
                    ]
                )
            elif style == "plaza":
                fountain_size = min(bounds.width, bounds.depth) * 0.16
                fountain = self._outdoor_mesh(
                    f"{site_id}_fountain", city.id,
                    Vec3(bounds.center.x, bounds.center.y, 1.4),
                    Vec3(min(fountain_size, 3.0), min(fountain_size, 3.0), 2.8),
                    0.0, "plaza_feature", "fountain", "park plaza fountain",
                    layer, metadata={"landscape_site": site_id, "feature": "fountain"},
                )
                scene.primitives.extend([fountain] if fountain else
                    [self._box(
                        f"{site_id}_fountain",
                        city.id,
                        Vec3(bounds.center.x, bounds.center.y, 0.25),
                        Vec3(fountain_size, fountain_size, 0.5),
                        45.0,
                        "plaza_feature",
                        "concrete",
                        layer,
                        metadata={"landscape_site": site_id},
                    ), self._box(
                        f"{site_id}_fountain_water", city.id,
                        Vec3(bounds.center.x, bounds.center.y, 0.53),
                        Vec3(fountain_size * 0.72, fountain_size * 0.72, 0.08),
                        45.0, "water_feature", "water", layer,
                        collision_enabled=False,
                        metadata={"landscape_site": site_id, "feature": "fountain"},
                    )]
                )

            if profile.feature == "playground" and style == "park":
                feature_w = min(16.0, bounds.width * 0.24)
                feature_d = min(12.0, bounds.depth * 0.22)
                fx = bounds.center.x + bounds.width * 0.22
                fy = bounds.center.y - bounds.depth * 0.22
                scene.primitives.append(
                    self._box(f"{site_id}_playground_surface", city.id, Vec3(fx, fy, 0.08), Vec3(feature_w, feature_d, 0.12), 8.0, "playground_surface", "playground_surface", layer, collision_enabled=False, metadata={"landscape_site": site_id, "feature": "playground"})
                )
                playground = self._outdoor_mesh(
                    f"{site_id}_playground_frame", city.id,
                    Vec3(fx, fy, 1.55), Vec3(5.2, 4.2, 3.1), 8.0,
                    "playground_equipment", "playground", "compact playground climber slide",
                    layer, metadata={"landscape_site": site_id, "feature": "playground"},
                )
                scene.primitives.append(
                    playground or self._box(f"{site_id}_playground_frame", city.id, Vec3(fx, fy, 1.05), Vec3(3.6, 2.4, 2.0), 8.0, "playground_equipment", "playground_accent", layer, collision_enabled=False, metadata={"landscape_site": site_id, "feature": "playground"})
                )
            elif profile.feature == "flower_bed" and style == "garden":
                for bed_index, offset in enumerate((-0.22, 0.0, 0.22)):
                    bed_x = bounds.center.x + bounds.width * offset
                    bed_y = bounds.center.y + bounds.depth * 0.22
                    scene.primitives.append(
                        self._box(
                            f"{site_id}_flower_bed_{bed_index:02d}", city.id,
                            Vec3(bed_x, bed_y, 0.18),
                            Vec3(bounds.width * 0.14, bounds.depth * 0.10, 0.32),
                            12.0 * (bed_index - 1), "flower_bed", "flower_bed", layer,
                            collision_enabled=False,
                            metadata={"landscape_site": site_id, "feature": "flower_bed"},
                        )
                    )
                    # Add a few sparse, textured botanical clusters on top of
                    # the bed.  These are optional visual details: the bed
                    # remains valid if a user has not downloaded the plant
                    # pack, and no low-poly cyan fallback is introduced.
                    flower_category = "outdoor_prop" if bed_index == 2 else "plant"
                    flower_query = (
                        "realistic yellow wildflower dandelion"
                        if bed_index == 2
                        else "realistic flowering garden plant groundcover"
                    )
                    for cluster_index, cluster_offset in enumerate((-0.28, 0.28)):
                        cluster_x = bed_x + bounds.width * 0.035 * cluster_offset
                        cluster = self._outdoor_mesh(
                            f"{site_id}_flower_{bed_index:02d}_{cluster_index:02d}",
                            city.id,
                            Vec3(cluster_x, bed_y, 0.72),
                            Vec3(1.4, 1.4, 1.45),
                            17.0 * (bed_index + cluster_index),
                            "flower_cluster",
                            flower_category,
                            flower_query,
                            layer,
                            metadata={
                                "landscape_site": site_id,
                                "feature": "flower_bed",
                                "botanical_cluster": True,
                            },
                        )
                        if cluster is not None:
                            scene.primitives.append(cluster)

            # Every public-space tier gets a small amount of flowering
            # understorey.  Previously this branch was restricted to gardens,
            # leaving large parks and plazas as mostly empty grass/paving.
            flower_target = max(0, min(24, round(bounds.area * profile.flower_density)))
            flower_index = 0
            flower_attempt = 0
            while flower_index < flower_target and flower_attempt < flower_target * 8 + 8:
                x_ratio = 0.12 + 0.76 * ((flower_attempt * 0.61803398875 + site_index * 0.11) % 1.0)
                y_ratio = 0.12 + 0.76 * ((flower_attempt * 0.41421356237 + site_index * 0.19) % 1.0)
                flower_attempt += 1
                point = Point2D(
                    bounds.min_x + bounds.width * x_ratio,
                    bounds.min_y + bounds.depth * y_ratio,
                )
                if road_clearance(point) < 1.2:
                    continue
                if style in {"park", "garden"}:
                    public_path_width = max(2.0, min(4.0, min(bounds.width, bounds.depth) * 0.06))
                    if abs(point.y - bounds.center.y) < public_path_width * 0.8:
                        continue
                cluster = self._outdoor_mesh(
                    f"{site_id}_flower_cluster_{flower_index:02d}", city.id,
                    Vec3(point.x, point.y, 0.48), Vec3(1.0, 1.0, 0.9),
                    float((flower_index * 37 + site_index * 13) % 360),
                    "flower_cluster", "plant", "flowering plant cluster group",
                    layer,
                    metadata={
                        "landscape_site": site_id,
                        "feature": "flower_cluster",
                        "botanical_cluster": True,
                    },
                )
                if cluster is not None:
                    scene.primitives.append(cluster)
                    flower_index += 1

            # Activate the perimeter/entrance of large public spaces with
            # small, walkable clusters.  Keeping these elements near the
            # boundary makes them visible from street-level cameras while
            # leaving the centre available for circulation and events.
            edge_cluster_target = {
                "park": 3,
                "garden": 3,
                "plaza": 4,
            }.get(style, 0)
            if profile.density_tier == "sparse":
                edge_cluster_target = max(1, edge_cluster_target - 2)
            elif profile.density_tier == "standard":
                edge_cluster_target = max(1, edge_cluster_target - 1)
            edge_candidates = []
            for index in range(edge_cluster_target * 3):
                ratio = 0.16 + 0.68 * ((index + 0.5) / max(1, edge_cluster_target * 3))
                side = index % 4
                if side == 0:
                    edge_candidates.append((bounds.min_x + bounds.width * ratio, bounds.min_y + bounds.depth * 0.12, 0.0))
                elif side == 1:
                    edge_candidates.append((bounds.max_x - bounds.width * 0.12, bounds.min_y + bounds.depth * ratio, 90.0))
                elif side == 2:
                    edge_candidates.append((bounds.max_x - bounds.width * ratio, bounds.max_y - bounds.depth * 0.12, 180.0))
                else:
                    edge_candidates.append((bounds.min_x + bounds.width * 0.12, bounds.max_y - bounds.depth * ratio, 270.0))
            edge_clusters = 0
            for candidate_index, (edge_x, edge_y, edge_rotation) in enumerate(edge_candidates):
                if edge_clusters >= edge_cluster_target:
                    break
                edge_point = Point2D(edge_x, edge_y)
                if road_clearance(edge_point) < 2.0:
                    continue
                angle = math.radians(edge_rotation)
                nx, ny = -math.sin(angle), math.cos(angle)
                cluster_base = f"{site_id}_edge_cluster_{edge_clusters:02d}"
                bench_point = Point2D(edge_x, edge_y)
                planter_point = Point2D(edge_x + nx * 1.35, edge_y + ny * 1.35)
                sign_point = Point2D(edge_x - nx * 1.45, edge_y - ny * 1.45)
                if min(road_clearance(planter_point), road_clearance(sign_point)) < 0.8:
                    continue
                bench = self._outdoor_mesh(
                    f"{cluster_base}_bench", city.id,
                    Vec3(bench_point.x, bench_point.y, 0.43), Vec3(1.9, 0.62, 0.86),
                    edge_rotation, "bench", "street_bench", "public street bench wood metal", layer,
                    metadata={"landscape_site": site_id, "feature": "entrance_cluster", "cluster_index": edge_clusters},
                )
                planter = self._outdoor_mesh(
                    f"{cluster_base}_planter", city.id,
                    Vec3(planter_point.x, planter_point.y, 0.36), Vec3(1.2, 0.65, 0.72),
                    edge_rotation, "entrance_planter", "street_planter", "urban flower planter greenery", layer,
                    metadata={"landscape_site": site_id, "feature": "entrance_cluster", "cluster_index": edge_clusters},
                )
                sign_asset = self._outdoor_mesh(
                    f"{cluster_base}_sign", city.id,
                    Vec3(sign_point.x, sign_point.y, 0.82), Vec3(0.55, 0.12, 1.65),
                    edge_rotation, "wayfinding_sign", "small_sign", "small pedestrian wayfinding sign", layer,
                    metadata={"landscape_site": site_id, "feature": "entrance_cluster", "cluster_index": edge_clusters},
                )
                scene.primitives.extend([
                    bench or self._box(f"{cluster_base}_bench", city.id, Vec3(bench_point.x, bench_point.y, 0.45), Vec3(1.8, 0.52, 0.18), edge_rotation, "bench", "street_furniture", layer, collision_enabled=False, metadata={"landscape_site": site_id, "feature": "entrance_cluster"}),
                    planter or self._box(f"{cluster_base}_planter", city.id, Vec3(planter_point.x, planter_point.y, 0.30), Vec3(1.15, 0.62, 0.55), edge_rotation, "entrance_planter", "facade_frame_stone", layer, collision_enabled=False, metadata={"landscape_site": site_id, "feature": "entrance_cluster"}),
                    sign_asset or self._box(f"{cluster_base}_sign", city.id, Vec3(sign_point.x, sign_point.y, 0.90), Vec3(0.52, 0.08, 1.55), edge_rotation, "wayfinding_sign", "street_furniture", layer, collision_enabled=False, metadata={"landscape_site": site_id, "feature": "entrance_cluster"}),
                ])
                edge_clusters += 1

            # Plazas are intentionally more open than parks, but should still
            # contain a few shade/accent trees instead of an entirely barren
            # paved block. Respect authored density while enforcing a modest
            # public-space minimum.
            target_trees = max(1, min(28, round(bounds.area * profile.tree_density)))
            if style == "plaza":
                target_trees = max(2, min(8, round(bounds.area * max(profile.tree_density, 0.00045))))
            tree_index = 0
            candidate_index = 0
            while tree_index < target_trees and candidate_index < target_trees * 8 + 12:
                # Seeded low-discrepancy candidates avoid both rigid grids and
                # accidental clustering while remaining bitwise deterministic.
                x_ratio = 0.10 + 0.80 * ((candidate_index * 0.61803398875 + (site_index * 0.173)) % 1.0)
                y_ratio = 0.10 + 0.80 * ((candidate_index * 0.41421356237 + (site_index * 0.271)) % 1.0)
                candidate_index += 1
                point = Point2D(
                    bounds.min_x + bounds.width * x_ratio,
                    bounds.min_y + bounds.depth * y_ratio,
                )
                nearest_clearance = road_clearance(point)
                if nearest_clearance < 3.5:
                    continue
                if style in {"park", "garden"} and abs(point.y - bounds.center.y) < path_width * 0.85:
                    continue
                height = 4.4 + ((site_index + tree_index) % 5) * 0.55
                tree_variant, tree_query = landscape_tree_query(site_id, style, tree_index, site)
                tree_mesh = self._outdoor_mesh(
                    f"{site_id}_tree_{tree_index:02d}", city.id,
                    Vec3(point.x, point.y, 5.0), Vec3(7.0, 7.0, 10.0),
                    tree_index * 31.0, "park_tree_asset", "park_tree",
                    tree_query, layer,
                    metadata={
                        "landscape_site": site_id,
                        "vegetation_variant": tree_index % 5,
                        "vegetation_preference": tree_variant,
                    },
                )
                if tree_mesh is not None:
                    scene.primitives.append(tree_mesh)
                    tree_index += 1
                    continue
                # A configured asset registry means this is a production
                # render.  Never emit the legacy cyan geometric tree when a
                # curated botanical mesh cannot be resolved; the candidate
                # is simply skipped and later candidates may still fill the
                # available slots.
                if self.asset_registry_configured:
                    continue
                scene.primitives.extend(
                    [
                        self._cylinder(
                            f"{site_id}_tree_{tree_index:02d}_trunk",
                            city.id,
                            Vec3(point.x, point.y, height * 0.35),
                            Vec3(0.34, 0.34, height * 0.70),
                            0.0,
                            "tree_trunk",
                            "tree_trunk",
                            layer,
                            collision_enabled=False,
                            metadata={"landscape_site": site_id, "vegetation_variant": tree_index % 5},
                        ),
                        self._sphere(
                            f"{site_id}_tree_{tree_index:02d}_canopy_low",
                            city.id,
                            Vec3(point.x, point.y, height * 0.82),
                            Vec3(3.2 + (tree_index % 3) * 0.35, 3.0, height * 0.42),
                            18.0 + tree_index * 9.0,
                            "tree_canopy",
                            "tree_canopy",
                            layer,
                            collision_enabled=False,
                            metadata={"landscape_site": site_id, "vegetation_variant": tree_index % 5},
                        ),
                        self._sphere(
                            f"{site_id}_tree_{tree_index:02d}_canopy_high", city.id,
                            Vec3(point.x + 0.18, point.y - 0.12, height * 0.94),
                            Vec3(2.35, 2.45, height * 0.34),
                            -12.0 - tree_index * 7.0, "tree_canopy", "tree_canopy", layer,
                            collision_enabled=False,
                            metadata={"landscape_site": site_id, "vegetation_variant": tree_index % 5},
                        ),
                    ]
                )
                tree_index += 1

            shrub_count = max(0, min(36, round(bounds.area * profile.shrub_density)))
            hedge_count = max(0, min(shrub_count, round(bounds.area * profile.hedge_density)))
            for shrub_index in range(shrub_count):
                ratio = (shrub_index + 0.5) / max(shrub_count, 1)
                edge = shrub_index % 4
                x = bounds.min_x + bounds.width * (0.08 + 0.84 * ratio) if edge < 2 else bounds.min_x + bounds.width * (0.08 if edge == 2 else 0.92)
                y = bounds.min_y + bounds.depth * (0.08 if edge == 0 else 0.92) if edge < 2 else bounds.min_y + bounds.depth * (0.08 + 0.84 * ratio)
                if road_clearance(Point2D(x, y)) < 1.0:
                    continue
                shrub_query = "low clipped hedge segment" if shrub_index < hedge_count else "ornamental landscape shrub"
                shrub_mesh = self._outdoor_mesh(
                    f"{site_id}_shrub_{shrub_index:03d}", city.id,
                    Vec3(x, y, 0.45), Vec3(1.25, 1.25, .9), shrub_index * 17.0,
                    "landscape_shrub_asset", "shrub", shrub_query,
                    layer, metadata={"landscape_site": site_id, "vegetation_layer": "hedge" if shrub_index < hedge_count else "shrub"},
                )
                scene.primitives.append(
                    shrub_mesh or self._sphere(
                        f"{site_id}_shrub_{shrub_index:03d}", city.id,
                        Vec3(x, y, 0.42), Vec3(1.25, 1.05, 0.78),
                        shrub_index * 17.0, "landscape_shrub", "landscape_shrub", layer,
                        collision_enabled=False,
                        metadata={"landscape_site": site_id, "vegetation_layer": "shrub"},
                    )
                )

            for bench_index in range(profile.seating_count):
                ratio = (bench_index + 1) / (profile.seating_count + 1)
                bench_x = bounds.min_x + bounds.width * ratio
                bench_y = bounds.center.y + bounds.depth * (0.13 if bench_index % 2 == 0 else -0.13)
                bench_point = Point2D(bench_x, bench_y)
                light_point = Point2D(bench_x + 2.0, bench_y)
                if road_clearance(bench_point) < 1.2 or road_clearance(light_point) < 0.8:
                    continue
                bench = self._outdoor_mesh(
                    f"{site_id}_bench_{bench_index:02d}", city.id,
                    Vec3(bench_x, bench_y, .43), Vec3(1.9, .62, .86), 0.0,
                    "bench", "street_bench", "public street bench wood metal", layer,
                    metadata={"landscape_site": site_id},
                )
                light = self._outdoor_mesh(
                    f"{site_id}_light_{bench_index:02d}", city.id,
                    Vec3(bench_x + 2.0, bench_y, 2.6), Vec3(.8, .8, 5.2), 0.0,
                    "street_light_asset", "street_light", "modern urban LED street light", layer,
                    metadata={"landscape_site": site_id},
                )
                scene.primitives.extend([
                    bench or self._box(f"{site_id}_bench_{bench_index:02d}", city.id, Vec3(bench_x, bench_y, 0.48), Vec3(2.4, 0.55, 0.18), 0.0, "bench", "street_furniture", layer, collision_enabled=False, metadata={"landscape_site": site_id}),
                    light or self._box(f"{site_id}_light_{bench_index:02d}", city.id, Vec3(bench_x + 2.0, bench_y, 1.8), Vec3(0.18, 0.18, 3.6), 0.0, "street_light", "street_furniture", layer, collision_enabled=False, metadata={"landscape_site": site_id}),
                ])

    def _compile_buildings(
        self,
        city: City,
        scene: GeometryScene,
        *,
        building_ids: set[str] | None = None,
    ) -> None:
        for building in city.iter_buildings():
            if building_ids is not None and building.id not in building_ids:
                continue
            prototype_id = building.metadata.get("prototype_id")
            prototype = (
                prototype_by_id(str(prototype_id))
                if prototype_id is not None
                else prototype_for_function(building.function)
            )
            scene.building_prototypes[building.id] = prototype.id
            self._compile_shell(building, prototype, scene)
            if self.include_interiors:
                from cityg.planning.interior_scope import floor_enabled
                active_floors=[f for f in building.floors if floor_enabled(city,building,f)]
                for floor in active_floors:
                    detail_start = len(scene.primitives)
                    self._compile_floor(building, floor, prototype, scene)
                    if building.metadata.get("massing_style"):
                        self._conform_building_details(
                            building, scene, detail_start, clip_interior_walls=True
                        )
                connector_start = len(scene.primitives)
                if len(active_floors)>1:
                    from dataclasses import replace
                    lo=min(f.level for f in active_floors);hi=max(f.level for f in active_floors)
                    scoped_building=replace(building,floors=active_floors,vertical_connectors=[
                        replace(c,from_level=max(lo,c.from_level),to_level=min(hi,c.to_level))
                        for c in building.vertical_connectors if max(lo,c.from_level)<min(hi,c.to_level)])
                    self._compile_vertical_connectors(scoped_building, scene)
                if building.metadata.get("massing_style"):
                    self._conform_building_details(
                        building, scene, connector_start, clip_interior_walls=False
                    )

    def _compile_shell(
        self, building: Building, prototype: BuildingPrototype, scene: GeometryScene
    ) -> None:
        from cityg.envelopes import envelope_config
        if envelope_config(building):
            from cityg.geometry.envelopes import compile_envelope
            compile_envelope(building, scene)
            return
        if building.metadata.get("massing_style"):
            start = len(scene.primitives)
            self._compile_rect_shell(building, prototype, scene)
            for primitive in scene.primitives[start:]:
                primitive.semantic_class = "collision_envelope"
                primitive.material_id = "collision_proxy"
            self._compile_visual_massing(building, prototype, scene)
            self._compile_facade_system(building, prototype, scene)
            return
        self._compile_rect_shell(building, prototype, scene)
        self._compile_facade_system(building, prototype, scene)

    def _compile_rect_shell(
        self, building: Building, prototype: BuildingPrototype, scene: GeometryScene
    ) -> None:
        bounds = building.footprint
        wall = prototype.wall_thickness_m
        layer = f"shell:{building.id}"
        connector_hole = None
        if building.vertical_connectors:
            connector_hole = Bounds2D(
                min(item.bounds.min_x for item in building.vertical_connectors),
                min(item.bounds.min_y for item in building.vertical_connectors),
                max(item.bounds.max_x for item in building.vertical_connectors),
                max(item.bounds.max_y for item in building.vertical_connectors),
            )
        for floor in building.floors:
            slab_z = floor.elevation_m - prototype.slab_thickness_m / 2
            if building.metadata.get('transport_core_retrofit'):
                from cityg.geometry.slab_openings import subtract_openings,transport_slab_holes
                for index,part in enumerate(subtract_openings(bounds,transport_slab_holes(building,floor))):
                    scene.primitives.append(self._bounds_box(
                        f'{floor.id}_slab_{index:02d}',floor.id,part,slab_z,
                        prototype.slab_thickness_m,'floor_slab','concrete',layer))
            elif floor.level > 0 and connector_hole is not None:
                self._add_slab_frame(
                    scene,
                    f"{floor.id}_slab",
                    floor.id,
                    bounds,
                    connector_hole,
                    slab_z,
                    prototype.slab_thickness_m,
                    layer,
                )
            else:
                scene.primitives.append(
                    self._bounds_box(
                        f"{floor.id}_slab",
                        floor.id,
                        bounds,
                        slab_z,
                        prototype.slab_thickness_m,
                        "floor_slab",
                        "concrete",
                        layer,
                    )
                )
            self._add_exterior_walls(building, floor, prototype, scene)

        top = max(floor.elevation_m + floor.height_m for floor in building.floors)
        scene.primitives.append(
            self._bounds_box(
                f"{building.id}_roof",
                building.id,
                bounds,
                top + 0.10,
                0.20,
                "roof",
                "roof",
                layer,
                metadata={"roof_style": prototype.roof_style},
            )
        )
        if prototype.roof_monitor:
            scene.primitives.append(
                self._box(
                    f"{building.id}_roof_monitor",
                    building.id,
                    Vec3(bounds.center.x, bounds.center.y, top + 0.65),
                    Vec3(bounds.width * 0.45, bounds.depth * 0.28, 1.10),
                    0.0,
                    "roof_monitor",
                    prototype.facade_material,
                    layer,
                )
            )
        elif prototype.id == "commercial_tower":
            scene.primitives.append(
                self._box(
                    f"{building.id}_mechanical_penthouse",
                    building.id,
                    Vec3(bounds.center.x, bounds.center.y, top + 0.45),
                    Vec3(bounds.width * 0.22, bounds.depth * 0.22, 0.70),
                    0.0,
                    "mechanical_roof",
                    "industrial_metal",
                    layer,
                )
            )

    def _compile_visual_massing(
        self, building: Building, prototype: BuildingPrototype, scene: GeometryScene
    ) -> None:
        layer = f"shell:{building.id}"
        top = max(floor.elevation_m + floor.height_m for floor in building.floors)
        parts = self._massing_parts(building)
        for part_index, part in enumerate(parts):
            part_top = max(building.floors[0].height_m, top * part["height_scale"])
            metadata = {
                "massing_style": building.metadata.get("massing_style", "bar"),
                "massing_variant": building.metadata.get("highrise", {}).get(
                    "massing_variant"
                ),
                "massing_part": part_index,
                "orientation_deg": part["rotation"],
                "visual_proxy": True,
            }
            scene.primitives.append(
                self._box(
                    f"{building.id}_massing_{part_index:02d}",
                    # This primitive spans multiple floors and therefore
                    # belongs to the building, not to Floor 0. Assigning it
                    # to the first floor causes strict floor views to include
                    # the entire tower shell and derive incorrect bounds.
                    building.id,
                    Vec3(part["center_x"], part["center_y"], part_top / 2),
                    Vec3(part["width"], part["depth"], part_top),
                    part["rotation"],
                    "exterior_wall",
                    prototype.facade_material,
                    layer,
                    collision_enabled=False,
                    metadata=metadata,
                )
            )
            scene.primitives.append(
                self._box(
                    f"{building.id}_massing_roof_{part_index:02d}",
                    building.id,
                    Vec3(part["center_x"], part["center_y"], part_top + 0.10),
                    Vec3(part["width"] * 1.01, part["depth"] * 1.01, 0.20),
                    part["rotation"],
                    "roof",
                    "roof",
                    layer,
                    collision_enabled=False,
                    metadata=metadata,
                )
            )
            for floor in building.floors:
                if floor.elevation_m >= part_top - 0.2:
                    continue
                if building.metadata.get('transport_core_retrofit'):
                    from cityg.geometry.slab_openings import subtract_openings,transport_slab_holes
                    if abs(part['rotation']%360)>1e-7:
                        raise ValueError('Transport slab openings require axis-aligned massing')
                    outer=Bounds2D(part['center_x']-part['width']/2,part['center_y']-part['depth']/2,
                        part['center_x']+part['width']/2,part['center_y']+part['depth']/2)
                    for index,cut in enumerate(subtract_openings(outer,transport_slab_holes(building,floor))):
                        scene.primitives.append(self._box(
                            f'{floor.id}_massing_slab_{part_index:02d}_opening_{index:02d}',floor.id,
                            Vec3(cut.center.x,cut.center.y,floor.elevation_m-.071),
                            Vec3(cut.width,cut.depth,.14),0.,'floor_slab','concrete',layer,
                            collision_enabled=False,metadata=metadata))
                    continue
                scene.primitives.append(
                    self._box(
                        f"{floor.id}_massing_slab_{part_index:02d}",
                        floor.id,
                        Vec3(
                            part["center_x"],
                            part["center_y"],
                            floor.elevation_m,
                        ),
                        Vec3(part["width"], part["depth"], 0.14),
                        part["rotation"],
                        "floor_slab",
                        "concrete",
                        layer,
                        collision_enabled=False,
                        metadata=metadata,
                    )
                )

        # Roof features must be anchored to the highest realized massing
        # part.  High-rise variants deliberately place the first part at a
        # lower podium height, so using ``parts[0]`` here leaves a feature
        # horizontally over the podium while its Z is computed from the
        # tower height (a visibly floating red/metallic box).
        roof_part = max(parts, key=lambda part: float(part.get("height_scale", 0.0)))
        if prototype.roof_monitor or prototype.id == "commercial_tower":
            semantic = (
                "roof_monitor" if prototype.roof_monitor else "mechanical_roof"
            )
            material = (
                prototype.facade_material
                if prototype.roof_monitor
                else "industrial_metal"
            )
            scene.primitives.append(
                self._box(
                    f"{building.id}_visual_roof_feature",
                    building.id,
                    Vec3(roof_part["center_x"], roof_part["center_y"], top + 0.55),
                    Vec3(roof_part["width"] * 0.28, roof_part["depth"] * 0.32, 0.90),
                    roof_part["rotation"],
                    semantic,
                    material,
                    layer,
                    collision_enabled=False,
                    metadata={"visual_proxy": True},
                )
            )

    @staticmethod
    def _massing_parts(building: Building) -> list[dict[str, float]]:
        if building.metadata.get('interior_layout_contract', {}).get('source') == 'new_scene_rectangular_interior_v1':
            if (building.metadata.get('massing_style') != 'bar'
                    or abs(float(building.metadata.get('orientation_deg', 0))) > 1e-6
                    or building.metadata.get('highrise', {}).get('enabled')):
                raise ValueError('Interior rectangular shell contract conflicts with massing')
            b = building.footprint
            # This capability uses the same physical plate for planning and
            # rendering. Do not shrink already dimensioned interior spaces by
            # the legacy visual-only bar grammar's 0.96/0.64 factors.
            return [{'center_x': b.center.x, 'center_y': b.center.y,
                     'width': b.width, 'depth': b.depth, 'height_scale': 1., 'rotation': 0.}]
        if building.metadata.get("massing_style") == "tower_podium":
            highrise = building.metadata.get("highrise", {})
            return GeometryCompiler._align_massing_heights_to_floors(
                building,
                HighRisePolicy.massing_parts(
                    building.footprint,
                    len(building.floors),
                    str(highrise.get("massing_variant", "standard")),
                    orientation_deg=float(
                        building.metadata.get("orientation_deg", 0.0)
                    ),
                ),
            )
        bounds = building.footprint
        rotation = float(building.metadata.get("orientation_deg", 0.0))
        angle = math.radians(rotation)
        cos_angle = abs(math.cos(angle))
        sin_angle = abs(math.sin(angle))
        raw_width = bounds.width
        raw_depth = bounds.depth
        rotated_width = cos_angle * raw_width + sin_angle * raw_depth
        rotated_depth = sin_angle * raw_width + cos_angle * raw_depth
        fit = 0.90 * min(
            bounds.width / max(rotated_width, 1e-6),
            bounds.depth / max(rotated_depth, 1e-6),
        )
        width = raw_width * fit
        depth = raw_depth * fit
        style = str(building.metadata.get("massing_style", "bar"))
        highrise = building.metadata.get("highrise", {})
        podium_ratio = max(
            0.12,
            float(highrise.get("podium_floors", 2))
            / max(1, len(building.floors)),
        )
        highrise_variant = str(highrise.get("massing_variant", "standard"))
        tower_podium_variants = {
            # Each option retains one continuous full-height tower over a
            # connected podium, so silhouette diversity cannot break the core.
            "standard": (
                (0.0, 0.04, 0.56, 0.54, 1.0),
                (0.0, -0.04, 0.98, 0.78, podium_ratio),
            ),
            "setback": (
                (0.02, 0.06, 0.42, 0.43, 1.0),
                (0.0, 0.03, 0.58, 0.56, 0.68),
                (0.0, -0.04, 0.98, 0.78, podium_ratio),
            ),
            "offset": (
                (0.13, 0.08, 0.52, 0.49, 1.0),
                (0.0, -0.04, 0.98, 0.78, podium_ratio),
            ),
            "slender_landmark": (
                (0.0, 0.05, 0.38, 0.45, 1.0),
                (0.0, 0.02, 0.50, 0.55, 0.34),
                (0.0, -0.04, 0.98, 0.78, podium_ratio),
            ),
        }
        definitions: dict[str, tuple[tuple[float, float, float, float, float], ...]] = {
            "bar": ((0.0, 0.0, 0.96, 0.64, 1.0),),
            "l_shape": (
                (0.0, -0.30, 0.96, 0.36, 1.0),
                (-0.31, 0.06, 0.34, 0.76, 0.82),
            ),
            "u_shape": (
                (0.0, -0.34, 0.96, 0.30, 0.92),
                (-0.35, 0.04, 0.26, 0.76, 1.0),
                (0.35, 0.04, 0.26, 0.76, 0.84),
            ),
            "t_shape": (
                (0.0, 0.31, 0.96, 0.32, 1.0),
                (0.0, -0.08, 0.32, 0.70, 0.86),
            ),
            # Additional footprint grammars used by the building archetype
            # catalog.  They remain visual-only compositions over the
            # validated rectangular envelope, just like the original L/U/T
            # grammar.  Floor/room details are conformed against these parts
            # later in the compilation pass.
            "h_shape": (
                (0.0, -0.30, 0.96, 0.24, 1.0),
                (0.0, 0.30, 0.96, 0.24, 1.0),
                (0.0, 0.0, 0.26, 0.48, 1.0),
            ),
            "courtyard": (
                (0.0, -0.36, 0.96, 0.20, 1.0),
                (0.0, 0.36, 0.96, 0.20, 1.0),
                (-0.38, 0.0, 0.20, 0.56, 1.0),
                (0.38, 0.0, 0.20, 0.56, 1.0),
            ),
            "cross": (
                (0.0, 0.0, 0.96, 0.25, 1.0),
                (0.0, 0.0, 0.25, 0.96, 1.0),
            ),
            "stepped_bar": (
                (0.0, 0.0, 0.96, 0.64, 0.58),
                (0.0, 0.0, 0.86, 0.58, 0.78),
                (0.0, 0.0, 0.74, 0.52, 1.0),
            ),
            "tower_podium": tower_podium_variants.get(
                highrise_variant, tower_podium_variants["standard"]
            ),
        }
        selected = definitions.get(style, definitions["bar"])
        raw_parameters = building.metadata.get("massing_parameters", {})
        parameters = raw_parameters if isinstance(raw_parameters, dict) else {}
        width_scale = min(1.0, max(0.55, float(parameters.get("width_scale", 1.0))))
        depth_scale = min(1.0, max(0.40, float(parameters.get("depth_scale", 1.0))))
        signature_offset_x = min(0.22, max(-0.22, float(parameters.get("offset_x", 0.0))))
        signature_offset_y = min(0.22, max(-0.22, float(parameters.get("offset_y", 0.0))))
        cos_signed = math.cos(angle)
        sin_signed = math.sin(angle)
        parts: list[dict[str, float]] = []
        for local_x, local_y, scale_x, scale_y, height_scale in selected:
            scale_x *= width_scale
            scale_y *= depth_scale
            local_x += signature_offset_x
            local_y += signature_offset_y
            offset_x = local_x * width
            offset_y = local_y * depth
            parts.append(
                {
                    "center_x": bounds.center.x
                    + offset_x * cos_signed
                    - offset_y * sin_signed,
                    "center_y": bounds.center.y
                    + offset_x * sin_signed
                    + offset_y * cos_signed,
                    "width": width * scale_x,
                    "depth": depth * scale_y,
                    "height_scale": height_scale,
                    "rotation": rotation,
                }
            )
        return GeometryCompiler._align_massing_heights_to_floors(building, parts)

    @staticmethod
    def _align_massing_heights_to_floors(
        building: Building,
        parts: list[dict[str, float]],
    ) -> list[dict[str, float]]:
        """Snap every massing tier to a complete physical floor boundary.

        Massing grammars express tier heights as normalized silhouette ratios.
        Applying those ratios directly can place a setback roof halfway through
        a floor. Walls happen to be clipped at their center height, while doors
        and headers can then remain above that partial roof and look like panels
        standing on the roof. Preserve the grammar's intended number of active
        floors, but realize its height at the corresponding physical ceiling.
        This also works when individual floor heights are not uniform.
        """

        ordered_floors = sorted(building.floors, key=lambda item: item.elevation_m)
        if not ordered_floors:
            return [dict(part) for part in parts]
        floor_count = len(ordered_floors)
        building_top = max(
            floor.elevation_m + floor.height_m for floor in ordered_floors
        )
        if building_top <= 1e-6:
            return [dict(part) for part in parts]

        aligned = []
        for source in parts:
            part = dict(source)
            requested_scale = min(1.0, max(0.0, float(part["height_scale"])))
            active_floor_count = sum(
                (index + 0.5) / floor_count <= requested_scale + 1e-6
                for index in range(floor_count)
            )
            active_floor_count = min(floor_count, max(1, active_floor_count))
            realized_top = max(
                floor.elevation_m + floor.height_m
                for floor in ordered_floors[:active_floor_count]
            )
            part["height_scale"] = min(1.0, realized_top / building_top)
            aligned.append(part)
        return aligned

    @classmethod
    def _massing_frame(cls, building: Building) -> dict:
        parts = cls._massing_parts(building)
        rotation = float(building.metadata.get("orientation_deg", 0.0))
        angle = math.radians(rotation)
        cos_angle = math.cos(angle)
        sin_angle = math.sin(angle)
        local_parts = []
        for part in parts:
            dx = part["center_x"] - building.footprint.center.x
            dy = part["center_y"] - building.footprint.center.y
            center_x = dx * cos_angle + dy * sin_angle
            center_y = -dx * sin_angle + dy * cos_angle
            local_parts.append(
                {
                    "min_x": center_x - part["width"] / 2,
                    "max_x": center_x + part["width"] / 2,
                    "min_y": center_y - part["depth"] / 2,
                    "max_y": center_y + part["depth"] / 2,
                    "height_scale": part["height_scale"],
                }
            )
        return {
            "rotation": rotation,
            "cos": cos_angle,
            "sin": sin_angle,
            "parts": local_parts,
            "min_x": min(part["min_x"] for part in local_parts),
            "max_x": max(part["max_x"] for part in local_parts),
            "min_y": min(part["min_y"] for part in local_parts),
            "max_y": max(part["max_y"] for part in local_parts),
        }

    @staticmethod
    def _point_in_part(x: float, y: float, part: dict, tolerance=1e-6) -> bool:
        return (
            part["min_x"] - tolerance <= x <= part["max_x"] + tolerance
            and part["min_y"] - tolerance <= y <= part["max_y"] + tolerance
        )

    @staticmethod
    def _frame_at_height(frame: dict, z: float, building_top: float) -> dict:
        eligible = [
            part
            for part in frame["parts"]
            if z <= building_top * part["height_scale"] + 1e-6
        ]
        if not eligible:
            eligible = [max(frame["parts"], key=lambda item: item["height_scale"])]
        return {**frame, "parts": eligible}

    @classmethod
    def _map_to_massing(
        cls,
        building: Building,
        point_x: float,
        point_y: float,
        frame: dict,
        *,
        project: bool,
    ) -> tuple[float, float]:
        bounds = building.footprint
        x_ratio = (point_x - bounds.min_x) / bounds.width
        y_ratio = (point_y - bounds.min_y) / bounds.depth
        local_x = frame["min_x"] + x_ratio * (frame["max_x"] - frame["min_x"])
        local_y = frame["min_y"] + y_ratio * (frame["max_y"] - frame["min_y"])
        if project and not any(
            cls._point_in_part(local_x, local_y, part) for part in frame["parts"]
        ):
            candidates = []
            for part in frame["parts"]:
                clipped_x = min(max(local_x, part["min_x"]), part["max_x"])
                clipped_y = min(max(local_y, part["min_y"]), part["max_y"])
                distance = (local_x - clipped_x) ** 2 + (local_y - clipped_y) ** 2
                candidates.append((distance, clipped_x, clipped_y))
            _, local_x, local_y = min(candidates)
        world_x = (
            building.footprint.center.x
            + local_x * frame["cos"]
            - local_y * frame["sin"]
        )
        world_y = (
            building.footprint.center.y
            + local_x * frame["sin"]
            + local_y * frame["cos"]
        )
        return world_x, world_y

    @staticmethod
    def _fit_rect_to_massing_parts(
        local_x: float,
        local_y: float,
        size_x: float,
        size_y: float,
        frame: dict,
        z: float,
        building_top: float,
        *,
        clearance: float = 0.035,
    ) -> tuple[float, float, bool, float, float]:
        """Fit a complete XY rectangle inside one realized massing part.

        Center-only projection is sufficient for points, but not for doors:
        their wall-thickness remains visible after the center reaches a
        setback/concave edge.  Pick the nearest part that can contain the
        entire rectangle and clamp the center by its half extents.
        """

        half_x = abs(float(size_x)) / 2 + clearance
        half_y = abs(float(size_y)) / 2 + clearance
        active_parts = [
            part
            for part in frame["parts"]
            if z <= building_top * part["height_scale"] + 1e-6
        ]
        if not active_parts:
            active_parts = [max(frame["parts"], key=lambda item: item["height_scale"])]
        candidates = []
        for part in active_parts:
            width = part["max_x"] - part["min_x"]
            depth = part["max_y"] - part["min_y"]
            if width >= 2 * half_x and depth >= 2 * half_y:
                fitted_x = min(max(local_x, part["min_x"] + half_x), part["max_x"] - half_x)
                fitted_y = min(max(local_y, part["min_y"] + half_y), part["max_y"] - half_y)
                candidates.append(
                    ((fitted_x - local_x) ** 2 + (fitted_y - local_y) ** 2, fitted_x, fitted_y)
                )
        if candidates:
            _, fitted_x, fitted_y = min(candidates)
            return (
                fitted_x,
                fitted_y,
                abs(fitted_x - local_x) > 1e-5 or abs(fitted_y - local_y) > 1e-5,
                size_x,
                size_y,
            )

        # Extremely narrow parts can be smaller than a nominal door.  Shrink
        # the visible panel to the largest safe rectangle instead of letting
        # it protrude beyond the envelope.
        nearest = []
        for part in active_parts:
            clipped_x = min(max(local_x, part["min_x"]), part["max_x"])
            clipped_y = min(max(local_y, part["min_y"]), part["max_y"])
            nearest.append(((clipped_x - local_x) ** 2 + (clipped_y - local_y) ** 2, part))
        _, part = min(nearest, key=lambda item: item[0])
        fitted_x = (part["min_x"] + part["max_x"]) / 2
        fitted_y = (part["min_y"] + part["max_y"]) / 2
        fitted_size_x = min(abs(size_x), max(0.05, part["max_x"] - part["min_x"] - 2 * clearance))
        fitted_size_y = min(abs(size_y), max(0.05, part["max_y"] - part["min_y"] - 2 * clearance))
        return fitted_x, fitted_y, True, fitted_size_x, fitted_size_y

    def _door_fit_geometry(
        self,
        building: Building,
        primitive,
        frame: dict,
        building_top: float,
        *,
        required_top_z: float | None = None,
    ) -> tuple[float, float, float, float, bool]:
        """Return a door's realized local center and complete XY size."""

        bounds = building.footprint
        scale_x = (frame["max_x"] - frame["min_x"]) / bounds.width
        scale_y = (frame["max_y"] - frame["min_y"]) / bounds.depth
        local_x = frame["min_x"] + (
            (primitive.center.x - bounds.min_x) / bounds.width
        ) * (frame["max_x"] - frame["min_x"])
        local_y = frame["min_y"] + (
            (primitive.center.y - bounds.min_y) / bounds.depth
        ) * (frame["max_y"] - frame["min_y"])
        size_x = primitive.size.x * scale_x
        size_y = primitive.size.y * scale_y
        if building.metadata.get('interior_layout_contract', {}).get('source') == 'new_scene_rectangular_interior_v1':
            # A boundary-centered door straddles a wall by its thickness. In
            # the exact rectangular contract it must not be pushed inward as
            # if it were furniture fitted inside a legacy visual massing part.
            return local_x, local_y, size_x, size_y, False
        local_x, local_y, fitted, size_x, size_y = self._fit_rect_to_massing_parts(
            local_x,
            local_y,
            size_x,
            size_y,
            frame,
            (
                float(required_top_z)
                if required_top_z is not None
                else primitive.center.z + primitive.size.z / 2
            ),
            building_top,
        )
        return local_x, local_y, size_x, size_y, fitted

    def _conform_door_detail(
        self,
        building: Building,
        primitive,
        frame: dict,
        building_top: float,
        scene: GeometryScene,
        *,
        required_top_z: float | None = None,
    ) -> None:
        """Conform a door panel, including its wall thickness, to massing."""

        local_x, local_y, size_x, size_y, fitted = self._door_fit_geometry(
            building,
            primitive,
            frame,
            building_top,
            required_top_z=required_top_z,
        )
        bounds = building.footprint
        world_x = bounds.center.x + local_x * frame["cos"] - local_y * frame["sin"]
        world_y = bounds.center.y + local_x * frame["sin"] + local_y * frame["cos"]
        primitive.center = Vec3(world_x, world_y, primitive.center.z)
        primitive.size = Vec3(size_x, size_y, primitive.size.z)
        primitive.rotation_z_deg += frame["rotation"]
        primitive.metadata.update(
            {
                "massing_conformed": True,
                "massing_fitted": fitted,
                "massing_fit_clearance_m": 0.035,
                "massing_style": building.metadata.get("massing_style"),
            }
        )
        scene.primitives.append(primitive)

    def _conform_building_details(
        self,
        building: Building,
        scene: GeometryScene,
        start_index: int,
        *,
        clip_interior_walls: bool,
    ) -> None:
        frame = self._massing_frame(building)
        scale_x = (frame["max_x"] - frame["min_x"]) / building.footprint.width
        scale_y = (frame["max_y"] - frame["min_y"]) / building.footprint.depth
        source = scene.primitives[start_index:]
        del scene.primitives[start_index:]
        floors_by_id = {floor.id: floor for floor in building.floors}
        # Doors are owned by their door entity and furniture is owned by its
        # object entity.  Their layer is the stable link back to the floor.
        # Keeping this mapping here lets us distinguish details that were
        # already planned in a realized high-rise floor plate from legacy
        # footprint-relative details.
        floors_by_layer = {f"floor:{floor.id}": floor for floor in building.floors}
        building_top = max(
            floor.elevation_m + floor.height_m for floor in building.floors
        )
        connector_ids = {connector.id for connector in building.vertical_connectors}
        # Cache the realized door opening intervals so clipped walls use the
        # same location as the rendered door panel.
        door_fits = {}
        for candidate in source:
            if candidate.semantic_class != "door":
                continue
            floor = floors_by_layer.get(candidate.layer_id)
            plate = floor.metadata.get("realized_floor_plate", {}) if floor else {}
            if plate.get("source") == "highrise_massing_outline_v1":
                continue
            door_fits[candidate.owner_id] = (
                *self._door_fit_geometry(
                    building,
                    candidate,
                    frame,
                    building_top,
                    required_top_z=(
                        floor.elevation_m + floor.height_m
                        if floor is not None
                        else candidate.center.z + candidate.size.z / 2
                    ),
                ),
                set(candidate.metadata.get("room_ids", [])),
                candidate.metadata.get("wall_axis"),
            )
        for primitive in source:
            if primitive.metadata.get("metric_room_placement") and primitive.semantic_class.startswith("furniture_"):
                # Already laid out in actual floor metres, independent of the
                # larger canonical template. Only apply the building rotation.
                metric = primitive.metadata["metric_room_placement"]
                bounds = building.footprint
                if (metric["source_footprint"] != [bounds.min_x,bounds.min_y,bounds.max_x,bounds.max_y]
                    or (metric.get('source_massing_parts') is not None and metric['source_massing_parts']!=frame['parts'])
                    or any(abs(a-b)>1e-6 for a,b in zip(metric["source_frame_bounds"],
                                                       [frame[k] for k in ("min_x","min_y","max_x","max_y")]))):
                    raise ValueError("Metric furniture frame changed; replan affected room")
                # A metric room placement has already passed room containment,
                # access and collision checks. Re-fitting it into an arbitrary
                # massing part would separate groups or move furniture outside
                # its owning room. Only the rigid building rotation remains.
                x=primitive.center.x-bounds.center.x
                y=primitive.center.y-bounds.center.y
                primitive.center=Vec3(bounds.center.x+x*frame['cos']-y*frame['sin'],
                                      bounds.center.y+x*frame['sin']+y*frame['cos'],primitive.center.z)
                primitive.rotation_z_deg+=frame['rotation']
                primitive.metadata.update(massing_conformed=True,massing_fitted=False,
                                          coordinate_frame='realized_metric_room')
                scene.primitives.append(primitive)
                continue
            realized_floor = floors_by_layer.get(primitive.layer_id)
            realized_plate = (
                realized_floor.metadata.get("realized_floor_plate", {})
                if realized_floor is not None
                else {}
            )
            if (
                realized_plate.get("source") == "highrise_massing_outline_v1"
                and (
                    # The shared core is planned inside the intersection of realized plates.
                    primitive.owner_id in connector_ids
                    or primitive.semantic_class == "door"
                    or primitive.semantic_class.startswith("furniture_")
                )
            ):
                self._conform_realized_floor_detail(
                    building, primitive, frame, building_top, scene
                )
                continue
            if primitive.semantic_class == "door":
                self._conform_door_detail(
                    building,
                    primitive,
                    frame,
                    building_top,
                    scene,
                    required_top_z=(
                        realized_floor.elevation_m + realized_floor.height_m
                        if realized_floor is not None
                        else primitive.center.z + primitive.size.z / 2
                    ),
                )
                continue
            if clip_interior_walls and primitive.semantic_class == "interior_wall":
                realized_floor = floors_by_id.get(primitive.owner_id)
                realized_plate = (
                    realized_floor.metadata.get("realized_floor_plate", {})
                    if realized_floor is not None
                    else {}
                )
                if realized_plate.get("source") == "highrise_massing_outline_v1":
                    self._conform_realized_floor_wall(
                        building,
                        primitive,
                        frame,
                        building_top,
                        scene,
                    )
                    continue
                if primitive.metadata.get("wall_role") == "door_header":
                    door_fit = door_fits.get(primitive.metadata.get("door_id"))
                    if door_fit is not None:
                        local_x, local_y, size_x, size_y, fitted, _, _ = door_fit
                        world_x = (
                            building.footprint.center.x
                            + local_x * frame["cos"]
                            - local_y * frame["sin"]
                        )
                        world_y = (
                            building.footprint.center.y
                            + local_x * frame["sin"]
                            + local_y * frame["cos"]
                        )
                        primitive.center = Vec3(world_x, world_y, primitive.center.z)
                        primitive.size = Vec3(size_x, size_y, primitive.size.z)
                        primitive.rotation_z_deg += frame["rotation"]
                        primitive.metadata.update(
                            {
                                "massing_conformed": True,
                                "massing_fitted": fitted,
                                "massing_clipped": True,
                                "massing_fit_clearance_m": 0.035,
                                "massing_style": building.metadata.get("massing_style"),
                            }
                        )
                        scene.primitives.append(primitive)
                        continue
                local_center_x = (
                    frame["min_x"]
                    + (primitive.center.x - building.footprint.min_x)
                    / building.footprint.width
                    * (frame["max_x"] - frame["min_x"])
                )
                local_center_y = (
                    frame["min_y"]
                    + (primitive.center.y - building.footprint.min_y)
                    / building.footprint.depth
                    * (frame["max_y"] - frame["min_y"])
                )
                primitive_min_x = local_center_x - primitive.size.x * scale_x / 2
                primitive_max_x = local_center_x + primitive.size.x * scale_x / 2
                primitive_min_y = local_center_y - primitive.size.y * scale_y / 2
                primitive_max_y = local_center_y + primitive.size.y * scale_y / 2
                primitive_bottom_z = primitive.center.z - primitive.size.z / 2
                primitive_top_z = primitive.center.z + primitive.size.z / 2
                fragment_index = 0
                for part in frame["parts"]:
                    part_top_z = building_top * part["height_scale"]
                    if primitive_bottom_z >= part_top_z - 1e-6:
                        continue
                    clipped_top_z = min(primitive_top_z, part_top_z)
                    clipped_height = clipped_top_z - primitive_bottom_z
                    if clipped_height <= 1e-5:
                        continue
                    clipped_center_z = primitive_bottom_z + clipped_height / 2
                    min_x = max(primitive_min_x, part["min_x"])
                    max_x = min(primitive_max_x, part["max_x"])
                    min_y = max(primitive_min_y, part["min_y"])
                    max_y = min(primitive_max_y, part["max_y"])
                    if max_x - min_x <= 1e-5 or max_y - min_y <= 1e-5:
                        continue
                    wall_axis = "horizontal" if primitive.size.x >= primitive.size.y else "vertical"
                    room_ids = set(primitive.metadata.get("room_ids", []))
                    openings = []
                    # A door header is the wall volume *above* an opening;
                    # carving it with the door's XY interval would remove
                    # the lintel entirely.  Only boundary wall segments are
                    # split around the realized door panel.
                    if primitive.metadata.get("wall_role") == "door_header":
                        door_fits_for_wall = ()
                    else:
                        door_fits_for_wall = door_fits.values()
                    for door_x, door_y, door_size_x, door_size_y, _, door_rooms, door_axis in door_fits_for_wall:
                        if room_ids and not room_ids.intersection(door_rooms):
                            continue
                        if door_axis != wall_axis:
                            continue
                        if wall_axis == "horizontal":
                            if abs(door_y - local_center_y) > 1.0:
                                continue
                            openings.append((door_x - door_size_x / 2, door_x + door_size_x / 2))
                        else:
                            if abs(door_x - local_center_x) > 1.0:
                                continue
                            openings.append((door_y - door_size_y / 2, door_y + door_size_y / 2))
                    span_start, span_end = (min_x, max_x) if wall_axis == "horizontal" else (min_y, max_y)
                    for segment_start, segment_end in self._segments_excluding(
                        span_start, span_end, openings
                    ):
                        if segment_end - segment_start <= 1e-5:
                            continue
                        local_x = (
                            (segment_start + segment_end) / 2
                            if wall_axis == "horizontal"
                            else (min_x + max_x) / 2
                        )
                        local_y = (
                            (min_y + max_y) / 2
                            if wall_axis == "horizontal"
                            else (segment_start + segment_end) / 2
                        )
                        segment_size_x = (
                            segment_end - segment_start
                            if wall_axis == "horizontal"
                            else max_x - min_x
                        )
                        segment_size_y = (
                            max_y - min_y
                            if wall_axis == "horizontal"
                            else segment_end - segment_start
                        )
                        world_x = (
                            building.footprint.center.x
                            + local_x * frame["cos"]
                            - local_y * frame["sin"]
                        )
                        world_y = (
                            building.footprint.center.y
                            + local_x * frame["sin"]
                            + local_y * frame["cos"]
                        )
                        scene.primitives.append(
                            self._box(
                                f"{primitive.id}_clip_{fragment_index:02d}",
                                primitive.owner_id,
                                Vec3(world_x, world_y, clipped_center_z),
                                Vec3(segment_size_x, segment_size_y, clipped_height),
                                primitive.rotation_z_deg + frame["rotation"],
                                primitive.semantic_class,
                                primitive.material_id,
                                primitive.layer_id,
                                body_type=primitive.body_type,
                                instance_key=primitive.instance_key,
                                metadata={
                                    **primitive.metadata,
                                    "massing_clipped": True,
                                    "massing_style": building.metadata.get("massing_style"),
                                },
                                collision_enabled=primitive.collision_enabled,
                            )
                        )
                        fragment_index += 1
                continue

            if primitive.semantic_class.startswith("furniture_"):
                object_center = primitive.metadata.get("canonical_object_center", {})
                component_offset = primitive.metadata.get(
                    "canonical_component_offset", {}
                )
                try:
                    source_object_x = float(object_center["x"])
                    source_object_y = float(object_center["y"])
                    offset_x = float(component_offset["x"]) * scale_x
                    offset_y = float(component_offset["y"]) * scale_y
                    object_width = float(primitive.metadata["object_width_m"])
                    object_depth = float(primitive.metadata["object_depth_m"])
                    object_rotation = math.radians(
                        float(primitive.metadata["object_rotation_deg"])
                    )
                except (KeyError, TypeError, ValueError):
                    source_object_x = source_object_y = None
                if source_object_x is not None and source_object_y is not None:
                    intended_x = (
                        frame["min_x"]
                        + (source_object_x - building.footprint.min_x)
                        / building.footprint.width
                        * (frame["max_x"] - frame["min_x"])
                    )
                    intended_y = (
                        frame["min_y"]
                        + (source_object_y - building.footprint.min_y)
                        / building.footprint.depth
                        * (frame["max_y"] - frame["min_y"])
                    )
                    half_x = (
                        abs(math.cos(object_rotation)) * object_width
                        + abs(math.sin(object_rotation)) * object_depth
                    ) * scale_x / 2
                    half_y = (
                        abs(math.sin(object_rotation)) * object_width
                        + abs(math.cos(object_rotation)) * object_depth
                    ) * scale_y / 2
                    # Keep the complete visible asset footprint away from a
                    # clipped massing edge.  The semantic box may be valid at
                    # exact contact, but a textured GLB has bevels and
                    # interpolation that make wall penetration obvious.
                    interior_clearance = 0.35
                    half_x += interior_clearance
                    half_y += interior_clearance
                    candidates = []
                    for part in frame["parts"]:
                        if (
                            primitive.center.z + primitive.size.z / 2
                            > building_top * part["height_scale"] + 1e-6
                        ):
                            continue
                        if (
                            part["max_x"] - part["min_x"] < 2 * half_x
                            or part["max_y"] - part["min_y"] < 2 * half_y
                        ):
                            continue
                        fitted_x = min(
                            max(intended_x, part["min_x"] + half_x),
                            part["max_x"] - half_x,
                        )
                        fitted_y = min(
                            max(intended_y, part["min_y"] + half_y),
                            part["max_y"] - half_y,
                        )
                        distance = (fitted_x - intended_x) ** 2 + (
                            fitted_y - intended_y
                        ) ** 2
                        candidates.append((distance, fitted_x, fitted_y))
                    if candidates:
                        _, object_local_x, object_local_y = min(candidates)
                        component_local_x = object_local_x + offset_x
                        component_local_y = object_local_y + offset_y
                        world_x = (
                            building.footprint.center.x
                            + component_local_x * frame["cos"]
                            - component_local_y * frame["sin"]
                        )
                        world_y = (
                            building.footprint.center.y
                            + component_local_x * frame["sin"]
                            + component_local_y * frame["cos"]
                        )
                        primitive.center = Vec3(world_x, world_y, primitive.center.z)
                        primitive.size = Vec3(
                            primitive.size.x * scale_x,
                            primitive.size.y * scale_y,
                            primitive.size.z,
                        )
                        primitive.rotation_z_deg += frame["rotation"]
                        primitive.metadata.update(
                            {
                                "massing_conformed": True,
                                "massing_fitted": True,
                                "massing_style": building.metadata.get(
                                    "massing_style"
                                ),
                            }
                        )
                        scene.primitives.append(primitive)
                        continue

            projection_frame = self._frame_at_height(
                frame,
                primitive.center.z + primitive.size.z / 2,
                building_top,
            )
            world_x, world_y = self._map_to_massing(
                building,
                primitive.center.x,
                primitive.center.y,
                projection_frame,
                project=True,
            )
            primitive.center = Vec3(world_x, world_y, primitive.center.z)
            primitive.size = Vec3(
                primitive.size.x * scale_x,
                primitive.size.y * scale_y,
                primitive.size.z,
            )
            primitive.rotation_z_deg += frame["rotation"]
            primitive.metadata.update(
                {
                    "massing_conformed": True,
                    "massing_style": building.metadata.get("massing_style"),
                }
            )
            scene.primitives.append(primitive)

        # A low-rise L/U/T massing can clip a rectangular room at a concave
        # setback.  The authoritative collision/layout model remains the
        # planned room, but isolated Room mode must still render a closed,
        # realizable inspection shell.  Add non-colliding caps at the missing
        # edges of the *realized* wall envelope after clipping.  This keeps the
        # cap local to the actual massing instead of resurrecting a wall in the
        # excluded void.
        if clip_interior_walls:
            self._ensure_room_view_boundaries(building, scene)

    def _ensure_room_view_boundaries(
        self,
        building: Building,
        scene: GeometryScene,
    ) -> None:
        """Close clipped room envelopes for isolated Viewer inspection.

        Non-rectangular visual massing is allowed to trim legacy rectangular
        room plans.  When that happens, one of the room-owned wall fragments
        can disappear entirely.  Derive the visible envelope from the
        surviving wall fragments and add a room-only cap for any missing side.
        These caps are visual-only (no collision) and are never shown outside
        Room mode.
        """

        cos_angle = math.cos(math.radians(float(building.metadata.get("orientation_deg", 0.0))))
        sin_angle = math.sin(math.radians(float(building.metadata.get("orientation_deg", 0.0))))
        center_x = building.footprint.center.x
        center_y = building.footprint.center.y
        wall_t = 0.0621
        frame = self._massing_frame(building)
        for floor in building.floors:
            rooms = [room for room in floor.rooms if room.function != "corridor"]
            for room in rooms:
                walls = [
                    item
                    for item in scene.primitives
                    if item.layer_id == f"floor:{floor.id}"
                    and item.semantic_class == "interior_wall"
                    and room.id in item.metadata.get("room_ids", [])
                ]
                if not walls:
                    continue
                min_x = min_y = float("inf")
                max_x = max_y = float("-inf")
                for wall in walls:
                    angle = math.radians(float(wall.rotation_z_deg or 0.0))
                    c, s = math.cos(angle), math.sin(angle)
                    for sx in (-0.5, 0.5):
                        for sy in (-0.5, 0.5):
                            wx = wall.center.x + c * sx * wall.size.x - s * sy * wall.size.y
                            wy = wall.center.y + s * sx * wall.size.x + c * sy * wall.size.y
                            lx = (wx - center_x) * cos_angle + (wy - center_y) * sin_angle
                            ly = -(wx - center_x) * sin_angle + (wy - center_y) * cos_angle
                            min_x, max_x = min(min_x, lx), max(max_x, lx)
                            min_y, max_y = min(min_y, ly), max(max_y, ly)
                if not (max_x - min_x > 0.5 and max_y - min_y > 0.5):
                    continue
                # Metadata side labels describe the source boundary (for
                # example a corridor's ``north`` wall is the room's south
                # edge).  Classify surviving fragments by their realized
                # coordinates instead of trusting that source label.
                present: set[str] = set()
                for wall in walls:
                    lx = (wall.center.x - center_x) * cos_angle + (wall.center.y - center_y) * sin_angle
                    ly = -(wall.center.x - center_x) * sin_angle + (wall.center.y - center_y) * cos_angle
                    # A short horizontal fragment near a corner must not be
                    # mistaken for a complete east/west wall.  Classify only
                    # long-axis-compatible fragments; this is especially
                    # important after a door opening splits a boundary.
                    wall_side = wall.metadata.get("wall_side")
                    horizontal = (
                        wall_side in {"north", "south"}
                        if wall_side in {"north", "south", "east", "west"}
                        else wall.size.x >= wall.size.y
                    )
                    if not horizontal:
                        if abs(lx - min_x) <= 0.15:
                            present.add("west")
                        if abs(lx - max_x) <= 0.15:
                            present.add("east")
                    else:
                        if abs(ly - min_y) <= 0.15:
                            present.add("south")
                        if abs(ly - max_y) <= 0.15:
                            present.add("north")
                sides = (
                    ("west", min_x, "y", min_y, max_y),
                    ("east", max_x, "y", min_y, max_y),
                    ("south", min_y, "x", min_x, max_x),
                    ("north", max_y, "x", min_x, max_x),
                )
                for side, boundary, axis, start, end in sides:
                    if side in present or end - start <= 0.5:
                        continue
                    # A union AABB can cross the concave void of an L/U/T
                    # massing.  Snap the missing side to the best-overlapping
                    # realized part and clip its tangent span before emitting
                    # it; otherwise it would be another plate floating in the
                    # setback.
                    candidates = []
                    for part in frame["parts"]:
                        if axis == "x":
                            clipped_start = max(start, part["min_x"])
                            clipped_end = min(end, part["max_x"])
                            part_boundary = (
                                part["min_y"] + wall_t / 2
                                if side == "south"
                                else part["max_y"] - wall_t / 2
                            )
                        else:
                            clipped_start = max(start, part["min_y"])
                            clipped_end = min(end, part["max_y"])
                            part_boundary = (
                                part["min_x"] + wall_t / 2
                                if side == "west"
                                else part["max_x"] - wall_t / 2
                            )
                        if clipped_end - clipped_start > 0.5:
                            candidates.append((clipped_end - clipped_start, clipped_start, clipped_end, part_boundary))
                    if not candidates:
                        continue
                    _, start, end, boundary = max(candidates)
                    existing_caps = [
                        item
                        for item in scene.primitives
                        if item.metadata.get("room_isolation_cap")
                        and room.id in item.metadata.get("room_ids", [])
                        and item.metadata.get("wall_side") == side
                    ]
                    if any(
                        abs(float(item.metadata.get("realized_boundary", 1e9)) - boundary)
                        <= 1e-5
                        for item in existing_caps
                    ):
                        continue
                    cap_index = len(existing_caps)
                    if axis == "x":
                        local_x, local_y = (start + end) / 2, boundary
                        size = Vec3(end - start, wall_t, floor.height_m)
                    else:
                        local_x, local_y = boundary, (start + end) / 2
                        size = Vec3(wall_t, end - start, floor.height_m)
                    world_x = center_x + local_x * cos_angle - local_y * sin_angle
                    world_y = center_y + local_x * sin_angle + local_y * cos_angle
                    scene.primitives.append(
                        self._box(
                            f"{floor.id}_{room.id}_viewer_cap_{side}_{cap_index:02d}",
                            floor.id,
                            Vec3(world_x, world_y, floor.elevation_m + floor.height_m / 2),
                            size,
                            float(building.metadata.get("orientation_deg", 0.0)),
                            "interior_wall",
                            "interior_wall",
                            f"floor:{floor.id}",
                            collision_enabled=False,
                            metadata={
                                "room_ids": [room.id],
                                "wall_role": "room_view_cap",
                                "wall_side": side,
                                "viewer_room_only": True,
                                "room_isolation_cap": True,
                                "realized_boundary": boundary,
                                "massing_clipped": True,
                            },
                        )
                    )

    def _conform_realized_floor_wall(
        self,
        building: Building,
        primitive,
        frame: dict,
        building_top: float,
        scene: GeometryScene,
    ) -> None:
        """Conform a wall that was planned in a realized high-rise floor plate.

        ``ProgrammedCityPlanner`` already emits these walls in the selected
        floor-plate's building-local coordinates.  The legacy detail pass maps
        all primitives from the full building footprint into the massing frame,
        which scales an already-conformed wall a second time.  Keep the local
        wall coordinates intact, clip them against the massing part active at
        this height, and apply the building rotation once for rendering. Door
        openings are inset from room corners, so this height clip does not
        recreate the old corner cracks.
        """

        rotation = float(frame["rotation"])
        angle = math.radians(rotation)
        cos_angle = math.cos(angle)
        sin_angle = math.sin(angle)
        center_x = building.footprint.center.x
        center_y = building.footprint.center.y
        local_center_x = primitive.center.x - center_x
        local_center_y = primitive.center.y - center_y
        local_min_x = local_center_x - primitive.size.x / 2
        local_max_x = local_center_x + primitive.size.x / 2
        local_min_y = local_center_y - primitive.size.y / 2
        local_max_y = local_center_y + primitive.size.y / 2
        active_parts = [
            part
            for part in frame["parts"]
            if primitive.center.z <= building_top * part["height_scale"] + 1e-6
        ]
        if not active_parts:
            active_parts = [max(frame["parts"], key=lambda item: item["height_scale"])]
        # At a given height the lowest active massing tier is the broadest
        # valid envelope (podium at ground level, tower at upper levels).
        active_part = min(active_parts, key=lambda item: item["height_scale"])
        min_x = max(local_min_x, active_part["min_x"])
        max_x = min(local_max_x, active_part["max_x"])
        min_y = max(local_min_y, active_part["min_y"])
        max_y = min(local_max_y, active_part["max_y"])
        if max_x - min_x <= 1e-5 or max_y - min_y <= 1e-5:
            return
        local_x = (min_x + max_x) / 2
        local_y = (min_y + max_y) / 2
        world_x = center_x + local_x * cos_angle - local_y * sin_angle
        world_y = center_y + local_x * sin_angle + local_y * cos_angle
        scene.primitives.append(
            self._box(
                f"{primitive.id}_realized_plate",
                primitive.owner_id,
                Vec3(world_x, world_y, primitive.center.z),
                Vec3(max_x - min_x, max_y - min_y, primitive.size.z),
                primitive.rotation_z_deg + rotation,
                primitive.semantic_class,
                primitive.material_id,
                primitive.layer_id,
                body_type=primitive.body_type,
                instance_key=primitive.instance_key,
                metadata={
                    **primitive.metadata,
                    "massing_clipped": True,
                    "massing_style": building.metadata.get("massing_style"),
                    "coordinate_frame": "realized_floor_plate",
                },
                collision_enabled=primitive.collision_enabled,
            )
        )

    def _conform_realized_floor_detail(
        self,
        building: Building,
        primitive,
        frame: dict,
        building_top: float,
        scene: GeometryScene,
    ) -> None:
        """Transform a door/furniture item from floor-plate to world space.

        Room planning and object placement happen after the actual high-rise
        floor plate is selected.  Doors are already in that building-local
        metric frame. Furnishings may still come from a floor template whose
        room envelope is wider than a later tower tier, so fit the complete
        object footprint into the active massing part while preserving its
        local scale and relative component offsets.
        """

        angle = math.radians(float(frame["rotation"]))
        cos_angle = math.cos(angle)
        sin_angle = math.sin(angle)
        local_x = primitive.center.x - building.footprint.center.x
        local_y = primitive.center.y - building.footprint.center.y
        fitted = False
        if primitive.semantic_class == "door":
            local_x, local_y, fitted, fitted_size_x, fitted_size_y = self._fit_rect_to_massing_parts(
                local_x,
                local_y,
                primitive.size.x,
                primitive.size.y,
                frame,
                primitive.center.z + primitive.size.z / 2,
                building_top,
            )
            primitive.size = Vec3(fitted_size_x, fitted_size_y, primitive.size.z)
        elif primitive.semantic_class.startswith("furniture_"):
            object_center = primitive.metadata.get("canonical_object_center", {})
            try:
                source_object_x = float(object_center["x"])
                source_object_y = float(object_center["y"])
            except (KeyError, TypeError, ValueError):
                source_object_x = primitive.center.x
                source_object_y = primitive.center.y
            try:
                object_width = float(
                    primitive.metadata.get("object_width_m", primitive.size.x)
                )
                object_depth = float(
                    primitive.metadata.get("object_depth_m", primitive.size.y)
                )
                object_rotation = math.radians(
                    float(
                        primitive.metadata.get(
                            "object_rotation_deg", primitive.rotation_z_deg
                        )
                    )
                )
            except (TypeError, ValueError):
                object_width = primitive.size.x
                object_depth = primitive.size.y
                object_rotation = math.radians(primitive.rotation_z_deg)
            half_x = (
                abs(math.cos(object_rotation)) * object_width
                + abs(math.sin(object_rotation)) * object_depth
            ) / 2
            half_y = (
                abs(math.sin(object_rotation)) * object_width
                + abs(math.cos(object_rotation)) * object_depth
            ) / 2
            active_parts = [
                part
                for part in frame["parts"]
                if (
                    primitive.center.z + primitive.size.z / 2
                    <= building_top * part["height_scale"] + 1e-6
                )
            ]
            if not active_parts:
                active_parts = [
                    max(frame["parts"], key=lambda item: item["height_scale"])
                ]
            active_part = min(active_parts, key=lambda item: item["height_scale"])
            # Keep a small interior clearance from the rendered shell.  Exact
            # boundary fitting is geometrically inside the box but makes
            # furniture visibly pierce curtain walls and podium edges.
            interior_clearance = 0.35
            fit_half_x = half_x + interior_clearance
            fit_half_y = half_y + interior_clearance
            if active_part["max_x"] - active_part["min_x"] >= 2 * fit_half_x:
                object_local_x = min(
                    max(
                        source_object_x - building.footprint.center.x,
                        active_part["min_x"] + fit_half_x,
                    ),
                    active_part["max_x"] - fit_half_x,
                )
            else:
                object_local_x = (active_part["min_x"] + active_part["max_x"]) / 2
            if active_part["max_y"] - active_part["min_y"] >= 2 * fit_half_y:
                object_local_y = min(
                    max(
                        source_object_y - building.footprint.center.y,
                        active_part["min_y"] + fit_half_y,
                    ),
                    active_part["max_y"] - fit_half_y,
                )
            else:
                object_local_y = (active_part["min_y"] + active_part["max_y"]) / 2
            component_offset = primitive.metadata.get(
                "canonical_component_offset", {}
            )
            try:
                local_x = object_local_x + float(component_offset.get("x", 0.0))
                local_y = object_local_y + float(component_offset.get("y", 0.0))
            except (TypeError, ValueError):
                local_x, local_y = object_local_x, object_local_y
            fitted = abs(object_local_x - (source_object_x - building.footprint.center.x)) > 1e-5 or abs(
                object_local_y - (source_object_y - building.footprint.center.y)
            ) > 1e-5
        world_x = (
            building.footprint.center.x + local_x * cos_angle - local_y * sin_angle
        )
        world_y = (
            building.footprint.center.y + local_x * sin_angle + local_y * cos_angle
        )
        primitive.center = Vec3(world_x, world_y, primitive.center.z)
        primitive.rotation_z_deg += float(frame["rotation"])
        primitive.metadata.update(
            {
                "massing_conformed": True,
                "massing_fitted": fitted,
                "massing_style": building.metadata.get("massing_style"),
                "coordinate_frame": "realized_floor_plate",
            }
        )
        scene.primitives.append(primitive)

    def _compile_facade_system(
        self, building: Building, prototype: BuildingPrototype, scene: GeometryScene
    ) -> None:
        """Decorate the shell with visual-only windows and frontage elements.

        All pieces are non-colliding and live in the shell layer.  The validated
        room/door/navigation geometry therefore remains the authoritative
        simulation representation while the Viewer receives a much more legible
        architectural envelope.
        """
        highrise = bool(building.metadata.get("highrise", {}).get("enabled"))
        profile = facade_profile_for_building(
            building.function,
            len(building.floors),
            highrise=highrise,
            variant_key=str(
                building.metadata.get("facade_style_override") or building.id
            ),
        )
        style = facade_material_style(building, profile.style)
        # Apply the selected family palette to the primary shell as well as the
        # decorative grammar. Collision/topology are unchanged; only the visual
        # material assignment varies deterministically by building ID.
        layer = f"shell:{building.id}"
        for primitive in scene.primitives:
            if (
                primitive.layer_id == layer
                and primitive.semantic_class == "exterior_wall"
            ):
                primitive.material_id = style.wall_material
        frame = self._facade_frame(building)
        building_top = max(
            floor.elevation_m + floor.height_m for floor in building.floors
        )
        building_metadata = scene.metadata.setdefault("facade_buildings", {})
        ordered_floors = sorted(building.floors, key=lambda item: item.elevation_m)
        facade_asset_plan = (
            self.facade_asset_runtime.plan_for_building(
                building,
                zones={
                    profile.zone_for_ordinal(index)
                    for index in range(len(ordered_floors))
                },
            )
            if self.facade_asset_runtime is not None
            else FacadeBuildingAssetPlan(building.id, ())
        )
        ground_floor = ordered_floors[0]
        ground_mid = ground_floor.elevation_m + ground_floor.height_m * 0.5
        ground_parts = [
            part
            for part in frame["parts"]
            if ground_mid <= building_top * part["height_scale"] + 1e-6
        ]
        entrance_anchor = self._resolve_facade_entrance_anchor(
            building,
            ground_floor,
            ground_parts,
            frame,
            style,
            profile.zone_for_ordinal(0),
        )
        building_metadata[building.id] = {
            "system": (
                "grammar_v3_asset_hybrid"
                if facade_asset_plan.selections
                else "grammar_v3"
            ),
            "style": style.id,
            "appearance_plan": building.metadata.get("appearance_plan", {}),
            "wall_material": style.wall_material,
            "glass_material": style.glass_material,
            "frame_material": style.frame_material,
            "function": building.function,
            "highrise": highrise,
            "window_count": 0,
            "balcony_count": 0,
            "storefront_count": 0,
            "window_backing_count": 0,
            "mechanical_louver_count": 0,
            "zones": {
                "podium_floors": profile.podium_floors,
                "mechanical_levels": list(profile.mechanical_levels),
                "crown_floors": profile.crown_floors,
            },
            "asset_plan": facade_asset_plan.to_dict(),
            "resolved_asset_primitive_count": 0,
            "entrance_anchor": entrance_anchor,
        }
        for floor_ordinal, floor in enumerate(ordered_floors):
            facade_zone = profile.zone_for_ordinal(floor_ordinal)
            floor_mid = floor.elevation_m + floor.height_m * 0.5
            active_parts = [
                part
                for part in frame["parts"]
                if floor_mid <= building_top * part["height_scale"] + 1e-6
            ]
            if not active_parts:
                continue
            for part_index, part in enumerate(active_parts):
                self._compile_facade_part(
                    building,
                    floor,
                    part,
                    active_parts,
                    part_index,
                    frame,
                    style,
                    profile,
                    facade_zone,
                    floor_ordinal,
                    building_metadata[building.id],
                    building_top,
                    facade_asset_plan,
                    entrance_anchor,
                    scene,
                )
        if prototype.entrance_canopy and entrance_anchor is not None:
            self._add_visual_canopy(
                building,
                prototype,
                ground_floor,
                frame,
                entrance_anchor,
                scene,
            )
        self._compile_roof_edge_details(
            building, frame, style, building_top, scene
        )

    @classmethod
    def _facade_frame(cls, building: Building) -> dict:
        if building.metadata.get("massing_style"):
            return cls._massing_frame(building)
        bounds = building.footprint
        rotation = float(building.metadata.get("orientation_deg", 0.0))
        angle = math.radians(rotation)
        return {
            "rotation": rotation,
            "cos": math.cos(angle),
            "sin": math.sin(angle),
            "parts": [
                {
                    "min_x": -bounds.width / 2,
                    "max_x": bounds.width / 2,
                    "min_y": -bounds.depth / 2,
                    "max_y": bounds.depth / 2,
                    "height_scale": 1.0,
                }
            ],
        }

    @staticmethod
    def _facade_world_point(building: Building, frame: dict, x: float, y: float):
        return (
            building.footprint.center.x + x * frame["cos"] - y * frame["sin"],
            building.footprint.center.y + x * frame["sin"] + y * frame["cos"],
        )

    @staticmethod
    def _facade_side_data(part: dict, side: str):
        if side == "north":
            return part["min_x"], part["max_x"], part["max_y"], (0.0, 1.0), False
        if side == "south":
            return part["min_x"], part["max_x"], part["min_y"], (0.0, -1.0), False
        if side == "east":
            return part["min_y"], part["max_y"], part["max_x"], (1.0, 0.0), True
        return part["min_y"], part["max_y"], part["min_x"], (-1.0, 0.0), True

    @staticmethod
    def _facade_is_exposed(
        part: dict,
        other_parts: list[dict],
        tangent: float,
        boundary: float,
        normal: tuple[float, float],
        side_axis_swapped: bool,
    ) -> bool:
        if side_axis_swapped:
            point = (boundary + normal[0] * 0.10, tangent)
        else:
            point = (tangent, boundary + normal[1] * 0.10)
        for other in other_parts:
            if (
                other["min_x"] - 1e-6 <= point[0] <= other["max_x"] + 1e-6
                and other["min_y"] - 1e-6 <= point[1] <= other["max_y"] + 1e-6
            ):
                return False
        return True

    def _resolve_facade_entrance_anchor(
        self,
        building: Building,
        floor: Floor,
        active_parts: list[dict],
        frame: dict,
        style: FacadeStyle,
        facade_zone: str,
    ) -> dict[str, Any] | None:
        """Resolve one realized entrance bay shared by the door and canopy.

        The authored entrance lives on the coarse rectangular footprint, while
        facade modules live on rotated, possibly multi-part massing.  Map the
        authored point into the realized massing envelope, then choose the
        nearest *exposed* bay on the requested entrance side.  Returning this
        contract once avoids independent snapping rules for the door asset and
        its canopy, and prevents one entrance from being repeated on every
        massing part.
        """

        if not active_parts:
            return None
        side = str(building.metadata.get("entrance_side", "west")).lower()
        if side not in {"north", "south", "east", "west"}:
            side = "west"
        style = facade_style_for_face(building, style, side)
        bounds = building.footprint
        frame_min_x = min(part["min_x"] for part in active_parts)
        frame_max_x = max(part["max_x"] for part in active_parts)
        frame_min_y = min(part["min_y"] for part in active_parts)
        frame_max_y = max(part["max_y"] for part in active_parts)
        x_ratio = min(
            1.0,
            max(0.0, (building.entrance.x - bounds.min_x) / max(bounds.width, 1e-6)),
        )
        y_ratio = min(
            1.0,
            max(0.0, (building.entrance.y - bounds.min_y) / max(bounds.depth, 1e-6)),
        )
        target_x = frame_min_x + x_ratio * (frame_max_x - frame_min_x)
        target_y = frame_min_y + y_ratio * (frame_max_y - frame_min_y)
        zone_bay_factor = 1.24 if facade_zone == "podium" else 1.0
        if facade_zone == "crown":
            zone_bay_factor = 0.90

        exposed_candidates: list[tuple[float, int, int, dict[str, Any]]] = []
        fallback_candidates: list[tuple[float, int, int, dict[str, Any]]] = []
        for part_index, part in enumerate(active_parts):
            start, end, boundary, normal, swapped = self._facade_side_data(part, side)
            length = end - start
            if length <= 0.8:
                continue
            bay_count = max(
                1,
                min(14, round(length / (style.bay_width_m * zone_bay_factor))),
            )
            spacing = length / bay_count
            other_parts = [item for item in active_parts if item is not part]
            for bay_index in range(bay_count):
                tangent = bay_tangent(building, start, spacing, bay_index, bay_count)
                local_x, local_y = (
                    (boundary, tangent) if swapped else (tangent, boundary)
                )
                distance = (local_x - target_x) ** 2 + (local_y - target_y) ** 2
                world_x, world_y = self._facade_world_point(
                    building, frame, local_x, local_y
                )
                anchor = {
                    "id": f"{building.id}:entrance:ground",
                    "floor_id": floor.id,
                    "floor_level": floor.level,
                    "side": side,
                    "massing_part": part_index,
                    "bay_index": bay_index,
                    "bay_count": bay_count,
                    "bay_spacing_m": spacing,
                    "tangent_m": tangent,
                    "boundary_m": boundary,
                    "normal": [normal[0], normal[1]],
                    "axis_swapped": swapped,
                    "local_point": {"x": local_x, "y": local_y},
                    "world_point": {"x": world_x, "y": world_y},
                }
                candidate = (distance, part_index, bay_index, anchor)
                fallback_candidates.append(candidate)
                if self._facade_is_exposed(
                    part,
                    other_parts,
                    tangent,
                    boundary,
                    normal,
                    swapped,
                ):
                    exposed_candidates.append(candidate)
        candidates = exposed_candidates or fallback_candidates
        if not candidates:
            return None
        return min(candidates, key=lambda item: item[:3])[3]

    def _compile_facade_part(
        self,
        building: Building,
        floor: Floor,
        part: dict,
        active_parts: list[dict],
        part_index: int,
        frame: dict,
        style: FacadeStyle,
        profile: FacadeProfile,
        facade_zone: str,
        floor_ordinal: int,
        counters: dict,
        building_top: float,
        facade_asset_plan: FacadeBuildingAssetPlan,
        entrance_anchor: dict[str, Any] | None,
        scene: GeometryScene,
    ) -> None:
        layer = f"shell:{building.id}"
        facade_meta = {
            "facade_system": "grammar_v3",
            "facade_style": style.id,
            "facade_zone": facade_zone,
            "building_id": building.id,
            "floor_level": floor.level,
            "massing_part": part_index,
            "visual_proxy": True,
        }
        base_style = style
        for side in ("north", "south", "east", "west"):
            style = facade_style_for_face(building, base_style, side)
            facade_meta = {**facade_meta,
                           "design_language": building.metadata.get("appearance_plan", {}).get("language"),
                           "face_role": face_role(building, side)}
            start, end, boundary, normal, swapped = self._facade_side_data(part, side)
            length = end - start
            if length <= 0.8:
                continue
            zone_bay_factor = 1.24 if facade_zone == "podium" else 1.0
            if facade_zone == "crown":
                zone_bay_factor = 0.90
            bay_count = max(
                1,
                min(14, round(length / (style.bay_width_m * zone_bay_factor))),
            )
            spacing = length / bay_count
            window_ratio = style.window_ratio
            if facade_zone == "podium":
                window_ratio = min(0.88, window_ratio + 0.08)
            elif facade_zone == "crown":
                window_ratio *= 0.82
            window_width = min(spacing * window_ratio, spacing - 0.28)
            window_height = min(
                floor.height_m * style.window_height_ratio,
                floor.height_m - style.sill_height_m - 0.24,
            )
            if window_width <= 0.25 or window_height <= 0.25:
                continue
            for bay_index in range(bay_count):
                tangent = bay_tangent(building, start, spacing, bay_index, bay_count)
                if not self._facade_is_exposed(
                    part,
                    [item for item in active_parts if item is not part],
                    tangent,
                    boundary,
                    normal,
                    swapped,
                ):
                    continue
                is_entry_bay = (
                    entrance_anchor is not None
                    and floor.id == entrance_anchor["floor_id"]
                    and side == entrance_anchor["side"]
                    and part_index == entrance_anchor["massing_part"]
                    and bay_index == entrance_anchor["bay_index"]
                )
                storefront = floor.level == 0 and style.storefront
                window_h = (
                    min(2.55, floor.height_m - 0.34)
                    if storefront
                    else window_height
                )
                sill = 0.14 if storefront else style.sill_height_m
                if is_entry_bay:
                    entrance_meta = {
                        **facade_meta,
                        "entrance_anchor_id": entrance_anchor["id"],
                        "entrance_anchor_tangent_m": entrance_anchor["tangent_m"],
                        "entrance_anchor_bay_index": entrance_anchor["bay_index"],
                    }
                    entrance_asset = facade_asset_plan.get("entrance")
                    if entrance_asset is not None and self._add_facade_asset(
                        building,
                        floor,
                        side,
                        tangent,
                        boundary,
                        normal,
                        swapped,
                        frame,
                        window_width * 0.88,
                        min(floor.height_m - 0.18, max(2.2, window_h)),
                        floor.elevation_m + min(floor.height_m - 0.18, max(2.2, window_h)) / 2,
                        entrance_asset,
                        "entrance",
                        entrance_meta,
                        counters,
                        scene,
                    ):
                        # Most modular entrance assets are a textured wall bay
                        # with an opening rather than a complete opaque door.
                        # Keep a recessed deterministic door core behind it so
                        # the collision shell does not visually fill the hole.
                        self._add_facade_box(
                            building,
                            floor,
                            side,
                            tangent,
                            boundary,
                            normal,
                            swapped,
                            frame,
                            window_width * 0.62,
                            min(floor.height_m - 0.34, max(2.05, window_h * 0.88)),
                            floor.elevation_m + min(
                                floor.height_m - 0.34, max(2.05, window_h * 0.88)
                            ) / 2,
                            style.accent_material,
                            "entrance_door_core",
                            "entrance_asset_core",
                            entrance_meta,
                            scene,
                            outward_offset=0.018,
                            depth=0.025,
                        )
                        continue
                    self._add_facade_box(
                        building,
                        floor,
                        side,
                        tangent,
                        boundary,
                        normal,
                        swapped,
                        frame,
                        window_width * 0.82,
                        max(2.2, window_h),
                        floor.elevation_m + 1.05,
                        style.accent_material,
                        "entrance_portal",
                        "entrance",
                        entrance_meta,
                        scene,
                    )
                    continue
                if facade_zone == "mechanical":
                    louver_height = min(floor.height_m * 0.48, 1.65)
                    self._add_facade_box(
                        building,
                        floor,
                        side,
                        tangent,
                        boundary,
                        normal,
                        swapped,
                        frame,
                        spacing * 0.82,
                        louver_height,
                        floor.elevation_m + floor.height_m * 0.52,
                        "mechanical_louver",
                        "mechanical_louver",
                        f"bay_{bay_index:02d}_louver",
                        facade_meta,
                        scene,
                        outward_offset=0.06,
                        depth=0.10,
                    )
                    counters["mechanical_louver_count"] += 1
                    continue
                semantic = "storefront_window" if storefront else "facade_window"
                glass_material = style.glass_material
                if storefront:
                    glass_material = "storefront_glass"
                center_z = floor.elevation_m + sill + window_h / 2
                self._compile_appearance_bay(
                    building, floor, side, tangent, boundary, normal, swapped, frame,
                    spacing, window_width, window_h, center_z, style, bay_index,
                    facade_meta, scene)
                window_asset = facade_asset_plan.get(
                    "crown_window"
                    if facade_zone == "crown"
                    else "podium_window"
                    if facade_zone == "podium"
                    else "shaft_window"
                )
                if window_asset is not None and self._add_facade_asset(
                    building,
                    floor,
                    side,
                    tangent,
                    boundary,
                    normal,
                    swapped,
                    frame,
                    min(spacing * 0.94, window_width + style.frame_width_m * 2),
                    min(floor.height_m - 0.22, window_h + style.frame_width_m * 2),
                    center_z,
                    window_asset,
                    "window",
                    facade_meta,
                    counters,
                    scene,
                ):
                    counters["window_count"] += 1
                    # Asset-backed bays commonly provide masonry/frame geometry
                    # but intentionally leave their opening empty.  A thin
                    # glass layer and interior backing remain necessary behind
                    # the mesh, otherwise the opaque simulation shell fills the
                    # opening and the facade appears blank.
                    self._add_facade_box(
                        building,
                        floor,
                        side,
                        tangent,
                        boundary,
                        normal,
                        swapped,
                        frame,
                        window_width * 0.76,
                        window_h * 0.82,
                        center_z,
                        glass_material,
                        semantic,
                        f"bay_{bay_index:02d}_asset_glass",
                        facade_meta,
                        scene,
                        outward_offset=0.026,
                        depth=0.028,
                    )
                    backing_material = self._window_backing_material(
                        building,
                        floor,
                        side,
                        bay_index,
                        storefront=storefront,
                    )
                    self._add_facade_box(
                        building,
                        floor,
                        side,
                        tangent,
                        boundary,
                        normal,
                        swapped,
                        frame,
                        window_width * 0.71,
                        window_h * 0.77,
                        center_z,
                        backing_material,
                        "window_backing",
                        f"bay_{bay_index:02d}_asset_backing",
                        facade_meta,
                        scene,
                        outward_offset=0.009,
                        depth=0.012,
                    )
                    counters["window_backing_count"] += 1
                    continue
                self._add_facade_box(
                    building,
                    floor,
                    side,
                    tangent,
                    boundary,
                    normal,
                    swapped,
                    frame,
                    window_width + style.frame_width_m * 2,
                    window_h + style.frame_width_m * 2,
                    center_z,
                    style.frame_material,
                    "facade_frame",
                    f"bay_{bay_index:02d}_frame",
                    facade_meta,
                    scene,
                )
                self._add_facade_box(
                    building,
                    floor,
                    side,
                    tangent,
                    boundary,
                    normal,
                    swapped,
                    frame,
                    window_width,
                    window_h,
                    center_z,
                    glass_material,
                    semantic,
                    f"bay_{bay_index:02d}",
                    facade_meta,
                    scene,
                    outward_offset=0.018,
                    depth=0.035,
                )
                counters["window_count"] += 1
                backing_material = self._window_backing_material(
                    building,
                    floor,
                    side,
                    bay_index,
                    storefront=storefront,
                )
                self._add_facade_box(
                    building,
                    floor,
                    side,
                    tangent,
                    boundary,
                    normal,
                    swapped,
                    frame,
                    window_width * 0.94,
                    window_h * 0.94,
                    center_z,
                    backing_material,
                    "window_backing",
                    f"bay_{bay_index:02d}_backing",
                    facade_meta,
                    scene,
                    outward_offset=0.002,
                    depth=0.018,
                )
                counters["window_backing_count"] += 1

                if style.vertical_fins and bay_index % 2 == 0 and not storefront:
                    self._add_facade_box(
                        building,
                        floor,
                        side,
                        tangent - spacing * 0.5,
                        boundary,
                        normal,
                        swapped,
                        frame,
                        style.frame_width_m * 0.65,
                        window_h + 0.35,
                        center_z,
                        style.accent_material,
                        "facade_fin",
                        f"bay_{bay_index:02d}_fin",
                        facade_meta,
                        scene,
                        outward_offset=0.055,
                        depth=0.06,
                    )

            # Horizontal bands break the otherwise perfectly repeated stack and
            # make the ground floor and occasional transfer floors legible from
            # both aerial and street-level views.
            zone_boundary = (
                floor_ordinal == profile.podium_floors
                or floor_ordinal in profile.mechanical_levels
                or (
                    profile.crown_floors > 0
                    and floor_ordinal == profile.floor_count - profile.crown_floors
                )
            )
            if floor.level == 0 or zone_boundary:
                self._add_facade_box(
                    building, floor, side, (start + end) / 2, boundary, normal,
                    swapped, frame, length * 0.96,
                    0.24 if floor.level == 0 else 0.18,
                    floor.elevation_m + (0.26 if floor.level == 0 else 0.10),
                    style.accent_material,
                    "facade_ground_band" if floor.level == 0 else "facade_zone_band",
                    "ground_band" if floor.level == 0 else f"{facade_zone}_band",
                    facade_meta, scene, outward_offset=0.07, depth=0.11,
                )

            if (
                style.balcony_stride
                and facade_zone == "shaft"
                and floor.level > 0
                and floor.level % style.balcony_stride == 0
                and side == style.balcony_side
                and self._facade_is_exposed(
                    part,
                    [item for item in active_parts if item is not part],
                    (start + end) / 2,
                    boundary,
                    normal,
                    swapped,
                )
            ):
                self._add_balcony(
                    building,
                    floor,
                    side,
                    (start + end) / 2,
                    boundary,
                    normal,
                    swapped,
                    frame,
                    style,
                    facade_meta,
                    scene,
                )
                counters["balcony_count"] += 1
            if floor.level == 0 and style.storefront:
                counters["storefront_count"] += sum(
                    1
                    for primitive in scene.primitives[-bay_count * 3 :]
                    if primitive.semantic_class == "storefront_window"
                )

    def _add_facade_asset(
        self,
        building: Building,
        floor: Floor,
        side: str,
        tangent: float,
        boundary: float,
        normal: tuple[float, float],
        swapped: bool,
        frame: dict,
        width: float,
        height: float,
        center_z: float,
        selection: FacadeModuleSelection,
        role: str,
        metadata: dict,
        counters: dict,
        scene: GeometryScene,
    ) -> bool:
        """Place a canonical +X-forward facade GLB on one realized bay."""

        if width <= 0.2 or height <= 0.2:
            return False
        outward_offset = 0.075
        local_x, local_y = (
            (boundary + normal[0] * outward_offset, tangent)
            if swapped
            else (tangent, boundary + normal[1] * outward_offset)
        )
        world_x, world_y = self._facade_world_point(
            building, frame, local_x, local_y
        )
        world_normal_x = normal[0] * frame["cos"] - normal[1] * frame["sin"]
        world_normal_y = normal[0] * frame["sin"] + normal[1] * frame["cos"]
        rotation = math.degrees(math.atan2(world_normal_y, world_normal_x))
        record = self.asset_registry.get(selection.asset_id)
        if record is None or not record.geometry_path:
            return False
        scene.primitives.append(
            self._mesh(
                f"{floor.id}_facade_asset_p{metadata.get('massing_part', 0)}_{side}_{role}_{counters['resolved_asset_primitive_count']:04d}",
                floor.id,
                Vec3(world_x, world_y, center_z),
                Vec3(0.16, width, height),
                rotation,
                f"facade_asset_{role}",
                "facade_frame_light",
                f"shell:{building.id}",
                collision_enabled=False,
                instance_key=f"asset_{selection.asset_id}",
                metadata={
                    **metadata,
                    "facade_side": side,
                    "facade_asset_role": role,
                    "asset_id": selection.asset_id,
                    "asset_category": record.category,
                    "asset_source": record.source,
                    "asset_license": record.license_id,
                    "asset_geometry_path": str(
                        self.asset_registry.resolve_path(record.geometry_path)
                    ),
                    "asset_quality_score": record.quality_score,
                    "asset_selection_reason": selection.selection_reason,
                    "resolved_asset": True,
                    "canonical_forward_axis": "+X",
                    "canonical_up_axis": "+Z",
                },
            )
        )
        counters["resolved_asset_primitive_count"] += 1
        scene.metadata["resolved_asset_primitive_count"] = int(
            scene.metadata.get("resolved_asset_primitive_count", 0)
        ) + 1
        return True

    @staticmethod
    def _window_backing_material(
        building: Building,
        floor: Floor,
        side: str,
        bay_index: int,
        *,
        storefront: bool,
    ) -> str:
        """Choose restrained, deterministic interior variation behind glass."""
        key = f"{building.id}:{floor.id}:{side}:{bay_index}"
        value = int.from_bytes(hashlib.sha256(key.encode("utf-8")).digest()[:2], "big") % 100
        if storefront:
            return "window_interior_warm" if value < 32 else "window_interior_dark"
        warm_threshold = 18 if building.function in {"commercial", "mixed_use"} else 10
        if value < warm_threshold:
            return "window_interior_warm"
        if value < warm_threshold + 13:
            return "window_blind"
        return "window_interior_dark"

    def _compile_roof_edge_details(
        self,
        building: Building,
        frame: dict,
        style: FacadeStyle,
        building_top: float,
        scene: GeometryScene,
    ) -> None:
        """Add a parapet and small rooftop plant without touching collision."""

        top_floor = max(building.floors, key=lambda item: item.elevation_m)
        active_parts = [
            part for part in frame["parts"]
            if building_top * part["height_scale"] >= building_top - top_floor.height_m
        ]
        for part_index, part in enumerate(active_parts):
            metadata = {
                "facade_system": "grammar_v2",
                "facade_style": style.id,
                "building_id": building.id,
                "massing_part": part_index,
                "visual_proxy": True,
                "roof_detail": True,
            }
            part_top = building_top * part["height_scale"]
            for side in ("north", "south", "east", "west"):
                start, end, boundary, normal, swapped = self._facade_side_data(part, side)
                if not self._facade_is_exposed(
                    part, [item for item in active_parts if item is not part],
                    (start + end) / 2, boundary, normal, swapped,
                ):
                    continue
                self._add_facade_box(
                    building, top_floor, side, (start + end) / 2, boundary,
                    normal, swapped, frame, end - start, 0.52, part_top + 0.26,
                    style.frame_material, "roof_parapet", f"parapet_{part_index}",
                    metadata, scene, outward_offset=0.01, depth=0.14,
                )
        # Keep the decorative rooftop plant on the same highest part as the
        # parapet.  The first frame part can be a low podium in tower/podium
        # profiles and is not a valid support surface for a full-height roof
        # detail.
        roof_part = max(
            frame["parts"], key=lambda part: float(part.get("height_scale", 0.0))
        )
        local_x = (roof_part["min_x"] + roof_part["max_x"]) / 2
        local_y = (roof_part["min_y"] + roof_part["max_y"]) / 2
        world_x, world_y = self._facade_world_point(building, frame, local_x, local_y)
        width = min(5.0, (roof_part["max_x"] - roof_part["min_x"]) * 0.24)
        depth = min(4.0, (roof_part["max_y"] - roof_part["min_y"]) * 0.22)
        if width > 1.0 and depth > 1.0:
            scene.primitives.append(
                self._box(
                    f"{building.id}_facade_rooftop_plant", building.id,
                    Vec3(world_x, world_y, building_top + 0.55),
                    Vec3(width, depth, 0.62), frame["rotation"],
                    "roof_equipment", "industrial_metal", f"shell:{building.id}",
                    collision_enabled=False,
                    metadata={"facade_system": "grammar_v2", "building_id": building.id, "roof_detail": True, "roof_detail_kind": "screened_service_plant"},
                )
            )
            if building.metadata.get("height_contract", {}).get("landmark"):
                # A restrained crown/spire gives designated landmarks a
                # readable skyline role without turning every tower into a
                # billboard or introducing a new collision body.
                scene.primitives.append(
                    self._box(
                        f"{building.id}_landmark_crown", building.id,
                        Vec3(world_x, world_y, building_top + 0.48),
                        Vec3(max(1.2, width * 0.42), max(1.0, depth * 0.38), 0.46),
                        frame["rotation"], "landmark_crown", style.accent_material,
                        f"shell:{building.id}", collision_enabled=False,
                        metadata={"building_id": building.id, "roof_detail": True, "landmark_feature": "crown"},
                    )
                )
                scene.primitives.append(
                    self._box(
                        f"{building.id}_landmark_spire", building.id,
                        Vec3(world_x, world_y, building_top + 1.35),
                        Vec3(0.18, 0.18, 1.3), frame["rotation"],
                        "landmark_spire", style.accent_material,
                        f"shell:{building.id}", collision_enabled=False,
                        metadata={"building_id": building.id, "roof_detail": True, "landmark_feature": "spire"},
                    )
                )
            # A second, offset low-profile unit breaks the single-box roof
            # silhouette on large/high-rise masses without creating the
            # floating red blocks seen in earlier previews.
            if building.metadata.get("highrise", {}).get("enabled") or width > 3.0:
                local_offset = min(width * 0.34, 2.2)
                ox, oy = self._facade_world_point(
                    building, frame, local_x + local_offset, local_y - depth * 0.22
                )
                scene.primitives.append(
                    self._box(
                        f"{building.id}_facade_rooftop_plant_aux", building.id,
                        Vec3(ox, oy, building_top + 0.34),
                        Vec3(max(0.9, width * 0.34), max(0.8, depth * 0.30), 0.34),
                        frame["rotation"], "roof_auxiliary", "roof",
                        f"shell:{building.id}", collision_enabled=False,
                        metadata={"facade_system": "grammar_v2", "building_id": building.id, "roof_detail": True, "roof_detail_kind": "auxiliary_hvac"},
                    )
                )

    def _add_facade_box(
        self,
        building,
        floor,
        side,
        tangent,
        boundary,
        normal,
        swapped,
        frame,
        width,
        height,
        center_z,
        material,
        semantic,
        suffix,
        metadata,
        scene,
        *,
        outward_offset=0.055,
        depth=0.09,
    ):
        local_x, local_y = (
            (boundary + normal[0] * outward_offset, tangent)
            if swapped
            else (tangent, boundary + normal[1] * outward_offset)
        )
        world_x, world_y = self._facade_world_point(building, frame, local_x, local_y)
        size = Vec3(depth, width, height) if swapped else Vec3(width, depth, height)
        scene.primitives.append(
            self._box(
                f"{floor.id}_facade_p{metadata.get('massing_part', 0)}_{side}_{suffix}",
                floor.id,
                Vec3(world_x, world_y, center_z),
                size,
                frame["rotation"],
                semantic,
                material,
                f"shell:{building.id}",
                collision_enabled=False,
                metadata={**metadata, "facade_side": side},
            )
        )

    def _add_balcony(
        self,
        building,
        floor,
        side,
        tangent,
        boundary,
        normal,
        swapped,
        frame,
        style,
        metadata,
        scene,
    ):
        balcony_width = 2.6
        balcony_depth = 1.05
        local_x, local_y = (
            (boundary + normal[0] * balcony_depth / 2, tangent)
            if swapped
            else (tangent, boundary + normal[1] * balcony_depth / 2)
        )
        world_x, world_y = self._facade_world_point(building, frame, local_x, local_y)
        slab_size = (
            Vec3(balcony_depth, balcony_width, 0.16)
            if swapped
            else Vec3(balcony_width, balcony_depth, 0.16)
        )
        scene.primitives.append(
            self._box(
                f"{floor.id}_balcony_p{metadata.get('massing_part', 0)}_{side}_slab",
                floor.id,
                Vec3(world_x, world_y, floor.elevation_m + 0.22),
                slab_size,
                frame["rotation"],
                "balcony_slab",
                style.accent_material,
                f"shell:{building.id}",
                collision_enabled=False,
                metadata={**metadata, "facade_side": side},
            )
        )
        rail_local_x, rail_local_y = (
            (boundary + normal[0] * balcony_depth, tangent)
            if swapped
            else (tangent, boundary + normal[1] * balcony_depth)
        )
        rail_x, rail_y = self._facade_world_point(
            building, frame, rail_local_x, rail_local_y
        )
        rail_size = (
            Vec3(0.07, balcony_width, 0.92)
            if swapped
            else Vec3(balcony_width, 0.07, 0.92)
        )
        scene.primitives.append(
            self._box(
                f"{floor.id}_balcony_p{metadata.get('massing_part', 0)}_{side}_rail",
                floor.id,
                Vec3(rail_x, rail_y, floor.elevation_m + 0.70),
                rail_size,
                frame["rotation"],
                "balcony_rail",
                "balcony_rail",
                f"shell:{building.id}",
                collision_enabled=False,
                metadata={**metadata, "facade_side": side},
            )
        )

    def _add_visual_canopy(
        self,
        building: Building,
        prototype: BuildingPrototype,
        floor: Floor,
        frame: dict,
        entrance_anchor: dict[str, Any],
        scene: GeometryScene,
    ) -> None:
        """Add a canopy centered on the exact realized entrance bay."""

        side = str(entrance_anchor["side"])
        tangent = float(entrance_anchor["tangent_m"])
        boundary = float(entrance_anchor["boundary_m"])
        normal = tuple(float(value) for value in entrance_anchor["normal"])
        swapped = bool(entrance_anchor["axis_swapped"])
        canopy_depth = 1.6
        canopy_width = min(
            3.2,
            max(1.6, float(entrance_anchor["bay_spacing_m"]) * 0.92),
        )
        outward_offset = canopy_depth * 0.5 + 0.08
        local_x, local_y = (
            (boundary + normal[0] * outward_offset, tangent)
            if swapped
            else (tangent, boundary + normal[1] * outward_offset)
        )
        world_x, world_y = self._facade_world_point(
            building, frame, local_x, local_y
        )
        center_z = floor.elevation_m + min(2.65, floor.height_m - 0.18)
        center = Vec3(world_x, world_y, center_z)
        size = (
            Vec3(canopy_depth, canopy_width, 0.16)
            if swapped
            else Vec3(canopy_width, canopy_depth, 0.16)
        )
        scene.primitives.append(
            self._box(
                f"{building.id}_visual_entrance_canopy",
                building.id,
                center,
                size,
                frame["rotation"],
                "entrance_canopy",
                prototype.facade_material,
                f"shell:{building.id}",
                collision_enabled=False,
                metadata={
                    "visual_proxy": True,
                    "building_id": building.id,
                    "entrance_side": side,
                    "facade_side": side,
                    "entrance_anchor_id": entrance_anchor["id"],
                    "entrance_anchor_tangent_m": tangent,
                    "entrance_anchor_bay_index": entrance_anchor["bay_index"],
                    "massing_part": entrance_anchor["massing_part"],
                    "aligned_to_facade_entry": True,
                },
            )
        )

    def _add_exterior_walls(self, building, floor, prototype, scene) -> None:
        bounds = building.footprint
        thickness = prototype.wall_thickness_m
        openings = {"east": [], "west": [], "north": [], "south": []}
        for door in floor.doors if floor.level == 0 else ():
            if door.room_b_id is not None:
                continue
            point = self._door_geometry_position(floor, door)
            half = self._door_effective_width(floor, door) / 2
            if self._door_wall_axis(floor, door) == "horizontal":
                sides = {"south": abs(point.y - bounds.min_y), "north": abs(point.y - bounds.max_y)}
                tangent = point.x
            else:
                sides = {"west": abs(point.x - bounds.min_x), "east": abs(point.x - bounds.max_x)}
                tangent = point.y
            side = min(sides, key=sides.get)
            if sides[side] <= thickness:
                openings[side].append((tangent - half, tangent + half))

        for side, normal in (
            ("east", bounds.max_x - thickness / 2), ("south", bounds.min_y + thickness / 2),
            ("north", bounds.max_y - thickness / 2), ("west", bounds.min_x + thickness / 2),
        ):
            horizontal = side in {"north", "south"}
            lo, hi = (bounds.min_x, bounds.max_x) if horizontal else (bounds.min_y, bounds.max_y)
            spans = self._segments_excluding(lo, hi, openings[side])
            pieces = []
            for index, (start, end) in enumerate(spans):
                if not openings[side]:
                    suffix = ""
                elif start == lo:
                    suffix = "_west" if horizontal else "_south"
                elif end == hi:
                    suffix = "_east" if horizontal else "_north"
                else:
                    suffix = f"_pier_{index}"
                pieces.append((suffix, start, end, 0.0, floor.height_m))
            if floor.height_m > self.door_height_m:
                # The complement of the full-height spans merges overlapping apertures.
                for index, (start, end) in enumerate(self._segments_excluding(lo, hi, spans)):
                    suffix = "_header" if index == 0 else f"_header_{index}"
                    pieces.append((suffix, start, end, self.door_height_m, floor.height_m))
            for suffix, start, end, bottom, top in pieces:
                tangent = (start + end) / 2
                x, y = (tangent, normal) if horizontal else (normal, tangent)
                w, d = (end - start, thickness) if horizontal else (thickness, end - start)
                scene.primitives.append(self._box(
                    f"{floor.id}_wall_{side}{suffix}", floor.id,
                    Vec3(x, y, floor.elevation_m + (bottom + top) / 2), Vec3(w, d, top - bottom),
                    0.0, "exterior_wall", prototype.facade_material, f"shell:{building.id}",
                ))

    def _compile_floor(
        self, building: Building, floor: Floor, prototype: BuildingPrototype, scene: GeometryScene
    ) -> None:
        if floor.metadata.get("spatial_layout", {}).get("status") == "accepted":
            from cityg.geometry.spatial_floor import compile_spatial_floor
            compile_spatial_floor(self, building, floor, prototype, scene)
            return
        layer = f"floor:{floor.id}"
        corridors = [room for room in floor.rooms if room.function == "corridor"]
        corridor = next(
            (room for room in corridors if room.metadata.get("corridor_role") == "central"),
            corridors[0],
        )
        height = floor.height_m
        wall_t = max(0.12, prototype.wall_thickness_m * 0.75)
        center_z = floor.elevation_m + height / 2

        # Every corridor band owns two boundary walls.  The old compiler only
        # emitted walls for the central corridor, which made a deep-plate
        # multi-corridor floor visually open between room bands.  Split each
        # boundary at both door openings *and* adjacent-room limits.  A wall
        # primitive must never span several rooms and then claim all of them:
        # room-isolated rendering relies on this ownership being spatially
        # exact.
        for corridor_index, corridor_item in enumerate(corridors):
            for side, y in (
                ("south", corridor_item.bounds.min_y),
                ("north", corridor_item.bounds.max_y),
            ):
                openings = []
                for door in floor.doors:
                    if door.room_b_id is None:
                        continue
                    position = self._door_geometry_position(floor, door)
                    door_width = self._door_effective_width(floor, door)
                    if abs(position.y - y) <= 1e-5:
                        openings.append(
                            (
                                position.x - door_width / 2,
                                position.x + door_width / 2,
                            )
                        )
                adjacent_rooms = [
                    room
                    for room in floor.rooms
                    if room.function != "corridor"
                    and (
                        abs(room.bounds.min_y - y) <= 1e-5
                        or abs(room.bounds.max_y - y) <= 1e-5
                    )
                    and room.bounds.max_x > building.footprint.min_x + 1e-5
                    and room.bounds.min_x < building.footprint.max_x - 1e-5
                ]
                breakpoints = {
                    building.footprint.min_x,
                    building.footprint.max_x,
                }
                for room in adjacent_rooms:
                    breakpoints.add(
                        min(
                            building.footprint.max_x,
                            max(building.footprint.min_x, room.bounds.min_x),
                        )
                    )
                    breakpoints.add(
                        min(
                            building.footprint.max_x,
                            max(building.footprint.min_x, room.bounds.max_x),
                        )
                    )
                for opening_start, opening_end in openings:
                    breakpoints.add(
                        min(
                            building.footprint.max_x,
                            max(building.footprint.min_x, opening_start),
                        )
                    )
                    breakpoints.add(
                        min(
                            building.footprint.max_x,
                            max(building.footprint.min_x, opening_end),
                        )
                    )

                segment_index = 0
                ordered_breakpoints = sorted(breakpoints)
                for start, end in zip(ordered_breakpoints, ordered_breakpoints[1:]):
                    if end - start <= 1e-6:
                        continue
                    midpoint = (start + end) / 2
                    if any(left - 1e-6 <= midpoint <= right + 1e-6 for left, right in openings):
                        continue
                    touching_rooms = [
                        room
                        for room in adjacent_rooms
                        if room.bounds.min_x - 1e-5 <= midpoint <= room.bounds.max_x + 1e-5
                    ]
                    room_ids = [corridor_item.id, *(room.id for room in touching_rooms)]
                    scene.primitives.append(
                        self._box(
                            f"{floor.id}_corridor_{corridor_index:02d}_wall_{side}_{segment_index:02d}",
                            floor.id,
                            Vec3((start + end) / 2, y, center_z),
                            Vec3(end - start, wall_t, height),
                            0.0,
                            "interior_wall",
                            "interior_wall",
                            layer,
                            metadata={
                                "room_ids": room_ids,
                                "corridor_id": corridor_item.id,
                                "wall_role": "corridor_boundary",
                                "wall_side": side,
                                "canonical_span": [start, end],
                                "canonical_boundary": y,
                            },
                        )
                    )
                    segment_index += 1

        # Rooms are laid out in rectangular bands.  Grouping by exact y-span
        # emits the vertical partitions for every band without assuming that
        # all rooms lie immediately north/south of the central corridor.
        room_bands: dict[tuple[float, float], list[Any]] = {}
        for room in floor.rooms:
            if room.function == "corridor":
                continue
            key = (round(room.bounds.min_y, 6), round(room.bounds.max_y, 6))
            room_bands.setdefault(key, []).append(room)
        for band_index, (span, rooms) in enumerate(sorted(room_bands.items())):
            rooms = sorted(rooms, key=lambda room: room.bounds.min_x)
            for index, room in enumerate(rooms[:-1]):
                x = room.bounds.max_x
                scene.primitives.append(
                    self._box(
                        f"{floor.id}_partition_band_{band_index:02d}_{index:02d}",
                        floor.id,
                        Vec3(x, (span[0] + span[1]) / 2, center_z),
                        Vec3(wall_t, span[1] - span[0], height),
                        0.0,
                        "interior_wall",
                        "interior_wall",
                        layer,
                        metadata={
                            "room_ids": [room.id, rooms[index + 1].id],
                            "wall_role": "room_partition",
                            "canonical_span": [span[0], span[1]],
                            "canonical_boundary": x,
                        },
                    )
                )

        self._compile_room_exterior_boundaries(building, floor, wall_t, scene)
        self._compile_room_closure_boundaries(building, floor, wall_t, scene)
        for door in floor.doors:
            self._compile_door(floor, door, scene)
        self._compile_furniture(floor, scene)

    def _compile_room_exterior_boundaries(
        self,
        building: Building,
        floor: Floor,
        wall_t: float,
        scene: GeometryScene,
    ) -> None:
        """Emit room-addressable exterior walls for isolated room inspection.

        The architectural shell is building/floor owned and, for non-rectangular
        massing, is visually separate from the canonical collision envelope.
        These non-colliding fragments follow the same massing-conformance pass
        as interior walls and are hidden by the Viewer outside Room mode.
        """

        bounds = building.footprint
        layer = f"floor:{floor.id}"
        height = floor.height_m
        center_z = floor.elevation_m + height / 2
        tolerance = 1e-5
        exterior_doors = [door for door in floor.doors if door.room_b_id is None]
        sides = (
            ("south", "x", bounds.min_y),
            ("north", "x", bounds.max_y),
            ("west", "y", bounds.min_x),
            ("east", "y", bounds.max_x),
        )
        for side, axis, boundary in sides:
            for room in floor.rooms:
                touches_boundary = (
                    abs(room.bounds.min_y - boundary) <= tolerance
                    if side == "south"
                    else abs(room.bounds.max_y - boundary) <= tolerance
                    if side == "north"
                    else abs(room.bounds.min_x - boundary) <= tolerance
                    if side == "west"
                    else abs(room.bounds.max_x - boundary) <= tolerance
                )
                if not touches_boundary:
                    continue
                start = room.bounds.min_x if axis == "x" else room.bounds.min_y
                end = room.bounds.max_x if axis == "x" else room.bounds.max_y
                openings = []
                for door in exterior_doors:
                    position = self._door_geometry_position(floor, door)
                    door_width = self._door_effective_width(floor, door)
                    on_boundary = (
                        abs(position.y - boundary) <= tolerance
                        if axis == "x"
                        else abs(position.x - boundary) <= tolerance
                    )
                    tangent = position.x if axis == "x" else position.y
                    if on_boundary and start - tolerance <= tangent <= end + tolerance:
                        openings.append(
                            (tangent - door_width / 2, tangent + door_width / 2)
                        )
                metadata = {
                    "room_ids": [room.id],
                    "wall_role": "room_exterior_boundary",
                    "wall_side": side,
                    "viewer_room_only": True,
                    "canonical_boundary": boundary,
                }
                for segment_index, (segment_start, segment_end) in enumerate(
                    self._segments_excluding(start, end, openings)
                ):
                    if axis == "x":
                        center = Vec3((segment_start + segment_end) / 2, boundary, center_z)
                        size = Vec3(segment_end - segment_start, wall_t, height)
                    else:
                        center = Vec3(boundary, (segment_start + segment_end) / 2, center_z)
                        size = Vec3(wall_t, segment_end - segment_start, height)
                    scene.primitives.append(
                        self._box(
                            f"{floor.id}_{room.id}_exterior_{side}_{segment_index:02d}",
                            floor.id,
                            center,
                            size,
                            0.0,
                            "interior_wall",
                            "interior_wall",
                            layer,
                            collision_enabled=False,
                            metadata={
                                **metadata,
                                "canonical_span": [segment_start, segment_end],
                            },
                        )
                    )

                header_height = max(0.0, height - self.door_height_m)
                for opening_index, (opening_start, opening_end) in enumerate(openings):
                    clipped_start = max(start, opening_start)
                    clipped_end = min(end, opening_end)
                    if clipped_end - clipped_start <= tolerance or header_height <= tolerance:
                        continue
                    header_z = floor.elevation_m + self.door_height_m + header_height / 2
                    if axis == "x":
                        center = Vec3((clipped_start + clipped_end) / 2, boundary, header_z)
                        size = Vec3(clipped_end - clipped_start, wall_t, header_height)
                    else:
                        center = Vec3(boundary, (clipped_start + clipped_end) / 2, header_z)
                        size = Vec3(wall_t, clipped_end - clipped_start, header_height)
                    scene.primitives.append(
                        self._box(
                            f"{floor.id}_{room.id}_exterior_{side}_header_{opening_index:02d}",
                            floor.id,
                            center,
                            size,
                            0.0,
                            "interior_wall",
                            "interior_wall",
                            layer,
                            collision_enabled=False,
                            metadata={
                                **metadata,
                                "wall_role": "room_exterior_header",
                                "canonical_span": [clipped_start, clipped_end],
                            },
                        )
                    )

    def _compile_room_closure_boundaries(
        self,
        building: Building,
        floor: Floor,
        wall_t: float,
        scene: GeometryScene,
    ) -> None:
        """Close unshared edges of enclosed rooms.

        Corridor boundaries and room partitions are emitted by the main floor
        compiler.  A room can nevertheless end beside an unused plate strip
        (especially on a setback tower), where neither of those passes owns the
        edge.  Emit a room-owned wall for such edges so an ``enclosed_room`` is
        never rendered as an open shell.  Shared edges are intentionally left
        to the corridor/partition owner to avoid duplicate coplanar walls.
        """

        rooms = [room for room in floor.rooms if room.function != "corridor"]
        corridors = [room for room in floor.rooms if room.function == "corridor"]
        tolerance = 1e-5

        def overlap(start_a, end_a, start_b, end_b):
            return min(end_a, end_b) - max(start_a, start_b) > tolerance

        def has_adjacent(room, side):
            if side == "south":
                boundary = room.bounds.min_y
                return any(
                    abs(other.bounds.max_y - boundary) <= tolerance
                    and overlap(room.bounds.min_x, room.bounds.max_x, other.bounds.min_x, other.bounds.max_x)
                    for other in (*rooms, *corridors)
                    if other.id != room.id
                )
            if side == "north":
                boundary = room.bounds.max_y
                return any(
                    abs(other.bounds.min_y - boundary) <= tolerance
                    and overlap(room.bounds.min_x, room.bounds.max_x, other.bounds.min_x, other.bounds.max_x)
                    for other in (*rooms, *corridors)
                    if other.id != room.id
                )
            if side == "west":
                boundary = room.bounds.min_x
                return any(
                    abs(other.bounds.max_x - boundary) <= tolerance
                    and overlap(room.bounds.min_y, room.bounds.max_y, other.bounds.min_y, other.bounds.max_y)
                    for other in (*rooms, *corridors)
                    if other.id != room.id
                )
            boundary = room.bounds.max_x
            return any(
                abs(other.bounds.min_x - boundary) <= tolerance
                and overlap(room.bounds.min_y, room.bounds.max_y, other.bounds.min_y, other.bounds.max_y)
                for other in (*rooms, *corridors)
                if other.id != room.id
            )

        existing = [
            primitive
            for primitive in scene.primitives
            if primitive.semantic_class == "interior_wall"
        ]

        for room in rooms:
            # Open-plan spaces are intentionally not forced into four enclosed
            # sides. All other semantic rooms receive closure geometry.
            if room.metadata.get("open_plan") is True or room.metadata.get("space_kind") == "open_plan":
                continue
            sides = (
                ("south", "x", room.bounds.min_y, room.bounds.min_x, room.bounds.max_x),
                ("north", "x", room.bounds.max_y, room.bounds.min_x, room.bounds.max_x),
                ("west", "y", room.bounds.min_x, room.bounds.min_y, room.bounds.max_y),
                ("east", "y", room.bounds.max_x, room.bounds.min_y, room.bounds.max_y),
            )
            for side, axis, boundary, start, end in sides:
                if has_adjacent(room, side):
                    continue
                if any(
                    room.id in primitive.metadata.get("room_ids", [])
                    and primitive.metadata.get("wall_role") in {
                        "room_exterior_boundary",
                        "room_closure",
                    }
                    and abs(primitive.metadata.get("canonical_boundary", 1e9) - boundary) <= tolerance
                    for primitive in existing
                ):
                    continue

                openings = []
                for door in floor.doors:
                    if room.id not in {door.room_a_id, door.room_b_id}:
                        continue
                    position = self._door_geometry_position(floor, door)
                    door_width = self._door_effective_width(floor, door)
                    tangent = position.x if axis == "x" else position.y
                    on_boundary = (
                        abs(position.y - boundary) <= tolerance
                        if axis == "x"
                        else abs(position.x - boundary) <= tolerance
                    )
                    if on_boundary and start - tolerance <= tangent <= end + tolerance:
                        openings.append((tangent - door_width / 2, tangent + door_width / 2))

                for segment_index, (segment_start, segment_end) in enumerate(
                    self._segments_excluding(start, end, openings)
                ):
                    if axis == "x":
                        center = Vec3((segment_start + segment_end) / 2, boundary, floor.elevation_m + floor.height_m / 2)
                        size = Vec3(segment_end - segment_start, wall_t, floor.height_m)
                    else:
                        center = Vec3(boundary, (segment_start + segment_end) / 2, floor.elevation_m + floor.height_m / 2)
                        size = Vec3(wall_t, segment_end - segment_start, floor.height_m)
                    scene.primitives.append(
                        self._box(
                            f"{floor.id}_{room.id}_closure_{side}_{segment_index:02d}",
                            floor.id,
                            center,
                            size,
                            0.0,
                            "interior_wall",
                            "interior_wall",
                            f"floor:{floor.id}",
                            metadata={
                                "room_ids": [room.id],
                                "wall_role": "room_closure",
                                "wall_side": side,
                                "viewer_room_only": True,
                                "canonical_span": [segment_start, segment_end],
                                "canonical_boundary": boundary,
                            },
                        )
                    )

    def _compile_furniture(self, floor: Floor, scene: GeometryScene) -> None:
        """Compile indoor objects, using a normalized local Mesh when available."""

        from cityg.planning.room_envelope import room_geometry_binding
        room_bindings={room.id:room_geometry_binding(floor,room) for room in floor.rooms}
        for obj in floor.objects:
            metric = obj.metadata.get("metric_room_placement")
            if metric:
                if (metric.get('source_room_geometry') is not None and
                        metric['source_room_geometry']!=room_bindings.get(obj.room_id)):
                    raise ValueError('Metric furniture room/door geometry changed; replan affected room')
                if (metric.get('source_floor_vertical_extent') is not None and
                        metric['source_floor_vertical_extent']!=[floor.elevation_m,floor.height_m]):
                    raise ValueError('Metric furniture floor changed; replan affected room')
                if metric.get("canonical_binding") != [obj.position.x,obj.position.y,obj.width_m,
                                                       obj.depth_m,obj.height_m,obj.rotation_deg,obj.asset_id]:
                    raise ValueError("Metric furniture pose changed; replan affected room")
                from cityg.schemas import Point2D
                obj = replace(obj, position=Point2D(*metric["center"]),
                              width_m=metric["dimensions_m"][0], depth_m=metric["dimensions_m"][1],
                              height_m=metric["dimensions_m"][2])
            spec = asset_spec(obj.category)
            record = self.asset_registry.get(obj.asset_id)
            if record is not None and record.geometry_path:
                material = record.material_id or spec.material_id
                if material not in {item.id for item in scene.materials}:
                    material = spec.material_id
                scene.primitives.append(
                    self._mesh(
                        f"geom_{obj.id}_mesh",
                        obj.id,
                        Vec3(
                            obj.position.x,
                            obj.position.y,
                            floor.elevation_m + obj.height_m / 2,
                        ),
                        Vec3(obj.width_m, obj.depth_m, obj.height_m),
                        obj.rotation_deg,
                        spec.semantic_class,
                        material,
                        f"floor:{floor.id}",
                        instance_key=f"asset_{record.asset_id}",
                        metadata={
                            "asset_id": record.asset_id,
                            "asset_category": record.category,
                            "asset_source": record.source,
                            "asset_license": record.license_id,
                            "asset_geometry_path": (
                                str(self.asset_registry.resolve_path(record.geometry_path))
                                if record.geometry_path
                                else None
                            ),
                            "asset_collision_path": (
                                str(self.asset_registry.resolve_path(record.collision_path))
                                if record.collision_path
                                else None
                            ),
                            "asset_preview_path": (
                                str(self.asset_registry.resolve_path(record.preview_path))
                                if record.preview_path
                                else None
                            ),
                            "asset_quality_score": record.quality_score,
                            "asset_metadata": record.metadata,
                            "metric_room_placement": metric,
                            "object_width_m": obj.width_m,
                            "object_depth_m": obj.depth_m,
                            "object_height_m": obj.height_m,
                            "object_rotation_deg": obj.rotation_deg,
                            "object_front_axis": obj.metadata.get("front_axis", "+Y"),
                            "orientation_confidence": obj.metadata.get(
                                "orientation_confidence", "default"
                            ),
                            # Keep the planner-space anchor available to the
                            # massing conformance pass.  Resolved GLB assets
                            # follow the same fit path as procedural furniture;
                            # without this anchor a mesh is projected to the
                            # nearest massing boundary by center only and its
                            # visible footprint can cross the wall.
                            "canonical_object_center": {
                                "x": obj.position.x,
                                "y": obj.position.y,
                            },
                            "canonical_component_offset": {"x": 0.0, "y": 0.0},
                            "massing_fitted": True,
                            "resolved_asset": True,
                        },
                    )
                )
                continue
            angle = math.radians(obj.rotation_deg)
            cos_angle = math.cos(angle)
            sin_angle = math.sin(angle)
            components = self._furniture_components(
                spec.proxy_style, obj.width_m, obj.depth_m, obj.height_m
            )
            for index, (name, dx, dy, z, width, depth, height, material) in enumerate(
                components
            ):
                offset_x = dx * cos_angle - dy * sin_angle
                offset_y = dx * sin_angle + dy * cos_angle
                scene.primitives.append(
                    self._box(
                        f"geom_{obj.id}_{index:02d}_{name}",
                        obj.id,
                        Vec3(
                            obj.position.x + offset_x,
                            obj.position.y + offset_y,
                            floor.elevation_m + z,
                        ),
                        Vec3(width, depth, height),
                        obj.rotation_deg,
                        spec.semantic_class,
                        material or spec.material_id,
                        f"floor:{floor.id}",
                        instance_key=f"procedural_{spec.proxy_style}",
                        metadata={
                            "asset_id": obj.asset_id,
                            "asset_category": obj.category,
                            "metric_room_placement": metric,
                            "proxy_style": spec.proxy_style,
                            "component": name,
                            "canonical_object_center": {
                                "x": obj.position.x,
                                "y": obj.position.y,
                            },
                            "canonical_component_offset": {
                                "x": offset_x,
                                "y": offset_y,
                            },
                            "object_width_m": obj.width_m,
                            "object_depth_m": obj.depth_m,
                            "object_rotation_deg": obj.rotation_deg,
                            "object_front_axis": obj.metadata.get("front_axis", "+Y"),
                            "orientation_confidence": obj.metadata.get(
                                "orientation_confidence", "default"
                            ),
                        },
                    )
                )

    @staticmethod
    def _furniture_components(style, width, depth, height):
        """Return local component boxes as name, xyz center, xyz size, material."""

        if style == "table":
            top = min(0.12, height * 0.18)
            leg = min(0.09, min(width, depth) * 0.13)
            result = [("top", 0.0, 0.0, height - top / 2, width, depth, top, None)]
            for sx in (-1, 1):
                for sy in (-1, 1):
                    result.append(
                        (
                            f"leg_{sx}_{sy}",
                            sx * (width / 2 - leg),
                            sy * (depth / 2 - leg),
                            (height - top) / 2,
                            leg,
                            leg,
                            height - top,
                            "furniture_metal",
                        )
                    )
            return result
        if style == "chair":
            seat_z = height * 0.47
            return [
                ("seat", 0.0, 0.0, seat_z, width, depth * 0.88, height * 0.12, None),
                ("back", 0.0, depth * 0.40, height * 0.73, width, depth * 0.12, height * 0.48, None),
                ("base", 0.0, 0.0, seat_z * 0.48, width * 0.14, depth * 0.14, seat_z * 0.90, "furniture_metal"),
                ("foot", 0.0, 0.0, 0.06, width * 0.72, depth * 0.72, 0.12, "furniture_metal"),
            ]
        if style == "sofa":
            return [
                ("seat", 0.0, -depth * 0.06, height * 0.34, width * 0.82, depth * 0.72, height * 0.30, None),
                ("back", 0.0, depth * 0.40, height * 0.60, width, depth * 0.20, height * 0.76, None),
                ("arm_left", -width * 0.45, 0.0, height * 0.43, width * 0.10, depth * 0.82, height * 0.54, None),
                ("arm_right", width * 0.45, 0.0, height * 0.43, width * 0.10, depth * 0.82, height * 0.54, None),
            ]
        if style == "bed":
            return [
                ("frame", 0.0, 0.0, height * 0.16, width, depth, height * 0.26, "furniture_wood_dark"),
                ("mattress", 0.0, -depth * 0.03, height * 0.37, width * 0.94, depth * 0.88, height * 0.28, None),
                ("headboard", 0.0, depth * 0.46, height * 0.52, width, depth * 0.08, height * 0.72, "furniture_wood_dark"),
                ("pillow_left", -width * 0.24, depth * 0.28, height * 0.57, width * 0.34, depth * 0.22, height * 0.13, "ceramic"),
                ("pillow_right", width * 0.24, depth * 0.28, height * 0.57, width * 0.34, depth * 0.22, height * 0.13, "ceramic"),
            ]
        if style in {"cabinet", "counter"}:
            body_height = height * (0.88 if style == "counter" else 0.96)
            return [
                ("body", 0.0, 0.0, body_height / 2, width, depth, body_height, None),
                ("top", 0.0, 0.0, height - (height - body_height) / 2, width * 1.04, depth * 1.05, height - body_height, "ceramic" if style == "counter" else None),
            ]
        if style == "rack":
            shelf = min(0.07, height * 0.05)
            post = min(0.07, min(width, depth) * 0.14)
            result = []
            for level in (0.05, 0.36, 0.68, 0.97):
                result.append((f"shelf_{level}", 0.0, 0.0, max(shelf / 2, height * level), width, depth, shelf, None))
            for sx in (-1, 1):
                for sy in (-1, 1):
                    result.append((f"post_{sx}_{sy}", sx * (width / 2 - post / 2), sy * (depth / 2 - post / 2), height / 2, post, post, height, "furniture_metal"))
            return result
        if style == "toilet":
            return [
                ("base", 0.0, -depth * 0.12, height * 0.28, width * 0.72, depth * 0.62, height * 0.56, None),
                ("seat", 0.0, -depth * 0.12, height * 0.57, width, depth * 0.64, height * 0.10, None),
                ("tank", 0.0, depth * 0.36, height * 0.58, width * 0.90, depth * 0.28, height * 0.62, None),
            ]
        if style == "sink":
            return [
                ("pedestal", 0.0, 0.0, height * 0.42, width * 0.32, depth * 0.34, height * 0.78, None),
                ("basin", 0.0, 0.0, height * 0.86, width, depth, height * 0.20, None),
            ]
        if style in {"machine", "console"}:
            return [
                ("base", 0.0, 0.0, height * 0.36, width, depth, height * 0.72, None),
                ("upper", 0.0, depth * 0.12, height * 0.78, width * 0.82, depth * 0.66, height * 0.44, None),
                ("panel", 0.0, -depth * 0.34, height * 0.76, width * 0.62, depth * 0.06, height * 0.20, "commercial_glass"),
            ]
        return [("body", 0.0, 0.0, height / 2, width, depth, height, None)]

    @staticmethod
    def _door_geometry_position(floor: Floor, door: Door) -> Point2D:
        """Return a wall-safe door center for rendering and wall openings.

        Oversized rooms can be split after their original corridor door was
        planned.  An original center that lies exactly on the new split line
        then becomes a corner door and cuts a half-width opening from the
        neighbouring room.  Infer the shared wall from the two connected
        rooms and keep the opening inside that wall with a short corner pier.
        The canonical planner now applies the same rule; this compatibility
        path also repairs already-generated city manifests on recompilation.
        """

        rooms = {room.id: room for room in floor.rooms}
        room_a = rooms.get(door.room_a_id)
        room_b = rooms.get(door.room_b_id) if door.room_b_id else None
        if room_a is None:
            return door.position

        tolerance = 1e-5
        corner_pier = 0.18
        door_width = GeometryCompiler._door_effective_width(floor, door)

        def clamp_tangent(value: float, start: float, end: float) -> float:
            inset = door_width / 2 + corner_pier
            if end - start <= 2 * inset:
                return (start + end) / 2
            return min(max(value, start + inset), end - inset)

        if room_b is not None:
            overlap_x = (
                max(room_a.bounds.min_x, room_b.bounds.min_x),
                min(room_a.bounds.max_x, room_b.bounds.max_x),
            )
            overlap_y = (
                max(room_a.bounds.min_y, room_b.bounds.min_y),
                min(room_a.bounds.max_y, room_b.bounds.max_y),
            )
            shared_horizontal = (
                abs(room_a.bounds.min_y - room_b.bounds.max_y) <= tolerance
                or abs(room_a.bounds.max_y - room_b.bounds.min_y) <= tolerance
            ) and overlap_x[1] - overlap_x[0] > tolerance
            shared_vertical = (
                abs(room_a.bounds.min_x - room_b.bounds.max_x) <= tolerance
                or abs(room_a.bounds.max_x - room_b.bounds.min_x) <= tolerance
            ) and overlap_y[1] - overlap_y[0] > tolerance
            if shared_horizontal:
                return Point2D(
                    clamp_tangent(door.position.x, *overlap_x), door.position.y
                )
            if shared_vertical:
                return Point2D(
                    door.position.x,
                    clamp_tangent(door.position.y, *overlap_y),
                )

        # Exterior doors have no second room.  Only adjust the tangent when
        # the door unambiguously lies on one side of its owning room.
        distances = {
            "south": abs(door.position.y - room_a.bounds.min_y),
            "north": abs(door.position.y - room_a.bounds.max_y),
            "west": abs(door.position.x - room_a.bounds.min_x),
            "east": abs(door.position.x - room_a.bounds.max_x),
        }
        side, distance = min(distances.items(), key=lambda item: item[1])
        if distance > tolerance:
            return door.position
        if side in {"south", "north"}:
            return Point2D(
                clamp_tangent(
                    door.position.x, room_a.bounds.min_x, room_a.bounds.max_x
                ),
                door.position.y,
            )
        return Point2D(
            door.position.x,
            clamp_tangent(
                door.position.y, room_a.bounds.min_y, room_a.bounds.max_y
            ),
        )

    @staticmethod
    def _door_effective_width(floor: Floor, door: Door) -> float:
        """Return a door width that fits the actual shared wall span.

        Room splitting can leave a door at (or very close to) a corner.  The
        planner's nominal width is still useful as an upper bound, but the
        rendered opening must leave a small corner pier on both sides.
        """

        rooms = {room.id: room for room in floor.rooms}
        room_a = rooms.get(door.room_a_id)
        room_b = rooms.get(door.room_b_id) if door.room_b_id else None
        if room_a is None:
            return float(door.width_m)
        corner_pier = 0.18
        spans: list[float] = []
        if room_b is not None:
            overlap_x = min(room_a.bounds.max_x, room_b.bounds.max_x) - max(
                room_a.bounds.min_x, room_b.bounds.min_x
            )
            overlap_y = min(room_a.bounds.max_y, room_b.bounds.max_y) - max(
                room_a.bounds.min_y, room_b.bounds.min_y
            )
            if overlap_x > 1e-5 and (
                abs(room_a.bounds.min_y - room_b.bounds.max_y) <= 1e-5
                or abs(room_a.bounds.max_y - room_b.bounds.min_y) <= 1e-5
            ):
                spans.append(overlap_x)
            if overlap_y > 1e-5 and (
                abs(room_a.bounds.min_x - room_b.bounds.max_x) <= 1e-5
                or abs(room_a.bounds.max_x - room_b.bounds.min_x) <= 1e-5
            ):
                spans.append(overlap_y)
        else:
            distances = {
                abs(door.position.y - room_a.bounds.min_y): room_a.bounds.width,
                abs(door.position.y - room_a.bounds.max_y): room_a.bounds.width,
                abs(door.position.x - room_a.bounds.min_x): room_a.bounds.depth,
                abs(door.position.x - room_a.bounds.max_x): room_a.bounds.depth,
            }
            spans.append(min(distances.values()))
        if not spans:
            return float(door.width_m)
        usable = max(0.45, max(spans) - 2 * corner_pier)
        return min(float(door.width_m), usable)

    @staticmethod
    def _door_wall_axis(floor: Floor, door: Door) -> str:
        """Return ``horizontal`` or ``vertical`` for the wall containing door."""

        rooms = {room.id: room for room in floor.rooms}
        room_a = rooms.get(door.room_a_id)
        room_b = rooms.get(door.room_b_id) if door.room_b_id else None
        if room_a is not None and room_b is not None:
            if (
                abs(room_a.bounds.min_y - room_b.bounds.max_y) <= 1e-5
                or abs(room_a.bounds.max_y - room_b.bounds.min_y) <= 1e-5
            ):
                return "horizontal"
            if (
                abs(room_a.bounds.min_x - room_b.bounds.max_x) <= 1e-5
                or abs(room_a.bounds.max_x - room_b.bounds.min_x) <= 1e-5
            ):
                return "vertical"
        if room_a is None:
            return "horizontal"
        distances = {
            "horizontal": min(
                abs(door.position.y - room_a.bounds.min_y),
                abs(door.position.y - room_a.bounds.max_y),
            ),
            "vertical": min(
                abs(door.position.x - room_a.bounds.min_x),
                abs(door.position.x - room_a.bounds.max_x),
            ),
        }
        return min(distances, key=distances.get)

    def _compile_door(self, floor: Floor, door: Door, scene: GeometryScene) -> None:
        exterior = door.room_b_id is None
        position = self._door_geometry_position(floor, door)
        door_width = self._door_effective_width(floor, door)
        horizontal = self._door_wall_axis(floor, door) == "horizontal"
        size = (
            Vec3(door_width, self.door_thickness_m, self.door_height_m)
            if horizontal
            else Vec3(self.door_thickness_m, door_width, self.door_height_m)
        )
        state_machine_id = f"state_machine__{door.id}" if door.interactive else None
        scene.primitives.append(
            self._box(
                f"geom_{door.id}",
                door.id,
                Vec3(
                    position.x,
                    position.y,
                    floor.elevation_m + self.door_height_m / 2,
                ),
                size,
                0.0,
                "door",
                "door",
                f"floor:{floor.id}",
                body_type="articulated" if door.interactive else "static",
                instance_key="door_panel",
                metadata={
                    "door_type": door.door_type,
                    "hinge_axis": "Z",
                    "lower_limit_deg": 0.0,
                    "upper_limit_deg": 90.0,
                    "mass_kg": 25.0,
                    "state_machine_id": state_machine_id,
                    "canonical_position": {
                        "x": door.position.x,
                        "y": door.position.y,
                    },
                    "wall_safe_position": {
                        "x": position.x,
                        "y": position.y,
                    },
                    "effective_width_m": door_width,
                    "wall_axis": "horizontal" if horizontal else "vertical",
                    "room_ids": [
                        room_id
                        for room_id in (door.room_a_id, door.room_b_id)
                        if room_id
                    ],
                },
            )
        )
        if door.interactive:
            scene.state_machines.append(
                InteractionStateMachine(
                    id=state_machine_id,
                    owner_id=door.id,
                    state_type="revolute_door",
                    initial_state="closed",
                    states={
                        "closed": {"joint_angle_deg": 0.0, "nav_passable": False},
                        "open": {"joint_angle_deg": 90.0, "nav_passable": True},
                    },
                    transitions=[
                        StateTransition("open", "closed", "open", 0.8),
                        StateTransition("close", "open", "closed", 0.8),
                    ],
                )
            )
        # Exterior openings already receive a wall-owned header in
        # ``_compile_room_exterior_boundaries``; only interior door openings
        # need the explicit header primitive here.
        if exterior:
            return
        header_height = max(0.0, floor.height_m - self.door_height_m)
        if header_height <= 1e-6:
            return
        room_ids = [item for item in (door.room_a_id, door.room_b_id) if item]
        header_size = (
            Vec3(door_width, self.door_thickness_m, header_height)
            if horizontal
            else Vec3(self.door_thickness_m, door_width, header_height)
        )
        scene.primitives.append(
            self._box(
                f"geom_{door.id}_header",
                floor.id,
                Vec3(
                    position.x,
                    position.y,
                    floor.elevation_m + self.door_height_m + header_height / 2,
                ),
                header_size,
                0.0,
                "interior_wall",
                "interior_wall",
                f"floor:{floor.id}",
                collision_enabled=False,
                metadata={
                    "room_ids": room_ids,
                    "wall_role": "door_header",
                    "door_id": door.id,
                    "viewer_room_only": False,
                    "effective_width_m": door_width,
                },
            )
        )

    def _compile_vertical_connectors(
        self, building: Building, scene: GeometryScene
    ) -> None:
        floors = {floor.level: floor for floor in building.floors}
        for connector in building.vertical_connectors:
            if connector.connector_type == "elevator":
                self._compile_elevator(building, connector, floors, scene)
                continue
            for level in range(connector.from_level, connector.to_level):
                # A selective interior scope can contain non-adjacent floors.
                # Do not invent a flight through an uncompiled landing.
                if level not in floors or level + 1 not in floors:
                    continue
                floor = floors[level]
                run_x=connector.metadata.get('stair_run_axis')=='x'
                step_depth = (connector.bounds.width if run_x else connector.bounds.depth) / self.stair_steps_per_floor
                rise = floor.height_m / self.stair_steps_per_floor
                for step in range(self.stair_steps_per_floor):
                    height = rise * (step + 1)
                    run = (connector.bounds.min_x if run_x else connector.bounds.min_y) + step_depth * (step + 0.5)
                    scene.primitives.append(
                        self._box(
                            f"{connector.id}_level_{level:02d}_step_{step:02d}",
                            connector.id,
                            Vec3(
                                run if run_x else connector.bounds.center.x,
                                connector.bounds.center.y if run_x else run,
                                floor.elevation_m + height / 2,
                            ),
                            Vec3(step_depth, connector.bounds.depth, height) if run_x else Vec3(connector.bounds.width, step_depth, height),
                            0.0,
                            "stair_tread",
                            "stairs",
                            f"floor:{floor.id}",
                            instance_key="stair_step",
                            metadata={"from_level": level, "to_level": level + 1},
                        )
                    )

    def _compile_elevator(self, building, connector, floors, scene) -> None:
        """Compile a CPU-neutral shaft and discrete-floor cabin controller."""

        if connector.metadata.get('transport_elevator_version') == 1:
            from cityg.geometry.transport_elevator import compile_transport_elevator
            compile_transport_elevator(self, connector, floors, scene)
            return

        machine_id = f"state_machine__{connector.id}"
        wall_t = min(0.14, connector.bounds.width * 0.09)
        served = [
            floors[level]
            for level in range(connector.from_level, connector.to_level + 1)
            if level in floors
        ]
        for floor in served:
            layer = f"floor:{floor.id}"
            center_z = floor.elevation_m + floor.height_m / 2
            shaft_height = max(0.2, floor.height_m - 0.08)
            pieces = (
                (
                    "left",
                    Vec3(connector.bounds.min_x + wall_t / 2, connector.bounds.center.y, center_z),
                    Vec3(wall_t, connector.bounds.depth, shaft_height),
                ),
                (
                    "right",
                    Vec3(connector.bounds.max_x - wall_t / 2, connector.bounds.center.y, center_z),
                    Vec3(wall_t, connector.bounds.depth, shaft_height),
                ),
                (
                    "back",
                    Vec3(connector.bounds.center.x, connector.bounds.max_y - wall_t / 2, center_z),
                    Vec3(connector.bounds.width, wall_t, shaft_height),
                ),
            )
            for name, center, size in pieces:
                scene.primitives.append(
                    self._box(
                        f"{connector.id}_level_{floor.level:02d}_shaft_{name}",
                        connector.id,
                        center,
                        size,
                        0.0,
                        "elevator_shaft",
                        "industrial_metal",
                        layer,
                        metadata={"served_level": floor.level},
                    )
                )
            scene.primitives.append(
                self._box(
                    f"{connector.id}_level_{floor.level:02d}_landing_door",
                    connector.id,
                    Vec3(
                        connector.bounds.center.x,
                        connector.bounds.min_y + wall_t / 2,
                        floor.elevation_m + min(1.15, floor.height_m * 0.38),
                    ),
                    Vec3(
                        max(0.65, connector.bounds.width - wall_t * 2),
                        wall_t,
                        min(2.2, floor.height_m * 0.72),
                    ),
                    0.0,
                    "elevator_landing_door",
                    "commercial_glass",
                    layer,
                    collision_enabled=False,
                    metadata={"served_level": floor.level},
                )
            )

        if not served:
            return
        cabin_height = min(2.35, served[0].height_m * 0.78)
        initial_z = served[0].elevation_m + cabin_height / 2
        scene.primitives.append(
            self._box(
                f"{connector.id}_cabin",
                connector.id,
                Vec3(connector.bounds.center.x, connector.bounds.center.y, initial_z),
                Vec3(
                    max(0.55, connector.bounds.width - wall_t * 2.6),
                    max(0.65, connector.bounds.depth - wall_t * 2.6),
                    cabin_height,
                ),
                0.0,
                "elevator_cabin",
                "industrial_metal",
                f"floor:{served[0].id}",
                collision_enabled=False,
                metadata={
                    "state_machine_id": machine_id,
                    "motion_axis": "z",
                    "motion_model": "discrete_floor_state",
                },
            )
        )
        states = {
            f"level_{floor.level:02d}": {
                "current_level": floor.level,
                "cabin_z_m": floor.elevation_m + cabin_height / 2,
                "nav_passable": True,
            }
            for floor in served
        }
        transitions = []
        for source in served:
            for target in served:
                if source.level == target.level:
                    continue
                transitions.append(
                    StateTransition(
                        f"go_to_level_{target.level:02d}",
                        f"level_{source.level:02d}",
                        f"level_{target.level:02d}",
                        max(1.0, abs(target.level - source.level) * 1.2),
                    )
                )
        scene.state_machines.append(
            InteractionStateMachine(
                id=machine_id,
                owner_id=connector.id,
                state_type="elevator_controller",
                initial_state=f"level_{served[0].level:02d}",
                states=states,
                transitions=transitions,
            )
        )

    @staticmethod
    def _metadata(scene: GeometryScene) -> dict:
        return {
            "compiler": "deterministic_geometry_v1",
            "primitive_count": len(scene.primitives),
            "collision_primitive_count": sum(
                primitive.collision_enabled for primitive in scene.primitives
            ),
            "articulated_primitive_count": sum(
                primitive.body_type == "articulated" for primitive in scene.primitives
            ),
            "navigation_node_count": len(scene.navigation.nodes),
            "navigation_edge_count": len(scene.navigation.edges),
            "state_machine_count": len(scene.state_machines),
            "elevator_controller_count": sum(
                machine.state_type == "elevator_controller"
                for machine in scene.state_machines
            ),
            "layer_count": len(scene.layers),
            "furnishing_primitive_count": sum(
                primitive.semantic_class.startswith("furniture_")
                for primitive in scene.primitives
            ),
            "facade_primitive_count": sum(
                primitive.semantic_class.startswith(("facade_", "storefront_", "balcony_"))
                or primitive.semantic_class == "entrance_portal"
                for primitive in scene.primitives
            ),
            "streetscape_primitive_count": sum(
                bool(
                    primitive.layer_id == "roads"
                    and (
                        primitive.metadata.get("road_detail")
                        or primitive.metadata.get("street_asset")
                        or primitive.metadata.get("population_role")
                    )
                )
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
            "elevator_primitive_count": sum(
                primitive.semantic_class.startswith("elevator_")
                for primitive in scene.primitives
            ),
            "asset_registry_count": 0,
            "resolved_asset_primitive_count": sum(
                bool(primitive.metadata.get("resolved_asset"))
                for primitive in scene.primitives
            ),
            "city_ground_plane_count": sum(
                primitive.semantic_class == "city_ground" for primitive in scene.primitives
            ),
            "parcel_edge_count": sum(
                primitive.semantic_class == "parcel_edge" for primitive in scene.primitives
            ),
            "surface_patch_count": sum(
                primitive.semantic_class
                in {"parcel_surface_patch", "landscape_surface_patch"}
                for primitive in scene.primitives
            ),
            "surface_material_variant_count": len(
                {
                    primitive.material_id
                    for primitive in scene.primitives
                    if primitive.semantic_class
                    in {"parcel_surface_patch", "landscape_surface_patch"}
                }
            ),
            "landmark_feature_count": sum(
                bool(primitive.metadata.get("landmark_feature"))
                for primitive in scene.primitives
            ),
        }

    @staticmethod
    def _rendering_profile(city: City) -> dict[str, Any]:
        """Stable scene-level lighting hints for reproducible captures."""
        seed = int(city.metadata.get("seed", 0) or 0)
        return {
            "version": "city_rendering.v1",
            "preset": "sunny_hazy_day",
            "sun_azimuth_deg": round(132.0 + (seed % 37), 3),
            "sun_elevation_deg": round(42.0 + (seed % 11), 3),
            "sun_intensity_scale": 1.0,
            "fog_density_scale": 0.82,
            "exposure_scale": 1.04,
            "shadow_softness": "medium",
            "color_grading": "warm_neutral",
        }

    @staticmethod
    def _segments_excluding(start, end, openings):
        clipped = sorted(
            (max(start, left), min(end, right))
            for left, right in openings
            if right > start and left < end
        )
        cursor = start
        result = []
        for left, right in clipped:
            if left > cursor + 1e-6:
                result.append((cursor, left))
            cursor = max(cursor, right)
        if cursor < end - 1e-6:
            result.append((cursor, end))
        return result

    def _add_slab_frame(
        self, scene, prefix, owner_id, outer, hole, z, thickness, layer
    ) -> None:
        pieces = [
            Bounds2D(outer.min_x, outer.min_y, hole.min_x, outer.max_y),
            Bounds2D(hole.max_x, outer.min_y, outer.max_x, outer.max_y),
            Bounds2D(hole.min_x, outer.min_y, hole.max_x, hole.min_y),
            Bounds2D(hole.min_x, hole.max_y, hole.max_x, outer.max_y),
        ]
        for index, bounds in enumerate(pieces):
            if bounds.width > 1e-6 and bounds.depth > 1e-6:
                scene.primitives.append(
                    self._bounds_box(
                        f"{prefix}_{index:02d}",
                        owner_id,
                        bounds,
                        z,
                        thickness,
                        "floor_slab",
                        "concrete",
                        layer,
                    )
                )
