from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import ProjectMemberRole


class InviteCreateRequest(BaseModel):
    project_id: uuid.UUID
    email: EmailStr
    role: ProjectMemberRole = ProjectMemberRole.CONTRIBUTOR


class InviteCreatedResponse(BaseModel):
    invite_id: uuid.UUID
    project_id: uuid.UUID
    email: str
    role: str
    token: uuid.UUID
    expires_at: datetime


class AcceptInviteRequest(BaseModel):
    token: uuid.UUID


class MemberSummary(BaseModel):
    user_id: uuid.UUID
    role: str
    created_at: datetime


class MemberListResponse(BaseModel):
    items: list[MemberSummary]
