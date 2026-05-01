"""STATE_001 — state_transition_log, project_gates, blueprint-aligned enums (additive).

Revision ID: state001001
Revises: fix003001
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "state001001"
down_revision = "fix003001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "state_transition_log",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("directive_id", sa.Uuid(), nullable=True),
        sa.Column("from_state", sa.String(length=64), nullable=True),
        sa.Column("to_state", sa.String(length=64), nullable=False),
        sa.Column("actor_type", sa.String(length=16), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("correlation_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["directive_id"], ["directives.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_state_transition_log_directive_id"), "state_transition_log", ["directive_id"], unique=False)
    op.create_index(op.f("ix_state_transition_log_correlation_id"), "state_transition_log", ["correlation_id"], unique=False)

    op.create_table(
        "project_gates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("gate_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("approved_by", sa.Uuid(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("waiver_flag", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("waiver_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "gate_type", name="uq_project_gates_project_gate_type"),
    )
    op.create_index(op.f("ix_project_gates_project_id"), "project_gates", ["project_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_project_gates_project_id"), table_name="project_gates")
    op.drop_table("project_gates")
    op.drop_index(op.f("ix_state_transition_log_correlation_id"), table_name="state_transition_log")
    op.drop_index(op.f("ix_state_transition_log_directive_id"), table_name="state_transition_log")
    op.drop_table("state_transition_log")
