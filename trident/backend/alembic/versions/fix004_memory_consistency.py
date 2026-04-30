"""FIX 004 — memory_sequence, vector lifecycle, sequence anchor.

Revision ID: fix004001
Revises: 100d003
Create Date: 2026-04-30

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "fix004001"
down_revision = "100d003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "memory_sequence_anchor",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("next_sequence", sa.BigInteger(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(sa.text("INSERT INTO memory_sequence_anchor (id, next_sequence) VALUES (1, 0)"))

    op.add_column("memory_entries", sa.Column("memory_sequence", sa.BigInteger(), nullable=True))
    op.add_column(
        "memory_entries",
        sa.Column("vector_state", sa.String(length=32), nullable=True),
    )
    op.add_column("memory_entries", sa.Column("vector_last_error", sa.Text(), nullable=True))
    op.add_column(
        "memory_entries",
        sa.Column("vector_indexed_at", sa.DateTime(timezone=True), nullable=True),
    )

    bind = op.get_bind()

    rows = bind.execute(sa.text("SELECT id FROM memory_entries ORDER BY created_at, id")).fetchall()
    for i, row in enumerate(rows, start=1):
        bind.execute(
            sa.text("UPDATE memory_entries SET memory_sequence = :seq WHERE id = :id"),
            {"seq": i, "id": row[0]},
        )

    bind.execute(
        sa.text(
            """
            UPDATE memory_entries SET vector_state = CASE
                WHEN chroma_document_id IS NOT NULL THEN 'VECTOR_INDEXED'
                ELSE 'VECTOR_FAILED'
            END
            """
        )
    )
    bind.execute(
        sa.text(
            "UPDATE memory_entries SET vector_indexed_at = created_at WHERE vector_state = 'VECTOR_INDEXED'"
        )
    )

    op.alter_column(
        "memory_entries",
        "memory_sequence",
        existing_type=sa.BigInteger(),
        nullable=False,
    )
    op.alter_column(
        "memory_entries",
        "vector_state",
        existing_type=sa.String(length=32),
        nullable=False,
    )

    mx = bind.execute(sa.text("SELECT COALESCE(MAX(memory_sequence), 0) FROM memory_entries")).scalar()
    mx = int(mx or 0)
    bind.execute(
        sa.text("UPDATE memory_sequence_anchor SET next_sequence = :mx WHERE id = 1"),
        {"mx": mx},
    )

    op.create_index(
        "ix_memory_entries_directive_sequence",
        "memory_entries",
        ["directive_id", "memory_sequence"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_memory_entries_directive_sequence", table_name="memory_entries")
    op.drop_column("memory_entries", "vector_indexed_at")
    op.drop_column("memory_entries", "vector_last_error")
    op.drop_column("memory_entries", "vector_state")
    op.drop_column("memory_entries", "memory_sequence")
    op.drop_table("memory_sequence_anchor")
