"""Page chat: one shared chat per page, and private messages between two people on it.

Messages are saved in their own table. Live changes are pushed on the page stream, but never stored
as events, so webhooks and agents never see them.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.db.models import Page, PageMessage, User
from app.schemas.chat import MessageOut, Sender
from app.services import events, notifications, pages, presence

LIMIT = 50
PREVIEW = 80


def _sender(user: User) -> Sender:
    return Sender(id=user.id, handle=user.handle, display_name=user.display_name)


def _out(m: PageMessage, people: dict[uuid.UUID, User]) -> MessageOut:
    return MessageOut(
        id=m.id,
        sender=_sender(people[m.sender_id]),
        to=m.recipient_id,
        body="" if m.deleted_at else m.body,
        created_at=m.created_at,
        deleted=m.deleted_at is not None,
    )


async def _people(db: AsyncSession, rows: list[PageMessage]) -> dict[uuid.UUID, User]:
    ids = {m.sender_id for m in rows}
    return {u.id: u for u in await db.scalars(select(User).where(User.id.in_(ids)))}


async def list_messages(
    db: AsyncSession, page: Page, user: User, with_id: uuid.UUID | None, before: datetime | None
) -> tuple[list[MessageOut], bool]:
    """The page chat, or the private thread with one person. Newest 50, shown oldest first."""
    query = select(PageMessage).where(PageMessage.page_id == page.id)
    if with_id is None:
        query = query.where(PageMessage.recipient_id.is_(None))
    else:
        query = query.where(
            or_(
                and_(PageMessage.sender_id == user.id, PageMessage.recipient_id == with_id),
                and_(PageMessage.sender_id == with_id, PageMessage.recipient_id == user.id),
            )
        )
    if before is not None:
        query = query.where(PageMessage.created_at < before)
    rows = list(
        await db.scalars(
            query.order_by(PageMessage.created_at.desc(), PageMessage.id.desc()).limit(LIMIT + 1)
        )
    )
    more = len(rows) > LIMIT
    rows = rows[:LIMIT][::-1]
    people = await _people(db, rows)
    return [_out(m, people) for m in rows], more


async def send(
    db: AsyncSession, page: Page, user: User, body: str, to: uuid.UUID | None
) -> MessageOut:
    if to is not None:
        allowed = {u.id for u in await presence.people_with_access(db, page)}
        if to == user.id or to not in allowed:
            raise AppError(422, "validation_failed", "That person cannot be messaged on this page")
    message = PageMessage(page_id=page.id, sender_id=user.id, recipient_id=to, body=body)
    db.add(message)
    await db.flush()
    await db.refresh(message)
    if to is not None and not await presence.has_here(db, page.id, to):
        name = user.display_name or f"@{user.handle}"
        notifications.add(
            db,
            to,
            "chat_message",
            page_id=page.id,
            request_id=None,
            actor_id=user.id,
            body=f"{name}: {body[:PREVIEW]}",
        )
    await db.commit()
    events.push(
        page.id,
        "message.created",
        {"id": str(message.id), "sender_id": str(user.id), "to": str(to) if to else None},
        audience=[user.id, to] if to else None,
    )
    return _out(message, {user.id: user})


async def delete(db: AsyncSession, actor, message_id: uuid.UUID) -> None:
    """The sender may delete their own message. The page owner may delete any page-wide one."""
    message = await db.get(PageMessage, message_id)
    if message is None:
        raise AppError(404, "not_found", "Message not found")
    page = await pages.get_for_actor(db, actor, message.page_id, "page.view")
    user = actor.user
    if message.recipient_id is not None and user.id not in (
        message.sender_id,
        message.recipient_id,
    ):
        raise AppError(404, "not_found", "Message not found")
    if not (
        message.sender_id == user.id or (message.recipient_id is None and page.owner_id == user.id)
    ):
        raise AppError(403, "forbidden", "Only the sender can delete this message")
    if message.deleted_at is None:
        message.deleted_at = datetime.now(UTC)
        message.body = ""
        await db.commit()
        to = message.recipient_id
        events.push(
            page.id,
            "message.deleted",
            {
                "id": str(message.id),
                "sender_id": str(message.sender_id),
                "to": str(to) if to else None,
            },
            audience=[message.sender_id, to] if to else None,
        )
