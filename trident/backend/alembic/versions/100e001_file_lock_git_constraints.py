"""100E — file_locks NOT NULL + partial unique active lock.

Revision ID: 100e001
Revises: fix004001
Create Date: 2026-04-30

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "100e001"
down_revision = "fix004001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "DELETE FROM file_locks WHERE directive_id IS NULL OR locked_by_user_id IS NULL"
        )
    )
    op.alter_column(
        "file_locks",
        "directive_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )
    op.alter_column(
        "file_locks",
        "locked_by_user_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )
    bind.execute(
        sa.text(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_file_locks_active_project_path
            ON file_locks (project_id, file_path)
            WHERE lock_status = 'ACTIVE' AND released_at IS NULL
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DROP INDEX IF EXISTS uq_file_locks_active_project_path"))
    op.alter_column(
        "file_locks",
        "locked_by_user_id",
        existing_type=sa.Uuid(),
        nullable=True,
    )
    op.alter_column(
        "file_locks",
        "directive_id",
        existing_type=sa.Uuid(),
        nullable=True,
    )
