"""DECISION_ENGINE_001 — decision_records append-only table.

Revision ID: decision001001
Revises: reviewer001001
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "decision001001"
down_revision = "reviewer001001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "decision_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("directive_id", sa.Uuid(), nullable=False),
        sa.Column("patch_id", sa.Uuid(), nullable=True),
        sa.Column("recommendation", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("summary", sa.String(length=4096), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=True),
        sa.Column("blocking_reasons_json", sa.JSON(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["directive_id"], ["directives.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["patch_id"], ["patch_proposals.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_decision_records_project_id"), "decision_records", ["project_id"], unique=False)
    op.create_index(op.f("ix_decision_records_directive_id"), "decision_records", ["directive_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_decision_records_directive_id"), table_name="decision_records")
    op.drop_index(op.f("ix_decision_records_project_id"), table_name="decision_records")
    op.drop_table("decision_records")
