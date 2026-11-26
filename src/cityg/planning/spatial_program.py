"""Semantic floor requirements, independent of coordinates and rendering.

An explicit program is optional for backwards compatibility.  Invalid programs
are rejected at the agent boundary; geometrically infeasible ones are reported by
the compiler, never silently presented as fulfilled requirements.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re


FAMILIES = ("double_loaded", "residential_clusters", "open_office")


@dataclass(frozen=True)
class SpaceRequirement:
    key: str
    function: str
    target_area_m2: float
    min_area_m2: float = 6.0
    max_area_m2: float = 500.0
    capacity: int = 1
    group: str = ""
    access_via: str = "circulation"
    daylight: str = "preferred"
    enclosure: str = "closed"
    near_entrance: bool = False
    adjacent_to: tuple[str, ...] = ()
    separate_from: tuple[str, ...] = ()
    merge_with: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, data: dict) -> "SpaceRequirement":
        if not isinstance(data, dict):
            raise ValueError("space requirement must be an object")
        unknown = set(data) - set(cls.__dataclass_fields__)
        if unknown:
            raise ValueError(f"unknown space requirement fields: {sorted(unknown)}")
        values = dict(data)
        for name in ("adjacent_to", "separate_from", "merge_with"):
            raw = values.get(name, ())
            if not isinstance(raw, (list, tuple)) or not all(isinstance(x, str) for x in raw):
                raise ValueError(f"{name} must be an array of space keys")
            values[name] = tuple(raw)
        try:
            return cls(**values)
        except TypeError as exc:
            raise ValueError(f"invalid space requirement: {exc}") from exc


@dataclass(frozen=True)
class FloorSpatialProgram:
    family: str
    spaces: tuple[SpaceRequirement, ...]

    @classmethod
    def from_dict(cls, data: dict | None) -> "FloorSpatialProgram | None":
        if data is None:
            return None
        if not isinstance(data, dict) or set(data) != {"family", "spaces"}:
            raise ValueError("spatial_program requires exactly family and spaces")
        if not isinstance(data["spaces"], (list, tuple)):
            raise ValueError("spatial_program.spaces must be an array")
        result = cls(data["family"], tuple(SpaceRequirement.from_dict(x) for x in data["spaces"]))
        result.validate()
        return result

    def validate(self, allowed_functions=None) -> None:
        if self.family not in FAMILIES or not 1 <= len(self.spaces) <= 32:
            raise ValueError(f"spatial program requires a supported family and 1..32 spaces; family={self.family!r}, allowed={FAMILIES}, count={len(self.spaces)}")
        keys = [s.key for s in self.spaces]
        if not all(isinstance(key, str) for key in keys):
            raise ValueError("space keys must be strings")
        if len(set(keys)) != len(keys):
            raise ValueError("duplicate spatial requirement key")
        by_key = {s.key: s for s in self.spaces}
        for s in self.spaces:
            if not isinstance(s.function, str) or not s.function or s.function == "corridor":
                raise ValueError("functional spaces cannot replace compiler-owned circulation")
            if not isinstance(s.key, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,47}", s.key) or s.key == "circulation":
                raise ValueError("space keys must be safe identifiers, not circulation")
            if not isinstance(s.group, str) or (s.group and not re.fullmatch(r"[a-z][a-z0-9_]{0,47}", s.group)):
                raise ValueError("space group must be a safe identifier")
            if allowed_functions is not None and s.function not in allowed_functions:
                raise ValueError(f"unsupported spatial function: {s.function}")
            values = (s.min_area_m2, s.target_area_m2, s.max_area_m2)
            if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in values):
                raise ValueError("space areas must be finite numbers")
            if not 4 <= s.min_area_m2 <= s.target_area_m2 <= s.max_area_m2 <= 5000:
                raise ValueError(f"space areas require 4 <= min <= target <= max <= 5000; space={s.key}, observed={values}. Set explicit min_area_m2 and max_area_m2 around target_area_m2.")
            if type(s.capacity) is not int or not 0 <= s.capacity <= 500:
                raise ValueError("space capacity must be an integer in [0, 500]")
            if not isinstance(s.access_via, str):
                raise ValueError("access_via must be a space key or the string circulation, never null")
            if not isinstance(s.daylight, str) or not isinstance(s.enclosure, str) or s.daylight not in {"required", "preferred", "none"} or s.enclosure not in {"closed", "open"}:
                raise ValueError("invalid daylight/enclosure preference")
            if type(s.near_entrance) is not bool:
                raise ValueError("near_entrance must be boolean")
            for target in (*s.adjacent_to, *s.separate_from, *s.merge_with, s.access_via):
                if target == s.key or (target not in by_key and target != "circulation"):
                    raise ValueError(f"invalid spatial relation {s.key} -> {target}")
            if set(s.adjacent_to) & set(s.separate_from):
                raise ValueError("conflicting adjacency/separation requirements")
            for target in s.merge_with:
                other = by_key.get(target)
                if other is None or (other.function, other.group, other.enclosure) != (s.function, s.group, s.enclosure):
                    raise ValueError("merges require the same function, group and enclosure")
            # Access hierarchy must be rooted at circulation, not circular.
            seen, current = {s.key}, s.access_via
            while current != "circulation":
                if current not in by_key:
                    raise ValueError(f"unknown access anchor: {current}")
                if current in seen:
                    raise ValueError("cyclic access_via hierarchy")
                seen.add(current)
                current = by_key[current].access_via


SPATIAL_PROGRAM_GUIDANCE = {
    "families": list(FAMILIES),
    "minimal_schema_example": {
        "family": "double_loaded",
        "spaces": [
            {"key": "office_a", "function": "office", "target_area_m2": 45, "access_via": "circulation"},
            {"key": "office_b", "function": "office", "target_area_m2": 65, "access_via": "circulation"},
        ],
    },
    "example_note": "Schema illustration only, not a layout to copy. Enumerate EVERY desired room, not categories with implicit counts. circulation is implicit; never add a corridor space or use null as access_via.",
    "space_fields": {
        "key": "unique local identifier, e.g. unit_a_living",
        "function": "exact room function from the supplied catalog",
        "target_area_m2": "desired area; not a command to divide the floor equally",
        "min_area_m2": "hard minimum, default 6",
        "max_area_m2": "hard maximum, default 500",
        "capacity": "intended occupants; planning metadata, not a certified occupancy limit",
        "group": "dwelling or department key, optional",
        "access_via": "circulation or another space key; hard direct-door connection",
        "daylight": "required (facade contact), preferred, or none; not daylight simulation",
        "enclosure": "closed or open; open means functional open space, not missing perimeter walls",
        "near_entrance": "boolean soft preference",
        "adjacent_to": "space keys requiring a shared wall (not necessarily a door)",
        "separate_from": "space keys which must not share a wall",
        "merge_with": "same-function same-group space keys to combine into one room",
    },
    "rules": [
        "Predict functional spaces, areas and access before geometry; do not output coordinates.",
        "Each residential group has one living/entry anchor accessing circulation; bedrooms, kitchen and bathroom access that anchor, not the public corridor.",
        "An open_office group has one open anchor plus closed support rooms accessing it. Multiple independent groups are allowed.",
        "Use double_loaded for independent rooms directly accessing circulation. Adjacency constraints must be geometrically realizable.",
        "The initial solver supports a public spine and star-shaped groups; do not request deep chains or atria.",
        "Provide at least two independent circulation-access roots; a centered stable core has usable space on both sides.",
        "Each space is one room, except explicit merges. Counts after merges must respect the enclosing archetype count range.",
        "Min/max areas are hard; target areas, capacity and near_entrance guide planning. Daylight refers only to exterior boundary contact.",
    ],
}
