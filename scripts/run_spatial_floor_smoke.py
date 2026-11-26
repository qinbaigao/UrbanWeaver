"""Three controlled floor-layout examples; optional real Building Floor Agent.

Fixed 24x22m floor plates isolate topology changes from city/massing variation.
No asset generation, VLM review or robot experiment; furniture is procedural.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

from cityg.agents.building_floor import BuildingFloorAgent
from cityg.geometry import GeometryCompiler, GeometryValidator
from cityg.planning.programmed import ProgrammedCityPlanner
from cityg.planning.programs import (
    UrbanProgram, BuildingProgram, BuildingProfile, FloorProgram, FloorProfile,
    FloorArchetype, HierarchicalProgram,
)
from cityg.planning.spatial_program import FloorSpatialProgram, SpaceRequirement
from cityg.schemas import Bounds2D, CitySpec, ZoneSpec
from cityg.serialization import save_json
from cityg.services import OpenUSDBackend, OpenAICompatibleService
from cityg.services.interfaces import ModelEndpoint
from cityg.validation import CityValidator
from cityg.viewer import export_portable_viewer


class ControlledPlatePlanner(ProgrammedCityPlanner):
    def _select_building_archetype(self, **kwargs):
        # The fixture deliberately isolates rectangular interiors from wing
        # clipping. Do not change the production building selection policy.
        selection = super()._select_building_archetype(**kwargs)
        return replace(selection, archetype=replace(selection.archetype,
                       massing_style="bar", massing_parameters=()))

    @staticmethod
    def _layout_footprint(spec, rng, index, function, parcel_bounds, entrance_side):
        inner = parcel_bounds.inset(spec.parcel_setback_m)
        p = inner.center
        x = inner.min_x if entrance_side == "west" else inner.max_x-24 if entrance_side == "east" else p.x-12
        y = inner.min_y if entrance_side == "south" else inner.max_y-22 if entrance_side == "north" else p.y-11
        box = Bounds2D(x, y, x+24, y+22)
        if not inner.contains_bounds(box):
            raise ValueError("Smoke-test parcel too small for controlled plate")
        return box


def example_programs():
    residential = []
    for i in range(4):
        group = f"home_{i}"
        residential.extend([
            SpaceRequirement(group+"_living", "living_room", 45, 20, 100, group=group),
            SpaceRequirement(group+"_bed", "bedroom", 28, 12, 70, group=group,
                             access_via=group+"_living", daylight="required"),
            SpaceRequirement(group+"_bath", "bathroom", 20, 8, 65, group=group,
                             access_via=group+"_living", daylight="none"),
        ])
    office = []
    for i in range(2):
        group = f"department_{i}"
        office.append(SpaceRequirement(group, "open_office", 110, 50, 250,
                                       capacity=12, group=group, enclosure="open"))
        for j, (function, area) in enumerate((("meeting_room", 45), ("office", 35), ("break_room", 30))):
            office.append(SpaceRequirement(f"{group}_support_{j}", function, area, 15, 90,
                                           group=group, access_via=group))
    public = [SpaceRequirement(f"space_{i}", fn, area, 18, 150) for i,(fn,area) in enumerate([
        ("office", 24), ("waiting_room", 42), ("service_hall", 65),
        ("storage", 32), ("office", 50), ("service_hall", 75)])]
    return {
        "residential": FloorSpatialProgram("residential_clusters", tuple(residential)),
        "commercial": FloorSpatialProgram("open_office", tuple(office)),
        "public_service": FloorSpatialProgram("double_loaded", tuple(public)),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--online", action="store_true", help="Personalize one commercial building with local vLLM")
    args = parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        parser.error("Output must be absent or empty")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    programs = example_programs()
    profiles = []
    for function, spatial in programs.items():
        cycle = tuple(dict.fromkeys(s.function for s in spatial.spaces))
        archetypes = tuple(FloorArchetype(role, len(spatial.spaces), 2, 24, 40, 2.4,
                                         cycle, max_room_aspect_ratio=2.8, spatial_program=spatial)
                           for role in ("ground", "typical", "top"))
        profiles.append(FloorProfile(function, "double_loaded_corridor", .14, cycle, archetypes))
    program = HierarchicalProgram(
        UrbanProgram(("zone_00", "zone_01", "zone_02")),
        BuildingProgram(tuple(BuildingProfile(fn, "minimum", "west", proto) for fn,proto in (
            ("residential", "residential_slab"), ("commercial", "commercial_tower"), ("public_service", "public_civic")))),
        FloorProgram(tuple(profiles)),
    )
    spec = CitySpec(name="spatial_floor_showcase", width_m=240, depth_m=200,
                    building_count=3, min_floors=2, max_floors=2, seed=19,
                    room_count_strategy="adaptive", open_space_ratio=.1,
                    zones=tuple(ZoneSpec(fn, fn, 1) for fn in programs))
    planner = ControlledPlatePlanner(program)
    city = planner.plan(spec)
    if args.online:
        building = next(b for b in city.iter_buildings() if b.function == "commercial")
        service = OpenAICompatibleService(ModelEndpoint(
            base_url="http://127.0.0.1:8000/v1", model="cityg-llm", max_tokens=10000,
            timeout_s=240, temperature=.25, seed=19))
        print("Calling actual BuildingFloorAgent for one commercial building", flush=True)
        try:
            result = BuildingFloorAgent(service, model_id="cityg-llm", max_calls=4).plan(
                building, program.floor.for_function("commercial"), spec)
            save_json(result.trace_dict(), output / "building_floor_trace.json")
            save_json(result.program, output / "building_floor_program.json")
            if not all(z.spatial_program for z in result.program.profile.vertical_zones):
                raise ValueError("Agent returned no spatial program for one or more zones")
            city = ControlledPlatePlanner(program, floor_program_overrides={building.id: result.program.profile}).plan(spec)
        except Exception as exc:
            save_json({"error": str(exc), "attempts": getattr(exc, "attempts", ())}, output / "agent_failure.json")
            raise
    compiler = GeometryCompiler()
    scene = compiler.compile(city)
    city_report = CityValidator().validate(city)
    geometry_report = GeometryValidator().validate(city, scene)
    floors = [{"building_id": b.id, "function": b.function, "floor_id": f.id,
               "spatial_layout": f.metadata.get("spatial_layout")} for b in city.iter_buildings() for f in b.floors]
    report = {"scope": "controlled_floor_integration", "llm_used": args.online, "vlm_used": False,
              "city_validation": city_report.to_dict(), "geometry_validation": geometry_report.to_dict(),
              "floors": floors,
              "ok": city_report.ok and geometry_report.ok and all((f["spatial_layout"] or {}).get("status")=="accepted" for f in floors)}
    save_json(report, output / "report.json")
    if not report["ok"]:
        raise RuntimeError("Integration validation failed; inspect report.json")
    OpenUSDBackend(compiler).compile(city, output / "scene", _scene_override=scene)
    save_json(city_report.to_dict(), output / "scene/validation_report.json")
    export_portable_viewer(output / "scene", output / "viewer")
    views = [{"view_id": b.function, "kind": "floor_plan", "mode": "floor_plan",
              "target_entity_ids": [b.id, b.floors[1].id], "floor_camera_preset": "top",
              "render_profile": "review", "appearance": "semantic", "auto_cutaway": True}
             for b in city.iter_buildings()]
    save_json({"selected_views": views}, output / "observation.json")
    print(f"Accepted {len(floors)} floors; portable Viewer: {output / 'viewer'}", flush=True)


if __name__ == "__main__":
    main()
