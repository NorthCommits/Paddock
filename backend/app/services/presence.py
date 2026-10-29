"""Who has a page open right now: here for 45 seconds after the last heartbeat."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Page, PageMember, PagePresence, User
from app.schemas.presence import PersonOut
from app.services import events

PRESENCE_SECONDS = 45


def _cutoff() -> datetime:
    return datetime.now(UTC) - timedelta(seconds=PRESENCE_SECONDS)


async def heartbeat(db: AsyncSession, page: Page, user: User) -> None:
    """Record that the person is here. Others are told only when they were not here before."""
    before = await db.scalar(
        select(PagePresence.last_seen_at).where(
            PagePresence.page_id == page.id, PagePresence.user_id == user.id
        )
    )
    await db.execute(
        insert(PagePresence)
        .values(page_id=page.id, user_id=user.id)
        .on_conflict_do_update(
            index_elements=["page_id", "user_id"], set_={"last_seen_at": func.now()}
        )
    )
    await db.commit()
    if before is None or before < _cutoff():
        events.push(page.id, "presence.changed", {"user_id": str(user.id), "here": True})


async def leave(db: AsyncSession, page: Page, user: User) -> None:
    result = await db.execute(
        delete(PagePresence).where(PagePresence.page_id == page.id, PagePresence.user_id == user.id)
    )
    await db.commit()
    if result.rowcount:
        events.push(page.id, "presence.changed", {"user_id": str(user.id), "here": False})


async def has_here(db: AsyncSession, page_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    seen = await db.scalar(
        select(PagePresence.last_seen_at).where(
            PagePresence.page_id == page_id, PagePresence.user_id == user_id
        )
    )
    return seen is not None and seen >= _cutoff()


async def people_with_access(db: AsyncSession, page: Page) -> list[User]:
    """The owner, plus the members unless the page is private. Used for who may be chatted to."""
    ids = [page.owner_id]
    if page.visibility != "private":
        ids += list(
            await db.scalars(select(PageMember.user_id).where(PageMember.page_id == page.id))
        )
    users = list(await db.scalars(select(User).where(User.id.in_(ids))))
    return sorted(users, key=lambda u: (u.id != page.owner_id, u.display_name.lower()))


async def people(db: AsyncSession, page: Page) -> list[PersonOut]:
    users = await people_with_access(db, page)
    here = set(
        await db.scalars(
            select(PagePresence.user_id).where(
                PagePresence.page_id == page.id, PagePresence.last_seen_at >= _cutoff()
            )
        )
    )
    return [
        PersonOut(id=u.id, handle=u.handle, display_name=u.display_name, here=u.id in here)
        for u in users
    ]
