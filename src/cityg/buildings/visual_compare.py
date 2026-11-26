"""Bounded contact-sheet comparison for compatible building archetypes.

The comparison is deliberately a proposal layer.  It may render and rank
several valid visual alternatives, but it never writes an archetype directly
to the canonical city.  The Building Refinement Agent and PatchEngine remain
the commit path.
"""

from __future__ import annotations

import asyncio
import base64
import copy
import hashlib
import html
import json
import math
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

from cityg.assets import AssetRegistry, MaterialLibrary
from cityg.buildings.selector import (
    BuildingSelection,
    BuildingSelectionContext,
    BuildingSelector,
)
from cityg.ccwp import build_world_program
from cityg.geometry import GeometryCompiler
from cityg.schemas import Building, City
from cityg.serialization import save_json
from cityg.services import OpenUSDBackend
from cityg.services.interfaces import ChatMessage, TextReasoningService
from cityg.viewer import create_viewer_server


BUILDING_VISUAL_COMPARISON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "building_id": {"type": "string"},
        "selected_archetype_id": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "comparison_summary": {"type": "string"},
        "ranking": {
            "type": "array",
            "maxItems": 4,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "panel_id": {"type": "string"},
                    "archetype_id": {"type": "string"},
                    "rank": {"type": "integer", "minimum": 1, "maximum": 4},
                    "semantic_fit": {"type": "number", "minimum": 0, "maximum": 1},
                    "visual_fit": {"type": "number", "minimum": 0, "maximum": 1},
                    "context_fit": {"type": "number", "minimum": 0, "maximum": 1},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "reason": {"type": "string"},
                    "visible_risks": {
                        "type": "array",
                        "maxItems": 4,
                        "items": {"type": "string"},
                    },
                },
                "required": [
                    "panel_id", "archetype_id", "rank", "semantic_fit",
                    "visual_fit", "context_fit", "confidence", "reason",
                    "visible_risks",
                ],
            },
        },
    },
    "required": [
        "building_id", "selected_archetype_id", "confidence",
        "comparison_summary", "ranking",
    ],
}


