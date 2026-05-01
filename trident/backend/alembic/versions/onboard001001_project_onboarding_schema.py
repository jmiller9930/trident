"""ONBOARD_001 — project_onboarding table + project onboarding metadata columns.

Revision ID: onboard001001
Revises: impl001001
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "onboard001001"
down_revision = "impl001001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Extend projects table ──────────────────────────────────────────────
    op.add_column("projects", sa.Column("onboarding_status", sa.String(length=32), nullable=True))
    op.add_column("projects", sa.Column("git_branch", sa.String(length=255), nullable=True))
    op.add_column("projects", sa.Column("git_commit_sha", sa.String(length=64), nullable=True))
    op.add_column("projects", sa.Column("language_primary", sa.String(length=64), nullable=True))
    op.add_column("projects", sa.Column("description", sa.Text(), nullable=True))

    # ── project_onboarding table ───────────────────────────────────────────
    op.create_table(
        "project_onboarding",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"),
        # Repository identity
        sa.Column("repo_local_path", sa.Text(), nullable=True),
        sa.Column("git_remote_url", sa.Text(), nullable=True),
        sa.Column("git_branch", sa.String(length=255), nullable=True),
        sa.Column("git_commit_sha", sa.String(length=64), nullable=True),
        # Detected tech stack
        sa.Column("language_primary", sa.String(length=64), nullable=True),
        sa.Column("languages_detected", sa.JSON(), nullable=True),
        sa.Column("framework_hints", sa.JSON(), nullable=True),
        # Audit artifacts
        sa.Column("scan_artifact_json", sa.JSON(), nullable=True),
        sa.Column("asbuilt_artifact_json", sa.JSON(), nullable=True),
        # Indexing
        sa.Column("index_job_id", sa.String(length=64), nullable=True),
        # Approval
        sa.Column("approved_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        # Re-onboarding chain
        sa.Column("previous_onboarding_id", sa.Uuid(), nullable=True),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["previous_onboarding_id"],
            ["project_onboarding.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="Onboarding lifecycle for existing repo import",
    )
    op.create_index(
        op.f("ix_project_onboarding_project_id"),
        "project_onboarding",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_project_onboarding_active_unique",
        "project_onboarding",
        ["project_id"],
        unique=True,
        postgresql_where=sa.text("status NOT IN ('APPROVED', 'REJECTED')"),
    )


def downgrade() -> None:
    op.drop_index("ix_project_onboarding_active_unique", table_name="project_onboarding")
    op.drop_index(
        op.f("ix_project_onboarding_project_id"), table_name="project_onboarding"
    )
    op.drop_table("project_onboarding")
    op.drop_column("projects", "description")
    op.drop_column("projects", "language_primary")
    op.drop_column("projects", "git_commit_sha")
    op.drop_column("projects", "git_branch")
    op.drop_column("projects", "onboarding_status")
