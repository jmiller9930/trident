"""Read-only Git repository validation (100E)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from app.git.path_safety import resolve_under_project_root
from app.locks.exceptions import GitValidationError, PathSafetyError


def assert_relative_path_under_root(*, repo_root: Path, relative_file_path: str) -> Path:
    """Validate repo-relative file path and return resolved absolute path under repo root."""
    try:
        return resolve_under_project_root(root=str(repo_root), relative_file_path=relative_file_path)
    except PathSafetyError as e:
        raise GitValidationError(str(e.args[0]) if e.args else "path_error") from e


def assert_git_repository(repo_root: Path) -> None:
    """Verify repo_root is inside a git working tree (read-only check)."""
    if not repo_root.is_dir():
        raise GitValidationError("repo_root_not_directory")
    proc = subprocess.run(
        ["git", "-c", "safe.directory=*", "rev-parse", "--is-inside-work-tree"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if proc.returncode != 0 or proc.stdout.strip() != "true":
        raise GitValidationError("not_a_git_repository")


def current_branch(repo_root: Path) -> str:
    proc = subprocess.run(
        ["git", "-c", "safe.directory=*", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if proc.returncode != 0:
        raise GitValidationError("branch_resolve_failed")
    name = proc.stdout.strip()
    if not name or name == "HEAD":
        raise GitValidationError("detached_head_not_supported")
    return name
