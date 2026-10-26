"""sign in moves to Neon Auth

Our own passwords, browser sessions and email links are replaced by Neon Auth.
Existing accounts are removed (development data only), then users get a Neon Auth id.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-26 22:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("truncate table users cascade")
    op.drop_table("email_tokens")
    op.drop_table("sessions")
    op.drop_column("users", "password_hash")
    op.add_column("users", sa.Column("neon_auth_id", sa.String(length=100), nullable=False))
    op.create_unique_constraint("uq_users_neon_auth_id", "users", ["neon_auth_id"])


def downgrade() -> None:
    """Restores the old table shapes so older migrations can be undone. No data comes back."""
    op.drop_constraint("uq_users_neon_auth_id", "users", type_="unique")
    op.drop_column("users", "neon_auth_id")
    op.add_column("users", sa.Column("password_hash", sa.Text(), nullable=False, server_default=""))
    op.alter_column("users", "password_hash", server_default=None)
    op.create_table(
        "sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("user_agent", sa.String(length=300), nullable=True),
        sa.Column("ip", sa.String(length=45), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"], unique=False)
    op.create_table(
        "email_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.String(length=20), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_email_tokens_user_id_purpose", "email_tokens", ["user_id", "purpose"])
