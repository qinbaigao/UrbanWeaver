#!/usr/bin/env python3
"""Bind the downloaded ground PBR pack to CityG material IDs.

This is intentionally a separate, repeatable curation step: replacing the
Poly Haven pack or using a private equivalent only requires rerunning this
script (or editing the generated material records), not changing geometry.
"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / "assets" / "material_library.json"
PACK_ROOT = "incoming/ground_materials"


def pbr_record(material_id: str, asset_id: str, color: list[float], scale: float) -> dict:
    prefix = f"{PACK_ROOT}/{asset_id}/{asset_id}"
    return {
        "material_id": material_id,
        "display_color": color,
        "roughness": 0.88 if "paving" in asset_id or "concrete" in asset_id else 0.96,
        "metallic": 0.0,
        "opacity": 1.0,
        "base_color_path": f"{prefix}_base_color_2k.jpg",
        "normal_path": f"{prefix}_normal_2k.jpg",
        "roughness_path": f"{prefix}_roughness_2k.jpg",
        "ambient_occlusion_path": f"{prefix}_ambient_occlusion_2k.jpg",
        "source": f"Poly Haven:{asset_id}",
        "license_id": "CC0-1.0",
        "texture_scale_m": scale,
    }


def main() -> None:
    payload = json.loads(LIBRARY.read_text(encoding="utf-8"))
    records = {str(item["material_id"]): item for item in payload.get("materials", [])}

    grass_ids = ("grass", "parcel_lawn", "grass_deep", "grass_dry", "parcel_lawn_deep", "parcel_lawn_dry")
    for material_id in grass_ids:
        scale = 5.0 if material_id in {"grass", "parcel_lawn"} else 3.5
        records[material_id] = pbr_record(material_id, "grass_path_2", [0.25, 0.45, 0.18], scale)

    concrete_ids = (
        "courtyard_paving", "civic_forecourt", "service_yard", "plaza_paving",
        "landscape_path", "paving_light", "paving_dark", "permeable_paver",
        "service_concrete_light", "service_concrete_dark",
    )
    for material_id in concrete_ids:
        scale = {
            "courtyard_paving": 4.0,
            "civic_forecourt": 6.0,
            "service_yard": 8.0,
            "plaza_paving": 6.0,
            "landscape_path": 4.0,
        }.get(material_id, 2.8)
        records[material_id] = pbr_record(material_id, "concrete_pavement", [0.58, 0.57, 0.53], scale)

    records["brick_paving"] = pbr_record("brick_paving", "brick_pavement", [0.55, 0.28, 0.18], 2.2)
    records["gravel_warm"] = pbr_record("gravel_warm", "gravel_ground_01", [0.48, 0.41, 0.31], 2.6)

    payload["schema_version"] = "cityg.materials.v1"
    payload["materials"] = [records[key] for key in sorted(records)]
    LIBRARY.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Updated {LIBRARY}: {len(payload['materials'])} materials")


if __name__ == "__main__":
    main()
