"""100O — Nike event orchestration tables.

Revision ID: 100o002
Revises: 100b001
Create Date: 2026-04-30

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "100o002"
down_revision = "100b001"
branch_labels = None
depends_on = None

_JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "nike_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(128), nullable=False),
        sa.Column("source", sa.String(128), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=True),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("directive_id", sa.Uuid(), nullable=True),
        sa.Column("task_id", sa.Uuid(), nullable=True),
        sa.Column("correlation_id", sa.Uuid(), nullable=True),
        sa.Column("payload_json", _JSON, nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id"),
    )
    op.create_index(op.f("ix_nike_events_correlation_id"), "nike_events", ["correlation_id"], unique=False)
    op.create_index(op.f("ix_nike_events_directive_id"), "nike_events", ["directive_id"], unique=False)
    op.create_index(op.f("ix_nike_events_event_type"), "nike_events", ["event_type"], unique=False)
    op.create_index(op.f("ix_nike_events_project_id"), "nike_events", ["project_id"], unique=False)
    op.create_index(op.f("ix_nike_events_status"), "nike_events", ["status"], unique=False)
    op.create_index(op.f("ix_nike_events_task_id"), "nike_events", ["task_id"], unique=False)
    op.create_index(op.f("ix_nike_events_workspace_id"), "nike_events", ["workspace_id"], unique=False)

    op.create_table(
        "nike_event_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_pk", sa.Uuid(), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("error_detail", sa.String(4096), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["event_pk"], ["nike_events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "nike_dead_letter_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_pk", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.String(2048), nullable=False),
        sa.Column("failed_attempt_count", sa.Integer(), nullable=False),
        sa.Column("payload_snapshot_json", _JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["event_pk"], ["nike_events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "nike_notification_outbox",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_pk", sa.Uuid(), nullable=True),
        sa.Column("channel", sa.String(64), nullable=False),
        sa.Column("notification_type", sa.String(128), nullable=False),
        sa.Column("payload_json", _JSON, nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["event_pk"], ["nike_events.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("nike_notification_outbox")
    op.drop_table("nike_dead_letter_events")
    op.drop_table("nike_event_attempts")
    op.drop_index(op.f("ix_nike_events_workspace_id"), table_name="nike_events")
    op.drop_index(op.f("ix_nike_events_task_id"), table_name="nike_events")
    op.drop_index(op.f("ix_nike_events_status"), table_name="nike_events")
    op.drop_index(op.f("ix_nike_events_project_id"), table_name="nike_events")
    op.drop_index(op.f("ix_nike_events_event_type"), table_name="nike_events")
    op.drop_index(op.f("ix_nike_events_directive_id"), table_name="nike_events")
    op.drop_index(op.f("ix_nike_events_correlation_id"), table_name="nike_events")
    op.drop_table("nike_events")
