"""whether to email a person when someone asks their agent for a change

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-29 18:30:00
"""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("notify_requests", sa.Boolean(), server_default=sa.true(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("users", "notify_requests")
