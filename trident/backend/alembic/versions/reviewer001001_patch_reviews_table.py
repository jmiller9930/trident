"""AGENT_REVIEWER_001 — patch_reviews table for governed Reviewer agent records.

Revision ID: reviewer001001
Revises: signoff001001
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "reviewer001001"
down_revision = "signoff001001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "patch_reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("directive_id", sa.Uuid(), nullable=False),
        sa.Column("patch_id", sa.Uuid(), nullable=False),
        sa.Column("reviewer_agent_role", sa.String(length=32), nullable=False),
        sa.Column("recommendation", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("summary", sa.String(length=4096), nullable=True),
        sa.Column("findings_json", sa.JSON(), nullable=True),
        sa.Column("model_routing_trace_json", sa.JSON(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["directive_id"], ["directives.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["patch_id"], ["patch_proposals.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_patch_reviews_project_id"), "patch_reviews", ["project_id"], unique=False)
    op.create_index(op.f("ix_patch_reviews_directive_id"), "patch_reviews", ["directive_id"], unique=False)
    op.create_index(op.f("ix_patch_reviews_patch_id"), "patch_reviews", ["patch_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_patch_reviews_patch_id"), table_name="patch_reviews")
    op.drop_index(op.f("ix_patch_reviews_directive_id"), table_name="patch_reviews")
    op.drop_index(op.f("ix_patch_reviews_project_id"), table_name="patch_reviews")
    op.drop_table("patch_reviews")
