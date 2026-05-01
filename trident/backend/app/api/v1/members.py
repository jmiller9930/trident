from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps.auth_deps import get_current_user
from app.db.session import get_db
from app.models.enums import AuditActorType, AuditEventType, ProjectMemberRole
from app.models.project_invite import ProjectInvite
from app.models.user import User
from app.repositories.audit_repository import AuditRepository
from app.repositories.membership_repository import MembershipRepository
from app.schemas.member_schemas import (
    AcceptInviteRequest,
    InviteCreatedResponse,
    InviteCreateRequest,
    MemberListResponse,
    MemberSummary,
)

router = APIRouter()

INVITE_TTL_DAYS = 14


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _as_utc(dt: datetime) -> datetime:
    """SQLite may return naive datetimes even when columns are timezone=True."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@router.post("/invites", response_model=InviteCreatedResponse, status_code=201)
def create_invite(
    body: InviteCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> InviteCreatedResponse:
    if body.role == ProjectMemberRole.OWNER:
        raise HTTPException(status_code=400, detail="cannot_invite_owner_role")

    mrepo = MembershipRepository(db)
    try:
        mrepo.require_role_at_least(user.id, body.project_id, ProjectMemberRole.ADMIN)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e

    email = _normalize_email(str(body.email))
    existing_user = db.scalars(select(User).where(User.email == email)).first()
    if existing_user is not None:
        existing_member = mrepo.get_membership(existing_user.id, body.project_id)
        if existing_member is not None:
            raise HTTPException(status_code=409, detail="user_already_member")

    now = datetime.now(timezone.utc)
    token = uuid.uuid4()
    inv = ProjectInvite(
        project_id=body.project_id,
        email=email,
        role=body.role.value,
        token=token,
        invited_by_user_id=user.id,
        expires_at=now + timedelta(days=INVITE_TTL_DAYS),
    )
    db.add(inv)
    db.flush()

    audit = AuditRepository(db)
    audit.record(
        event_type=AuditEventType.MEMBER_INVITED,
        event_payload={"email": email, "role": body.role.value, "invite_id": str(inv.id)},
        actor_type=AuditActorType.USER,
        actor_id=str(user.id),
        project_id=body.project_id,
    )
    audit.record(
        event_type=AuditEventType.CONTROL_PLANE_ACTION,
        event_payload={"action": "member_invite", "project_id": str(body.project_id), "email": email},
        actor_type=AuditActorType.USER,
        actor_id=str(user.id),
        project_id=body.project_id,
    )

    return InviteCreatedResponse(
        invite_id=inv.id,
        project_id=inv.project_id,
        email=inv.email,
        role=inv.role,
        token=inv.token,
        expires_at=inv.expires_at,
    )


@router.post("/accept", status_code=200)
def accept_invite(
    body: AcceptInviteRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, str]:
    inv = db.scalars(select(ProjectInvite).where(ProjectInvite.token == body.token)).first()
    if inv is None:
        raise HTTPException(status_code=404, detail="invite_not_found")
    if inv.accepted_at is not None:
        raise HTTPException(status_code=409, detail="invite_already_accepted")
    now = datetime.now(timezone.utc)
    if _as_utc(inv.expires_at) < now:
        raise HTTPException(status_code=410, detail="invite_expired")

    if _normalize_email(user.email) != inv.email:
        raise HTTPException(status_code=403, detail="invite_email_mismatch")

    mrepo = MembershipRepository(db)
    if mrepo.get_membership(user.id, inv.project_id) is not None:
        inv.accepted_at = now
        db.flush()
        return {"status": "already_member"}

    mrepo.add_member(project_id=inv.project_id, user_id=user.id, role=ProjectMemberRole(inv.role))
    inv.accepted_at = now

    audit = AuditRepository(db)
    audit.record(
        event_type=AuditEventType.MEMBER_ACCEPTED,
        event_payload={"invite_id": str(inv.id), "user_id": str(user.id)},
        actor_type=AuditActorType.USER,
        actor_id=str(user.id),
        project_id=inv.project_id,
    )
    audit.record(
        event_type=AuditEventType.CONTROL_PLANE_ACTION,
        event_payload={"action": "member_accept", "project_id": str(inv.project_id)},
        actor_type=AuditActorType.USER,
        actor_id=str(user.id),
        project_id=inv.project_id,
    )
    return {"status": "joined"}


@router.get("/projects/{project_id}", response_model=MemberListResponse)
def list_members(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MemberListResponse:
    mrepo = MembershipRepository(db)
    try:
        mrepo.require_role_at_least(user.id, project_id, ProjectMemberRole.VIEWER)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    rows = mrepo.list_members(project_id)
    return MemberListResponse(
        items=[MemberSummary(user_id=r.user_id, role=r.role, created_at=r.created_at) for r in rows]
    )
