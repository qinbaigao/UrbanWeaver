"""Write layered, human-auditable USDA without requiring the pxr Python package."""

from __future__ import annotations

import json
import math
import posixpath
import re
import shutil
from collections import defaultdict
from pathlib import Path, PurePosixPath

from cityg.geometry.model import GeometryPrimitive, GeometryScene
from cityg.schemas import City


class UsdaWriter:
    """Compile GeometryScene layers into OpenUSD ASCII files.

    Runtime validation with ``ovphysx``/``usdchecker`` is intentionally separate;
    this writer keeps Phase 2 generation deterministic and dependency-free.
    """

    def write(
        self,
        city: City,
        scene: GeometryScene,
        output_dir: str | Path,
        active_floor_id: str | None = None,
    ) -> list[Path]:
        root = Path(output_dir)
        self._material_specs = {item.id: item for item in scene.materials}
        active_building_id = None
        if active_floor_id is not None:
            for building in city.iter_buildings():
                if any(floor.id == active_floor_id for floor in building.floors):
                    active_building_id = building.id
                    break
            if active_building_id is None:
                raise ValueError(f"Unknown active floor: {active_floor_id}")
        paths = {layer.id: root / layer.relative_path for layer in scene.layers}
        external_assets = self._prepare_asset_package(city, scene, root)
        primitives_by_layer: dict[str, list[GeometryPrimitive]] = defaultdict(list)
        for primitive in scene.primitives:
            primitives_by_layer[primitive.layer_id].append(primitive)

        written = []
        for layer in scene.layers:
            if (
                active_floor_id is not None
                and layer.layer_type == "building_interior"
                and layer.owner_id != active_building_id
            ):
                continue
            if (
                active_floor_id is not None
                and layer.layer_type == "floor"
                and layer.owner_id != active_floor_id
            ):
                continue
            path = paths[layer.id]
            path.parent.mkdir(parents=True, exist_ok=True)
            if layer.layer_type == "root":
                content = self._root_layer(city, scene, path, paths)
            elif layer.layer_type == "assets":
                content = self._assets_layer(scene, path)
            elif layer.layer_type == "roads":
                content = self._geometry_layer(
                    "Roads", primitives_by_layer[layer.id], path, paths["assets"], external_assets
                )
            elif layer.layer_type == "district":
                content = self._district_layer(
                    city,
                    layer.owner_id,
                    scene,
                    path,
                    paths,
                    active_building_id,
                )
            elif layer.layer_type == "building_shell":
                content = self._geometry_layer(
                    "BuildingShell", primitives_by_layer[layer.id], path, paths["assets"], external_assets
                )
            elif layer.layer_type == "building_interior":
                content = self._interior_layer(
                    layer.owner_id, scene, path, paths, active_floor_id
                )
            elif layer.layer_type == "floor":
                content = self._geometry_layer(
                    "Floor", primitives_by_layer[layer.id], path, paths["assets"], external_assets
                )
            else:
                raise ValueError(f"Unsupported USDA layer type: {layer.layer_type}")
            path.write_text(content, encoding="utf-8")
            written.append(path)
        return written

    def _root_layer(self, city, scene, current_path, paths):
        lines = self._header("City")
        lines.extend(
            [
                'def Xform "City"',
                "{",
                f'    custom string cityg:entityId = {self._string(city.id)}',
                f'    custom string cityg:schemaVersion = {self._string(city.schema_version)}',
                f'    custom string cityg:coordinateSystem = {self._string(city.coordinate_system)}',
            ]
        )
        roads_asset = self._asset_path(current_path, paths["roads"])
        lines.extend(self._reference_prim("Roads", roads_asset, "/Roads", 1, payload=False))
        for district in city.districts:
            layer_id = f"district:{district.id}"
            asset = self._asset_path(current_path, paths[layer_id])
            lines.extend(
                self._reference_prim(
                    self._identifier(district.id), asset, "/District", 1, payload=False
                )
            )
        lines.append("}")
        lines.extend(
            [
                "",
                'def PhysicsScene "PhysicsScene"',
                "{",
                "    vector3f physics:gravityDirection = (0, 0, -1)",
                "    float physics:gravityMagnitude = 9.81",
                "}",
            ]
        )
        return "\n".join(lines) + "\n"

    def _assets_layer(self, scene, current_path):
        lines = self._header("Assets")
        lines.extend(['def Xform "Assets"', "{"])
        for material in sorted(scene.materials, key=lambda item: item.id):
            r, g, b = material.display_color
            for shape, usd_type in (("box", "Cube"), ("cylinder", "Cylinder"), ("sphere", "Sphere")):
                name = self._identifier(f"{shape}_{material.id}")
                lines.extend([
                    f'    def Xform "{name}" (',
                    "        instanceable = true",
                    "    )",
                    "    {",
                    f'        def {usd_type} "Geometry"',
                    "        {",
                    *(["            double size = 1"] if shape == "box" else []),
                    *(["            double radius = 0.5", "            double height = 1", '            token axis = "Z"'] if shape == "cylinder" else []),
                    *(["            double radius = 0.5"] if shape == "sphere" else []),
                    f"            color3f[] primvars:displayColor = [({self._number(r)}, {self._number(g)}, {self._number(b)})]",
                    f"            float primvars:displayOpacity = {self._number(material.opacity)}",
                    f"            custom string cityg:materialSource = {self._string(material.source)}",
                    f"            custom string cityg:materialLicense = {self._string(material.license_id)}",
                    f"            custom string cityg:baseColorPath = {self._string(material.base_color_path or '')}",
                    f"            custom string cityg:normalPath = {self._string(material.normal_path or '')}",
                    f"            custom string cityg:roughnessPath = {self._string(material.roughness_path or '')}",
                    f"            custom string cityg:ambientOcclusionPath = {self._string(material.ambient_occlusion_path or '')}",
                    f"            float cityg:textureScaleM = {self._number(material.texture_scale_m or 0.0)}",
                    "        }",
                    "    }",
                ])
        lines.append("}")
        return "\n".join(lines) + "\n"

    def _geometry_layer(
        self, default_prim, primitives, current_path, assets_path, external_assets=None
    ):
        lines = self._header(default_prim)
        lines.extend([f'def Xform "{default_prim}"', "{"])
        self._geometry_root = default_prim
        if any(p.material_id == "curtain_glass" for p in primitives):
            lines.extend([
                '    def Scope "Looks" {',
                '        def Material "CurtainGlass" {',
                f'            token outputs:surface.connect = </{default_prim}/Looks/CurtainGlass/Shader.outputs:surface>',
                '            def Shader "Shader" {',
                '                uniform token info:id = "UsdPreviewSurface"',
                '                color3f inputs:diffuseColor = (0.17, 0.36, 0.44)',
                '                float inputs:roughness = 0.13',
                '                float inputs:metallic = 0.03',
                '                float inputs:opacity = 0.55',
                '                float inputs:ior = 1.46',
                '                token outputs:surface',
                '            }', '        }', '    }',
            ])
        assets = self._asset_path(current_path, assets_path)
        for primitive in sorted(primitives, key=lambda item: item.id):
            lines.extend(
                self._primitive(
                    primitive,
                    assets,
                    indent=1,
                    current_path=current_path,
                    external_assets=external_assets or {},
                )
            )
        lines.append("}")
        return "\n".join(lines) + "\n"

    def _district_layer(
        self, city, district_id, scene, current_path, paths, active_building_id
    ):
        district = next(item for item in city.districts if item.id == district_id)
        lines = self._header("District")
        lines.extend(
            [
                'def Xform "District"',
                "{",
                f'    custom string cityg:entityId = {self._string(district.id)}',
            ]
        )
        for parcel in district.parcels:
            for building in parcel.buildings:
                name = self._identifier(building.id)
                lines.extend(
                    [
                        f'    def Xform "{name}"',
                        "    {",
                        f'        custom string cityg:entityId = {self._string(building.id)}',
                        f'        custom token cityg:prototype = {self._string(scene.building_prototypes[building.id])}',
                    ]
                )
                shell_asset = self._asset_path(
                    current_path, paths[f"shell:{building.id}"]
                )
                lines.extend(
                    self._reference_prim(
                        "Shell", shell_asset, "/BuildingShell", 2, payload=False
                    )
                )
                if active_building_id is None or building.id == active_building_id:
                    interior_asset = self._asset_path(
                        current_path, paths[f"interior:{building.id}"]
                    )
                    lines.extend(
                        self._reference_prim(
                            "Interior",
                            interior_asset,
                            "/BuildingInterior",
                            2,
                            payload=True,
                        )
                    )
                lines.append("    }")
        lines.append("}")
        return "\n".join(lines) + "\n"

    def _interior_layer(
        self, building_id, scene, current_path, paths, active_floor_id
    ):
        floors = [
            layer
            for layer in scene.layers
            if layer.layer_type == "floor" and layer.parent_layer_id == f"interior:{building_id}"
            and (active_floor_id is None or layer.owner_id == active_floor_id)
        ]
        lines = self._header("BuildingInterior")
        lines.extend(
            [
                'def Xform "BuildingInterior"',
                "{",
                f'    custom string cityg:entityId = {self._string(building_id)}',
            ]
        )
        for floor in floors:
            asset = self._asset_path(current_path, paths[floor.id])
            lines.extend(
                self._reference_prim(
                    self._identifier(floor.owner_id), asset, "/Floor", 1, payload=True
                )
            )
        lines.append("}")
        return "\n".join(lines) + "\n"

    def _primitive(
        self,
        primitive,
        assets_path,
        indent,
        *,
        current_path: Path | None = None,
        external_assets: dict[str, Path] | None = None,
    ):
        prefix = "    " * indent
        name = self._identifier(primitive.id)
        if primitive.primitive_type == "path_mesh":
            return self._path_mesh(primitive, indent)
        if primitive.body_type == "articulated":
            return self._articulated_primitive(primitive, indent)
        if primitive.body_type == "kinematic":
            return self._kinematic_primitive(primitive, indent)
        external_target = None
        asset_id = primitive.metadata.get("asset_id")
        if current_path is not None and external_assets and asset_id in external_assets:
            external_target = self._asset_path(current_path, external_assets[asset_id])
        shape = primitive.primitive_type if primitive.primitive_type in {"box", "cylinder", "sphere"} else "box"
        prototype = self._identifier(f"{shape}_{primitive.material_id}")
        visual_reference = (
            f"{prefix}    prepend references = @{external_target}@<"
            f"{primitive.metadata.get('asset_prim_path', '/Asset')}>"
            if external_target
            else f"{prefix}    prepend references = @{assets_path}@</Assets/{prototype}>"
        )
        lines = [f'{prefix}def Xform "{name}" (']
        lines.extend(
            [
                visual_reference,
                f"{prefix}    instanceable = true",
                f"{prefix})",
                f"{prefix}{{",
                f"{prefix}    double3 xformOp:translate = ({self._number(primitive.center.x)}, {self._number(primitive.center.y)}, {self._number(primitive.center.z)})",
                f"{prefix}    double xformOp:rotateZ = {self._number(primitive.rotation_z_deg)}",
                f"{prefix}    double3 xformOp:scale = ({self._number(primitive.size.x)}, {self._number(primitive.size.y)}, {self._number(primitive.size.z)})",
                f'{prefix}    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:rotateZ", "xformOp:scale"]',
                f"{prefix}    custom string cityg:ownerId = {self._string(primitive.owner_id)}",
                f"{prefix}    custom token cityg:semanticClass = {self._string(primitive.semantic_class)}",
                f"{prefix}    custom token cityg:bodyType = {self._string(primitive.body_type)}",
                f"{prefix}    custom token cityg:materialId = {self._string(primitive.material_id)}",
                f"{prefix}    custom int cityg:lod = {primitive.lod}",
                f"{prefix}    custom bool cityg:collisionEnabled = {str(primitive.collision_enabled).lower()}",
                f"{prefix}    custom string cityg:assetGeometryPath = {self._string(primitive.metadata.get('asset_geometry_path', ''))}",
                f"{prefix}    custom string cityg:assetLicense = {self._string(primitive.metadata.get('asset_license', ''))}",
            ]
        )
        lines.append(f"{prefix}}}")
        if primitive.collision_enabled:
            lines.extend(self._static_collision(primitive, indent))
        return lines

    def _kinematic_primitive(self, primitive, indent):
        """One moving visual/collider; never leave a static collider behind."""
        if primitive.primitive_type!='box':raise ValueError('Kinematic export supports boxes only')
        prefix='    '*indent;name=self._identifier(primitive.id)
        color=getattr(self,'_material_specs',{}).get(primitive.material_id)
        color=color.display_color if color is not None else (.55,.58,.62)
        return [f'{prefix}def Cube "{name}" (',
            f'{prefix}    prepend apiSchemas = ["PhysicsCollisionAPI", "PhysicsRigidBodyAPI"]',
            f'{prefix})',f'{prefix}{{',f'{prefix}    double size = 1',
            f'{prefix}    double3 xformOp:translate = ({primitive.center.x}, {primitive.center.y}, {primitive.center.z})',
            f'{prefix}    double xformOp:rotateZ = {primitive.rotation_z_deg}',
            f'{prefix}    double3 xformOp:scale = ({primitive.size.x}, {primitive.size.y}, {primitive.size.z})',
            f'{prefix}    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:rotateZ", "xformOp:scale"]',
            f'{prefix}    bool physics:rigidBodyEnabled = true',
            f'{prefix}    bool physics:kinematicEnabled = true',
            f'{prefix}    bool physics:collisionEnabled = {str(primitive.collision_enabled).lower()}',
            f'{prefix}    color3f[] primvars:displayColor = [{tuple(color)}]',
            f'{prefix}    custom string cityg:ownerId = {self._string(primitive.owner_id)}',
            f'{prefix}    custom token cityg:semanticClass = {self._string(primitive.semantic_class)}',
            f'{prefix}    custom token cityg:bodyType = "kinematic"',
            f'{prefix}    custom string cityg:elevatorRole = {self._string(primitive.metadata.get("elevator_role", ""))}',
            f'{prefix}}}']

    def _path_mesh(self, primitive, indent):
        """Use the actual swept surface for both rendering and CPU collision."""
        prefix = "    " * indent
        name = self._identifier(primitive.id)
        vertices = primitive.metadata["mesh_vertices"]
        faces = primitive.metadata["mesh_triangles"]
        material = self._material_specs[primitive.material_id]
        points = ", ".join("(" + ", ".join(self._number(v) for v in p) + ")" for p in vertices)
        indices = ", ".join(str(v) for face in faces for v in face)
        lines = [f'{prefix}def Mesh "{name}" (']
        if primitive.collision_enabled:
            lines.append(f'{prefix}    prepend apiSchemas = ["PhysicsCollisionAPI", "PhysicsMeshCollisionAPI"]')
        elif primitive.material_id == "curtain_glass":
            lines.append(f'{prefix}    prepend apiSchemas = ["MaterialBindingAPI"]')
        lines.extend([
            f'{prefix})', f'{prefix}{{',
            f'{prefix}    point3f[] points = [{points}]',
            f'{prefix}    int[] faceVertexCounts = [{", ".join("3" for _ in faces)}]',
            f'{prefix}    int[] faceVertexIndices = [{indices}]',
            f'{prefix}    uniform token subdivisionScheme = "none"',
            f'{prefix}    double3 xformOp:translate = ({primitive.center.x}, {primitive.center.y}, {primitive.center.z})',
            f'{prefix}    double3 xformOp:scale = ({primitive.size.x}, {primitive.size.y}, {primitive.size.z})',
            f'{prefix}    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]',
            f'{prefix}    color3f[] primvars:displayColor = [{tuple(material.display_color)}]',
            f'{prefix}    custom string cityg:ownerId = {self._string(primitive.owner_id)}',
            f'{prefix}    custom token cityg:semanticClass = {self._string(primitive.semantic_class)}',
            f'{prefix}    custom token cityg:materialId = {self._string(primitive.material_id)}',
            f'{prefix}    custom token cityg:bodyType = "static"',
            f'{prefix}    custom bool cityg:collisionEnabled = {str(primitive.collision_enabled).lower()}',
        ])
        if primitive.collision_enabled:
            lines.extend([f'{prefix}    bool physics:collisionEnabled = true',
                          f'{prefix}    token physics:approximation = "none"'])
        if primitive.semantic_class == "collision_envelope":
            lines.extend([f'{prefix}    token visibility = "invisible"',
                          f'{prefix}    token purpose = "guide"'])
        if primitive.material_id == "curtain_glass":
            lines.append(f'{prefix}    rel material:binding = </{self._geometry_root}/Looks/CurtainGlass>')
        lines.append(f'{prefix}}}')
        return lines

    @staticmethod
    def _prepare_asset_package(city, scene, root: Path) -> dict[str, Path]:
        """Copy normalized USD assets into the package and return target paths."""
        targets: dict[str, Path] = {}
        destination = root / "assets"
        destination.mkdir(parents=True, exist_ok=True)
        seen: set[str] = set()
        for primitive in scene.primitives:
            asset_id = primitive.metadata.get("asset_id")
            source_value = primitive.metadata.get("asset_geometry_path")
            if not asset_id or not source_value or asset_id in seen:
                continue
            seen.add(asset_id)
            source = Path(str(source_value))
            # GLB is retained in the manifest for the Web Viewer, but USDA can
            # reference only USD-family files.  Such assets use the box fallback.
            if source.suffix.lower() not in {".usd", ".usda", ".usdc"} or not source.is_file():
                continue
            safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(asset_id))
            target = destination / f"{safe_id}{source.suffix.lower()}"
            if not target.exists():
                shutil.copy2(source, target)
            targets[str(asset_id)] = target
        return targets

    def _static_collision(self, primitive, indent):
        """Author non-instanced physics beside an instanced visual primitive.

        ovphysx 0.5.9 does not register CollisionAPI nested inside CityG's
        instanceable external references as static shapes. A sibling collision
        prim preserves visual instancing while giving all USD Physics backends a
        concrete, local Gprim to consume.
        """

        prefix = "    " * indent
        name = self._identifier(f"collision_{primitive.id}")
        return [
            f'{prefix}def Cube "{name}" (',
            f'{prefix}    prepend apiSchemas = ["PhysicsCollisionAPI"]',
            f"{prefix})",
            f"{prefix}{{",
            f"{prefix}    double size = 1",
            f"{prefix}    double3 xformOp:translate = ({self._number(primitive.center.x)}, {self._number(primitive.center.y)}, {self._number(primitive.center.z)})",
            f"{prefix}    double xformOp:rotateZ = {self._number(primitive.rotation_z_deg)}",
            f"{prefix}    double3 xformOp:scale = ({self._number(primitive.size.x)}, {self._number(primitive.size.y)}, {self._number(primitive.size.z)})",
            f'{prefix}    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:rotateZ", "xformOp:scale"]',
            f'{prefix}    token visibility = "invisible"',
            f'{prefix}    token purpose = "guide"',
            f"{prefix}    bool physics:collisionEnabled = true",
            f"{prefix}    custom string cityg:ownerId = {self._string(primitive.owner_id)}",
            f"{prefix}    custom token cityg:semanticClass = {self._string(primitive.semantic_class)}",
            f"{prefix}    custom token cityg:bodyType = \"static_collision\"",
            f"{prefix}}}",
        ]

    def _articulated_primitive(self, primitive, indent):
        prefix = "    " * indent
        name = self._identifier(primitive.id)
        joint_name = self._identifier(f"joint_{primitive.id}")
        from cityg.geometry.door_kinematics import local_hinge as resolve_hinge
        local_hinge = resolve_hinge(
            (primitive.size.x, primitive.size.y, primitive.size.z), primitive.metadata)
        angle = math.radians(primitive.rotation_z_deg)
        cos_angle = math.cos(angle)
        sin_angle = math.sin(angle)
        rotated_hinge = (
            local_hinge[0] * cos_angle - local_hinge[1] * sin_angle,
            local_hinge[0] * sin_angle + local_hinge[1] * cos_angle,
            0.0,
        )
        world_hinge = (
            primitive.center.x + rotated_hinge[0],
            primitive.center.y + rotated_hinge[1],
            primitive.center.z,
        )
        lines = [
            f'{prefix}def Xform "{name}" (',
            f'{prefix}    prepend apiSchemas = ["PhysicsRigidBodyAPI", "PhysicsMassAPI"]',
            f"{prefix})",
            f"{prefix}{{",
            f"{prefix}    double3 xformOp:translate = ({self._number(primitive.center.x)}, {self._number(primitive.center.y)}, {self._number(primitive.center.z)})",
            f"{prefix}    double xformOp:rotateZ = {self._number(primitive.rotation_z_deg)}",
            f'{prefix}    uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:rotateZ"]',
            f"{prefix}    bool physics:rigidBodyEnabled = true",
            f"{prefix}    float physics:mass = {self._number(float(primitive.metadata.get('mass_kg', 1.0)))}",
            f"{prefix}    custom string cityg:ownerId = {self._string(primitive.owner_id)}",
            f"{prefix}    custom token cityg:semanticClass = {self._string(primitive.semantic_class)}",
            f"{prefix}    custom token cityg:bodyType = {self._string(primitive.body_type)}",
            f"{prefix}    custom string cityg:stateMachineId = {self._string(primitive.metadata.get('state_machine_id', ''))}",
            f'{prefix}    def Cube "Geometry" (',
            f'{prefix}        prepend apiSchemas = ["PhysicsCollisionAPI"]',
            f"{prefix}    )",
            f"{prefix}    {{",
            f"{prefix}        double size = 1",
            f"{prefix}        double3 xformOp:scale = ({self._number(primitive.size.x)}, {self._number(primitive.size.y)}, {self._number(primitive.size.z)})",
            f'{prefix}        uniform token[] xformOpOrder = ["xformOp:scale"]',
            f"{prefix}        bool physics:collisionEnabled = true",
            f"{prefix}    }}",
            f"{prefix}}}",
            f'{prefix}def PhysicsRevoluteJoint "{joint_name}"',
            f"{prefix}{{",
            f'{prefix}    uniform token physics:axis = "Z"',
            f"{prefix}    float physics:lowerLimit = {self._number(float(primitive.metadata.get('lower_limit_deg', 0.0)))}",
            f"{prefix}    float physics:upperLimit = {self._number(float(primitive.metadata.get('upper_limit_deg', 90.0)))}",
            f"{prefix}    point3f physics:localPos0 = ({self._number(world_hinge[0])}, {self._number(world_hinge[1])}, {self._number(world_hinge[2])})",
            f"{prefix}    point3f physics:localPos1 = ({self._number(local_hinge[0])}, {self._number(local_hinge[1])}, 0)",
            # Match joint frames at the closed pose, including rotated buildings.
            f"{prefix}    quatf physics:localRot0 = ({self._number(math.cos(angle / 2))}, 0, 0, {self._number(math.sin(angle / 2))})",
            f"{prefix}    quatf physics:localRot1 = (1, 0, 0, 0)",
            f"{prefix}    rel physics:body1 = <../{name}>",
            f"{prefix}}}",
        ]
        return lines

    @staticmethod
    def _reference_prim(name, asset_path, prim_path, indent, payload):
        prefix = "    " * indent
        arc = "prepend payload" if payload else "prepend references"
        return [
            f'{prefix}def Xform "{name}" (',
            f"{prefix}    {arc} = @{asset_path}@<{prim_path}>",
            f"{prefix})",
            f"{prefix}{{",
            f"{prefix}}}",
        ]

    @staticmethod
    def _header(default_prim):
        return [
            "#usda 1.0",
            "(",
            f'    defaultPrim = "{default_prim}"',
            "    metersPerUnit = 1",
            '    upAxis = "Z"',
            ")",
            "",
        ]

    @staticmethod
    def _asset_path(current: Path, target: Path) -> str:
        current_posix = PurePosixPath(current.as_posix())
        target_posix = PurePosixPath(target.as_posix())
        return posixpath.relpath(target_posix, current_posix.parent)

    @staticmethod
    def _identifier(value: str) -> str:
        result = re.sub(r"[^A-Za-z0-9_]", "_", value)
        if not result or result[0].isdigit():
            result = f"_{result}"
        return result

    @staticmethod
    def _string(value) -> str:
        return json.dumps(str(value), ensure_ascii=False)

    @staticmethod
    def _number(value: float) -> str:
        return format(float(value), ".9g")
