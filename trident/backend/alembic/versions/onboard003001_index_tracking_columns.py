"""ONBOARD_003 — index tracking columns on project_onboarding.

Revision ID: onboard003001
Revises: decision001001
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "onboard003001"
down_revision = "decision001001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("project_onboarding", sa.Column("index_status", sa.String(length=32), nullable=False, server_default="NOT_STARTED"))
    op.add_column("project_onboarding", sa.Column("indexed_file_count", sa.Integer(), nullable=True))
    op.add_column("project_onboarding", sa.Column("indexed_chunk_count", sa.Integer(), nullable=True))
    op.add_column("project_onboarding", sa.Column("index_error_safe", sa.Text(), nullable=True))
    op.add_column("project_onboarding", sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("project_onboarding", "indexed_at")
    op.drop_column("project_onboarding", "index_error_safe")
    op.drop_column("project_onboarding", "indexed_chunk_count")
    op.drop_column("project_onboarding", "indexed_file_count")
    op.drop_column("project_onboarding", "index_status")
