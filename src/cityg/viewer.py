"""Read-only HTTP server for the bundled CityG Web Viewer."""

from __future__ import annotations

import json
import mimetypes
import re
import shutil
import threading
import webbrowser
from dataclasses import dataclass, field
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from cityg.assets import AssetRegistry, MaterialLibrary
from cityg.geometry import GeometryCompiler, GeometryValidator
from cityg.runtime import run_interaction_smoke
from cityg.serialization import load_city, to_primitive
from cityg.validation import CityValidator
from cityg.viewer_streaming import partition_viewer_files
from cityg.viewer_lod import collect_viewer_lods
from cityg.viewer_sky import collect_viewer_skies, default_environment_file


VIEWER_FILES = (
    "task_replay.json",
    "robot_model.glb",
    "geometry_manifest.json",
    "city.json",
    "navigation.json",
    "interactions.json",
    "activation_manifest.json",
    "validation_report.json",
    "geometry_validation_report.json",
    "interaction_smoke_report.json",
    "usd_validation_report.json",
    "compile_metrics.json",
)


@dataclass(frozen=True)
class ViewerDataset:
    label: str
    source: str
    files: dict[str, bytes]
    assets: dict[str, bytes] = field(default_factory=dict)
    textures: dict[str, bytes] = field(default_factory=dict)
    material_textures: dict[str, dict[str, str]] = field(default_factory=dict)
    environments: dict[str, bytes] = field(default_factory=dict)
    asset_lods: dict[str, list[dict]] = field(default_factory=dict)
    sky_presets: dict[str, dict] = field(default_factory=dict)

    def config(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "source": self.source,
            "files": sorted(self.files),
            "asset_base": "/asset/",
            "asset_files": {asset_id: f"{asset_id}.glb" for asset_id in sorted(self.assets)},
            "asset_lods": self.asset_lods,
            "texture_base": "/texture/",
            "texture_files": {name: name for name in sorted(self.textures)},
            "material_textures": self.material_textures,
            "environment_base": "/environment/",
            "environment_file": default_environment_file(self.environments, self.sky_presets),
            "sky_presets": self.sky_presets,
            "read_only": True,
        }


def viewer_static_dir() -> Path:
    return Path(__file__).with_name("viewer_static")


def build_viewer_dataset(scene_path: str | Path) -> ViewerDataset:
    """Load compiled manifests, or derive them in memory from a canonical city."""

    requested = Path(scene_path).expanduser().resolve()
    if not requested.exists():
        raise ValueError(f"Viewer scene does not exist: {requested}")

    compiled_root = _find_compiled_root(requested)
    if compiled_root is not None:
        files = {
            name: (compiled_root / name).read_bytes()
            for name in VIEWER_FILES
            if (compiled_root / name).is_file()
        }
        if "city.json" not in files:
            raise ValueError(f"Compiled viewer scene is missing city.json: {compiled_root}")
        assets = _collect_assets(
            compiled_root / "assets" / "asset_registry.json",
            files.get("geometry_manifest.json", b""),
        )
        textures, material_textures, environments = _collect_material_textures(
            files.get("geometry_manifest.json", b""), compiled_root
        )
        files = partition_viewer_files(files)
        return ViewerDataset(
            compiled_root.name,
            "compiled_manifests",
            files,
            assets,
            textures,
            material_textures,
            environments,
            collect_viewer_lods(assets),
            collect_viewer_skies(environments),
        )

    city_path = requested if requested.is_file() else requested / "city.json"
    if not city_path.is_file():
        raise ValueError(
            "Viewer input must be city.json or a directory containing "
            "geometry_manifest.json/city.json"
        )
    city = load_city(city_path)
    registry_path = city_path.parent / "assets" / "asset_registry.json"
    material_path = city_path.parent / "assets" / "material_library.json"
    registry = AssetRegistry(registry_path) if registry_path.is_file() else None
    materials = MaterialLibrary(material_path) if material_path.is_file() else None
    geometry = GeometryCompiler(
        asset_registry=registry,
        material_library=materials,
    ).compile(city)
    city_report = CityValidator().validate(city)
    geometry_report = GeometryValidator().validate(city, geometry)
    interaction_report = run_interaction_smoke(geometry)
    values = {
        "geometry_manifest.json": geometry,
        "city.json": city,
        "navigation.json": geometry.navigation,
        "interactions.json": {"state_machines": geometry.state_machines},
        "activation_manifest.json": {
            "layers": geometry.layers,
            "activation_tiers": geometry.activation_tiers,
            "building_prototypes": geometry.building_prototypes,
        },
        "validation_report.json": city_report.to_dict(),
        "geometry_validation_report.json": geometry_report.to_dict(),
        "interaction_smoke_report.json": interaction_report.to_dict(),
    }
    files = {
        name: (json.dumps(to_primitive(value), ensure_ascii=False) + "\n").encode("utf-8")
        for name, value in values.items()
    }
    assets = _collect_assets(registry_path, files["geometry_manifest.json"])
    textures, material_textures, environments = _collect_material_textures(
        files["geometry_manifest.json"], city_path.parent
    )
    files = partition_viewer_files(files)
    return ViewerDataset(
        city.name,
        "derived_in_memory",
        files,
        assets,
        textures,
        material_textures,
        environments,
        collect_viewer_lods(assets),
        collect_viewer_skies(environments),
    )


