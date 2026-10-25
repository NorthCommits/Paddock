import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
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
from app.db.models import EmailToken, User, UserSession
from app.services import audit, emails, mailer

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


async def update_profile(db: AsyncSession, user: User, display_name: str, ip: str | None) -> User:
    user.display_name = display_name
    audit.record(db, action="user.update_profile", user_id=user.id, ip=ip)
    await db.commit()
    return user


async def change_password(
    db: AsyncSession,
    user: User,
    keep: UserSession,
    *,
    current_password: str,
    new_password: str,
    ip: str | None,
) -> None:
    """Change the password and sign out every other browser."""
    if not await asyncio.to_thread(verify_password, user.password_hash, current_password):
        audit.record(db, action="user.password_change_failed", user_id=user.id, ip=ip)
        await db.commit()
        raise AppError(403, "forbidden", "Your current password is incorrect")
    user.password_hash = await asyncio.to_thread(hash_password, new_password)
    await db.execute(
        delete(UserSession).where(UserSession.user_id == user.id, UserSession.id != keep.id)
    )
    audit.record(db, action="user.password_change", user_id=user.id, ip=ip)
    await db.commit()


async def list_sessions(db: AsyncSession, user: User) -> list[UserSession]:
    rows = await db.scalars(
        select(UserSession)
        .where(UserSession.user_id == user.id, UserSession.expires_at > _now())
        .order_by(UserSession.last_seen_at.desc())
    )
    return list(rows)


async def revoke_session(
    db: AsyncSession, user: User, keep: UserSession, session_id, ip: str | None
) -> None:
    if session_id == keep.id:
        raise AppError(422, "validation_failed", "Use sign out to end this session")
    result = await db.execute(
        delete(UserSession).where(UserSession.id == session_id, UserSession.user_id == user.id)
    )
    if result.rowcount == 0:
        raise AppError(404, "not_found", "Session not found")
    audit.record(db, action="user.session_revoke", user_id=user.id, ip=ip)
    await db.commit()


async def revoke_other_sessions(
    db: AsyncSession, user: User, keep: UserSession, ip: str | None
) -> None:
    await db.execute(
        delete(UserSession).where(UserSession.user_id == user.id, UserSession.id != keep.id)
    )
    audit.record(db, action="user.sessions_revoke_others", user_id=user.id, ip=ip)
    await db.commit()


# Email verification and password reset -------------------------------------------------

RESEND_COOLDOWN = timedelta(seconds=60)


async def _issue_email_token(
    db: AsyncSession, user: User, purpose: str, lifetime: timedelta
) -> str:
    """Create a fresh single-use token. Older unused ones for the same purpose stop working."""
    await db.execute(
        delete(EmailToken).where(
            EmailToken.user_id == user.id,
            EmailToken.purpose == purpose,
            EmailToken.used_at.is_(None),
        )
    )
    raw = new_secret()
    db.add(
        EmailToken(
            user_id=user.id,
            purpose=purpose,
            token_hash=sha256_hex(raw),
            expires_at=_now() + lifetime,
        )
    )
    return raw


async def _asked_recently(db: AsyncSession, user: User, purpose: str) -> bool:
    latest = await db.scalar(
        select(func.max(EmailToken.created_at)).where(
            EmailToken.user_id == user.id, EmailToken.purpose == purpose
        )
    )
    return latest is not None and _now() - latest < RESEND_COOLDOWN


async def send_verification(db: AsyncSession, user: User, ip: str | None) -> bool:
    """Email a confirmation link. Raises 429 if one was sent under a minute ago."""
    if await _asked_recently(db, user, "verify"):
        raise AppError(429, "rate_limited", "An email was just sent. Wait a minute and try again.")
    settings = get_settings()
    raw = await _issue_email_token(db, user, "verify", timedelta(hours=settings.verify_email_hours))
    audit.record(db, action="user.verification_sent", user_id=user.id, ip=ip)
    await db.commit()
    link = f"{settings.app_origin}/verify-email?token={raw}"
    return await mailer.send_quietly(
        emails.verify_email(user.email, user.display_name, link, settings.verify_email_hours)
    )


async def verify_email(db: AsyncSession, raw: str, ip: str | None) -> None:
    token = await _use_email_token(db, raw, "verify")
    user = await db.get(User, token.user_id)
    if user is None or user.disabled_at is not None:
        raise BAD_LINK
    if user.email_verified_at is None:
        user.email_verified_at = _now()
    audit.record(db, action="user.email_verified", user_id=user.id, ip=ip)
    await db.commit()


async def forgot_password(db: AsyncSession, email: str, ip: str | None) -> None:
    """Email a reset link if the account exists. The caller always answers the same way."""
    user = await db.scalar(select(User).where(User.email == email.lower()))
    if user is None or user.disabled_at is not None:
        return
    if await _asked_recently(db, user, "reset"):
        return
    settings = get_settings()
    raw = await _issue_email_token(
        db, user, "reset", timedelta(minutes=settings.reset_password_minutes)
    )
    audit.record(db, action="user.password_reset_requested", user_id=user.id, ip=ip)
    await db.commit()
    link = f"{settings.app_origin}/reset-password?token={raw}"
    await mailer.send_quietly(
        emails.reset_password(user.email, user.display_name, link, settings.reset_password_minutes)
    )


async def reset_password(db: AsyncSession, raw: str, new_password: str, ip: str | None) -> None:
    token = await _use_email_token(db, raw, "reset")
    user = await db.get(User, token.user_id)
    if user is None or user.disabled_at is not None:
        raise BAD_LINK
    user.password_hash = await asyncio.to_thread(hash_password, new_password)
    if user.email_verified_at is None:
        user.email_verified_at = _now()  # they received mail at this address
    await db.execute(delete(UserSession).where(UserSession.user_id == user.id))
    audit.record(db, action="user.password_reset", user_id=user.id, ip=ip)
    await db.commit()


BAD_LINK = AppError(400, "invalid_token", "This link is invalid or has expired. Request a new one.")


async def _use_email_token(db: AsyncSession, raw: str, purpose: str) -> EmailToken:
    """Find a valid token and mark it used. The mark and the caller's change commit together."""
    token = await db.scalar(
        select(EmailToken)
        .where(
            EmailToken.token_hash == sha256_hex(raw),
            EmailToken.purpose == purpose,
            EmailToken.used_at.is_(None),
            EmailToken.expires_at > _now(),
        )
        .with_for_update()
    )
    if token is None:
        raise BAD_LINK
    token.used_at = _now()
    return token
