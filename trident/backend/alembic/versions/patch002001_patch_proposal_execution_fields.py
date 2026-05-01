"""PATCH_002 — execution metadata columns on patch_proposals.

Revision ID: patch002001
Revises: patch001001
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "patch002001"
down_revision = "patch001001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("patch_proposals", sa.Column("execution_status", sa.String(length=32), nullable=False, server_default="NOT_EXECUTED"))
    op.add_column("patch_proposals", sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("patch_proposals", sa.Column("executed_by_user_id", sa.Uuid(), nullable=True))
    op.add_column("patch_proposals", sa.Column("execution_commit_sha", sa.String(length=64), nullable=True))
    op.add_column("patch_proposals", sa.Column("execution_branch_name", sa.String(length=255), nullable=True))
    op.add_column("patch_proposals", sa.Column("execution_proof_object_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_patch_proposals_executed_by",
        "patch_proposals", "users",
        ["executed_by_user_id"], ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_patch_proposals_executed_by", "patch_proposals", type_="foreignkey")
    op.drop_column("patch_proposals", "execution_proof_object_id")
    op.drop_column("patch_proposals", "execution_branch_name")
    op.drop_column("patch_proposals", "execution_commit_sha")
    op.drop_column("patch_proposals", "executed_by_user_id")
    op.drop_column("patch_proposals", "executed_at")
    op.drop_column("patch_proposals", "execution_status")
