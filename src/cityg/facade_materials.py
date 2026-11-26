"""Curate downloaded PBR sources into CityG's semantic facade materials."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from cityg.assets import MaterialLibrary, MaterialRecord


@dataclass(frozen=True)
class FacadeMaterialBinding:
    material_id: str
    source_asset_id: str
    display_color: tuple[float, float, float]
    roughness: float
    metallic: float = 0.0


DEFAULT_FACADE_BINDINGS = (
    FacadeMaterialBinding("residential_facade", "plastered_wall_03", (0.88, 0.82, 0.72), 0.82),
    FacadeMaterialBinding("residential_brick", "brick_wall_09", (0.82, 0.68, 0.56), 0.86),
    FacadeMaterialBinding("residential_sage", "grey_plaster_02", (0.67, 0.76, 0.66), 0.84),
    FacadeMaterialBinding("civic_stone", "granite_wall", (0.78, 0.75, 0.68), 0.78),
    FacadeMaterialBinding("civic_limestone", "rectangular_facade_tiles", (0.88, 0.82, 0.70), 0.76),
    FacadeMaterialBinding("civic_brick", "brick_wall_003", (0.78, 0.57, 0.43), 0.84),
    FacadeMaterialBinding("industrial_metal", "box_profile_metal_sheet", (0.56, 0.60, 0.61), 0.48, 0.34),
    FacadeMaterialBinding("industrial_light", "metal_plate_02", (0.68, 0.70, 0.69), 0.52, 0.28),
    FacadeMaterialBinding("facade_frame_stone", "concrete_wall_008", (0.67, 0.63, 0.56), 0.72),
    FacadeMaterialBinding("facade_frame_limestone", "concrete_wall_007", (0.79, 0.73, 0.63), 0.72),
    FacadeMaterialBinding("roof", "roof_tiles", (0.31, 0.32, 0.32), 0.82),
)


def build_default_facade_material_library(
    source_root: str | Path,
    destination: str | Path,
    *,
    environment_path: str | Path | None = None,
) -> MaterialLibrary:
    """Build a semantic library from verified Poly Haven source manifests."""
    source_root = Path(source_root).expanduser().resolve()
    destination = Path(destination).expanduser().resolve()
    library = MaterialLibrary()
    for binding in DEFAULT_FACADE_BINDINGS:
        directory = source_root / binding.source_asset_id
        source_manifest = directory / "source.json"
        if not source_manifest.is_file():
            raise ValueError(f"Missing facade source manifest: {source_manifest}")
        source = json.loads(source_manifest.read_text(encoding="utf-8"))
        maps = source.get("maps", {})

        def relative_map(channel: str) -> str | None:
            filename = maps.get(channel)
            if not filename:
                return None
            path = directory / filename
            if not path.is_file():
                raise ValueError(f"Missing {channel} texture: {path}")
            return str(path.relative_to(destination.parent))

        dimensions = source.get("physical_dimensions_m") or [2.0]
        texture_scale = max(0.1, float(dimensions[0]))
        library.register(
            MaterialRecord(
                material_id=binding.material_id,
                display_color=binding.display_color,
                roughness=binding.roughness,
                metallic=binding.metallic,
                base_color_path=relative_map("base_color"),
                normal_path=relative_map("normal_gl"),
                roughness_path=relative_map("roughness"),
                ambient_occlusion_path=relative_map("ambient_occlusion"),
                source=f"Poly Haven:{binding.source_asset_id}",
                license_id="CC0-1.0",
                texture_scale_m=texture_scale,
            )
        )
    if environment_path is not None:
        environment = Path(environment_path).expanduser().resolve()
        if not environment.is_file():
            raise ValueError(f"Missing HDRI environment: {environment}")
        library.set_environment(str(environment.relative_to(destination.parent)))
    library.save(destination)
    return library


__all__ = [
    "DEFAULT_FACADE_BINDINGS",
    "FacadeMaterialBinding",
    "build_default_facade_material_library",
]
