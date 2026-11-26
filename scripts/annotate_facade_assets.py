#!/usr/bin/env python3
"""Build CityG's machine-readable facade asset annotation index."""

from __future__ import annotations

import argparse
from pathlib import Path

from cityg.facade_assets import build_facade_asset_annotations, save_facade_asset_annotations


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default="assets/facades/asset_annotations.json",
        help="output path relative to the CityG project root",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    output = Path(args.output)
    if not output.is_absolute():
        output = project_root / output
    payload = build_facade_asset_annotations(project_root)
    save_facade_asset_annotations(payload, output)
    summary = payload["summary"]
    print(f"Annotated {summary['asset_count']} facade assets -> {output}")
    print(f"Sources: {summary['source_counts']}")
    print(f"Status: {summary['selection_status_counts']}")


if __name__ == "__main__":
    main()
