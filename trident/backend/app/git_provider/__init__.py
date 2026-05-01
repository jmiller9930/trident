"""Git provider abstraction package (GITHUB_001).

Public re-exports for callers:
    from app.git_provider import (
        GitProvider, RepoInfo, BranchInfo, CommitInfo,
        GitProviderDisabledError, GitProviderConfigError, GitProviderError,
        git_provider_for_settings, directive_branch_name,
    )
"""

from app.git_provider.base import (
    BranchInfo,
    CommitInfo,
    GitProvider,
    GitProviderConfigError,
    GitProviderDisabledError,
    GitProviderError,
    RepoInfo,
)
from app.git_provider.branch_naming import directive_branch_name
from app.git_provider.registry import git_provider_for_settings

__all__ = [
    "BranchInfo",
    "CommitInfo",
    "GitProvider",
    "GitProviderConfigError",
    "GitProviderDisabledError",
    "GitProviderError",
    "RepoInfo",
    "directive_branch_name",
    "git_provider_for_settings",
]
