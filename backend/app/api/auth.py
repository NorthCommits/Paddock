import uuid
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
from app.core.errors import AppError
from app.core.security import csrf_for_session
from app.schemas.auth import (
    BrowserSessionOut,
    ForgotPasswordIn,
    LoginIn,
    MeOut,
    PasswordChangeIn,
    ProfileUpdate,
    ResetPasswordIn,
    SessionOut,
    SignupIn,
    UserOut,
    VerifyEmailIn,
)
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
    out = _session_out(user, session)
    await accounts.send_verification(db, user, client_ip(request))  # best effort, see mailer
    return out


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


@router.patch("/me", response_model=UserOut)
async def update_me(body: ProfileUpdate, request: Request, db: DbDep, actor: SessionActorDep):
    return await accounts.update_profile(db, actor.user, body.display_name, client_ip(request))


@router.post("/me/password", status_code=204)
async def change_password(
    body: PasswordChangeIn, request: Request, db: DbDep, actor: SessionActorDep
):
    await accounts.change_password(
        db,
        actor.user,
        actor.session,
        current_password=body.current_password,
        new_password=body.new_password,
        ip=client_ip(request),
    )


@router.get("/me/sessions", response_model=list[BrowserSessionOut])
async def my_sessions(db: DbDep, actor: SessionActorDep):
    rows = await accounts.list_sessions(db, actor.user)
    return [
        BrowserSessionOut(
            id=r.id,
            created_at=r.created_at,
            last_seen_at=r.last_seen_at,
            expires_at=r.expires_at,
            user_agent=r.user_agent,
            ip=r.ip,
            current=r.id == actor.session.id,
        )
        for r in rows
    ]


@router.post("/me/sessions/revoke-others", status_code=204)
async def revoke_others(request: Request, db: DbDep, actor: SessionActorDep):
    await accounts.revoke_other_sessions(db, actor.user, actor.session, client_ip(request))


@router.delete("/me/sessions/{session_id}", status_code=204)
async def revoke_one(session_id: uuid.UUID, request: Request, db: DbDep, actor: SessionActorDep):
    await accounts.revoke_session(db, actor.user, actor.session, session_id, client_ip(request))


@router.post("/auth/verify-email", status_code=204)
async def verify_email(body: VerifyEmailIn, request: Request, db: DbDep):
    await accounts.verify_email(db, body.token, client_ip(request))


@router.post("/auth/forgot-password", status_code=204)
async def forgot_password(body: ForgotPasswordIn, request: Request, db: DbDep):
    # Always the same answer, so nobody can use this to find out who has an account.
    await accounts.forgot_password(db, body.email, client_ip(request))


@router.post("/auth/reset-password", status_code=204)
async def reset_password(body: ResetPasswordIn, request: Request, db: DbDep):
    await accounts.reset_password(db, body.token, body.new_password, client_ip(request))


@router.post("/me/verification/resend", status_code=204)
async def resend_verification(request: Request, db: DbDep, actor: SessionActorDep):
    if actor.user.email_verified_at is not None:
        return
    sent = await accounts.send_verification(db, actor.user, client_ip(request))
    if not sent:
        raise AppError(
            503, "email_unavailable", "We could not send the email right now. Try again soon."
        )
