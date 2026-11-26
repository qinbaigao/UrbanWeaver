# Edit an existing city

**English** | [简体中文](editing.zh-CN.md)

UrbanWeaver edits an existing scene and saves the result as a new version. Each version records the source, the proposed changes and their validation results.

## Edit a scene

```bash
PYTHONPATH=src python -m cityg agent-edit \
  --scene outputs/city_001 \
  --instruction "Change the facade of building_03 to a glass curtain wall." \
  --output outputs/city_001_edit_01
```

Pass a run directory, `final/`, `final/openusd/`, or the canonical `city.json` as `--scene`. The editor reads the canonical city model. Replace the example ID with one that exists in your scene.

## How an edit is applied

The Edit Agent proposes a structured `EditPlan`. The deterministic executor binds each target using its ID, stable UID, full hierarchy path, or unique display name. It checks confidence, scope and entity versions, applies low-risk patches atomically to a copy through `PatchEngine`, validates semantics, geometry and interactions, then compiles OpenUSD and the portable Viewer. If “this building” or “that empty lot” matches several entities, the result is `needs_clarification`. Supply an ID or distinguish the target by location, function or adjacency.

| Edit | Scope and effect |
|---|---|
| Facade material | Change `appearance_plan.material_family`, optionally prefixed with `metadata.`, to an accepted value from `brick`, `plaster`, `stone`, `metal` or `glass`. The field is deep-merged with existing metadata. Unsupported paths return to the proposal stage within the retry budget. |
| `floor_layout` | Rebuild the rooms, doors and furniture references on one floor. |
| `building_subtree` | Rebuild a building's floor stack, vertical circulation and rooms. Elevations accumulate the actual height of each preceding floor. |
| `urban_subgraph` | Update functions, boundaries, buildings or road attributes within the selected city, district or parcel. |
| `building_profile` | Ask the Building Refinement Agent to revise permitted appearance and massing parameters. |
| `room_furnishing` | Ask the Room Program Agent to regenerate the furnishings of a bound room. |

Structural transactions require the corresponding root entity. They rebuild the Contract-Carrying World Program (CCWP) on the copy and validate the resulting scene before publication.

**Names and counts.** For an explicitly identified target, a quoted new name or a literal room count becomes a postcondition checked against the final name or non-corridor room count. The editor recognizes Arabic numerals, including English thousands separators, and phrases such as “independent offices.” Multiple explicit targets can share a per-floor count or receive individual counts in separate clauses. An undivided total across several floors requires clarification. If the model omits its target list, only explicit identifiers in the request can restore it. Floor replacements support 1–64 rooms. For a single explicit building, literal floor and per-floor room counts must also survive replacement. Building replacements support 1–128 floors. Out-of-range requests are rejected. More complex allocations and stylistic requests may need additional contracts or visual evidence.

**Furniture and repair scope.** Room edits restore the scene's pinned registry and default to local asset resolution. Prototype-specific uses of accepted furniture are retained. Whole-room rearrangements check mesh counts for major furniture classes so a renamed procedural proxy cannot stand in for an accepted mesh. Local VLM repairs bind a design group or a compiled group supported by object records one-to-one within the room. Unknown groups give no authority to change the rest of the room.

### Call a structural planner directly

```python
from cityg.subtree_transactions import FloorSubtreePlanner, BuildingSubtreePlanner, UrbanSubgraphPlanner

edited = FloorSubtreePlanner().replace(city, "building_000_floor_02", {"room_count": 12}).city
edited = BuildingSubtreePlanner().replace(edited, "building_000", {"floor_count": 18}).city
edited = UrbanSubgraphPlanner().replace(edited, "district_00", {"function": "commercial"}).city
```

A transaction returns `created_ids`, `removed_ids`, `replaced_ids`, validation results and audit metadata. Save the result as a new version. Plans may also include `asset_requests`. With `--asset-registry` the editor first searches locally. With `--generate-missing-assets` and a configured Hunyuan worker it can generate a bounded number of missing assets and bind them to identified interior objects.

### Request a visual review

```bash
PYTHONPATH=src python -m cityg agent-edit \
  --scene outputs/city_001 \
  --instruction "Inspect the facade of building_03 and fix obvious misalignment." \
  --output outputs/city_001_edit_02 \
  --visual-review --auto-vlm-refine
```

`--visual-review` captures adaptive local views and produces a report. Add `--auto-vlm-refine` to allow bounded building, room and streetscape repairs in the new version. If the VLM is unavailable, the system keeps an edit that passed deterministic validation and records the error in `visual_review_result.json`.

## Output

```text
city_001_edit_01/
├── base_scene_ref.json       # Source scene path, canonical file and hash
├── edit_request.json
├── edit_plan.json            # Model proposal and attempts
├── patch.json                # Committed low-risk patch, when applicable
├── validation_before.json
├── validation_after.json
├── edit_result.json
├── final/city.json
├── final/openusd/
└── viewer/                   # Portable Viewer, unless --no-viewer was set
```

If the input has a geometry manifest, local building, floor, room and furniture edits can reuse building-level incremental compilation. Global changes such as roads and city boundaries require full compilation. If planning exhausts its retries, the hidden `.<target>.pending-*` diagnostic directory retains `edit_plan_failure.json` (raw responses, errors, usage and prompts) and `publication_failure.json`.

## Batch edits and rollback

Supply a JSON array of strings or a file with one instruction per line:

```bash
PYTHONPATH=src python -m cityg batch-edit \
  --scene outputs/city_001 \
  --instructions-file edits.txt \
  --output outputs/city_001_batch
```

Each step is saved under `steps/step_NN/`. The batch pauses on ambiguous references or unsupported structural operations. To restore the source recorded in `base_scene_ref.json`, run:

```bash
PYTHONPATH=src python -m cityg rollback \
  --scene outputs/city_001_edit_01 \
  --output outputs/city_001_rollback
```

Pass `--to PATH` to select a different historical scene. Rollback writes another version with the selected geometry, asset bindings, facade modules and interior compilation settings. If a geometry manifest exists, rollback re-exports it directly, preserving the original decoration selection. The version covers scene state. Generator source and external asset files are managed separately.

## Move or resize a building

A `building_site` transaction can translate a building within its parcel or resize a shell, a supported furnished low-rise or a tower with verifiable floor plates. For example, ask “Move building_002 east by 0.5 m” or “Increase the footprint of building_000 to 125 m² and keep its furniture.” A furnished resize checks that the accepted furniture groups fit the revised rooms. An area-only request preserves the aspect ratio. For a tower, you can explicitly allow changing the ratio at a fixed target area if moving partitions still cannot accommodate the existing tables and chairs. See [urban spatial constraints and footprint adaptation](urban_spatial_coordination.md).
