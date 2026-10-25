"""pages and versions

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-25 09:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "blobs",
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("storage_key", sa.String(length=200), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("ref_count", sa.Integer(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("sha256", name=op.f("pk_blobs")),
    )
    op.create_table(
        "pages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=60), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("visibility", sa.String(length=10), server_default="private", nullable=False),
        sa.Column("current_version_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], name=op.f("fk_pages_owner_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pages")),
    )
    op.create_index(
        "uq_pages_owner_id_slug_live",
        "pages",
        ["owner_id", "slug"],
        unique=True,
        postgresql_where=sa.text("deleted_at is null"),
    )
    op.create_table(
        "page_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("page_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("message", sa.String(length=500), nullable=True),
        sa.Column("author_user_id", sa.Uuid(), nullable=True),
        sa.Column("author_token_id", sa.Uuid(), nullable=True),
        sa.Column("entry_path", sa.String(length=200), nullable=False),
        sa.Column("total_bytes", sa.BigInteger(), nullable=False),
        sa.Column("file_count", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("rolled_back_from", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["author_user_id"],
            ["users.id"],
            name=op.f("fk_page_versions_author_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["page_id"],
            ["pages.id"],
            name=op.f("fk_page_versions_page_id_pages"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["rolled_back_from"],
            ["page_versions.id"],
            name=op.f("fk_page_versions_rolled_back_from_page_versions"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_page_versions")),
        sa.UniqueConstraint("page_id", "number", name="uq_page_versions_page_id_number"),
    )
    op.create_foreign_key(
        "fk_pages_current_version_id_page_versions",
        "pages",
        "page_versions",
        ["current_version_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_table(
        "version_files",
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("path", sa.String(length=200), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.ForeignKeyConstraint(
            ["sha256"], ["blobs.sha256"], name=op.f("fk_version_files_sha256_blobs")
        ),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["page_versions.id"],
            name=op.f("fk_version_files_version_id_page_versions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("version_id", "path", name="pk_version_files"),
    )


def downgrade() -> None:
    op.drop_table("version_files")
    op.drop_constraint("fk_pages_current_version_id_page_versions", "pages", type_="foreignkey")
    op.drop_table("page_versions")
    op.drop_index("uq_pages_owner_id_slug_live", table_name="pages")
    op.drop_table("pages")
    op.drop_table("blobs")
