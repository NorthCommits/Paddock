"""Page chat: one shared chat per page, and private messages between two people on it.

Messages are saved in their own table. Live changes are pushed on the page stream, but never stored
as events, so webhooks and agents never see them.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import and_, or_, select, tuple_
from sqlalchemy import delete as sql_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.db.models import ChatRead, Notification, Page, PageMessage, User
from app.schemas.chat import MessageOut, SeenBy, Sender
from app.services import events, notifications, pages, presence

LIMIT = 50
PREVIEW = 80


def _sender(user: User) -> Sender:
    return Sender(id=user.id, handle=user.handle, display_name=user.display_name)


def _out(
    m: PageMessage,
    people: dict[uuid.UUID, User],
    receipts: dict[uuid.UUID, tuple[list[SeenBy], int]] | None = None,
) -> MessageOut:
    seen_by, audience = (receipts or {}).get(m.id, ([], 0))
    return MessageOut(
        seen_by=seen_by,
        audience=audience,
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
    db: AsyncSession, page: Page, user: User, with_id: uuid.UUID | None, before: uuid.UUID | None
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
        cursor = await db.get(PageMessage, before)
        if cursor is not None and cursor.page_id == page.id:
            query = query.where(
                tuple_(PageMessage.created_at, PageMessage.id) < (cursor.created_at, cursor.id)
            )
    rows = list(
        await db.scalars(
            query.order_by(PageMessage.created_at.desc(), PageMessage.id.desc()).limit(LIMIT + 1)
        )
    )
    more = len(rows) > LIMIT
    rows = rows[:LIMIT][::-1]
    people = await _people(db, rows)
    receipts = await _receipts(db, page, user, with_id, rows)
    return [_out(m, people, receipts) for m in rows], more


def conversation_key(with_id: uuid.UUID | None) -> str:
    return "all" if with_id is None else str(with_id)


async def _receipts(
    db: AsyncSession, page: Page, user: User, with_id: uuid.UUID | None, rows: list[PageMessage]
) -> dict[uuid.UUID, tuple[list[SeenBy], int]]:
    """Who has read each of the caller's own messages. Others' messages get no receipts."""
    own = [m for m in rows if m.sender_id == user.id and m.deleted_at is None]
    if not own:
        return {}
    # A reader's marker for a conversation is keyed by the OTHER person: for them, "me".
    key = "all" if with_id is None else str(user.id)
    readers = [with_id] if with_id is not None else None
    query = select(ChatRead, User).join(User, User.id == ChatRead.user_id)
    query = query.where(ChatRead.page_id == page.id, ChatRead.conversation == key)
    if readers is not None:
        query = query.where(ChatRead.user_id.in_(readers))
    else:
        query = query.where(ChatRead.user_id != user.id)
    markers = list((await db.execute(query)).all())
    if with_id is None:
        access = {u.id for u in await presence.people_with_access(db, page)}
        access.discard(user.id)
        markers = [(r, u) for r, u in markers if u.id in access]
        audience = len(access)
    else:
        audience = 1
    out = {}
    for m in own:
        seen = [
            SeenBy(id=u.id, name=u.display_name or f"@{u.handle}", at=r.read_at)
            for r, u in markers
            if r.up_to >= m.created_at
        ]
        out[m.id] = (seen, audience)
    return out


async def mark_read(
    db: AsyncSession,
    page: Page,
    user: User,
    with_id: uuid.UUID | None,
    up_to_id: uuid.UUID,
) -> None:
    """Record that the caller has read a conversation up to a message, and tell its senders."""
    message = await db.get(PageMessage, up_to_id)
    if message is None or message.page_id != page.id:
        raise AppError(404, "not_found", "Message not found")
    if with_id is None:
        ours = message.recipient_id is None
    else:
        ours = {message.sender_id, message.recipient_id} == {user.id, with_id}
    if not ours:
        raise AppError(404, "not_found", "Message not found")
    key = conversation_key(with_id)
    row = await db.scalar(
        select(ChatRead).where(
            ChatRead.page_id == page.id, ChatRead.user_id == user.id, ChatRead.conversation == key
        )
    )
    if row is None:
        db.add(
            ChatRead(
                page_id=page.id,
                user_id=user.id,
                conversation=key,
                up_to=message.created_at,
                read_at=datetime.now(UTC),
            )
        )
    elif message.created_at > row.up_to:
        row.up_to = message.created_at
        row.read_at = datetime.now(UTC)
    else:
        return  # already read this far, so there is nothing new to say
    await db.flush()
    senders_query = select(PageMessage.sender_id).where(
        PageMessage.page_id == page.id,
        PageMessage.sender_id != user.id,
        PageMessage.created_at <= message.created_at,
        PageMessage.deleted_at.is_(None),
    )
    if with_id is None:
        senders_query = senders_query.where(PageMessage.recipient_id.is_(None))
    else:
        senders_query = senders_query.where(
            PageMessage.sender_id == with_id, PageMessage.recipient_id == user.id
        )
    senders = list(await db.scalars(senders_query.distinct()))
    await db.commit()
    if senders:
        events.push(
            page.id,
            "chat.read",
            {"reader_id": str(user.id), "scope": "all" if with_id is None else "private"},
            audience=senders,
        )


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
        if message.recipient_id is not None:
            name = actor.user.display_name or f"@{actor.user.handle}"
            await db.execute(
                sql_delete(Notification).where(
                    Notification.user_id == message.recipient_id,
                    Notification.kind == "chat_message",
                    Notification.actor_id == message.sender_id,
                    Notification.page_id == message.page_id,
                    Notification.body == f"{name}: {message.body[:PREVIEW]}",
                )
            )
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
