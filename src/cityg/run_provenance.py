"""Small, secret-free source fingerprints captured before stage execution."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import subprocess


def source_snapshot(root=None):
    root = Path(root) if root is not None else Path(__file__).resolve().parents[2]
    files = set()
    patterns = {'src': ('*.py',), 'scripts': ('*.py', '*.sh'),
                'configs': ('*.json', '*.env'),
                'viewer/src': ('*.js', '*.css', '*.html')}
    for folder, globs in patterns.items():
        for pattern in globs:
            files.update((root/folder).rglob(pattern))
    for name in ('pyproject.toml', 'viewer/package.json', 'viewer/package-lock.json',
                 'assets/asset_registry.json', 'assets/facades/asset_annotations_reviewed.json'):
        if (root/name).is_file(): files.add(root/name)
    # Hash configuration values, never persist environment variables or secrets.
    fingerprints = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sorted(files) if p.is_file() and not p.is_symlink()}
    def git(*args):
        try:
            return subprocess.run(['git', '-C', str(root), *args], check=True,
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                timeout=5).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return None
    status = git('status', '--porcelain', '--untracked-files=normal')
    return {'schema_version': 1, 'captured_at': datetime.now(timezone.utc).isoformat(),
        'python_version': platform.python_version(), 'git_revision': git('rev-parse', 'HEAD'),
        'git_dirty': bool(status) if status is not None else None,
        'tree_sha256': hashlib.sha256(json.dumps(fingerprints, sort_keys=True).encode()).hexdigest(),
        'file_sha256': fingerprints, 'asset_binary_hashes_included': False,
        'note': 'Stage-start on-disk fingerprints, not a source archive or a model weights snapshot.'}


def record_stage_start(output):
    from cityg.serialization import save_json
    return save_json(source_snapshot(), Path(output)/'source_provenance.json')
