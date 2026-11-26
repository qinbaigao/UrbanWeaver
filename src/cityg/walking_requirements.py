"""Quoted indoor/outdoor walking requirements and their final-geometry witnesses."""
import math
import re

from cityg.agents.building_uses import label_key


# Constrain easy-to-confuse endpoint translations independently of agent output.
_SPACE_ALIASES = {
    "open_office": ("open office", "开放办公室", "开放式办公区", "开放办公区"),
    "waiting_room": ("waiting room", "候诊室", "候客室", "等候室"),
    "meeting_room": ("meeting room", "conference room", "会议室"),
    "reception": ("lobby", "reception", "门厅", "接待厅", "大堂"),
    "service_hall": ("service hall", "办事大厅", "服务大厅"),
    "sidewalk": ("sidewalk", "人行道"),
    "frontage_path": ("frontage path", "门前步道", "入口步道"),
    "entrance": ("building entrance", "大门", "楼门"),
}


def route_clauses(text):
    """Request structured extraction for explicit endpoint-to-endpoint walking clauses."""
    return [
        part.strip()
        for part in re.split(r"[。；;!?！？\n]|\.(?!\d)", text)
        if re.search(r"步行|步道|步行可达|走到|步行路径|人行路径|\b(?:walk\w*|pedestrian|on foot)\b", part, re.I)
        and re.search(r"从|到|至|之间|\b(?:from|to|between)\b", part, re.I)
        and re.search(
            r"(?i:building)[_\s]+[A-Z0-9]+(?![A-Za-z0-9_])|building_[0-9]+|[A-Z0-9](?:号楼|楼|栋|座)|"
            r"(?:建筑|楼栋|住宅|诊所|办公楼)\s*[A-Z0-9]|room_[0-9]+",
            part,
        )
    ]


def response_schema():
    def obj(fields):
        return dict(type="object", properties=fields, required=list(fields), additionalProperties=False)

    endpoint = obj(
        {
            "quote": {"type": "string"},
            "building": {"type": "string"},
            "space": {
                "type": "string",
                "description": "Canonical room function, exact room ID, entrance, frontage_path, or sidewalk.",
            },
            "level": {"type": ["integer", "null"], "minimum": 0},
        }
    )
    return {
        "type": "array",
        "maxItems": 12,
        "items": obj(
            {
                "source_quote": {"type": "string"},
                "start": endpoint,
                "end": endpoint,
                "max_distance_m": {"type": ["number", "null"], "exclusiveMinimum": 0},
                "via_bridge": {"type": "boolean"},
                "opposite_banks": {"type": "boolean"},
            }
        ),
    }


