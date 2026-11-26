# Urban spatial constraints and building footprint adaptation

## From a brief to a measurable requirement

The Requirement Agent records directional constraints, proximity and separation, facility service distances, and minimum building footprints in `CitySpec.urban_requirements`. The Urban Agent reads these rules during parcel allocation. The final check measures the realized buildings again.

```json
{
  "id": "homes_school_access",
  "source_quote": "Every home must be within 160 metres of at least one school.",
  "subject": "zone:residential",
  "relation": "served_by",
  "target": "zone:schools",
  "threshold": 160,
  "strength": "hard",
  "reason": "Measure the plan distance from each residential building centre to the nearest school building centre."
}
```

Use an exact zone name (`zone:<name>`), function (`function:<function>`) or building ID (`building:<ID>`). In this example the scene needs zones named `residential` and `schools`. Give specialized facilities their own named zone when a broader function such as `public_service` also includes unrelated buildings.

| Relation | Measurement |
|---|---|
| `north_half`, `south_half`, `east_half`, `west_half` | Building centre relative to the city centre. Both `target` and `threshold` are null. |
| `near`, `far`, `served_by` | Plan distance in metres from each subject to its nearest target. For a river or road, measure to the water's edge or the road boundary including sidewalks. Walking distance requires a separate route check. |
| `min_footprint_area` | Area of the planned rectangular envelope in `Building.footprint`, in m². Set `target` to null. Actual tower plates, irregular projections, usable interiors and gross floor area require their own measurements. |

For a vague request such as “near the park,” the agent proposes an explained soft threshold. Missing subjects or targets, and a subject with only itself as a target, cannot satisfy a rule. Each rule retains the source text, interpretation and entity-level results. Hard rules enter the requirements ledger, the city validator and the CCWP `urban_spatial` contract. Soft rules produce warnings and satisfaction records. Reviewing the extracted rules against the original brief can reveal omissions or misinterpretations.

## Parcel allocation and terrain conflicts

The planner swaps parcel assignments within a bounded search (up to 2,048 candidate evaluations and four scans). It first reduces hard violations, then improves soft preferences while preserving building count, functional allocation and unique parcel assignments. Parcel centres and buildable areas screen candidates. The validator repeats the checks after building generation.

If the terrain leaves too few buildable parcels, the planner tries the original road and block configuration, subdivision of legal parcels, then a more compact internal road spacing and new blocks. Each new parcel needs a buildable rectangle and road frontage. The search has at most three configuration candidates and a separate subdivision limit. If the road skeleton already failed for lack of dry land, it skips the subdivision-only retry. The site extent, requested building count, river width, banks and setbacks stay fixed throughout recovery.

When the search exhausts its candidates, the main loop records an `UrbanPlanningConflict` in `failures/urban_planning.json` and returns `replan_required`. This describes the outcome of the bounded search. Successful runs retain `geography_recovery` and `urban_spatial_assignment` in scene metadata and write `programs/urban_spatial.json` for inspection.

## Building placement and resizing

During generation, minimum footprint area participates in parcel allocation. If a building starts too small, the planner enlarges it inside the setbacks, preserves the street-facing side, then lays out its entrance, floors, rooms and core. An undersized parcel can still cause an explicit failure.

In edit mode, a `building_site` transaction accepts `area_m2`, `aspect_ratio` (width/depth), `offset_x_m` and `offset_y_m`. For example, `{"area_m2":500,"aspect_ratio":1.5,"offset_x_m":2}` requests a 500 m² footprint, a width/depth ratio of 1.5 and a two-metre shift along X. Translating a building carries its entrances, floors, core and furniture together, including for tall, rotated and irregular buildings. Metric placement records are validated before rebinding their dimensions and positions.

The interior scope and the source compilation settings determine whether a building is shell-only. For a furnished rectangular low-rise, the planner adjusts its existing partitions and tries translating furniture groups inside the revised rooms while preserving instances, assets and dimensions. It checks door clearances, functional zones, group relations and circulation in detailed rooms. Furnished towers also require checks against actual tower plates, room capacity and compiled furnishings. A failed check identifies the relevant room or constraint. Only validated edits are committed.

## Feedback across scales

The new footprint determines the available floor plate, rooms and doors. If a room cannot accommodate its original-size furniture, the Room Agent can request space from the Floor Agent using the entity, function, measured dimensions and inventory. The Floor Agent can transfer space between rooms sharing a full partition or report the limits of the current partitioning. Every trial rechecks both rooms, their doors and furniture. Checks in an accepted furnished room cover the route from the door to furniture use areas.

When the user explicitly permits changing the aspect ratio at the target area, set `allow_aspect_adjustment: true`. The Building Agent can select a new ratio in response to floor feedback and pass the revised plate down for another trial. Candidates ruled out by dimensional conflicts are excluded from subsequent rounds. The search allows up to two alternative ratios, three floors needing wall moves per round and three partition candidates per floor. Agents decide when to escalate and which candidate to try. Geometry planners instantiate and check those candidates in metres. Final acceptance checks CCWP contracts, whole-scene geometry, circulation on furnished floors and preservation of compiled furniture.

Validation covers axis-aligned setback towers with recorded plates and interiors representable as verifiable rectangular rooms and connected corridors. Slanted shells, concave interior partitions and movable cores remain outside this edit scope. Other open cases include service distance along a road network, arbitrary spatial anchors, relations between clusters or centres, and broader road–parcel replanning after all bounded candidates fail. Group-level building counts and high-rise proportions also need separate evaluation.
