"""A small support-scoped object language; no guessed world-space elevations.

These are static visual subentities, not floor furniture or dynamic rigid bodies.
The compiler resolves support member IDs to *realized* surfaces after massing.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class SurfaceItemSpec:
    size: tuple[float, float, float]
    material: str


SURFACE_CATALOG = {
    "monitor": SurfaceItemSpec((.46, .19, .38), "furniture_metal"),
    "keyboard": SurfaceItemSpec((.38, .14, .025), "furniture_metal"),
    "desk_lamp": SurfaceItemSpec((.16, .16, .32), "ceramic"),
    "book_stack": SurfaceItemSpec((.23, .17, .08), "furniture_blue"),
    "book": SurfaceItemSpec((.045, .18, .24), "furniture_warm"),
    "file_box": SurfaceItemSpec((.12, .24, .28), "furniture_wood"),
    "cup": SurfaceItemSpec((.09, .09, .11), "ceramic"),
    "small_plant": SurfaceItemSpec((.16, .16, .26), "furniture_fabric"),
    "tray": SurfaceItemSpec((.28, .20, .035), "furniture_wood"),
    "notebook": SurfaceItemSpec((.21, .30, .02), "furniture_warm"),
    "vase": SurfaceItemSpec((.13, .13, .25), "ceramic"),
    "pen": SurfaceItemSpec((.01, .15, .01), "furniture_blue"),
    "pencil": SurfaceItemSpec((.008, .18, .008), "furniture_warm"),
    "pencil_cup": SurfaceItemSpec((.10, .10, .11), "furniture_metal"),
    "eraser": SurfaceItemSpec((.02, .05, .012), "ceramic"),
}

SURFACE_ITEMS_SCHEMA = {"type": "array", "maxItems": 32, "items": {
    "type": "object", "additionalProperties": False,
    "properties": {
        "id": {"type": "string"}, "support_member_id": {"type": "string"},
        "surface": {"type": "string", "enum": ["top", "shelves"]},
        "category": {"type": "string", "enum": list(SURFACE_CATALOG)},
        "count": {"type": "integer", "minimum": 1, "maximum": 8},
        "placement": {"type": "string", "enum": ["front", "back", "left", "right", "spread"]},
    }, "required": ["id", "support_member_id", "surface", "category", "count", "placement"],
}}


def validate_surface_items(items, groups, key_validator):
    if not isinstance(items, (tuple, list)) or len(items) > 32:
        raise ValueError("surface_items must contain at most 32 requests")
    members = {i["id"] for g in groups for i in [g["anchor"], *g["members"]]}
    ids, total = set(), 0
    for item in items:
        if not isinstance(item, dict) or set(item) != set(SURFACE_ITEMS_SCHEMA["items"]["properties"]):
            raise ValueError("invalid surface item fields")
        key_validator(item["id"])
        if item["id"] in ids or item["support_member_id"] not in members:
            raise ValueError("surface item needs unique ID and an existing furniture member as support")
        ids.add(item["id"])
        if (item["surface"] not in ("top", "shelves") or item["category"] not in SURFACE_CATALOG
                or item["placement"] not in ("front", "back", "left", "right", "spread")):
            raise ValueError("unsupported surface item/category/placement")
        if type(item["count"]) is not int or not 1 <= item["count"] <= 8:
            raise ValueError("surface item count must be 1..8")
        total += item["count"]
    if total > 48:
        raise ValueError("surface items exceed 48 instances per room")


def support_options(catalog):
    """Disclose procedural capabilities; GLBs still require reviewed surfaces."""
    return {k: (["shelves"] if s.proxy_style == "rack" else ["top"])
            for k, s in catalog.items() if s.proxy_style in {"rack", "table", "counter"}
            or (s.proxy_style == "cabinet" and s.height_m <= 1.3)}
