"""GitBranchLog — append-only log of branch/commit events per project (GITHUB_002)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base

# Allowed event_type values (not a DB constraint; validated by service layer)
GIT_BRANCH_LOG_EVENTS = frozenset({"branch_created", "commit_pushed"})


class GitBranchLog(Base):
    """Append-only audit trail for git branch and commit activity.

    directive_id is nullable so scaffold commits before directive assignment
    can still be recorded. Event types are restricted to the values in
    GIT_BRANCH_LOG_EVENTS.
    """

    __tablename__ = "git_branch_log"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    directive_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("directives.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    provider: Mapped[str] = mapped_column(String(32), nullable=False)  # "github" | "gitlab" (future)
    branch_name: Mapped[str] = mapped_column(String(255), nullable=False)
    commit_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    commit_message: Mapped[str | None] = mapped_column(Text(), nullable=True)

    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)  # "branch_created" | "commit_pushed"

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
