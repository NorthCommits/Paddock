"""Webhooks: Paddock calls your server with each matching event (SDD section 6.5).

Every call is signed so the receiver knows it came from Paddock. A worker sends them and retries
failures with growing waits. It sleeps until something is due, so an idle service does not keep the
database awake.
"""

import asyncio
import base64
import hashlib
import hmac
import ipaddress
import json
import logging
import secrets
import socket
import time
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

import httpx
from cryptography.fernet import Fernet
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.db.models import Event, Webhook, WebhookDelivery
from app.db.session import get_sessionmaker
from app.services import audit

log = logging.getLogger("paddock.webhooks")

MAX_WEBHOOKS = 10
RETRY_WAITS = (60, 300, 1800, 7200, 21600)  # seconds between attempts, so 6 attempts in all
SEND_TIMEOUT = 10
BATCH = 10


def _now() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------- secrets and signing


def _fernet() -> Fernet:
    key = hashlib.sha256(("webhooks:" + get_settings().secret_key).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def new_secret() -> str:
    return "whsec_" + secrets.token_urlsafe(24)


def lock_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode()).decode()


def open_secret(stored: str) -> str:
    return _fernet().decrypt(stored.encode()).decode()


def sign(secret: str, timestamp: str, body: bytes) -> str:
    """The receiver computes the same HMAC over `timestamp.body` and compares."""
    mac = hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256)
    return "v1=" + mac.hexdigest()


# ---------------------------------------------------------------- where we may call


async def addresses(host: str) -> list[str]:
    """Every address the host name points to. Replaced in tests."""
    try:
        infos = await asyncio.to_thread(socket.getaddrinfo, host, None, proto=socket.IPPROTO_TCP)
    except OSError:
        return []
    return sorted({info[4][0] for info in infos})


async def check_url(url: str) -> str:
    """Refuse anything that could reach Paddock's own network (server-side request forgery)."""
    parts = urlparse(url.strip())
    production = get_settings().environment == "production"
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise AppError(
            422, "validation_failed", "Use a full web address such as https://example.com/hook"
        )
    if production and parts.scheme != "https":
        raise AppError(422, "validation_failed", "Use an https address")
    if parts.username or parts.password:
        raise AppError(
            422, "validation_failed", "Leave the user name and password out of the address"
        )
    if get_settings().webhook_allow_private:
        return url.strip()
    found = await addresses(parts.hostname)
    if not found:
        raise AppError(422, "validation_failed", "Paddock cannot find that host name")
    for text in found:
        if not ipaddress.ip_address(text).is_global:
            raise AppError(
                422, "validation_failed", "That address points to a private or internal network"
            )
    return url.strip()


# ---------------------------------------------------------------- sending


def make_client() -> httpx.AsyncClient:
    """No redirects, since the target could point somewhere private. Replaced in tests."""
    return httpx.AsyncClient(timeout=SEND_TIMEOUT, follow_redirects=False)


async def attempt(db: AsyncSession, delivery: WebhookDelivery) -> None:
    """Send one delivery and record what happened. The caller commits."""
    hook = await db.get(Webhook, delivery.webhook_id)
    row = await db.get(Event, delivery.event_id)
    delivery.attempts += 1
    error = None
    code = None
    if hook is None or not hook.active:
        error = "The webhook is off"
    else:
        try:
            await check_url(hook.url)
            body = json.dumps(
                {
                    "id": row.id,
                    "type": row.type,
                    "page_id": str(row.page_id) if row.page_id else None,
                    "created_at": row.created_at.isoformat(),
                    "data": row.payload,
                }
            ).encode()
            stamp = str(int(time.time()))
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "Paddock-Webhooks/1",
                "X-Paddock-Event": row.type,
                "X-Paddock-Delivery": str(delivery.id),
                "X-Paddock-Timestamp": stamp,
                "X-Paddock-Signature": sign(open_secret(hook.secret_enc), stamp, body),
            }
            async with make_client() as client:
                res = await client.post(hook.url, content=body, headers=headers)
            code = res.status_code
            if not 200 <= code < 300:
                error = f"The server answered {code}"
        except AppError as err:
            error = err.message
        except httpx.HTTPError as err:
            error = f"{type(err).__name__}: {err}"[:300]

    delivery.last_status_code = code
    delivery.last_error = error
    if error is None:
        delivery.status = "delivered"
        delivery.next_attempt_at = None
    elif hook is None or not hook.active or delivery.attempts > len(RETRY_WAITS):
        delivery.status = "failed"
        delivery.next_attempt_at = None
    else:
        delivery.next_attempt_at = _now() + timedelta(seconds=RETRY_WAITS[delivery.attempts - 1])


