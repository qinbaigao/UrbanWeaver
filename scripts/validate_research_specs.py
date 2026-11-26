"""Generate and validate every Phase 0 research specification."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from cityg.planning import BaselineCityPlanner
from cityg.schemas import CitySpec
from cityg.validation import CityValidator


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    spec_dir = project_root / "examples" / "research_specs"
    paths = sorted(spec_dir.glob("*.json"))
    if not paths:
        print("No research specifications found", file=sys.stderr)
        return 2

    failed = False
    print("spec\tbuildings\tfloors\trooms\troads\tvalidation")
    for path in paths:
        spec = CitySpec.from_dict(json.loads(path.read_text(encoding="utf-8")))
        city = BaselineCityPlanner().plan(spec)
        report = CityValidator().validate(city)
        buildings = list(city.iter_buildings())
        floors = list(city.iter_floors())
        rooms = list(city.iter_rooms())
        status = "OK" if report.ok else f"FAILED({len(report.errors)})"
        print(
            f"{path.stem}\t{len(buildings)}\t{len(floors)}\t{len(rooms)}\t"
            f"{len(city.road_network.segments)}\t{status}"
        )
        if len(buildings) != spec.building_count or not report.ok:
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

