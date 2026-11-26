#!/usr/bin/env python3
"""Acquire pinned, bounded source bundles for review; never change the live registry.

Only allowlisted public GitHub repositories are supported. Preserve author/license
files and raw formats; an FBX download is NOT an approved runtime GLB.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import quote, urlparse

from scripts.prepare_exterior_assets import safe_relative, write_json

REPOSITORIES = {"microsoft/Microsoft-Rocketbox", "nesdesignco/FormDrive", "KhronosGroup/glTF-Sample-Assets", "osrf/gazebo_models"}


def fetch(url: str, path: Path, limit: int) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in {"api.github.com", "raw.githubusercontent.com"}:
        raise ValueError("Unsupported public source URL")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    subprocess.run(["curl", "--fail", "--silent", "--show-error", "--location", "--proto", "=https",
                    "--proto-redir", "=https", "--retry", "2", "--connect-timeout", "20",
                    "--max-time", "240", "--max-filesize", str(limit),
                    "--output", str(temporary), url], check=True)
    if temporary.stat().st_size > limit:
        raise ValueError("File exceeds configured budget")
    temporary.replace(path)


def blob_hash(path: Path) -> str:
    digest = hashlib.sha1(f"blob {path.stat().st_size}\0".encode())
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def select_files(tree: dict, group: dict) -> list[dict]:
    if tree.get("truncated"):
        raise ValueError("Refusing incomplete upstream tree")
    selected = []
    for item in tree["tree"]:
        name = item["path"]
        if item["type"] != "blob":
            continue
        if any(fnmatch.fnmatchcase(name, pattern) for pattern in group.get("exclude_patterns", [])):
            continue
        if name in group.get("files", []) or any(fnmatch.fnmatchcase(name, pattern) for pattern in group.get("patterns", [])):
            safe_relative(name)
            mode = item.get("mode")
            # Some upstream image/model files accidentally carry an executable
            # bit. Download as inert bytes (never chmod/execute); still reject
            # links and executable scripts selected by a broad folder pattern.
            inert_suffixes = {".png", ".jpg", ".jpeg", ".tga", ".dds", ".mtl", ".obj",
                              ".dae", ".sdf", ".config", ".material", ".stl", ".fbx", ".glb"}
            regular = mode == "100644" or (mode == "100755" and Path(name).suffix.lower() in inert_suffixes)
            if not regular or not re.fullmatch(r"[a-f0-9]{40}", item["sha"]):
                raise ValueError(f"Only regular data files accepted: {name}")
            selected.append(item)
    names = {item["path"] for item in selected}
    missing = set(group.get("files", [])) - names
    if missing or not selected:
        raise ValueError(f"Missing requested files in {group['id']}: {sorted(missing)}")
    for pattern in group.get("patterns", []):
        if not any(fnmatch.fnmatchcase(name, pattern) for name in names):
            raise ValueError(f"Pattern selected no files: {pattern}")
    if not any(Path(name).suffix.lower() in {".fbx", ".glb", ".gltf", ".obj", ".dae"} for name in names):
        raise ValueError(f"No model payload in {group['id']}")
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["plan", "download"])
    parser.add_argument("--config", type=Path, default=Path("configs/exterior_review_sources_v3.json"))
    parser.add_argument("--output", type=Path, default=Path("assets/incoming/exterior_v3_sources"))
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    output = args.output.resolve()
    project_assets = Path(__file__).resolve().parents[1] / "assets"
    if not output.is_relative_to(project_assets.resolve()):
        raise ValueError("Source acquisition output must be under project assets/")
    output.mkdir(parents=True, exist_ok=True)
    records, jobs = [], {}
    for provider in config["providers"]:
        repo, revision = provider["repo"], provider["revision"]
        if repo not in REPOSITORIES or not re.fullmatch(r"[a-f0-9]{40}", revision):
            raise ValueError("Allowlisted repository and immutable commit are required")
        cache = output / "metadata" / f"{repo.replace('/', '_')}_{revision}.json"
        if not cache.exists():
            fetch(f"https://api.github.com/repos/{repo}/git/trees/{revision}?recursive=1", cache, 16 * 2**20)
        tree = json.loads(cache.read_text())
        for group in provider["groups"]:
            group = {**group, "exclude_patterns": [*provider.get("exclude_patterns", []), *group.get("exclude_patterns", [])]}
            items = select_files(tree, group)
            paths = []
            for item in items:
                relative = Path(repo.replace('/', '_')) / revision[:12] / safe_relative(item["path"])
                destination = output / relative
                if not destination.resolve().is_relative_to(output):
                    raise ValueError("Escaping output symlink")
                if item["size"] > config["max_file_mib"] * 2**20:
                    raise ValueError(f"Oversize source file: {item['path']}")
                jobs[str(relative)] = {**item, "relative": str(relative),
                    "url": f"https://raw.githubusercontent.com/{repo}/{revision}/{quote(item['path'], safe='/')}"}
                paths.append(str(relative))
            records.append({**group, "repo": repo, "revision": revision,
                            "status": "planned", "runtime_ready": False, "local_files": paths})
    total = sum(item["size"] for item in jobs.values())
    if total > config["max_total_mib"] * 2**20 or shutil.disk_usage(output).free < total * 2 + 2**30:
        raise ValueError("Download or disk budget exceeded")
    report = {"schema_version": "cityg.review_sources.v1", "planned_bytes": total,
              "source_file_count": len(jobs), "groups": records, "failures": [],
              "files": list(jobs.values()), "production_registry_changed": False}
    write_json(output / "acquisition_manifest.json", report)
    print(f"Plan: {len(records)} groups, {len(jobs)} files, {total / 2**20:.1f} MiB", flush=True)
    if args.action == "plan":
        return

    def acquire(item):
        destination = output / item["relative"]
        if not (destination.is_file() and blob_hash(destination) == item["sha"]):
            fetch(item["url"], destination, item["size"])
        if destination.stat().st_size != item["size"] or blob_hash(destination) != item["sha"]:
            raise ValueError(f"Git blob hash/size mismatch: {item['path']}")
        with destination.open("rb") as stream:
            if stream.read(80).startswith(b"version https://git-lfs.github.com/spec/v1"):
                raise ValueError(f"LFS pointer is not a model: {item['path']}")
        return item["relative"]

    successful = set()
    with ThreadPoolExecutor(max_workers=3) as pool:
        pending = {pool.submit(acquire, item): item for item in jobs.values()}
        for future in as_completed(pending):
            try:
                successful.add(future.result())
            except Exception as error:
                report["failures"].append({"path": pending[future]["relative"], "error": str(error)})
            if (len(successful) + len(report["failures"])) % 10 == 0:
                print(f"Verified {len(successful)}/{len(jobs)}; failures {len(report['failures'])}", flush=True)
    for group in records:
        group["status"] = "downloaded_pending_conversion_review" if set(group["local_files"]) <= successful else "incomplete"
    report["verified_bytes"] = sum(item["size"] for key, item in jobs.items() if key in successful)
    write_json(output / "acquisition_manifest.json", report)
    print(f"Completed: {len(successful)} files; {len(report['failures'])} failures", flush=True)
    if report["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
