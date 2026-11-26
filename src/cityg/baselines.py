"""Small, content-addressed records for immutable-by-convention scene baselines."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


DEFAULT_BASELINE_FILES = (
    "city.json",
    "geometry_manifest.json",
    "summary.json",
    "compile_metrics.json",
    "validation_report.json",
    "geometry_validation_report.json",
    "interaction_smoke_report.json",
    "usd_validation_report.json",
    "activation_manifest.json",
    "navigation.json",
    "interactions.json",
    "usd/city.usda",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path) -> Any | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def freeze_baseline(
    source: str | Path,
    output_dir: str | Path,
    *,
    name: str,
    spec_path: str | Path | None = None,
    reproduction_command: str | None = None,
    file_names: Iterable[str] = DEFAULT_BASELINE_FILES,
) -> Path:
    """Record hashes and compact evidence without duplicating a large scene.

    The source remains the canonical payload. The baseline folder is a small,
    auditable lock record that detects accidental changes through
    :func:`verify_baseline`.
    """
    root = Path(source).expanduser().resolve()
    destination = Path(output_dir).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"Baseline source directory does not exist: {root}")
    if not (root / "city.json").is_file():
        raise ValueError(f"Baseline source has no city.json: {root}")
    if destination.exists() and any(destination.iterdir()):
        raise ValueError(f"Baseline output must be empty: {destination}")
    destination.mkdir(parents=True, exist_ok=True)

    files: dict[str, dict[str, Any]] = {}
    for name_in_source in file_names:
        path = root / name_in_source
        if not path.is_file():
            continue
        files[name_in_source] = {
            "sha256": _sha256(path),
            "size_bytes": path.stat().st_size,
        }
    if "city.json" not in files:
        raise ValueError("A baseline must include city.json")

    spec_copy = None
    if spec_path is not None:
        spec = Path(spec_path).expanduser().resolve()
        if not spec.is_file():
            raise ValueError(f"Baseline spec does not exist: {spec}")
        spec_copy = "spec.json"
        shutil.copy2(spec, destination / spec_copy)

    manifest = {
        "protocol_version": "cityg.baseline.v1",
        "name": name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_directory": str(root),
        "immutable_by_convention": True,
        "spec_copy": spec_copy,
        "reproduction_command": reproduction_command,
        "files": files,
        "summary": _read_json(root / "summary.json"),
        "compile_metrics": _read_json(root / "compile_metrics.json"),
        "validation": {
            report: _read_json(root / report)
            for report in (
                "validation_report.json",
                "geometry_validation_report.json",
                "interaction_smoke_report.json",
                "usd_validation_report.json",
            )
            if (root / report).is_file()
        },
    }
    manifest_path = destination / "baseline_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (destination / "README.md").write_text(
        "# Frozen CityG baseline\n\n"
        f"Name: `{name}`  \n"
        f"Canonical scene: `{root}`\n\n"
        "This folder intentionally stores hashes and compact evidence rather than "
        "duplicating the full scene. Run `cityg baseline-verify baseline_manifest.json` "
        "before using the scene as an experimental reference.\n",
        encoding="utf-8",
    )
    return manifest_path


def verify_baseline(manifest_path: str | Path) -> dict[str, Any]:
    """Verify all recorded source files and return a machine-readable report."""
    path = Path(manifest_path).expanduser().resolve()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("protocol_version") != "cityg.baseline.v1":
        raise ValueError("Unsupported CityG baseline manifest")
    root = Path(payload["source_directory"])
    issues: list[dict[str, Any]] = []
    for relative, expected in payload.get("files", {}).items():
        source = root / relative
        if not source.is_file():
            issues.append({"file": relative, "code": "missing"})
            continue
        actual_size = source.stat().st_size
        if actual_size != int(expected["size_bytes"]):
            issues.append(
                {
                    "file": relative,
                    "code": "size_mismatch",
                    "expected": expected["size_bytes"],
                    "actual": actual_size,
                }
            )
            continue
        actual_hash = _sha256(source)
        if actual_hash != expected["sha256"]:
            issues.append(
                {
                    "file": relative,
                    "code": "hash_mismatch",
                    "expected": expected["sha256"],
                    "actual": actual_hash,
                }
            )
    return {
        "protocol_version": "cityg.baseline.verification.v1",
        "baseline": payload.get("name"),
        "source_directory": str(root),
        "checked_file_count": len(payload.get("files", {})),
        "ok": not issues,
        "issues": issues,
    }


__all__ = ["DEFAULT_BASELINE_FILES", "freeze_baseline", "verify_baseline"]
