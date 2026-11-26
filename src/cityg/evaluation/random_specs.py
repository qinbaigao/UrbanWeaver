"""Seeded CitySpec generator used by the Phase 1 gate."""

from __future__ import annotations

import random

from cityg.schemas import CitySpec, ZoneSpec


ZONE_FUNCTIONS = (
    ("residential", "residential"),
    ("commercial", "commercial"),
    ("public_services", "public_service"),
    ("industrial", "industrial"),
    ("mixed_use", "mixed_use"),
)


def random_city_specs(count: int = 100, seed: int = 20260812) -> list[CitySpec]:
    """Create valid, diverse and fully reproducible CPU-sized specifications."""

    if count < 1:
        raise ValueError("count must be positive")
    rng = random.Random(seed)
    specs = []
    for index in range(count):
        building_count = rng.randint(1, 12)
        zone_count = rng.randint(1, min(3, building_count))
        selected = rng.sample(ZONE_FUNCTIONS, zone_count)
        road_width = rng.uniform(8.0, 16.0)
        specs.append(
            CitySpec(
                name=f"phase1_random_{index:03d}",
                width_m=rng.uniform(260.0, 420.0),
                depth_m=rng.uniform(240.0, 380.0),
                building_count=building_count,
                min_floors=(min_floors := rng.randint(1, 3)),
                max_floors=min_floors + rng.randint(0, 3),
                rooms_per_floor=rng.randint(1, 7),
                road_width_m=road_width,
                sidewalk_width_m=rng.uniform(1.5, 4.0),
                parcel_setback_m=rng.uniform(2.0, 6.0),
                seed=rng.randint(0, 2**31 - 1),
                zones=tuple(
                    ZoneSpec(name, function, rng.uniform(0.25, 2.0))
                    for name, function in selected
                ),
            )
        )
    return specs
