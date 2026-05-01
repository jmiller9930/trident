"""FIX 003 — file_locks.last_heartbeat_at for lock heartbeat / staleness.

Revision ID: fix003001
Revises: 100e001
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "fix003001"
down_revision = "100e001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "file_locks",
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
    )
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE file_locks SET last_heartbeat_at = created_at "
            "WHERE last_heartbeat_at IS NULL"
        )
    )


def downgrade() -> None:
    op.drop_column("file_locks", "last_heartbeat_at")
