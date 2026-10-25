"""Every table is defined here and imported by Alembic.

Tables arrive milestone by milestone (see docs/SDD.md section 13):
accounts first, then pages and versions, sharing, comments, events and webhooks.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _now_column(**kwargs):
    return mapped_column(DateTime(timezone=True), server_default=func.now(), **kwargs)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True)  # always stored lowercase
    handle: Mapped[str] = mapped_column(String(30), unique=True)  # used in page URLs
    display_name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = _now_column()
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EmailToken(Base):
    """A single-use link sent by email: verify an address or reset a password.

    Only a hash of the token is stored, like sessions and API tokens.
    """

    __tablename__ = "email_tokens"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    purpose: Mapped[str] = mapped_column(String(20))  # "verify" or "reset"
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = _now_column()
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_email_tokens_user_id_purpose", "user_id", "purpose"),)


class UserSession(Base):
    """A browser login. Only a hash of the cookie value is stored."""

    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = _now_column()
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = _now_column()
    user_agent: Mapped[str | None] = mapped_column(String(300))
    ip: Mapped[str | None] = mapped_column(String(45))

    __table_args__ = (Index("ix_sessions_user_id", "user_id"),)


class ApiToken(Base):
    """A token an agent uses to call the API. Only a hash of the token is stored."""

    __tablename__ = "api_tokens"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100))
    prefix: Mapped[str] = mapped_column(String(12))  # first characters, safe to display
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    scopes: Mapped[list[str]] = mapped_column(ARRAY(Text))
    created_at: Mapped[datetime] = _now_column()
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_api_tokens_user_id", "user_id"),)


class AuditLog(Base):
    """A record of important actions: sign ups, logins, token changes, and later publishes."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    token_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    action: Mapped[str] = mapped_column(String(60))
    target_type: Mapped[str | None] = mapped_column(String(40))
    target_id: Mapped[str | None] = mapped_column(String(64))
    meta: Mapped[dict | None] = mapped_column("metadata", JSONB)
    ip: Mapped[str | None] = mapped_column(String(45))
    created_at: Mapped[datetime] = _now_column()

    __table_args__ = (Index("ix_audit_log_user_id_created_at", "user_id", "created_at"),)


class Blob(Base):
    """One stored file, identified by its SHA-256. Many versions can share a blob."""

    __tablename__ = "blobs"

    sha256: Mapped[str] = mapped_column(String(64), primary_key=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    storage_key: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = _now_column()
    ref_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class Page(Base):
    __tablename__ = "pages"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    slug: Mapped[str] = mapped_column(String(60))
    title: Mapped[str] = mapped_column(String(200))
    visibility: Mapped[str] = mapped_column(String(10), default="private", server_default="private")
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(
            "page_versions.id",
            use_alter=True,
            name="fk_pages_current_version_id_page_versions",
            ondelete="SET NULL",
        )
    )
    created_at: Mapped[datetime] = _now_column()
    updated_at: Mapped[datetime] = _now_column(onupdate=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        # A slug is unique per owner, but a deleted page frees its slug.
        Index(
            "uq_pages_owner_id_slug_live",
            "owner_id",
            "slug",
            unique=True,
            postgresql_where=text("deleted_at is null"),
        ),
    )


class PageVersion(Base):
    """An immutable snapshot of a page. Numbers go 1, 2, 3 and never change."""

    __tablename__ = "page_versions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    page_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pages.id", ondelete="CASCADE"))
    number: Mapped[int] = mapped_column(Integer)
    message: Mapped[str | None] = mapped_column(String(500))
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    author_token_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    entry_path: Mapped[str] = mapped_column(String(200))
    total_bytes: Mapped[int] = mapped_column(BigInteger)
    file_count: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String(64))  # fingerprint of the file set
    rolled_back_from: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("page_versions.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = _now_column()

    __table_args__ = (
        UniqueConstraint("page_id", "number", name="uq_page_versions_page_id_number"),
    )


class VersionFile(Base):
    __tablename__ = "version_files"

    version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("page_versions.id", ondelete="CASCADE")
    )
    path: Mapped[str] = mapped_column(String(200))
    sha256: Mapped[str] = mapped_column(ForeignKey("blobs.sha256"))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    content_type: Mapped[str] = mapped_column(String(100))

    __table_args__ = (PrimaryKeyConstraint("version_id", "path", name="pk_version_files"),)
