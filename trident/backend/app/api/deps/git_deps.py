"""FastAPI dependency: resolve GitProvider from settings (fail-closed on 503)."""

from __future__ import annotations

from fastapi import Depends, HTTPException

from app.config.settings import Settings
from app.db.session import get_settings_dep
from app.git_provider.base import GitProvider, GitProviderConfigError, GitProviderDisabledError
from app.git_provider.registry import git_provider_for_settings


def get_git_provider(cfg: Settings = Depends(get_settings_dep)) -> GitProvider:
    """FastAPI dependency that builds the active GitProvider.

    Returns a ready provider on success.
    Raises HTTP 503 when GitHub is disabled or token is missing — never leaks config.
    Override this dependency in tests to inject a mock provider.
    """
    try:
        return git_provider_for_settings(cfg)
    except GitProviderDisabledError:
        raise HTTPException(status_code=503, detail="git_provider_disabled") from None
    except GitProviderConfigError as e:
        raise HTTPException(status_code=503, detail=e.reason_code) from None


def get_optional_git_provider(cfg: Settings = Depends(get_settings_dep)) -> GitProvider | None:
    """Non-blocking variant: returns None when GitHub is disabled or unconfigured.

    Used by endpoints where Git integration is supplemental (directive issue, onboarding).
    Override this dependency in tests to inject a mock provider without triggering 503.
    """
    if not cfg.github_enabled:
        return None
    try:
        return git_provider_for_settings(cfg)
    except (GitProviderDisabledError, GitProviderConfigError):
        return None
