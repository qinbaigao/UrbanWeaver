"""Room-level adaptive furnishing programs with archetype-friendly context."""

from __future__ import annotations

import json
import hashlib
import time
from copy import deepcopy
from cityg.planning.room_design import RoomDesign, DESIGN_SCHEMA, PALETTES
from cityg.planning.room_constraints import wall_segments, WALL_DEFAULTS
from cityg.planning.furnishing_brief import capacity_context
from cityg.planning.furnishing_sufficiency import assess_furnishing, FUNCTION_BUNDLES
from cityg.planning.room_envelope import metric_envelope, envelope_context
from cityg.planning.surface_items import SURFACE_CATALOG, support_options
from dataclasses import dataclass, replace
from typing import Any

from cityg.agents.requirement import AgentAttempt, AgentGenerationError, _parse_json_object
from cityg.memory import MemoryQuery, MemoryStore
from cityg.planning.interiors import (
    ASSET_CATALOG,
    FALLBACK_TEMPLATE,
    ROOM_TEMPLATES,
    FurnishingProgram,
    ObjectRequest,
    SpatialRelation,
)
from cityg.assets import AssetRegistry, infer_asset_room_types
from cityg.schemas import Building, City, Floor, InteriorObject, Room
from cityg.serialization import to_primitive
from cityg.services.interfaces import ChatMessage, TextReasoningService
from cityg.refinement.room_patch import LOCAL_ROOM_PATCH_SCHEMA, expand_local_patch


ROOM_PROGRAM_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "room_id": {"type": "string"},
        "style": {"type": "string"},
        "density": {"type": "number", "minimum": 0, "maximum": 1},
        "design": {**DESIGN_SCHEMA, "required": [*DESIGN_SCHEMA["required"], "furnishing_brief", "surface_items"]},
        "requests": {
            "type": "array",
            "maxItems": 12,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "category": {"type": "string", "enum": sorted(ASSET_CATALOG)},
                    "count": {"type": "integer", "minimum": 0, "maximum": 8},
                    "placement": {"type": "string", "enum": ["wall_back", "wall_side", "center", "grid"]},
                    "required": {"type": "boolean"},
                },
                "required": ["category", "count", "placement", "required"],
            },
        },
        "relations": {
            "type": "array",
            "maxItems": 16,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "subject_category": {"type": "string", "enum": sorted(ASSET_CATALOG)},
                    "relation": {"type": "string", "enum": ["near", "in_front_of", "beside", "faces", "against_wall"]},
                    "target_category": {"type": "string"},
                    "distance_m": {"type": "number", "minimum": 0, "maximum": 5},
                    "required": {"type": "boolean"},
                },
                "required": ["subject_category", "relation", "target_category", "distance_m", "required"],
            },
        },
    },
    "required": ["room_id", "style", "density", "requests", "design"],
}

# Bind the reusable design language to this planner's supported furniture.
# The generic design schema deliberately has no catalog dependency.
ROOM_PROGRAM_RESPONSE_SCHEMA = deepcopy(ROOM_PROGRAM_RESPONSE_SCHEMA)
_design_props = ROOM_PROGRAM_RESPONSE_SCHEMA["properties"]["design"]["properties"]
_group_props = _design_props["groups"]["items"]["properties"]
_group_props["placement"]["properties"]["max_gap_m"]["minimum"] = .12
for _item_schema in (_group_props["anchor"], _group_props["members"]["items"],
                     _design_props["furnishing_brief"]["properties"]["items"]["items"]):
    _item_schema["properties"]["category"]["enum"] = sorted(ASSET_CATALOG)


ROOM_LAYOUT_REFINEMENT_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "room_id": {"type": "string"},
        "reason": {"type": "string", "maxLength": 640},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "operations": {
            "type": "array",
            "minItems": 1,
            "maxItems": 12,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "object_id": {"type": "string"},
                    "action": {
                        "type": "string",
                        "enum": ["move", "rotate", "replace", "remove"],
                    },
                    "placement": {
                        "type": "string",
                        "enum": ["preserve", "wall_back", "wall_side", "center", "grid"],
                    },
                    "facing": {
                        "type": "string",
                        "enum": ["preserve", "room_center", "nearest_wall", "door", "target_object"],
                    },
                    "target_object_id": {"type": ["string", "null"]},
                    "replacement_category": {"type": ["string", "null"]},
                    "reason": {"type": "string", "maxLength": 240},
                },
                "required": [
                    "object_id", "action", "placement", "facing",
                    "target_object_id", "replacement_category", "reason",
                ],
            },
        },
    },
    "required": ["room_id", "reason", "confidence", "operations"],
}


@dataclass(frozen=True)
class RoomProgramResult:
    program: FurnishingProgram
    raw: dict[str, Any]
    archetype_key: str
    attempts: tuple[AgentAttempt, ...] = ()


@dataclass(frozen=True)
class RoomObjectAdjustment:
    object_id: str
    action: str
    placement: str = "preserve"
    facing: str = "preserve"
    target_object_id: str | None = None
    replacement_category: str | None = None
    reason: str = ""


@dataclass(frozen=True)
class RoomLayoutRefinementPlan:
    room_id: str
    reason: str
    confidence: float
    operations: tuple[RoomObjectAdjustment, ...]


@dataclass(frozen=True)
class RoomLayoutRefinementProposal:
    plan: RoomLayoutRefinementPlan
    raw: dict[str, Any]
    attempts: int
    normalization_notes: tuple[str, ...] = ()


def room_archetype_key(room: Room, building: Building | None = None) -> str:
    """Stable key for caching a program across repeated floor layouts."""
    width_bucket = round(room.bounds.width / 2.0) * 2
    depth_bucket = round(room.bounds.depth / 2.0) * 2
    building_function = building.function if building is not None else "unknown"
    return f"{building_function}:{room.function}:{width_bucket:.0f}x{depth_bucket:.0f}"


