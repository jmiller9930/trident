"""PATCH_001 — patch_proposals table for governed diff review lifecycle.

Revision ID: patch001001
Revises: github002001
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "patch001001"
down_revision = "github002001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "patch_proposals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("directive_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PROPOSED"),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("files_changed", sa.JSON(), nullable=True),
        sa.Column("unified_diff", sa.Text(), nullable=True),
        sa.Column("proposed_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("proposed_by_agent_role", sa.String(length=32), nullable=True),
        sa.Column("accepted_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["accepted_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["directive_id"], ["directives.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["proposed_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["rejected_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_patch_proposals_project_id"), "patch_proposals", ["project_id"], unique=False)
    op.create_index(op.f("ix_patch_proposals_directive_id"), "patch_proposals", ["directive_id"], unique=False)
    op.create_index("ix_patch_proposals_status", "patch_proposals", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_patch_proposals_status", table_name="patch_proposals")
    op.drop_index(op.f("ix_patch_proposals_directive_id"), table_name="patch_proposals")
    op.drop_index(op.f("ix_patch_proposals_project_id"), table_name="patch_proposals")
    op.drop_table("patch_proposals")
