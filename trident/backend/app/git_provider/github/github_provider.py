"""GitHubProvider — implements GitProvider using GitHubClient (GITHUB_001).

Token isolation rule: this module NEVER reads the token directly.
All GitHub API calls go through self._client (GitHubClient), which is
the sole token holder.
"""

from __future__ import annotations

from app.git_provider.base import (
    BranchInfo,
    CommitInfo,
    GitProvider,
    GitProviderError,
    RepoInfo,
)
from app.git_provider.github.github_client import GitHubClient


class GitHubProvider(GitProvider):
    """GitHub implementation of GitProvider.

    Accepts an injected GitHubClient so it can be tested with mocked HTTP.
    Never constructs Authorization headers; never reads the token.
    """

    def __init__(self, client: GitHubClient) -> None:
        self._client = client

    # ── GitProvider interface ───────────────────────────────────────────────

    @property
    def provider_name(self) -> str:
        return "github"

    def ping(self) -> bool:
        return self._client.ping()

    def create_repo(
        self,
        *,
        name: str,
        description: str = "",
        private: bool = True,
        org: str | None = None,
    ) -> RepoInfo:
        raw = self._client.create_repo(
            name=name,
            description=description,
            private=private,
            org=org,
        )
        return RepoInfo(
            provider="github",
            owner=raw.owner,
            repo_name=raw.name,
            clone_url=raw.clone_url,
            html_url=raw.html_url,
            default_branch=raw.default_branch,
            private=raw.private,
            created=True,
        )

    def get_repo_info(self, *, owner: str, repo_name: str) -> RepoInfo:
        raw = self._client.get_repo(owner=owner, repo_name=repo_name)
        return RepoInfo(
            provider="github",
            owner=raw.owner,
            repo_name=raw.name,
            clone_url=raw.clone_url,
            html_url=raw.html_url,
            default_branch=raw.default_branch,
            private=raw.private,
            created=False,
        )

    def link_repo(self, *, clone_url: str) -> RepoInfo:
        raw = self._client.get_repo_from_clone_url(clone_url=clone_url)
        return RepoInfo(
            provider="github",
            owner=raw.owner,
            repo_name=raw.name,
            clone_url=raw.clone_url,
            html_url=raw.html_url,
            default_branch=raw.default_branch,
            private=raw.private,
            created=False,
        )

    def get_default_branch_sha(self, *, owner: str, repo_name: str) -> str:
        info = self.get_repo_info(owner=owner, repo_name=repo_name)
        raw = self._client.get_branch_head_sha(
            owner=owner,
            repo_name=repo_name,
            branch=info.default_branch,
        )
        return raw.sha

    def create_branch(
        self,
        *,
        owner: str,
        repo_name: str,
        branch_name: str,
        from_sha: str,
    ) -> BranchInfo:
        raw = self._client.create_ref(
            owner=owner,
            repo_name=repo_name,
            branch_name=branch_name,
            from_sha=from_sha,
        )
        return BranchInfo(
            provider="github",
            branch_name=branch_name,
            commit_sha=raw.sha,
            html_url=f"https://github.com/{owner}/{repo_name}/tree/{branch_name}",
        )

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
        """Push multiple files to a branch using sequential Contents API calls.

        For MVP: sequential PUT /contents per file; last commit SHA is returned.
        Future: replace with Git Data API tree + commit batch for atomicity.
        """
        if not files:
            raise GitProviderError(
                "push_files called with empty files dict",
                reason_code="no_files_to_push",
            )

        last_commit: str = ""
        last_url: str = ""
        for path, content in files.items():
            raw = self._client.put_file(
                owner=owner,
                repo_name=repo_name,
                path=path,
                content_utf8=content,
                message=message,
                branch=branch_name,
                committer_name=committer_name,
                committer_email=committer_email,
            )
            last_commit = raw.sha
            last_url = raw.html_url

        return CommitInfo(
            provider="github",
            sha=last_commit,
            message=message,
            branch_name=branch_name,
            html_url=last_url or None,
        )
