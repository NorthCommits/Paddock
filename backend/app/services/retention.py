"""Cleanup that keeps the database and storage from growing without end (SDD section 2.3).

It runs about once a day inside the API process, or on demand with `python -m app.jobs retention`.
Every step is safe to repeat. Counts of what was removed are returned and logged.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    ApiToken,
    AuditLog,
    Blob,
    Event,
    OAuthClient,
    OAuthCode,
    Page,
    PageInvite,
    PageVersion,
    ShareLink,
    VersionFile,
    WebhookDelivery,
)
from app.db.session import get_sessionmaker
from app.services.storage import get_storage

log = logging.getLogger("paddock.retention")

EVENT_DAYS = 30  # events and delivery history
DELETED_PAGE_DAYS = 30  # a deleted page is kept this long, then removed for good
BLOB_DAYS = 7  # a file nobody uses is kept this long, then removed from storage
OLD_ACCESS_DAYS = 30  # invitations and share links that ended
AUDIT_DAYS = 365
OAUTH_CODE_DAYS = 1  # sign-in codes that expired or were used
OAUTH_CLIENT_DAYS = 30  # apps nobody has used and that hold no live token

FIRST_RUN_DELAY = 300  # seconds after start
EVERY = 24 * 60 * 60


def _ago(days: int) -> datetime:
    return datetime.now(UTC) - timedelta(days=days)


async def purge_deleted_pages(db: AsyncSession) -> int:
    """Remove pages deleted long ago, and let go of the files their versions used."""
    ids = list(
        await db.scalars(
            select(Page.id).where(
                Page.deleted_at.is_not(None), Page.deleted_at < _ago(DELETED_PAGE_DAYS)
            )
        )
    )
    if not ids:
        return 0
    # A version counts once for each distinct file it holds (see pages._add_version).
    used = (
        select(VersionFile.sha256, func.count(func.distinct(VersionFile.version_id)).label("n"))
        .join(PageVersion, PageVersion.id == VersionFile.version_id)
        .where(PageVersion.page_id.in_(ids))
        .group_by(VersionFile.sha256)
    )
    for sha, n in (await db.execute(used)).all():
        await db.execute(
            update(Blob).where(Blob.sha256 == sha).values(ref_count=Blob.ref_count - n)
        )
    await db.execute(delete(Page).where(Page.id.in_(ids)))  # versions, comments and so on follow
    await db.commit()
    return len(ids)


async def purge_old_events(db: AsyncSession) -> int:
    """Old events go, except those a webhook still has to deliver. Their deliveries go with them."""
    waiting = select(WebhookDelivery.event_id).where(WebhookDelivery.status == "pending")
    result = await db.execute(
        delete(Event).where(Event.created_at < _ago(EVENT_DAYS), Event.id.not_in(waiting))
    )
    await db.commit()
    return result.rowcount


async def purge_old_access(db: AsyncSession) -> int:
    cutoff = _ago(OLD_ACCESS_DAYS)
    invites = await db.execute(
        delete(PageInvite).where(
            (PageInvite.accepted_at < cutoff) | (PageInvite.expires_at < cutoff)
        )
    )
    links = await db.execute(
        delete(ShareLink).where((ShareLink.revoked_at < cutoff) | (ShareLink.expires_at < cutoff))
    )
    await db.commit()
    return invites.rowcount + links.rowcount


async def purge_audit(db: AsyncSession) -> int:
    result = await db.execute(delete(AuditLog).where(AuditLog.created_at < _ago(AUDIT_DAYS)))
    await db.commit()
    return result.rowcount


async def purge_oauth(db: AsyncSession) -> int:
    """Remove old sign-in codes, and apps that are unused and hold no live token."""
    codes = await db.execute(
        delete(OAuthCode).where(
            (OAuthCode.expires_at < _ago(OAUTH_CODE_DAYS))
            | (OAuthCode.used_at < _ago(OAUTH_CODE_DAYS))
        )
    )
    now = datetime.now(UTC)
    live = select(ApiToken.client_id).where(
        ApiToken.client_id.is_not(None),
        ApiToken.revoked_at.is_(None),
        (ApiToken.expires_at.is_(None)) | (ApiToken.expires_at > now),
    )
    clients = await db.execute(
        delete(OAuthClient).where(
            func.coalesce(OAuthClient.last_used_at, OAuthClient.created_at)
            < _ago(OAUTH_CLIENT_DAYS),
            OAuthClient.client_id.not_in(live),
        )
    )
    await db.commit()
    return codes.rowcount + clients.rowcount


async def purge_unused_blobs(db: AsyncSession) -> int:
    """Delete files no version uses. Rows go first, so a row never points at a missing file."""
    rows = (
        await db.execute(
            select(Blob.sha256)
            .where(Blob.ref_count <= 0, Blob.created_at < _ago(BLOB_DAYS))
            .with_for_update(skip_locked=True)
        )
    ).all()
    shas = [r[0] for r in rows]
    if not shas:
        return 0
    await db.execute(delete(Blob).where(Blob.sha256.in_(shas)))
    await db.commit()
    storage = get_storage()
    removed = 0
    for sha in shas:
        try:
            await storage.delete(sha)
            removed += 1
        except Exception:
            log.exception("Could not delete file %s from storage", sha)
    return removed


async def run() -> dict[str, int]:
    steps = (
        ("pages", purge_deleted_pages),
        ("events", purge_old_events),
        ("access", purge_old_access),
        ("audit", purge_audit),
        ("oauth", purge_oauth),
        ("blobs", purge_unused_blobs),  # after pages, which frees files
    )
    counts: dict[str, int] = {}
    for name, step in steps:
        async with get_sessionmaker()() as db:
            counts[name] = await step(db)
    log.info("Retention removed %s", counts)
    return counts


async def loop() -> None:
    """Run once a day. A failure is logged and tried again the next day."""
    await asyncio.sleep(FIRST_RUN_DELAY)
    while True:
        try:
            await run()
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Retention failed")
        await asyncio.sleep(EVERY)
