"""What the bell in the app shows. Requests waiting for a person's yes, and news about requests."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Notification, Page, RequestOffer, RevisionRequest, User
from app.schemas.notifications import (
    NotificationItem,
    NotificationList,
    NotificationPage,
    NotificationRequest,
)
from app.services import agents

KEEP = 30  # the bell shows this many, newest first


def add(
    db: AsyncSession,
    user_id: uuid.UUID,
    kind: str,
    *,
    page_id: uuid.UUID,
    request_id: uuid.UUID,
    actor_id: uuid.UUID | None,
    body: str,
) -> None:
    db.add(
        Notification(
            user_id=user_id,
            kind=kind,
            page_id=page_id,
            request_id=request_id,
            actor_id=actor_id,
            body=body[:300],
        )
    )


def _name(user: User | None) -> str:
    if user is None:
        return "Someone"
    return user.display_name or f"@{user.handle}"


async def list_for(db: AsyncSession, user: User) -> NotificationList:
    rows = list(
        await db.scalars(
            select(Notification)
            .where(Notification.user_id == user.id)
            .order_by(Notification.created_at.desc(), Notification.id)
            .limit(KEEP)
        )
    )
    unread = await db.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user.id, Notification.read_at.is_(None))
    )
    pages = {
        p.id: p
        for p in await db.scalars(
            select(Page).where(Page.id.in_({r.page_id for r in rows if r.page_id}))
        )
    }
    requests = {
        r.id: r
        for r in await db.scalars(
            select(RevisionRequest).where(
                RevisionRequest.id.in_({r.request_id for r in rows if r.request_id})
            )
        )
    }
    offers = {
        o.request_id: o.status
        for o in await db.scalars(
            select(RequestOffer).where(
                RequestOffer.user_id == user.id,
                RequestOffer.request_id.in_(list(requests)),
            )
        )
    }
    people = {
        u.id: u
        for u in await db.scalars(
            select(User).where(
                User.id.in_(
                    {r.actor_id for r in rows if r.actor_id}
                    | {q.approved_by_user_id for q in requests.values() if q.approved_by_user_id}
                )
            )
        )
    }
    items = []
    for n in rows:
        page = pages.get(n.page_id) if n.page_id else None
        req = requests.get(n.request_id) if n.request_id else None
        items.append(
            NotificationItem(
                id=n.id,
                kind=n.kind,
                created_at=n.created_at,
                read=n.read_at is not None,
                body=n.body,
                actor=_name(people.get(n.actor_id)) if n.actor_id else None,
                page=NotificationPage(id=page.id, title=page.title) if page else None,
                request=NotificationRequest(
                    id=req.id,
                    status=req.status,
                    my_offer=offers.get(req.id),
                    approved_by=_name(people.get(req.approved_by_user_id))
                    if req.approved_by_user_id
                    else None,
                    approved_by_me=req.approved_by_user_id == user.id,
                )
                if req
                else None,
            )
        )
    return NotificationList(
        items=items, unread=unread or 0, agent=await agents.presence(db, user.id)
    )


async def mark_all_read(db: AsyncSession, user: User) -> None:
    await db.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.read_at.is_(None))
        .values(read_at=datetime.now(UTC))
    )
    await db.commit()
