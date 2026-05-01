"""TRIDENT_IMPLEMENTATION_DIRECTIVE_GITHUB_001 — provider layer tests (mocked httpx)."""

from __future__ import annotations

import json
import uuid

import httpx
import pytest

from app.config.settings import Settings
from app.git_provider.base import (
    BranchInfo,
    CommitInfo,
    GitProviderConfigError,
    GitProviderDisabledError,
    GitProviderError,
    RepoInfo,
)
from app.git_provider.branch_naming import directive_branch_name, validate_trident_branch_name
from app.git_provider.github.github_client import GitHubClient, _CLONE_URL_RE
from app.git_provider.github.github_provider import GitHubProvider
from app.git_provider.registry import git_provider_for_settings


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _repo_json(owner: str = "acme", name: str = "myrepo", private: bool = False) -> dict:
    return {
        "owner": {"login": owner},
        "name": name,
        "clone_url": f"https://github.com/{owner}/{name}.git",
        "html_url": f"https://github.com/{owner}/{name}",
        "default_branch": "main",
        "private": private,
        "full_name": f"{owner}/{name}",
    }


def _branch_json(branch: str, sha: str) -> dict:
    return {"name": branch, "commit": {"sha": sha, "url": ""}}


def _ref_json(branch: str, sha: str) -> dict:
    return {
        "ref": f"refs/heads/{branch}",
        "object": {"sha": sha, "type": "commit"},
    }


def _commit_json(sha: str) -> dict:
    return {
        "commit": {"sha": sha, "html_url": f"https://github.com/acme/myrepo/commit/{sha}"},
        "content": {},
    }


def _make_client(handlers: dict[str, dict[str, httpx.Response]]) -> GitHubClient:
    """Build a GitHubClient with a mock transport routing (method, path) → Response."""

    def handler(request: httpx.Request) -> httpx.Response:
        method = request.method.upper()
        url = str(request.url)
        for path_key, method_map in handlers.items():
            if path_key in url:
                resp = method_map.get(method) or method_map.get("ANY")
                if resp:
                    return resp
        return httpx.Response(404, json={"message": "not found"})

    cfg = Settings(github_enabled=True, github_token="test_token_123")
    return GitHubClient(cfg, http_client=httpx.Client(transport=httpx.MockTransport(handler)))


# ── Branch naming ─────────────────────────────────────────────────────────────

def test_directive_branch_name_format() -> None:
    did = uuid.UUID("d3f1a2b4-0000-0000-0000-000000000000")
    name = directive_branch_name(did, "Add model router")
    assert name == "trident/d3f1a2b4/add-model-router"


def test_directive_branch_name_slugify_special_chars() -> None:
    did = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000000")
    name = directive_branch_name(did, "Fix: CI/CD pipeline!!! (urgent)")
    assert name.startswith("trident/aaaaaaaa/")
    assert " " not in name
    assert "!" not in name


def test_directive_branch_name_empty_title() -> None:
    did = uuid.UUID("bbbbbbbb-0000-0000-0000-000000000000")
    name = directive_branch_name(did)
    assert name == "trident/bbbbbbbb/work"


def test_directive_branch_slug_max_length() -> None:
    did = uuid.UUID("cccccccc-0000-0000-0000-000000000000")
    long_title = "a" * 200
    name = directive_branch_name(did, long_title)
    slug = name.split("/")[2]
    assert len(slug) <= 40


def test_validate_trident_branch_name_pass() -> None:
    assert validate_trident_branch_name("trident/d3f1a2b4/add-router") is True


def test_validate_trident_branch_name_fail_no_prefix() -> None:
    assert validate_trident_branch_name("feature/add-router") is False


def test_validate_trident_branch_name_fail_bad_id() -> None:
    assert validate_trident_branch_name("trident/ZZZZZZZZ/add-router") is False


# ── Settings / token isolation ────────────────────────────────────────────────

def test_registry_disabled_raises_when_github_not_enabled() -> None:
    cfg = Settings(github_enabled=False)
    with pytest.raises(GitProviderDisabledError) as ei:
        git_provider_for_settings(cfg)
    assert ei.value.reason_code == "git_provider_disabled"


def test_registry_raises_config_error_when_token_missing() -> None:
    cfg = Settings(github_enabled=True, github_token="", github_token_file="")
    with pytest.raises(GitProviderConfigError) as ei:
        git_provider_for_settings(cfg)
    assert ei.value.reason_code == "github_token_missing"


