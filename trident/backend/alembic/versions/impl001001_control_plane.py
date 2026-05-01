"""TRIDENT_IMPLEMENTATION_DIRECTIVE_001 — auth passwords, project_members, project_invites.

Revision ID: impl001001
Revises: state001001
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "impl001001"
down_revision = "state001001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_hash", sa.Text(), nullable=True))

    op.create_table(
        "project_members",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "user_id", name="uq_project_members_project_user"),
    )
    op.create_index(op.f("ix_project_members_project_id"), "project_members", ["project_id"], unique=False)
    op.create_index(op.f("ix_project_members_user_id"), "project_members", ["user_id"], unique=False)

    op.create_table(
        "project_invites",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=512), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("token", sa.Uuid(), nullable=False),
        sa.Column("invited_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["invited_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_project_invites_email"), "project_invites", ["email"], unique=False)
    op.create_index(op.f("ix_project_invites_project_id"), "project_invites", ["project_id"], unique=False)
    op.create_index(op.f("ix_project_invites_token"), "project_invites", ["token"], unique=True)

    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            INSERT INTO project_members (id, project_id, user_id, role, created_at)
            SELECT gen_random_uuid(), p.id, w.created_by_user_id, 'OWNER', now()
            FROM projects p
            JOIN workspaces w ON p.workspace_id = w.id
            WHERE NOT EXISTS (SELECT 1 FROM project_members pm WHERE pm.project_id = p.id)
            """
        )
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_project_invites_token"), table_name="project_invites")
    op.drop_index(op.f("ix_project_invites_project_id"), table_name="project_invites")
    op.drop_index(op.f("ix_project_invites_email"), table_name="project_invites")
    op.drop_table("project_invites")
    op.drop_index(op.f("ix_project_members_user_id"), table_name="project_members")
    op.drop_index(op.f("ix_project_members_project_id"), table_name="project_members")
    op.drop_table("project_members")
    op.drop_column("users", "password_hash")
