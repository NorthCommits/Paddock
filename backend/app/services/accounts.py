import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import (
    burn_password_time,
    hash_password,
    new_secret,
    password_needs_rehash,
    sha256_hex,
    verify_password,
)
from app.db.models import User, UserSession
from app.services import audit

SEEN_UPDATE_EVERY = timedelta(minutes=5)

BAD_LOGIN = AppError(401, "unauthenticated", "Incorrect email or password")


def _now() -> datetime:
    return datetime.now(UTC)


async def _start_session(
    db: AsyncSession, user: User, ip: str | None, user_agent: str | None
) -> tuple[UserSession, str]:
    raw = new_secret()
    now = _now()
    session = UserSession(
        user_id=user.id,
        token_hash=sha256_hex(raw),
        expires_at=now + timedelta(days=get_settings().session_days),
        last_seen_at=now,
        ip=ip,
        user_agent=(user_agent or "")[:300] or None,
    )
    db.add(session)
    await db.flush()  # assigns the id
    return session, raw


async def signup(
    db: AsyncSession,
    *,
    email: str,
    password: str,
    handle: str,
    display_name: str | None,
    ip: str | None,
    user_agent: str | None,
) -> tuple[User, UserSession, str]:
    if await db.scalar(select(User.id).where(User.email == email)):
        raise AppError(409, "conflict", "That email is already registered")
    if await db.scalar(select(User.id).where(User.handle == handle)):
        raise AppError(409, "conflict", "That handle is already taken")

    user = User(
        email=email,
        handle=handle,
        display_name=display_name or handle,
        password_hash=await asyncio.to_thread(hash_password, password),
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError as exc:  # two sign ups raced each other
        await db.rollback()
        raise AppError(409, "conflict", "That email or handle is already in use") from exc

    session, raw = await _start_session(db, user, ip, user_agent)
    audit.record(db, action="user.signup", user_id=user.id, ip=ip)
    await db.commit()
    return user, session, raw


async def login(
    db: AsyncSession,
    *,
    email: str,
    password: str,
    ip: str | None,
    user_agent: str | None,
) -> tuple[User, UserSession, str]:
    user = await db.scalar(select(User).where(User.email == email.lower()))
    if user is None or user.disabled_at is not None:
        await asyncio.to_thread(burn_password_time, password)
        raise BAD_LOGIN

    if not await asyncio.to_thread(verify_password, user.password_hash, password):
        audit.record(db, action="user.login_failed", user_id=user.id, ip=ip)
        await db.commit()
        raise BAD_LOGIN

    if password_needs_rehash(user.password_hash):
        user.password_hash = await asyncio.to_thread(hash_password, password)

    session, raw = await _start_session(db, user, ip, user_agent)
    audit.record(db, action="user.login", user_id=user.id, ip=ip)
    await db.commit()
    return user, session, raw


async def find_session(db: AsyncSession, raw: str) -> tuple[User, UserSession] | None:
    """Look up a browser session from its cookie value. None if missing, expired or disabled."""
    now = _now()
    row = (
        await db.execute(
            select(User, UserSession)
            .join(UserSession, UserSession.user_id == User.id)
            .where(
                UserSession.token_hash == sha256_hex(raw),
                UserSession.expires_at > now,
                User.disabled_at.is_(None),
            )
        )
    ).first()
    if row is None:
        return None
    user, session = row
    if now - session.last_seen_at > SEEN_UPDATE_EVERY:
        session.last_seen_at = now
        await db.commit()
    return user, session


async def end_session(db: AsyncSession, session: UserSession, ip: str | None) -> None:
    await db.execute(delete(UserSession).where(UserSession.id == session.id))
    audit.record(db, action="user.logout", user_id=session.user_id, ip=ip)
    await db.commit()