async def process_due() -> int:
    """Send everything that is due. Returns how many were tried."""
    tried = 0
    while True:
        async with get_sessionmaker()() as db:
            rows = list(
                await db.scalars(
                    select(WebhookDelivery)
                    .where(
                        WebhookDelivery.status == "pending",
                        WebhookDelivery.next_attempt_at <= _now(),
                    )
                    .order_by(WebhookDelivery.next_attempt_at)
                    .limit(BATCH)
                    .with_for_update(skip_locked=True)
                )
            )
            for delivery in rows:
                await attempt(db, delivery)
            await db.commit()
        tried += len(rows)
        if len(rows) < BATCH:
            return tried


async def seconds_until_next() -> float | None:
    async with get_sessionmaker()() as db:
        soonest = await db.scalar(
            select(func.min(WebhookDelivery.next_attempt_at)).where(
                WebhookDelivery.status == "pending"
            )
        )
    if soonest is None:
        return None
    return max(0.0, (soonest - _now()).total_seconds())


class Worker:
    """Sleeps until a delivery is due or a new one is saved, then sends what is due."""

    def __init__(self) -> None:
        self.wake = asyncio.Event()
        self.task: asyncio.Task | None = None

    def kick(self) -> None:
        self.wake.set()

    def start(self) -> None:
        if self.task is None:
            self.task = asyncio.create_task(self.run())

    async def stop(self) -> None:
        if self.task:
            self.task.cancel()
            self.task = None

    async def run(self) -> None:
        wait: float | None = 0  # look once at start, in case deliveries were left pending
        while True:
            try:
                await asyncio.wait_for(self.wake.wait(), wait)
            except TimeoutError:
                pass
            self.wake.clear()
            try:
                await process_due()
                wait = await seconds_until_next()
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("Webhook worker failed, trying again in a minute")
                wait = 60


worker = Worker()


# ---------------------------------------------------------------- managing webhooks


async def create(
    db: AsyncSession, actor, *, url: str, event_types: list[str], ip: str | None
) -> tuple[Webhook, str]:
    count = await db.scalar(
        select(func.count()).select_from(Webhook).where(Webhook.user_id == actor.user.id)
    )
    if count >= MAX_WEBHOOKS:
        raise AppError(409, "conflict", f"You can have up to {MAX_WEBHOOKS} webhooks")
    secret = new_secret()
    hook = Webhook(
        user_id=actor.user.id,
        url=await check_url(url),
        secret_enc=lock_secret(secret),
        event_types=sorted(set(event_types)),
        active=True,
    )
    db.add(hook)
    await db.flush()
    audit.record(
        db,
        action="webhook.create",
        user_id=actor.user.id,
        token_id=actor.token.id if actor.token else None,
        target_type="webhook",
        target_id=str(hook.id),
        ip=ip,
    )
    await db.commit()
    await db.refresh(hook)
    return hook, secret


async def mine(db: AsyncSession, actor, hook_id: uuid.UUID) -> Webhook:
    hook = await db.get(Webhook, hook_id)
    if hook is None or hook.user_id != actor.user.id:
        raise AppError(404, "not_found", "Webhook not found")
    return hook


async def remove(db: AsyncSession, actor, hook_id: uuid.UUID, ip: str | None) -> None:
    hook = await mine(db, actor, hook_id)
    await db.delete(hook)
    audit.record(
        db,
        action="webhook.delete",
        user_id=actor.user.id,
        token_id=actor.token.id if actor.token else None,
        target_type="webhook",
        target_id=str(hook_id),
        ip=ip,
    )
    await db.commit()


async def send_test(db: AsyncSession, actor, hook_id: uuid.UUID) -> WebhookDelivery:
    """Send a test event right now and report what the receiver answered."""
    hook = await mine(db, actor, hook_id)
    row = Event(
        page_id=None,
        user_id=actor.user.id,
        type="webhook.test",
        payload={"webhook_id": str(hook.id)},
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)
    delivery = WebhookDelivery(webhook_id=hook.id, event_id=row.id, next_attempt_at=_now())
    db.add(delivery)
    await db.flush()
    await attempt(db, delivery)
    if delivery.status == "pending":  # a test is tried once, it does not retry
        delivery.status = "failed"
        delivery.next_attempt_at = None
    await db.commit()
    await db.refresh(delivery)
    return delivery
