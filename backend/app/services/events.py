"""Events: what happened, written in the same transaction as the change, then pushed live.

A service calls `emit` before it commits. The event row is saved with the change. When the commit
succeeds, the row is handed to the hub, which pushes it to open streams. A client that was away
asks again with Last-Event-ID and gets what it missed from the table. See SDD section 6.
"""

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from sqlalchemy import and_, any_, event, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.db.models import Event, Page, PageMember, Webhook, WebhookDelivery
from app.db.session import get_sessionmaker
from app.services import webhooks

EVENT_TYPES = (
    "version.published",
    "version.rolled_back",
    "page.updated",
    "page.deleted",
    "comment.created",
    "comment.updated",
    "comment.deleted",
    "comment.resolved",
    "request.created",
    "request.awaiting",
    "request.approved",
    "request.claimed",
    "request.reopened",
    "request.needs_info",
    "request.answered",
    "request.updated",
    "request.completed",
    "request.dismissed",
    "member.added",
    "member.removed",
)
# Only the owner sees who joined or left.
OWNER_ONLY = ("member.added", "member.removed")

PING_SECONDS = 20
MAX_REPLAY = 1000
QUEUE_SIZE = 500


def envelope(row: Event) -> dict:
    return {
        "id": row.id,
        "type": row.type,
        "page_id": str(row.page_id) if row.page_id else None,
        "created_at": row.created_at.isoformat(),
        "data": row.payload,
    }


# ---------------------------------------------------------------- the hub


class Subscription:
    def __init__(self) -> None:
        self.queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=QUEUE_SIZE)
        self.lost = False  # set when the client fell too far behind


class Hub:
    """Pushes events to the streams open in this process. A single instance is enough for v1."""

    def __init__(self) -> None:
        self.subscriptions: set[Subscription] = set()

    def subscribe(self) -> Subscription:
        sub = Subscription()
        self.subscriptions.add(sub)
        return sub

    def unsubscribe(self, sub: Subscription) -> None:
        self.subscriptions.discard(sub)

    def publish(self, item: dict) -> None:
        for sub in list(self.subscriptions):
            try:
                sub.queue.put_nowait(item)
            except asyncio.QueueFull:
                sub.lost = True


hub = Hub()


# ---------------------------------------------------------------- writing


async def emit(db: AsyncSession, page_id: uuid.UUID, type_: str, data: dict) -> Event:
    """Save an event with the change in progress. The caller commits."""
    page = await db.get(Page, page_id)
    row = Event(page_id=page_id, user_id=page.owner_id, type=type_, payload=data)
    db.add(row)
    await db.flush()
    await db.refresh(row)  # loads created_at from the database
    db.info.setdefault("events", []).append({**envelope(row), "owner": str(page.owner_id)})

    hooks = await db.scalars(
        select(Webhook).where(
            Webhook.user_id == page.owner_id,
            Webhook.active.is_(True),
            or_(
                func.cardinality(Webhook.event_types) == 0,
                literal(type_) == any_(Webhook.event_types),
            ),
        )
    )
    for hook in hooks:
        db.add(
            WebhookDelivery(webhook_id=hook.id, event_id=row.id, next_attempt_at=datetime.now(UTC))
        )
        db.info["kick"] = True
    return row


def push(
    page_id: uuid.UUID, type_: str, data: dict, audience: list[uuid.UUID] | None = None
) -> None:
    """Send a live-only event to open page streams. Nothing is stored and webhooks never see it.

    It is for people only: agent streams skip it. With an audience, only those people get it.
    Call it after the change is committed.
    """
    hub.publish(
        {
            "id": None,
            "type": type_,
            "page_id": str(page_id),
            "created_at": datetime.now(UTC).isoformat(),
            "data": data,
            "owner": "",
            "people_only": True,
            "audience": [str(a) for a in audience] if audience else None,
        }
    )


@event.listens_for(Session, "after_commit")
def _publish(session: Session) -> None:
    events = session.info.pop("events", [])
    kick = session.info.pop("kick", False)
    for item in events:
        hub.publish(item)
    if kick:
        webhooks.worker.kick()


@event.listens_for(Session, "after_rollback")
def _forget(session: Session) -> None:
    session.info.pop("events", None)
    session.info.pop("kick", None)


# ---------------------------------------------------------------- reading


async def can_see(user_id: uuid.UUID, page_id: uuid.UUID | None, type_: str) -> bool:
    """Checked for every event, so someone who loses access stops receiving at once."""
    if page_id is None:
        return False
    async with get_sessionmaker()() as db:
        page = await db.get(Page, page_id)
        if page is None:
            return False
        if page.owner_id == user_id:
            return True  # the owner still hears about a deleted page
        if page.deleted_at is not None or page.visibility == "private" or type_ in OWNER_ONLY:
            return False
        return await db.get(PageMember, (page_id, user_id)) is not None


async def replay(user_id: uuid.UUID, page_id: uuid.UUID | None, last_id: int) -> list[dict] | None:
    """Events after last_id that this person may see. None means too many, so refetch instead."""
    owned = select(Page.id).where(Page.owner_id == user_id)
    shared = (
        select(PageMember.page_id)
        .join(Page, Page.id == PageMember.page_id)
        .where(
            PageMember.user_id == user_id,
            Page.visibility != "private",
            Page.deleted_at.is_(None),
        )
    )
    query = select(Event).where(
        Event.id > last_id,
        or_(
            Event.page_id.in_(owned),
            and_(Event.page_id.in_(shared), Event.type.notin_(OWNER_ONLY)),
        ),
    )
    if page_id is not None:
        query = query.where(Event.page_id == page_id)
    async with get_sessionmaker()() as db:
        rows = list(await db.scalars(query.order_by(Event.id).limit(MAX_REPLAY + 1)))
    if len(rows) > MAX_REPLAY:
        return None
    return [envelope(r) for r in rows]


def frame(item: dict) -> str:
    body = {k: v for k, v in item.items() if k not in ("owner", "people_only", "audience")}
    ident = f"id: {item['id']}\n" if item["id"] is not None else ""
    return f"{ident}event: {item['type']}\ndata: {json.dumps(body)}\n\n"


RESYNC = "event: resync\ndata: {}\n\n"


async def stream(
    user_id: uuid.UUID, page_id: uuid.UUID | None, last_id: int | None, person: bool = True
) -> AsyncIterator[str]:
    """Server-sent events for one person, optionally limited to one page."""
    sub = hub.subscribe()  # subscribe first, so nothing is missed while replaying
    try:
        yield ": connected\n\n"
        seen = last_id
        if last_id is not None:
            missed = await replay(user_id, page_id, last_id)
            if missed is None:
                yield RESYNC
                seen = None
            else:
                for item in missed:
                    seen = item["id"]
                    yield frame(item)
        while True:
            if sub.lost:
                yield RESYNC
                return
            try:
                item = await asyncio.wait_for(sub.queue.get(), PING_SECONDS)
            except TimeoutError:
                yield ": ping\n\n"
                continue
            live_only = item["id"] is None  # not stored, so no id to compare or remember
            if live_only and (
                not person or str(user_id) not in (item["audience"] or [str(user_id)])
            ):
                continue
            if not live_only and seen is not None and item["id"] <= seen:
                continue  # already sent during the replay
            if page_id is not None and item["page_id"] != str(page_id):
                continue
            page = uuid.UUID(item["page_id"]) if item["page_id"] else None
            if not await can_see(user_id, page, item["type"]):
                continue
            if not live_only:
                seen = item["id"]
            yield frame(item)
    finally:
        hub.unsubscribe(sub)
