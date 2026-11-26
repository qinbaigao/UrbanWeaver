"""Contact-sheet VLM audit and conservative write-back for facade assets."""

from __future__ import annotations

import asyncio
import base64
import html
import json
import threading
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterable, Sequence
from urllib.parse import quote

from cityg.buildings.visual_compare import _parse_json_object
from cityg.facade_assets import (
    FacadeAssetIndex,
    _asset_family,
    _compatibility,
    _placement,
    _repeatability,
    _zones,
    save_facade_asset_annotations,
)
from cityg.services.interfaces import ChatMessage, TextReasoningService


FACADE_VISUAL_REVIEW_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "sheet_id": {"type": "string"},
        "summary": {"type": "string"},
        "reviews": {
            "type": "array",
            "minItems": 1,
            "maxItems": 8,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "panel_id": {"type": "string"},
                    "asset_id": {"type": "string"},
                    "semantic_assessment": {
                        "type": "string",
                        "enum": ["correct", "incorrect", "uncertain"],
                    },
                    "suggested_semantic_type": {"type": ["string", "null"]},
                    "front_axis_assessment": {
                        "type": "string",
                        "enum": ["correct", "opposite", "orthogonal", "uncertain"],
                    },
                    "suggested_source_front_axis": {
                        "type": ["string", "null"],
                        "enum": ["+X", "-X", "+Z", "-Z", None],
                    },
                    "upright": {"type": "boolean"},
                    "scale_assessment": {
                        "type": "string",
                        "enum": ["plausible", "too_small", "too_large", "unknown"],
                    },
                    "visual_quality": {"type": "number", "minimum": 0, "maximum": 1},
                    "placement_readiness": {
                        "type": "string",
                        "enum": ["ready", "needs_review", "reject"],
                    },
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "issues": {
                        "type": "array",
                        "maxItems": 5,
                        "items": {"type": "string"},
                    },
                    "reason": {"type": "string"},
                },
                "required": [
                    "panel_id", "asset_id", "semantic_assessment",
                    "suggested_semantic_type", "front_axis_assessment",
                    "suggested_source_front_axis", "upright", "scale_assessment",
                    "visual_quality", "placement_readiness", "confidence", "issues", "reason",
                ],
            },
        },
    },
    "required": ["sheet_id", "summary", "reviews"],
}


@dataclass(frozen=True)
class FacadeReviewCandidate:
    panel_id: str
    record: dict[str, Any]
    stratum_id: str
    stratum_size: int

    def mapping(self) -> dict[str, Any]:
        return {
            "panel_id": self.panel_id,
            "asset_id": self.record["asset_id"],
            "display_name": self.record["display_name"],
            "semantic_type": self.record["semantic_type"],
            "source_id": self.record["source_id"],
            "source_front_axis": self.record["orientation"]["source_front_axis"],
            "alignment_mode": self.record["orientation"].get("alignment_mode", "front_normal"),
            "native_extent_xyz": self.record["scale"]["native_extent_xyz"],
            "native_scale_confidence": self.record["scale"]["native_scale_confidence"],
            "stratum_id": self.stratum_id,
            "stratum_size": self.stratum_size,
        }


@dataclass(frozen=True)
class FacadeSheetReview:
    available: bool
    sheet_id: str
    reviews: tuple[dict[str, Any], ...] = ()
    summary: str = ""
    error: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "sheet_id": self.sheet_id,
            "reviews": [dict(item) for item in self.reviews],
            "summary": self.summary,
            "error": self.error,
            "raw": self.raw,
        }


