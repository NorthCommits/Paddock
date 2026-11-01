"""read markers for page chat

Revision ID: 0015
Revises: 0014
Create Date: 2026-11-01 23:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_reads",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("page_id", sa.Uuid(), sa.ForeignKey("pages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation", sa.String(40), nullable=False),
        sa.Column("up_to", sa.DateTime(timezone=True), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("page_id", "user_id", "conversation", name="uq_chat_reads_one"),
    )


def downgrade() -> None:
    op.drop_table("chat_reads")
