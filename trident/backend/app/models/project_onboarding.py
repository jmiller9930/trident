"""Project onboarding record (EXISTING_PROJECT_ONBOARDING_001 / ONBOARD_001)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON, Uuid

from app.db.base import Base


class ProjectOnboarding(Base):
    """State machine for onboarding a single existing repository into Trident.

    Lifecycle: PENDING → SCANNING → SCANNED → INDEXING → INDEXED
               → AWAITING_APPROVAL → APPROVED | REJECTED

    Rules:
    - One *active* onboarding per project (enforced by partial unique index in migration).
    - APPROVED rows are treated as immutable; re-onboarding must create a new row
      linked via previous_onboarding_id.
    - No code changes to the repo may occur until onboarding is APPROVED.
    """

    __tablename__ = "project_onboarding"
    __table_args__ = (
        # Enforces at most one non-APPROVED/non-REJECTED row per project.
        # Uniqueness is partial in the migration (WHERE status NOT IN ('APPROVED','REJECTED'))
        # — annotated here for documentation only; DB enforces via the partial index.
        {"comment": "Onboarding lifecycle for existing repo import"},
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")

    # ── Repository identity ────────────────────────────────────────────────
    repo_local_path: Mapped[str | None] = mapped_column(Text(), nullable=True)
    git_remote_url: Mapped[str | None] = mapped_column(Text(), nullable=True)
    git_branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    git_commit_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # ── Detected tech stack ────────────────────────────────────────────────
    language_primary: Mapped[str | None] = mapped_column(String(64), nullable=True)
    languages_detected: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=True
    )
    framework_hints: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=True
    )

    # ── Audit artifacts ────────────────────────────────────────────────────
    scan_artifact_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=True
    )
    asbuilt_artifact_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=True
    )

    # ── Indexing (ONBOARD_003) ─────────────────────────────────────────────
    index_job_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    index_status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="NOT_STARTED")
    indexed_file_count: Mapped[int | None] = mapped_column(nullable=True)
    indexed_chunk_count: Mapped[int | None] = mapped_column(nullable=True)
    index_error_safe: Mapped[str | None] = mapped_column(Text(), nullable=True)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── Approval ───────────────────────────────────────────────────────────
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text(), nullable=True)

    # ── Re-onboarding chain ────────────────────────────────────────────────
    previous_onboarding_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("project_onboarding.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ── Timestamps ────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