def _collect_assets(registry_path: Path, geometry_payload: bytes = b"") -> dict[str, bytes]:
    """Read self-contained GLB payloads referenced by an asset registry."""
    if not registry_path.is_file():
        return {}
    registry = AssetRegistry(registry_path)
    referenced: set[str] = set()
    try:
        geometry = json.loads(geometry_payload.decode("utf-8"))
        referenced = {
            str(item.get("metadata", {}).get("asset_id"))
            for item in geometry.get("primitives", [])
            if item.get("metadata", {}).get("asset_id")
        }
    except (UnicodeDecodeError, json.JSONDecodeError):
        pass
    assets: dict[str, bytes] = {}
    for record in registry.list_all():
        if referenced and record.asset_id not in referenced:
            continue
        if not record.geometry_path:
            continue
        path = Path(record.geometry_path)
        if path.suffix.lower() != ".glb":
            continue
        resolved = registry.resolve_path(path)
        if resolved.is_file():
            assets[record.asset_id] = resolved.read_bytes()
    return assets


def _collect_material_textures(
    geometry_payload: bytes,
    base_dir: Path,
) -> tuple[dict[str, bytes], dict[str, dict[str, str]], dict[str, bytes]]:
    """Package referenced PBR files while retaining color-only fallbacks."""
    try:
        geometry = json.loads(geometry_payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}, {}, {}
    textures: dict[str, bytes] = {}
    mapping: dict[str, dict[str, str]] = {}
    referenced_materials = {
        str(item.get("material_id"))
        for item in geometry.get("primitives", [])
        if item.get("material_id")
    }
    for material in geometry.get("materials", []):
        material_id = str(material.get("id", ""))
        if not material_id:
            continue
        if referenced_materials and material_id not in referenced_materials:
            continue
        for channel in ("base_color", "normal", "roughness", "ambient_occlusion"):
            raw_path = material.get(f"{channel}_path")
            if not raw_path:
                continue
            source = Path(str(raw_path))
            candidates = [source] if source.is_absolute() else [base_dir / source, base_dir / "assets" / source]
            resolved = next((item for item in candidates if item.is_file()), None)
            if resolved is None:
                continue
            safe_name = f"{re.sub(r'[^A-Za-z0-9_.-]+', '_', material_id)}_{channel}{resolved.suffix.lower()}"
            textures[safe_name] = resolved.read_bytes()
            mapping.setdefault(material_id, {})[channel] = safe_name
    environments: dict[str, bytes] = {}
    raw_environment = geometry.get("metadata", {}).get("environment_path")
    if raw_environment:
        source = Path(str(raw_environment))
        candidates = (
            [source]
            if source.is_absolute()
            else [base_dir / source, base_dir / "assets" / source]
        )
        resolved = next((item for item in candidates if item.is_file()), None)
        if resolved is not None:
            safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", resolved.name)
            environments[safe_name] = resolved.read_bytes()
    return textures, mapping, environments


def _find_compiled_root(requested: Path) -> Path | None:
    candidates = [requested] if requested.is_dir() else []
    if requested.is_dir():
        candidates.append(requested / "openusd")
    for candidate in candidates:
        if (candidate / "geometry_manifest.json").is_file():
            return candidate
    return None


