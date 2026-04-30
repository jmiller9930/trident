"""Read-only git status (100E)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from app.locks.exceptions import GitValidationError


def porcelain_status(repo_root: Path) -> str:
    proc = subprocess.run(
        ["git", "-c", "safe.directory=*", "status", "--porcelain"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if proc.returncode != 0:
        raise GitValidationError("git_status_failed")
    return proc.stdout