def resolve_local_group_scope(room, floor, scope):
    """Bind only exact local IDs or aliases witnessed on this room's objects."""
    known={g['id'] for g in room.metadata.get('room_design',{}).get('groups',[])}
    aliases={key:{key} for key in known}
    for obj in floor.objects:
        alias,key=obj.metadata.get('group_id'),obj.metadata.get('group_key')
        if obj.room_id==room.id and isinstance(alias,str) and key in known:
            aliases.setdefault(alias,set()).add(key)
    if (not isinstance(scope,list) or not scope or any(not isinstance(g,str)
            or len(aliases.get(g,()))!=1 for g in scope)):
        raise ValueError('Local repair needs nonempty exact existing target_group_ids; refusing scope expansion')
    return sorted({next(iter(aliases[g])) for g in scope})


class RoomProgramAgent:
    """Generate bounded object requests, never absolute object coordinates."""

    def __init__(
        self,
        service: TextReasoningService,
        *,
        model_id: str = "unknown",
        memory_store: MemoryStore | None = None,
        max_attempts: int = 2,
        asset_resolver=None,
        placement_seed: int = 17,
        review_sufficiency: bool = True,
    ) -> None:
        self.service = service
        self.model_id = model_id
        self.cache: dict[str, RoomProgramResult] = {}
        self.memory_store = memory_store
        self.max_attempts = max(1, max_attempts)
        self.asset_resolver=asset_resolver
        self.placement_seed=placement_seed
        self.review_sufficiency=review_sufficiency

    def propose(
        self,
        city: City,
        building: Building,
        floor: Floor,
        room: Room,
        *,
        use_cache: bool = True,
        visual_feedback: dict[str, Any] | str | None = None,
        compiled_preflight=None,
        inventory_targets=None,
    ) -> RoomProgramResult:
        if compiled_preflight is not None:
            use_cache = False
        scope = visual_feedback.get("target_group_ids") if isinstance(visual_feedback,dict) else None
        forced_protection = None
        if scope is not None:
            known = {g["id"] for g in room.metadata.get("room_design",{}).get("groups",[])}
            original_scope=scope
            scope=resolve_local_group_scope(room,floor,scope)
            visual_feedback={**visual_feedback,'target_group_ids':scope,
                'group_binding':{'requested_ids':original_scope,'local_ids':scope,
                                 'source':'exact_room_object_metadata_aliases'}}
            forced_protection = tuple(sorted(known-set(scope)))
        envelope=metric_envelope(building,floor,room) if self.asset_resolver is not None else None
        if envelope and envelope['status']!='supported':
            raise ValueError('Room geometry needs floor-level replanning before furnishing: '
                             +envelope['reason'])
        planning_room=envelope['room'] if envelope and envelope['status']=='supported' else room
        planning_floor=envelope['floor'] if envelope and envelope['status']=='supported' else floor
        key = room_archetype_key(room, building)
        # Cache semantic designs only when openings, exact dimensions, capacity,
        # intent and feedback agree. Similar-sized rooms are not interchangeable.
        from cityg.interior_requirements import inventory_for
        floor_inventory=inventory_for(building,floor.level,room.function)
        other_counts={}
        sibling_ids={r.id for r in floor.rooms if r.function==room.function and r.id!=room.id}
        for obj in floor.objects:
            if obj.room_id in sibling_ids: other_counts[obj.category]=other_counts.get(obj.category,0)+1
        residual_inventory=[{**i,"min_count":max(0,i["min_count"]-other_counts.get(i["category"],0))}
                            for i in floor_inventory]
        if inventory_targets is not None:
            # Internal floor allocation, never a VLM permission to weaken the
            # original contract. Final floor-wide acceptance is unchanged.
            residual_inventory=inventory_targets
        completion_pass=isinstance(visual_feedback,dict) and visual_feedback.get('major_inventory_only')
        configuration_pass=isinstance(visual_feedback,dict) and visual_feedback.get('source')=='functional_configuration'
        completion_limits={}
        if completion_pass:
            from collections import Counter
            completion_limits=dict(Counter(o.category for o in floor.objects if o.room_id==room.id))
            for item in residual_inventory:
                completion_limits[item['category']]=max(completion_limits.get(item['category'],0),item['min_count'])
            completion_limits={k:v for k,v in completion_limits.items() if v>0}
        context_key = {"required_inventory":residual_inventory,"bounds":to_primitive(room.bounds),"height":room.height_m,
                       "requirement":room.metadata.get("spatial_requirement"),
                       "doors":[{"position":to_primitive(d.position), "width_m":d.width_m}
                                for d in floor.doors if room.id in {d.room_a_id,d.room_b_id}],
                       "objects":[{"category":o.category,"asset":o.asset_id,"position":to_primitive(o.position),
                                   "rotation":o.rotation_deg,"size":[o.width_m,o.depth_m,o.height_m]}
                                  for o in floor.objects if o.room_id==room.id],
                       "accepted_design":room.metadata.get("room_design"),
                       "feedback":visual_feedback,"city":city.name,
                       "metric_envelope":envelope_context(envelope) if envelope else None,
                       "asset_contracts":[(r.asset_id,r.dimensions_m,r.metadata.get('room_support_surfaces'))
                           for r in self.asset_resolver.registry.list_all()
                           if r.supports(environment='indoor',room_type=room.function)] if self.asset_resolver else None,
                       "review_sufficiency":self.review_sufficiency}
        key += ":" + hashlib.sha256(json.dumps(context_key,sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:16]
        if use_cache and key in self.cache:
            cached = self.cache[key]
            return RoomProgramResult(
                program=FurnishingProgram(
                    room.id,
                    cached.program.room_type,
                    cached.program.style,
                    cached.program.density,
                    cached.program.requests,
                    cached.program.relations,
                    cached.program.design,
                ),
                raw=cached.raw,
                archetype_key=key,
            )
        template = ROOM_TEMPLATES.get(room.function, FALLBACK_TEMPLATE)
        prompt = {
            "room": {
                "id": room.id,
                "function": room.function,
                "bounds": to_primitive(planning_room.bounds),
                "coordinate_note":"Actual unrotated building-local metric room; existing legacy object positions are not placement targets.",
                "realized_envelope":envelope_context(envelope) if envelope else None,
                "height_m": room.height_m,
                "existing_object_count": len(room.object_ids),
                "existing_objects": [{"category":obj.category, "group_id":obj.metadata.get("group_id"),
                                     "group_key":obj.metadata.get("group_key"), "object_id":obj.id,
                                     "position":to_primitive(obj.position), "rotation_deg":obj.rotation_deg,
                                     "wall_binding":obj.metadata.get("wall_binding")}
                                     for obj in floor.objects if obj.room_id == room.id],
                "available_wall_segments":wall_segments(planning_floor,planning_room),
                "default_wall_categories":sorted(WALL_DEFAULTS),
                "accepted_design": room.metadata.get("room_design"),
                "spatial_requirement": room.metadata.get("spatial_requirement"),
                "required_inventory": residual_inventory,
                "doors": [to_primitive(d) for d in planning_floor.doors if room.id in {d.room_a_id,d.room_b_id}],
            },
            "building": {"id": building.id, "function": building.function, "floor_level": floor.level},
            "archetype_key": key,
            "deterministic_template": [item.__dict__ for item in template],
            "available_categories": sorted(ASSET_CATALOG),
            "asset_dimensions_m": {k:[v.width_m,v.depth_m,v.height_m] for k,v in ASSET_CATALOG.items()},
            "palette_definitions": PALETTES,
            "capacity_context": capacity_context(planning_room),
            "functional_bundle_options":FUNCTION_BUNDLES.get(room.function,[]),
            "sufficiency_policy":("Do not anchor capacity to a sparse existing layout. Reason from actual usable area, "
                "purpose and requested occupancy. Consider complementary functional groups, not isolated filler. "
                "Large private rooms may have reading/storage/visitor areas without becoming open offices. "
                "Maintain normal physical sizes. density is only an upper occupancy bound, not an automatic object count. "
                "Leave circulation and intentional negative space. Report floor-level scale/binding problems rather than hiding them with furniture."),
            "surface_object_dimensions_m": {k: list(v.size) for k, v in SURFACE_CATALOG.items()},
            "procedural_support_options": support_options(ASSET_CATALOG),
            "furnishing_workflow": (
                "First reason about occupants and functional completeness. In design.furnishing_brief return "
                "{occupants,capacity_reason,items:[{category,minimum,target,purpose}],tradeoffs}. List every "
                "major furniture category; minimum is an essential count, target is desired. Then construct "
                "design.groups to meet the inventory. Never just copy small fixed template counts for a large "
                "open office. A private office can have few occupants plus visitor/storage areas. Office/study "
                "capacity requires one desk and office_chair per occupant; meeting capacity requires one "
                "meeting_chair per occupant. Explain reductions from requested capacity and unmet targets in "
                "tradeoffs. Geometric feasibility and existing furniture retention still take precedence. "
                "Finally design.surface_items contains [{id,support_member_id,surface:top|shelves,category,"
                "count,placement:front|back|left|right|spread}]. Bind to exact group anchor/member IDs, never "
                "a category or a coordinate. Use 0..32 requests and <=48 small instances. Distribute books "
                "across bookcase shelves; give workstations monitor/keyboard and selected lamps/books/cups. "
                "Choose items appropriate to this room's purpose, not every category everywhere. Front/back "
                "are relative to the supporting furniture's semantic front. These are optional static visual "
                "subentities, not floor obstacles or interactive rigid bodies. Missing/unverified support "
                "surfaces are skipped with a diagnostic; do not invent surfaces on arbitrary GLBs. "
                "For protected groups preserve their existing surface_items unchanged."
            ),
            "protected_group_ids": forced_protection,
            "design_guidance": (
                "Return design with intent, palette (warm/minimal/industrial), zones, groups, wall_art and tabletop. "
                "Zones have id, purpose, position (north/south/east/west/center), are soft functional areas, not walls. "
                "Each group has id, zone, anchor {id,category}, members [{id,category,side,slot,gap_m,face_anchor}]. "
                "Members refer to their own group's anchor, not a category. side is front/back/left/right in the anchor's "
                "semantic front frame. slot is -2..2 in half steps along that side; 0 centers it; gap_m is .15..1.5. "
                "Use globally unique furniture IDs across ALL groups (e.g. g01_desk, g01_chair, g02_desk). "
                "Only available_categories may be anchors/members; lamps/books/plants use surface_items. "
                "The anchor ALREADY creates one physical object; members are ONLY additional objects. "
                "A singleton cabinet has members:[]; never repeat its anchor as a member. "
                "For wall-bound anchors, do not put members behind the anchor (that is inside the wall). "
                "A desk and its chair, or sofa and coffee table, are one group. "
                "For rectangular meeting/dining tables, prefer paired chairs on the two long sides "
                "(distinct slots) when end seats consume door or wall clearance. gap_m is EXTRA separation "
                "between furniture bounds, not center distance; 0.2-0.35 is a reasonable starting preference "
                "for table/chair groups in compact rooms. The solver separately enforces chair pull-back "
                "and access space; do not reserve the same clearance twice through oversized gaps. "
                "Concrete four-seat example for a table wider in X with front_axis +Y: members at "
                "(side=front,slot=-0.5), (front,+0.5), (back,-0.5), (back,+0.5), all face_anchor=true. "
                "Here front/back are the LONG edges; left/right are the table ends. Do not describe "
                "two-long-side seating in prose while assigning one chair to each of four sides. "
                "Choose 1..4 functional zones and 1..16 groups, <=32 major objects; allow clear doors and use space. "
                "Use the disclosed actual room purpose/capacity; avoid filling every free patch. "
                "Retain existing functional category counts: the non-degradation gate rejects losing anchors. "
                "requests remains a conservative fallback only; it is not added on top of design. "
                "Surface items are separately budgeted optional visual accents, not interactive simulation assets."
                " Palette RGB definitions are fixed; free-form intent text cannot override colors. "
                "Do not claim an unsupported recoloring or fine mesh detail change in the intent."
                " Groups may add placement {mode:auto|wall|free,wall:auto|north|south|east|west,"
                "contact:auto|head|back,max_gap_m:0.12..0.35}. Auto puts bed headboards and storage backs "
                "against door-free walls; choose free explicitly for an island/room-divider. "
                "Wall sides use the room's planning frame, not world compass directions. "
                "Keep cabinet fronts clear (.75m), chair pull-back clear (.65m), at least one bed side "
                "clear (.60m), and connected door-to-use routes (.55m clearance). "
                "Member gap_m is a preferred minimum; cabinet-front spacing is raised to .80m when needed, "
                "and all members reserve at least .17m object separation. Bedside tables normally face "
                "the same direction as the bed (face_anchor:false), aligned with the headboard. "
                "and the effective spacing is recorded. Procedural bed front is its foot side, head is opposite. "
                "group_relations is optional: [{subject:group_id,target:group_id,relation:near|faces|aligned,"
                "min_distance_m:number,max_distance_m:number,required:boolean}]. Distances refer to anchors' centers. "
                "Use cross-group relations for sofa/TV alignment and viewing direction. "
                "For local repairs list unaffected existing group keys in protected_groups; keep their group "
                "definitions unchanged. They remain fixed in pose, asset, scale and identity. If they conflict "
                "with the requested repair, report the infeasibility instead of silently clearing protections. "
            ),
            "rules": (
                "Preserve room bounds and circulation; output semantic requests only, "
                "not coordinates. Use only available_categories and the listed placement "
                "strategies. Derive counts from furnishing_brief and capacity, not fixed template counts. "
                "Do not fill space at the expense of circulation. The room_id must be copied "
                "exactly. Prefer instance-bound design groups; legacy relations are fallback only. "
                "Add a small number of semantic relations for important furniture "
                "groups (for example chair faces desk or coffee_table near sofa); never "
                "invent world coordinates."
            ),
            "group_syntax_examples": [
                {"id":"storage","zone":"main","anchor":{"id":"cabinet_01","category":"cabinet"},"members":[]},
                {"id":"work","zone":"main","anchor":{"id":"desk_01","category":"desk"},
                 "members":[{"id":"chair_01","category":"office_chair","side":"front",
                             "slot":0,"gap_m":.7,"face_anchor":True}]},
            ],
            "field_type_contract": {
                "design.wall_art": "JSON boolean true or false, NOT a list; false disables wall decoration",
                "design.tabletop": "JSON boolean true or false, NOT a list; surface_items is the explicit prop list",
                "design.furnishing_brief": "Required object nested INSIDE design, never at the response root",
                "design.surface_items": "Required array; [] means no support-scoped props",
                "requests": "Required array at response root; [] is valid when using design.groups",
            },
        }
        if visual_feedback:
            prompt["visual_feedback"] = (
                visual_feedback
                if isinstance(visual_feedback, str)
                else dict(visual_feedback)
            )
            prompt["rules"] += (
                " Address the visual feedback conservatively. Add only the missing "
                "semantic categories or relations that can be realized inside the "
                "room; do not change room geometry. Return the COMPLETE replacement program, "
                "not a list of changes. Keep existing unaffected groups and all their members. "
                "If accepted_design exists you MUST return design; requests-only output is invalid. "
                "VLM claims are hypotheses: do not duplicate an object that existing_objects already contains."
            )
        if self.asset_resolver is not None:
            prompt["existing_real_asset_options"]={category:[{
                "asset_id":r.asset_id,"dimensions_m":r.dimensions_m,
                "front_axis":r.metadata.get("orientation",{}).get("canonical_forward_axis"),
                "verified_support_surfaces":[{'kind':s.get('kind'),'size_fraction':s.get('size'),
                    'clearance_fraction':s.get('clearance_fraction')} for s in r.metadata.get('room_support_surfaces',[])
                    if s.get('verified') is True]}
                for r,_ in self.asset_resolver.registry.search(category,category=category,
                    environment="indoor",room_type=room.function,require_geometry=True,limit=3)]
                for category in ASSET_CATALOG}
            prompt["asset_size_policy"]=("Actual meshes keep physical dimensions. When surface_items are requested, resolver prefers a compatible "
                "asset with verified support of that kind. Do not assume procedural support options apply to GLBs. "
                "If no compatible annotated support exists, choose another suitable furniture category or explain the unmet support need.")
        if self.memory_store is not None:
            prompt["relevant_memory"] = [item.to_dict() for item in self.memory_store.query(
                MemoryQuery(scope_id=room.id,
                            world_version=next(n.version for n in city.world_program.nodes if n.entity_id == room.id),
                            allow_cross_run=True, limit=4)
            )]
        if completion_pass:
            prompt['required_or_retained_inventory']=completion_limits
            prompt['deterministic_template']=[]
            prompt['completion_policy']=(
                'This is a bounded primary-function completion pass. Preserve existing objects and realize only '
                'required_or_retained_inventory. These are minima, not an exact aesthetic layout: choose feasible '
                'table seating/work capacity in these requested categories, but do not add secondary categories. Other rooms carry '
                'other allocated functions. Optional visual enrichment is a later pass. '
                'An unspecified plural such as staff workspaces has presence minimum 1 for verification; '
                'this does not mean a large shared office should have only one workstation. Infer a modest '
                'desired capacity from usable dimensions and actual asset sizes, explain it in furnishing_brief, '
                'and realize additional useful same-category groups if feasible. Do not multiply beds in a private bedroom '
                'or dining tables in a home merely to fill empty space. These desired counts are soft, not user requirements. '
                'A six-seat rectangular table with width along X and front +Y uses three chairs on front and '
                'three on back at slots -1,0,+1; prefer no end seats in a compact room. '
                'For wall furniture choose wall=auto unless a specific wall is required; openings can split a wall '
                'into segments too short for the actual mesh. A singleton counter does not need dining furniture.')
        messages = [
            ChatMessage(role="system", content=(
                "You are a room furnishing program agent. Return a compact JSON program. "
                "Copy room_id exactly. Use only listed categories and placement strategies; "
                "plan capacity and a functional inventory before furniture groups and support-scoped small objects. "
                "required_inventory gives mandatory residual counts for THIS room after counting other same-function "
                "rooms on this floor. Meet them with actual groups, not prose or decorations; do not waive them in tradeoffs. "
                "For measured_inventory_shortfall, first realize the missing primary functions with existing inventory retained. "
                "Do not invent explicit user-requested occupancy or large secondary bundles; inferred desired capacity "
                "must be marked as your design choice. Avoid optional new surface requests until the "
                "required major furniture is feasible. Never output world coordinates or alter room bounds."
            )),
            ChatMessage(role="user", content=json.dumps(prompt, ensure_ascii=False, sort_keys=True)),
        ]
        if forced_protection is not None:
            messages.append(ChatMessage(role='user',content=(
                'This is a scoped local repair. Prefer the compact local patch schema: room_id, reason, '
                'group_updates [{group_id, placement}]. Only update these existing groups: '
                +json.dumps(scope)+'. The coordinator retains the original inventory, members, '
                'relations, zones and support objects. Unedited groups keep their exact poses. '
                'If infeasible, report the conflict; do not delete furniture or expand scope.')))
        last_error: Exception | None = None
        attempts: list[AgentAttempt] = []
        response_schema = LOCAL_ROOM_PATCH_SCHEMA if forced_protection is not None else ROOM_PROGRAM_RESPONSE_SCHEMA
        major_only=(isinstance(visual_feedback,dict) and visual_feedback.get('major_inventory_only')
                    and not room.metadata.get('room_design',{}).get('surface_items')
                    and forced_protection is None)
        if major_only:
            response_schema=deepcopy(response_schema)
            response_schema['properties']['design']['properties']['surface_items']['maxItems']=0
            messages.append(ChatMessage('user','This is a primary-furniture completion pass. Return surface_items: []. '
                'Do not add optional support decorations before primary furniture is accepted. Existing inventory stays protected.'))
        fresh_completion=completion_pass and not any(o.room_id==room.id for o in floor.objects)
        if fresh_completion:
            # Optional model preferences must not replace measured access rules.
            response_schema=deepcopy(response_schema)
            props=response_schema['properties']['design']['properties']
            for key in ('reserved_areas','group_relations'):props.pop(key,None)
            props['zones']['items']['properties'].pop('bounds_uv',None)
            placement=props['groups']['items']['properties']['placement']['properties']
            placement.pop('facing',None)
            placement['wall']['enum']=['auto']
            placement['contact']['enum']=['auto']
            messages.append(ChatMessage(role='user',content=(
                'For this fresh completion use soft zone positions only. Do not invent hard reserved_areas, '
                'bounds_uv, group_relations or fixed facing. Set placement wall/contact to auto; the solver '
                'uses real door-free walls. Actual wall, door, access and furniture-use constraints remain mandatory.')))
            # Local grammar decoders can stall on this nested optional schema.
            # Plain JSON retains the same validation and bounded retry policy.
            messages.append(ChatMessage(role='user',content=(
                'Return one compact JSON instance matching the following schema (not the schema itself). '
                'Use requests:[] when design groups carry the inventory. Omit unused optional fields. '
                +json.dumps(response_schema,separators=(',',':')))))
            response_schema=None
        best_feasible = None
        best_preview = None
        sufficiency_requested = False
        for attempt in range(1, self.max_attempts + 1):
            from cityg.progress import progress
            progress('Room Agent', '请求房间方案并预检', room=room.id, attempt=f'{attempt}/{self.max_attempts}')
            raw_text = ""
            finish_reason = None
            usage = {}
            started = time.monotonic()
            try:
                method = getattr(self.service, 'complete_with_metadata', None)
                if callable(method):
                    completion = method(messages, response_schema)
                    raw_text = completion.content
                    finish_reason = completion.finish_reason
                    usage = completion.usage
                else:
                    raw_text = self.service.complete(messages, response_schema)
                if finish_reason == 'length':
                    raise ValueError('model output reached max_tokens; return a compact complete program')
                data = _parse_json_object(raw_text)
                if major_only and data.get('design',{}).get('surface_items'):
                    raise ValueError('Primary-furniture completion requires surface_items=[] in this pass')
                if major_only and isinstance(data.get('design'),dict):
                    from collections import Counter
                    groups=data['design'].get('groups',[])
                    designed=Counter(i['category'] for g in groups for i in [g['anchor'],*g['members']])
                    brief=data['design'].get('furnishing_brief') or {}
                    for item in brief.get('items',[]):
                        if designed[item['category']]>item['target']:
                            raise ValueError(f"Primary completion: groups create {designed[item['category']]} {item['category']}, "
                                f"but the furnishing brief targets {item['target']}. Every anchor creates an object. "
                                "Combine members sharing one intended anchor into ONE group, or explicitly justify and update the inventory target.")
                patch_protection = None
                if 'group_updates' in data:
                    if forced_protection is None:
                        raise ValueError('Local patch requires explicit target_group_ids')
                    data = expand_local_patch(data,room,scope)
                    patch_protection = tuple(data['design']['protected_groups'])
                if response_schema is None:
                    missing=set(ROOM_PROGRAM_RESPONSE_SCHEMA["required"])-set(data)
                    if missing:
                        raise ValueError(f"Response is missing required root fields {sorted(missing)}; requests may be []")
                    if not isinstance(data.get("design"),dict):
                        raise ValueError("design must be a JSON object")
                    missing=set(ROOM_PROGRAM_RESPONSE_SCHEMA["properties"]["design"]["required"])-set(data["design"])
                    if missing:
                        raise ValueError(f"design is missing required nested fields {sorted(missing)}; "
                                         "furnishing_brief belongs inside design, not at the response root")
                    if not isinstance(data["design"]["furnishing_brief"],dict):
                        raise ValueError("design.furnishing_brief must be a non-null inventory object")
                    if not isinstance(data["design"]["surface_items"],list):
                        raise ValueError("design.surface_items must be an array, possibly []")
                if str(data.get("room_id")) != room.id:
                    raise ValueError("room program targets a different room")
                requests: list[ObjectRequest] = []
                for item in data.get("requests", []):
                    request = ObjectRequest(
                        category=str(item["category"]),
                        count=int(item["count"]),
                        placement=str(item["placement"]),
                        required=bool(item["required"]),
                    )
                    if request.category not in ASSET_CATALOG:
                        raise ValueError(f"unknown indoor asset category: {request.category}")
                    requests.append(request)
                relations: list[SpatialRelation] = []
                for item in data.get("relations", []):
                    relation = SpatialRelation(
                        subject_category=str(item["subject_category"]),
                        relation=str(item["relation"]),
                        target_category=str(item["target_category"]),
                        distance_m=float(item.get("distance_m", 1.0)),
                        required=bool(item.get("required", False)),
                    )
                    relations.append(relation)
                program = FurnishingProgram(
                    room_id=room.id,
                    room_type=room.function,
                    style=str(data["style"]),
                    density=float(data["density"]),
                    requests=tuple(requests),
                    relations=tuple(relations),
                    design=RoomDesign.from_dict(data.get("design"), ASSET_CATALOG),
                )
                program.validate(ASSET_CATALOG)
                if fresh_completion and program.design is not None:
                    design=program.design
                    if (design.reserved_areas or design.group_relations or any('bounds_uv' in z for z in design.zones)
                        or any('facing' in g.get('placement',{}) or g.get('placement',{}).get('wall','auto')!='auto'
                               or g.get('placement',{}).get('contact','auto')!='auto' for g in design.groups)):
                        raise ValueError('Fresh completion must leave optional zones/orientation soft; use wall/contact auto, '
                                         'no reserved_areas, bounds_uv, facing or group_relations. Compiled access remains enforced.')
                if completion_pass and program.design is not None:
                    from collections import Counter
                    proposed_counts=Counter(item['category'] for group in program.design.groups
                                            for item in [group['anchor'],*group['members']])
                    excess={k:v for k,v in proposed_counts.items() if k not in completion_limits}
                    if excess:
                        raise ValueError(f'Completion pass adds unrequested secondary furniture {excess}; '
                                         f'use these current-room categories and minimum counts {completion_limits}. '
                                         'Keep all original floor requirements; other allocated rooms cover their own bundles.')
                if forced_protection is not None:
                    if program.design is None:
                        raise ValueError("Group-local repair requires the full design and fixed non-target groups")
                    program = replace(program,design=replace(program.design,
                        protected_groups=patch_protection if patch_protection is not None else forced_protection))
                    program.validate(ASSET_CATALOG)
                    data["design"] = program.design.to_dict()
                if room.metadata.get("room_design", {}).get("status") == "accepted" and program.design is None:
                    raise ValueError("Existing grouped design requires a complete design replacement, not a requests-only patch")
                if program.design is not None:
                    from cityg.planning.interiors import FloorDetailAgent
                    from cityg.planning.room_groups import place_room_design
                    # Existing real assets must be checked in the realized
                    # metric frame before accepting a model's room program.
                    # Preview never generates assets or mutates the source room.
                    from cityg.assets import AssetResolver
                    from cityg.planning.room_metric_frame import place_metric_room
                    resolver=(AssetResolver(self.asset_resolver.registry,(),max_provider_calls=0)
                              if self.asset_resolver is not None else None)
                    detail=FloorDetailAgent(asset_resolver=resolver)
                    preview_room=deepcopy(room)
                    preview=place_metric_room(detail,building,floor,preview_room,program,self.placement_seed) if resolver else None
                    if preview is None:
                        preview=place_room_design(detail,building,floor,preview_room,program,self.placement_seed)
                    from cityg.planning.furnishing_gate import furnishing_non_degradation_check
                    gate = furnishing_non_degradation_check(
                        [obj for obj in floor.objects if obj.room_id == room.id], preview, room)
                    if not gate["ok"]:
                        raise ValueError(gate["reason"] + "; return the complete room design with unaffected anchors retained")
                    if best_preview is not None:
                        supplement_gate=furnishing_non_degradation_check(best_preview,preview,room)
                        if not supplement_gate['ok']:
                            raise ValueError('Supplement regresses the feasible draft: '+supplement_gate['reason'])
                if residual_inventory:
                    if program.design is None: raise ValueError("Explicit inventory requires a compiled room design")
                    from collections import Counter
                    realized_counts=Counter(o.category for o in preview)
                    deficits=[i for i in residual_inventory if realized_counts[i['category']]<i['min_count']]
                    if deficits: raise ValueError('Explicit functional inventory remains unmet after placement: '+json.dumps(deficits))
                if compiled_preflight is not None:
                    data['_compiled_preflight'] = compiled_preflight(program)
                attempts.append(AgentAttempt(
                    index=attempt, prompt_hash=hashlib.sha256(str(messages).encode()).hexdigest(),
                    messages=tuple({"role":m.role,"content":m.content} for m in messages),
                    raw_output=raw_text, elapsed_s=time.monotonic()-started,
                    finish_reason=finish_reason, usage=usage))
                if program.design is not None:
                    quality_room=deepcopy(planning_room)
                    quality_room.metadata['room_design']=program.design.to_dict()
                    quality=assess_furnishing(quality_room,preview,area_m2=planning_room.bounds.area)
                    data['_sufficiency_review']=quality
                result = RoomProgramResult(program=program, raw=data, archetype_key=key, attempts=tuple(attempts))
                if (self.review_sufficiency and self.asset_resolver is not None and program.design is not None
                        and quality['needs_review'] and not sufficiency_requested
                        and (not visual_feedback or (completion_pass and visual_feedback.get('allow_capacity_review')))
                        and not program.design.protected_groups and attempt<self.max_attempts):
                    best_feasible=result
                    best_preview=deepcopy(preview)
                    sufficiency_requested=True
                    messages.extend([ChatMessage(role='assistant',content=raw_text),ChatMessage(role='user',content=(
                        'The layout passed safety checks. Perform ONE bounded furnishing-completeness review: '
                        +json.dumps(quality,ensure_ascii=False)+
                        (' Consider useful additional groups within required_or_retained_inventory categories only, '
                         'especially additional workstations in shared offices when space supports them. '
                         'Do not treat the presence minima as ideal room capacity. '
                         if completion_pass else ' Add purposeful complementary groups where justified, ')+
                        'Retain existing functional inventory. '
                        'Do not shrink furniture or relax access. If spaciousness is intentional, retain the program and explain it in tradeoffs. '
                        'Return the complete program, not a patch.'))])
                    continue
                if use_cache:
                    self.cache[key] = result
                return result
            except (TypeError, ValueError, KeyError, json.JSONDecodeError, RuntimeError) as exc:
                last_error = exc
                progress('Room Agent', '方案未通过；预算内重试，否则保留原场景',
                         error_type=type(exc).__name__, truncated=finish_reason=='length')
                if isinstance(exc, json.JSONDecodeError) or finish_reason == 'length':
                    # Some local constrained decoders get trapped emitting
                    # whitespace at a typed value. Retry plain JSON, retaining
                    # all local schema, inventory and geometric validation.
                    response_schema = None
                attempts.append(AgentAttempt(
                    index=attempt, prompt_hash=hashlib.sha256(str(messages).encode()).hexdigest(),
                    messages=tuple({"role":m.role,"content":m.content} for m in messages),
                    raw_output=raw_text, elapsed_s=time.monotonic()-started,
                    error=f"{type(exc).__name__}: {exc}", finish_reason=finish_reason, usage=usage))
                if attempt < self.max_attempts:
                    # Removing constrained decoding must not remove the output
                    # contract. The initial brief describes design intent, but
                    # is not a substitute for the complete response schema.
                    schema_reminder = (' Plain JSON mode still requires the COMPLETE response matching this schema, '
                        'not a schema copied as data. '
                        'Response JSON schema: '+json.dumps(
                            LOCAL_ROOM_PATCH_SCHEMA if forced_protection is not None else ROOM_PROGRAM_RESPONSE_SCHEMA,
                            separators=(',',':'))
                        if response_schema is None else '')
                    messages.extend([
                        ChatMessage(role="assistant", content=raw_text.rstrip()),
                        ChatMessage(
                            role="user",
                            content=(
                                "Correct the room program JSON. Validation error: "
                                f"{type(exc).__name__}: {exc}. Keep the exact room_id "
                                "and use only the provided categories." + (
                                    f' In this completion pass, minima are {completion_limits}. You may reduce your own '
                                    'unrequested extra counts/capacity or change wall/seat arrangement; never reduce these '
                                    'minima or remove existing furniture. Update your furnishing_brief consistently.'
                                    if completion_pass else '') + (
                                    ' The functional_configuration recommended/minimum/maximum values are ALL soft '
                                    'design targets, not user requirements. On this fit failure, reduce proposed '
                                    'optional groups or recommended copies, prioritize the primary activity and '
                                    'retain ALL preexisting furniture plus required_inventory. Do not repeat the '
                                    'same infeasible counts. Adjust furnishing_brief.occupants/minimum/target to '
                                    'the revised proposal and explain the shortfall in tradeoffs. '
                                    if configuration_pass else '') + schema_reminder
                            ),
                        ),
                    ])
        if best_feasible is not None:
            return replace(best_feasible, attempts=tuple(attempts),raw={**best_feasible.raw,
                '_sufficiency_fallback':'Supplement failed safety checks; retained the last feasible complete program.'})
        raise AgentGenerationError(
            f"Room refinement failed after {self.max_attempts} attempts: {last_error}",
            attempts,
        )


class RoomLayoutRefinementAgent:
    """Turn room-bound VLM feedback into bounded semantic object edits.

    The model may choose *what* should move, rotate, be replaced, or be
    removed. It never authors metric coordinates: the deterministic placement
    layer remains the only component allowed to commit geometry.
    """

    def __init__(
        self,
        service: TextReasoningService,
        *,
        model_id: str = "unknown",
        asset_registry: AssetRegistry | None = None,
        max_attempts: int = 2,
    ) -> None:
        self.service = service
        self.model_id = model_id
        self.asset_registry = asset_registry
        self.max_attempts = max(1, max_attempts)

    def propose(
        self,
        city: City,
        building: Building,
        floor: Floor,
        room: Room,
        *,
        visual_feedback: dict[str, Any] | str,
    ) -> RoomLayoutRefinementProposal:
        objects = [item for item in floor.objects if item.room_id == room.id]
        if not objects:
            raise ValueError("local room rearrangement requires existing objects")
        object_ids = {item.id for item in objects}
        editable_ids = object_ids
        schema = ROOM_LAYOUT_REFINEMENT_RESPONSE_SCHEMA
        if isinstance(visual_feedback, dict) and "target_group_ids" in visual_feedback:
            groups = resolve_local_group_scope(room, floor, visual_feedback["target_group_ids"])
            editable_ids = {item.id for item in objects if item.metadata.get("group_key") in groups}
            if not editable_ids:
                raise ValueError("No existing objects in the authorized repair groups")
            schema = deepcopy(schema)
            schema["properties"]["operations"]["items"]["properties"]["object_id"]["enum"] = sorted(editable_ids)
        prompt = {
            "room": {
                "id": room.id,
                "function": room.function,
                "bounds": to_primitive(room.bounds),
                "height_m": room.height_m,
            },
            "building": {
                "id": building.id,
                "function": building.function,
                "floor_level": floor.level,
            },
            "doors": [
                {
                    "id": door.id,
                    "position": to_primitive(door.position),
                    "width_m": door.width_m,
                }
                for door in floor.doors
                if room.id in {door.room_a_id, door.room_b_id}
            ],
            "editable_object_ids": sorted(editable_ids),
            "existing_objects": [self._object_context(item) for item in objects],
            "visual_feedback": (
                visual_feedback
                if isinstance(visual_feedback, str)
                else dict(visual_feedback)
            ),
            "available_replacement_categories": sorted(ASSET_CATALOG),
            "room_template_categories": sorted({
                item.category
                for item in ROOM_TEMPLATES.get(room.function, FALLBACK_TEMPLATE)
            }),
            "rules": (
                "Return only the smallest set of object-local corrections needed to address "
                "visible feedback. Use exact existing object IDs. Prefer move or rotate over "
                "replace, and replace over remove when the object is useful. Never output "
                "coordinates, room geometry, walls, or doors. placement and facing are semantic "
                "hints that a deterministic solver will validate. Use target_object only with an "
                "exact existing target_object_id. A replacement must use an available category "
                "appropriate for the room function. Indoor/outdoor and room-type asset tags are "
                "hard constraints. Do not include unchanged objects. Furniture with group_id is "
                "protected: do not edit its members individually; request a RoomProgram redesign "
                "in the reason instead. Other objects may still be locally adjusted."
            ),
        }
        messages = [
            ChatMessage(
                role="system",
                content=(
                    "You are CityG's local room layout refinement agent. Convert grounded VLM "
                    "feedback into a minimal JSON edit plan over existing furniture. Never emit "
                    "metric coordinates and never modify architectural geometry."
                ),
            ),
            ChatMessage(role="user", content=json.dumps(prompt, ensure_ascii=False, sort_keys=True)),
        ]
        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            raw_text = ""
            try:
                raw_text = self.service.complete(
                    messages, schema
                )
                data = _parse_json_object(raw_text)
                if str(data.get("room_id")) != room.id:
                    raise ValueError("room layout refinement targets a different room")
                operations = tuple(
                    self._parse_operation(item, object_ids)
                    for item in data.get("operations", [])
                )
                if any(op.object_id not in editable_ids for op in operations):
                    raise ValueError("Operation targets an object outside the authorized repair groups")
                if not operations:
                    raise ValueError("room layout refinement must contain an operation")
                if len({item.object_id for item in operations}) != len(operations):
                    raise ValueError("an object may be adjusted at most once per refinement")
                existing_by_id = {item.id: item for item in objects}
                normalized_operations: list[RoomObjectAdjustment] = []
                normalization_notes: list[str] = []
                for operation in operations:
                    if operation.action not in {"move", "rotate"}:
                        normalized_operations.append(operation)
                        continue
                    existing_object = existing_by_id[operation.object_id]
                    record = (
                        self.asset_registry.get(existing_object.asset_id)
                        if self.asset_registry is not None
                        else None
                    )
                    environment = record.environment if record is not None else "indoor"
                    room_types = (
                        record.room_types
                        if record is not None
                        else infer_asset_room_types(existing_object.category)
                    )
                    if environment not in {"indoor", "both"} or (
                        room_types and room.function not in room_types
                    ):
                        normalized_operations.append(
                            RoomObjectAdjustment(
                                object_id=operation.object_id,
                                action="remove",
                                reason=(
                                    f"{operation.reason} Normalized from {operation.action}: "
                                    f"asset tags are incompatible with {room.function}."
                                ).strip(),
                            )
                        )
                        normalization_notes.append(
                            f"normalized {operation.object_id} from {operation.action} to remove "
                            f"because its asset tags are incompatible with {room.function}"
                        )
                    else:
                        normalized_operations.append(operation)
                operations = tuple(normalized_operations)
                confidence = float(data["confidence"])
                if not 0.0 <= confidence <= 1.0:
                    raise ValueError("confidence must be within [0, 1]")
                plan = RoomLayoutRefinementPlan(
                    room_id=room.id,
                    reason=str(data["reason"]),
                    confidence=confidence,
                    operations=operations,
                )
                return RoomLayoutRefinementProposal(
                    plan, data, attempt, tuple(normalization_notes)
                )
            except (TypeError, ValueError, KeyError, json.JSONDecodeError, RuntimeError) as exc:
                last_error = exc
                if attempt < self.max_attempts:
                    messages.extend(
                        [
                            ChatMessage(role="assistant", content=raw_text[:8000]),
                            ChatMessage(
                                role="user",
                                content=(
                                    "Correct the local room edit JSON. Validation error: "
                                    f"{type(exc).__name__}: {exc}. Use only exact object IDs and "
                                    "available replacement categories; do not output coordinates."
                                ),
                            ),
                        ]
                    )
        raise AgentGenerationError(
            f"Room layout refinement failed after {self.max_attempts} attempts: {last_error}",
            (),
        )

    def _object_context(self, item: InteriorObject) -> dict[str, Any]:
        context: dict[str, Any] = {
            "object_id": item.id,
            "category": item.category,
            "asset_id": item.asset_id,
            "position": to_primitive(item.position),
            "size_m": [item.width_m, item.depth_m, item.height_m],
            "rotation_deg": item.rotation_deg,
            "placement_strategy": item.metadata.get("placement_strategy"),
            "front_axis": item.metadata.get("front_axis", "+Y"),
            "group_id": item.metadata.get("group_id"),
            "group_anchor_id": item.metadata.get("group_anchor_id"),
            "zone_id": item.metadata.get("zone_id"),
        }
        if self.asset_registry is not None:
            record = self.asset_registry.get(item.asset_id)
            if record is not None:
                context["asset_tags"] = {
                    "environment": record.environment,
                    "room_types": list(record.room_types),
                    "tags": list(record.tags[:16]),
                    "quality_score": record.quality_score,
                    "source": record.source,
                }
        return context

    @staticmethod
    def _parse_operation(
        item: dict[str, Any], object_ids: set[str]
    ) -> RoomObjectAdjustment:
        object_id = str(item["object_id"])
        if object_id not in object_ids:
            raise ValueError(f"unknown room object: {object_id}")
        action = str(item["action"])
        placement = str(item["placement"])
        facing = str(item["facing"])
        target = item.get("target_object_id")
        target_id = str(target) if target is not None else None
        replacement = item.get("replacement_category")
        replacement_category = str(replacement) if replacement is not None else None
        if action not in {"move", "rotate", "replace", "remove"}:
            raise ValueError(f"unsupported room object action: {action}")
        if placement not in {"preserve", "wall_back", "wall_side", "center", "grid"}:
            raise ValueError(f"unsupported room placement hint: {placement}")
        if facing not in {"preserve", "room_center", "nearest_wall", "door", "target_object"}:
            raise ValueError(f"unsupported room facing hint: {facing}")
        if action == "replace" and replacement_category not in ASSET_CATALOG:
            raise ValueError("replace requires an available replacement_category")
        if action != "replace" and replacement_category is not None:
            raise ValueError("replacement_category is only valid for replace")
        if facing == "target_object":
            if target_id not in object_ids or target_id == object_id:
                raise ValueError("target_object requires another exact object ID")
        elif target_id is not None:
            raise ValueError("target_object_id is only valid with target_object facing")
        if action == "rotate" and facing == "preserve":
            raise ValueError("rotate requires a concrete facing hint")
        return RoomObjectAdjustment(
            object_id=object_id,
            action=action,
            placement=placement,
            facing=facing,
            target_object_id=target_id,
            replacement_category=replacement_category,
            reason=str(item.get("reason", "")),
        )


__all__ = [
    "ROOM_LAYOUT_REFINEMENT_RESPONSE_SCHEMA",
    "ROOM_PROGRAM_RESPONSE_SCHEMA",
    "RoomLayoutRefinementAgent",
    "RoomLayoutRefinementPlan",
    "RoomLayoutRefinementProposal",
    "RoomObjectAdjustment",
    "RoomProgramAgent",
    "RoomProgramResult",
    "room_archetype_key",
]
