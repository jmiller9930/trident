"""Pydantic schemas for GitHub provider API endpoints (GITHUB_003).

No token fields in any schema.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# ── Request schemas ──────────────────────────────────────────────────────────

class GitCreateRepoRequest(BaseModel):
    name: str | None = Field(default=None, max_length=100, pattern=r"^[a-zA-Z0-9._-]*$")
    description: str = Field(default="", max_length=1024)
    private: bool = True
    org: str | None = Field(default=None, max_length=255)
    init_scaffold: bool = False


class GitLinkRepoRequest(BaseModel):
    clone_url: str = Field(min_length=5, max_length=2048)
    branch: str | None = Field(default=None, max_length=255)


class GitCreateBranchRequest(BaseModel):
    branch_name: str | None = Field(default=None, max_length=255)
    directive_id: uuid.UUID | None = None
    from_sha: str | None = Field(default=None, max_length=64)


# ── Response schemas ─────────────────────────────────────────────────────────

class GitRepoStatusResponse(BaseModel):
    provider: str
    owner: str
    repo_name: str
    clone_url: str
    html_url: str
    default_branch: str
    current_git_branch: str | None
    current_git_commit_sha: str | None
    private: bool
    linked_at: datetime
    linked_by_user_id: uuid.UUID


class GitCreateRepoResponse(BaseModel):
    provider: str
    owner: str
    repo_name: str
    clone_url: str
    html_url: str
    default_branch: str
    private: bool
    created: bool
    git_commit_sha: str | None


class GitLinkRepoResponse(BaseModel):
    provider: str
    owner: str
    repo_name: str
    clone_url: str
    html_url: str
    default_branch: str
    private: bool
    git_commit_sha: str | None


class GitBranchResponse(BaseModel):
    provider: str
    branch_name: str
    commit_sha: str | None
    directive_id: uuid.UUID | None
    event_type: str
    created_at: datetime


class GitBranchListResponse(BaseModel):
    items: list[GitBranchResponse]


class GitCreateBranchResponse(BaseModel):
    provider: str
    branch_name: str
    commit_sha: str
    directive_id: uuid.UUID | None


class GitPushFileItem(BaseModel):
    path: str = Field(min_length=1, max_length=4096)
    content: str = Field(max_length=1_000_000)


class GitPushFilesRequest(BaseModel):
    files: list[GitPushFileItem] = Field(min_length=1)
    commit_message: str = Field(min_length=1, max_length=4096)


class GitPushFilesResponse(BaseModel):
    provider: str
    owner: str
    repo_name: str
    branch_name: str
    commit_sha: str
    commit_message: str
    file_count: int
    proof_object_id: uuid.UUID | None = None
