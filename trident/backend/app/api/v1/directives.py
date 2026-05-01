from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps.auth_deps import get_current_user
from app.api.deps.git_deps import get_optional_git_provider
from app.config.settings import Settings
from app.db.session import get_db, get_settings_dep
from app.git_provider.base import GitProvider
from app.models.enums import DirectiveStatus, ProjectMemberRole
from app.models.project import Project
from app.models.user import User
from app.repositories.directive_repository import DirectiveRepository
from app.repositories.membership_repository import MembershipRepository
from app.repositories.task_ledger_repository import TaskLedgerRepository
from app.schemas.directive import (
    CreateDirectiveApiRequest,
    CreateDirectiveRequest,
    DirectiveDetailResponse,
    DirectiveIssueResponse,
    DirectiveListResponse,
    DirectiveSignoffResponse,
    DirectiveSummary,
    TaskLedgerSummary,
)
from app.services.git_project_service import GitProjectService
from app.services.signoff_service import (
    DirectiveAlreadyClosedError,
    DirectiveMismatchError as SignoffDirectiveMismatchError,
    DirectiveNotIssuedError,
    SignoffNotEligibleError,
    SignoffService,
)
from app.schemas.workflow import WorkflowRunResponse
from app.models.enums import DirectiveStatus as DirectiveStatusEnum
from app.services.state_transition_service import StateTransitionService
from app.workflow.spine import run_spine_workflow

router = APIRouter()


def _require_contributor(db: Session, user_id: uuid.UUID, project_id: uuid.UUID) -> None:
    mrepo = MembershipRepository(db)
    try:
        mrepo.require_role_at_least(user_id, project_id, ProjectMemberRole.CONTRIBUTOR)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e


def _require_viewer(db: Session, user_id: uuid.UUID, project_id: uuid.UUID) -> None:
    mrepo = MembershipRepository(db)
    try:
        mrepo.require_role_at_least(user_id, project_id, ProjectMemberRole.VIEWER)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e


@router.post("/{directive_id}/workflow/run", response_model=WorkflowRunResponse)
def run_workflow(
    directive_id: uuid.UUID,
    db: Session = Depends(get_db),
    cfg: Settings = Depends(get_settings_dep),
    user: User = Depends(get_current_user),
    reviewer_rejections_remaining: int = Query(
        0,
        ge=0,
        le=32,
        description="Deterministic reviewer rejections before accept (100C simulation).",
    ),
) -> WorkflowRunResponse:
    drepo = DirectiveRepository(db)
    d = drepo.get_by_id(directive_id)
    if d is None:
        raise HTTPException(status_code=404, detail="directive_not_found")
    _require_contributor(db, user.id, d.project_id)
    try:
        out = run_spine_workflow(
            db,
            directive_id,
            reviewer_rejections_remaining=reviewer_rejections_remaining,
            model_router_settings=cfg,
        )
    except ValueError as e:
        code = str(e)
        if code == "directive_not_found":
            raise HTTPException(status_code=404, detail=code) from e
        if code == "workflow_already_complete":
            raise HTTPException(status_code=409, detail=code) from e
        raise HTTPException(status_code=400, detail=code) from e
    trepo = TaskLedgerRepository(db)
    ledger = trepo.get_by_directive_id(directive_id)
    d2 = drepo.get_by_id(directive_id)
    assert d2 is not None and ledger is not None
    return WorkflowRunResponse(
        directive_id=directive_id,
        final_ledger_state=ledger.current_state,
        directive_status=d2.status,
        nodes_executed=out["nodes_executed"],
    )


