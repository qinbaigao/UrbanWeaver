#!/usr/bin/env python3
"""Build CityG's default semantic PBR facade material library."""

from pathlib import Path

from cityg.facade_materials import build_default_facade_material_library


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    library = build_default_facade_material_library(
        root / "assets" / "incoming" / "facade_materials",
        root / "assets" / "material_library.json",
        environment_path=root / "assets" / "incoming" / "hdri" / "urban_street_02_2k.hdr",
    )
    print(f"Facade material library: {library.manifest_path}")
    print(f"Materials: {len(library.list_all())}")


if __name__ == "__main__":
    main()
