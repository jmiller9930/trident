from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base


class FileLock(Base):
    __tablename__ = "file_locks"

    __table_args__ = (
        Index(
            "uq_file_locks_active_project_path",
            "project_id",
            "file_path",
            unique=True,
            sqlite_where=text("lock_status = 'ACTIVE' AND released_at IS NULL"),
            postgresql_where=text("lock_status = 'ACTIVE' AND released_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)
    directive_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("directives.id"), nullable=False)
    file_path: Mapped[str] = mapped_column(Text(), nullable=False)
    locked_by_agent_role: Mapped[str] = mapped_column(String(32), nullable=False)
    locked_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)
    lock_status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
