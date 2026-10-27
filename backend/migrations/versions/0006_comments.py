"""comments and revision requests

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-27 22:00:00
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

_now = sa.text("now()")


def upgrade() -> None:
    op.create_table(
        "comments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("page_id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=True),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("author_user_id", sa.Uuid(), nullable=True),
        sa.Column("author_token_id", sa.Uuid(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("anchor", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("mentions_agent", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_now, nullable=False),
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["page_id"], ["pages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["version_id"], ["page_versions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["parent_id"], ["comments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["resolved_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_comments_page_id_created_at", "comments", ["page_id", "created_at"])
    op.create_index("ix_comments_parent_id", "comments", ["parent_id"])

    op.create_table(
        "revision_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("page_id", sa.Uuid(), nullable=False),
        sa.Column("comment_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by", sa.Uuid(), nullable=True),
        sa.Column("base_version_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=10), server_default="open", nullable=False),
        sa.Column("claimed_by_token_id", sa.Uuid(), nullable=True),
        sa.Column("claim_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result_version_id", sa.Uuid(), nullable=True),
        sa.Column("dismiss_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_now, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=_now, nullable=False),
        sa.ForeignKeyConstraint(["page_id"], ["pages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["comment_id"], ["comments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["base_version_id"], ["page_versions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["result_version_id"], ["page_versions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("comment_id", name="uq_revision_requests_comment_id"),
    )
    op.create_index(
        "ix_revision_requests_page_id_status", "revision_requests", ["page_id", "status"]
    )


def downgrade() -> None:
    op.drop_index("ix_revision_requests_page_id_status", table_name="revision_requests")
    op.drop_table("revision_requests")
    op.drop_index("ix_comments_parent_id", table_name="comments")
    op.drop_index("ix_comments_page_id_created_at", table_name="comments")
    op.drop_table("comments")
