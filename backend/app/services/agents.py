"""Which people have an agent connected, and whether it has been seen lately."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import any_, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ApiToken

ACTIVE_FOR = timedelta(minutes=10)  # an agent that called in this recently counts as active


def _live():
    return (
        ApiToken.revoked_at.is_(None),
        or_(ApiToken.expires_at.is_(None), ApiToken.expires_at > datetime.now(UTC)),
        literal("requests:act") == any_(ApiToken.scopes),
    )


async def with_agents(
    db: AsyncSession, user_ids: list[uuid.UUID]
) -> dict[uuid.UUID, datetime | None]:
    """The people among user_ids with an agent that can take requests, and when it last called."""
    if not user_ids:
        return {}
    rows = await db.execute(
        select(ApiToken.user_id, func.max(ApiToken.last_used_at))
        .where(ApiToken.user_id.in_(user_ids), *_live())
        .group_by(ApiToken.user_id)
    )
    return {user_id: seen for user_id, seen in rows.all()}


async def presence(db: AsyncSession, user_id: uuid.UUID) -> dict:
    found = await with_agents(db, [user_id])
    if user_id not in found:
        return {"connected": False, "active": False, "last_seen_at": None}
    seen = found[user_id]
    active = seen is not None and datetime.now(UTC) - seen <= ACTIVE_FOR
    return {"connected": True, "active": active, "last_seen_at": seen}
