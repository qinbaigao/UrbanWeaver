#!/usr/bin/env python3
"""Render facade contact sheets, optionally audit with VLM, and write reviewed tags."""

from __future__ import annotations

import argparse
from pathlib import Path

from cityg.facade_visual_review import run_facade_visual_review
from cityg.services.interfaces import ModelEndpoint
from cityg.services.openai_compatible import OpenAICompatibleService


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", default="assets/facades/asset_annotations.json")
    parser.add_argument("--output", default="outputs/facade_asset_review")
    parser.add_argument("--output-index")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/v1")
    parser.add_argument("--model", default="cityg-llm")
    parser.add_argument("--max-assets", type=int, default=24)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--max-expansion-assets", type=int, default=8)
    parser.add_argument("--timeout", type=float, default=240.0)
    parser.add_argument("--render-only", action="store_true")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    index = Path(args.index)
    output = Path(args.output)
    output_index = Path(args.output_index) if args.output_index else None
    if not index.is_absolute():
        index = project_root / index
    if not output.is_absolute():
        output = project_root / output
    if output_index is not None and not output_index.is_absolute():
        output_index = project_root / output_index
    service = None
    if not args.render_only:
        service = OpenAICompatibleService(
            ModelEndpoint(
                base_url=args.base_url,
                model=args.model,
                timeout_s=args.timeout,
                temperature=0.0,
                top_p=0.8,
                max_tokens=4096,
                seed=0,
                enable_thinking=False,
            )
        )
    report = run_facade_visual_review(
        index,
        output,
        service,
        project_root=project_root,
        output_index_path=output_index,
        max_assets=args.max_assets,
        batch_size=args.batch_size,
        max_expansion_assets=args.max_expansion_assets,
    )
    print(f"Rendered {report['rendered_panels']} panels in {report['sheet_count']} sheet(s)")
    print(f"VLM sheets available: {report['vlm_available_sheets']}")
    print(f"Write-back: {report['writeback']}")
    print(f"Reviewed index: {report['output_index']}")


if __name__ == "__main__":
    main()
