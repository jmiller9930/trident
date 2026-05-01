"""GitHub repository API — /projects/{project_id}/git/* (GITHUB_003)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps.auth_deps import get_current_user
from app.api.deps.git_deps import get_git_provider
from app.db.session import get_db
from app.git_provider.base import GitProvider, GitProviderError
from app.models.enums import ProjectMemberRole
from app.models.user import User
from app.repositories.membership_repository import MembershipRepository
from app.schemas.git_schemas import (
    GitBranchListResponse,
    GitCreateBranchRequest,
    GitCreateBranchResponse,
    GitCreateRepoRequest,
    GitCreateRepoResponse,
    GitLinkRepoRequest,
    GitLinkRepoResponse,
    GitPushFilesRequest,
    GitPushFilesResponse,
    GitRepoStatusResponse,
)
from app.services.git_project_service import (
    GitAlreadyLinkedError,
    GitDirectiveMismatchError,
    GitInvalidBranchNameError,
    GitNotLinkedError,
    GitProjectService,
)

router = APIRouter()

# ── RBAC helper ───────────────────────────────────────────────────────────────

def _require_role(db: Session, user_id: uuid.UUID, project_id: uuid.UUID, minimum: ProjectMemberRole) -> None:
    try:
        MembershipRepository(db).require_role_at_least(user_id, project_id, minimum)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e


# ── Provider error mapper ─────────────────────────────────────────────────────

def _provider_error_to_http(e: GitProviderError) -> HTTPException:
    code = e.reason_code
    if code in ("repo_name_conflict", "branch_already_exists"):
        return HTTPException(status_code=409, detail=code)
    if code in ("github_auth_failed", "github_permission_denied"):
        return HTTPException(status_code=403, detail=code)
    if code == "github_not_found":
        return HTTPException(status_code=404, detail=code)
    return HTTPException(status_code=502, detail=f"git_provider_error:{code}")


# ── POST /create-repo ─────────────────────────────────────────────────────────

@router.post("/create-repo", response_model=GitCreateRepoResponse, status_code=201)
def create_repo(
    project_id: uuid.UUID,
    body: GitCreateRepoRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    provider: GitProvider = Depends(get_git_provider),
) -> GitCreateRepoResponse:
    _require_role(db, user.id, project_id, ProjectMemberRole.ADMIN)
    svc = GitProjectService(db, provider=provider)
    try:
        return svc.create_repo(project_id, user.id, body)
    except GitAlreadyLinkedError:
        raise HTTPException(status_code=409, detail="repo_already_linked") from None
    except GitProviderError as e:
        raise _provider_error_to_http(e) from None


# ── POST /link-repo ───────────────────────────────────────────────────────────

@router.post("/link-repo", response_model=GitLinkRepoResponse, status_code=201)
def link_repo(
    project_id: uuid.UUID,
    body: GitLinkRepoRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    provider: GitProvider = Depends(get_git_provider),
) -> GitLinkRepoResponse:
    _require_role(db, user.id, project_id, ProjectMemberRole.ADMIN)
    svc = GitProjectService(db, provider=provider)
    try:
        return svc.link_repo(project_id, user.id, body)
    except GitAlreadyLinkedError:
        raise HTTPException(status_code=409, detail="repo_already_linked") from None
    except GitProviderError as e:
        raise _provider_error_to_http(e) from None


# ── GET /repo-status ──────────────────────────────────────────────────────────

@router.get("/repo-status", response_model=GitRepoStatusResponse)
def repo_status(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> GitRepoStatusResponse:
    """Read-only; does not require GitHub provider (reads from DB)."""
    _require_role(db, user.id, project_id, ProjectMemberRole.VIEWER)
    svc = GitProjectService(db, provider=None)  # type: ignore[arg-type]
    try:
        return svc.get_repo_status(project_id)
    except GitNotLinkedError:
        raise HTTPException(status_code=404, detail="repo_not_linked") from None


# ── POST /create-branch ───────────────────────────────────────────────────────

@router.post("/create-branch", response_model=GitCreateBranchResponse, status_code=201)
def create_branch(
    project_id: uuid.UUID,
    body: GitCreateBranchRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    provider: GitProvider = Depends(get_git_provider),
) -> GitCreateBranchResponse:
    _require_role(db, user.id, project_id, ProjectMemberRole.CONTRIBUTOR)
    svc = GitProjectService(db, provider=provider)
    try:
        return svc.create_branch(project_id, user.id, body)
    except GitNotLinkedError:
        raise HTTPException(status_code=404, detail="repo_not_linked") from None
    except GitAlreadyLinkedError:
        raise HTTPException(status_code=409, detail="repo_already_linked") from None
    except GitDirectiveMismatchError:
        raise HTTPException(status_code=422, detail="directive_not_in_project") from None
    except GitInvalidBranchNameError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None
    except GitProviderError as e:
        raise _provider_error_to_http(e) from None


# ── POST /directives/{directive_id}/push-files ───────────────────────────────

@router.post("/directives/{directive_id}/push-files", response_model=GitPushFilesResponse, status_code=201)
def push_files(
    project_id: uuid.UUID,
    directive_id: uuid.UUID,
    body: GitPushFilesRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    provider: GitProvider = Depends(get_git_provider),
) -> GitPushFilesResponse:
    _require_role(db, user.id, project_id, ProjectMemberRole.CONTRIBUTOR)
    svc = GitProjectService(db, provider=provider)
    try:
        return svc.push_files_for_directive(project_id, directive_id, user.id, body)
    except GitNotLinkedError as e:
        code = str(e)
        status = 409 if code == "directive_branch_missing" else 404
        raise HTTPException(status_code=status, detail=code) from None
    except GitDirectiveMismatchError:
        raise HTTPException(status_code=422, detail="directive_not_in_project") from None
    except GitInvalidBranchNameError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None
    except GitProviderError as e:
        raise _provider_error_to_http(e) from None


# ── GET /branches ─────────────────────────────────────────────────────────────

@router.get("/branches", response_model=GitBranchListResponse)
def list_branches(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> GitBranchListResponse:
    """Read-only; does not require GitHub provider (reads from DB)."""
    _require_role(db, user.id, project_id, ProjectMemberRole.VIEWER)
    svc = GitProjectService(db, provider=None)  # type: ignore[arg-type]
    return svc.list_branches(project_id)
