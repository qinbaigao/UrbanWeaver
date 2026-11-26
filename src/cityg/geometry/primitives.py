"""Primitive construction helpers shared by geometry compilation stages.

The helpers intentionally remain a small mixin instead of a second scene
compiler.  ``GeometryCompiler`` keeps the public entry point and orchestration,
while this module owns the repetitive IR construction and asset-backed outdoor
mesh lookup.
"""

from __future__ import annotations

from cityg.assets import choose_asset_variant
from cityg.geometry.model import GeometryPrimitive, Vec3
from cityg.geometry.asset_fitting import fit_outdoor_asset, outdoor_asset_yaw_offset, outdoor_asset_ground_offset


class PrimitiveFactoryMixin:
    """Factory methods for simulator-neutral geometry primitives."""

    def _outdoor_mesh(
        self,
        primitive_id,
        owner_id,
        center,
        size,
        rotation,
        semantic,
        category,
        query,
        layer,
        *,
        metadata=None,
        required_asset_tags=(),
        exclude_stylized=False,
    ):
        required_tokens = {
            "park_tree": (),
            "shrub": ("shrub", "bush", "ornamental"),
            "playground": ("playground", "climber", "slide"),
            "street_bench": ("bench", "seating"),
            "street_light": ("light", "lamp", "streetlight"),
        }.get(category, ())
        candidates = self.asset_registry.search(
            query,
            category=category,
            limit=64,
            require_geometry=True,
            required_tokens=required_tokens,
        )
        # A broadleaf tree is a valid park asset even when the registry's
        # source classifier recorded it as a street tree.  This lets the
        # photorealistic Poly Haven variants serve both contexts instead of
        # forcing every park to reuse one legacy model.
        if category == "park_tree":
            candidates += self.asset_registry.search(
                query,
                category="street_tree",
                limit=64,
                require_geometry=True,
                required_tokens=("tree", "broadleaf", "deciduous"),
            )
        greenery_categories = {"park_tree", "street_tree", "shrub", "plant"}
        if category in greenery_categories:
            # Kenney/Quaternius foliage is retained for compatibility and
            # regression fixtures, but the presentation path must not select
            # the simple cyan/low-poly proxies. Prefer realistic PBR records
            # whenever at least one is available.
            realistic = [
                item for item in candidates
                if str(item[0].metadata.get("style", "")).lower()
                not in {"stylized_low_poly", "stylized_pbr"}
            ]
            # Do not silently fall back to a stylized tree when the requested
            # subtype has no realistic candidate; callers can then use their
            # semantic fallback (for example columnar -> deciduous PBR).
            candidates = realistic
        candidates = [
            item
            for item in candidates
            if item[0].metadata.get("outdoor_pack_status")
            not in {"rejected", "candidate"}
        ]
        if required_asset_tags:
            # A curated planting palette requests actual species/groups, not
            # just the top-scoring generic 'plant'. Missing groups stay empty.
            candidates = [item for item in candidates
                if set(required_asset_tags).issubset(item[0].tags)
                and item[0].environment in {"outdoor", "both"}
                and self.asset_registry.resolve_path(item[0].geometry_path).is_file()]
        if exclude_stylized:
            candidates=[item for item in candidates if item[0].metadata.get('style')
                not in {'stylized_low_poly','stylized_pbr'}
                and item[0].environment in {'outdoor','both'}
                and self.asset_registry.resolve_path(item[0].geometry_path).is_file()]
        if category in {"park_tree", "street_tree"} and "dead" not in str(query).lower():
            candidates = [
                item
                for item in candidates
                if "dead" not in " ".join(
                    (
                        item[0].asset_id,
                        str(item[0].metadata.get("source_relative_path", "")),
                        *item[0].tags,
                    )
                ).lower()
            ]
        if category in {"park_tree", "street_tree"} and "palm" not in str(query).lower():
            candidates = [
                item
                for item in candidates
                if "palm" not in " ".join(
                    (
                        item[0].asset_id,
                        str(item[0].metadata.get("source_relative_path", "")),
                        *item[0].tags,
                    )
                ).lower()
            ]
        if category in {"park_tree", "street_tree"} and not {
            "fall", "autumn"
        } & set(str(query).lower().split()):
            candidates = [
                item
                for item in candidates
                if not any(
                    token in " ".join(
                        (
                            item[0].asset_id,
                            str(item[0].metadata.get("source_relative_path", "")),
                            *item[0].tags,
                        )
                    ).lower()
                    for token in ("fall", "autumn")
                )
            ]
        if not candidates:
            return None
        # Ultra-dense source meshes remain available for deliberate hero
        # close-ups, but must not silently multiply across an entire city.
        record = choose_asset_variant(
            candidates,
            f"{primitive_id}|{query}",
            # City-scale foliage is instanced by the viewer, so allowing a
            # larger textured mesh gives real botanical silhouettes without
            # multiplying geometry per placement.
            max_triangle_count=(4_000_000 if category == "park_tree" else 2_500_000),
            premium_probability=(0.90 if category in greenery_categories else 0.58),
        )
        if record is None:
            return None
        if not record.geometry_path:
            return None
        material = record.material_id or "street_furniture"
        if material not in {item.id for item in self._materials()}:
            material = "street_furniture"
        fitted_size = fit_outdoor_asset(record, size)
        center = Vec3(center.x, center.y, center.z + (fitted_size.z - size.z) / 2
                      - outdoor_asset_ground_offset(record, fitted_size))
        rotation += outdoor_asset_yaw_offset(record)
        return self._mesh(
            primitive_id,
            owner_id,
            center,
            fitted_size,
            rotation,
            semantic,
            material,
            layer,
            collision_enabled=False,
            instance_key=f"asset_{record.asset_id}",
            metadata={
                **(metadata or {}),
                "asset_id": record.asset_id,
                "asset_category": record.category,
                "asset_source": record.source,
                "asset_license": record.license_id,
                "asset_geometry_path": str(
                    self.asset_registry.resolve_path(record.geometry_path)
                ),
                "outdoor_slot": record.metadata.get("outdoor_slot"),
                "resolved_asset": True,
            },
        )

    @staticmethod
    def _box(
        primitive_id,
        owner_id,
        center,
        size,
        rotation,
        semantic,
        material,
        layer,
        *,
        body_type="static",
        instance_key="unit_box",
        metadata=None,
        collision_enabled=True,
    ):
        return GeometryPrimitive(
            id=primitive_id,
            owner_id=owner_id,
            primitive_type="box",
            center=center,
            size=size,
            rotation_z_deg=rotation,
            semantic_class=semantic,
            material_id=material,
            layer_id=layer,
            collision_enabled=collision_enabled,
            body_type=body_type,
            instance_key=instance_key,
            metadata=metadata or {},
        )

    @staticmethod
    def _mesh(
        primitive_id,
        owner_id,
        center,
        size,
        rotation,
        semantic,
        material,
        layer,
        *,
        body_type="static",
        instance_key="asset_mesh",
        metadata=None,
        collision_enabled=True,
    ):
        return GeometryPrimitive(
            id=primitive_id,
            owner_id=owner_id,
            primitive_type="mesh",
            center=center,
            size=size,
            rotation_z_deg=rotation,
            semantic_class=semantic,
            material_id=material,
            layer_id=layer,
            collision_enabled=collision_enabled,
            body_type=body_type,
            instance_key=instance_key,
            metadata=metadata or {},
        )

    @staticmethod
    def _cylinder(
        primitive_id,
        owner_id,
        center,
        size,
        rotation,
        semantic,
        material,
        layer,
        *,
        body_type="static",
        instance_key="unit_cylinder",
        metadata=None,
        collision_enabled=True,
    ):
        return GeometryPrimitive(
            id=primitive_id,
            owner_id=owner_id,
            primitive_type="cylinder",
            center=center,
            size=size,
            rotation_z_deg=rotation,
            semantic_class=semantic,
            material_id=material,
            layer_id=layer,
            collision_enabled=collision_enabled,
            body_type=body_type,
            instance_key=instance_key,
            metadata=metadata or {},
        )

    @staticmethod
    def _sphere(
        primitive_id,
        owner_id,
        center,
        size,
        rotation,
        semantic,
        material,
        layer,
        *,
        body_type="static",
        instance_key="unit_sphere",
        metadata=None,
        collision_enabled=True,
    ):
        return GeometryPrimitive(
            id=primitive_id,
            owner_id=owner_id,
            primitive_type="sphere",
            center=center,
            size=size,
            rotation_z_deg=rotation,
            semantic_class=semantic,
            material_id=material,
            layer_id=layer,
            collision_enabled=collision_enabled,
            body_type=body_type,
            instance_key=instance_key,
            metadata=metadata or {},
        )

    @classmethod
    def _bounds_box(
        cls,
        primitive_id,
        owner_id,
        bounds,
        z,
        height,
        semantic,
        material,
        layer,
        metadata=None,
        collision_enabled=True,
    ):
        return cls._box(
            primitive_id,
            owner_id,
            Vec3(bounds.center.x, bounds.center.y, z),
            Vec3(bounds.width, bounds.depth, height),
            0.0,
            semantic,
            material,
            layer,
            metadata=metadata,
            collision_enabled=collision_enabled,
        )
