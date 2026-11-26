"""Versioned, review-gated layout references; never a source of fixed poses.

The first library supports furniture combinations and rooms. It is opt-in:
loading it does not alter the production planner or approve any candidate.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import dataclass, replace
import hashlib
import json
import math
from pathlib import Path
import re

from cityg.assets import AssetRegistry
from cityg.planning.interiors import ASSET_CATALOG, FurnishingProgram
from cityg.planning.room_design import RoomDesign


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _positive(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


@dataclass(frozen=True)
class MaterializedPrototype:
    prototype_id: str
    revision: int
    content_fingerprint: str
    room_type: str
    design: RoomDesign
    asset_bindings: dict[str, str]
    asset_roles: dict[str, dict]

    def program(self, room_id):
        return FurnishingProgram(room_id, self.room_type, self.design.palette, .5, (),
                                 design=deepcopy(self.design))


class LayoutPrototypeLibrary:
    def __init__(self, root):
        self.root = Path(root)
        self.combinations = self._read("combinations.json", "combination")
        self.rooms = self._read("rooms.json", "room")
        decor_file = self.root/'decoration_assets.json'
        self.decoration_assets = json.loads(decor_file.read_text()).get('assets', []) if decor_file.is_file() else []
        self.reference_assets = [item for path in sorted(self.root.glob('reference_assets_*.json'))
                                 for item in json.loads(path.read_text())['assets']]
        if set(self.combinations) & set(self.rooms):
            raise ValueError("Prototype IDs must be globally unique")
        for record in self.rooms.values():
            self._validate_room(record)
            self.materialize(record["id"])

    def _read(self, filename, level):
        documents = [json.loads(path.read_text(encoding="utf-8")) for path in
                     [self.root / filename, *sorted(self.root.glob(Path(filename).stem + '_*.json'))]]
        if any(d.get('schema_version') != 1 or not isinstance(d.get('prototypes'), list) for d in documents):
            raise ValueError("Expected prototype library schema_version=1")
        document = {'schema_version': 1, 'prototypes': [r for d in documents for r in d['prototypes']]}
        if document.get("schema_version") != 1 or not isinstance(document.get("prototypes"), list):
            raise ValueError("Expected prototype library schema_version=1")
        result = {}
        for raw in document["prototypes"]:
            record = deepcopy(raw)
            key = record.get("id", "")
            if not re.fullmatch(r"[a-z][a-z0-9_]{0,47}", key) or key in result:
                raise ValueError("Unsafe or duplicate prototype ID")
            if record.get("level") != level or type(record.get("revision")) is not int or record["revision"] < 1:
                raise ValueError("Invalid prototype level/revision")
            if not record.get("display_name") or not record.get("intent"):
                raise ValueError("Prototype needs display_name and intent")
            review = record.get("review", {})
            if review.get("status") not in {"draft", "pending_review", "approved", "needs_revision"}:
                raise ValueError("Invalid review status")
            if review["status"] == "approved" and not all(review.get(k) for k in ("reviewer", "reviewed_fingerprint")):
                raise ValueError("Approval requires a reviewer and content fingerprint")
            result[key] = record
        return result

    @staticmethod
    def _validate_room(record):
        from cityg.planning.room_decorations import validate_decorations
        validate_decorations(record.get('decorations', []))
        finishes = record.get('finishes')
        if finishes is not None and (not isinstance(finishes, dict)
                or set(finishes) != {'floor', 'wall'}
                or any(not isinstance(v, str) or not v.strip() for v in finishes.values())):
            raise ValueError('Room finishes require floor and wall material IDs')
        fit = record["applicability"]
        for key in ("width_m", "depth_m", "area_m2", "aspect_ratio"):
            interval = fit[key]
            if len(interval) != 2 or not all(_positive(v) for v in interval) or interval[0] > interval[1]:
                raise ValueError("Invalid applicability interval")
        if fit["door_walls"] != ["south"]:
            raise ValueError("First library supports a south entrance; do not silently rotate a prototype")
        if not _positive(fit['min_height_m']):
            raise ValueError("Invalid minimum room height")
        for case in [record["reference"], *record.get("adaptation_cases", [])]:
            if not all(_positive(case[k]) for k in ("width_m", "depth_m", "height_m", "door_width_m")):
                raise ValueError("Invalid reference dimensions")
            if not _positive(case["door_fraction"]) or not .05 <= case["door_fraction"] <= .95:
                raise ValueError("Invalid door fraction")
            half = case['door_width_m']/2 + .12
            if min(case['door_fraction'], 1-case['door_fraction'])*case['width_m'] < half:
                raise ValueError("Reference door crosses a room corner")
        if type(record["occupants"]) is not int or not 1 <= record["occupants"] <= 64:
            raise ValueError("Invalid occupants")
        if not record.get("hard_constraints") or not record.get("editable_fields"):
            raise ValueError("Prototype needs hard constraints and declared editable fields")

    def content_fingerprint(self, key):
        source = self.rooms.get(key, self.combinations.get(key))
        if source is None:
            raise KeyError(key)
        content = {k: v for k, v in source.items() if k != "review"}
        if key in self.rooms:
            content = {**content, "dependency_fingerprints": {
                item["combination"]: self.content_fingerprint(item["combination"])
                for item in source["group_instances"]},
                'decoration_asset_annotations': self.decoration_assets if source.get('decorations') else []}
            used = {d['asset_id'] for d in source.get('decorations', [])}
            used.update(asset for group in source['group_instances']
                        for asset in self.combinations[group['combination']]['asset_bindings'].values())
            dependencies = [a for a in self.reference_assets if a['id'] in used]
            if dependencies:
                content['reference_asset_annotations'] = dependencies
        return fingerprint(content)

    def approved(self, key):
        record = self.rooms.get(key, self.combinations.get(key))
        if not record:
            return False
        review = record["review"]
        own = (review["status"] == "approved" and bool(review.get("reviewer"))
               and review.get("reviewed_fingerprint") == self.content_fingerprint(key))
        return own and (key not in self.rooms or all(
            self.approved(i["combination"]) for i in record["group_instances"]))

    def compatible(self, key, *, room_type, width_m, depth_m, height_m, door_wall="south"):
        r = self.rooms[key]
        if not all(_positive(v) for v in (width_m, depth_m, height_m)):
            return False
        if r["room_type"] != room_type or door_wall not in r["applicability"]["door_walls"]:
            return False
        values = {"width_m": width_m, "depth_m": depth_m,
                  "area_m2": width_m * depth_m, "aspect_ratio": width_m / depth_m}
        return (height_m >= r["applicability"]["min_height_m"] and all(
            r["applicability"][k][0] <= v <= r["applicability"][k][1] for k, v in values.items()))

    def candidates(self, *, include_unapproved=False, **geometry):
        """Prefilter only; every candidate still requires metric placement checks."""
        return [key for key in sorted(self.rooms)
                if (include_unapproved or self.approved(key)) and self.compatible(key, **geometry)]

    def materialize(self, key, *, for_production=False):
        if for_production and not self.approved(key):
            raise ValueError("Prototype or its combinations lack current human approval")
        record = self.rooms[key]
        groups, props, bindings, roles = [], [], {}, {}
        for instance in record["group_instances"]:
            combo = self.combinations[instance["combination"]]
            prefix = instance["id"]
            def scoped(value):
                return f"{prefix}_{value}"
            members = [{**deepcopy(m), "id": scoped(m["id"])} for m in combo["members"]]
            groups.append({"id": prefix, "zone": instance["zone"],
                           "anchor": {**combo["anchor"], "id": scoped(combo["anchor"]["id"])},
                           "members": members, "placement": deepcopy(instance["placement"])})
            props.extend({**deepcopy(p), "id": scoped(p["id"]),
                          "support_member_id": scoped(p["support_member_id"])}
                         for p in combo.get("surface_items", []))
            for category, asset_id in combo["asset_bindings"].items():
                if category in bindings and bindings[category] != asset_id:
                    raise ValueError("First adapter requires one asset per category per room")
                bindings[category] = asset_id
            for category, role in combo.get('asset_roles', {}).items():
                # A physical dining table can serve as a meeting table, but
                # unrelated categories must not bypass semantic admissibility.
                same_role = (role.get('source_category') == category and category in
                             {'desk','office_chair','sofa','coffee_table','bookcase','cabinet',
                              'dining_table','dining_chair'})
                if (not (same_role or (role.get('source_category'), category) == ('dining_table', 'meeting_table'))
                        or not role.get('rationale') or category not in combo['asset_bindings']):
                    raise ValueError('Unsupported prototype-only asset role')
                if category in roles and roles[category] != role:
                    raise ValueError('Conflicting reference asset roles')
                roles[category] = deepcopy(role)
        counts = Counter(item["category"] for g in groups for item in [g["anchor"], *g["members"]])
        if set(bindings) != set(counts):
            raise ValueError("Every major category needs an explicit reference asset binding")
        member_ids = {i['id'] for g in groups for i in [g['anchor'], *g['members']]}
        if any(q['kind']=='rug' and q['anchor_member_id'] not in member_ids for q in record.get('decorations', [])):
            raise ValueError('Decoration rug anchor is not a furniture member')
        design = RoomDesign.from_dict({
            "intent": record["intent"], "palette": record["palette"],
            "zones": deepcopy(record["zones"]), "groups": groups,
            "reserved_areas": deepcopy(record.get('reserved_areas', [])),
            "surface_items": props, "group_relations": deepcopy(record.get("group_relations", [])),
            "wall_art": False, "tabletop": False,
            "furnishing_brief": {"occupants": record["occupants"],
                "capacity_reason": record["capacity_reason"],
                "items": [{"category": c, "minimum": n, "target": n,
                           "purpose": "Required reference inventory; never shrink to force feasibility"}
                          for c, n in sorted(counts.items())],
                "tradeoffs": "Reference draft; asset fidelity and adaptation require human review."}}, ASSET_CATALOG)
        return MaterializedPrototype(key, record["revision"], self.content_fingerprint(key),
                                     record["room_type"], design, bindings, roles)


def reference_registry(source, prototype):
    """Detached, pinned major assets; no generation, silent replacement, or writes.

The compiler can use the full registry for small props, but major furniture is
selected from these exact IDs. Source geometry is never rescaled or copied here.
"""
    result = AssetRegistry()
    for category, asset_id in prototype.asset_bindings.items():
        record = source.get(asset_id)
        role = prototype.asset_roles.get(category)
        expected_category = role['source_category'] if role else category
        if (record is None or record.category != expected_category or not record.has_geometry
                or record.metadata.get("runtime_enabled") is False
                or not record.supports(environment="indoor", room_type=None if role else prototype.room_type)):
            raise ValueError(f"Missing/incompatible reference asset: {category}={asset_id}")
        geometry = source.resolve_path(record.geometry_path).resolve()
        if not geometry.is_file() or record.dimensions_m is None:
            raise ValueError(f"Missing geometry or physical dimensions: {asset_id}")
        if role:
            record = replace(record, category=category, room_types=(prototype.room_type,),
                             metadata={**record.metadata, 'prototype_only_role': deepcopy(role)})
        result.register(replace(record, geometry_path=str(geometry)))
    return result
