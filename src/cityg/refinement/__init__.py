"""Selective, schema-constrained post-planning refinements."""

from cityg.refinement.building import (
    BUILDING_REFINEMENT_RESPONSE_SCHEMA,
    BuildingRefinementAgent,
    BuildingRefinementPlan,
    BuildingRefinementResult,
    apply_building_refinement,
    select_refinement_candidates,
)
from cityg.refinement.room import (
    ROOM_LAYOUT_REFINEMENT_RESPONSE_SCHEMA,
    ROOM_PROGRAM_RESPONSE_SCHEMA,
    RoomLayoutRefinementAgent,
    RoomLayoutRefinementPlan,
    RoomLayoutRefinementProposal,
    RoomObjectAdjustment,
    RoomProgramAgent,
    RoomProgramResult,
    room_archetype_key,
)
from cityg.refinement.room_layout import (
    FurnishingNonDegradationPolicy,
    RoomLayoutRefinementResult,
    apply_room_layout_refinement,
)
from cityg.refinement.streetscape import (
    STREET_VISUAL_ISSUE_CODES,
    StreetscapeRefinementResult,
    apply_streetscape_visual_refinement,
)
from cityg.refinement.selection import (
    RoomDetailCandidate,
    RoomDetailSelection,
    mark_room_detail,
    select_hero_rooms,
)

__all__ = [
    "BUILDING_REFINEMENT_RESPONSE_SCHEMA",
    "BuildingRefinementAgent",
    "BuildingRefinementPlan",
    "BuildingRefinementResult",
    "apply_building_refinement",
    "select_refinement_candidates",
    "ROOM_PROGRAM_RESPONSE_SCHEMA",
    "ROOM_LAYOUT_REFINEMENT_RESPONSE_SCHEMA",
    "RoomLayoutRefinementAgent",
    "RoomLayoutRefinementPlan",
    "RoomLayoutRefinementProposal",
    "RoomLayoutRefinementResult",
    "FurnishingNonDegradationPolicy",
    "RoomObjectAdjustment",
    "apply_room_layout_refinement",
    "STREET_VISUAL_ISSUE_CODES",
    "StreetscapeRefinementResult",
    "apply_streetscape_visual_refinement",
    "RoomProgramAgent",
    "RoomProgramResult",
    "room_archetype_key",
    "RoomDetailCandidate",
    "RoomDetailSelection",
    "mark_room_detail",
    "select_hero_rooms",
]
