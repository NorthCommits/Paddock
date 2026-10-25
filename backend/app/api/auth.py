from datetime import datetime

from fastapi import APIRouter, Request, Response

from app.api.deps import (
    SESSION_COOKIE,
    ActorDep,
    DbDep,
    SessionActorDep,
    client_ip,
)
from app.core.config import get_settings
from app.core.security import csrf_for_session
from app.schemas.auth import LoginIn, MeOut, SessionOut, SignupIn, UserOut
from app.services import accounts

router = APIRouter(prefix="/v1", tags=["auth"])


def _set_session_cookie(response: Response, raw: str, expires_at: datetime) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        raw,
        expires=expires_at,
        httponly=True,
        secure=get_settings().cookie_secure,
        samesite="lax",
        path="/",
    )


def _session_out(user, session) -> SessionOut:
    return SessionOut(user=UserOut.model_validate(user), csrf_token=csrf_for_session(session.id))


@router.post("/auth/signup", status_code=201, response_model=SessionOut)
async def signup(body: SignupIn, request: Request, response: Response, db: DbDep):
    user, session, raw = await accounts.signup(
        db,
        email=body.email,
        password=body.password,
        handle=body.handle,
        display_name=body.display_name,
        ip=client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    _set_session_cookie(response, raw, session.expires_at)
    return _session_out(user, session)


@router.post("/auth/login", response_model=SessionOut)
async def login(body: LoginIn, request: Request, response: Response, db: DbDep):
    user, session, raw = await accounts.login(
        db,
        email=body.email,
        password=body.password,
        ip=client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    _set_session_cookie(response, raw, session.expires_at)
    return _session_out(user, session)


@router.post("/auth/logout", status_code=204)
async def logout(request: Request, response: Response, db: DbDep, actor: SessionActorDep):
    await accounts.end_session(db, actor.session, client_ip(request))
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.get("/me", response_model=MeOut)
async def me(actor: ActorDep):
    return MeOut(
        user=UserOut.model_validate(actor.user),
        scopes=sorted(actor.scopes),
        csrf_token=csrf_for_session(actor.session.id) if actor.session else None,
    )
