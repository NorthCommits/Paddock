"""Reactions to parts of a page: one small mark per person, block and kind."""

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.db.models import BlockReaction, Page, User
from app.schemas.live import ReactionOut
from app.services import events

MAX_PER_PERSON = 200  # on one page
NAMES_SHOWN = 5


async def set_reaction(
    db: AsyncSession, page: Page, user: User, block: str, key: str, on: bool
) -> None:
    """Add or remove a reaction. Doing it twice is fine. Others are told only when it changed."""
    mine = and_mine(page, user, block, key)
    present = await db.scalar(select(BlockReaction.id).where(*mine))
    if on and present is None:
        total = await db.scalar(
            select(func.count())
            .select_from(BlockReaction)
            .where(BlockReaction.page_id == page.id, BlockReaction.user_id == user.id)
        )
        if (total or 0) >= MAX_PER_PERSON:
            raise AppError(409, "conflict", "You have reacted to as much of this page as allowed")
        db.add(BlockReaction(page_id=page.id, user_id=user.id, block=block, key=key))
    elif not on and present is not None:
        await db.execute(delete(BlockReaction).where(*mine))
    else:
        return
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()  # the same reaction was added a moment ago by another request
        return
    count = await db.scalar(
        select(func.count())
        .select_from(BlockReaction)
        .where(
            BlockReaction.page_id == page.id, BlockReaction.block == block, BlockReaction.key == key
        )
    )
    events.push(
        page.id,
        "reaction.changed",
        {"block": block, "key": key, "user_id": str(user.id), "on": on, "count": count or 0},
    )


def and_mine(page: Page, user: User, block: str, key: str):
    return (
        BlockReaction.page_id == page.id,
        BlockReaction.user_id == user.id,
        BlockReaction.block == block,
        BlockReaction.key == key,
    )


async def list_for_page(db: AsyncSession, page: Page, me: User) -> list[ReactionOut]:
    rows = await db.execute(
        select(BlockReaction.block, BlockReaction.key, BlockReaction.user_id, User.display_name)
        .join(User, User.id == BlockReaction.user_id)
        .where(BlockReaction.page_id == page.id)
        .order_by(BlockReaction.created_at)
    )
    grouped: dict[tuple[str, str], ReactionOut] = {}
    for block, key, user_id, name in rows:
        item = grouped.setdefault(
            (block, key), ReactionOut(block=block, key=key, count=0, mine=False, who=[])
        )
        item.count += 1
        item.mine = item.mine or user_id == me.id
        if len(item.who) < NAMES_SHOWN:
            item.who.append(name)
    return list(grouped.values())
