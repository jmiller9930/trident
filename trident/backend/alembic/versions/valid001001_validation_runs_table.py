"""VALIDATION_001 — validation_runs table for post-commit validation tracking.

Revision ID: valid001001
Revises: patch002001
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "valid001001"
down_revision = "patch002001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "validation_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("directive_id", sa.Uuid(), nullable=False),
        sa.Column("patch_id", sa.Uuid(), nullable=True),
        sa.Column("commit_sha", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column("validation_type", sa.String(length=32), nullable=False),
        sa.Column("result_summary", sa.Text(), nullable=True),
        sa.Column("result_payload_json", sa.JSON(), nullable=True),
        sa.Column("started_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("completed_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["completed_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["directive_id"], ["directives.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["patch_id"], ["patch_proposals.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["started_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_validation_runs_project_id"), "validation_runs", ["project_id"], unique=False)
    op.create_index(op.f("ix_validation_runs_directive_id"), "validation_runs", ["directive_id"], unique=False)
    op.create_index("ix_validation_runs_status", "validation_runs", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_validation_runs_status", table_name="validation_runs")
    op.drop_index(op.f("ix_validation_runs_directive_id"), table_name="validation_runs")
    op.drop_index(op.f("ix_validation_runs_project_id"), table_name="validation_runs")
    op.drop_table("validation_runs")
