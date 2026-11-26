"""End-to-end multi-view visual review and bounded local refinement.

The coordinator intentionally keeps the VLM outside the canonical write path:
it can report an issue, but only validated Building/Room agents (and the
existing PatchEngine) can commit a change.  Layout/road issues are aggregated
and persisted for a later deterministic patch instead of being guessed.
"""

from __future__ import annotations

import asyncio
import base64
import json
import math
import threading
import time
from pathlib import Path
from typing import Any

from cityg.assets import AssetRegistry, AssetResolver, MaterialLibrary
from cityg.architecture import DESIGN_LANGUAGES
from cityg.asset_providers import HunyuanAssetEndpoint, HunyuanAssetProvider
from cityg.buildings.catalog import DEFAULT_BUILDING_CATALOG
from cityg.buildings.visual_compare import run_building_visual_comparison
from cityg.ccwp import build_world_program
from cityg.geometry import GeometryCompiler
from cityg.observation import AdaptiveObservationPlanner
from cityg.planning.interiors import FloorDetailAgent
from cityg.refinement.building import BuildingRefinementAgent, apply_building_refinement
from cityg.refinement.room import RoomLayoutRefinementAgent, RoomProgramAgent
from cityg.planning.room_design import PALETTES
from cityg.refinement.room_layout import apply_room_layout_refinement
from cityg.refinement.streetscape import apply_streetscape_visual_refinement
from cityg.refinement.selection import mark_room_detail
from cityg.schemas import City
from cityg.visual_evidence import capture_signature, batch_evidence_constraints, render_evidence_ready, proxy_detail_issue, compiled_inventory_facts
from cityg.serialization import load_city, save_json
from cityg.services import OpenAICompatibleService, OpenUSDBackend
from cityg.services.interfaces import ModelEndpoint
from cityg.viewer import create_viewer_server, export_portable_viewer
from cityg.progress import progress, report_run
from cityg.visual_review import VisualReviewAgent


def _review_asset_registry(scene_path, extra_registry=None):
    """Keep package-pinned bindings; extra assets may extend, not replace them.

    The returned registry is detached, so review cannot rewrite its source
    package or the user's global registry. Resolve paths before merging.
    """
    from cityg.asset_bindings import merge_pinned_registries
    source_path = _city_path(scene_path).parent / "assets" / "asset_registry.json"
    return merge_pinned_registries(source_path, extra_registry)


def _severity_rank(value: str) -> int:
    return {"error": 3, "warning": 2, "info": 1}.get(value, 0)