def test_token_never_in_provider_error_message() -> None:
    """Token must not appear in GitProviderError messages or detail dicts."""
    cfg = Settings(github_enabled=True, github_token="SUPERSECRET_PAT")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "Unauthorized"})

    client = GitHubClient(cfg, http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(GitProviderError) as ei:
        client.ping()

    err_str = str(ei.value) + json.dumps(ei.value.as_dict())
    assert "SUPERSECRET_PAT" not in err_str


def test_token_not_in_provider_public_return_values() -> None:
    """GitHubProvider public return values must never contain the token."""
    token = "ANOTHER_SECRET_TOKEN_DO_NOT_RETURN"
    cfg = Settings(github_enabled=True, github_token=token)

    def handler(r: httpx.Request) -> httpx.Response:
        if "/repos/acme/myrepo" in str(r.url) and r.method == "GET":
            return httpx.Response(200, json=_repo_json())
        return httpx.Response(404)

    client = GitHubClient(cfg, http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    provider = GitHubProvider(client)
    info = provider.get_repo_info(owner="acme", repo_name="myrepo")
    serialized = json.dumps(vars(info))
    assert token not in serialized, "token must not appear in RepoInfo"


# ── GitHubClient unit tests ────────────────────────────────────────────────────

def test_client_ping_true_on_200() -> None:
    client = _make_client({"/user": {"GET": httpx.Response(200, json={"login": "trident"})}})
    assert client.ping() is True


def test_client_ping_false_on_401() -> None:
    client = _make_client({"/user": {"GET": httpx.Response(401, json={"message": "Unauthorized"})}})
    with pytest.raises(GitProviderError) as ei:
        client.ping()
    assert ei.value.reason_code == "github_auth_failed"


def test_client_create_repo_success() -> None:
    client = _make_client({"/user/repos": {"POST": httpx.Response(201, json=_repo_json())}})
    raw = client.create_repo(name="myrepo")
    assert raw.name == "myrepo"
    assert raw.clone_url == "https://github.com/acme/myrepo.git"


def test_client_create_repo_conflict_raises_correct_code() -> None:
    conflict_body = {"errors": [{"field": "name", "message": "name already exists on this account"}]}
    client = _make_client({"/user/repos": {"POST": httpx.Response(422, json=conflict_body)}})
    with pytest.raises(GitProviderError) as ei:
        client.create_repo(name="myrepo")
    assert ei.value.reason_code == "repo_name_conflict"


def test_client_invalid_repo_name_raises() -> None:
    cfg = Settings(github_enabled=True, github_token="tok")
    client = GitHubClient(cfg, http_client=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200))))
    with pytest.raises(GitProviderError) as ei:
        client.create_repo(name="has spaces!!!")
    assert ei.value.reason_code == "invalid_repo_name"


def test_client_get_repo_from_clone_url_valid() -> None:
    client = _make_client({"/repos/acme/myrepo": {"GET": httpx.Response(200, json=_repo_json())}})
    raw = client.get_repo_from_clone_url(clone_url="https://github.com/acme/myrepo.git")
    assert raw.owner == "acme"
    assert raw.name == "myrepo"


def test_client_invalid_clone_url_raises() -> None:
    client = _make_client({})
    with pytest.raises(GitProviderError) as ei:
        client.get_repo_from_clone_url(clone_url="git@github.com:acme/myrepo.git")
    assert ei.value.reason_code == "invalid_clone_url"


def test_client_clone_url_regex_https_variants() -> None:
    valid = [
        "https://github.com/acme/repo",
        "https://github.com/acme/repo.git",
        "https://github.com/org-name/repo-name.git",
    ]
    invalid = [
        "http://github.com/acme/repo",
        "git@github.com:acme/repo.git",
        "https://gitlab.com/acme/repo",
    ]
    for url in valid:
        assert _CLONE_URL_RE.match(url), f"Expected valid: {url}"
    for url in invalid:
        assert not _CLONE_URL_RE.match(url), f"Expected invalid: {url}"


def test_client_create_ref_success() -> None:
    sha = "abc123def456"
    client = _make_client({
        "/repos/acme/myrepo/git/refs": {
            "POST": httpx.Response(201, json=_ref_json("trident/d3f1a2b4/add-model-router", sha))
        }
    })
    raw = client.create_ref(owner="acme", repo_name="myrepo", branch_name="trident/d3f1a2b4/test", from_sha=sha)
    assert raw.sha == sha


