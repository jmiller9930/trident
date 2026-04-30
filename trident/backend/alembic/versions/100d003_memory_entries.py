"""100D — structured memory_entries table.

Revision ID: 100d003
Revises: 100o002
Create Date: 2026-04-30

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "100d003"
down_revision = "100o002"
branch_labels = None
depends_on = None

_JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "memory_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("directive_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("task_ledger_id", sa.Uuid(), nullable=False),
        sa.Column("agent_role", sa.String(32), nullable=False),
        sa.Column("memory_kind", sa.String(32), nullable=False),
        sa.Column("title", sa.String(512), nullable=True),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("payload_json", _JSON, nullable=False),
        sa.Column("chroma_document_id", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["directive_id"], ["directives.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_ledger_id"], ["task_ledger.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_memory_entries_directive_id"), "memory_entries", ["directive_id"], unique=False)
    op.create_index(op.f("ix_memory_entries_project_id"), "memory_entries", ["project_id"], unique=False)
    op.create_index(op.f("ix_memory_entries_task_ledger_id"), "memory_entries", ["task_ledger_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_memory_entries_task_ledger_id"), table_name="memory_entries")
    op.drop_index(op.f("ix_memory_entries_project_id"), table_name="memory_entries")
    op.drop_index(op.f("ix_memory_entries_directive_id"), table_name="memory_entries")
    op.drop_table("memory_entries")