def plan_facade_visual_review(
    index: FacadeAssetIndex,
    *,
    max_assets: int = 32,
    representatives_per_stratum: int = 2,
) -> tuple[FacadeReviewCandidate, ...]:
    """Round-robin across source/type/axis strata before sampling repeats."""

    if max_assets <= 0 or representatives_per_stratum <= 0:
        return ()
    strata: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in index.assets:
        if record.get("selection_status") != "usable":
            continue
        if not record.get("orientation", {}).get("visual_review_required", True):
            continue
        key = "|".join(
            (
                str(record["source_id"]),
                str(record["semantic_type"]),
                str(record["orientation"]["source_front_axis"]),
            )
        )
        strata[key].append(record)
    for records in strata.values():
        records.sort(key=lambda item: (-float(item["quality"]["score"]), item["asset_id"]))
    source_strata: dict[str, list[str]] = defaultdict(list)
    for key in strata:
        source_strata[key.split("|", 1)[0]].append(key)
    for keys in source_strata.values():
        keys.sort(key=lambda key: (-len(strata[key]), key))
    queues: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for source_id, keys in source_strata.items():
        queues[source_id] = [
            (key, strata[key][round_index])
            for round_index in range(representatives_per_stratum)
            for key in keys
            if round_index < len(strata[key])
        ]
    sources = sorted(queues, key=lambda item: (0 if item == "polyhaven" else 1, item))
    selected: list[tuple[str, dict[str, Any]]] = []
    while len(selected) < max_assets and any(queues.values()):
        for source_id in sources:
            if queues[source_id]:
                selected.append(queues[source_id].pop(0))
                if len(selected) >= max_assets:
                    break
    return tuple(
        FacadeReviewCandidate(
            panel_id=f"F{index_:03d}",
            record=record,
            stratum_id=key,
            stratum_size=len(strata[key]),
        )
        for index_, (key, record) in enumerate(selected, 1)
    )


def plan_facade_visual_expansion(
    index: FacadeAssetIndex,
    observed: Sequence[FacadeReviewCandidate],
    reviews: Sequence[FacadeSheetReview],
    *,
    max_assets: int = 8,
) -> tuple[FacadeReviewCandidate, ...]:
    """Expand only strata whose representative was uncertain or problematic."""

    if max_assets <= 0:
        return ()
    candidates_by_asset = {item.record["asset_id"]: item for item in observed}
    risky_strata: set[str] = set()
    for sheet in reviews:
        if not sheet.available:
            continue
        for review in sheet.reviews:
            candidate = candidates_by_asset.get(str(review["asset_id"]))
            if candidate is None:
                continue
            front_applicable = bool(
                candidate.record["orientation"].get("front_axis_review_applicable", True)
            )
            risky = (
                float(review["confidence"]) < 0.90
                or review["semantic_assessment"] != "correct"
                or not bool(review["upright"])
                or review["scale_assessment"] != "plausible"
                or review["placement_readiness"] != "ready"
                or float(review["visual_quality"]) < 0.65
                or (
                    front_applicable
                    and review["front_axis_assessment"] != "correct"
                )
            )
            if risky:
                risky_strata.add(candidate.stratum_id)
    if not risky_strata:
        return ()
    excluded = set(candidates_by_asset)
    strata: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in index.assets:
        key = "|".join(
            (
                str(record["source_id"]),
                str(record["semantic_type"]),
                str(record["orientation"]["source_front_axis"]),
            )
        )
        if (
            key in risky_strata
            and record.get("selection_status") == "usable"
            and record["asset_id"] not in excluded
        ):
            strata[key].append(record)
    for records in strata.values():
        records.sort(key=lambda item: (-float(item["quality"]["score"]), item["asset_id"]))
    selected: list[tuple[str, dict[str, Any]]] = []
    keys = sorted(strata)
    offset = len(observed) + 1
    while len(selected) < max_assets and any(strata.values()):
        for key in keys:
            if strata[key]:
                selected.append((key, strata[key].pop(0)))
                if len(selected) >= max_assets:
                    break
    return tuple(
        FacadeReviewCandidate(
            panel_id=f"F{offset + index_:03d}",
            record=record,
            stratum_id=key,
            stratum_size=len(
                [
                    item
                    for item in index.assets
                    if "|".join(
                        (
                            str(item["source_id"]),
                            str(item["semantic_type"]),
                            str(item["orientation"]["source_front_axis"]),
                        )
                    )
                    == key
                ]
            ),
        )
        for index_, (key, record) in enumerate(selected)
    )


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return


