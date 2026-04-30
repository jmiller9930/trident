"""Read-only git diff (100E). No writes; suitable for proof placeholder."""

from __future__ import annotations

import subprocess
from pathlib import Path

from app.locks.exceptions import GitValidationError


def working_tree_diff(repo_root: Path, *, max_bytes: int = 120_000) -> str:
    """Unified diff of unstaged changes vs index (read-only)."""
    proc = subprocess.run(
        ["git", "-c", "safe.directory=*", "diff", "--no-ext-diff", "--no-color"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if proc.returncode != 0:
        raise GitValidationError("git_diff_failed")
    out = proc.stdout or ""
    if len(out) > max_bytes:
        return out[:max_bytes] + "\n…[truncated]\n"
    return out
