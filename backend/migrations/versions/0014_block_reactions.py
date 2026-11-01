"""reactions on parts of a page

Revision ID: 0014
Revises: 0013
Create Date: 2026-11-01 20:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "block_reactions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("page_id", sa.Uuid(), sa.ForeignKey("pages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("block", sa.String(64), nullable=False),
        sa.Column("key", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("page_id", "user_id", "block", "key", name="uq_block_reactions_one"),
    )
    op.create_index("ix_block_reactions_page_id", "block_reactions", ["page_id"])


def downgrade() -> None:
    op.drop_index("ix_block_reactions_page_id", table_name="block_reactions")
    op.drop_table("block_reactions")
