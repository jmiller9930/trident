"""Internal dataclasses for GitHub API responses (GITHUB_001).

Not exported outside git_provider.github — callers use base.py types only.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class _GitHubRepoRaw:
    """Parsed from GitHub GET /repos/:owner/:repo response."""
    owner: str
    name: str
    clone_url: str
    html_url: str
    default_branch: str
    private: bool


@dataclass(frozen=True)
class _GitHubBranchRaw:
    """Parsed from GitHub POST /repos/:owner/:repo/git/refs response."""
    ref: str           # refs/heads/{branch}
    sha: str           # object.sha


@dataclass(frozen=True)
class _GitHubCommitRaw:
    """Parsed from GitHub PUT /repos/:owner/:repo/contents/:path response."""
    sha: str           # commit.sha
    html_url: str      # commit.html_url


@dataclass(frozen=True)
class _GitHubBranchHeadRaw:
    """Parsed from GET /repos/:owner/:repo/branches/:branch."""
    sha: str           # commit.sha
