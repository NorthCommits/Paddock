"""who is on a page, and page chat messages

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-29 23:30:00
"""

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "page_presence",
        sa.Column("page_id", sa.Uuid(), sa.ForeignKey("pages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("page_id", "user_id"),
    )
    op.create_table(
        "page_messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("page_id", sa.Uuid(), sa.ForeignKey("pages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sender_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("recipient_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_page_messages_page_created", "page_messages", ["page_id", "created_at"])
    op.create_index("ix_page_messages_recipient_id", "page_messages", ["recipient_id"])


def downgrade() -> None:
    op.drop_table("page_messages")
    op.drop_table("page_presence")
