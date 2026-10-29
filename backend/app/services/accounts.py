import random
import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.neon import Identity
from app.db.models import User
from app.schemas.auth import HANDLE_PATTERN, RESERVED_HANDLES
from app.services import audit

# Words for handle ideas. Paddock is a horse field, so the ideas lean that way.
ADJECTIVES = [
    "swift", "calm", "bright", "steady", "wild", "gentle", "brave", "quiet",
    "lucky", "golden", "misty", "sunny", "merry", "nimble", "bold", "clever",
]  # fmt: skip
NOUNS = [
    "foal", "mare", "colt", "pony", "meadow", "pasture", "gate", "clover",
    "stable", "hoof", "gallop", "saddle", "paddock", "fence", "hay", "canter",
]  # fmt: skip


def _now() -> datetime:
    return datetime.now(UTC)


def handle_problem(handle: str) -> str | None:
    """Why a handle cannot be used, or None when it is fine."""
    if not HANDLE_PATTERN.match(handle):
        return "Use 3 to 30 letters, numbers or dashes, not starting or ending with a dash"
    if handle in RESERVED_HANDLES:
        return "This handle is reserved"
    return None


async def find_by_neon(db: AsyncSession, identity: Identity) -> User | None:
    user = await db.scalar(select(User).where(User.neon_auth_id == identity.sub))
    if user is None or user.disabled_at is not None:
        return user
    if identity.email_verified and user.email_verified_at is None:
        user.email_verified_at = _now()
        await db.commit()
    return user


async def handle_is_free(db: AsyncSession, handle: str) -> bool:
    return await db.scalar(select(User.id).where(User.handle == handle)) is None


def _ideas(identity: Identity) -> list[str]:
    """Candidate handles: some from the person's own name, some from Paddock words."""
    rng = random.SystemRandom()
    base = re.sub(r"[^a-z0-9]+", "-", identity.email.split("@")[0].lower()).strip("-")[:18]
    name = re.sub(r"[^a-z0-9]+", "-", (identity.name or "").lower()).strip("-")[:18]
    own = [b for b in {base, name} if b]
    ideas: list[str] = []
    for b in own:
        ideas += [b, f"{b}-{rng.choice(NOUNS)}", f"{rng.choice(ADJECTIVES)}-{b}"]
        ideas.append(f"{b}{rng.randint(10, 99)}")
    for _ in range(6):
        ideas.append(f"{rng.choice(ADJECTIVES)}-{rng.choice(NOUNS)}")
        ideas.append(f"{rng.choice(ADJECTIVES)}-{rng.choice(NOUNS)}{rng.randint(2, 99)}")
    seen: set[str] = set()
    return [h for h in ideas if not (h in seen or seen.add(h)) and handle_problem(h) is None]


async def suggest_handles(db: AsyncSession, identity: Identity, count: int = 5) -> list[str]:
    """Handles nobody has taken yet. Ideas from the person's own name come first."""
    ideas = _ideas(identity)
    taken = set(await db.scalars(select(User.handle).where(User.handle.in_(ideas))))
    free = [h for h in ideas if h not in taken]
    return free[:count]


async def onboard(
    db: AsyncSession,
    identity: Identity,
    *,
    handle: str,
    display_name: str | None,
    ip: str | None,
) -> User:
    """Create the Paddock account for someone who has signed up with Neon Auth."""
    handle = handle.lower()
    problem = handle_problem(handle)
    if problem:
        raise AppError(422, "validation_error", problem)
    if await db.scalar(select(User.id).where(User.neon_auth_id == identity.sub)):
        raise AppError(409, "conflict", "You already have an account")
    if await db.scalar(select(User.id).where(User.email == identity.email)):
        raise AppError(409, "conflict", "That email is already used by another account")
    if not await handle_is_free(db, handle):
        raise AppError(409, "conflict", "That handle is already taken")

    user = User(
        neon_auth_id=identity.sub,
        email=identity.email,
        handle=handle,
        display_name=(display_name or identity.name or handle).strip()[:100] or handle,
        email_verified_at=_now() if identity.email_verified else None,
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError as exc:  # two requests raced each other
        await db.rollback()
        raise AppError(409, "conflict", "That handle or account is already in use") from exc
    audit.record(db, action="user.signup", user_id=user.id, ip=ip)
    await db.commit()
    return user


async def update_profile(
    db: AsyncSession,
    user: User,
    display_name: str | None,
    ip: str | None,
    theme: str | None = None,
) -> User:
    if display_name is not None:
        user.display_name = display_name
    if theme is not None:
        user.theme = theme
    audit.record(db, action="user.update_profile", user_id=user.id, ip=ip)
    await db.commit()
    return user
