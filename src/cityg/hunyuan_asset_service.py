"""Isolated local HunyuanDiT -> Hunyuan3D asset generation worker.

Heavy model libraries are imported lazily so the request contract and its tests
remain usable in CityG's lightweight core environment.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
import re
import threading
import traceback
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


HUNYUAN_LICENSE_ID = "Tencent-Hunyuan-3D-2.0-Community-License"


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "asset"


@dataclass(frozen=True)
class HunyuanWorkerConfig:
    repo_path: Path
    shape_model_root: Path
    text_to_image_model: Path
    output_root: Path
    shape_subfolder: str = "hunyuan3d-dit-v2-0-turbo"
    paint_subfolder: str = "hunyuan3d-paint-v2-0"
    device: str = "cuda"
    low_vram: bool = True
    enable_flashvdm: bool = True
    octree_resolution: int = 256
    shape_steps: int = 5
    guidance_scale: float = 5.0
    face_count: int = 40000

    @property
    def delight_path(self) -> Path:
        return self.shape_model_root / "hunyuan3d-delight-v2-0"

    @property
    def texture_available(self) -> bool:
        return self.delight_path.is_dir() and (
            self.shape_model_root / self.paint_subfolder
        ).is_dir()

    def validate(self) -> None:
        required = {
            "Hunyuan3D repository": self.repo_path,
            "shape model root": self.shape_model_root,
            "shape checkpoint": self.shape_model_root / self.shape_subfolder,
            "text-to-image checkpoint": self.text_to_image_model,
        }
        missing = [f"{label}: {path}" for label, path in required.items() if not path.exists()]
        if missing:
            raise ValueError("Missing local Hunyuan resources:\n- " + "\n- ".join(missing))
        if self.octree_resolution < 64:
            raise ValueError("octree_resolution must be at least 64")
        if self.shape_steps <= 0 or self.face_count <= 0:
            raise ValueError("shape_steps and face_count must be positive")


def validate_generation_request(payload: dict[str, Any]) -> dict[str, Any]:
    description = str(payload.get("description", "")).strip()
    category = str(payload.get("category", "generic_object")).strip()
    if not description:
        raise ValueError("description must not be empty")
    if not category:
        raise ValueError("category must not be empty")
    dimensions = payload.get("dimensions_m")
    if dimensions is not None:
        if (
            not isinstance(dimensions, list)
            or len(dimensions) != 3
            or any(not isinstance(value, (int, float)) or value <= 0 for value in dimensions)
        ):
            raise ValueError("dimensions_m must contain three positive numbers")
        dimensions = tuple(float(value) for value in dimensions)
    seed = int(payload.get("seed", 0))
    if seed < 0 or seed > 2**32 - 1:
        raise ValueError("seed must be in [0, 2^32-1]")
    return {
        "description": description,
        "category": category,
        "dimensions_m": dimensions,
        "seed": seed,
        "texture": bool(payload.get("texture", True)),
    }


def generation_identity(request: dict[str, Any], config: HunyuanWorkerConfig) -> str:
    canonical = {
        **request,
        "shape_subfolder": config.shape_subfolder,
        "paint_subfolder": config.paint_subfolder,
        "octree_resolution": config.octree_resolution,
        "shape_steps": config.shape_steps,
        "face_count": config.face_count,
    }
    digest = hashlib.sha256(
        json.dumps(canonical, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]
    return f"hunyuan_{_slug(request['category'])}_{digest}"


class HunyuanAssetWorker:
    """Serial, cache-aware worker intended for one local GPU."""

    def __init__(self, config: HunyuanWorkerConfig) -> None:
        config.validate()
        self.config = config
        self.config.output_root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def health(self) -> dict[str, Any]:
        return {
            "status": "ready",
            "service": "cityg-hunyuan-assets",
            "device": self.config.device,
            "low_vram": self.config.low_vram,
            "shape_model": str(self.config.shape_model_root / self.config.shape_subfolder),
            "text_to_image_model": str(self.config.text_to_image_model),
            "texture_requested_model": str(
                self.config.shape_model_root / self.config.paint_subfolder
            ),
            "texture_available": self.config.texture_available,
            "missing_optional_resources": (
                []
                if self.config.texture_available
                else [str(self.config.delight_path)]
            ),
        }

    def generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = validate_generation_request(payload)
        asset_id = generation_identity(request, self.config)
        asset_dir = self.config.output_root / asset_id
        manifest_path = asset_dir / "manifest.json"
        with self._lock:
            if manifest_path.is_file():
                cached = json.loads(manifest_path.read_text(encoding="utf-8"))
                geometry = Path(cached["asset_record"]["geometry_path"])
                if geometry.is_file() and geometry.stat().st_size > 0:
                    return {**cached, "cache_hit": True}
            asset_dir.mkdir(parents=True, exist_ok=True)
            result = self._run_generation(asset_id, asset_dir, request)
            manifest_path.write_text(
                json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            return {**result, "cache_hit": False}

    def _run_generation(
        self, asset_id: str, asset_dir: Path, request: dict[str, Any]
    ) -> dict[str, Any]:
        self._prepare_import_path()
        source_path = asset_dir / "source.png"
        condition_path = asset_dir / "condition.png"
        geometry_path = asset_dir / "asset.glb"
        warnings: list[str] = []

        image = self._text_to_image(self._image_prompt(request), request["seed"])
        image.save(source_path)
        condition = self._remove_background(image)
        condition.save(condition_path)
        self._release_cuda()

        mesh = self._image_to_mesh(condition, request["seed"])
        texture_status = "not_requested"
        if request["texture"]:
            if self.config.texture_available:
                mesh = self._paint_mesh(mesh, condition)
                texture_status = "generated"
            else:
                texture_status = "skipped_missing_delight_checkpoint"
                warnings.append(
                    "Texture generation skipped because hunyuan3d-delight-v2-0 is missing"
                )

        mesh, validation = self._canonicalize_and_validate(mesh)
        mesh.export(geometry_path, file_type="glb")
        if not geometry_path.is_file() or geometry_path.stat().st_size == 0:
            raise RuntimeError("Hunyuan export produced an empty GLB")
        self._release_cuda()

        dimensions = request["dimensions_m"] or (1.0, 1.0, 1.0)
        record = {
            "asset_id": asset_id,
            "category": request["category"],
            "tags": [request["category"], "generated", "hunyuan3d", "textured" if texture_status == "generated" else "untextured"],
            "dimensions_m": list(dimensions),
            "geometry_path": str(geometry_path.resolve()),
            "collision_path": None,
            "preview_path": str(source_path.resolve()),
            "material_id": None,
            "source": "hunyuan3d2_local",
            "license_id": HUNYUAN_LICENSE_ID,
            "quality_score": 0.7 if texture_status == "generated" else 0.55,
            "metadata": {
                "generated_content": True,
                "description": request["description"],
                "seed": request["seed"],
                "texture_status": texture_status,
                "coordinate_system": "right_handed_z_up_unit_bounds",
                "generator": {
                    "text_to_image": str(self.config.text_to_image_model),
                    "shape": self.config.shape_subfolder,
                    "paint": self.config.paint_subfolder if texture_status == "generated" else None,
                },
                "mesh_validation": validation,
                "warnings": warnings,
            },
        }
        return {
            "schema_version": "cityg.generated_asset.v1",
            "asset_record": record,
            "artifacts": {
                "source_image": str(source_path.resolve()),
                "condition_image": str(condition_path.resolve()),
                "geometry": str(geometry_path.resolve()),
            },
            "warnings": warnings,
        }

    def _prepare_import_path(self) -> None:
        import sys

        repo = str(self.config.repo_path.resolve())
        if repo not in sys.path:
            sys.path.insert(0, repo)

    def _image_prompt(self, request: dict[str, Any]) -> str:
        category = request["category"].replace("_", " ")
        return (
            f"A single physically plausible {category}, {request['description']}, "
            "complete object fully visible, centered, orthographic product view, "
            "realistic materials, no people, no text, no floor, no surrounding objects"
        )

    def _text_to_image(self, prompt: str, seed: int):
        from hy3dgen.text2image import HunyuanDiTPipeline

        pipeline = HunyuanDiTPipeline(
            str(self.config.text_to_image_model), device=self.config.device
        )
        try:
            return pipeline(prompt, seed=seed)
        finally:
            del pipeline
            self._release_cuda()

    @staticmethod
    def _remove_background(image):
        from hy3dgen.rembg import BackgroundRemover

        remover = BackgroundRemover()
        try:
            return remover(image)
        finally:
            del remover

    def _image_to_mesh(self, image, seed: int):
        import torch
        from hy3dgen.shapegen import Hunyuan3DDiTFlowMatchingPipeline

        pipeline = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(
            str(self.config.shape_model_root),
            subfolder=self.config.shape_subfolder,
            use_safetensors=True,
            device=self.config.device,
        )
        if self.config.enable_flashvdm:
            pipeline.enable_flashvdm(mc_algo="mc")
        try:
            generator = torch.Generator(self.config.device).manual_seed(seed)
            return pipeline(
                image=image,
                generator=generator,
                octree_resolution=self.config.octree_resolution,
                num_inference_steps=self.config.shape_steps,
                guidance_scale=self.config.guidance_scale,
                mc_algo="mc",
            )[0]
        finally:
            del pipeline
            self._release_cuda()

    def _paint_mesh(self, mesh, image):
        from hy3dgen.shapegen import DegenerateFaceRemover, FaceReducer, FloaterRemover
        from hy3dgen.texgen import Hunyuan3DPaintPipeline

        mesh = FloaterRemover()(mesh)
        mesh = DegenerateFaceRemover()(mesh)
        mesh = FaceReducer()(mesh, max_facenum=self.config.face_count)
        pipeline = Hunyuan3DPaintPipeline.from_pretrained(
            str(self.config.shape_model_root), subfolder=self.config.paint_subfolder
        )
        # The reference Paint pipelines contain a custom local DiffusionPipeline
        # whose prompt/control tensors are not compatible with Diffusers'
        # generic CPU-offload hooks (they can remain split across CPU and CUDA).
        # Shape is released before this stage, and an A100 has ample headroom for
        # keeping Paint on one device, so prefer correctness over offload here.
        try:
            return pipeline(mesh, image=image)
        finally:
            del pipeline
            self._release_cuda()

    @staticmethod
    def _canonicalize_and_validate(mesh):
        import numpy as np
        import trimesh

        if isinstance(mesh, trimesh.Scene):
            mesh = mesh.dump(concatenate=True)
        if not isinstance(mesh, trimesh.Trimesh):
            raise RuntimeError(f"Unsupported mesh result: {type(mesh).__name__}")
        if len(mesh.vertices) < 4 or len(mesh.faces) < 4:
            raise RuntimeError("Generated mesh has insufficient geometry")
        # Hunyuan's native samples are Y-up. CityG is Z-up.
        rotation = trimesh.transformations.rotation_matrix(math.pi / 2, [1, 0, 0])
        mesh.apply_transform(rotation)
        bounds = np.asarray(mesh.bounds, dtype=np.float64)
        extents = bounds[1] - bounds[0]
        if not np.isfinite(bounds).all() or np.any(extents <= 1e-8):
            raise RuntimeError("Generated mesh has invalid or degenerate bounds")
        center = (bounds[0] + bounds[1]) / 2
        mesh.vertices = (np.asarray(mesh.vertices) - center) / extents
        normalized_bounds = np.asarray(mesh.bounds)
        components = len(mesh.split(only_watertight=False))
        validation = {
            "vertex_count": int(len(mesh.vertices)),
            "face_count": int(len(mesh.faces)),
            "connected_component_count": int(components),
            "watertight": bool(mesh.is_watertight),
            "native_extents": [round(float(value), 8) for value in extents],
            "normalized_bounds": [
                [round(float(value), 8) for value in row]
                for row in normalized_bounds
            ],
        }
        return mesh, validation

    @staticmethod
    def _release_cuda() -> None:
        gc.collect()
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.ipc_collect()
        except (ImportError, RuntimeError):
            pass


class _Handler(BaseHTTPRequestHandler):
    server_version = "CityGHunyuanAssets/0.1"

    @property
    def worker(self) -> HunyuanAssetWorker:
        return self.server.worker  # type: ignore[attr-defined]

    def do_GET(self) -> None:  # noqa: N802
        if self.path.rstrip("/") == "/health":
            self._json(HTTPStatus.OK, self.worker.health())
            return
        self._json(HTTPStatus.NOT_FOUND, {"error": "unknown route"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path.rstrip("/") != "/v1/assets/generate":
            self._json(HTTPStatus.NOT_FOUND, {"error": "unknown route"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 1_000_000:
                raise ValueError("request body must be between 1 byte and 1 MB")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("request body must be a JSON object")
            self._json(HTTPStatus.OK, self.worker.generate(payload))
        except (ValueError, json.JSONDecodeError) as error:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
        except Exception as error:  # keep model failures visible to the client
            traceback.print_exc()
            self._json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": type(error).__name__, "message": str(error)},
            )

    def _json(self, status: HTTPStatus, value: dict[str, Any]) -> None:
        body = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        print(f"asset-worker: {format % args}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Serve local Hunyuan assets to CityG")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8091)
    parser.add_argument(
        "--repo-path",
        type=Path,
        default=Path("../Hunyuan3D-2"),
    )
    parser.add_argument(
        "--model-root",
        type=Path,
        default=Path("models/Hunyuan3D-2"),
    )
    parser.add_argument(
        "--t2i-model",
        type=Path,
        default=Path("models/HunyuanDiT-v1.1-Diffusers-Distilled"),
    )
    parser.add_argument("--output-root", type=Path, default=Path("assets/generated"))
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--shape-subfolder", default="hunyuan3d-dit-v2-0-turbo")
    parser.add_argument("--paint-subfolder", default="hunyuan3d-paint-v2-0")
    parser.add_argument("--octree-resolution", type=int, default=256)
    parser.add_argument("--shape-steps", type=int, default=5)
    parser.add_argument("--face-count", type=int, default=40000)
    parser.add_argument("--no-flashvdm", action="store_true")
    parser.add_argument("--keep-models", action="store_true", help="Reserved for a future throughput mode")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    config = HunyuanWorkerConfig(
        repo_path=args.repo_path.expanduser().resolve(),
        shape_model_root=args.model_root.expanduser().resolve(),
        text_to_image_model=args.t2i_model.expanduser().resolve(),
        output_root=args.output_root.expanduser().resolve(),
        shape_subfolder=args.shape_subfolder,
        paint_subfolder=args.paint_subfolder,
        device=args.device,
        low_vram=not args.keep_models,
        enable_flashvdm=not args.no_flashvdm,
        octree_resolution=args.octree_resolution,
        shape_steps=args.shape_steps,
        face_count=args.face_count,
    )
    worker = HunyuanAssetWorker(config)
    server = ThreadingHTTPServer((args.host, args.port), _Handler)
    server.worker = worker  # type: ignore[attr-defined]
    print(f"CityG Hunyuan asset worker: http://{args.host}:{server.server_address[1]}")
    print(json.dumps(worker.health(), indent=2, ensure_ascii=False))
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nAsset worker stopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
