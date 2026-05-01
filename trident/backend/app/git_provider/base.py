"""GitProvider abstract interface and shared dataclasses (GITHUB_001).

All concrete providers (GitHubProvider, future GitLabProvider) implement GitProvider.
No provider-specific details leak through this module.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


# ── Exceptions ─────────────────────────────────────────────────────────────────

class GitProviderError(Exception):
    """Base for all git provider errors."""

    def __init__(self, message: str, *, reason_code: str, detail: dict | None = None) -> None:
        super().__init__(message)
        self.reason_code = reason_code
        self.detail: dict = detail or {}

    def as_dict(self) -> dict:
        return {"error": "git_provider_error", "reason_code": self.reason_code, **self.detail}


class GitProviderDisabledError(GitProviderError):
    """Raised when TRIDENT_GITHUB_ENABLED=false or provider not configured."""

    def __init__(self, reason: str = "git_provider_disabled") -> None:
        super().__init__(reason, reason_code=reason)


class GitProviderConfigError(GitProviderError):
    """Raised when provider credentials / config are missing or invalid."""

    def __init__(self, reason: str = "git_provider_config_invalid") -> None:
        super().__init__(reason, reason_code=reason)


# ── Shared return types ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class RepoInfo:
    """Sanitized repository metadata — never contains credentials."""
    provider: str           # "github" | "gitlab" (future)
    owner: str              # GitHub user or org
    repo_name: str
    clone_url: str          # HTTPS clone URL
    html_url: str           # Browser URL
    default_branch: str
    private: bool
    created: bool           # True = just created; False = pre-existing (link flow)


@dataclass(frozen=True)
class BranchInfo:
    """Branch creation result."""
    provider: str
    branch_name: str
    commit_sha: str         # HEAD SHA of source commit (from_sha)
    html_url: str | None = None


@dataclass(frozen=True)
class CommitInfo:
    """Push / file-update result."""
    provider: str
    sha: str
    message: str
    branch_name: str
    html_url: str | None = None


# ── Abstract interface ────────────────────────────────────────────────────────

class GitProvider(ABC):
    """Provider-agnostic interface for git hosting operations.

    Implementations must:
    - Never expose credentials through return values or exceptions.
    - Raise GitProviderError (or subclass) for all failure cases.
    - Be stateless (settings-driven); callers may construct fresh per-request.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Short slug: 'github', 'gitlab', etc."""

    @abstractmethod
    def ping(self) -> bool:
        """Validate connectivity and credentials. Returns True on success.

        Never leaks token details. Raises GitProviderConfigError on auth failure.
        """

    @abstractmethod
    def create_repo(
        self,
        *,
        name: str,
        description: str = "",
        private: bool = True,
        org: str | None = None,
    ) -> RepoInfo:
        """Create a new repository.

        Raises GitProviderError on conflict (use reason_code='repo_name_conflict') or permission
        failure (reason_code='permission_denied').
        """

    @abstractmethod
    def get_repo_info(self, *, owner: str, repo_name: str) -> RepoInfo:
        """Fetch metadata for an existing repository.

        Raises GitProviderError if not found or not accessible.
        """

    @abstractmethod
    def link_repo(self, *, clone_url: str) -> RepoInfo:
        """Validate and return metadata for an existing repo by its HTTPS clone URL.

        Validates URL format and provider reachability. Does NOT write anything.
        Raises GitProviderError(reason_code='repo_not_accessible') if inaccessible.
        """

    @abstractmethod
    def get_default_branch_sha(self, *, owner: str, repo_name: str) -> str:
        """Return the HEAD commit SHA of the default branch."""

    @abstractmethod
    def create_branch(
        self,
        *,
        owner: str,
        repo_name: str,
        branch_name: str,
        from_sha: str,
    ) -> BranchInfo:
        """Create a branch at from_sha.

        Branch name MUST follow: trident/{directive_id}/{slug}
        Caller is responsible for enforcing this via branch_naming.directive_branch_name().
        """

    @abstractmethod
    def push_files(
        self,
        *,
        owner: str,
        repo_name: str,
        branch_name: str,
        files: dict[str, str],
        message: str,
        committer_name: str = "Trident",
        committer_email: str = "trident@localhost",
    ) -> CommitInfo:
        """Create or update multiple files in a single commit via the provider API.

        files: {relative_path: utf-8_content}
        Returns CommitInfo with SHA of the new commit.
        """
