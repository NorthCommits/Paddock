"""Shared building blocks for routes: who is calling, and what may they do."""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import neon
from app.core.errors import AppError
from app.core.policy import ALL_SCOPES
from app.db.models import ApiToken, User
from app.db.session import get_session
from app.services import accounts, tokens

DbDep = Annotated[AsyncSession, Depends(get_session)]


@dataclass
class Actor:
    user: User
    scopes: frozenset[str]
    token: ApiToken | None = None  # set when an agent token was used

    @property
    def is_person(self) -> bool:
        """True for someone signed in through Neon Auth, false for an agent token."""
        return self.token is None


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _bearer(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if not auth:
        raise AppError(401, "unauthenticated", "Sign in required")
    if not auth.lower().startswith("bearer "):
        raise AppError(401, "unauthenticated", "Use a Bearer token")
    return auth[7:].strip()


async def get_identity(request: Request) -> neon.Identity:
    """Who Neon says is calling. Works before the Paddock account exists."""
    raw = _bearer(request)
    if not neon.looks_like_jwt(raw):
        raise AppError(401, "unauthenticated", "Sign in required")
    return await neon.verify(raw)


IdentityDep = Annotated[neon.Identity, Depends(get_identity)]


async def get_actor(request: Request, db: DbDep) -> Actor:
    """Work out who is calling from an agent token or a Neon Auth sign-in token."""
    raw = _bearer(request)
    if not neon.looks_like_jwt(raw):
        found = await tokens.find(db, raw)
        if found is None:
            raise AppError(401, "unauthenticated", "Invalid or expired token")
        user, token = found
        return Actor(user=user, scopes=frozenset(token.scopes), token=token)

    identity = await neon.verify(raw)
    user = await accounts.find_by_neon(db, identity)
    if user is None:
        raise AppError(
            403, "onboarding_required", "Choose a handle to finish creating your account"
        )
    if user.disabled_at is not None:
        raise AppError(401, "unauthenticated", "This account is disabled")
    return Actor(user=user, scopes=ALL_SCOPES)


ActorDep = Annotated[Actor, Depends(get_actor)]


async def get_person(actor: ActorDep) -> Actor:
    """For account management: only a signed-in person, never an agent token."""
    if not actor.is_person:
        raise AppError(403, "forbidden", "This needs a signed-in person, not an API token")
    return actor


PersonDep = Annotated[Actor, Depends(get_person)]


def require_scope(scope: str):
    """Build a dependency that rejects callers who lack a scope."""

    async def check(actor: ActorDep) -> Actor:
        if scope not in actor.scopes:
            raise AppError(403, "forbidden", f"This token lacks the {scope} scope")
        return actor

    return check


async def get_verified_actor(actor: ActorDep) -> Actor:
    """For actions that need a confirmed email address (publishing, creating tokens)."""
    if actor.user.email_verified_at is None:
        raise AppError(
            403,
            "email_not_verified",
            "Verify your email address first. Check your inbox for the code.",
        )
    return actor


VerifiedActorDep = Annotated[Actor, Depends(get_verified_actor)]


async def get_verified_person(actor: PersonDep) -> Actor:
    return await get_verified_actor(actor)


VerifiedPersonDep = Annotated[Actor, Depends(get_verified_person)]
