"""the colour theme a person chose

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-29 14:30:00
"""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("theme", sa.String(length=10), server_default="system", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("users", "theme")
