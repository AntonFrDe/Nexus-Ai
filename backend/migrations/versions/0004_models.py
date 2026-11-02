"""Encrypted secrets, providers and models.

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "secrets",
        sa.Column("name", sa.String(120), primary_key=True),
        sa.Column("ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "providers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column("name", sa.String(120), nullable=False, unique=True),
        sa.Column("endpoint", sa.String(500), nullable=True),
        sa.Column("secret_name", sa.String(120), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("timeout_seconds", sa.Float(), nullable=False),
        sa.Column("rate_limit_rpm", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "models",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "provider_id",
            sa.String(36),
            sa.ForeignKey("providers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("model_id", sa.String(200), nullable=False),
        sa.Column("context_window", sa.Integer(), nullable=True),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Column("capability_overrides", sa.JSON(), nullable=False),
        sa.Column("input_cost_per_mtok", sa.Float(), nullable=True),
        sa.Column("output_cost_per_mtok", sa.Float(), nullable=True),
        sa.Column("defaults", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("last_test", sa.JSON(), nullable=True),
        sa.UniqueConstraint("provider_id", "model_id"),
    )


def downgrade() -> None:
    op.drop_table("models")
    op.drop_table("providers")
    op.drop_table("secrets")