def test_client_put_file_encodes_base64() -> None:
    sha = "deadbeef"
    commit_payload = _commit_json(sha)

    requests_seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests_seen.append(request)
        return httpx.Response(200, json=commit_payload)

    cfg = Settings(github_enabled=True, github_token="tok")
    client = GitHubClient(cfg, http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    raw = client.put_file(
        owner="acme", repo_name="myrepo", path="README.md",
        content_utf8="# Hello", message="init", branch="main",
    )
    assert raw.sha == sha
    req = requests_seen[0]
    body = req.content
    import base64, json as j
    parsed = j.loads(body)
    decoded = base64.b64decode(parsed["content"]).decode()
    assert decoded == "# Hello"


# ── GitHubProvider tests ──────────────────────────────────────────────────────

def test_provider_name_is_github() -> None:
    client = _make_client({"/user": {"GET": httpx.Response(200, json={"login": "u"})}})
    provider = GitHubProvider(client)
    assert provider.provider_name == "github"


def test_provider_create_repo_returns_repo_info() -> None:
    client = _make_client({"/user/repos": {"POST": httpx.Response(201, json=_repo_json(private=True))}})
    provider = GitHubProvider(client)
    info = provider.create_repo(name="myrepo", private=True)
    assert isinstance(info, RepoInfo)
    assert info.created is True
    assert info.provider == "github"
    assert info.private is True


def test_provider_link_repo_returns_repo_info_created_false() -> None:
    client = _make_client({"/repos/acme/myrepo": {"GET": httpx.Response(200, json=_repo_json())}})
    provider = GitHubProvider(client)
    info = provider.link_repo(clone_url="https://github.com/acme/myrepo.git")
    assert isinstance(info, RepoInfo)
    assert info.created is False
    assert info.clone_url == "https://github.com/acme/myrepo.git"


def test_provider_create_branch_returns_branch_info() -> None:
    sha = "aabbcc112233"
    client = _make_client({
        "/repos/acme/myrepo/git/refs": {
            "POST": httpx.Response(201, json=_ref_json("trident/aaaaaaaa/feat", sha))
        }
    })
    provider = GitHubProvider(client)
    info = provider.create_branch(
        owner="acme", repo_name="myrepo",
        branch_name="trident/aaaaaaaa/feat", from_sha=sha,
    )
    assert isinstance(info, BranchInfo)
    assert info.branch_name == "trident/aaaaaaaa/feat"
    assert info.commit_sha == sha


def test_provider_push_files_returns_commit_info() -> None:
    sha = "cafebabe"
    client = _make_client({"/repos/acme/myrepo/contents/": {"PUT": httpx.Response(200, json=_commit_json(sha))}})
    provider = GitHubProvider(client)
    info = provider.push_files(
        owner="acme", repo_name="myrepo", branch_name="main",
        files={"README.md": "# Hello"},
        message="init scaffold",
    )
    assert isinstance(info, CommitInfo)
    assert info.sha == sha
    assert info.branch_name == "main"


def test_provider_push_files_empty_raises() -> None:
    client = _make_client({})
    provider = GitHubProvider(client)
    with pytest.raises(GitProviderError) as ei:
        provider.push_files(owner="a", repo_name="r", branch_name="main", files={}, message="x")
    assert ei.value.reason_code == "no_files_to_push"


def test_provider_link_repo_invalid_url_raises() -> None:
    client = _make_client({})
    provider = GitHubProvider(client)
    with pytest.raises(GitProviderError) as ei:
        provider.link_repo(clone_url="not-a-valid-url")
    assert ei.value.reason_code == "invalid_clone_url"


# ── Token isolation static scan ───────────────────────────────────────────────

def test_no_module_outside_github_client_constructs_bearer_header() -> None:
    """Enforce that ONLY github_client.py constructs 'Authorization': 'Bearer' headers for GitHub.

    Uses specific patterns that indicate active header construction, not docstring mentions.
    """
    import re
    from pathlib import Path

    backend_app = Path(__file__).resolve().parents[1] / "app"

    # Only these patterns indicate live credential injection — not commentary
    bearer_construction_pattern = re.compile(
        r'"Authorization"\s*:\s*f?["\']Bearer\s*\{',
        re.IGNORECASE,
    )
    token_env_read_pattern = re.compile(
        r'os\.(?:environ|getenv)\s*\(\s*["\'].*GITHUB_TOKEN',
        re.IGNORECASE,
    )

    allowed_files = {
        "config/settings.py",
        "git_provider/github/github_client.py",
    }
    offenders: list[str] = []

    for path in backend_app.rglob("*.py"):
        rel = str(path.relative_to(backend_app))
        if rel in allowed_files or "test_" in rel:
            continue
        text = path.read_text(encoding="utf-8")
        if bearer_construction_pattern.search(text) or token_env_read_pattern.search(text):
            offenders.append(rel)

    assert not offenders, f"Bearer header construction outside github_client.py: {offenders}"
