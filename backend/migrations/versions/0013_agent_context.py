"""request briefs and the page context note

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-30 15:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("revision_requests", sa.Column("brief", sa.Text()))
    op.add_column("pages", sa.Column("context_note", sa.Text()))
    op.add_column("pages", sa.Column("context_updated_at", sa.DateTime(timezone=True)))


def downgrade() -> None:
    op.drop_column("pages", "context_updated_at")
    op.drop_column("pages", "context_note")
    op.drop_column("revision_requests", "brief")
