"""GitRepoLink — one active GitHub (or future provider) repo per project (GITHUB_002)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base


class GitRepoLink(Base):
    """Records the active repository linked to a Trident project.

    Design rules (enforced by migration / application layer):
    - One active repo link per project (unique constraint on project_id).
    - No credential or token fields — clone_url/html_url only.
    - provider field enables future GitLab / Gitea support without schema change.
    """

    __tablename__ = "git_repo_links"
    __table_args__ = (
        UniqueConstraint("project_id", name="uq_git_repo_links_project_id"),
        {"comment": "Active git provider repo link for a Trident project (GITHUB_002)"},
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    provider: Mapped[str] = mapped_column(String(32), nullable=False)  # "github" | "gitlab" (future)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    repo_name: Mapped[str] = mapped_column(String(255), nullable=False)
    clone_url: Mapped[str] = mapped_column(Text(), nullable=False)   # HTTPS clone URL, never tokenized
    html_url: Mapped[str] = mapped_column(Text(), nullable=False)    # Browser URL
    default_branch: Mapped[str] = mapped_column(String(255), nullable=False, default="main")
    private: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=True)

    linked_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
