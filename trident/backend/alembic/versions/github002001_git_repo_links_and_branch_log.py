"""GITHUB_002 — git_repo_links + git_branch_log tables + indexes.

Revision ID: github002001
Revises: onboard001001
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "github002001"
down_revision = "onboard001001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── git_repo_links ──────────────────────────────────────────────────────
    op.create_table(
        "git_repo_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("owner", sa.String(length=255), nullable=False),
        sa.Column("repo_name", sa.String(length=255), nullable=False),
        sa.Column("clone_url", sa.Text(), nullable=False),
        sa.Column("html_url", sa.Text(), nullable=False),
        sa.Column("default_branch", sa.String(length=255), nullable=False, server_default="main"),
        sa.Column("private", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("linked_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("linked_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["linked_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", name="uq_git_repo_links_project_id"),
        comment="Active git provider repo link for a Trident project (GITHUB_002)",
    )
    op.create_index(
        op.f("ix_git_repo_links_project_id"),
        "git_repo_links",
        ["project_id"],
        unique=False,
    )

    # ── git_branch_log ──────────────────────────────────────────────────────
    op.create_table(
        "git_branch_log",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("directive_id", sa.Uuid(), nullable=True),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("branch_name", sa.String(length=255), nullable=False),
        sa.Column("commit_sha", sa.String(length=64), nullable=True),
        sa.Column("commit_message", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["directive_id"], ["directives.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_git_branch_log_project_id"),
        "git_branch_log",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_git_branch_log_directive_id"),
        "git_branch_log",
        ["directive_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_git_branch_log_directive_id"), table_name="git_branch_log")
    op.drop_index(op.f("ix_git_branch_log_project_id"), table_name="git_branch_log")
    op.drop_table("git_branch_log")
    op.drop_index(op.f("ix_git_repo_links_project_id"), table_name="git_repo_links")
    op.drop_table("git_repo_links")
