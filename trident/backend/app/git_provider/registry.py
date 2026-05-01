"""Provider registry — builds a GitProvider from Settings (fail-closed).

This is the only external entry point for constructing a provider.
Callers never construct GitHubClient or read tokens directly.

Fail-closed rules:
1. If settings.github_enabled is False → GitProviderDisabledError immediately.
2. If token is absent → GitProviderConfigError (via GitHubClient constructor).
3. Any network/auth error during ping → GitProviderError.
"""

from __future__ import annotations

from app.config.settings import Settings
from app.git_provider.base import GitProvider, GitProviderDisabledError


def git_provider_for_settings(settings: Settings) -> GitProvider:
    """Return the configured GitProvider or raise GitProviderDisabledError.

    Returns a ready GitHubProvider (token loaded, httpx client ready).
    Never returns None — callers either get a usable provider or an exception.
    """
    if not settings.github_enabled:
        raise GitProviderDisabledError("git_provider_disabled")

    from app.git_provider.github.github_client import GitHubClient
    from app.git_provider.github.github_provider import GitHubProvider

    client = GitHubClient(settings)  # raises GitProviderConfigError if token missing
    return GitHubProvider(client)
