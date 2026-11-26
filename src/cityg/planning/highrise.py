"""Deterministic safety and reuse policy for tall CityG buildings."""

from __future__ import annotations

import math
import random
from collections import defaultdict

from cityg.schemas import Bounds2D, Floor, VerticalConnector


HIGHRISE_MASSING_VARIANTS = frozenset(
    {"standard", "setback", "offset", "slender_landmark"}
)
DEFAULT_HIGHRISE_MASSING_PALETTE = (
    "standard",
    "setback",
    "offset",
    "slender_landmark",
)


class HighRisePolicy:
    """Add non-negotiable tall-building structure after height intent is accepted."""

    highrise_threshold_floors = 10
    second_elevator_threshold_floors = 18

    @classmethod
    def is_highrise(cls, floor_count: int) -> bool:
        return floor_count >= cls.highrise_threshold_floors

    @classmethod
    def podium_floors(cls, floor_count: int) -> int:
        if not cls.is_highrise(floor_count):
            return 0
        return 3 if floor_count >= cls.second_elevator_threshold_floors else 2

    @classmethod
    def massing_variant(
        cls,
        *,
        building_id: str,
        floor_count: int,
        function: str,
        landmark: bool,
        seed: int,
        palette: tuple[str, ...] = DEFAULT_HIGHRISE_MASSING_PALETTE,
    ) -> str | None:
        """Choose controlled silhouette diversity without changing core topology."""

        if not cls.is_highrise(floor_count):
            return None
        allowed = tuple(dict.fromkeys(palette))
        if not allowed or any(
            item not in HIGHRISE_MASSING_VARIANTS for item in allowed
        ):
            raise ValueError("High-rise massing palette is empty or unsupported")
        weights = {
            "standard": 0.64,
            "setback": 0.20,
            "offset": 0.11,
            "slender_landmark": 0.05,
        }
        if landmark:
            weights.update(
                {
                    "standard": 0.12,
                    "setback": 0.30,
                    "offset": 0.12,
                    "slender_landmark": 0.46,
                }
            )
        elif function == "residential":
            weights.update(
                {
                    "standard": 0.72,
                    "setback": 0.18,
                    "offset": 0.08,
                    "slender_landmark": 0.02,
                }
            )
        elif function == "mixed_use":
            weights.update(
                {
                    "standard": 0.58,
                    "setback": 0.23,
                    "offset": 0.15,
                    "slender_landmark": 0.04,
                }
            )
        rng = random.Random(
            f"{seed}:highrise-massing:{building_id}:{floor_count}"
        )
        return rng.choices(
            allowed,
            weights=[weights[item] for item in allowed],
            k=1,
        )[0]

    @classmethod
    def massing_parts(
        cls,
        footprint: Bounds2D,
        floor_count: int,
        massing_variant: str = "standard",
        *,
        orientation_deg: float = 0.0,
    ) -> list[dict[str, float]]:
        """Return the shared high-rise silhouette parts used by planning/rendering.

        The returned centers are in world planning coordinates and the part
        dimensions are in the building-local frame. Keeping this contract in
        ``HighRisePolicy`` prevents the Floor Agent and GeometryCompiler from
        silently using different tower/podium outlines.
        """

        rotation = math.radians(float(orientation_deg))
        cos_abs = abs(math.cos(rotation))
        sin_abs = abs(math.sin(rotation))
        raw_width = footprint.width
        raw_depth = footprint.depth
        rotated_width = cos_abs * raw_width + sin_abs * raw_depth
        rotated_depth = sin_abs * raw_width + cos_abs * raw_depth
        fit = 0.90 * min(
            footprint.width / max(rotated_width, 1e-6),
            footprint.depth / max(rotated_depth, 1e-6),
        )
        width = raw_width * fit
        depth = raw_depth * fit
        podium_ratio = max(0.12, cls.podium_floors(floor_count) / max(1, floor_count))
        variants = {
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
        selected = variants.get(massing_variant, variants["standard"])
        cos_signed = math.cos(rotation)
        sin_signed = math.sin(rotation)
        parts: list[dict[str, float]] = []
        for local_x, local_y, scale_x, scale_y, height_scale in selected:
            offset_x = local_x * width
            offset_y = local_y * depth
            parts.append(
                {
                    "center_x": footprint.center.x
                    + offset_x * cos_signed
                    - offset_y * sin_signed,
                    "center_y": footprint.center.y
                    + offset_x * sin_signed
                    + offset_y * cos_signed,
                    "width": width * scale_x,
                    "depth": depth * scale_y,
                    "height_scale": height_scale,
                    "rotation": float(orientation_deg),
                }
            )
        return parts

    @classmethod
    def floor_plate_contract(
        cls,
        footprint: Bounds2D,
        floor_count: int,
        massing_variant: str | None,
        *,
        orientation_deg: float = 0.0,
    ) -> dict:
        """Describe the realizable local plate for every floor.

        ``bounds`` is the largest active massing part at that level, while
        ``outline_parts`` retains all eligible parts for the LLM's context.
        The deterministic layout uses the same largest active part as a safe
        room-planning envelope; the geometry compiler still performs exact
        conformance against all eligible parts.
        """

        if not cls.is_highrise(floor_count) or not massing_variant:
            levels = range(floor_count)
            return {
                "source": "full_building_footprint",
                "coordinate_frame": "building_local",
                "levels": [
                    {
                        "level": level,
                        "stage": "full_plate",
                        "bounds": {
                            "min_x": footprint.min_x - footprint.center.x,
                            "min_y": footprint.min_y - footprint.center.y,
                            "max_x": footprint.max_x - footprint.center.x,
                            "max_y": footprint.max_y - footprint.center.y,
                        },
                        "area_m2": round(footprint.area, 3),
                        "outline_parts": [],
                    }
                    for level in levels
                ],
            }

        parts = cls.massing_parts(
            footprint,
            floor_count,
            massing_variant,
            orientation_deg=orientation_deg,
        )
        angle = math.radians(float(orientation_deg))
        cos_angle = math.cos(angle)
        sin_angle = math.sin(angle)

        def local_bounds(part: dict[str, float]) -> Bounds2D:
            dx = part["center_x"] - footprint.center.x
            dy = part["center_y"] - footprint.center.y
            center_x = dx * cos_angle + dy * sin_angle
            center_y = -dx * sin_angle + dy * cos_angle
            return Bounds2D(
                center_x - part["width"] / 2,
                center_y - part["depth"] / 2,
                center_x + part["width"] / 2,
                center_y + part["depth"] / 2,
            )

        level_contracts = []
        for level in range(floor_count):
            normalized_height = (level + 0.5) / max(1, floor_count)
            active = [
                part
                for part in parts
                if normalized_height <= part["height_scale"] + 1e-6
            ] or [max(parts, key=lambda item: item["height_scale"])]
            active_bounds = [local_bounds(part) for part in active]
            primary = max(active, key=lambda item: item["width"] * item["depth"])
            bounds = local_bounds(primary)
            level_contracts.append(
                {
                    "level": level,
                    "stage": "tower" if primary["height_scale"] >= 0.99 else "podium",
                    "bounds": {
                        "min_x": bounds.min_x,
                        "min_y": bounds.min_y,
                        "max_x": bounds.max_x,
                        "max_y": bounds.max_y,
                    },
                    "area_m2": round(bounds.area, 3),
                    "outline_parts": [
                        {
                            "min_x": item.min_x,
                            "min_y": item.min_y,
                            "max_x": item.max_x,
                            "max_y": item.max_y,
                            "height_scale": part["height_scale"],
                        }
                        for part, item in zip(active, active_bounds)
                    ],
                }
            )
        return {
            "source": "highrise_massing_outline_v1",
            "coordinate_frame": "building_local",
            "massing_variant": massing_variant,
            "orientation_deg": float(orientation_deg),
            "levels": level_contracts,
        }

    @classmethod
    def floor_plate_bounds(
        cls,
        footprint: Bounds2D,
        floor_count: int,
        level: int,
        massing_variant: str | None,
        *,
        orientation_deg: float = 0.0,
    ) -> Bounds2D:
        if not cls.is_highrise(floor_count) or not massing_variant:
            return footprint
        contract = cls.floor_plate_contract(
            footprint,
            floor_count,
            massing_variant,
            orientation_deg=orientation_deg,
        )
        item = contract["levels"][max(0, min(level, len(contract["levels"]) - 1))]
        raw = item["bounds"]
        # The contract is intentionally expressed in the building-local frame
        # for the LLM. City schemas, however, store room bounds in world
        # planning coordinates, so translate the selected envelope back to the
        # footprint origin before deterministic instantiation.
        return Bounds2D(
            raw["min_x"] + footprint.center.x,
            raw["min_y"] + footprint.center.y,
            raw["max_x"] + footprint.center.x,
            raw["max_y"] + footprint.center.y,
        )

    @classmethod
    def connectors(
        cls,
        building_id: str,
        floor_count: int,
        footprint: Bounds2D,
        corridor_depth: float,
    ) -> list[VerticalConnector]:
        if floor_count <= 1:
            return []
        if not cls.is_highrise(floor_count):
            width = min(2.4, footprint.width * 0.18)
            return [
                VerticalConnector(
                    id=f"{building_id}_stairs",
                    connector_type="stairs",
                    bounds=Bounds2D(
                        footprint.center.x - width / 2,
                        footprint.center.y - corridor_depth * 0.4,
                        footprint.center.x + width / 2,
                        footprint.center.y + corridor_depth * 0.4,
                    ),
                    from_level=0,
                    to_level=floor_count - 1,
                    metadata={"egress_role": "primary"},
                )
            ]

        elevator_count = 2 if floor_count >= cls.second_elevator_threshold_floors else 1
        kinds = ["stairs", *("elevator" for _ in range(elevator_count)), "stairs"]
        usable_width = min(footprint.width * 0.72, 10.5)
        gap = min(0.30, usable_width * 0.035)
        unit_width = (usable_width - gap * (len(kinds) - 1)) / len(kinds)
        unit_width = max(1.15, unit_width)
        total_width = unit_width * len(kinds) + gap * (len(kinds) - 1)
        cursor = footprint.center.x - total_width / 2
        depth = max(1.3, corridor_depth * 0.72)
        depth = min(depth, corridor_depth * 0.86)
        connectors = []
        stair_index = elevator_index = 0
        for connector_type in kinds:
            center_x = cursor + unit_width / 2
            bounds = Bounds2D(
                center_x - unit_width / 2,
                footprint.center.y - depth / 2,
                center_x + unit_width / 2,
                footprint.center.y + depth / 2,
            )
            if connector_type == "stairs":
                suffix = "primary" if stair_index == 0 else "secondary"
                connector_id = f"{building_id}_stairs_{suffix}"
                metadata = {
                    "egress_role": suffix,
                    "fire_separated_proxy": True,
                }
                interactive = False
                stair_index += 1
            else:
                connector_id = f"{building_id}_elevator_{elevator_index:02d}"
                metadata = {
                    "elevator_index": elevator_index,
                    "capacity_persons": 13,
                    "rated_load_kg": 1000,
                    "service_type": (
                        "passenger" if elevator_index == 0 else "service"
                    ),
                    "motion_model": "discrete_floor_state",
                }
                interactive = True
                elevator_index += 1
            connectors.append(
                VerticalConnector(
                    id=connector_id,
                    connector_type=connector_type,
                    bounds=bounds,
                    from_level=0,
                    to_level=floor_count - 1,
                    interactive=interactive,
                    metadata=metadata,
                )
            )
            cursor += unit_width + gap
        return connectors

    @classmethod
    def annotate_typical_floors(
        cls, building_id: str, floors: list[Floor], podium_floors: int
    ) -> list[dict]:
        """Mark semantic reuse groups without collapsing unique room/door IDs."""

        prototypes: dict[object, int] = {}
        groups: dict[str, list[int]] = defaultdict(list)
        top_level = max((floor.level for floor in floors), default=0)
        for floor in floors:
            # Geometry templates may be instanced even when room semantics/furniture vary.
            signature = tuple(
                (
                    round(room.bounds.width, 3),
                    round(room.bounds.depth, 3),
                    room.function == "corridor",
                )
                for room in floor.rooms
            )
            planned_zone_id = floor.metadata.get("vertical_zone_id")
            if planned_zone_id:
                role = str(floor.metadata.get("program_role", "typical"))
                zone_signature = (str(planned_zone_id), signature)
                prototype_level = prototypes.setdefault(zone_signature, floor.level)
                template_id = (
                    f"{building_id}_{planned_zone_id}_template_{prototype_level:02d}"
                )
            elif floor.level < podium_floors:
                template_id = f"{building_id}_podium_template_{floor.level:02d}"
                prototype_level = floor.level
                role = "podium"
            elif floor.level == top_level:
                template_id = f"{building_id}_top_template"
                prototype_level = floor.level
                role = "top"
            else:
                prototype_level = prototypes.setdefault(signature, floor.level)
                template_id = f"{building_id}_typical_template_{prototype_level:02d}"
                role = "typical"
            floor.metadata.update(
                {
                    "vertical_role": role,
                    "template_id": template_id,
                    "prototype_floor_level": prototype_level,
                    "is_typical_floor": role == "typical",
                }
            )
            groups[template_id].append(floor.level)
        return [
            {
                "template_id": template_id,
                "prototype_floor_level": levels[0],
                "levels": levels,
                "instance_count": len(levels),
            }
            for template_id, levels in sorted(groups.items())
        ]

    @classmethod
    def metadata(
        cls,
        floor_count: int,
        reuse_groups: list[dict],
        *,
        massing_variant: str | None = None,
        massing_palette: tuple[str, ...] = (),
    ) -> dict:
        highrise = cls.is_highrise(floor_count)
        podium = cls.podium_floors(floor_count)
        return {
            "enabled": highrise,
            "threshold_floors": cls.highrise_threshold_floors,
            "podium_floors": podium,
            "tower_floors": max(0, floor_count - podium),
            "required_stair_count": 2 if highrise else (1 if floor_count > 1 else 0),
            "required_elevator_count": (
                2
                if floor_count >= cls.second_elevator_threshold_floors
                else (1 if highrise else 0)
            ),
            "typical_floor_reuse": reuse_groups,
            "reuse_mode": "semantic_template_contract",
            "massing_variant": massing_variant if highrise else None,
            "massing_palette": list(massing_palette) if highrise else [],
            "massing_constraint": "single_continuous_core",
        }
