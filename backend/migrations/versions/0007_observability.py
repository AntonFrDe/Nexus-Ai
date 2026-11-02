"""Step-through runs and replay lineage.

Revision ID: 0007
Revises: 0006
"""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("executions") as batch:
        batch.add_column(
            sa.Column("step_mode", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch.add_column(sa.Column("replay_of", sa.String(36), nullable=True))
        batch.add_column(sa.Column("overrides", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("executions") as batch:
        batch.drop_column("overrides")
        batch.drop_column("replay_of")
        batch.drop_column("step_mode")
