"""GitHub REST API client — THE ONLY MODULE that holds the access token.

Architecture invariant (mandatory, per GIT_PROVIDER_GITHUB_001_PLAN accepted):
  - No other module in this codebase may read TRIDENT_GITHUB_TOKEN from env.
  - No other module may construct an Authorization header for GitHub.
  - Token is read once in _load_token() and kept in memory only.
  - Token is NEVER logged, NEVER included in error messages, NEVER returned.

Wraps GitHub REST API v3 using httpx (already a project dependency).
"""

from __future__ import annotations

import base64
import re
import time
from pathlib import Path
from typing import Any

import httpx

from app.config.settings import Settings
from app.git_provider.base import GitProviderConfigError, GitProviderError
from app.git_provider.github.github_schemas import (
    _GitHubBranchHeadRaw,
    _GitHubBranchRaw,
    _GitHubCommitRaw,
    _GitHubRepoRaw,
)

_GITHUB_API_VERSION = "2022-11-28"
_REPO_NAME_RE = re.compile(r"^[a-zA-Z0-9._-]{1,100}$")
_CLONE_URL_RE = re.compile(r"^https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?$")

# Retry on these status codes
_RETRYABLE = {429, 500, 502, 503, 504}
_MAX_RETRIES = 2
_RETRY_BASE_SEC = 0.5


def _load_token(settings: Settings) -> str:
    """Read token from file (preferred) or env.  Returns empty string if absent."""
    file_path = settings.github_token_file.strip()
    if file_path:
        try:
            return Path(file_path).read_text(encoding="utf-8").strip()
        except OSError:
            pass
    return settings.github_token.strip()


