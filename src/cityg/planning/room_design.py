"""Bounded room design language: zones, instance-bound groups and appearance."""
from __future__ import annotations

from dataclasses import dataclass, asdict
import math
import re
from cityg.planning.furnishing_brief import BRIEF_SCHEMA, validate_brief
from cityg.planning.surface_items import SURFACE_ITEMS_SCHEMA, validate_surface_items
from cityg.planning.room_regions import validate_uv

POSITIONS = ("north", "south", "east", "west", "center")
PALETTES = {
    "warm": {"floor": (.52, .37, .23), "wall": (.86, .81, .71), "accent": (.25, .40, .34)},
    "minimal": {"floor": (.65, .64, .60), "wall": (.88, .89, .87), "accent": (.24, .33, .43)},
    "industrial": {"floor": (.38, .39, .40), "wall": (.62, .60, .56), "accent": (.49, .28, .15)},
}

def _object(properties, required=None):
    return {"type": "object", "additionalProperties": False, "properties": properties,
            "required": list(properties) if required is None else required}

ITEM_SCHEMA = _object({"id": {"type":"string"}, "category": {"type":"string"}})
MEMBER_SCHEMA = _object({**ITEM_SCHEMA["properties"], "side":{"type":"string","enum":["front","back","left","right"]},
                         "slot":{"type":"number","minimum":-2,"maximum":2,"multipleOf":0.5},
                         "gap_m":{"type":"number","minimum":.15,"maximum":1.5}, "face_anchor":{"type":"boolean"}})
PLACEMENT_SCHEMA = _object({
    "mode": {"type":"string", "enum":["auto","wall","free"]},
    "wall": {"type":"string", "enum":["auto",*POSITIONS[:4]]},
    "contact": {"type":"string", "enum":["auto","back","head"]},
    "max_gap_m": {"type":"number", "minimum":.04, "maximum":.35},
    "facing": {"type":"string", "enum":["north","south","east","west"]},
}, required=["mode","wall","contact","max_gap_m"])
GROUP_RELATION_SCHEMA = _object({
    "subject": {"type":"string"}, "target": {"type":"string"},
    "relation": {"type":"string", "enum":["near","faces","aligned"]},
    "min_distance_m": {"type":"number", "minimum":0, "maximum":15},
    "max_distance_m": {"type":"number", "minimum":0, "maximum":30},
    "required": {"type":"boolean"},
})
DESIGN_SCHEMA = _object({
    "intent":{"type":"string","maxLength":500},
    "palette":{"type":"string","enum":list(PALETTES)},
    "zones":{"type":"array","minItems":1,"maxItems":8,"items":_object({
        "id":{"type":"string"},"purpose":{"type":"string"},"position":{"type":"string","enum":list(POSITIONS)},
        "bounds_uv":{"type":"array","minItems":4,"maxItems":4,"items":{"type":"number","minimum":0,"maximum":1}}},
        required=['id','purpose','position'])},
    "reserved_areas":{"type":"array","maxItems":8,"items":_object({
        "id":{"type":"string"},"purpose":{"type":"string"},
        "bounds_uv":{"type":"array","minItems":4,"maxItems":4,"items":{"type":"number","minimum":0,"maximum":1}},
        "min_width_m":{"type":"number","minimum":.55,"maximum":6}})},
    "groups":{"type":"array","minItems":1,"maxItems":16,"items":_object({
        "id":{"type":"string"},"zone":{"type":"string"},"anchor":ITEM_SCHEMA,
        "members":{"type":"array","maxItems":8,"items":MEMBER_SCHEMA},
        "placement": PLACEMENT_SCHEMA}, required=["id","zone","anchor","members"])},
    "wall_art":{"type":"boolean"}, "tabletop":{"type":"boolean"},
    "group_relations":{"type":"array","maxItems":16,"items":GROUP_RELATION_SCHEMA},
    # vLLM grammar backends may not implement uniqueItems. validate() below
    # still rejects duplicate group IDs; do not delegate this invariant to decoding.
    "protected_groups":{"type":"array","maxItems":16,"items":{"type":"string"}},
    "furnishing_brief": BRIEF_SCHEMA,
    "surface_items": SURFACE_ITEMS_SCHEMA,
}, required=["intent","palette","zones","groups","wall_art","tabletop"])