def _parse_json_object(raw: str) -> dict[str, Any]:
    """Parse a JSON object while tolerating an optional Markdown fence."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("model response must be a JSON object")
    return value


@dataclass(frozen=True)
class BuildingVisualCandidate:
    panel_id: str
    selection: BuildingSelection
    source: str

    @property
    def archetype_id(self) -> str:
        return self.selection.archetype.archetype_id

    def to_dict(self) -> dict[str, Any]:
        archetype = self.selection.archetype
        return {
            "panel_id": self.panel_id,
            "archetype_id": archetype.archetype_id,
            "source": self.source,
            "family": archetype.family,
            "massing_style": archetype.massing_style,
            "massing_signature": archetype.massing_signature,
            "massing_variant": archetype.massing_variant,
            "massing_parameters": dict(archetype.massing_parameters),
            "facade_style_id": self.selection.facade_style_id,
            "ornament_kit_ids": list(archetype.ornament_kit_ids),
            "selector_score": self.selection.score,
        }


@dataclass(frozen=True)
class BuildingVisualComparisonResult:
    available: bool
    building_id: str
    candidates: tuple[BuildingVisualCandidate, ...]
    contact_sheet_path: str | None = None
    selected_archetype_id: str | None = None
    confidence: float = 0.0
    ranking: tuple[dict[str, Any], ...] = ()
    comparison_summary: str = ""
    error: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "building_id": self.building_id,
            "candidate_archetype_ids": [item.archetype_id for item in self.candidates],
            "candidates": [item.to_dict() for item in self.candidates],
            "contact_sheet_path": self.contact_sheet_path,
            "selected_archetype_id": self.selected_archetype_id,
            "confidence": self.confidence,
            "ranking": [dict(item) for item in self.ranking],
            "comparison_summary": self.comparison_summary,
            "error": self.error,
            "raw": self.raw,
        }


def _stable_order(building_id: str, archetype_id: str) -> str:
    return hashlib.sha256(f"{building_id}:{archetype_id}".encode("utf-8")).hexdigest()


def shortlist_building_candidates(
    building: Building,
    *,
    max_candidates: int = 4,
    preferred_ids: Iterable[str] = (),
) -> tuple[BuildingVisualCandidate, ...]:
    """Return a compatible, priority-aware and visually diverse shortlist."""
    if not 1 <= max_candidates <= 4:
        raise ValueError("max_candidates must be within [1, 4]")
    selector = BuildingSelector()
    context = BuildingSelectionContext.from_building(building)
    preferred_ids = tuple(str(item) for item in preferred_ids if str(item))
    compatible = selector.candidates(context)
    if not compatible and context.prototype_id is not None:
        # Match the selector's legacy prototype relaxation while retaining all
        # geometric/function constraints.
        from dataclasses import replace

        compatible = selector.candidates(replace(context, prototype_id=None))
    by_id = {item.archetype_id: item for item in compatible}
    current_id = str(building.metadata.get("archetype_id", ""))
    semantic_ids = tuple(
        str(item) for item in building.metadata.get("semantic_archetype_palette", [])
    )
    requested = tuple(dict.fromkeys((current_id, *preferred_ids, *semantic_ids)))
    chosen_ids: list[str] = [item for item in requested if item in by_id][:max_candidates]
    chosen_signatures = {by_id[item].massing_signature for item in chosen_ids}
    chosen_styles = {by_id[item].massing_style for item in chosen_ids}
    chosen_facades = {
        facade for item in chosen_ids for facade in by_id[item].facade_style_ids
    }
    remaining = [item for item in compatible if item.archetype_id not in chosen_ids]
    while remaining and len(chosen_ids) < max_candidates:
        def score(item: Any) -> tuple[int, int, int, str]:
            return (
                int(item.massing_signature not in chosen_signatures),
                int(item.massing_style not in chosen_styles),
                int(any(facade not in chosen_facades for facade in item.facade_style_ids)),
                _stable_order(building.id, item.archetype_id),
            )

        selected = max(remaining, key=score)
        remaining.remove(selected)
        chosen_ids.append(selected.archetype_id)
        chosen_signatures.add(selected.massing_signature)
        chosen_styles.add(selected.massing_style)
        chosen_facades.update(selected.facade_style_ids)

    candidates: list[BuildingVisualCandidate] = []
    preferred_set = set(preferred_ids)
    semantic_set = set(semantic_ids)
    for index, archetype_id in enumerate(chosen_ids):
        selection = selector.select(context, preferred_ids=(archetype_id,))
        if selection.archetype.archetype_id != archetype_id:
            continue
        source = (
            "current" if archetype_id == current_id
            else "visual_issue" if archetype_id in preferred_set
            else "building_agent_palette" if archetype_id in semantic_set
            else "diversity_fill"
        )
        candidates.append(
            BuildingVisualCandidate(chr(ord("A") + index), selection, source)
        )
    return tuple(candidates)


def isolated_candidate_city(
    city: City,
    building_id: str,
    candidate: BuildingVisualCandidate,
) -> City:
    """Clone a city and retain only the target building for preview rendering."""
    preview = copy.deepcopy(city)
    target: Building | None = None
    for district in preview.districts:
        retained_parcels = []
        for parcel in district.parcels:
            parcel.buildings = [item for item in parcel.buildings if item.id == building_id]
            if parcel.buildings:
                target = parcel.buildings[0]
                retained_parcels.append(parcel)
        district.parcels = retained_parcels
    preview.districts = [district for district in preview.districts if district.parcels]
    if target is None:
        raise KeyError(building_id)
    target.metadata.update(candidate.selection.to_metadata())
    if candidate.selection.archetype.massing_variant and len(target.floors) >= 10:
        highrise = dict(target.metadata.get("highrise", {}))
        highrise["massing_variant"] = candidate.selection.archetype.massing_variant
        target.metadata["highrise"] = highrise
    target.metadata["contact_sheet_preview"] = {
        "panel_id": candidate.panel_id,
        "source": candidate.source,
    }
    preview.name = f"{city.name} · {candidate.panel_id} · {candidate.archetype_id}"
    preview.metadata = dict(preview.metadata)
    preview.metadata["preview_mode"] = "building_archetype_contact_sheet"
    preview.world_program = build_world_program(
        preview,
        producer="building_archetype_contact_sheet",
        seed=0,
    )
    return preview


def building_comparison_view(building: Building, panel_id: str) -> dict[str, Any]:
    """Use the same three-quarter camera contract for every candidate."""
    center = building.footprint.center
    extent = max(building.footprint.width, building.footprint.depth, 4.0)
    height = max(
        (floor.elevation_m + floor.height_m for floor in building.floors),
        default=6.0,
    )
    orientation = float(
        building.metadata.get("orientation_contract", {}).get(
            "orientation_deg", building.metadata.get("orientation_deg", 0.0)
        )
    )
    angle = math.radians(orientation + 38.0)
    distance = max(extent * 2.15, height * 0.72, 22.0)
    return {
        "view_id": f"panel_{panel_id}",
        "kind": "building_exterior",
        "purpose": "candidate building archetype comparison",
        "target_entity_ids": [building.id],
        "camera_position": [
            center.x + math.cos(angle) * distance,
            center.y + math.sin(angle) * distance,
            max(12.0, height * 0.72 + extent * 0.62),
        ],
        "look_at": [center.x, center.y, height * 0.36],
        "up": [0.0, 0.0, 1.0],
        "fov_deg": 46.0,
        "mode": "building",
        "appearance": "presentation",
        "auto_cutaway": False,
        "show_outlines": False,
        "show_labels": False,
        "show_road_markings": False,
    }


async def _render_view(
    url: str,
    view: dict[str, Any],
    destination: Path,
    *,
    wait_ms: int = 350,
    asset_timeout_ms: int = 60_000,
) -> dict[str, Any]:
    try:
        from playwright.async_api import async_playwright
    except ImportError as error:  # pragma: no cover - environment dependent
        raise RuntimeError("Playwright is required for building contact sheets") from error
    launch_args = [
        "--disable-dev-shm-usage", "--use-angle=swiftshader",
        "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist",
    ]
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True, args=launch_args)
        page = await browser.new_page(
            viewport={"width": 1200, "height": 800}, device_scale_factor=1
        )
        try:
            # Candidate previews are often below the Viewer's large-scene
            # threshold even though their full interiors still contain many
            # GLBs. Inject the exact building view before startup so the page
            # never performs an unnecessary Full/Presentation load first.
            await page.add_init_script(
                "window.__CITYG_INITIAL_OBSERVATION_VIEW__ = "
                + json.dumps(view, ensure_ascii=False)
                + "; window.__CITYG_RENDER_PROFILE__ = 'review';"
            )
            await page.goto(url, wait_until="commit", timeout=60_000)
            await page.wait_for_function(
                "window.citygObservation && window.citygObservation.ready",
                timeout=180_000,
            )
            view_status = await page.evaluate(
                "(candidateView) => window.citygObservation.setView(candidateView)",
                view,
            )
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
            if not asset_status.get("ready"):
                raise RuntimeError(f"candidate assets did not become ready: {asset_status}")
            await page.wait_for_timeout(max(0, wait_ms))
            destination.parent.mkdir(parents=True, exist_ok=True)
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
                data_url = None
            if not data_url:
                await page.locator("#scene-canvas").screenshot(
                    path=str(destination), timeout=30_000
                )
                return {
                    **dict(asset_status),
                    "view_status": dict(view_status),
                    "capture_method": "playwright_canvas_fallback",
                }
            destination.write_bytes(base64.b64decode(data_url.split(",", 1)[1]))
            return {
                **dict(asset_status),
                "view_status": dict(view_status),
                "capture_method": "viewer_capture_frame",
            }
        finally:
            await page.close()
            await browser.close()


def _sheet_html(
    panels: Sequence[tuple[BuildingVisualCandidate, Path]],
    *,
    embedded: bool,
) -> str:
    cards: list[str] = []
    for candidate, path in panels:
        if embedded:
            encoded = base64.b64encode(path.read_bytes()).decode("ascii")
            source = f"data:image/png;base64,{encoded}"
        else:
            source = f"panels/{html.escape(path.name)}"
        archetype = candidate.selection.archetype
        cards.append(
            "<article class='card'>"
            f"<div class='badge'>{html.escape(candidate.panel_id)}</div>"
            f"<img src='{source}' alt='{html.escape(candidate.archetype_id)}'>"
            "<div class='caption'>"
            f"<strong>{html.escape(candidate.panel_id)} · {html.escape(candidate.archetype_id)}</strong>"
            f"<span>{html.escape(archetype.massing_style)} · {html.escape(candidate.selection.facade_style_id)}</span>"
            "</div></article>"
        )
    return """<!doctype html><html><head><meta charset='utf-8'><style>
        * { box-sizing: border-box; }
        body { margin: 0; padding: 24px; background: #15201e; color: #f3f8f6;
               font: 16px system-ui, sans-serif; }
        .grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 18px; }
        .card { position: relative; overflow: hidden; border: 2px solid #53736b;
                border-radius: 12px; background: #25322f; }
        .card img { width: 100%; aspect-ratio: 3 / 2; display: block; object-fit: cover; }
        .badge { position: absolute; z-index: 2; top: 12px; left: 12px; width: 46px;
                 height: 46px; display: grid; place-items: center; border-radius: 50%;
                 color: #10211d; background: #78e3b8; font-size: 26px; font-weight: 800; }
        .caption { min-height: 72px; padding: 11px 15px; display: flex;
                   flex-direction: column; gap: 5px; }
        .caption strong { font-size: 18px; }
        .caption span { color: #b8ccc6; font-size: 14px; }
    </style></head><body><main class='grid'>""" + "".join(cards) + "</main></body></html>"


async def _render_contact_sheet(
    panels: Sequence[tuple[BuildingVisualCandidate, Path]],
    destination: Path,
    html_path: Path,
) -> None:
    try:
        from playwright.async_api import async_playwright
    except ImportError as error:  # pragma: no cover - environment dependent
        raise RuntimeError("Playwright is required for building contact sheets") from error
    html_path.write_text(_sheet_html(panels, embedded=False), encoding="utf-8")
    embedded_html = _sheet_html(panels, embedded=True)
    launch_args = ["--disable-dev-shm-usage", "--use-angle=swiftshader"]
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True, args=launch_args)
        page = await browser.new_page(viewport={"width": 1440, "height": 1000})
        try:
            await page.set_content(embedded_html, wait_until="load")
            await page.wait_for_function(
                "Array.from(document.images).every((image) => image.complete)"
            )
            await page.locator(".grid").screenshot(
                path=str(destination), timeout=30_000
            )
        finally:
            await page.close()
            await browser.close()


class BuildingVisualComparisonAgent:
    """Rank a rendered shortlist without gaining canonical write authority."""

    def __init__(self, service: TextReasoningService) -> None:
        self.service = service

    def compare(
        self,
        building: Building,
        candidates: Sequence[BuildingVisualCandidate],
        contact_sheet: Path,
        *,
        visual_feedback: dict[str, Any] | None = None,
    ) -> BuildingVisualComparisonResult:
        if not contact_sheet.is_file():
            return BuildingVisualComparisonResult(
                False, building.id, tuple(candidates), error="missing contact sheet"
            )
        allowed = {item.archetype_id: item.panel_id for item in candidates}
        context = {
            "building": {
                "id": building.id,
                "function": building.function,
                "floor_count": len(building.floors),
                "width_m": building.footprint.width,
                "depth_m": building.footprint.depth,
                "parcel_role": building.metadata.get("parcel_role"),
                "height_contract": building.metadata.get("height_contract", {}),
                "appearance_plan": building.metadata.get("appearance_plan", {}),
            },
            "panel_mapping": [item.to_dict() for item in candidates],
            "visual_feedback": visual_feedback or {},
        }
        prompt = (
            "You are CityG's visual building comparison agent. The contact sheet uses "
            "the same building, camera, lighting, footprint and floor count in every panel; "
            "only compatible massing/facade/ornament archetypes differ. Rank every shown "
            "panel. Balance semantic fitness for the building function, visible massing and "
            "facade quality, street/context fitness, and the supplied review evidence. "
            "Check compatibility with appearance_plan.context and the intended design language; "
            "judge visible articulation, not a stereotyped national style. The appearance plan "
            "is held fixed across these massing candidates. Do not infer hidden floor plans. "
            "Use only exact panel_id/archetype_id pairs "
            "from panel_mapping and return JSON matching the schema.\n"
            + json.dumps(context, ensure_ascii=False, sort_keys=True)
        )
        try:
            message = ChatMessage(
                role="user", content=prompt, image_paths=(contact_sheet,)
            )
            method = getattr(self.service, "complete_with_metadata", None)
            if callable(method):
                raw_text = method(
                    [message], BUILDING_VISUAL_COMPARISON_SCHEMA
                ).content
            else:
                review_method = getattr(self.service, "review", None)
                if callable(review_method):
                    raw_text = review_method(prompt, (contact_sheet,))
                else:
                    raw_text = self.service.complete(
                        [message], BUILDING_VISUAL_COMPARISON_SCHEMA
                    )
            data = _parse_json_object(raw_text)
            if str(data.get("building_id")) != building.id:
                raise ValueError("comparison returned a different building_id")
            selected = str(data.get("selected_archetype_id", ""))
            if selected not in allowed:
                raise ValueError("comparison selected an archetype outside the contact sheet")
            ranking: list[dict[str, Any]] = []
            seen: set[str] = set()
            for item in data.get("ranking", []):
                archetype_id = str(item.get("archetype_id", ""))
                panel_id = str(item.get("panel_id", ""))
                if archetype_id not in allowed or allowed[archetype_id] != panel_id:
                    raise ValueError("comparison ranking contains an invalid panel binding")
                if archetype_id in seen:
                    raise ValueError("comparison ranking contains duplicate archetypes")
                seen.add(archetype_id)
                normalized = dict(item)
                for key in ("semantic_fit", "visual_fit", "context_fit", "confidence"):
                    normalized[key] = min(1.0, max(0.0, float(item.get(key, 0.0))))
                normalized["rank"] = int(item.get("rank", len(ranking) + 1))
                normalized["visible_risks"] = [
                    str(value) for value in item.get("visible_risks", [])[:4]
                ]
                ranking.append(normalized)
            if seen != set(allowed):
                raise ValueError("comparison must rank every contact-sheet candidate")
            ranking.sort(key=lambda item: (item["rank"], item["archetype_id"]))
            return BuildingVisualComparisonResult(
                True,
                building.id,
                tuple(candidates),
                contact_sheet_path=str(contact_sheet),
                selected_archetype_id=selected,
                confidence=min(1.0, max(0.0, float(data.get("confidence", 0.0)))),
                ranking=tuple(ranking),
                comparison_summary=str(data.get("comparison_summary", "")),
                raw=data,
            )
        except Exception as error:
            return BuildingVisualComparisonResult(
                False,
                building.id,
                tuple(candidates),
                contact_sheet_path=str(contact_sheet),
                error=f"{type(error).__name__}: {error}",
            )


def run_building_visual_comparison(
    city: City,
    building_id: str,
    output_dir: str | Path,
    service: TextReasoningService,
    *,
    source_scene_root: str | Path,
    max_candidates: int = 4,
    preferred_ids: Iterable[str] = (),
    visual_feedback: dict[str, Any] | None = None,
    viewer_port: int = 0,
    wait_ms: int = 700,
) -> BuildingVisualComparisonResult:
    """Render a shortlist, compose its sheet, and obtain a bounded VLM rank."""
    building = next((item for item in city.iter_buildings() if item.id == building_id), None)
    if building is None:
        raise KeyError(building_id)
    root = Path(output_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    from cityg.envelopes import envelope_config
    if envelope_config(building):
        result = BuildingVisualComparisonResult(False, building_id, (),
            error="Exterior loft envelopes replace legacy massing; legacy archetype comparison is not applicable")
        save_json(result.to_dict(), root / "comparison.json")
        return result
    candidates = shortlist_building_candidates(
        building, max_candidates=max_candidates, preferred_ids=preferred_ids
    )
    save_json(
        {"building_id": building_id, "candidates": [item.to_dict() for item in candidates]},
        root / "candidates.json",
    )
    if len(candidates) < 2:
        result = BuildingVisualComparisonResult(
            False, building_id, candidates, error="fewer than two compatible candidates"
        )
        save_json(result.to_dict(), root / "comparison.json")
        return result

    source_root = Path(source_scene_root).expanduser().resolve()
    registry_path = source_root / "assets" / "asset_registry.json"
    material_path = source_root / "assets" / "material_library.json"
    registry = AssetRegistry(registry_path) if registry_path.is_file() else None
    materials = MaterialLibrary(material_path) if material_path.is_file() else None
    panels: list[tuple[BuildingVisualCandidate, Path]] = []
    panel_errors: list[str] = []
    for index, candidate in enumerate(candidates):
        try:
            preview = isolated_candidate_city(city, building_id, candidate)
            scene_dir = root / "scenes" / candidate.panel_id / "openusd"
            OpenUSDBackend(
                geometry_compiler=GeometryCompiler(
                    asset_registry=registry, material_library=materials
                )
            ).compile(preview, scene_dir)
            target = next(item for item in preview.iter_buildings())
            view = building_comparison_view(target, candidate.panel_id)
            save_json({"selected_views": [view]}, root / "scenes" / candidate.panel_id / "view.json")
            server, url, _ = create_viewer_server(
                scene_dir, host="127.0.0.1", port=(viewer_port + index if viewer_port else 0)
            )
            thread = threading.Thread(
                target=server.serve_forever,
                name=f"cityg-candidate-{candidate.panel_id}",
                daemon=True,
            )
            thread.start()
            destination = root / "panels" / f"{candidate.panel_id}.png"
            try:
                asset_status = asyncio.run(
                    _render_view(url, view, destination, wait_ms=wait_ms)
                )
                save_json(
                    {"view_id": view["view_id"], "asset_status": asset_status},
                    root / "scenes" / candidate.panel_id / "asset_load_status.json",
                )
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
            panels.append((candidate, destination))
        except Exception as error:
            panel_errors.append(
                f"{candidate.panel_id}/{candidate.archetype_id}: {type(error).__name__}: {error}"
            )
    if len(panels) != len(candidates):
        result = BuildingVisualComparisonResult(
            False,
            building_id,
            candidates,
            error="; ".join(panel_errors) or "candidate rendering failed",
        )
        save_json(result.to_dict(), root / "comparison.json")
        return result

    contact_sheet = root / "contact_sheet.png"
    asyncio.run(
        _render_contact_sheet(panels, contact_sheet, root / "contact_sheet.html")
    )
    result = BuildingVisualComparisonAgent(service).compare(
        building,
        candidates,
        contact_sheet,
        visual_feedback=visual_feedback,
    )
    save_json(result.to_dict(), root / "comparison.json")
    return result


__all__ = [
    "BUILDING_VISUAL_COMPARISON_SCHEMA",
    "BuildingVisualCandidate",
    "BuildingVisualComparisonAgent",
    "BuildingVisualComparisonResult",
    "building_comparison_view",
    "isolated_candidate_city",
    "run_building_visual_comparison",
    "shortlist_building_candidates",
]
