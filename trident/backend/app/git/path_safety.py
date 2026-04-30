"""Resolve relative paths strictly under an allowed root (100E)."""

from __future__ import annotations

import os
from pathlib import Path

from app.locks.exceptions import PathSafetyError


def resolve_under_project_root(*, root: str | os.PathLike[str], relative_file_path: str) -> Path:
    """
    Normalize `relative_file_path` (repo-relative POSIX-style) to an absolute path that must stay
    under `root`. Rejects absolute paths, '..', and symlink escapes after resolution.
    """
    raw = (relative_file_path or "").strip()
    if not raw:
        raise PathSafetyError("empty_path")
    if raw.startswith("/") or (len(raw) > 1 and raw[1] == ":"):
        raise PathSafetyError("absolute_path_forbidden")

    root_path = Path(root).expanduser().resolve()
    if not root_path.is_dir():
        raise PathSafetyError("root_not_a_directory")

    parts = Path(raw).as_posix().split("/")
    if ".." in parts or parts[0] == "..":
        raise PathSafetyError("path_traversal_forbidden")

    candidate = (root_path / Path(raw)).resolve()

    try:
        candidate.relative_to(root_path)
    except ValueError as e:
        raise PathSafetyError("path_escapes_root") from e

    return candidate