@dataclass(frozen=True)
class RoomDesign:
    intent: str
    palette: str
    zones: tuple[dict, ...]
    groups: tuple[dict, ...]
    wall_art: bool = False
    tabletop: bool = False
    group_relations: tuple[dict, ...] = ()
    protected_groups: tuple[str, ...] = ()
    furnishing_brief: dict | None = None
    surface_items: tuple[dict, ...] = ()
    reserved_areas: tuple[dict, ...] = ()

    @classmethod
    def from_dict(cls, value, catalog):
        if value is None:
            return None
        if not isinstance(value, dict) or set(value)-set(cls.__dataclass_fields__):
            raise ValueError("invalid room design fields")
        try:
            result = cls(**{**value, "zones":tuple(value["zones"]),"groups":tuple(value["groups"]),
                           "group_relations":tuple(value.get("group_relations", ())),
                           "surface_items":tuple(value.get("surface_items", ())),
                           "reserved_areas":tuple(value.get("reserved_areas", ())),
                           "protected_groups":tuple(value.get("protected_groups", ()))})
        except (KeyError, TypeError) as exc:
            raise ValueError("room design needs intent, palette, zones and groups") from exc
        result.validate(catalog)
        return result

    def validate(self, catalog):
        def key(value):
            if not isinstance(value, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,47}", value):
                raise ValueError("room design IDs must be safe local identifiers")
        if not isinstance(self.intent,str) or len(self.intent)>500 or self.palette not in PALETTES:
            raise ValueError("invalid room design intent/palette")
        if type(self.wall_art) is not bool or type(self.tabletop) is not bool:
            raise ValueError("design.wall_art and design.tabletop must be JSON booleans true/false, "
                             "NOT arrays, objects or strings; use false when no decoration is wanted")
        if not 1<=len(self.zones)<=8 or not 1<=len(self.groups)<=16:
            raise ValueError("room design needs 1..8 zones and 1..16 groups")
        zones, ids, groups = set(), set(), set()
        for z in self.zones:
            if (not isinstance(z,dict) or set(z)-{'id','purpose','position','bounds_uv'}
                    or not {'id','purpose','position'} <= set(z)):
                raise ValueError("zone requires id, purpose, position")
            key(z["id"])
            if z["id"] in zones or z["position"] not in POSITIONS or not isinstance(z["purpose"],str):
                raise ValueError("invalid/duplicate room zone")
            zones.add(z["id"])
            if 'bounds_uv' in z:
                validate_uv(z['bounds_uv'])
        if not isinstance(self.reserved_areas, (list, tuple)) or len(self.reserved_areas)>8:
            raise ValueError('At most eight reserved circulation areas are supported')
        reserved_ids=set()
        for area in self.reserved_areas:
            if not isinstance(area,dict) or set(area)!={'id','purpose','bounds_uv','min_width_m'}:
                raise ValueError('Invalid reserved area fields')
            key(area['id'])
            if area['id'] in reserved_ids or not isinstance(area['purpose'],str) or not area['purpose'].strip():
                raise ValueError('Reserved areas need unique IDs and purposes')
            reserved_ids.add(area['id'])
            validate_uv(area['bounds_uv'])
            width=area['min_width_m']
            if type(width) not in (int,float) or not math.isfinite(width) or not .55<=width<=6:
                raise ValueError('Invalid reserved minimum width')
        for g in self.groups:
            if (not isinstance(g,dict) or set(g)-{"id","zone","anchor","members","placement"}
                    or not {"id","zone","anchor","members"}<=set(g)):
                raise ValueError("group requires id, zone, anchor, members")
            key(g["id"])
            if g["id"] in groups:
                raise ValueError(f"duplicate group id {g['id']!r}; use distinct group IDs")
            if not isinstance(g['zone'], str) or g["zone"] not in zones:
                raise ValueError(f"group {g['id']!r} references undeclared zone {g['zone']!r}; "
                                 f"declared zone IDs: {sorted(zones)!r}. Use a declared ID or "
                                 "explicitly define the intended zone in design.zones")
            if not isinstance(g["members"],(list,tuple)) or len(g["members"])>8:
                raise ValueError(f"group {g['id']!r} members must be a list with at most 8 entries")
            groups.add(g["id"])
            if "placement" in g:
                p = g["placement"]
                if (not isinstance(p,dict) or set(p)-set(PLACEMENT_SCHEMA["properties"])
                        or not set(PLACEMENT_SCHEMA['required']) <= set(p)):
                    raise ValueError("placement requires mode, wall, contact, max_gap_m")
                if 'facing' in p and p['facing'] not in POSITIONS[:4]:
                    raise ValueError('invalid semantic facing direction')
                if p["mode"] not in ("auto","wall","free") or p["wall"] not in ("auto",*POSITIONS[:4]) or p["contact"] not in ("auto","back","head"):
                    raise ValueError("invalid wall placement policy")
                gap=p["max_gap_m"]
                if type(gap) not in (int,float) or not math.isfinite(gap) or not .04<=gap<=.35:
                    raise ValueError("invalid wall contact gap")
            for i,item in enumerate([g["anchor"], *g["members"]]):
                fields={"id","category"} if i==0 else {"id","category","side","slot","gap_m","face_anchor"}
                if not isinstance(item,dict) or set(item)!=fields:
                    raise ValueError("invalid group member fields")
                key(item["id"])
                if i and item["id"] == g["anchor"]["id"]:
                    raise ValueError(f"anchor {item['id']!r} in group {g['id']!r} is already instantiated; "
                                     "remove this duplicate member, do not rename it into a second object; "
                                     "a singleton group has members:[]")
                if item["id"] in ids:
                    raise ValueError(f"duplicate furniture ID {item['id']!r} in group {g['id']!r}; "
                                     "anchor/member IDs must be unique across the entire room, not just one group. "
                                     "Each group anchor creates a physical object, not a reference to another group. "
                                     "If these groups describe the SAME table, merge its chairs into ONE table-anchor group; "
                                     "do not rename the repeated anchor into an unintended second table.")
                if item["category"] not in catalog:
                    raise ValueError(f"unsupported furniture category {item['category']!r} on {item['id']!r}; "
                                     f"choose from {sorted(catalog)}; small props belong in surface_items")
                ids.add(item["id"])
                if i:
                    gap=item["gap_m"]
                    slot=item['slot']
                    if (item["side"] not in {"front","back","left","right"} or type(slot) not in (int,float)
                            or not -2<=slot<=2 or slot*2!=int(slot*2)):
                        raise ValueError("invalid member side/slot")
                    if type(gap) not in {int,float} or not math.isfinite(gap) or not .15<=gap<=1.5 or type(item["face_anchor"]) is not bool:
                        raise ValueError("invalid member clearance/facing")
        if len(ids)>32:
            raise ValueError("room design exceeds 32 furniture instances")
        if len(self.group_relations)>16:
            raise ValueError("too many group relations")
        for relation in self.group_relations:
            if not isinstance(relation,dict) or set(relation)!=set(GROUP_RELATION_SCHEMA["properties"]):
                raise ValueError("invalid group relation fields")
            if relation["subject"] not in groups or relation["target"] not in groups or relation["subject"]==relation["target"]:
                raise ValueError("group relation requires two known, distinct groups")
            if relation["relation"] not in ("near","faces","aligned") or type(relation["required"]) is not bool:
                raise ValueError("invalid group relation type")
            lo,hi=relation["min_distance_m"],relation["max_distance_m"]
            if any(type(v) not in (int,float) or not math.isfinite(v) for v in (lo,hi)) or not 0<=lo<=15 or not lo<=hi<=30:
                raise ValueError("invalid group relation distance range")
        if len(set(self.protected_groups))!=len(self.protected_groups) or any(g not in groups for g in self.protected_groups):
            raise ValueError("protected_groups must reference unique existing design groups")
        validate_brief(self.furnishing_brief, catalog, self.groups)
        validate_surface_items(self.surface_items, self.groups, key)

    def to_dict(self):
        return asdict(self)


