"""Every table is defined here and imported by Alembic.

Tables arrive milestone by milestone (see docs/SDD.md section 13):
accounts first, then pages and versions, sharing, comments, events and webhooks.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
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
    neon_auth_id: Mapped[str] = mapped_column(String(100), unique=True)  # Neon Auth user id
    created_at: Mapped[datetime] = _now_column()
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # The colour theme the person chose: "system" follows the device, or "light" or "dark".
    theme: Mapped[str] = mapped_column(String(10), default="system", server_default="system")
    # Email this person when someone asks their agent for a change on one of their pages.
    notify_requests: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


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
    # Set when a person approved an app through the sign-in flow ("oauth"), else "manual".
    client_id: Mapped[str | None] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(10), default="manual", server_default="manual")

    __table_args__ = (Index("ix_api_tokens_user_id", "user_id"),)


class OAuthClient(Base):
    """An app (Claude, ChatGPT, Codex...) that registered itself to connect through sign-in."""

    __tablename__ = "oauth_clients"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    client_id: Mapped[str] = mapped_column(String(64), unique=True)
    client_name: Mapped[str] = mapped_column(String(100))
    redirect_uris: Mapped[list[str]] = mapped_column(ARRAY(Text))
    created_at: Mapped[datetime] = _now_column()
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OAuthCode(Base):
    """A single-use code handed to an app after a person clicks Allow. Only a hash is stored."""

    __tablename__ = "oauth_codes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code_hash: Mapped[str] = mapped_column(String(64), unique=True)
    client_id: Mapped[str] = mapped_column(String(64))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    redirect_uri: Mapped[str] = mapped_column(Text)
    code_challenge: Mapped[str] = mapped_column(String(128))
    scopes: Mapped[list[str]] = mapped_column(ARRAY(Text))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # The token this code produced, so that using the code twice can revoke it.
    token_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    created_at: Mapped[datetime] = _now_column()

    __table_args__ = (Index("ix_oauth_codes_expires_at", "expires_at"),)


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


class PageMember(Base):
    """A person who was given access to someone else's page."""

    __tablename__ = "page_members"

    page_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pages.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(20))  # viewer, commenter or editor
    invited_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = _now_column()

    __table_args__ = (
        PrimaryKeyConstraint("page_id", "user_id"),
        Index("ix_page_members_user_id", "user_id"),
    )


class PageInvite(Base):
    """An invitation sent to an email address. Only a hash of the token is stored."""

    __tablename__ = "page_invites"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    page_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pages.id", ondelete="CASCADE"))
    email: Mapped[str] = mapped_column(String(320))  # lowercase
    role: Mapped[str] = mapped_column(String(20))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    invited_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = _now_column()
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_page_invites_page_id", "page_id"),)


class ShareLink(Base):
    """A secret link that lets anyone who holds it open the page. Never grants editing."""

    __tablename__ = "share_links"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    page_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pages.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    role: Mapped[str] = mapped_column(String(20))  # viewer or commenter
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = _now_column()
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_share_links_page_id", "page_id"),)


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


class Comment(Base):
    """A comment on a page, or a reply (parent_id points at the first comment of its thread)."""

    __tablename__ = "comments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    page_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pages.id", ondelete="CASCADE"))
    version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("page_versions.id", ondelete="SET NULL")
    )  # the version the author was looking at
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("comments.id", ondelete="CASCADE")
    )
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    author_token_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)  # set when an agent wrote it
    body: Mapped[str] = mapped_column(Text)
    anchor: Mapped[dict | None] = mapped_column(JSONB)  # stored as sent, never interpreted
    mentions_agent: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = _now_column()
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    __table_args__ = (
        Index("ix_comments_page_id_created_at", "page_id", "created_at"),
        Index("ix_comments_parent_id", "parent_id"),
    )


class RevisionRequest(Base):
    """What an @agent mention turns into: work for an agent to pick up (SDD section 5.4)."""

    __tablename__ = "revision_requests"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    page_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pages.id", ondelete="CASCADE"))
    comment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("comments.id", ondelete="CASCADE"))
    requested_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    base_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("page_versions.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(10), default="open", server_default="open")
    claimed_by_token_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    claim_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("page_versions.id", ondelete="SET NULL")
    )
    dismiss_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _now_column()
    updated_at: Mapped[datetime] = _now_column(onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("comment_id", name="uq_revision_requests_comment_id"),
        Index("ix_revision_requests_page_id_status", "page_id", "status"),
    )


class Event(Base):
    """An append-only record of something that happened. Streams replay from it."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    page_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("pages.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )  # the owner
    type: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = _now_column()

    __table_args__ = (
        Index("ix_events_user_id_id", "user_id", "id"),
        Index("ix_events_page_id_id", "page_id", "id"),
    )


class Webhook(Base):
    """A server address that Paddock calls with each matching event."""

    __tablename__ = "webhooks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    url: Mapped[str] = mapped_column(Text)
    secret_enc: Mapped[str] = mapped_column(Text)  # encrypted, the signing secret
    event_types: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)  # empty means all
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = _now_column()

    __table_args__ = (Index("ix_webhooks_user_id", "user_id"),)


class WebhookDelivery(Base):
    """One event owed to one webhook. The worker sends it and retries on failure."""

    __tablename__ = "webhook_deliveries"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    webhook_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("webhooks.id", ondelete="CASCADE"))
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(10), default="pending")  # pending, delivered, failed
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_status_code: Mapped[int | None] = mapped_column(Integer)
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _now_column()

    __table_args__ = (
        Index("ix_webhook_deliveries_status_next", "status", "next_attempt_at"),
        Index("ix_webhook_deliveries_webhook_id", "webhook_id"),
    )