class CityGViewerHandler(SimpleHTTPRequestHandler):
    server_version = "CityGViewer/0.1"

    def __init__(
        self,
        *args,
        dataset: ViewerDataset,
        static_root: Path,
        **kwargs,
    ) -> None:
        self.dataset = dataset
        super().__init__(*args, directory=str(static_root), **kwargs)

    def do_GET(self) -> None:  # noqa: N802 - standard-library handler API
        path = unquote(urlparse(self.path).path)
        if path == "/api/config":
            self._send_json(self.dataset.config())
            return
        if path.startswith("/scene/"):
            name = path.removeprefix("/scene/")
            if "/" in name or name not in self.dataset.files:
                self.send_error(HTTPStatus.NOT_FOUND, "Unknown scene resource")
                return
            payload = self.dataset.files[name]
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "model/gltf-binary" if name.endswith('.glb') else "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)
            return
        if path.startswith("/asset/"):
            name = path.removeprefix("/asset/")
            if "/" in name or not name.endswith(".glb"):
                self.send_error(HTTPStatus.NOT_FOUND, "Unknown asset resource")
                return
            asset_id = name.removesuffix(".glb")
            payload = self.dataset.assets.get(asset_id)
            if payload is None:
                self.send_error(HTTPStatus.NOT_FOUND, "Unknown asset resource")
                return
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "model/gltf-binary")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "public, max-age=3600, immutable")
            self.end_headers()
            self.wfile.write(payload)
            return
        if path.startswith("/texture/"):
            name = path.removeprefix("/texture/")
            if "/" in name or name not in self.dataset.textures:
                self.send_error(HTTPStatus.NOT_FOUND, "Unknown texture resource")
                return
            payload = self.dataset.textures[name]
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", mimetypes.guess_type(name)[0] or "application/octet-stream")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "public, max-age=3600, immutable")
            self.end_headers()
            self.wfile.write(payload)
            return
        if path.startswith("/environment/"):
            name = path.removeprefix("/environment/")
            if "/" in name or name not in self.dataset.environments:
                self.send_error(HTTPStatus.NOT_FOUND, "Unknown environment resource")
                return
            payload = self.dataset.environments[name]
            self.send_response(HTTPStatus.OK)
            self.send_header(
                "Content-Type",
                mimetypes.guess_type(name)[0] or "application/octet-stream",
            )
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "public, max-age=3600, immutable")
            self.end_headers()
            self.wfile.write(payload)
            return
        super().do_GET()

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        super().end_headers()

    def _send_json(self, value: Any) -> None:
        payload = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args) -> None:
        print(f"viewer: {format % args}")