class GitHubClient:
    """Thin, stateless httpx wrapper for GitHub REST API v3.

    Token isolation: this class is the single point of token access.
    All other modules receive an instance of this class; they never see the token.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        http_client: httpx.Client | None = None,
    ) -> None:
        token = _load_token(settings)
        if not token:
            raise GitProviderConfigError("github_token_missing")

        self._base_url = settings.github_api_base_url.rstrip("/")
        self._timeout = float(settings.github_api_timeout)

        # Build headers here — token never leaves this constructor scope as a plain variable
        self._headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": _GITHUB_API_VERSION,
        }
        token = None  # explicit clear; the string object may still exist in memory

        self._client_owned = http_client is None
        self._http = http_client or httpx.Client(timeout=self._timeout)

    def close(self) -> None:
        if self._client_owned:
            self._http.close()

    # ── Internal helpers ────────────────────────────────────────────────────

    def _url(self, path: str) -> str:
        p = path if path.startswith("/") else f"/{path}"
        return f"{self._base_url}{p}"

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        url = self._url(path)
        for attempt in range(1 + _MAX_RETRIES):
            try:
                resp = self._http.request(method, url, headers=self._headers, **kwargs)
            except httpx.TimeoutException as e:
                raise GitProviderError(
                    "GitHub request timed out",
                    reason_code="github_timeout",
                    detail={"path": path},
                ) from e
            except httpx.RequestError as e:
                raise GitProviderError(
                    "GitHub request failed",
                    reason_code="github_request_error",
                    detail={"path": path, "error": type(e).__name__},
                ) from e

            if resp.status_code not in _RETRYABLE or attempt == _MAX_RETRIES:
                return resp

            retry_after = resp.headers.get("Retry-After")
            wait = float(retry_after) if retry_after else _RETRY_BASE_SEC * (2**attempt)
            time.sleep(wait)

        return resp  # never reached; loop exits above

    def _raise_for_status(self, resp: httpx.Response, *, context: str) -> None:
        """Raise GitProviderError with safe detail (no token in message)."""
        if resp.status_code < 400:
            return
        if resp.status_code == 401:
            raise GitProviderError(
                "GitHub authentication failed",
                reason_code="github_auth_failed",
                detail={"context": context, "status_code": 401},
            )
        if resp.status_code == 403:
            raise GitProviderError(
                "GitHub permission denied",
                reason_code="github_permission_denied",
                detail={"context": context, "status_code": 403},
            )
        if resp.status_code == 404:
            raise GitProviderError(
                "GitHub resource not found",
                reason_code="github_not_found",
                detail={"context": context, "status_code": 404},
            )
        if resp.status_code == 422:
            body = self._safe_json(resp)
            errors = body.get("errors") if isinstance(body, dict) else None
            raise GitProviderError(
                "GitHub unprocessable entity",
                reason_code="github_unprocessable",
                detail={"context": context, "errors": errors},
            )
        raise GitProviderError(
            f"GitHub error {resp.status_code}",
            reason_code="github_api_error",
            detail={"context": context, "status_code": resp.status_code},
        )

    @staticmethod
    def _safe_json(resp: httpx.Response) -> Any:
        try:
            return resp.json()
        except Exception:
            return {}

    # ── Repo operations ─────────────────────────────────────────────────────

    def ping(self) -> bool:
        """Validate token by calling /user. Returns True on 200, raises on auth failure."""
        resp = self._request("GET", "/user")
        if resp.status_code == 401:
            raise GitProviderError(
                "GitHub authentication failed during ping",
                reason_code="github_auth_failed",
                detail={"status_code": 401},
            )
        if resp.status_code == 403:
            raise GitProviderError(
                "GitHub permission denied during ping",
                reason_code="github_permission_denied",
                detail={"status_code": 403},
            )
        return resp.status_code == 200

    def create_repo(
        self,
        *,
        name: str,
        description: str = "",
        private: bool = True,
        org: str | None = None,
    ) -> _GitHubRepoRaw:
        if not _REPO_NAME_RE.match(name):
            raise GitProviderError(
                "Invalid repo name",
                reason_code="invalid_repo_name",
                detail={"name": name},
            )
        payload: dict[str, Any] = {
            "name": name,
            "description": description,
            "private": private,
            "auto_init": False,
        }
        path = f"/orgs/{org}/repos" if org else "/user/repos"
        resp = self._request("POST", path, json=payload)

        if resp.status_code == 422:
            body = self._safe_json(resp)
            errors = body.get("errors", []) if isinstance(body, dict) else []
            if any(e.get("field") == "name" and "already exists" in str(e.get("message", "")) for e in errors):
                raise GitProviderError(
                    "Repo name already exists",
                    reason_code="repo_name_conflict",
                    detail={"name": name},
                )
        self._raise_for_status(resp, context="create_repo")
        data = self._safe_json(resp)
        return self._parse_repo(data)

    def get_repo(self, *, owner: str, repo_name: str) -> _GitHubRepoRaw:
        resp = self._request("GET", f"/repos/{owner}/{repo_name}")
        self._raise_for_status(resp, context="get_repo")
        return self._parse_repo(self._safe_json(resp))

    def get_repo_from_clone_url(self, *, clone_url: str) -> _GitHubRepoRaw:
        m = _CLONE_URL_RE.match(clone_url.strip())
        if not m:
            raise GitProviderError(
                "clone_url must be https://github.com/owner/repo",
                reason_code="invalid_clone_url",
                detail={"clone_url": clone_url},
            )
        owner = m.group("owner")
        repo = m.group("repo")
        return self.get_repo(owner=owner, repo_name=repo)

    def get_branch_head_sha(self, *, owner: str, repo_name: str, branch: str) -> _GitHubBranchHeadRaw:
        resp = self._request("GET", f"/repos/{owner}/{repo_name}/branches/{branch}")
        self._raise_for_status(resp, context="get_branch_head")
        data = self._safe_json(resp)
        sha = data.get("commit", {}).get("sha", "")
        if not sha:
            raise GitProviderError(
                "Could not read branch HEAD SHA",
                reason_code="branch_sha_missing",
                detail={"owner": owner, "repo": repo_name, "branch": branch},
            )
        return _GitHubBranchHeadRaw(sha=sha)

    def create_ref(
        self,
        *,
        owner: str,
        repo_name: str,
        branch_name: str,
        from_sha: str,
    ) -> _GitHubBranchRaw:
        payload = {"ref": f"refs/heads/{branch_name}", "sha": from_sha}
        resp = self._request("POST", f"/repos/{owner}/{repo_name}/git/refs", json=payload)
        if resp.status_code == 422:
            raise GitProviderError(
                "Branch already exists",
                reason_code="branch_already_exists",
                detail={"branch": branch_name},
            )
        self._raise_for_status(resp, context="create_ref")
        data = self._safe_json(resp)
        return _GitHubBranchRaw(
            ref=data.get("ref", f"refs/heads/{branch_name}"),
            sha=data.get("object", {}).get("sha", from_sha),
        )

    def put_file(
        self,
        *,
        owner: str,
        repo_name: str,
        path: str,
        content_utf8: str,
        message: str,
        branch: str,
        committer_name: str = "Trident",
        committer_email: str = "trident@localhost",
        sha: str | None = None,
    ) -> _GitHubCommitRaw:
        """Create or update a single file via Contents API."""
        encoded = base64.b64encode(content_utf8.encode("utf-8")).decode("ascii")
        payload: dict[str, Any] = {
            "message": message,
            "content": encoded,
            "branch": branch,
            "committer": {"name": committer_name, "email": committer_email},
        }
        if sha:
            payload["sha"] = sha  # required for updates

        resp = self._request("PUT", f"/repos/{owner}/{repo_name}/contents/{path.lstrip('/')}", json=payload)
        self._raise_for_status(resp, context="put_file")
        data = self._safe_json(resp)
        commit_data = data.get("commit", {})
        return _GitHubCommitRaw(
            sha=commit_data.get("sha", ""),
            html_url=commit_data.get("html_url", ""),
        )

    # ── Internal parsers ────────────────────────────────────────────────────

    @staticmethod
    def _parse_repo(data: dict) -> _GitHubRepoRaw:
        return _GitHubRepoRaw(
            owner=data.get("owner", {}).get("login", ""),
            name=data.get("name", ""),
            clone_url=data.get("clone_url", ""),
            html_url=data.get("html_url", ""),
            default_branch=data.get("default_branch", "main"),
            private=bool(data.get("private", False)),
        )