def _split_entity_ids(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(item.strip() for item in value.replace(";", ",").split(",") if item.strip())


def aggregate_visual_reviews(
    plan: dict[str, Any],
    image_dir: str | Path,
    reviewer: VisualReviewAgent,
    *,
    scene_id: str = "unknown",
    batch_size: int = 4,
) -> dict[str, Any]:
    """Review selected views in bounded batches and deduplicate their issues."""
    image_root = Path(image_dir)
    status_path = image_root / 'asset_load_status.json'
    render_statuses = json.loads(status_path.read_text()).get('views', {}) if status_path.is_file() else {}
    captures = {key: capture_signature(status) for key,status in render_statuses.items()}
    views = list(plan.get("selected_views", []))
    batches: list[dict[str, Any]] = []
    followups: list[dict[str, Any]] = []
    grouped: dict[tuple, dict[str, Any]] = {}
    # Keep a room's paired views together and out of outdoor prompts. A mixed
    # final batch must not silently disable the compact production protocol.
    review_groups = {}
    for view in views:
        compact=view.get('semantic_context',{}).get('compact_room')
        key=('room',compact['room_id']) if view.get('kind')=='room_interior' and compact else ('other',)
        review_groups.setdefault(key,[]).append(view)
    width=max(1,min(batch_size,getattr(reviewer,'max_images',batch_size)))
    review_batches=[group[i:i+width] for group in review_groups.values() for i in range(0,len(group),width)]
    for batch_index, batch in enumerate(review_batches):
        progress('VLM 核对', '检查图像批次', batch=f'{batch_index+1}/{len(review_batches)}')
        evidence_constraints=batch_evidence_constraints(batch,render_statuses)
        building_review = any(view.get("kind") == "building_exterior" for view in batch)
        paths = [image_root / f"{view['view_id']}.png" for view in batch]
        view_ids = [str(view["view_id"]) for view in batch]
        pending_checks=[row for row in plan.get('issue_recheck_queue',[])
                        if set(row['assigned_view_ids']) & set(view_ids)]
        allowed_ids = sorted({
            str(entity_id)
            for view in batch
            for entity_id in view.get("target_entity_ids", [])
            if str(entity_id)
        })
        view_entity_ids = {
            str(view["view_id"]): list(view.get("target_entity_ids", []))
            for view in batch
        }
        view_semantic_context = {
            str(view["view_id"]): dict(view.get("semantic_context", {}))
            for view in batch
            if view.get("semantic_context")
        }
        # Room observation targets are ordered room -> floor -> building.
        # Publish a compact, target-local binding table so opaque IDs cannot
        # be mistaken for the accepted wall after reference rotation.
        room_group_bindings = {}
        for view in batch:
            targets=view.get('target_entity_ids',[])
            design=view.get('semantic_context',{}).get('room_design',{})
            if view.get('kind')=='room_interior' and targets and design.get('status')=='accepted':
                room_group_bindings[targets[0]]=[{
                    'group_id':g['id'],'anchor_id':g.get('anchor',{}).get('id'),
                    'accepted_placement':g.get('placement',{}),
                } for g in design.get('groups',[])]
        prompt = (
            "Review this batch of CityG observations as a scene-quality inspector. "
            "Compare views where possible. Report only visible problems in layout, "
            "roads, intersections, streetscape population, landscapes, buildings, "
            "facades, rooms, or lighting. Check that vehicles follow lanes, pedestrians "
            "stay on sidewalks, trees preserve entrances, and public spaces are neither "
            "empty nor cluttered. "
            "For rooms, compare the accepted room_design intent/zones/groups with the top and "
            "interior views. Check chair-to-own-table facing, group usability, door access, "
            "functional completeness and palette coherence. Bind problems to the room ID and "
            "name the exact group/member IDs in the description when visible. "
            "For a group-local room defect, also set target_group_ids to exact local group IDs from "
            "room_design.groups. These are affected groups, not edit permissions; independent checks determine editable scope. "
            "Omit that field for genuinely room-wide problems. "
            "Do not invent missing decoration: wall art and tabletop accents are optional, visual-only details. "
            "A group's anchor is itself a furniture instance, not an invisible placeholder. "
            "Use compiled_inventory_by_view for exact category presence in the bound compiled snapshot; "
            "do not recount inventory from pixels. Unknown or incomplete inventory cannot prove absence. "
            "These counts exclude surface decorations and certify neither loaded meshes nor visibility, "
            "usability, aesthetics, or freshness. Use images for those visual questions, and preserve "
            "uncertainty when evidence is insufficient. A present but invisible object is not missing. "
            "Consult compiled_object_ids: an unrecognized procedural proxy does not prove the "
            "object is absent. Camera occlusion does not imply blocked circulation. Soft zone "
            "positions are preferences, not hard boundaries. Require corroborating top-view "
            "evidence before claiming a wrongly oriented chair or blocked route. "
            "Use room_palette_definitions as the color contract: warm allows green accents. "
            "Procedural furniture lacks fine hardware by construction; do not request a layout "
            "repair for missing decorative mesh detail. Separate asset fidelity from arrangement. "
            "For facades use appearance_plan and adjacent_appearance_plans in view_semantic_context "
            "to check intended opening rhythm, articulation, main/service "
            "faces and contextual coherence. Do not judge nationality from appearance or demand "
            "exact window counts in global/road views: background facades are simplified in review "
            "renders; precise facade rhythm is preserved only in a targeted building view. "
            "Streaming city LOD also samples distant outdoor props; do not infer missing assets "
            "or deficient density from an overview alone. Consult renderer_status in image_evidence "
            "and require a loaded local detail view for such claims. "
            "In global review renders outdoor GLBs are proxy boxes and textures are disabled. "
            "proxy_only_entity_ids cannot support asset shape, material, facade-detail or furnishing "
            "defect claims; request local inspection instead. Loaded proxies are not loaded detailed assets. "
            "Use design_language_definitions as the contract, not your own interpretation of the ID: "
            "solid_punched does not require irregular placement; framed_grid does not constrain massing; "
            "shaded_bays requires visible solar hoods, not recessed geometry. If the target is occluded "
            "or too small, do not assert a style mismatch with high confidence. "
            "Images follow image_evidence order exactly. Do not transfer a material, era or "
            "language from another image's target. The accepted target contract is authoritative. "
            "Do not demand "
            "unsupported historical roofs. Report visible design-language mismatches with a "
            "concrete suggested adjustment. Bind an issue only to "
            "an exact ID from allowed_entity_ids. Return entity_id=null when the "
            "view does not support a reliable binding; never invent IDs. Return "
            "entity_type, confidence, binding_confidence, binding_basis, and up "
            "to four candidate_entity_ids when ambiguity remains. For a bound "
            "room that visibly lacks a concrete furnishing, optionally return up "
            "to four asset_requests with a semantic category, count, and short "
            "description; do not request hidden or unverifiable objects. For a "
            "building/facade issue, optionally rank up to four compatible "
            "candidate_archetype_ids from allowed_archetype_ids based on the "
            "visible facade and surrounding context; never invent an ID. For an exact "
            "road-bound issue, set category=road, entity_type=road, and choose issue_code "
            "from street_underfurnished, street_overcrowded, frontage_disconnect, "
            "cross_section_conflict, street_asset_repetition, vegetation_overdensity, "
            "traffic_implausible, or road_intrusion. For room-bound issues use room_function_incomplete, "
            "room_group_misaligned, room_access_blocked, or room_style_incoherent where applicable. "
            "Otherwise use issue_code=unspecified."
        )
        review_context = {
                **evidence_constraints,
                "scene_id": scene_id,
                "pending_issue_checks": pending_checks,
                "room_group_bindings": room_group_bindings,
                "room_palette_definitions": PALETTES,
                "design_language_definitions": DESIGN_LANGUAGES,
                "image_evidence": [
                    {"image_index": index + 1, "view_id": view["view_id"],
                     "target_entity_ids": view.get("target_entity_ids", []),
                     "renderer_status": render_statuses.get(str(view['view_id']), {}),
                     "semantic_context": view.get("semantic_context", {})}
                    for index, view in enumerate(batch)
                ],
                "view_ids": view_ids,
                "view_kinds": [v.get("kind") for v in batch],
                "allowed_entity_ids": allowed_ids,
                "view_entity_ids": view_entity_ids,
                "view_semantic_context": view_semantic_context,
                "compiled_inventory_by_view": {str(v['view_id']):compiled_inventory_facts(v)
                                               for v in batch if v.get('kind')=='room_interior'},
                "allowed_archetype_ids": [
                    item.archetype_id for item in DEFAULT_BUILDING_CATALOG if building_review
                ],
                "archetype_catalog": [
                    {
                        "archetype_id": item.archetype_id,
                        "family": item.family,
                        "massing_style": item.massing_style,
                        "massing_signature": item.massing_signature,
                        "compatible_functions": list(item.compatible_functions),
                        "facade_style_ids": list(item.facade_style_ids),
                    }
                    for item in DEFAULT_BUILDING_CATALOG
                    if building_review
                ],
                "entity_binding_rule": "exact_allowed_id_only",
                "archetype_binding_rule": "exact_catalog_id_only",
            }
        from cityg.room_review_context import compact_review_request
        prompt, review_context = compact_review_request(prompt, review_context, batch)
        result = reviewer.review(prompt, paths, context=review_context)
        batch_record = result.to_dict()
        progress('VLM 核对', '批次完成', available=result.available, issues=len(result.issues), attempts=len(result.attempts))
        batch_record["view_ids"] = view_ids
        batches.append(batch_record)
        checks={r['issue_key']:r for r in pending_checks}
        for row in result.issue_followups:
            check=checks[row['issue_key']]
            comparable={c['view_id'] for c in check['candidates'] if c['comparable_camera']
                        and c.get('source_capture_signature')
                        and c['source_capture_signature'] == captures.get(c['view_id'])}
            evidence=row['evidence_view_ids']
            ready=all(render_evidence_ready(render_statuses.get(v,{})) for v in evidence)
            followups.append({**row,'entity_id':check['entity_id'],
                'expected_entity_version':check['expected_entity_version'],
                'comparable_loaded_evidence':ready and set(evidence)<=comparable,
                'verified_resolved':False})
        for issue in result.issues:
            exact_ids = _split_entity_ids(issue.entity_id)
            candidate_ids = tuple(
                item for item in issue.candidate_entity_ids if item in allowed_ids
            )
            allowed_archetypes = {
                item.archetype_id for item in DEFAULT_BUILDING_CATALOG
            }
            candidate_archetypes = tuple(
                item
                for item in issue.candidate_archetype_ids
                if item in allowed_archetypes
            )
            # Promote one unambiguous, high-confidence candidate; multiple
            # candidates stay ambiguous and are not sent to a repair agent.
            if not exact_ids and len(candidate_ids) == 1 and issue.binding_confidence >= 0.85:
                exact_ids = candidate_ids
            bound_ids = tuple(item for item in exact_ids if item in allowed_ids)
            entities = bound_ids or (None,)
            for entity_id in entities:
                # Recheck after candidate-ID promotion too; an unbound model
                # issue must not bypass target-local renderer readiness.
                if entity_id in evidence_constraints['unready_entity_ids']:
                    batch_record.setdefault('deferred_issues',[]).append({
                        **issue.__dict__,'entity_id':entity_id,'automatic_repair_allowed':False,
                        'deferred_reason':'render_evidence_not_ready_after_binding'})
                    continue
                if proxy_detail_issue(issue,evidence_constraints,entity_id):
                    batch_record.setdefault('deferred_issues',[]).append({
                        **issue.__dict__,'entity_id':entity_id,'automatic_repair_allowed':False,
                        'deferred_reason':'proxy_overview_requires_local_detail_evidence'})
                    continue
                key = (
                    issue.category,
                    entity_id or "",
                    issue.issue_code, tuple(sorted(issue.target_group_ids)), tuple(sorted(issue.target_object_ids)),
                    " ".join(issue.description.lower().split()),
                )
                item = grouped.setdefault(
                    key,
                    {
                        "issue_id": issue.issue_id,
                        "severity": issue.severity,
                        "category": issue.category,
                        "issue_code": issue.issue_code,
                        "entity_id": entity_id,
                        "description": issue.description,
                        "suggested_action": issue.suggested_action,
                        "entity_type": issue.entity_type,
                        "confidence": issue.confidence,
                        "binding_confidence": issue.binding_confidence if entity_id else 0.0,
                        "binding_basis": issue.binding_basis if entity_id else "none",
                        "candidate_entity_ids": list(candidate_ids),
                        "candidate_archetype_ids": list(candidate_archetypes),
                        "target_group_ids": list(issue.target_group_ids),
                        "target_object_ids": list(issue.target_object_ids),
                        "asset_requests": list(issue.asset_requests),
                        "binding_status": "exact" if entity_id else (
                            "ambiguous" if candidate_ids else "unbound"
                        ),
                        "evidence_view_ids": [],
                        "occurrences": 0,
                        "automatic_repair_allowed": False,
                    },
                )
                item["severity"] = (
                    issue.severity
                    if _severity_rank(issue.severity) > _severity_rank(item["severity"])
                    else item["severity"]
                )
                item["occurrences"] += 1
                # Do not combine high issue confidence from one observation
                # with high binding confidence from another weak observation.
                item['automatic_repair_allowed'] |= bool(entity_id and
                    issue.confidence >= .65 and issue.binding_confidence >= .72)
                item["target_group_ids"] = sorted(set(item.get("target_group_ids",[])) | set(issue.target_group_ids))
                item["target_object_ids"] = sorted(set(item.get("target_object_ids",[])) | set(issue.target_object_ids))
                item["confidence"] = max(item["confidence"], issue.confidence)
                if item.get("issue_code") == "unspecified" and issue.issue_code != "unspecified":
                    item["issue_code"] = issue.issue_code
                item["binding_confidence"] = max(
                    item["binding_confidence"], issue.binding_confidence if entity_id else 0.0
                )
                item["candidate_entity_ids"] = sorted(
                    set(item["candidate_entity_ids"]) | set(candidate_ids)
                )
                item["candidate_archetype_ids"] = sorted(
                    set(item.get("candidate_archetype_ids", []))
                    | set(candidate_archetypes)
                )
                item["asset_requests"] = _merge_asset_requests(
                    item.get("asset_requests", []), issue.asset_requests
                )
                item["binding_status"] = "exact" if entity_id else item["binding_status"]
                evidence = [
                    view_id for view_id, ids in view_entity_ids.items()
                    if entity_id is None or entity_id in ids
                ] or view_ids
                item["evidence_view_ids"] = sorted(
                    set(item["evidence_view_ids"]) | set(evidence)
                )
    issues = sorted(
        grouped.values(),
        key=lambda item: (-_severity_rank(item["severity"]), item["category"], item["entity_id"] or ""),
    )
    available_batches = sum(bool(item.get("available")) for item in batches)
    return {
        "scene_id": scene_id,
        "status": ("complete" if batches and available_batches == len(batches)
                   else "partial" if available_batches else "unavailable"),
        "batch_size": max(1, batch_size),
        "batch_count": len(batches),
        "batches": batches,
        "aggregated_issues": issues,
        "deferred_issues": [issue for batch in batches for issue in batch.get('deferred_issues',[])],
        "requires_manual_review": any(batch.get('deferred_issues') for batch in batches),
        "available_batches": available_batches,
        "capture_signatures": captures,
        "issue_followups": followups,
    }


def _merge_asset_requests(
    current: list[dict[str, Any]],
    incoming: tuple[dict[str, Any], ...] | list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge small VLM asset hints without allowing an unbounded list."""
    merged: dict[str, dict[str, Any]] = {
        str(item.get("category")): dict(item)
        for item in current
        if item.get("category")
    }
    for item in incoming:
        category = str(item.get("category", ""))
        if not category:
            continue
        if category in merged:
            merged[category]["count"] = min(
                4,
                max(int(merged[category].get("count", 1)), int(item.get("count", 1))),
            )
        else:
            merged[category] = {
                "category": category,
                "count": min(4, max(1, int(item.get("count", 1)))),
                "description": str(item.get("description", "")),
            }
    return [merged[key] for key in sorted(merged)[:4]]


def route_visual_issues(city: City, report: dict[str, Any]) -> dict[str, Any]:
    """Route only addressable, known, sufficiently confident entities."""
    buildings = {building.id for building in city.iter_buildings()}
    rooms = {room.id for room in city.iter_rooms()}
    roads = {road.id for road in city.road_network.segments}
    building_ids: dict[str, dict[str, Any]] = {}
    room_ids: dict[str, dict[str, Any]] = {}
    road_ids: dict[str, dict[str, Any]] = {}
    deferred: list[dict[str, Any]] = []
    for issue in report.get("aggregated_issues", []):
        entity_id = issue.get("entity_id")
        category = str(issue.get("category", "unknown"))
        def trusted_score(field, minimum):
            value = issue.get(field, 0.0)
            return (type(value) in (int, float) and math.isfinite(value)
                    and minimum <= value <= 1)
        binding_ok = trusted_score("binding_confidence", 0.72)
        observation_ok = (trusted_score("confidence", 0.65)
                          and issue.get('automatic_repair_allowed') is not False)
        entity_type = str(issue.get("entity_type", "unknown"))
        building_type_ok = entity_type in {"unknown", "building"}
        room_type_ok = entity_type in {"unknown", "room"}
        road_type_ok = entity_type in {"unknown", "road"}
        if (
            entity_id in buildings
            and category in {"building", "facade"}
            and binding_ok and observation_ok
            and building_type_ok
        ):
            building_ids.setdefault(entity_id, issue)
        elif (
            entity_id in rooms
            and entity_type in {"room", "unknown"}
            and binding_ok and observation_ok
            and room_type_ok
        ):
            room_ids.setdefault(entity_id, issue)
        elif (
            entity_id in roads
            and category in {"road", "population", "layout"}
            and binding_ok and observation_ok
            and road_type_ok
        ):
            road_ids.setdefault(entity_id, issue)
        else:
            deferred_issue = dict(issue)
            deferred_issue["route_reason"] = (
                "independent_room_check_not_confirmed"
                if issue.get('independent_verification',{}).get('status') in {'unverified','not_supported_by_geometry'}
                else "unknown_entity"
                if entity_id not in buildings and entity_id not in rooms and entity_id not in roads
                and entity_id is not None
                else "unsupported_entity_type"
                if entity_type not in {"unknown", "building", "room", "road"}
                else "low_binding_confidence_or_type_mismatch"
                if not binding_ok
                else "low_or_missing_issue_confidence"
                if not observation_ok
                else "low_binding_confidence_or_type_mismatch"
            )
            deferred.append(deferred_issue)
    return {
        "building_refinement_ids": sorted(building_ids),
        "room_refinement_ids": sorted(room_ids),
        "streetscape_refinement_ids": sorted(road_ids),
        "deferred_patch_issues": deferred,
        "routing_policy": "known_entity_and_dual_confidence_v4",
    }


def _city_path(scene: Path) -> Path:
    candidate = scene if scene.is_file() else scene / "city.json"
    if not candidate.is_file():
        raise ValueError(f"scene does not contain city.json: {scene}")
    return candidate


def _geometry_manifest(scene: Path) -> dict[str, Any] | None:
    path = _city_path(scene).parent / "geometry_manifest.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid geometry manifest: {path}") from error


def _interiors_compiled(scene: Path) -> bool:
    manifest = _geometry_manifest(scene) or {}
    metadata = manifest.get("metadata", {}) if isinstance(manifest, dict) else {}
    return bool(metadata.get("interiors_compiled", True))


async def _render_plan(
    url: str,
    plan: dict[str, Any],
    output_dir: Path,
    *,
    wait_ms: int = 350,
    asset_timeout_ms: int = 60_000,
) -> list[str]:
    try:
        from playwright.async_api import async_playwright
    except ImportError as error:  # pragma: no cover - environment-dependent
        raise RuntimeError("Playwright is required for adaptive review rendering") from error
    views = list(plan.get("selected_views", []))
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    asset_statuses: dict[str, dict[str, Any]] = {}
    started=time.monotonic(); timings=[]
    progress('截图', '启动无头浏览器并加载场景', phase=output_dir.name, views=len(views))
    launch_args = ["--disable-dev-shm-usage", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True, args=launch_args)
        # Keep one generation-scoped Viewer page. Loading every GLB/PBR asset
        # again for every camera is both expensive and, with SwiftShader, can
        # exhaust the rasterizer on the second page. Camera changes remain
        # isolated by the narrow setView contract and every capture still waits
        # for the Viewer asset barrier.
        page = await browser.new_page(
            viewport={"width": 1200, "height": 800}, device_scale_factor=1
        )
        try:
            if views:
                await page.add_init_script(
                    "window.__CITYG_INITIAL_OBSERVATION_VIEW__ = "
                    + json.dumps(views[0], ensure_ascii=False)
                    + "; window.__CITYG_RENDER_PROFILE__ = 'review';"
                )
            await page.goto(url, wait_until="commit", timeout=60000)
            await page.wait_for_function(
                "window.citygObservation && window.citygObservation.ready",
                timeout=180000,
            )
            # Resolve the stable canvas rectangle before a very large scene
            # can occupy the renderer main thread for tens of seconds. The
            # rectangle stays constant across observation views and lets the
            # compositor fallback avoid a second Locator lookup entirely.
            canvas = page.locator("#scene-canvas")
            locator_timeout_ms = max(60_000, asset_timeout_ms)
            await canvas.wait_for(state="attached", timeout=locator_timeout_ms)
            canvas_box = await canvas.bounding_box(timeout=locator_timeout_ms)
            if not canvas_box:
                raise RuntimeError("Viewer scene-canvas has no renderable bounds")
            for view_index, view in enumerate(views, 1):
                progress('截图', '切换视点并等待资产', view=f'{view_index}/{len(views)}', target=view['view_id'])
                view_started=time.monotonic()
                from cityg.observation import fit_capture_view
                effective_view=fit_capture_view(view,width=canvas_box['width'],height=canvas_box['height'])
                view_status = await page.evaluate(
                    "(view) => window.citygObservation.setView(view)", effective_view
                )
                if view.get("kind") == "room_interior" and view_status.get("visible_primitive_count",0) == 0:
                    raise RuntimeError(f"Room observation is empty: {view['view_id']}; refusing blank-image review")
                switched=time.monotonic()
                asset_status = await page.evaluate(
                    """async (options) => {
                        if (!window.citygObservation?.waitForAssets) {
                            return { ready: true, signal_available: false };
                        }
                        const status = await window.citygObservation.waitForAssets(options);
                        return { ...status, signal_available: true };
                    }""",
                    {"timeout_ms": max(100, asset_timeout_ms), "quiet_ms": 180},
                )
                asset_statuses[str(view["view_id"])] = {
                    **dict(asset_status),
                    "view_status": dict(view_status),
                    "capture_camera": {k:effective_view[k] for k in ('camera_position','look_at','up','fov_deg')},
                    "capture_canvas": {k:canvas_box[k] for k in ('width','height')},
                }
                # Preserve the last completed asset barrier even if a later
                # GPU readback or camera fails; ready proxies and real GLBs
                # remain distinguishable in partial-run diagnostics.
                save_json({"policy":"viewer_generation_scoped_asset_barrier_v1", "views":asset_statuses},
                          output_dir / "asset_load_status.json")
                if not asset_status.get("ready"):
                    raise RuntimeError(
                        f"Viewer assets did not become ready for {view['view_id']}: "
                        f"{asset_status}"
                    )
                assets_ready=time.monotonic()
                await page.wait_for_timeout(max(0, wait_ms))
                destination = output_dir / f"{view['view_id']}.png"
                # Read the WebGL canvas directly. Playwright's page screenshot
                # can stall inside Chromium's compositor for large SwiftShader
                # scenes even after fonts and the viewer are fully ready.
                data_url = None
                for _ in range(20):
                    # Query the current DOM node inside the page. Three.js may
                    # replace the canvas while assets finish loading, which
                    # makes a Playwright Locator's element handle stale.
                    try:
                        data_url = await asyncio.wait_for(
                            page.evaluate(
                                """() => window.citygObservation?.captureFrame
                                    ? window.citygObservation.captureFrame()
                                    : document.querySelector('#scene-canvas')?.toDataURL('image/png')"""
                            ),
                            timeout=30.0,
                        )
                    except asyncio.TimeoutError:
                        # CDP compositor capture is slower but avoids an
                        # unbounded WebGL readback on some SwiftShader scenes.
                        # Use the cached canvas rectangle: resolving a Locator
                        # while the renderer is busy with a 100k+ primitive
                        # frame can itself exhaust Playwright's 30 s default.
                        await page.screenshot(
                            path=str(destination),
                            clip=canvas_box,
                            timeout=locator_timeout_ms,
                        )
                        paths.append(str(destination))
                        data_url = "captured_by_compositor"
                        break
                    if data_url:
                        break
                    await page.wait_for_timeout(250)
                if not data_url:
                    raise RuntimeError("Viewer scene-canvas was not ready for screenshot")
                if data_url != "captured_by_compositor":
                    destination.write_bytes(base64.b64decode(data_url.split(",", 1)[1]))
                    paths.append(str(destination))
                timings.append({'view_id':view['view_id'],'set_view_s':round(switched-view_started,4),
                    'asset_barrier_s':round(assets_ready-switched,4),
                    'capture_s':round(time.monotonic()-assets_ready,4),
                    'capture_backend':'compositor' if data_url=='captured_by_compositor' else 'canvas'})
                save_json({'elapsed_s':round(time.monotonic()-started,4),'views':timings,
                           'page_reused':True},output_dir/'capture_timings.json')
                progress('截图', '图像已保存', view=f'{view_index}/{len(views)}', elapsed_s=f'{time.monotonic()-view_started:.1f}')
        finally:
            await page.close()
        await browser.close()
    save_json(
        {
            "policy": "viewer_generation_scoped_asset_barrier_v1",
            "views": asset_statuses,
        },
        output_dir / "asset_load_status.json",
    )
    return paths


def _start_server(scene: Path, port: int) -> tuple[Any, threading.Thread, str]:
    server, url, _ = create_viewer_server(scene, host="127.0.0.1", port=port)
    thread = threading.Thread(target=server.serve_forever, name=f"cityg-viewer-{port}", daemon=True)
    thread.start()
    return server, thread, url


def _local_recheck_plan(
    city: City,
    touched: set[str],
    max_views: int,
    *,
    geometry_manifest: object | None = None,
) -> dict[str, Any]:
    """Build a compact post-patch plan focused on touched entities.

    One global context view is retained when possible; all remaining selected
    views must target a changed building or room.  If no patch was committed,
    the ordinary bounded plan is used for a before/after smoke comparison.
    """
    plan = AdaptiveObservationPlanner(max_views=max_views).plan(
        city,
        risk_entity_ids=touched,
        geometry_manifest=geometry_manifest,
    ).to_dict()
    if not touched:
        return plan
    selected = list(plan.get("selected_views", []))
    candidates = list(plan.get("candidates", []))
    local: list[dict[str, Any]] = []
    # Guarantee one deterministic pre-existing candidate for every changed
    # entity before adding secondary angles. This prevents two directions of
    # one road from starving another changed road in a bounded recheck.
    for entity_id in sorted(touched):
        matches = [
            view
            for view in candidates
            if view.get("kind") != "global"
            and entity_id in view.get("target_entity_ids", [])
        ]
        matches.sort(
            key=lambda view: (
                0 if str(view.get("view_id", "")).endswith("_road_a") else 1,
                0 if str(view.get("view_id", "")).endswith("_exterior_00") else 1,
                0 if str(view.get("view_id", "")).endswith("_top_00") else 1,
                str(view.get("view_id", "")),
            )
        )
        if matches and all(matches[0].get("view_id") != item.get("view_id") for item in local):
            local.append(matches[0])
    for view in selected:
        if view.get("kind") == "global":
            continue
        if not set(view.get("target_entity_ids", [])) & touched:
            continue
        if all(view.get("view_id") != item.get("view_id") for item in local):
            local.append(view)
    context = next((view for view in selected if view.get("kind") == "global"), None)
    if context is not None:
        local.insert(0, context)
    plan["selected_views"] = local[:max(1, max_views)]
    plan["max_views"] = len(plan["selected_views"])
    return plan


@report_run('视觉闭环')
def run_adaptive_review(scene, output, *, memory_store_path=None, **options):
    from cityg.memory import MemoryStore
    from contextlib import ExitStack
    with ExitStack() as stack:
        # Open the database only after input/config/output preflight. Opening
        # it earlier makes an otherwise empty output fail its own emptiness gate.
        return _run_adaptive_review(scene, output,
            memory_factory=lambda root: stack.enter_context(MemoryStore(
                memory_store_path or root/'memory.sqlite')), **options)


def _run_adaptive_review(
    scene: str | Path,
    output: str | Path,
    *,
    base_url: str = "http://127.0.0.1:8000/v1",
    model: str = "cityg-llm",
    timeout: float = 180.0,
    max_tokens: int = 1024,
    viewer_port: int = 5210,
    asset_load_timeout: float = 180.0,
    max_views: int = 10,
    max_building_refinements: int = 2,
    max_room_refinements: int = 2,
    max_room_layout_refinements: int = 1,
    max_streetscape_refinements: int = 2,
    enable_archetype_contact_sheets: bool = True,
    max_archetype_candidates: int = 4,
    batch_size: int = 4,
    seed: int = 17,
    asset_registry: str | Path | None = None,
    facade_asset_index: str | Path | None = None,
    generate_missing_assets: bool = False,
    asset_url: str = "http://127.0.0.1:8091",
    asset_timeout: float = 1800.0,
    max_generated_assets: int = 4,
    asset_texture: bool = True,
    memory_store=None,
    memory_factory=None,
) -> dict[str, Any]:
    """Run screenshot -> VLM -> route -> local refine -> local re-render."""
    if (
        max_room_refinements < 0
        or max_building_refinements < 0
        or max_room_layout_refinements < 0
        or max_streetscape_refinements < 0
    ):
        raise ValueError("refinement budgets must be non-negative")
    if not 1 <= max_archetype_candidates <= 4:
        raise ValueError("max_archetype_candidates must be within [1, 4]")
    if max_generated_assets < 0:
        raise ValueError("max_generated_assets must be non-negative")
    if asset_load_timeout <= 0:
        raise ValueError("asset_load_timeout must be positive")
    scene_path = Path(scene).expanduser().resolve()
    if facade_asset_index is not None and not Path(facade_asset_index).is_file():
        raise ValueError(f'Facade asset index does not exist: {facade_asset_index}')
    before_geometry = _geometry_manifest(scene_path)
    if (before_geometry and before_geometry.get('metadata', {}).get('facade_asset_system_enabled')
            and facade_asset_index is None):
        raise ValueError('Source scene uses facade assets; pass --facade-asset-index to preserve them during review recompilation')
    city = load_city(_city_path(scene_path))
    root = Path(output).expanduser().resolve()
    if root.exists() and any(root.iterdir()):
        raise ValueError(f'adaptive review output must be empty: {root}')
    root.mkdir(parents=True, exist_ok=True)
    from cityg.run_provenance import record_stage_start
    record_stage_start(root)
    if memory_factory is not None:
        memory_store = memory_factory(root)
    hero_room_ids = tuple(
        room.id for room in city.iter_rooms()
        if room.metadata.get("detail_tier") == "hero"
    )
    before_plan = AdaptiveObservationPlanner(max_views=max_views).plan(
        city,
        risk_entity_ids=hero_room_ids,
        geometry_manifest=before_geometry,
    )
    del before_geometry  # Do not retain the full large-scene manifest during VLM/recompile.
    before_plan_path = save_json(before_plan.to_dict(), root / "observation_plan_before.json")
    progress('观察规划', '已选择多尺度视点', selected=len(before_plan.selected_views))
    server, thread, url = _start_server(scene_path, viewer_port)
    try:
        before_images = asyncio.run(
            _render_plan(
                url,
                before_plan.to_dict(),
                root / "observations_before",
                asset_timeout_ms=int(asset_load_timeout * 1000),
            )
        )
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)

    endpoint = ModelEndpoint(base_url=base_url, model=model, timeout_s=timeout, max_tokens=max_tokens, enable_thinking=False)
    service = OpenAICompatibleService(endpoint)
    review = aggregate_visual_reviews(before_plan.to_dict(), root / "observations_before", VisualReviewAgent(service, max_images=batch_size), scene_id=city.id, batch_size=batch_size)
    from cityg.validation.visual_grounding import ground_review, resolution_proofs
    from cityg.issue_rechecks import issue_key
    review = ground_review(city, review, memory_store=memory_store)
    from cityg.review_memory import record_observations, bounded_review_outcome
    evidence_records = record_observations(memory_store, city, before_plan.to_dict(),
                                           root/'observations_before', stage='before')
    route = route_visual_issues(city, review)
    progress('问题分流', '按独立核验和预算选择修复；未绑定问题不自动修改',
             issues=len(review.get('aggregated_issues', [])))
    selected_buildings = route["building_refinement_ids"][: max(0, max_building_refinements)]
    routed_rooms = route["room_refinement_ids"]
    # When the scene declares a hero budget, visual feedback is restricted to
    # those rooms.  This prevents a large proxy-only city from turning a single
    # review into an unbounded room-agent pass.
    if hero_room_ids:
        hero_set = set(hero_room_ids)
        routed_rooms = [room_id for room_id in routed_rooms if room_id in hero_set]
    selected_rooms = routed_rooms[: max(0, max_room_refinements)]
    selected_streets = route["streetscape_refinement_ids"][
        : max(0, max_streetscape_refinements)
    ]
    traces: dict[str, Any] = {
        "streetscape": [],
        "building_visual_comparison": [],
        "building": [],
        "room": [],
        "room_layout": [],
    }
    touched: set[str] = set()
    current = city
    street_issues = [
        item
        for item in review.get("aggregated_issues", [])
        if item.get("entity_id") in selected_streets
    ]
    if street_issues:
        progress('街景修复', '检查局部街景候选', roads=len(selected_streets))
        try:
            streetscape_result = apply_streetscape_visual_refinement(
                current, street_issues, max_roads=max_streetscape_refinements,
                memory_store=memory_store)
            current = streetscape_result.city
            touched.update(streetscape_result.changed_road_ids)
            traces["streetscape"].append(streetscape_result.trace_dict())
        except Exception as error:
            traces['streetscape'].append({'road_id':selected_streets[0] if selected_streets else None,
                                         'error':f'{type(error).__name__}: {error}'})
    building_agent = BuildingRefinementAgent(service, model_id=model, max_attempts=2,
                                             memory_store=memory_store)
    issue_by_building: dict[str, dict[str, Any]] = {}
    for item in review.get("aggregated_issues", []):
        building_id = str(item.get("entity_id"))
        if building_id in selected_buildings:
            issue_by_building.setdefault(
                building_id,
                {"building_id": building_id, "issues": []},
            )["issues"].append({
                "category": item.get("category"),
                "severity": item.get("severity"),
                "description": item.get("description"),
                "suggested_action": item.get("suggested_action"),
                "confidence": item.get("confidence"),
                "candidate_archetype_ids": item.get("candidate_archetype_ids", []),
            })
    registry = _review_asset_registry(scene_path, asset_registry)
    material_path = _city_path(scene_path).parent / "assets" / "material_library.json"
    materials = MaterialLibrary(material_path) if material_path.is_file() else None
    room_compiler = GeometryCompiler(asset_registry=registry, material_library=materials,
        include_interiors=_interiors_compiled(scene_path),
        facade_asset_index_path=str(facade_asset_index) if facade_asset_index else None)
    for building_id in selected_buildings:
        progress('建筑修复', '检查候选原型、外观与局部事务', building=building_id)
        feedback = issue_by_building.get(building_id)
        if enable_archetype_contact_sheets:
            preferred_ids = tuple(
                dict.fromkeys(
                    archetype_id
                    for issue in (feedback or {}).get("issues", [])
                    for archetype_id in issue.get("candidate_archetype_ids", [])
                    if archetype_id
                )
            )
            try:
                comparison = run_building_visual_comparison(
                    current,
                    building_id,
                    root / "archetype_contact_sheets" / building_id,
                    service,
                    source_scene_root=_city_path(scene_path).parent,
                    max_candidates=max_archetype_candidates,
                    preferred_ids=preferred_ids,
                    visual_feedback=feedback,
                    viewer_port=0,
                )
                comparison_record = comparison.to_dict()
            except Exception as error:
                comparison_record = {
                    "available": False,
                    "building_id": building_id,
                    "error": f"{type(error).__name__}: {error}",
                }
            traces["building_visual_comparison"].append(comparison_record)
            feedback = dict(feedback or {"building_id": building_id, "issues": []})
            feedback["contact_sheet_comparison"] = comparison_record
        try:
            plan, attempts = building_agent.propose(
                current,
                building_id,
                visual_feedback=feedback,
            )
            from cityg.validation.local_room import building_compilation_gate
            result = apply_building_refinement(current, plan, attempts=attempts, model_id=model,
                memory_store=memory_store,
                compiled_gate=building_compilation_gate(current, building_id, room_compiler))
            current = result.city
            touched.add(building_id)
            traces["building"].append(result.trace_dict())
        except Exception as error:
            traces["building"].append({"building_id": building_id, "error": f"{type(error).__name__}: {error}"})

    room_index = {room.id: (building, floor, room) for building in current.iter_buildings() for floor in building.floors for room in floor.rooms}
    issue_by_room: dict[str, dict[str, Any]] = {}
    for item in review.get("aggregated_issues", []):
        room_id = str(item.get("entity_id"))
        if room_id not in selected_rooms or item.get('automatic_repair_allowed') is False:
            continue
        existing = issue_by_room.setdefault(
            room_id,
            {"room_id": room_id, "issues": []},
        )
        existing["issues"].append({
            "category": item.get("category"),
            "severity": item.get("severity"),
            "description": item.get("description"),
            "suggested_action": item.get("suggested_action"),
            "confidence": item.get("confidence"),
            "asset_requests": item.get("asset_requests", []),
            "target_group_ids": item.get("editable_group_ids", []),
            "affected_group_ids": item.get("target_group_ids", []),
            "target_object_ids": item.get("target_object_ids", []),
            "independent_verification": item.get("independent_verification"),
        })
        # Freeze non-target groups only when every issue has a local scope.
        # Unknown IDs are deliberately passed through for fail-closed checking
        # by RoomProgramAgent, never silently widened into a whole-room edit.
        if all(i.get("target_group_ids") for i in existing["issues"]):
            existing["target_group_ids"] = sorted({g for i in existing["issues"] for g in i["target_group_ids"]})
        else:
            existing.pop("target_group_ids",None)
    asset_resolver = None
    if registry.list_all():
        providers = ()
        if generate_missing_assets and max_generated_assets > 0:
            providers = (
                HunyuanAssetProvider(
                    HunyuanAssetEndpoint(
                        base_url=asset_url,
                        timeout_s=asset_timeout,
                        request_texture=asset_texture,
                    )
                ),
            )
        asset_resolver = AssetResolver(
            registry,
            providers,
            max_provider_calls=max(0, max_generated_assets) if generate_missing_assets else 0,
            strict_provider_errors=False,
        )
    room_agent = RoomProgramAgent(service, model_id=model, max_attempts=2,
                                  asset_resolver=asset_resolver, placement_seed=seed,
                                  memory_store=memory_store)
    for room_id in selected_rooms:
        progress('房间修复', '规划、预检与事务验收', room=room_id)
        target = next(((b, f, r) for b in current.iter_buildings() for f in b.floors
                       for r in f.rooms if r.id == room_id), None)
        if target is None:
            continue
        building, floor, room = target
        program_result = None
        repair_guard = None
        try:
            from cityg.refinement.room_preflight import prepare_preflight
            from cityg.refinement.room_repair_guard import RoomRepairGuard
            repair_issues=[i for i in review.get('aggregated_issues',[])
                           if i.get('entity_id')==room_id and i.get('automatic_repair_allowed')]
            repair_guard=RoomRepairGuard(current,room_id,repair_issues)
            support_context, preflight, compiled_gate = prepare_preflight(
                current, room_id, room_compiler, registry, seed=seed,repair_guard=repair_guard)
            feedback={**(issue_by_room.get(room_id) or {}),**repair_guard.feedback(),
                      'compiled_support_context':support_context}
            program_result = room_agent.propose(
                current,
                building,
                floor,
                room,
                use_cache=False,
                visual_feedback=feedback,
                compiled_preflight=preflight,
            )
            from cityg.refinement.room_commit import commit_room_program
            from cityg.validation.local_room import room_compilation_gate
            committed, stats = commit_room_program(current, room_id, program_result.program,
                asset_resolver=asset_resolver, seed=seed,
                memory_store=memory_store,
                compiled_gate=compiled_gate)
            current = committed.city
            if committed.report['status'] == 'accepted':
                touched.add(room_id)
            traces["room"].append({
                "room_id": room_id,
                "program": program_result.raw,
                "stats": stats,
                "transaction": committed.report,
                "visual_feedback": issue_by_room.get(room_id),
                "repair_issue_keys": [issue_key(i) for i in repair_issues],
                "editable_group_ids": repair_guard.editable,
                "repair_contract_check": repair_guard(committed.city),
            })
        except Exception as error:
            traces["room"].append({"room_id": room_id, "error": f"{type(error).__name__}: {error}"})
            # Retry only a concrete proposed program that failed feasibility;
            # model/service failure is not grounds for a larger scene edit.
            from cityg.repair import PatchRejected
            if repair_guard is not None and program_result is not None and isinstance(error,(PatchRejected,ValueError)):
                from cityg.refinement.room_commit import negotiate_room_program
                from cityg.validation.local_room import room_compilation_gate
                replanner=RoomProgramAgent(service,model_id=model,max_attempts=1,
                    asset_resolver=asset_resolver,placement_seed=seed,memory_store=memory_store)
                retry_records=[]
                def revised_program(draft,conflict):
                    b,f,r=next((b,f,r) for b in draft.iter_buildings() for f in b.floors
                               for r in f.rooms if r.id==room_id)
                    feedback={**(issue_by_room.get(room_id) or {}),
                        **repair_guard.feedback(),
                        'compiled_conflict':conflict,
                        'instruction':'Revise only this room. Preserve accepted inventory and asset scales. '
                            'Do not repeat the infeasible support/spacing request; propose a feasible alternative.'}
                    context, retry_preflight, _=prepare_preflight(draft,room_id,room_compiler,registry,
                        seed=seed,repair_guard=repair_guard)
                    feedback['compiled_support_context']=context
                    proposal=replanner.propose(draft,b,f,r,use_cache=False,visual_feedback=feedback,
                                               compiled_preflight=retry_preflight)
                    retry_records.append({'program':proposal.raw})
                    return proposal.program
                try:
                    next_city,negotiation,stats=negotiate_room_program(current,room_id,revised_program,
                        failure=str(error),asset_resolver=asset_resolver,seed=seed,
                        compiled_gate=compiled_gate,memory_store=memory_store)
                    if negotiation['status']=='resolved':
                        current=next_city; touched.add(room_id)
                    traces['room'].append({'room_id':room_id,'negotiation':negotiation,
                                           'repair_issue_keys':[issue_key(i) for i in repair_issues],
                                           'retry_proposals':retry_records,'stats':stats})
                except Exception as retry_error:
                    traces['room'].append({'room_id':room_id,'negotiation_status':'failed',
                        'error':f'{type(retry_error).__name__}: {retry_error}', 'retry_proposals':retry_records})
    save_json(current, root / "city_refined.json")
    material_path = _city_path(scene_path).parent / "assets" / "material_library.json"
    # Keep the same registry after asset generation, including package-only
    # prototype aliases and newly generated records. Reloading the global
    # registry here loses both and silently substitutes procedural furniture.
    registry.save(root / "runtime_assets" / "asset_registry.json")
    materials = MaterialLibrary(material_path) if material_path.is_file() else None
    after_openusd = root / "openusd_after"
    incremental_backend = OpenUSDBackend(
        geometry_compiler=GeometryCompiler(
            asset_registry=registry,
            material_library=materials,
            include_interiors=_interiors_compiled(scene_path),
            facade_asset_index_path=str(facade_asset_index) if facade_asset_index else None,
        )
    )
    # Room/building edits invalidate only their containing buildings; reuse the
    # untouched geometry from the input package whenever that cache is present.
    progress('局部编译', '编译复查版本，复用范围外几何', touched_entities=len(touched))
    incremental_backend.compile_incremental(
        current,
        after_openusd,
        scene_path,
        sorted(touched),
    )
    after_plan = _local_recheck_plan(
        current,
        touched,
        max_views,
        geometry_manifest=_geometry_manifest(after_openusd),
    )
    from cityg.issue_rechecks import plan_issue_rechecks
    after_plan = plan_issue_rechecks(current,before_plan.to_dict(),review,after_plan,
                                    max_views=max_views,touched=touched)
    save_json(after_plan, root / "observation_plan_after.json")
    server, thread, url = _start_server(after_openusd, viewer_port + 1 if viewer_port else 0)
    try:
        after_images = asyncio.run(
            _render_plan(
                url,
                after_plan,
                root / "observations_after",
                asset_timeout_ms=int(asset_load_timeout * 1000),
            )
        )
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)
    after_review = aggregate_visual_reviews(
        after_plan,
        root / "observations_after",
        VisualReviewAgent(service, max_images=batch_size),
        scene_id=city.id,
        batch_size=batch_size,
    )
    evidence_records.extend(record_observations(memory_store, current, after_plan,
                                                root/'observations_after', stage='after'))

    # A second, narrower Room Agent pass consumes the actual post-furnishing
    # observations. It can rearrange existing furniture but cannot rewrite the
    # room program, walls, doors, or metric coordinates. The deterministic
    # commit either validates each edit or retains the prior object.
    review_before_room_layout_refinement = None
    after_review = ground_review(current, after_review, memory_store=memory_store)
    room_layout_route = route_visual_issues(current, after_review)
    layout_room_ids = room_layout_route["room_refinement_ids"]
    if hero_room_ids:
        hero_set = set(hero_room_ids)
        layout_room_ids = [item for item in layout_room_ids if item in hero_set]
    layout_room_ids = layout_room_ids[:max_room_layout_refinements]
    layout_feedback: dict[str, dict[str, Any]] = {}
    for item in after_review.get("aggregated_issues", []):
        room_id = str(item.get("entity_id"))
        if room_id not in layout_room_ids or item.get('automatic_repair_allowed') is False:
            continue
        layout_feedback.setdefault(
            room_id, {"room_id": room_id, "issues": []}
        )["issues"].append(
            {
                "category": item.get("category"),
                "severity": item.get("severity"),
                "description": item.get("description"),
                "suggested_action": item.get("suggested_action"),
                "confidence": item.get("confidence"),
                "binding_confidence": item.get("binding_confidence"),
                "binding_basis": item.get("binding_basis"),
                "asset_requests": item.get("asset_requests", []),
            }
        )
    layout_agent = RoomLayoutRefinementAgent(
        service,
        model_id=model,
        asset_registry=registry,
        max_attempts=2,
    )
    layout_changed = False
    selected_layout_rooms: list[str] = []
    for room_id in layout_room_ids:
        progress('家具局部重排', '根据复查反馈验证候选', room=room_id)
        room_index = {
            room.id: (building, floor, room)
            for building in current.iter_buildings()
            for floor in building.floors
            for room in floor.rooms
        }
        target = room_index.get(room_id)
        if target is None:
            continue
        building, floor, room = target
        if not any(item.room_id == room.id for item in floor.objects):
            traces["room_layout"].append(
                {
                    "room_id": room_id,
                    "error": "local rearrangement skipped because the room has no objects",
                }
            )
            continue
        try:
            from cityg.refinement.room_repair_guard import RoomRepairGuard
            layout_issues=[i for i in after_review.get('aggregated_issues',[])
                           if i.get('entity_id')==room_id and i.get('automatic_repair_allowed')]
            layout_guard=RoomRepairGuard(current,room_id,layout_issues)
            layout_feedback[room_id]={**layout_feedback.get(room_id,{}),**layout_guard.feedback()}
            proposal = layout_agent.propose(
                current,
                building,
                floor,
                room,
                visual_feedback=layout_feedback.get(room_id, {"room_id": room_id}),
            )
            from cityg.validation.local_room import room_compilation_gate
            layout_compiled_gate=room_compilation_gate(current,room_id,incremental_backend.geometry_compiler)
            def guarded_layout(candidate):
                protected=layout_guard(candidate)
                return layout_compiled_gate(candidate) if protected['ok'] else protected
            layout_result = apply_room_layout_refinement(
                current,
                proposal.plan,
                asset_resolver=asset_resolver,
                seed=seed,
                compiled_gate=guarded_layout,
                memory_store=memory_store,
            )
            trace = layout_result.trace_dict()
            trace.update(
                {
                    "proposal": proposal.raw,
                    "repair_issue_keys": [issue_key(i) for i in layout_issues],
                    "attempts": proposal.attempts,
                    "normalization_notes": list(proposal.normalization_notes),
                    "visual_feedback": layout_feedback.get(room_id),
                }
            )
            traces["room_layout"].append(trace)
            if layout_result.changed:
                current = layout_result.city
                touched.add(room_id)
                selected_layout_rooms.append(room_id)
                layout_changed = True
        except Exception as error:
            traces["room_layout"].append(
                {
                    "room_id": room_id,
                    "visual_feedback": layout_feedback.get(room_id),
                    "error": f"{type(error).__name__}: {error}",
                }
            )

    if layout_changed:
        review_before_room_layout_refinement = after_review
        save_json(current, root / "city_refined.json")
        incremental_backend = OpenUSDBackend(
            geometry_compiler=GeometryCompiler(
                asset_registry=registry,
                material_library=materials,
                include_interiors=_interiors_compiled(after_openusd),
                facade_asset_index_path=str(facade_asset_index) if facade_asset_index else None,
            )
        )
        incremental_backend.compile_incremental(
            current,
            after_openusd,
            after_openusd,
            sorted(selected_layout_rooms),
        )
        after_plan = _local_recheck_plan(
            current,
            set(selected_layout_rooms),
            max_views,
            geometry_manifest=_geometry_manifest(after_openusd),
        )
        after_plan = plan_issue_rechecks(current,before_plan.to_dict(),review,after_plan,
                                        max_views=max_views,touched=touched|set(selected_layout_rooms))
        final_plan_path = root / "observation_plan_final.json"
        final_image_root = root / "observations_final"
        save_json(after_plan, final_plan_path)
        server, thread, url = _start_server(after_openusd, viewer_port + 2 if viewer_port else 0)
        try:
            after_images = asyncio.run(
                _render_plan(
                    url,
                    after_plan,
                    final_image_root,
                    asset_timeout_ms=int(asset_load_timeout * 1000),
                )
            )
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=5)
        after_review = aggregate_visual_reviews(
            after_plan,
            final_image_root,
            VisualReviewAgent(service, max_images=batch_size),
            scene_id=city.id,
            batch_size=batch_size,
        )
        after_plan_path = final_plan_path
        evidence_records.extend(record_observations(memory_store, current, after_plan,
                                                    final_image_root, stage='final'))
    else:
        after_plan_path = root / "observation_plan_after.json"

    after_review = ground_review(current, after_review, memory_store=memory_store)
    independent_proofs = resolution_proofs(city, current, review)
    save_json(independent_proofs, root / 'independent_issue_checks.json')
    # Export only after every accepted local refinement so the portable viewer
    # and city_refined.json always represent the same final canonical state.
    from cityg.validation.rendered_inventory import rendered_inventory_preserved
    after_manifest = _geometry_manifest(after_openusd)
    representation = rendered_inventory_preserved(
        city, current, _geometry_manifest(scene_path) or {}, after_manifest or {})
    save_json(representation, root / 'rendered_inventory_acceptance.json')
    if not representation['ok']:
        raise ValueError('Review lost existing GLB bindings; candidate not published: '
                         + str(representation['failures']))
    final_dir = _city_path(scene_path).parent.parent
    adaptation_path = final_dir.parent / 'programs' / 'prototype_adaptation.json'
    base_check = final_dir / 'reports' / 'prototype_compiled_acceptance.json'
    furnishing = None
    if base_check.is_file() and adaptation_path.is_file():
        adaptation = json.loads(adaptation_path.read_text())
        if 'max_rooms' in adaptation.get('options', {}):
            from cityg.planning.generation_prototypes import GenerationPrototypes
            furnishing_check = GenerationPrototypes.verify_final(
                current, after_manifest, adaptation, after_review=True)
            save_json(furnishing_check, root / 'furnishing_acceptance.json')
            furnishing = furnishing_check['furnishing_coverage']
    walking_contract = city.metadata.get('walking_contract')
    if walking_contract:
        from cityg.walking_requirements import assess
        paths = assess(current, walking_contract['bindings'], walking_contract['requirements'],
                       after_manifest)
        save_json(paths, root / 'walking_acceptance.json')
        if any(row['status'] != 'satisfied' for row in paths):
            raise ValueError('Post-review walking requirement unverified; see walking_acceptance.json')
    progress('便携 Viewer', '导出最终场景与资产')
    portable = export_portable_viewer(after_openusd, root / "viewer_after")
    from cityg.planning.conflicts import review_conflicts
    conflicts = review_conflicts(current, traces)
    save_json(conflicts, root/'planning_conflicts.json')
    result = {
        "scene_id": city.id,
        "planning_conflicts": conflicts,
        "bounded_outcome": bounded_review_outcome(review, after_review, after_plan, traces,
            current_versions={n.entity_id:n.version for n in current.world_program.nodes},
            deterministic_checks=independent_proofs),
        "independent_issue_checks": independent_proofs,
        "evidence_records": evidence_records,
        "memory": memory_store.stats(),
        "rendered_inventory_acceptance": representation,
        **({"furnishing_coverage": furnishing} if furnishing is not None else {}),
        **({"walking_acceptance": paths} if walking_contract else {}),
        "before_plan": str(before_plan_path),
        "before_images": before_images,
        "review": review,
        "review_after": after_review,
        "review_before_room_layout_refinement": review_before_room_layout_refinement,
        "route": {
            **route,
            "selected_building_refinements": selected_buildings,
            "selected_room_refinements": selected_rooms,
            "selected_streetscape_refinements": selected_streets,
            "room_layout_route": room_layout_route,
            "selected_room_layout_refinements": selected_layout_rooms,
        },
        "touched_entity_ids": sorted(touched),
        "traces": traces,
        "city_refined": str(root / "city_refined.json"),
        "openusd_after": str(after_openusd),
        "portable_viewer_after": str(portable),
        "after_plan": str(after_plan_path),
        "after_images": after_images,
        "asset_resolver": asset_resolver.stats() if asset_resolver is not None else None,
        "archetype_contact_sheets_enabled": enable_archetype_contact_sheets,
        "max_archetype_candidates": max_archetype_candidates,
        "facade_asset_index": str(facade_asset_index) if facade_asset_index else None,
    }
    save_json(result, root / "adaptive_review_report.json")
    progress('视觉闭环', '报告已保存；问题减少不等于已修复',
             before=review['status'], after=after_review['status'], committed_entities=len(touched),
             status=result['bounded_outcome'].get('status'))
    return result


__all__ = ["aggregate_visual_reviews", "route_visual_issues", "run_adaptive_review"]