def _start_server(project_root: Path) -> tuple[ThreadingHTTPServer, str, threading.Thread]:
    handler = partial(_QuietHandler, directory=str(project_root))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, name="facade-preview", daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    return server, f"http://{host}:{port}", thread


async def _render_panels_async(
    candidates: Sequence[FacadeReviewCandidate],
    project_root: Path,
    output_dir: Path,
) -> list[dict[str, Any]]:
    try:
        from playwright.async_api import async_playwright
    except ImportError as error:  # pragma: no cover - environment dependent
        raise RuntimeError("Playwright is required for facade contact sheets") from error
    server, base_url, thread = _start_server(project_root)
    results: list[dict[str, Any]] = []
    launch_args = [
        "--disable-dev-shm-usage", "--use-angle=swiftshader",
        "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist",
    ]
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True, args=launch_args)
            page = await browser.new_page(viewport={"width": 1000, "height": 620}, device_scale_factor=1)
            try:
                for candidate in candidates:
                    record = candidate.record
                    selector = record["selector"]
                    query = {
                        "asset": "/" + record["geometry_path"],
                        "front": record["orientation"]["source_front_axis"],
                        "mode": record["orientation"].get("alignment_mode", "front_normal"),
                    }
                    if selector.get("kind") == "gltf_node":
                        query["node"] = str(selector["node_name"])
                    encoded = "&".join(f"{key}={quote(value, safe='/')}" for key, value in query.items())
                    url = f"{base_url}/scripts/facade_preview/index.html?{encoded}"
                    await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
                    await page.wait_for_function(
                        "window.facadePreview && (window.facadePreview.ready || window.facadePreview.error)",
                        timeout=120_000,
                    )
                    status = await page.evaluate("() => window.facadePreview")
                    if not status.get("ready"):
                        raise RuntimeError(f"{candidate.panel_id}: {status.get('error')}")
                    destination = output_dir / "panels" / f"{candidate.panel_id}.png"
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    await page.locator("#preview-frame").screenshot(path=str(destination))
                    results.append(
                        {
                            **candidate.mapping(),
                            "image_path": str(destination),
                            "rendered_extent_xyz": status.get("source_extent"),
                        }
                    )
            finally:
                await page.close()
                await browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    return results


def render_facade_panels(
    candidates: Sequence[FacadeReviewCandidate],
    project_root: str | Path,
    output_dir: str | Path,
) -> list[dict[str, Any]]:
    return asyncio.run(
        _render_panels_async(candidates, Path(project_root).resolve(), Path(output_dir).resolve())
    )


def _sheet_html(sheet_id: str, panels: Sequence[dict[str, Any]], *, embedded: bool) -> str:
    cards: list[str] = []
    for panel in panels:
        path = Path(panel["image_path"])
        source = (
            f"data:image/png;base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"
            if embedded else f"../../panels/{html.escape(path.name)}"
        )
        extent = "×".join(f"{float(value):.2f}" for value in panel["native_extent_xyz"])
        cards.append(
            "<article class='card'>"
            f"<div class='badge'>{html.escape(panel['panel_id'])}</div>"
            f"<img src='{source}' alt='{html.escape(panel['asset_id'])}'>"
            "<div class='caption'>"
            f"<strong>{html.escape(panel['semantic_type'])}</strong>"
            f"<span>{html.escape(panel['display_name'])}</span>"
            f"<small>{html.escape(panel['alignment_mode'])} {html.escape(panel['source_front_axis'])} · extent {extent} · n={panel['stratum_size']}</small>"
            "</div></article>"
        )
    return """<!doctype html><html><head><meta charset='utf-8'><style>
      *{box-sizing:border-box} body{margin:0;padding:16px;background:#15201e;color:#f3f8f6;font:13px system-ui}
      h1{margin:0 0 12px;font-size:18px}.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}
      .card{position:relative;overflow:hidden;border:2px solid #53736b;border-radius:9px;background:#25322f}
      .card img{width:100%;aspect-ratio:1000/620;display:block;object-fit:cover}.badge{position:absolute;top:7px;left:7px;
      z-index:2;padding:5px 8px;border-radius:5px;color:#10211d;background:#78e3b8;font-weight:900;font-size:15px}
      .caption{padding:7px 10px;display:grid;gap:2px}.caption strong{font-size:14px}.caption span,.caption small{color:#bed0ca}
    </style></head><body>""" + f"<h1>{html.escape(sheet_id)} · red arrow is annotated front</h1><main class='grid'>" + "".join(cards) + "</main></body></html>"


