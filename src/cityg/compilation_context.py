"""Restore visual compiler settings when an existing package is edited."""
from pathlib import Path

from cityg.facade_assets import FacadeAssetIndex
from cityg.facade_runtime import FacadeAssetRuntime


def restore_facade_runtime(metadata, registry):
    if not metadata.get('facade_asset_system_enabled'):
        return None
    context = metadata.get('facade_asset_runtime_context')
    if context:
        return FacadeAssetRuntime(FacadeAssetIndex(context['index']), registry,
                                  project_root=context['project_root'])
    # Legacy packages did not serialize the reviewed module index. Recover
    # from this installation, or fail explicitly instead of dropping facades.
    project = Path(__file__).resolve().parents[2]
    index = project/'assets/facades/asset_annotations_reviewed.json'
    if not index.is_file():
        raise ValueError('Source uses facade modules but its runtime index cannot be restored')
    return FacadeAssetRuntime.load(index, registry, project_root=project)
