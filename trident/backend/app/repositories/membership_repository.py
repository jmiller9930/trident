from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import ProjectMemberRole
from app.models.project_member import ProjectMember

ROLE_RANK: dict[str, int] = {
    ProjectMemberRole.VIEWER.value: 1,
    ProjectMemberRole.CONTRIBUTOR.value: 2,
    ProjectMemberRole.ADMIN.value: 3,
    ProjectMemberRole.OWNER.value: 4,
}


def role_at_least(role: str, minimum: ProjectMemberRole) -> bool:
    return ROLE_RANK.get(role, 0) >= ROLE_RANK[minimum.value]


class MembershipRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_membership(self, user_id: uuid.UUID, project_id: uuid.UUID) -> ProjectMember | None:
        q = select(ProjectMember).where(
            ProjectMember.user_id == user_id,
            ProjectMember.project_id == project_id,
        )
        return self._session.scalars(q).first()

    def require_membership(self, user_id: uuid.UUID, project_id: uuid.UUID) -> ProjectMember:
        m = self.get_membership(user_id, project_id)
        if m is None:
            raise ValueError("not_a_project_member")
        return m

    def require_role_at_least(self, user_id: uuid.UUID, project_id: uuid.UUID, minimum: ProjectMemberRole) -> ProjectMember:
        m = self.require_membership(user_id, project_id)
        if not role_at_least(m.role, minimum):
            raise ValueError("insufficient_project_role")
        return m

    def list_project_ids_for_user(self, user_id: uuid.UUID) -> list[uuid.UUID]:
        q = select(ProjectMember.project_id).where(ProjectMember.user_id == user_id)
        return list(self._session.scalars(q).all())

    def add_member(self, *, project_id: uuid.UUID, user_id: uuid.UUID, role: ProjectMemberRole) -> ProjectMember:
        row = ProjectMember(project_id=project_id, user_id=user_id, role=role.value)
        self._session.add(row)
        self._session.flush()
        return row

    def list_members(self, project_id: uuid.UUID) -> list[ProjectMember]:
        q = select(ProjectMember).where(ProjectMember.project_id == project_id).order_by(ProjectMember.created_at)
        return list(self._session.scalars(q).all())
