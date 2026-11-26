"""OpenUSD Phase 2 backend built on deterministic geometry IR."""

from __future__ import annotations

import shutil
import json
from dataclasses import replace
from pathlib import Path

from cityg.assets import AssetRegistry, MaterialLibrary, MaterialRecord
from cityg.geometry import GeometryCompiler, GeometryValidator
from cityg.geometry.incremental import (
    affected_buildings,
    building_fingerprints,
    merge_building_scene,
    scene_from_manifest,
)
from cityg.runtime import ActivationManager, run_interaction_smoke
from cityg.schemas import Artifact, City
from cityg.serialization import load_city, save_json, to_primitive
from cityg.usd import UsdaPackageValidator, UsdaWriter
from cityg.validation import CityValidator


class OpenUSDBackend:
    """Compile CityG to layered USDA plus simulator-neutral runtime manifests."""

    def __init__(
        self,
        geometry_compiler: GeometryCompiler | None = None,
        geometry_validator: GeometryValidator | None = None,
        usd_writer: UsdaWriter | None = None,
    ) -> None:
        self.geometry_compiler = geometry_compiler or GeometryCompiler()
        self.geometry_validator = geometry_validator or GeometryValidator()
        self.usd_writer = usd_writer or UsdaWriter()

    def compile(
        self,
        city: City,
        output_dir: Path,
        *,
        _scene_override=None,
    ) -> list[Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        scene = _scene_override or self.geometry_compiler.compile(city)
        geometry_report = self.geometry_validator.validate(city, scene)
        report_path = save_json(
            geometry_report.to_dict(), output_dir / "geometry_validation_report.json"
        )
        if not geometry_report.ok:
            raise ValueError(
                f"Geometry validation failed with {len(geometry_report.errors)} error(s)"
            )

        interaction_report = run_interaction_smoke(scene)
        interaction_report_path = save_json(
            interaction_report.to_dict(), output_dir / "interaction_smoke_report.json"
        )
        if not interaction_report.ok:
            raise ValueError(
                f"Interaction smoke failed with {len(interaction_report.errors)} error(s)"
            )

        material_library_path = self._export_material_library(scene, output_dir)

        usd_dir = output_dir / "usd"
        usd_paths = self.usd_writer.write(city, scene, usd_dir)
        usd_report = UsdaPackageValidator().validate(usd_dir / "city.usda")
        usd_report_path = save_json(
            usd_report.to_dict(), output_dir / "usd_validation_report.json"
        )
        if not usd_report.ok:
            raise ValueError(
                f"USDA package validation failed with {len(usd_report.errors)} error(s)"
            )
        geometry_path = save_json(scene, output_dir / "geometry_manifest.json")
        asset_registry_path = self._export_asset_registry(scene, output_dir)
        navigation_path = save_json(scene.navigation, output_dir / "navigation.json")
        interactions_path = save_json(
            {"state_machines": scene.state_machines}, output_dir / "interactions.json"
        )
        activation_path = save_json(
            {
                "layers": scene.layers,
                "activation_tiers": scene.activation_tiers,
                "building_prototypes": scene.building_prototypes,
            },
            output_dir / "activation_manifest.json",
        )

        usda_bytes = sum(path.stat().st_size for path in usd_paths)
        metrics = dict(geometry_report.metrics)
        activation = ActivationManager(scene)
        first_building = next(city.iter_buildings())
        first_floor = first_building.floors[0]
        overview_primitives = activation.primitive_count(activation.select("overview"))
        active_building_primitives = activation.primitive_count(
            activation.select("active_building", building_id=first_building.id)
        )
        active_floor_primitives = activation.primitive_count(
            activation.select(
                "active_floor",
                building_id=first_building.id,
                floor_id=first_floor.id,
            )
        )
        metrics.update(
            {
                "usda_layer_count": len(usd_paths),
                "usda_bytes": usda_bytes,
                "geometry_manifest_bytes": geometry_path.stat().st_size,
                "estimated_full_ir_bytes": geometry_path.stat().st_size,
                "estimated_overview_ir_bytes": round(
                    geometry_path.stat().st_size
                    * metrics["overview_primitive_count"]
                    / max(1, metrics["primitive_count"])
                ),
                "reference_arc_count": usd_report.metrics["reference_arc_count"],
                "payload_arc_count": usd_report.metrics["payload_arc_count"],
                "instanceable_prim_count": usd_report.metrics[
                    "instanceable_prim_count"
                ],
                "overview_loaded_primitive_count": overview_primitives,
                "sample_active_building_primitive_count": active_building_primitives,
                "sample_active_floor_primitive_count": active_floor_primitives,
                "interaction_integration_steps": interaction_report.metrics[
                    "integration_steps"
                ],
                "structural_physics_errors": interaction_report.metrics[
                    "structural_physics_errors"
                ],
                "asset_registry_count": len(
                    self.geometry_compiler.asset_registry.list_all()
                ),
                "resolved_asset_primitive_count": scene.metadata.get(
                    "resolved_asset_primitive_count", 0
                ),
                "asset_registry_path": str(asset_registry_path.relative_to(output_dir)),
                "material_library_path": (
                    str(material_library_path.relative_to(output_dir))
                    if material_library_path
                    else None
                ),
            }
        )
        metrics_path = save_json(metrics, output_dir / "compile_metrics.json")

        artifacts = [
            (
                "artifact_openusd_root",
                "openusd_stage",
                "usd/city.usda",
                "application/vnd.usda",
            ),
            (
                "artifact_geometry_manifest",
                "geometry_manifest",
                "geometry_manifest.json",
                "application/json",
            ),
            (
                "artifact_navigation",
                "navigation_graph",
                "navigation.json",
                "application/json",
            ),
            (
                "artifact_interactions",
                "interaction_state",
                "interactions.json",
                "application/json",
            ),
            (
                "artifact_interaction_smoke",
                "interaction_validation",
                "interaction_smoke_report.json",
                "application/json",
            ),
            (
                "artifact_activation_manifest",
                "activation_manifest",
                "activation_manifest.json",
                "application/json",
            ),
        ]
        self._register_artifacts(city, artifacts)
        city_report = CityValidator().validate(city)
        if not city_report.ok:
            raise ValueError("Artifact registration broke CCWP integrity")
        city_path = save_json(city, output_dir / "city.json")
        return [
            report_path,
            interaction_report_path,
            usd_report_path,
            geometry_path,
            asset_registry_path,
            *( [material_library_path] if material_library_path else [] ),
            navigation_path,
            interactions_path,
            activation_path,
            metrics_path,
            city_path,
            *usd_paths,
        ]

    def compile_incremental(
        self,
        city: City,
        output_dir: Path,
        previous_output_dir: Path,
        changed_entity_ids: list[str] | tuple[str, ...] | set[str],
    ) -> list[Path]:
        """Recompile only buildings affected by room/building edits.

        The previous package is treated as an immutable cache.  A room ID is
        resolved to its containing building and that building is the safe
        invalidation unit; all other building primitives are reused from the
        previous geometry manifest.  If the cache is absent, the method
        transparently falls back to a full compile.
        """

        output_dir.mkdir(parents=True, exist_ok=True)
        previous_output_dir = Path(previous_output_dir)
        previous_manifest = previous_output_dir / "geometry_manifest.json"
        previous_city_path = previous_output_dir / "city.json"
        changed = {str(item) for item in changed_entity_ids}
        if not changed or not previous_manifest.is_file():
            paths = self.compile(city, output_dir)
            incremental_path = save_json(
                {
                    "mode": "full_fallback",
                    "changed_entity_ids": sorted(changed),
                    "affected_buildings": [],
                    "building_fingerprints": building_fingerprints(city),
                },
                output_dir / "incremental_manifest.json",
            )
            return [*paths, incremental_path]

        try:
            affected = affected_buildings(city, changed)
        except ValueError as error:
            # Road/district/city edits can change shared global layers.  It is
            # safer to invalidate the whole package than to merge stale roads
            # with a building subset; keep the reason in the manifest.
            paths = self.compile(city, output_dir)
            incremental_path = save_json(
                {
                    "mode": "full_fallback",
                    "changed_entity_ids": sorted(changed),
                    "affected_buildings": [],
                    "fallback_reason": str(error),
                    "building_fingerprints": building_fingerprints(city),
                },
                output_dir / "incremental_manifest.json",
            )
            return [*paths, incremental_path]
        try:
            previous = scene_from_manifest(
                json.loads(previous_manifest.read_text(encoding="utf-8"))
            )
            previous_city = load_city(previous_city_path) if previous_city_path.is_file() else None
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            paths = self.compile(city, output_dir)
            incremental_path = save_json(
                {
                    "mode": "full_fallback",
                    "changed_entity_ids": sorted(changed),
                    "affected_buildings": [],
                    "fallback_reason": f"invalid incremental cache: {error}",
                    "building_fingerprints": building_fingerprints(city),
                },
                output_dir / "incremental_manifest.json",
            )
            return [*paths, incremental_path]
        def geography_signature(value):
            return to_primitive({"rivers": value.rivers, "bridges": value.bridges,
                "roads": value.road_network,
                "building_frontages": [(b.id,b.footprint,b.entrance,b.metadata.get("orientation_deg"),
                    b.metadata.get("appearance_plan",{}).get("envelope"),b.metadata.get("massing_style"),
                    [(d.id,d.position,d.width_m) for f in b.floors if f.level==0 for d in f.doors
                     if d.room_b_id is None]) for b in value.iter_buildings()],
                "parcels": [(p.id, p.bounds, p.boundary, p.holes) for p in value.iter_parcels()]})
        if previous_city is not None and geography_signature(city) != geography_signature(previous_city):
            paths = self.compile(city, output_dir)
            manifest = save_json({"mode": "full_fallback", "changed_entity_ids": sorted(changed),
                                 "fallback_reason": "Global streetscape or frontage geometry changed"},
                                 output_dir / "incremental_manifest.json")
            return [*paths, manifest]
        subset = self.geometry_compiler.compile(city, building_ids=affected)
        # Ground-floor conformance can move a door even if its canonical
        # position did not change. Rebuild the road-owned frontage in that case.
        def compiled_entries(scene):
            ids = {d.id for b in city.iter_buildings() if b.id in affected
                   for f in b.floors if f.level == 0 for d in f.doors if d.room_b_id is None}
            return {p.owner_id: (p.center, p.rotation_z_deg,
                    tuple(p.metadata.get("aperture_size_m", (p.size.x, p.size.y, p.size.z))))
                    for p in scene.primitives if p.owner_id in ids and p.semantic_class == "door"}
        if "pedestrian_network" not in previous.metadata or compiled_entries(previous) != compiled_entries(subset):
            paths = self.compile(city, output_dir)
            manifest = save_json({"mode":"full_fallback","changed_entity_ids":sorted(changed),
                                  "fallback_reason":"Pedestrian network missing or compiled entrance changed"},
                                 output_dir / "incremental_manifest.json")
            return [*paths, manifest]
        merged, stats = merge_building_scene(
            city,
            previous,
            subset,
            affected,
            previous_city=previous_city,
        )
        paths = self.compile(city, output_dir, _scene_override=merged)
        incremental_path = save_json(
            {
                "mode": "incremental_building_merge",
                "changed_entity_ids": sorted(changed),
                "affected_buildings": sorted(affected),
                "room_changes_recompile_building": True,
                "building_fingerprints": building_fingerprints(city),
                **stats,
            },
            output_dir / "incremental_manifest.json",
        )
        return [*paths, incremental_path]

    def _export_asset_registry(self, scene, output_dir: Path) -> Path:
        """Copy portable mesh payloads next to the compiled viewer manifests.

        The canonical registry may point at a shared cache (often an absolute
        path under ``assets/generated``).  A compiled scene must not depend on
        that cache still existing, so GLB/GLTF payloads are copied into the
        output package and the exported registry is rewritten to use relative
        paths.  Procedural-only records remain unchanged.
        """
        assets_dir = output_dir / "assets"
        meshes_dir = assets_dir / "meshes"
        export_registry = AssetRegistry()
        referenced_asset_ids = {
            str(primitive.metadata["asset_id"])
            for primitive in scene.primitives
            if primitive.metadata.get("asset_id")
        }
        for record in self.geometry_compiler.asset_registry.list_all():
            if record.asset_id not in referenced_asset_ids:
                continue
            geometry_path = record.geometry_path
            if geometry_path and Path(geometry_path).suffix.lower() in {".glb", ".gltf"}:
                source = self.geometry_compiler.asset_registry.resolve_path(geometry_path)
                if source.is_file():
                    destination = meshes_dir / f"{record.asset_id}{source.suffix.lower()}"
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, destination)
                    record = replace(
                        record,
                        geometry_path=str(Path("meshes") / destination.name),
                    )
            export_registry.register(record)
        return export_registry.save(assets_dir / "asset_registry.json")

    def _export_material_library(self, scene, output_dir: Path) -> Path | None:
        """Copy only referenced PBR files and rewrite them as portable paths."""
        library = self.geometry_compiler.material_library
        if library is None:
            return None
        assets_dir = output_dir / "assets"
        material_dir = assets_dir / "materials"
        exported = MaterialLibrary()

        def copy_channel(material_id: str, channel: str, raw_path: str | None) -> str | None:
            if not raw_path:
                return None
            source = library.resolve_path(raw_path)
            if not source.is_file():
                return None
            safe_id = "".join(char if char.isalnum() or char in "_.-" else "_" for char in material_id)
            destination = material_dir / f"{safe_id}_{channel}{source.suffix.lower()}"
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            return str(Path("materials") / destination.name)

        exported_by_id: dict[str, MaterialRecord] = {}
        records = {record.material_id: record for record in library.list_all()}
        # Per-building colourways live in the geometry IR, not in the shared
        # source library. Package their channels too, keeping exports portable.
        for material in scene.materials:
            if material.id not in records:
                data = to_primitive(material)
                data['material_id'] = data.pop('id')
                records[material.id] = MaterialRecord.from_dict(data)
        for record in records.values():
            portable = replace(
                record,
                base_color_path=copy_channel(record.material_id, "base_color", record.base_color_path),
                normal_path=copy_channel(record.material_id, "normal", record.normal_path),
                roughness_path=copy_channel(record.material_id, "roughness", record.roughness_path),
                ambient_occlusion_path=copy_channel(
                    record.material_id, "ambient_occlusion", record.ambient_occlusion_path
                ),
            )
            exported.register(portable)
            exported_by_id[record.material_id] = portable

        environment_relative = None
        if library.environment_path:
            source = library.resolve_path(library.environment_path)
            if source.is_file():
                destination = assets_dir / "environment" / source.name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
                environment_relative = str(Path("environment") / destination.name)
                exported.set_environment(environment_relative)

        # Geometry paths are relative to the compiled root, while material
        # library paths are relative to assets/material_library.json.
        rewritten = []
        for material in scene.materials:
            record = exported_by_id.get(material.id)
            if record is None:
                rewritten.append(material)
                continue
            rewritten.append(
                replace(
                    material,
                    base_color_path=(
                        str(Path("assets") / record.base_color_path)
                        if record.base_color_path else None
                    ),
                    normal_path=(
                        str(Path("assets") / record.normal_path)
                        if record.normal_path else None
                    ),
                    roughness_path=(
                        str(Path("assets") / record.roughness_path)
                        if record.roughness_path else None
                    ),
                    ambient_occlusion_path=(
                        str(Path("assets") / record.ambient_occlusion_path)
                        if record.ambient_occlusion_path else None
                    ),
                )
            )
        scene.materials = rewritten
        scene.metadata["environment_path"] = (
            str(Path("assets") / environment_relative) if environment_relative else None
        )
        return exported.save(assets_dir / "material_library.json")

    @staticmethod
    def _register_artifacts(city: City, definitions) -> None:
        program = city.world_program
        by_id = {artifact.id: artifact for artifact in program.artifacts}
        city_node = next(node for node in program.nodes if node.entity_id == city.id)
        canonical = by_id.get("artifact_canonical_manifest")
        if canonical is not None:
            canonical.status = "compiled"
        for artifact_id, artifact_type, uri, media_type in definitions:
            artifact = by_id.get(artifact_id)
            if artifact is None:
                artifact = Artifact(
                    id=artifact_id,
                    owner_id=city.id,
                    artifact_type=artifact_type,
                    uri=uri,
                    media_type=media_type,
                    status="compiled",
                )
                program.artifacts.append(artifact)
                by_id[artifact_id] = artifact
            else:
                artifact.status = "compiled"
            if artifact_id not in city_node.artifact_ids:
                city_node.artifact_ids.append(artifact_id)
