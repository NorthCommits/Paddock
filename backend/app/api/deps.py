"""Shared building blocks for routes: who is calling, and what may they do."""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.policy import ALL_SCOPES
from app.core.security import csrf_for_session, same_value
from app.db.models import ApiToken, User, UserSession
from app.db.session import get_session
from app.services import accounts, tokens

SESSION_COOKIE = "paddock_session"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

DbDep = Annotated[AsyncSession, Depends(get_session)]


@dataclass
class Actor:
    user: User
    scopes: frozenset[str]
    token: ApiToken | None = None
    session: UserSession | None = None


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


async def get_actor(request: Request, db: DbDep) -> Actor:
    """Work out who is calling from a Bearer token or a browser session cookie."""
    auth = request.headers.get("authorization", "")
    if auth:
        if not auth.lower().startswith("bearer "):
            raise AppError(401, "unauthenticated", "Use a Bearer token")
        found = await tokens.find(db, auth[7:].strip())
        if found is None:
            raise AppError(401, "unauthenticated", "Invalid or expired token")
        user, token = found
        return Actor(user=user, scopes=frozenset(token.scopes), token=token)

    raw = request.cookies.get(SESSION_COOKIE)
    found = await accounts.find_session(db, raw) if raw else None
    if found is None:
        raise AppError(401, "unauthenticated", "Sign in required")
    user, session = found

    if request.method not in SAFE_METHODS:
        sent = request.headers.get("x-csrf-token", "")
        if not same_value(sent, csrf_for_session(session.id)):
            raise AppError(403, "forbidden", "Missing or invalid CSRF token")
    return Actor(user=user, scopes=ALL_SCOPES, session=session)


ActorDep = Annotated[Actor, Depends(get_actor)]


async def get_session_actor(actor: ActorDep) -> Actor:
    """For account management: only a browser session, never an agent token."""
    if actor.session is None:
        raise AppError(403, "forbidden", "This needs a browser session, not an API token")
    return actor


SessionActorDep = Annotated[Actor, Depends(get_session_actor)]


def require_scope(scope: str):
    """Build a dependency that rejects callers who lack a scope."""

    async def check(actor: ActorDep) -> Actor:
        if scope not in actor.scopes:
            raise AppError(403, "forbidden", f"This token lacks the {scope} scope")
        return actor

    return check