def validate(rows, instruction=None):
    if not isinstance(rows, list) or len(rows) > 12:
        raise ValueError("Expected up to 12 walking requirements")
    clauses = route_clauses(instruction) if instruction is not None else []
    if any(not any(isinstance(r, dict) and r.get("source_quote") == c for r in rows) for c in clauses):
        raise ValueError(f"Extract each explicit walking clause verbatim: {clauses}")
    for r in rows:
        if not isinstance(r, dict) or set(r) != set(response_schema()["items"]["properties"]):
            raise ValueError("Invalid walking requirement")
        quote = r["source_quote"]
        if (
            not isinstance(quote, str)
            or not quote.strip()
            or (instruction is not None and quote not in instruction)
        ):
            raise ValueError("Walking requirement needs the original clause")
        if instruction is not None and not clauses:
            raise ValueError(
                "Walking verification needs an explicit named source and destination clause"
            )
        for e in (r["start"], r["end"]):
            if (
                not isinstance(e, dict)
                or set(e) != {"quote", "building", "space", "level"}
                or any(
                    not isinstance(e[k], str) or not e[k].strip() for k in ("quote", "building", "space")
                )
                or e["quote"] not in quote
                or not re.search(
                    r"(?<![A-Za-z0-9_])" + re.escape(e["building"]) + r"(?![A-Za-z0-9_])",
                    e["quote"],
                    re.I,
                )
                or (e["level"] is not None and (type(e["level"]) != int or e["level"] < 0))
            ):
                raise ValueError(
                    "Walking endpoints require exact quotations and building labels or IDs from them"
                )
            if e["space"] not in e["quote"]:
                mentioned = {
                    k
                    for k, terms in _SPACE_ALIASES.items()
                    if any(term in e["quote"].lower() for term in terms)
                }
                if mentioned and e["space"] not in mentioned:
                    raise ValueError("Walking endpoint space differs from its quotation")
            if re.search(r"首层|一楼|ground.floor", e["quote"], re.I) and e["level"] != 0:
                raise ValueError("Ground-floor qualifier missing or changed")
        limit = r["max_distance_m"]
        distances = re.findall(
            r"(\d+(?:\.\d+)?)\s*(公里|千米|米|km\b|kilomet(?:er|re)s?\b|m(?:eters?|etres?)?\b)", quote, re.I
        )
        values = {
            float(n) * (1000 if unit.lower().startswith(("k", "公", "千")) else 1) for n, unit in distances
        }
        if re.search(r"至少|不少于|不低于|at least|no less than|minimum.{0,15}distance", quote, re.I) and values:
            raise ValueError("Minimum walking distances require a separate lower-bound verifier")
        if values and (
            len(values) != 1
            or type(limit) not in (int, float)
            or not math.isfinite(limit)
            or limit <= 0
            or limit not in values
        ):
            raise ValueError("Walking upper bound must match the quoted distance converted to metres")
        if not values and limit is not None:
            raise ValueError("No numeric walking distance in the original clause")
        if any(type(r[k]) != bool for k in ("via_bridge", "opposite_banks")):
            raise ValueError("Invalid walking qualifiers")
        if (
            bool(
                re.search(
                    r"过桥|经.{0,3}桥|跨桥|桥上|走桥|via (?:a |the )?bridge|(?:over|across|cross) (?:a |the )?bridge",
                    quote,
                    re.I,
                )
            )
            and not r["via_bridge"]
        ):
            raise ValueError("Do not drop the explicit bridge crossing")
        if re.search(r"两岸|对岸|opposite banks", quote, re.I) and not r["opposite_banks"]:
            raise ValueError("Do not drop the opposite-bank requirement")


def bind_endpoint(city, bindings, endpoint):
    name = endpoint["building"]
    ids = {b.id for b in city.iter_buildings() if b.id == name}
    ids.update(r["building_id"] for r in bindings if label_key(r["label"]) == label_key(name))
    if len(ids) != 1:
        raise ValueError(f"Building {name!r} has {len(ids)} bindings")
    b = next((b for b in city.iter_buildings() if b.id in ids), None)
    if b is None:
        raise ValueError("Bound building missing from final scene")
    if endpoint["space"] in ("entrance", "frontage_path", "sidewalk") and endpoint["level"] in (0, None):
        return b, None, None
    rooms = [
        (f, r)
        for f in b.floors
        for r in f.rooms
        if endpoint["space"] in (r.id, r.function) and endpoint["level"] in (None, f.level)
    ]
    if len(rooms) != 1:
        raise ValueError(f"{b.id}: {len(rooms)} matches for {endpoint['space']!r}")
    f, r = rooms[0]
    if f.level != 0:
        raise ValueError("This geometric walking verifier supports the ground floor")
    return b, f, r


def assess(city, bindings, requirements, manifest):
    from cityg.validation.walking_geometry import PedestrianScene

    scene = None
    scene_error = "No final geometry manifest for this city"
    if manifest and manifest.get("city_id") == city.id:
        try:
            scene = PedestrianScene(manifest)
        except RuntimeError as exc:
            scene_error = str(exc)
    results = []
    for i, request in enumerate(requirements):
        row = {
            "id": f"walking.{i+1}",
            "kind": "hard",
            "check": "compiled_walk",
            "expected": request,
            "status": "unverified",
        }
        try:
            if scene is None:
                raise ValueError(scene_error)
            endpoints = []
            errors = []
            for side in ("start", "end"):
                try:
                    binding = bind_endpoint(city, bindings, request[side])
                    building, floor, room = binding
                    if room is not None:
                        report = scene.realized_floor(building, floor).audit(room)
                        row.setdefault("floor_access", {})[side] = report
                    endpoints.append(binding)
                except ValueError as exc:
                    errors.append(f"{side}: {exc}")
            if errors:
                raise ValueError(" / ".join(errors))
            witness = scene.witness(city, endpoints, request)
            row["actual"] = witness
            limit = request["max_distance_m"]
            if limit is not None and witness["length_m"] > limit:
                row["reason"] = "Checked route exceeds distance bound; a shorter route may exist"
            else:
                row["status"] = "satisfied"
        except ValueError as exc:
            row["reason"] = str(exc)
        results.append(row)
    return results
