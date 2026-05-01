"""SIGNOFF_001 — directives.closed_at + closed_by_user_id for governed closure.

Revision ID: signoff001001
Revises: valid001001
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "signoff001001"
down_revision = "valid001001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("directives", sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("directives", sa.Column("closed_by_user_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_directives_closed_by_user",
        "directives", "users",
        ["closed_by_user_id"], ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_directives_closed_by_user", "directives", type_="foreignkey")
    op.drop_column("directives", "closed_by_user_id")
    op.drop_column("directives", "closed_at")