@router.post("/", response_model=DirectiveDetailResponse)
def create_directive(
    body: CreateDirectiveApiRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DirectiveDetailResponse:
    proj = db.get(Project, body.project_id)
    if proj is None:
        raise HTTPException(status_code=404, detail="project_not_found")
    _require_contributor(db, user.id, body.project_id)

    internal = CreateDirectiveRequest(
        workspace_id=proj.workspace_id,
        project_id=body.project_id,
        title=body.title,
        graph_id=body.graph_id,
        created_by_user_id=user.id,
        status=body.status,
    )
    repo = DirectiveRepository(db)
    try:
        directive, ledger, _gs = repo.create_directive_and_initialize(internal)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return DirectiveDetailResponse(
        directive=DirectiveSummary.model_validate(directive),
        task_ledger=TaskLedgerSummary.model_validate(ledger),
    )


@router.get("/", response_model=DirectiveListResponse)
def list_directives(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    limit: int = 100,
) -> DirectiveListResponse:
    mrepo = MembershipRepository(db)
    pids = mrepo.list_project_ids_for_user(user.id)
    repo = DirectiveRepository(db)
    rows = repo.list_summaries_for_projects(pids, limit=limit)
    return DirectiveListResponse(items=[DirectiveSummary.model_validate(r) for r in rows])


@router.get("/{directive_id}", response_model=DirectiveDetailResponse)
def get_directive(
    directive_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DirectiveDetailResponse:
    drepo = DirectiveRepository(db)
    trepo = TaskLedgerRepository(db)
    d = drepo.get_by_id(directive_id)
    if d is None:
        raise HTTPException(status_code=404, detail="directive_not_found")
    _require_viewer(db, user.id, d.project_id)
    ledger = trepo.get_by_directive_id(directive_id)
    if ledger is None:
        raise HTTPException(status_code=404, detail="task_ledger_not_found")
    return DirectiveDetailResponse(
        directive=DirectiveSummary.model_validate(d),
        task_ledger=TaskLedgerSummary.model_validate(ledger),
    )


@router.post("/{directive_id}/issue", response_model=DirectiveIssueResponse)
def issue_directive(
    directive_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    git_provider: GitProvider | None = Depends(get_optional_git_provider),
) -> DirectiveIssueResponse:
    drepo = DirectiveRepository(db)
    d = drepo.get_by_id(directive_id)
    if d is None:
        raise HTTPException(status_code=404, detail="directive_not_found")
    _require_contributor(db, user.id, d.project_id)

    # ── State transition (authoritative) ─────────────────────────────────────
    svc = StateTransitionService(db)
    try:
        d2 = svc.transition_directive_status(
            directive_id=directive_id,
            actor_user_id=user.id,
            to_status=DirectiveStatus.ISSUED,
        )
    except ValueError as e:
        code = str(e)
        if code == "invalid_directive_status_transition":
            raise HTTPException(status_code=409, detail=code) from e
        raise HTTPException(status_code=400, detail=code) from e

    # ── Git branch creation (non-blocking, runs after transition) ────────────
    git_branch_created = False
    git_branch_name: str | None = None
    git_commit_sha: str | None = None
    git_warning: str | None = None

    if git_provider is not None:
        try:
            git_svc = GitProjectService(db, provider=git_provider)
            git_branch_created, git_branch_name, git_commit_sha, git_warning = (
                git_svc.create_branch_for_directive(
                    directive_id=directive_id,
                    project_id=d2.project_id,
                    user_id=user.id,
                    directive_title=d2.title,
                )
            )
        except Exception as exc:
            git_warning = f"git_branch_error:{type(exc).__name__}"

    base = DirectiveSummary.model_validate(d2)
    return DirectiveIssueResponse(
        **base.model_dump(),
        git_branch_created=git_branch_created,
        git_branch_name=git_branch_name,
        git_commit_sha=git_commit_sha,
        git_warning=git_warning,
    )


@router.post("/{directive_id}/signoff", response_model=DirectiveSignoffResponse)
def signoff_directive(
    directive_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DirectiveSignoffResponse:
    drepo = DirectiveRepository(db)
    d = drepo.get_by_id(directive_id)
    if d is None:
        raise HTTPException(status_code=404, detail="directive_not_found")
    try:
        from app.repositories.membership_repository import MembershipRepository
        from app.models.enums import ProjectMemberRole
        MembershipRepository(db).require_role_at_least(user.id, d.project_id, ProjectMemberRole.ADMIN)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e

    svc = SignoffService(db)
    try:
        closed, proof_id = svc.signoff(d.project_id, directive_id, user.id)
    except DirectiveAlreadyClosedError:
        raise HTTPException(status_code=409, detail="directive_already_closed") from None
    except DirectiveNotIssuedError as e:
        raise HTTPException(status_code=409, detail=str(e)) from None
    except SignoffDirectiveMismatchError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None
    except SignoffNotEligibleError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None

    resp = DirectiveSignoffResponse.model_validate(closed)
    return resp.model_copy(update={"proof_object_id": proof_id})
