"""Agents, runtime configuration, and model usage on executions.

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("template", sa.String(64), nullable=True),
        sa.Column("definition", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "agent_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "agent_id",
            sa.String(36),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("definition", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("agent_id", "number"),
    )
    op.create_table(
        "runtime_configs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("secret_name", sa.String(120), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
    )
    with op.batch_alter_table("executions") as batch:
        batch.add_column(
            sa.Column("allow_paid", sa.Boolean(), nullable=False, server_default=sa.false())
        )
    with op.batch_alter_table("node_executions") as batch:
        batch.add_column(sa.Column("usage", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("node_executions") as batch:
        batch.drop_column("usage")
    with op.batch_alter_table("executions") as batch:
        batch.drop_column("allow_paid")
    op.drop_table("runtime_configs")
    op.drop_table("agent_versions")
    op.drop_table("agents")
