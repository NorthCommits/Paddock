import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import new_secret, sha256_hex
from app.db.models import ApiToken, User
from app.services import audit

TOKEN_PREFIX = "pdk_"
USED_UPDATE_EVERY = timedelta(minutes=1)


def _now() -> datetime:
    return datetime.now(UTC)


async def create(
    db: AsyncSession,
    user: User,
    *,
    name: str,
    scopes: list[str],
    expires_in_days: int | None,
    ip: str | None,
    client_id: str | None = None,
    source: str = "manual",
) -> tuple[ApiToken, str]:
    raw = TOKEN_PREFIX + new_secret()
    token = ApiToken(
        user_id=user.id,
        name=name,
        prefix=raw[:8],
        token_hash=sha256_hex(raw),
        scopes=scopes,
        expires_at=_now() + timedelta(days=expires_in_days) if expires_in_days else None,
        client_id=client_id,
        source=source,
    )
    db.add(token)
    await db.flush()
    audit.record(
        db,
        action="token.create",
        user_id=user.id,
        target_type="api_token",
        target_id=str(token.id),
        ip=ip,
        meta={"name": name, "scopes": scopes},
    )
    await db.commit()
    return token, raw


async def list_for_user(db: AsyncSession, user: User) -> list[ApiToken]:
    result = await db.scalars(
        select(ApiToken).where(ApiToken.user_id == user.id).order_by(ApiToken.created_at.desc())
    )
    return list(result)


async def revoke(db: AsyncSession, user: User, token_id: uuid.UUID, ip: str | None) -> None:
    token = await db.scalar(
        select(ApiToken).where(ApiToken.id == token_id, ApiToken.user_id == user.id)
    )
    if token is None:
        raise AppError(404, "not_found", "Token not found")
    if token.revoked_at is None:
        token.revoked_at = _now()
        audit.record(
            db,
            action="token.revoke",
            user_id=user.id,
            target_type="api_token",
            target_id=str(token.id),
            ip=ip,
        )
        await db.commit()


async def find(db: AsyncSession, raw: str) -> tuple[User, ApiToken] | None:
    """Look up an agent token. None if unknown, revoked, expired, or the user is disabled."""
    now = _now()
    row = (
        await db.execute(
            select(User, ApiToken)
            .join(ApiToken, ApiToken.user_id == User.id)
            .where(
                ApiToken.token_hash == sha256_hex(raw),
                ApiToken.revoked_at.is_(None),
                or_(ApiToken.expires_at.is_(None), ApiToken.expires_at > now),
                User.disabled_at.is_(None),
            )
        )
    ).first()
    if row is None:
        return None
    user, token = row
    if token.last_used_at is None or now - token.last_used_at > USED_UPDATE_EVERY:
        token.last_used_at = now
        await db.commit()
    return user, token