async def _compose_sheet_async(sheet_id: str, panels: Sequence[dict[str, Any]], destination: Path) -> None:
    try:
        from playwright.async_api import async_playwright
    except ImportError as error:  # pragma: no cover
        raise RuntimeError("Playwright is required for facade contact sheets") from error
    destination.parent.mkdir(parents=True, exist_ok=True)
    (destination.parent / "contact_sheet.html").write_text(
        _sheet_html(sheet_id, panels, embedded=False), encoding="utf-8"
    )
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=True, args=["--disable-dev-shm-usage", "--use-angle=swiftshader"]
        )
        page = await browser.new_page(viewport={"width": 1500, "height": 2400})
        try:
            await page.set_content(_sheet_html(sheet_id, panels, embedded=True), wait_until="load")
            await page.wait_for_function("Array.from(document.images).every((image)=>image.complete)")
            await page.locator("body").screenshot(path=str(destination))
        finally:
            await page.close()
            await browser.close()


def compose_facade_sheets(
    panels: Sequence[dict[str, Any]], output_dir: str | Path, *, batch_size: int = 8,
    sheet_prefix: str = "facade_sheet",
) -> list[dict[str, Any]]:
    if not 1 <= batch_size <= 8:
        raise ValueError("batch_size must be within [1, 8]")
    root = Path(output_dir).resolve()
    sheets: list[dict[str, Any]] = []
    for offset in range(0, len(panels), batch_size):
        batch = list(panels[offset : offset + batch_size])
        sheet_id = f"{sheet_prefix}_{offset // batch_size + 1:03d}"
        directory = root / "sheets" / sheet_id
        image_path = directory / "contact_sheet.png"
        asyncio.run(_compose_sheet_async(sheet_id, batch, image_path))
        mapping_path = directory / "mapping.json"
        mapping_path.write_text(
            json.dumps({"sheet_id": sheet_id, "panels": batch}, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        sheets.append({"sheet_id": sheet_id, "image_path": str(image_path), "panels": batch})
    return sheets


class FacadeVisualReviewAgent:
    def __init__(self, service: TextReasoningService) -> None:
        self.service = service

    def review(self, sheet: dict[str, Any], *, allowed_semantic_types: Iterable[str]) -> FacadeSheetReview:
        sheet_id = str(sheet["sheet_id"])
        data: dict[str, Any] = {}
        mapping = {panel["panel_id"]: panel for panel in sheet["panels"]}
        context = {
            "sheet_id": sheet_id,
            "panel_mapping": [
                {key: panel.get(key, "front_normal" if key == "alignment_mode" else None) for key in (
                    "panel_id", "asset_id", "display_name", "semantic_type", "source_id",
                    "source_front_axis", "native_extent_xyz", "native_scale_confidence",
                    "alignment_mode",
                )}
                for panel in sheet["panels"]
            ],
            "allowed_semantic_types": sorted(set(allowed_semantic_types)),
        }
        prompt = (
            "You are CityG's facade-asset visual audit agent. Review every exact panel in the contact sheet. "
            "Each panel has two views: LEFT is viewed from the annotated alignment axis; RIGHT is oblique. "
            "For front_normal/multi_face_module this axis is the proposed facade-facing direction; for path_tangent "
            "or roof_alignment it is only a module alignment reference, so report uncertain rather than inventing a front. "
            "The red arrow is the annotated alignment direction, RGB lines are source XYZ, the gray human is "
            "1.75 m, and the ground grid spacing is 1 m. Judge whether the labeled semantic type matches, whether "
            "the front axis is correct/opposite/orthogonal, whether the model is upright, whether scale is plausible, "
            "and whether it is ready for exterior placement. Calibrate visual_quality strictly: 1.0 is reserved for "
            "exceptional production-quality geometry/materials with no visible defect; ordinary clean PBR is 0.75-0.9, "
            "and stylized low-poly content normally remains below 0.75. If semantic_assessment is incorrect, use "
            "placement_readiness=needs_review unless the issue makes the asset unusable. Do not infer details hidden in the image. Use only exact "
            "panel_id/asset_id pairs and suggested semantic types from allowed_semantic_types. Return strict JSON.\n"
            + json.dumps(context, ensure_ascii=False, sort_keys=True)
        )
        try:
            message = ChatMessage(role="user", content=prompt, image_paths=(Path(sheet["image_path"]),))
            method = getattr(self.service, "complete_with_metadata", None)
            raw_text = (
                method([message], FACADE_VISUAL_REVIEW_SCHEMA).content
                if callable(method)
                else self.service.complete([message], FACADE_VISUAL_REVIEW_SCHEMA)
            )
            data = _parse_json_object(raw_text)
            if str(data.get("sheet_id")) != sheet_id:
                raise ValueError("VLM returned a different sheet_id")
            reviews: list[dict[str, Any]] = []
            seen: set[str] = set()
            allowed_types = set(allowed_semantic_types)
            for item in data.get("reviews", []):
                panel_id = str(item.get("panel_id", ""))
                asset_id = str(item.get("asset_id", ""))
                if panel_id not in mapping or mapping[panel_id]["asset_id"] != asset_id:
                    raise ValueError("VLM review contains an invalid panel binding")
                if panel_id in seen:
                    raise ValueError("VLM review contains duplicate panel IDs")
                suggested = item.get("suggested_semantic_type")
                normalized = dict(item)
                normalized["confidence"] = min(1.0, max(0.0, float(item["confidence"])))
                normalized["visual_quality"] = min(1.0, max(0.0, float(item["visual_quality"])))
                normalized["issues"] = [str(value) for value in item.get("issues", [])[:5]]
                if suggested is not None and str(suggested) not in allowed_types:
                    normalized["issues"].append(
                        f"unrecognized semantic suggestion ignored: {suggested}"
                    )
                    normalized["suggested_semantic_type"] = None
                reviews.append(normalized)
                seen.add(panel_id)
            if seen != set(mapping):
                raise ValueError("VLM must review every contact-sheet panel exactly once")
            reviews.sort(key=lambda item: item["panel_id"])
            return FacadeSheetReview(True, sheet_id, tuple(reviews), str(data.get("summary", "")), raw=data)
        except Exception as error:
            return FacadeSheetReview(
                False,
                sheet_id,
                error=f"{type(error).__name__}: {error}",
                raw=data,
            )


def _opposite_axis(axis: str) -> str:
    return ("-" if axis.startswith("+") else "+") + axis[-1]


def apply_facade_visual_reviews(
    payload: dict[str, Any],
    sheet_reviews: Sequence[FacadeSheetReview],
    *,
    confidence_threshold: float = 0.90,
    semantic_threshold: float = 0.95,
) -> tuple[dict[str, Any], dict[str, int]]:
    """Apply only exact, high-confidence corrections to a copied index."""

    result = json.loads(json.dumps(payload))
    by_id = {record["asset_id"]: record for record in result.get("assets", [])}
    allowed_types = set(result.get("summary", {}).get("semantic_type_counts", {}))
    stats: Counter[str] = Counter()
    for sheet in sheet_reviews:
        if not sheet.available:
            stats["unavailable_sheets"] += 1
            continue
        for review in sheet.reviews:
            record = by_id.get(str(review["asset_id"]))
            if record is None:
                stats["unknown_asset"] += 1
                continue
            confidence = float(review["confidence"])
            audit = {
                "sheet_id": sheet.sheet_id,
                "panel_id": review["panel_id"],
                "confidence": confidence,
                "semantic_assessment": review["semantic_assessment"],
                "front_axis_assessment": review["front_axis_assessment"],
                "upright": bool(review["upright"]),
                "scale_assessment": review["scale_assessment"],
                "placement_readiness": review["placement_readiness"],
                "visual_quality": review["visual_quality"],
                "issues": review["issues"],
                "reason": review["reason"],
            }
            record.setdefault("visual_review_history", []).append(audit)
            record["quality"]["vlm_visual_quality_score"] = review["visual_quality"]
            record["scale"]["visual_scale_assessment"] = review["scale_assessment"]
            record["scale"]["visual_scale_confidence"] = confidence

            front_applicable = bool(
                record["orientation"].get("front_axis_review_applicable", True)
            )
            if not review["upright"]:
                record["orientation"]["visual_review_required"] = True
                stats["deferred_not_upright"] += 1
            elif not front_applicable:
                if confidence >= confidence_threshold and review["placement_readiness"] == "ready":
                    record["orientation"]["visual_review_required"] = False
                    record["orientation"]["visual_alignment_status"] = "observed_non_front_module"
                    stats["non_front_alignment_observed"] += 1
                else:
                    stats["orientation_deferred"] += 1
            elif confidence >= confidence_threshold:
                assessment = review["front_axis_assessment"]
                if assessment == "correct":
                    record["orientation"]["confidence"] = "high"
                    record["orientation"]["visual_review_required"] = False
                    stats["orientation_verified"] += 1
                elif assessment == "opposite":
                    record["orientation"]["source_front_axis"] = _opposite_axis(
                        record["orientation"]["source_front_axis"]
                    )
                    record["orientation"]["confidence"] = "high"
                    record["orientation"]["visual_review_required"] = False
                    audit["applied_front_axis"] = record["orientation"]["source_front_axis"]
                    stats["orientation_flipped"] += 1
                elif assessment == "orthogonal" and confidence >= semantic_threshold:
                    suggested = review.get("suggested_source_front_axis")
                    if suggested in {"+X", "-X", "+Z", "-Z"}:
                        record["orientation"]["source_front_axis"] = suggested
                        record["orientation"]["confidence"] = "high"
                        record["orientation"]["visual_review_required"] = False
                        audit["applied_front_axis"] = suggested
                        stats["orientation_reassigned"] += 1
                else:
                    stats["orientation_deferred"] += 1

            if (
                review["semantic_assessment"] == "incorrect"
                and confidence >= semantic_threshold
                and review.get("suggested_semantic_type") in allowed_types
            ):
                semantic_type = str(review["suggested_semantic_type"])
                record["semantic_type"] = semantic_type
                record["asset_family"] = _asset_family(semantic_type)
                record["compatible_building_functions"] = list(
                    _compatibility(semantic_type, str(record["source_asset_id"]))
                )
                record["compatible_facade_zones"] = list(_zones(semantic_type))
                record["placement"] = _placement(semantic_type)
                record["repeatability"] = _repeatability(semantic_type)
                record["quality"]["semantic_confidence"] = "high"
                audit["applied_semantic_type"] = semantic_type
                stats["semantic_corrected"] += 1

            if confidence >= confidence_threshold:
                if review["placement_readiness"] == "reject":
                    record["selection_status"] = "rejected_visual"
                    stats["rejected"] += 1
                elif review["placement_readiness"] == "needs_review" or review[
                    "scale_assessment"
                ] in {"too_small", "too_large"}:
                    record["selection_status"] = "needs_visual_review"
                    stats["deferred"] += 1
                else:
                    stats["ready"] += 1
            else:
                stats["low_confidence"] += 1

    records = result.get("assets", [])
    result["summary"]["semantic_type_counts"] = dict(
        sorted(Counter(record["semantic_type"] for record in records).items())
    )
    result["summary"]["selection_status_counts"] = dict(
        sorted(Counter(record["selection_status"] for record in records).items())
    )
    result["summary"]["visually_reviewed_count"] = sum(
        bool(record.get("visual_review_history")) for record in records
    )
    result["annotation_policy"]["visual_writeback"] = {
        "orientation_confidence_threshold": confidence_threshold,
        "semantic_confidence_threshold": semantic_threshold,
        "policy": "exact_binding_high_confidence_only",
    }
    return result, dict(sorted(stats.items()))


def run_facade_visual_review(
    index_path: str | Path,
    output_dir: str | Path,
    service: TextReasoningService | None,
    *,
    project_root: str | Path,
    output_index_path: str | Path | None = None,
    max_assets: int = 24,
    batch_size: int = 8,
    max_expansion_assets: int = 8,
) -> dict[str, Any]:
    root = Path(output_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    index = FacadeAssetIndex.load(index_path)
    candidates = plan_facade_visual_review(index, max_assets=max_assets)
    plan = {"schema_version": "cityg.facade_visual_review_plan.v1", "candidates": [item.mapping() for item in candidates]}
    (root / "plan.json").write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    round_one_root = root / "round_1"
    panels = render_facade_panels(candidates, project_root, round_one_root)
    sheets = compose_facade_sheets(
        panels, round_one_root, batch_size=batch_size, sheet_prefix="facade_round1_sheet"
    )
    reviews: list[FacadeSheetReview] = []
    if service is not None:
        agent = FacadeVisualReviewAgent(service)
        allowed_types = index.summary.get("semantic_type_counts", {}).keys()
        for sheet in sheets:
            review = agent.review(sheet, allowed_semantic_types=allowed_types)
            reviews.append(review)
            review_path = Path(sheet["image_path"]).parent / "vlm_review.json"
            review_path.write_text(json.dumps(review.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    expansion = plan_facade_visual_expansion(
        index, candidates, reviews, max_assets=max_expansion_assets
    )
    expansion_panels: list[dict[str, Any]] = []
    expansion_sheets: list[dict[str, Any]] = []
    if expansion:
        expansion_plan = {
            "schema_version": "cityg.facade_visual_review_expansion.v1",
            "trigger": "uncertain_or_problematic_representative_strata",
            "candidates": [item.mapping() for item in expansion],
        }
        (root / "expansion_plan.json").write_text(
            json.dumps(expansion_plan, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        round_two_root = root / "round_2"
        expansion_panels = render_facade_panels(expansion, project_root, round_two_root)
        expansion_sheets = compose_facade_sheets(
            expansion_panels,
            round_two_root,
            batch_size=batch_size,
            sheet_prefix="facade_round2_sheet",
        )
        if service is not None:
            agent = FacadeVisualReviewAgent(service)
            allowed_types = index.summary.get("semantic_type_counts", {}).keys()
            for sheet in expansion_sheets:
                review = agent.review(sheet, allowed_semantic_types=allowed_types)
                reviews.append(review)
                review_path = Path(sheet["image_path"]).parent / "vlm_review.json"
                review_path.write_text(
                    json.dumps(review.to_dict(), indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
    reviewed_payload, writeback = apply_facade_visual_reviews(index.payload, reviews)
    destination = Path(output_index_path).resolve() if output_index_path else root / "asset_annotations_reviewed.json"
    save_facade_asset_annotations(reviewed_payload, destination)
    report = {
        "schema_version": "cityg.facade_visual_review_report.v1",
        "planned_assets": len(candidates),
        "expanded_assets": len(expansion),
        "rendered_panels": len(panels) + len(expansion_panels),
        "sheet_count": len(sheets) + len(expansion_sheets),
        "vlm_available_sheets": sum(review.available for review in reviews),
        "writeback": writeback,
        "output_index": str(destination),
        "sheets": [review.to_dict() for review in reviews],
    }
    (root / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


__all__ = [
    "FACADE_VISUAL_REVIEW_SCHEMA",
    "FacadeReviewCandidate",
    "FacadeSheetReview",
    "FacadeVisualReviewAgent",
    "apply_facade_visual_reviews",
    "compose_facade_sheets",
    "plan_facade_visual_review",
    "plan_facade_visual_expansion",
    "render_facade_panels",
    "run_facade_visual_review",
]
