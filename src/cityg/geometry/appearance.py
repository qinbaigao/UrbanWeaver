"""Facade-language geometry helpers, shared by entrance and opening placement.

All details are non-colliding visual relief on the validated shell. No new
roof/room geometry is implied. Plans without v1 appearance retain legacy output.
"""
from dataclasses import replace

from cityg.architecture import appearance_for_building


def facade_material_style(building, style):
    family = appearance_for_building(building).get("material_family")
    materials = {
        "brick": ("residential_brick", "facade_frame_cream", "facade_accent_brick"),
        "plaster": ("residential_facade", "facade_frame_light", "facade_accent_warm"),
        "stone": ("civic_limestone", "facade_frame_limestone", "facade_accent_bronze"),
        "metal": ("industrial_light", "facade_frame_silver", "facade_accent_metal"),
        "glass": ("commercial_glass", "facade_frame_dark", "facade_accent_blue"),
    }.get(family)
    return replace(style, wall_material=materials[0], frame_material=materials[1],
                   accent_material=materials[2]) if materials else style


def face_role(building, side):
    primary = building.metadata.get("entrance_side", "west")
    opposite = {"west": "east", "east": "west", "north": "south", "south": "north"}
    return "primary" if side == primary else "service" if side == opposite.get(primary) else "secondary"


def facade_style_for_face(building, style, side):
    plan = appearance_for_building(building)
    if not plan:
        return style
    language = plan["language"]
    values = {
        "framed_grid": dict(window_ratio=.68, window_height_ratio=.60, frame_width_m=.12),
        "horizontal_ribbon": dict(window_ratio=.90, window_height_ratio=.43, frame_width_m=.06),
        "vertical_piers": dict(window_ratio=.49, window_height_ratio=.76, sill_height_m=.40),
        "paired_windows": dict(window_ratio=.56, window_height_ratio=.62, frame_width_m=.09),
        "shaded_bays": dict(window_ratio=.64, window_height_ratio=.57, frame_width_m=.10),
        "solid_punched": dict(window_ratio=.43, window_height_ratio=.48, frame_width_m=.14),
    }[language]
    factor = {"horizontal_ribbon": 1.22, "paired_windows": .90,
              "solid_punched": 1.12}.get(language, 1.0)
    role = face_role(building, side)
    if role == "service":
        factor *= 1.25
        values = {**values, "window_ratio": values["window_ratio"] * .82}
    return replace(style, **values,
                   bay_width_m=style.bay_width_m * factor * plan["articulation_scale"],
                   vertical_fins=False,
                   balcony_side=building.metadata.get("entrance_side", "west"))


def bay_tangent(building, start, spacing, index, count):
    """Paired rhythm, preserving all openings inside their own safe bay cells."""
    plan = appearance_for_building(building)
    offset = 0.0
    if plan.get("language") == "paired_windows":
        # The last bay in an odd-length run remains centered.
        if index % 2 == 0 and index + 1 < count:
            offset = .12
        elif index % 2:
            offset = -.12
    return start + spacing * (index + .5 + offset)


class FacadeAppearanceCompilerMixin:
    def _compile_appearance_bay(self, building, floor, side, tangent, boundary,
                                normal, swapped, frame, spacing, window_width,
                                window_height, center_z, style, bay_index,
                                metadata, scene):
        plan = appearance_for_building(building)
        if not plan:
            return
        language = plan["language"]
        common = (building, floor, side)

        def detail(suffix, x, width, height, z, depth, outward=.06):
            self._add_facade_box(
                *common, x, boundary, normal, swapped, frame, width, height, z,
                style.accent_material, "facade_language_detail",
                f"bay_{bay_index:02d}_language_{suffix}", metadata, scene,
                outward_offset=outward, depth=depth)

        if language == "shaded_bays" and face_role(building, side) != "service":
            # Above the opening, not across its glazing or entrance.
            z = min(floor.elevation_m + floor.height_m - .12,
                    center_z + window_height / 2 + .12)
            detail("hood", tangent, min(spacing * .94, window_width + .32), .13, z, .48, .25)
        elif language == "vertical_piers":
            # Stay within the bay cell so corner strips cannot overshoot.
            detail("pier", tangent - spacing * .43, min(.20, spacing * .08),
                   floor.height_m * .92, floor.elevation_m + floor.height_m / 2, .20, .12)
        elif language == "horizontal_ribbon":
            detail("spandrel", tangent, spacing * .99, .26,
                   floor.elevation_m + .24, .10)
        elif language == "solid_punched":
            detail("sill", tangent, min(spacing * .90, window_width + .28), .14,
                   center_z - window_height / 2 - .09, .20, .12)
        elif language == "framed_grid":
            detail("beam", tangent, spacing * .98, .13,
                   floor.elevation_m + floor.height_m - .10, .12)
