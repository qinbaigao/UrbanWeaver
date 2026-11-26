"""JSON serialization for CityG's canonical dataclasses."""

from __future__ import annotations

import json
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any

from cityg.schemas import (
    Artifact,
    Bounds2D,
    Building,
    Bridge,
    River,
    CCWP_SCHEMA_VERSION,
    City,
    Contract,
    District,
    Door,
    Floor,
    GeometryBudget,
    InteractionState,
    Intent,
    InteriorObject,
    Junction,
    Parcel,
    Point2D,
    ProvenanceRecord,
    Relation,
    RoadNetwork,
    RoadSegment,
    Room,
    VerticalConnector,
    WorldNode,
    WorldProgram,
)
from cityg.migration import LEGACY_SCHEMA_VERSION, migrate_legacy_city, require_supported_version
from cityg.naming import annotate_city_identities


def to_primitive(value: Any) -> Any:
    if is_dataclass(value):
        return {field.name: to_primitive(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, dict):
        return {str(key): to_primitive(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_primitive(item) for item in value]
    return value


def save_json(value: Any, path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(to_primitive(value), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return destination


def load_city(path: str | Path) -> City:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return city_from_dict(data)


def _point(data: dict[str, Any]) -> Point2D:
    return Point2D(x=float(data["x"]), y=float(data["y"]))


def _bounds(data: dict[str, Any]) -> Bounds2D:
    return Bounds2D(
        min_x=float(data["min_x"]),
        min_y=float(data["min_y"]),
        max_x=float(data["max_x"]),
        max_y=float(data["max_y"]),
    )


def city_from_dict(data: dict[str, Any]) -> City:
    source_version = str(data.get("schema_version", LEGACY_SCHEMA_VERSION))
    require_supported_version(source_version)
    road_data = data["road_network"]
    network = RoadNetwork(
        junctions=[Junction(item["id"], _point(item["position"])) for item in road_data["junctions"]],
        segments=[
            RoadSegment(
                id=item["id"],
                start_junction_id=item["start_junction_id"],
                end_junction_id=item["end_junction_id"],
                centerline=tuple(_point(point) for point in item["centerline"]),
                road_class=item.get("road_class", "local"),
                lane_count=int(item.get("lane_count", 2)),
                width_m=float(item.get("width_m", 12.0)),
                sidewalk_width_m=float(item.get("sidewalk_width_m", 2.5)),
                speed_limit_kph=float(item.get("speed_limit_kph", 30.0)),
                directionality=item.get("directionality", "bidirectional"),
                median_width_m=float(item.get("median_width_m", 0.0)),
                parking_allowed=bool(item.get("parking_allowed", True)),
                bike_lane=bool(item.get("bike_lane", False)),
                bus_lane=bool(item.get("bus_lane", False)),
                turn_lane=bool(item.get("turn_lane", False)),
                intersection_control=item.get("intersection_control", "priority"),
            )
            for item in road_data["segments"]
        ],
    )
    city = City(
        id=data["id"],
        name=data["name"],
        bounds=_bounds(data["bounds"]),
        road_network=network,
        districts=[_district(item) for item in data.get("districts", [])],
        rivers=[River(id=item["id"], name=item.get("name", item["id"]),
                      centerline=tuple(_point(p) for p in item["centerline"]),
                      **{key: float(item[key]) for key in ("width_m", "bank_width_m", "setback_m",
                         "water_elevation_m", "bed_elevation_m") if key in item})
                for item in data.get("rivers", [])],
        bridges=[Bridge(**item) for item in data.get("bridges", [])],
        coordinate_system=data.get("coordinate_system", "right_handed_z_up_meters"),
        schema_version=source_version,
        metadata=data.get("metadata", {}),
        world_program=(
            _world_program(data["world_program"])
            if "world_program" in data
            else WorldProgram()
        ),
    )
    if source_version == LEGACY_SCHEMA_VERSION:
        return migrate_legacy_city(city, source_version)
    if source_version == CCWP_SCHEMA_VERSION and "world_program" not in data:
        raise ValueError("Schema 0.2.0 manifest is missing world_program")
    # Current manifests produced before the naming upgrade remain loadable;
    # enrich them in memory so a subsequent save also persists the registry.
    annotate_city_identities(city)
    return city


def _district(data: dict[str, Any]) -> District:
    return District(
        id=data["id"],
        name=data["name"],
        function=data["function"],
        bounds=_bounds(data["bounds"]),
        parcels=[_parcel(item) for item in data.get("parcels", [])],
    )


def _parcel(data: dict[str, Any]) -> Parcel:
    return Parcel(
        id=data["id"],
        bounds=_bounds(data["bounds"]),
        buildings=[_building(item) for item in data.get("buildings", [])],
        boundary=tuple(_point(p) for p in data.get("boundary", [])),
        holes=tuple(tuple(_point(p) for p in ring) for ring in data.get("holes", [])),
    )


def _building(data: dict[str, Any]) -> Building:
    return Building(
        id=data["id"],
        name=data["name"],
        function=data["function"],
        footprint=_bounds(data["footprint"]),
        entrance=_point(data["entrance"]),
        floors=[_floor(item) for item in data.get("floors", [])],
        vertical_connectors=[
            VerticalConnector(
                id=item["id"],
                connector_type=item["connector_type"],
                bounds=_bounds(item["bounds"]),
                from_level=int(item["from_level"]),
                to_level=int(item["to_level"]),
                interactive=bool(item.get("interactive", False)),
                metadata=dict(item.get("metadata", {})),
            )
            for item in data.get("vertical_connectors", [])
        ],
        metadata=data.get("metadata", {}),
    )


def _floor(data: dict[str, Any]) -> Floor:
    return Floor(
        id=data["id"],
        level=int(data["level"]),
        elevation_m=float(data["elevation_m"]),
        height_m=float(data["height_m"]),
        rooms=[
            Room(
                id=item["id"],
                name=item["name"],
                function=item["function"],
                bounds=_bounds(item["bounds"]),
                height_m=float(item.get("height_m", 3.0)),
                object_ids=list(item.get("object_ids", [])),
                metadata=dict(item.get("metadata", {})),
            )
            for item in data.get("rooms", [])
        ],
        doors=[
            Door(
                id=item["id"],
                room_a_id=item["room_a_id"],
                room_b_id=item.get("room_b_id"),
                position=_point(item["position"]),
                width_m=float(item.get("width_m", 0.9)),
                door_type=item.get("door_type", "interior"),
                interactive=bool(item.get("interactive", True)),
            )
            for item in data.get("doors", [])
        ],
        objects=[
            InteriorObject(
                id=item["id"],
                room_id=item["room_id"],
                category=item["category"],
                asset_id=item.get("asset_id", f"procedural::{item['category']}::v1"),
                position=_point(item["position"]),
                width_m=float(item["width_m"]),
                depth_m=float(item["depth_m"]),
                height_m=float(item["height_m"]),
                rotation_deg=float(item.get("rotation_deg", 0.0)),
                interactive=bool(item.get("interactive", False)),
                metadata=dict(item.get("metadata", {})),
            )
            for item in data.get("objects", [])
        ],
        metadata=dict(data.get("metadata", {})),
    )


def _world_program(data: dict[str, Any]) -> WorldProgram:
    return WorldProgram(
        nodes=[
            WorldNode(
                entity_id=item["entity_id"],
                entity_type=item["entity_type"],
                parent_id=item.get("parent_id"),
                intent=Intent(
                    description=item["intent"]["description"],
                    function=item["intent"]["function"],
                    tags=list(item["intent"].get("tags", [])),
                ),
                geometry=GeometryBudget(**item.get("geometry", {})),
                contract_ids=list(item.get("contract_ids", [])),
                relation_ids=list(item.get("relation_ids", [])),
                artifact_ids=list(item.get("artifact_ids", [])),
                provenance_ids=list(item.get("provenance_ids", [])),
                state=InteractionState(**item.get("state", {})),
                status=item.get("status", "draft"),
                version=int(item.get("version", 1)),
                locked=bool(item.get("locked", False)),
            )
            for item in data.get("nodes", [])
        ],
        contracts=[
            Contract(
                id=item["id"],
                kind=item["kind"],
                scope_id=item["scope_id"],
                subject_ids=list(item.get("subject_ids", [])),
                description=item.get("description", ""),
                parameters=dict(item.get("parameters", {})),
                inherited_from=item.get("inherited_from"),
                severity=item.get("severity", "error"),
            )
            for item in data.get("contracts", [])
        ],
        relations=[
            Relation(
                id=item["id"],
                relation_type=item["relation_type"],
                source_id=item["source_id"],
                target_ids=list(item.get("target_ids", [])),
                properties=dict(item.get("properties", {})),
            )
            for item in data.get("relations", [])
        ],
        artifacts=[
            Artifact(
                id=item["id"],
                owner_id=item["owner_id"],
                artifact_type=item["artifact_type"],
                uri=item["uri"],
                media_type=item.get("media_type", "application/octet-stream"),
                checksum=item.get("checksum"),
                status=item.get("status", "planned"),
                metadata=dict(item.get("metadata", {})),
            )
            for item in data.get("artifacts", [])
        ],
        provenance=[
            ProvenanceRecord(
                id=item["id"],
                entity_id=item["entity_id"],
                producer=item["producer"],
                operation=item["operation"],
                seed=item.get("seed"),
                model_id=item.get("model_id"),
                prompt_hash=item.get("prompt_hash"),
                parent_record_ids=list(item.get("parent_record_ids", [])),
                metadata=dict(item.get("metadata", {})),
            )
            for item in data.get("provenance", [])
        ],
    )
