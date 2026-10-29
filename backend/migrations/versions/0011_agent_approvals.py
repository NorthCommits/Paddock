"""ask before a colleague's agent works on a request, with notifications and a wake-up trigger

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-29 21:30:00
"""

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("agent_approval", sa.String(5), server_default="ask", nullable=False)
    )
    op.add_column(
        "revision_requests",
        sa.Column("approved_by_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
    )
    op.add_column(
        "revision_requests", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True)
    )
    # Requests that already exist keep working for the page owner's agent, as before.
    op.execute(
        """
        update revision_requests r
        set approved_by_user_id = p.owner_id, approved_at = r.created_at
        from pages p
        where p.id = r.page_id and r.status in ('open', 'claimed', 'done')
        """
    )
    op.create_table(
        "request_offers",
        sa.Column(
            "request_id",
            sa.Uuid(),
            sa.ForeignKey("revision_requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("status", sa.String(10), server_default="offered", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("request_id", "user_id"),
    )
    op.create_index("ix_request_offers_user_id", "request_offers", ["user_id"])
    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("page_id", sa.Uuid(), sa.ForeignKey("pages.id", ondelete="CASCADE")),
        sa.Column(
            "request_id", sa.Uuid(), sa.ForeignKey("revision_requests.id", ondelete="CASCADE")
        ),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_notifications_user_id_created_at", "notifications", ["user_id", "created_at"]
    )
    op.create_table(
        "agent_triggers",
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("token_enc", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_fired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_result", sa.String(80), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("agent_triggers")
    op.drop_index("ix_notifications_user_id_created_at", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index("ix_request_offers_user_id", table_name="request_offers")
    op.drop_table("request_offers")
    op.drop_column("revision_requests", "approved_at")
    op.drop_column("revision_requests", "approved_by_user_id")
    op.drop_column("users", "agent_approval")
