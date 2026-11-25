"""Resolve built standalone Linux Agent release bundles safely."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

BUNDLE_FILENAME_RE = re.compile(r"sentinelx-agent-([A-Za-z0-9._-]+)\.tar\.gz")


@dataclass(frozen=True)
class AgentBundleArtifact:
    """Resolved Agent bundle tarball ready to serve to Linux hosts."""

    release: str
    filename: str
    path: Path
    sha256: str
    size_bytes: int


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _validate_archive_file(root: Path, filename: str) -> tuple[Path, str] | None:
    match = BUNDLE_FILENAME_RE.fullmatch(filename)
    if match is None:
        return None
    raw_path = root / filename
    if raw_path.is_symlink() or not raw_path.is_file():
        return None
    resolved = raw_path.resolve()
    if resolved.parent != root:
        return None
    return resolved, match.group(1)


def resolve_latest_agent_bundle(bundle_dir: Path) -> AgentBundleArtifact | None:
    """Return the active standalone Agent bundle metadata, or None when absent."""
    if not bundle_dir.exists() or not bundle_dir.is_dir():
        return None
    root = bundle_dir.resolve()

    latest_file = root / "latest.json"
    if latest_file.is_file() and not latest_file.is_symlink():
        try:
            payload = json.loads(latest_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            payload = None
        if isinstance(payload, dict) and isinstance(payload.get("filename"), str):
            validated = _validate_archive_file(root, payload["filename"])
            if validated is not None:
                archive_path, derived_release = validated
                actual_sha256 = _sha256_file(archive_path)
                expected_sha256 = payload.get("sha256")
                if isinstance(expected_sha256, str) and expected_sha256.lower() != actual_sha256:
                    return None
                release = (
                    payload["release"]
                    if isinstance(payload.get("release"), str) and payload["release"]
                    else derived_release
                )
                return AgentBundleArtifact(
                    release=release,
                    filename=archive_path.name,
                    path=archive_path,
                    sha256=actual_sha256,
                    size_bytes=archive_path.stat().st_size,
                )

    candidates: list[tuple[float, str, Path, str]] = []
    for entry in root.iterdir():
        if entry.is_symlink() or not entry.is_file():
            continue
        validated = _validate_archive_file(root, entry.name)
        if validated is None:
            continue
        archive_path, derived_release = validated
        candidates.append(
            (archive_path.stat().st_mtime, archive_path.name, archive_path, derived_release)
        )

    if not candidates:
        return None

    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    _, filename, archive_path, release = candidates[0]
    return AgentBundleArtifact(
        release=release,
        filename=filename,
        path=archive_path,
        sha256=_sha256_file(archive_path),
        size_bytes=archive_path.stat().st_size,
    )