def group_integrity(before, after):
    """Protect accepted group geometry during legacy object-local repairs.

    Whole-room/group re-solve may deliberately redesign these relations. A legacy
    single-object edit may not detach a chair, drop a member or invalidate a pair.
    """
    by_id = {o.id:o for o in after}
    for old in before:
        anchor_id=old.metadata.get("group_anchor_id")
        if not anchor_id:
            continue
        current, anchor = by_id.get(old.id), by_id.get(anchor_id)
        if current is None or anchor is None:
            return False, "group member or anchor removed"
        old_anchor=next((o for o in before if o.id==anchor_id),None)
        if old_anchor is None:
            return False, "missing group anchor"
        # Until a group-aware repair is requested, preserve pairwise vector and
        # orientation. Translating the entire group is allowed.
        if abs((current.position.x-anchor.position.x)-(old.position.x-old_anchor.position.x))>1e-4 or abs((current.position.y-anchor.position.y)-(old.position.y-old_anchor.position.y))>1e-4:
            return False, "object-local edit would break a furniture group; replan the room/group"
        if (abs((current.rotation_deg-old.rotation_deg+180)%360-180)>1e-4 or current.asset_id!=old.asset_id
                or (current.width_m,current.depth_m,current.height_m)!=(old.width_m,old.depth_m,old.height_m)):
            return False, "group member orientation/asset changed without group revalidation"
    return True, "group relationships preserved"
