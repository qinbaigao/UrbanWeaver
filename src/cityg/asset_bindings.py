"""Detached asset unions for recompiling existing scene packages."""
from dataclasses import replace
from pathlib import Path

from cityg.assets import AssetRegistry


def merge_pinned_registries(*sources):
    """First binding wins; later registries only add previously absent IDs.

    Sources may be registries or paths. Relative geometry paths are resolved
    against each source before merging; the result never saves over a source.
    """
    result = AssetRegistry()
    for source in sources:
        if source is None:
            continue
        if not isinstance(source, AssetRegistry):
            path = Path(source).expanduser()
            if not path.is_file():
                continue
            source = AssetRegistry(path)
        for record in source.list_all():
            if result.get(record.asset_id) is not None:
                continue
            if record.geometry_path:
                record = replace(record, geometry_path=str(source.resolve_path(record.geometry_path).resolve()))
            result.register(record)
    return result
