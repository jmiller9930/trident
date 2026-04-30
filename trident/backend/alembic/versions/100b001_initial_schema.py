"""100B — initial persistence schema.

Revision ID: 100b001
Revises:
Create Date: 2026-04-29

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "100b001"
down_revision = None
branch_labels = None
depends_on = None


_JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(512), nullable=False),
        sa.Column("role", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )

    op.create_table(
        "workspaces",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("allowed_root_path", sa.Text(), nullable=False),
        sa.Column("git_remote_url", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "directives",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("graph_id", sa.String(255), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_directives_status"), "directives", ["status"], unique=False)

    op.create_table(
        "task_ledger",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("directive_id", sa.Uuid(), nullable=False),
        sa.Column("current_state", sa.String(32), nullable=False),
        sa.Column("current_agent_role", sa.String(32), nullable=False),
        sa.Column("current_owner_user_id", sa.Uuid(), nullable=True),
        sa.Column("last_transition_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["current_owner_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["directive_id"], ["directives.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("directive_id"),
    )

    op.create_table(
        "graph_states",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("directive_id", sa.Uuid(), nullable=False),
        sa.Column("graph_id", sa.String(255), nullable=False),
        sa.Column("current_node", sa.String(255), nullable=True),
        sa.Column("state_payload_json", _JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["directive_id"], ["directives.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_graph_states_directive_id"), "graph_states", ["directive_id"], unique=False)

    op.create_table(
        "handoffs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("directive_id", sa.Uuid(), nullable=False),
        sa.Column("from_agent_role", sa.String(32), nullable=False),
        sa.Column("to_agent_role", sa.String(32), nullable=False),
        sa.Column("handoff_payload_json", _JSON, nullable=False),
        sa.Column("requires_ack", sa.Boolean(), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["directive_id"], ["directives.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_handoffs_directive_id"), "handoffs", ["directive_id"], unique=False)

    op.create_table(
        "proof_objects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("directive_id", sa.Uuid(), nullable=False),
        sa.Column("proof_type", sa.String(64), nullable=False),
        sa.Column("proof_uri", sa.Text(), nullable=True),
        sa.Column("proof_summary", sa.Text(), nullable=True),
        sa.Column("proof_hash", sa.String(128), nullable=True),
        sa.Column("created_by_agent_role", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["directive_id"], ["directives.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_proof_objects_directive_id"), "proof_objects", ["directive_id"], unique=False)

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=True),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("directive_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("event_payload_json", _JSON, nullable=False),
        sa.Column("actor_type", sa.String(32), nullable=False),
        sa.Column("actor_id", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["directive_id"], ["directives.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_events_directive_id"), "audit_events", ["directive_id"], unique=False)
    op.create_index(op.f("ix_audit_events_event_type"), "audit_events", ["event_type"], unique=False)
    op.create_index(op.f("ix_audit_events_project_id"), "audit_events", ["project_id"], unique=False)
    op.create_index(op.f("ix_audit_events_workspace_id"), "audit_events", ["workspace_id"], unique=False)

    op.create_table(
        "file_locks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("directive_id", sa.Uuid(), nullable=True),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("locked_by_agent_role", sa.String(32), nullable=False),
        sa.Column("locked_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("lock_status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["directive_id"], ["directives.id"]),
        sa.ForeignKeyConstraint(["locked_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_file_locks_directive_id"), "file_locks", ["directive_id"], unique=False)
    op.create_index(op.f("ix_file_locks_project_id"), "file_locks", ["project_id"], unique=False)


def downgrade() -> None:
    op.drop_table("file_locks")
    op.drop_table("audit_events")
    op.drop_table("proof_objects")
    op.drop_table("handoffs")
    op.drop_table("graph_states")
    op.drop_table("task_ledger")
    op.drop_table("directives")
    op.drop_table("projects")
    op.drop_table("workspaces")
    op.drop_table("users")
