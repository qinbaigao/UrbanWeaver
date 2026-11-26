"""Function-aware landscape treatment for occupied building parcels."""

from __future__ import annotations

import hashlib
import math
from typing import Any

from cityg.ccwp import point_segment_distance
from cityg.geometry.model import Vec3
from cityg.schemas import City, Point2D


class ParcelLandscapeCompilerMixin:
    """Populate the usable setback around buildings without changing layout."""

    @staticmethod
    def _parcel_seed(*values: str) -> int:
        digest = hashlib.sha256("|".join(values).encode("utf-8")).digest()
        return int.from_bytes(digest[:4], "big")

    @staticmethod
    def _parcel_function(parcel: Any, district_function: str) -> str:
        functions = [str(item.function).lower() for item in parcel.buildings]
        value = functions[0] if functions else district_function.lower()
        if value in {"retail", "commercial", "office"}:
            return "commercial"
        if value in {"mixed-use", "mixed_use"}:
            return "mixed_use"
        if value in {"public", "public_service", "education", "healthcare"}:
            return "civic"
        return value

    @staticmethod
    def _point_clear_of_buildings(parcel: Any, point: Point2D, clearance: float) -> bool:
        return all(
            not (
                building.footprint.min_x - clearance <= point.x <= building.footprint.max_x + clearance
                and building.footprint.min_y - clearance <= point.y <= building.footprint.max_y + clearance
            )
            for building in parcel.buildings
        )

    def _point_clear_of_roads(self, city: City, point: Point2D, clearance: float) -> bool:
        # Keep the original >= boundary semantics; broad phase only skips
        # roads too far away to affect this candidate landscape point.
        if not hasattr(self, '_parcel_road_bounds'):
            self._parcel_road_bounds = {}
        for road in city.road_network.segments:
            cached = self._parcel_road_bounds.get(road.id)
            if cached is None or cached[0] is not road.centerline:
                points = road.centerline
                cached = (points, (min(p.x for p in points), min(p.y for p in points),
                                   max(p.x for p in points), max(p.y for p in points)))
                self._parcel_road_bounds[road.id] = cached
            x0, y0, x1, y1 = cached[1]
            radius = road.width_m / 2 + clearance + 1e-8
            if (point.x < x0 - radius or point.x > x1 + radius or
                    point.y < y0 - radius or point.y > y1 + radius):
                continue
            if not point_segment_distance(point, road.centerline) >= road.width_m / 2 + clearance:
                return False
        return True

    def _parcel_candidates(
        self,
        city: City,
        parcel: Any,
        *,
        clearance: float,
        count: int,
        token: str,
    ) -> list[Point2D]:
        bounds = parcel.bounds
        margin = max(0.8, min(2.2, clearance))
        if bounds.width <= margin * 2 or bounds.depth <= margin * 2:
            return []
        seed_x = (self._parcel_seed(parcel.id, token, "x") % 1000) / 1000.0
        seed_y = (self._parcel_seed(parcel.id, token, "y") % 1000) / 1000.0
        result: list[Point2D] = []
        attempts = max(24, count * 16)
        for index in range(attempts):
            x_ratio = (seed_x + (index + 1) * 0.61803398875) % 1.0
            y_ratio = (seed_y + (index + 1) * 0.41421356237) % 1.0
            point = Point2D(
                bounds.min_x + margin + x_ratio * (bounds.width - margin * 2),
                bounds.min_y + margin + y_ratio * (bounds.depth - margin * 2),
            )
            if not self._point_clear_of_buildings(parcel, point, clearance):
                continue
            if not self._point_clear_of_roads(city, point, 0.45):
                continue
            if any(math.hypot(point.x - item.x, point.y - item.y) < clearance * 1.5 for item in result):
                continue
            result.append(point)
            if len(result) >= count:
                break
        return result

    def _surface_patch_fits(
        self,
        city: City,
        parcel: Any,
        ground: Any,
        point: Point2D,
        width: float,
        depth: float,
        rotation_deg: float,
    ) -> bool:
        """Check the complete rotated patch, not only its centre point."""
        angle = math.radians(rotation_deg)
        cosine, sine = math.cos(angle), math.sin(angle)
        local_samples = (
            (0.0, 0.0),
            (-width / 2, -depth / 2),
            (-width / 2, depth / 2),
            (width / 2, -depth / 2),
            (width / 2, depth / 2),
            (-width / 2, 0.0),
            (width / 2, 0.0),
            (0.0, -depth / 2),
            (0.0, depth / 2),
        )
        for local_x, local_y in local_samples:
            sample = Point2D(
                point.x + local_x * cosine - local_y * sine,
                point.y + local_x * sine + local_y * cosine,
            )
            if not (
                ground.min_x + 0.25 <= sample.x <= ground.max_x - 0.25
                and ground.min_y + 0.25 <= sample.y <= ground.max_y - 0.25
            ):
                return False
            if not self._point_clear_of_buildings(parcel, sample, 0.20):
                return False
            if not self._point_clear_of_roads(city, sample, 0.35):
                return False
        return True

    def _compile_parcel_landscape(self, city: City, scene: Any) -> dict[str, int]:
        self._parcel_road_bounds = {}
        stats = {
            "parcel_count": 0,
            "ground_treatment_count": 0,
            "tree_count": 0,
            "shrub_count": 0,
            "seating_count": 0,
            "planting_bed_count": 0,
            "site_amenity_count": 0,
            "resolved_asset_count": 0,
            "procedural_fallback_count": 0,
            "surface_patch_count": 0,
            "surface_material_variant_count": 0,
        }
        layer = "roads"
        for district in city.districts:
            for parcel in district.parcels:
                if not parcel.buildings:
                    continue
                stats["parcel_count"] += 1
                function = self._parcel_function(parcel, district.function)
                ground_material = {
                    "residential": "parcel_lawn",
                    "commercial": "courtyard_paving",
                    "mixed_use": "courtyard_paving",
                    "civic": "civic_forecourt",
                    "industrial": "service_yard",
                }.get(function, "parcel_lawn")
                inset = min(0.35, parcel.bounds.width * 0.01, parcel.bounds.depth * 0.01)
                ground = parcel.bounds.inset(inset)
                metadata = {
                    "parcel_id": parcel.id,
                    "district_id": district.id,
                    "parcel_function": function,
                    "site_detail": True,
                }
                scene.primitives.append(
                    self._bounds_box(
                        f"{parcel.id}_ground_treatment",
                        parcel.id,
                        ground,
                        -0.005,
                        0.035,
                        "parcel_ground",
                        ground_material,
                        layer,
                        metadata=metadata,
                        collision_enabled=False,
                    )
                )
                free_area = max(
                    0.0,
                    parcel.bounds.area
                    - sum(building.footprint.area for building in parcel.buildings),
                )
                # A single parcel-wide material is retained as the semantic
                # base, but it is no longer the only visible surface.  Add a
                # handful of low, bounded patches so courtyards and setbacks
                # read as maintained mixtures of lawn, pavers, mulch and
                # gravel rather than one large synthetic colour rectangle.
                surface_specs = {
                    "residential": (
                        ("parcel_lawn_deep", 0.03),
                        ("parcel_lawn_dry", 0.03),
                        ("mulch_warm", 0.02),
                    ),
                    "commercial": (
                        ("paving_light", 0.025),
                        ("paving_dark", 0.025),
                        ("permeable_paver", 0.025),
                        ("brick_paving", 0.025),
                        ("mulch_warm", 0.02),
                    ),
                    "mixed_use": (
                        ("paving_light", 0.025),
                        ("parcel_lawn_deep", 0.03),
                        ("permeable_paver", 0.025),
                        ("mulch_warm", 0.02),
                    ),
                    "civic": (
                        ("paving_light", 0.025),
                        ("paving_dark", 0.025),
                        ("parcel_lawn_deep", 0.03),
                        ("brick_paving", 0.025),
                        ("flower_soil", 0.02),
                    ),
                    "industrial": (
                        ("service_concrete_light", 0.025),
                        ("service_concrete_dark", 0.025),
                        ("gravel_warm", 0.02),
                    ),
                }.get(function, (("parcel_lawn_deep", 0.03),))
                patch_count = min(8, max(1, round(free_area / 260.0)))
                patch_count = min(patch_count, max(0, round(min(ground.width, ground.depth) / 5.0)))
                patch_points = self._parcel_candidates(
                    city,
                    parcel,
                    clearance=2.0,
                    count=patch_count * 4,
                    token="surface_patch",
                )
                used_materials: set[str] = set()
                placed_patch_specs: list[tuple[Point2D, float, float]] = []
                placed_patches = 0
                for candidate_index, point in enumerate(patch_points):
                    if placed_patches >= patch_count:
                        break
                    material_id, height = surface_specs[
                        (self._parcel_seed(parcel.id, str(candidate_index), "surface_material") + candidate_index)
                        % len(surface_specs)
                    ]
                    # Keep patches comfortably inside the parcel and vary
                    # their footprint/orientation without affecting collision.
                    width = min(8.0, max(2.2, ground.width * (0.12 + (candidate_index % 3) * 0.025)))
                    depth = min(5.0, max(1.6, ground.depth * (0.07 + ((candidate_index + 1) % 3) * 0.018)))
                    rotation = float((self._parcel_seed(parcel.id, str(candidate_index), "surface_rotation") % 5) * 18 - 36)
                    if not self._surface_patch_fits(
                        city, parcel, ground, point, width, depth, rotation
                    ):
                        continue
                    patch_radius = math.hypot(width, depth) * 0.5
                    if any(
                        math.hypot(point.x - other.x, point.y - other.y)
                        < (patch_radius + other_radius) * 0.62
                        for other, other_radius, _ in placed_patch_specs
                    ):
                        continue
                    index = placed_patches
                    scene.primitives.append(
                        self._box(
                            f"{parcel.id}_surface_patch_{index:02d}",
                            parcel.id,
                            Vec3(point.x, point.y, 0.052 if height <= 0.025 else 0.058),
                            Vec3(width, depth, height),
                            rotation,
                            "parcel_surface_patch",
                            material_id,
                            layer,
                            collision_enabled=False,
                            metadata={
                                **metadata,
                                "site_feature": "surface_patch",
                                "surface_role": "internal_patch",
                                "surface_material_variant": material_id,
                                "surface_patch_index": index,
                            },
                        )
                    )
                    used_materials.add(material_id)
                    placed_patch_specs.append((point, patch_radius, rotation))
                    placed_patches += 1
                stats["surface_patch_count"] += placed_patches
                stats["surface_material_variant_count"] += len(used_materials)
                # Thin, function-aware edge bands make parcel boundaries read
                # as real curb/planting interfaces from above instead of large
                # untextured colour rectangles.  They are presentation-only
                # and stay below building shells and pedestrian assets.
                edge_material = {
                    "residential": "parcel_edge_residential",
                    "commercial": "parcel_edge_commercial",
                    "mixed_use": "parcel_edge_commercial",
                    "civic": "parcel_edge_civic",
                    "industrial": "parcel_edge_industrial",
                }.get(function, "parcel_edge_residential")
                edge_z = 0.035
                edge_t = 0.16
                edge_specs = (
                    ("south", Point2D(ground.center.x, ground.min_y + edge_t / 2), (ground.width, edge_t, 0.07), 0.0),
                    ("north", Point2D(ground.center.x, ground.max_y - edge_t / 2), (ground.width, edge_t, 0.07), 0.0),
                    ("west", Point2D(ground.min_x + edge_t / 2, ground.center.y), (edge_t, ground.depth, 0.07), 0.0),
                    ("east", Point2D(ground.max_x - edge_t / 2, ground.center.y), (edge_t, ground.depth, 0.07), 0.0),
                )
                for side, point, size, rotation in edge_specs:
                    scene.primitives.append(
                        self._box(
                            f"{parcel.id}_edge_{side}", parcel.id,
                            Vec3(point.x, point.y, edge_z),
                            Vec3(*size), rotation, "parcel_edge", edge_material,
                            layer, collision_enabled=False,
                            metadata={**metadata, "site_feature": "parcel_edge", "edge_side": side},
                        )
                    )
                stats["ground_treatment_count"] += 1

                if function == "industrial":
                    tree_target, shrub_target, seating_target = 0, 2, 0
                elif function in {"commercial", "mixed_use", "civic"}:
                    tree_target = min(2, max(1, round(free_area / 850.0)))
                    shrub_target = min(8, max(3, round(free_area / 150.0)))
                    seating_target = 2 if free_area >= 180.0 else 1
                else:
                    tree_target = min(3, max(1, round(free_area / 520.0)))
                    shrub_target = min(10, max(4, round(free_area / 120.0)))
                    seating_target = 1 if free_area >= 140.0 else 0

                # Small furniture disappears at city scale. One or two broad
                # planting beds give each occupied parcel a legible landscape
                # structure, while the assets below provide close-up detail.
                bed_target = 2 if free_area >= 260.0 else 1
                for index, point in enumerate(
                    self._parcel_candidates(
                        city,
                        parcel,
                        clearance=1.8,
                        count=bed_target,
                        token="planting_bed",
                    )
                ):
                    base = f"{parcel.id}_planting_bed_{index:02d}"
                    rotation = float(self._parcel_seed(base, "rotation") % 2) * 90.0
                    scene.primitives.append(
                        self._box(
                            base,
                            parcel.id,
                            Vec3(point.x, point.y, 0.08),
                            Vec3(3.0, 1.35, 0.16),
                            rotation,
                            "parcel_planting_bed",
                            "planting_soil",
                            layer,
                            collision_enabled=False,
                            metadata={**metadata, "site_feature": "planting_bed"},
                        )
                    )
                    angle = math.radians(rotation)
                    for plant_index, along in enumerate((-0.85, 0.0, 0.85)):
                        scene.primitives.append(
                            self._sphere(
                                f"{base}_plant_{plant_index}",
                                parcel.id,
                                Vec3(
                                    point.x + math.cos(angle) * along,
                                    point.y + math.sin(angle) * along,
                                    0.42,
                                ),
                                Vec3(0.62, 0.62, 0.68),
                                rotation,
                                "parcel_flower_mass",
                                "flower_accent" if plant_index == 1 else "tree_canopy",
                                layer,
                                collision_enabled=False,
                                metadata={**metadata, "site_feature": "planting_bed"},
                            )
                        )
                    stats["planting_bed_count"] += 1

                tree_query = {
                    "residential": "small deciduous residential shade tree",
                    "commercial": "ornamental broadleaf plaza tree",
                    "mixed_use": "ornamental broadleaf plaza tree",
                    "civic": "formal broadleaf civic tree",
                }.get(function, "deciduous urban tree")
                for index, point in enumerate(
                    self._parcel_candidates(
                        city,
                        parcel,
                        clearance=1.75,
                        count=tree_target,
                        token="tree",
                    )
                ):
                    base = f"{parcel.id}_site_tree_{index:02d}"
                    scale = 0.86 + (self._parcel_seed(base, "scale") % 21) / 100.0
                    tree = self._outdoor_mesh(
                        base,
                        parcel.id,
                        Vec3(point.x, point.y, 3.6 * scale),
                        Vec3(4.8 * scale, 4.8 * scale, 7.2 * scale),
                        float(self._parcel_seed(base, "rotation") % 360),
                        "parcel_tree_asset",
                        "street_tree",
                        tree_query,
                        layer,
                        metadata={**metadata, "site_feature": "tree"},
                    )
                    if tree is not None:
                        scene.primitives.append(tree)
                        stats["resolved_asset_count"] += 1
                    else:
                        scene.primitives.extend(
                            [
                                self._cylinder(
                                    f"{base}_trunk",
                                    parcel.id,
                                    Vec3(point.x, point.y, 2.25 * scale),
                                    Vec3(0.28 * scale, 0.28 * scale, 4.5 * scale),
                                    0.0,
                                    "parcel_tree_trunk",
                                    "tree_trunk",
                                    layer,
                                    collision_enabled=False,
                                    metadata=metadata,
                                ),
                                self._sphere(
                                    f"{base}_canopy",
                                    parcel.id,
                                    Vec3(point.x, point.y, 5.25 * scale),
                                    Vec3(4.4 * scale, 4.1 * scale, 3.6 * scale),
                                    0.0,
                                    "parcel_tree_canopy",
                                    "tree_canopy",
                                    layer,
                                    collision_enabled=False,
                                    metadata=metadata,
                                ),
                            ]
                        )
                        stats["procedural_fallback_count"] += 1
                    stats["tree_count"] += 1

                for index, point in enumerate(
                    self._parcel_candidates(
                        city,
                        parcel,
                        clearance=0.55,
                        count=shrub_target,
                        token="shrub",
                    )
                ):
                    base = f"{parcel.id}_site_shrub_{index:02d}"
                    shrub = self._outdoor_mesh(
                        base,
                        parcel.id,
                        Vec3(point.x, point.y, 0.45),
                        Vec3(1.25, 1.1, 0.9),
                        float(self._parcel_seed(base, "rotation") % 360),
                        "parcel_shrub_asset",
                        "shrub",
                        "ornamental landscape shrub",
                        layer,
                        metadata={**metadata, "site_feature": "shrub"},
                    )
                    if shrub is not None:
                        scene.primitives.append(shrub)
                        stats["resolved_asset_count"] += 1
                    else:
                        scene.primitives.append(
                            self._sphere(
                                base,
                                parcel.id,
                                Vec3(point.x, point.y, 0.42),
                                Vec3(1.25, 1.05, 0.78),
                                float(index * 23),
                                "parcel_shrub",
                                "landscape_shrub",
                                layer,
                                collision_enabled=False,
                                metadata=metadata,
                            )
                        )
                        stats["procedural_fallback_count"] += 1
                    stats["shrub_count"] += 1

                for index, point in enumerate(
                    self._parcel_candidates(
                        city,
                        parcel,
                        clearance=1.0,
                        count=seating_target,
                        token="seat",
                    )
                ):
                    base = f"{parcel.id}_site_bench_{index:02d}"
                    bench = self._outdoor_mesh(
                        base,
                        parcel.id,
                        Vec3(point.x, point.y, 0.43),
                        Vec3(1.9, 0.62, 0.86),
                        float(self._parcel_seed(base, "rotation") % 4) * 90.0,
                        "bench",
                        "street_bench",
                        "public outdoor bench wood metal",
                        layer,
                        metadata={**metadata, "site_feature": "seating"},
                    )
                    scene.primitives.append(
                        bench
                        or self._box(
                            base,
                            parcel.id,
                            Vec3(point.x, point.y, 0.45),
                            Vec3(1.8, 0.52, 0.18),
                            0.0,
                            "parcel_bench",
                            "furniture_wood",
                            layer,
                            collision_enabled=False,
                            metadata=metadata,
                        )
                    )
                    stats["resolved_asset_count" if bench is not None else "procedural_fallback_count"] += 1
                    stats["seating_count"] += 1

                amenity_specs = {
                    "residential": (
                        "large residential entrance planter with greenery",
                        "street_planter",
                        Vec3(1.45, 0.62, 0.85),
                    ),
                    "commercial": (
                        "secure urban bicycle rack outside commercial building",
                        "bicycle_rack",
                        Vec3(1.65, 0.72, 1.0),
                    ),
                    "mixed_use": (
                        "large architectural entrance planter with greenery",
                        "street_planter",
                        Vec3(1.45, 0.62, 0.85),
                    ),
                    "civic": (
                        "public bicycle rack outside civic building",
                        "bicycle_rack",
                        Vec3(1.65, 0.72, 1.0),
                    ),
                    "industrial": (
                        "protective street bollard for service yard",
                        "bollard",
                        Vec3(0.34, 0.34, 0.95),
                    ),
                }
                amenity = amenity_specs.get(function)
                amenity_points = self._parcel_candidates(
                    city,
                    parcel,
                    clearance=1.1,
                    count=1,
                    token="site_amenity",
                )
                if amenity is not None and amenity_points:
                    query, category, size = amenity
                    point = amenity_points[0]
                    base = f"{parcel.id}_site_amenity"
                    item = self._outdoor_mesh(
                        base,
                        parcel.id,
                        Vec3(point.x, point.y, size.z / 2),
                        size,
                        float(self._parcel_seed(base, "rotation") % 4) * 90.0,
                        "parcel_site_amenity",
                        category,
                        query,
                        layer,
                        metadata={**metadata, "site_feature": category},
                    )
                    if item is not None:
                        scene.primitives.append(item)
                        stats["resolved_asset_count"] += 1
                    else:
                        scene.primitives.append(
                            self._box(
                                base,
                                parcel.id,
                                Vec3(point.x, point.y, size.z / 2),
                                size,
                                0.0,
                                "parcel_site_amenity",
                                "street_furniture",
                                layer,
                                collision_enabled=False,
                                metadata={**metadata, "site_feature": category},
                            )
                        )
                        stats["procedural_fallback_count"] += 1
                    stats["site_amenity_count"] += 1
        return stats


__all__ = ["ParcelLandscapeCompilerMixin"]
