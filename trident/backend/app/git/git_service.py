"""Git read-only facade for 100E (status + diff + validation)."""

from __future__ import annotations

from pathlib import Path

from app.git import git_diff, git_status, git_validation


def validate_repo_and_paths(*, repo_root: Path, relative_file_path: str) -> tuple[Path, str, str]:
    """
    Returns (resolved_file_path, branch_name, git_status_porcelain).
    Raises GitValidationError on failure.
    """
    root = repo_root.resolve()
    git_validation.assert_git_repository(root)
    resolved = git_validation.assert_relative_path_under_root(repo_root=root, relative_file_path=relative_file_path)
    branch = git_validation.current_branch(root)
    status = git_status.porcelain_status(root)
    return resolved, branch, status


def capture_diff(repo_root: Path) -> str:
    return git_diff.working_tree_diff(repo_root.resolve())
