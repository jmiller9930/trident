from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps.auth_deps import get_current_user
from app.db.session import get_db
from app.models.enums import AuditActorType, AuditEventType, ProjectMemberRole
from app.models.project import Project
from app.models.user import User
from app.models.workspace import Workspace
from app.repositories.audit_repository import AuditRepository
from app.repositories.membership_repository import MembershipRepository
from app.schemas.project_schemas import ProjectCreateRequest, ProjectListResponse, ProjectSummary

router = APIRouter()


@router.post("/", response_model=ProjectSummary, status_code=201)
def create_project(
    body: ProjectCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProjectSummary:
    ws = Workspace(name=body.name, description=None, created_by_user_id=user.id)
    db.add(ws)
    db.flush()
    proj = Project(
        workspace_id=ws.id,
        name=body.name,
        allowed_root_path=body.allowed_root_path,
        git_remote_url=body.git_remote_url,
    )
    db.add(proj)
    db.flush()
    mrepo = MembershipRepository(db)
    mrepo.add_member(project_id=proj.id, user_id=user.id, role=ProjectMemberRole.OWNER)
    audit = AuditRepository(db)
    audit.record(
        event_type=AuditEventType.PROJECT_CREATED,
        event_payload={"project_id": str(proj.id), "name": body.name},
        actor_type=AuditActorType.USER,
        actor_id=str(user.id),
        workspace_id=ws.id,
        project_id=proj.id,
    )
    audit.record(
        event_type=AuditEventType.CONTROL_PLANE_ACTION,
        event_payload={"action": "project_create", "project_id": str(proj.id)},
        actor_type=AuditActorType.USER,
        actor_id=str(user.id),
        workspace_id=ws.id,
        project_id=proj.id,
    )
    return ProjectSummary.model_validate(proj)


@router.get("/", response_model=ProjectListResponse)
def list_projects(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> ProjectListResponse:
    mrepo = MembershipRepository(db)
    pids = mrepo.list_project_ids_for_user(user.id)
    if not pids:
        return ProjectListResponse(items=[])
    rows = list(db.scalars(select(Project).where(Project.id.in_(pids)).order_by(Project.created_at.desc())).all())
    return ProjectListResponse(items=[ProjectSummary.model_validate(r) for r in rows])


@router.get("/{project_id}", response_model=ProjectSummary)
def get_project(project_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> ProjectSummary:
    mrepo = MembershipRepository(db)
    try:
        mrepo.require_role_at_least(user.id, project_id, ProjectMemberRole.VIEWER)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    proj = db.get(Project, project_id)
    if proj is None:
        raise HTTPException(status_code=404, detail="project_not_found")
    return ProjectSummary.model_validate(proj)
