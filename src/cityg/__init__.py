"""CityG public package API."""

from cityg.assets import (
    AssetProvider,
    AssetRecord,
    AssetRegistry,
    AssetResolver,
    MaterialLibrary,
    MaterialRecord,
)
from cityg.asset_providers import (
    AssetProviderError,
    HunyuanAssetEndpoint,
    HunyuanAssetProvider,
)
from cityg.closed_loop import (
    ClosedLoopBudget,
    ClosedLoopCoordinator,
    ClosedLoopResult,
    IssueRouter,
)
from cityg.pipeline import GenerationResult, GenerationPipeline
from cityg.repair import PatchEngine, PatchOperation, WorldPatch
from cityg.schemas import CCWP_SCHEMA_VERSION, City, CitySpec, WorldProgram
from cityg.observation import AdaptiveObservationPlanner, ObservationPlan, ViewSpec
from cityg.adaptive_review import aggregate_visual_reviews, route_visual_issues, run_adaptive_review
from cityg.editing import (
    BatchEditResult,
    EditAgent,
    EditPlanResult,
    EditRunResult,
    SceneReference,
    resolve_scene,
    rollback_scene,
    run_batch_edit,
    run_edit,
)
from cityg.subtree_transactions import (
    SubtreeTransactionResult,
    FloorSubtreePlanner,
    BuildingSubtreePlanner,
    UrbanSubgraphPlanner,
    replace_subtree,
)
from cityg.outdoor_assets import (
    OutdoorAssetAudit,
    OutdoorAssetPackBuilder,
    OutdoorAssetSlot,
    default_outdoor_slots,
    import_outdoor_asset,
)
from cityg.buildings import (
    BuildingArchetype,
    BuildingSelection,
    BuildingSelectionContext,
    BuildingSelector,
    DEFAULT_BUILDING_CATALOG,
)
from cityg.naming import (
    IDENTITY_SCHEMA_VERSION,
    alias_index,
    annotate_city_identities,
    identity_for,
    identity_registry,
    resolve_alias,
)

__all__ = [
    "CCWP_SCHEMA_VERSION",
    "City",
    "CitySpec",
    "ClosedLoopBudget",
    "ClosedLoopCoordinator",
    "ClosedLoopResult",
    "GenerationPipeline",
    "GenerationResult",
    "IssueRouter",
    "PatchEngine",
    "PatchOperation",
    "WorldPatch",
    "WorldProgram",
    "AdaptiveObservationPlanner",
    "ObservationPlan",
    "ViewSpec",
    "aggregate_visual_reviews",
    "route_visual_issues",
    "run_adaptive_review",
    "EditAgent",
    "BatchEditResult",
    "EditPlanResult",
    "EditRunResult",
    "SceneReference",
    "resolve_scene",
    "run_edit",
    "run_batch_edit",
    "rollback_scene",
    "SubtreeTransactionResult",
    "FloorSubtreePlanner",
    "BuildingSubtreePlanner",
    "UrbanSubgraphPlanner",
    "replace_subtree",
    "AssetRecord",
    "AssetRegistry",
    "AssetProvider",
    "AssetResolver",
    "MaterialRecord",
    "MaterialLibrary",
    "AssetProviderError",
    "HunyuanAssetEndpoint",
    "HunyuanAssetProvider",
    "OutdoorAssetAudit",
    "OutdoorAssetPackBuilder",
    "OutdoorAssetSlot",
    "default_outdoor_slots",
    "import_outdoor_asset",
    "BuildingArchetype",
    "BuildingSelection",
    "BuildingSelectionContext",
    "BuildingSelector",
    "DEFAULT_BUILDING_CATALOG",
    "IDENTITY_SCHEMA_VERSION",
    "alias_index",
    "annotate_city_identities",
    "identity_for",
    "identity_registry",
    "resolve_alias",
]
__version__ = "0.2.0"
