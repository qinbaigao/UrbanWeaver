"""Coarse-to-fine generation pipeline orchestration."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from cityg.planning import BaselineCityPlanner, CityPlanner
from cityg.schemas import City, CitySpec
from cityg.serialization import save_json
from cityg.services import ManifestBackend, SimulationBackend
from cityg.validation import CityValidator, ValidationReport


@dataclass
class GenerationResult:
    city: City
    validation: ValidationReport
    artifacts: list[Path]

    @property
    def ok(self) -> bool:
        return self.validation.ok


class GenerationPipeline:
    """Orchestrate planning, deterministic validation, and compilation."""

    def __init__(
        self,
        planner: CityPlanner | None = None,
        validator: CityValidator | None = None,
        simulation_backend: SimulationBackend | None = None,
    ) -> None:
        self.planner = planner or BaselineCityPlanner()
        self.validator = validator or CityValidator()
        self.simulation_backend = simulation_backend or ManifestBackend()

    def run(self, spec: CitySpec, output_dir: str | Path) -> GenerationResult:
        destination = Path(output_dir)
        destination.mkdir(parents=True, exist_ok=True)

        city = self.planner.plan(spec)
        report = self.validator.validate(city)
        report_path = save_json(report.to_dict(), destination / "validation_report.json")
        artifacts = [report_path]

        if report.ok:
            artifacts.extend(self.simulation_backend.compile(city, destination))
            artifacts.append(save_json(self._summary(city), destination / "summary.json"))

        return GenerationResult(city=city, validation=report, artifacts=artifacts)

    @staticmethod
    def _summary(city: City) -> dict:
        buildings = list(city.iter_buildings())
        building_floor_counts = [len(building.floors) for building in buildings]
        floor_count_histogram = Counter(building_floor_counts)
        highrise_massing_variants = Counter(
            building.metadata.get("highrise", {}).get("massing_variant")
            for building in buildings
            if building.metadata.get("highrise", {}).get("enabled")
        )
        vertical_zone_counts = [
            len(building.metadata.get("vertical_zoning", {}).get("zones", []))
            for building in buildings
        ]
        vertical_zone_roles = Counter(
            zone.get("role")
            for building in buildings
            for zone in building.metadata.get("vertical_zoning", {}).get("zones", [])
            if zone.get("role")
        )
        floors = list(city.iter_floors())
        rooms = list(city.iter_rooms())
        objects = list(city.iter_objects())
        program = city.world_program
        return {
            "city_id": city.id,
            "schema_version": city.schema_version,
            "district_count": len(city.districts),
            "junction_count": len(city.road_network.junctions),
            "road_segment_count": len(city.road_network.segments),
            "building_count": len(buildings),
            "floor_count": len(floors),
            "room_count_including_corridors": len(rooms),
            "interior_object_count": len(objects),
            "furnished_room_count": sum(bool(room.object_ids) for room in rooms),
            "max_building_floor_count": max(
                building_floor_counts, default=0
            ),
            "unique_building_floor_count": len(floor_count_histogram),
            "dominant_building_floor_count_share": round(
                max(floor_count_histogram.values(), default=0)
                / max(1, len(buildings)),
                6,
            ),
            "building_floor_count_histogram": {
                str(floors): count
                for floors, count in sorted(floor_count_histogram.items())
            },
            "building_vertical_zone_count": sum(vertical_zone_counts),
            "unique_building_vertical_zone_count": len(
                set(vertical_zone_counts)
            ),
            "building_vertical_zone_count_histogram": {
                str(zones): count
                for zones, count in sorted(Counter(vertical_zone_counts).items())
            },
            "vertical_zone_role_histogram": dict(sorted(vertical_zone_roles.items())),
            "highrise_special_zone_building_count": sum(
                any(
                    zone.get("role") in {"amenity", "refuge", "service", "mechanical"}
                    for zone in building.metadata.get("vertical_zoning", {}).get("zones", [])
                )
                for building in buildings
            ),
            "highrise_building_count": sum(
                bool(building.metadata.get("highrise", {}).get("enabled"))
                for building in buildings
            ),
            "planned_highrise_building_count": sum(
                bool(building.metadata.get("height_contract", {}).get("highrise"))
                for building in buildings
            ),
            "highrise_massing_variant_histogram": dict(
                sorted(highrise_massing_variants.items())
            ),
            "strict_street_aligned_building_count": sum(
                bool(
                    building.metadata.get("orientation_contract", {}).get(
                        "strict_alignment"
                    )
                )
                for building in buildings
            ),
            "contextually_rotated_building_count": sum(
                abs(
                    float(
                        building.metadata.get("orientation_contract", {}).get(
                            "offset_deg", 0.0
                        )
                    )
                )
                > 1e-9
                for building in buildings
            ),
            "landmark_building_count": sum(
                bool(building.metadata.get("height_contract", {}).get("landmark"))
                for building in buildings
            ),
            "world_node_count": len(program.nodes),
            "contract_count": len(program.contracts),
            "relation_count": len(program.relations),
            "artifact_count": len(program.artifacts),
            "provenance_count": len(program.provenance),
            "interactive_door_count": sum(
                1 for floor in floors for door in floor.doors if door.interactive
            ),
        }