def serve_viewer(
    scene_path: str | Path,
    *,
    host: str = "127.0.0.1",
    port: int = 5173,
    open_browser: bool = True,
) -> None:
    server, url, dataset = create_viewer_server(scene_path, host=host, port=port)
    print(f"CityG Viewer: {url}")
    print(f"Scene: {dataset.label} ({dataset.source}, read-only)")
    print("Press Ctrl+C to stop.")
    if open_browser:
        threading.Timer(0.35, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nCityG Viewer stopped.")
    finally:
        server.server_close()


def create_viewer_server(
    scene_path: str | Path,
    *,
    host: str = "127.0.0.1",
    port: int = 5173,
) -> tuple[ThreadingHTTPServer, str, ViewerDataset]:
    """Create (but do not start) a Viewer server.

    The explicit lifecycle is useful for automated review loops that need to
    render a scene before and after a local patch in one process.
    """
    static_root = viewer_static_dir()
    if not (static_root / "index.html").is_file():
        raise ValueError(
            "CityG Viewer frontend is not built. Run `cd viewer && npm install && npm run build`."
        )
    dataset = build_viewer_dataset(scene_path)
    handler = partial(
        CityGViewerHandler,
        dataset=dataset,
        static_root=static_root,
    )
    server = ThreadingHTTPServer((host, port), handler)
    actual_port = server.server_address[1]
    display_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    url = f"http://{display_host}:{actual_port}"
    return server, url, dataset


PORTABLE_SERVER = '''#!/usr/bin/env python3
"""Serve this exported CityG scene locally."""
import argparse
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import os
import threading
import webbrowser

parser = argparse.ArgumentParser(description="Serve a portable CityG Viewer.")
parser.add_argument("--host", default="127.0.0.1")
parser.add_argument("--port", type=int, default=0, help="0 selects a free port")
browser = parser.add_mutually_exclusive_group()
browser.add_argument(
    "--open-browser",
    dest="open_browser",
    action="store_true",
    default=True,
    help="open the Viewer in the default browser after the server starts",
)
browser.add_argument(
    "--no-browser",
    dest="open_browser",
    action="store_false",
    help="start the server without opening a browser (for automated review)",
)
args = parser.parse_args()

root = Path(__file__).resolve().parent
os.chdir(root)
server = ThreadingHTTPServer((args.host, args.port), SimpleHTTPRequestHandler)
port = server.server_address[1]
display_host = "127.0.0.1" if args.host in {"0.0.0.0", "::"} else args.host
url = f"http://{display_host}:{port}"
print(f"CityG Viewer: {url}")
if not args.open_browser:
    print("Open the URL above in a browser when ready.")
print("Press Ctrl+C to stop.")
if args.open_browser:
    threading.Timer(0.3, lambda: webbrowser.open(url)).start()
try:
    server.serve_forever()
except KeyboardInterrupt:
    pass
finally:
    server.server_close()
'''


PORTABLE_README = """# Portable CityG Viewer

This directory is self-contained and read-only. It does not require CityG,
OpenUSD, vLLM, Node.js, or a discrete GPU.

On macOS, open Terminal in this directory and run:

```bash
python3 serve.py
```

The launcher selects a free local port and opens it in the default browser.
Automated review should use `python3 serve.py --no-browser`. Press Ctrl+C in
Terminal to stop.
The **Open folder** control can load another compiled CityG scene from disk.

Use **Navigation preview** in the Render quality selector while moving through
large scenes. It keeps lightweight building silhouettes and road context only.
Switch to **Presentation** when you want textured materials, outdoor GLBs,
lighting and shadows for final screenshots. The legacy HI-FI query/API flags
remain accepted for backwards compatibility but are no longer exposed in the
interface.
"""


def export_portable_viewer(scene_path: str | Path, output_dir: str | Path) -> Path:
    """Create a self-contained browser viewer suitable for copying to macOS."""

    static_root = viewer_static_dir()
    if not (static_root / "index.html").is_file():
        raise ValueError(
            "CityG Viewer frontend is not built. Run `cd viewer && npm install && npm run build`."
        )
    destination = Path(output_dir).expanduser().resolve()
    if destination.exists() and any(destination.iterdir()):
        raise ValueError(f"Portable viewer output must be empty: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copytree(static_root, destination, dirs_exist_ok=True)
    dataset = build_viewer_dataset(scene_path)
    scene_dir = destination / "scene"
    scene_dir.mkdir()
    for name, payload in dataset.files.items():
        (scene_dir / name).write_bytes(payload)
    assets_dir = destination / "assets"
    assets_dir.mkdir(exist_ok=True)
    for asset_id, payload in dataset.assets.items():
        (assets_dir / f"{asset_id}.glb").write_bytes(payload)
    textures_dir = destination / "textures"
    textures_dir.mkdir(exist_ok=True)
    for filename, payload in dataset.textures.items():
        (textures_dir / filename).write_bytes(payload)
    environment_dir = destination / "environment"
    environment_dir.mkdir(exist_ok=True)
    for filename, payload in dataset.environments.items():
        (environment_dir / filename).write_bytes(payload)
    config = {
        "label": dataset.label,
        "source": "portable_export",
        "original_source": dataset.source,
        "files": sorted(dataset.files),
        "asset_base": "./assets/",
        "asset_files": {asset_id: f"{asset_id}.glb" for asset_id in sorted(dataset.assets)},
        "asset_lods": dataset.asset_lods,
        "texture_base": "./textures/",
        "texture_files": {name: name for name in sorted(dataset.textures)},
        "material_textures": dataset.material_textures,
        "environment_base": "./environment/",
        "environment_file": default_environment_file(dataset.environments, dataset.sky_presets),
        "sky_presets": dataset.sky_presets,
        "read_only": True,
    }
    (destination / "viewer-config.json").write_text(
        json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (destination / "serve.py").write_text(PORTABLE_SERVER, encoding="utf-8")
    (destination / "README.md").write_text(PORTABLE_README, encoding="utf-8")
    return destination
