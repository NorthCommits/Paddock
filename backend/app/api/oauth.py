"""OAuth endpoints for agents: discovery, registration, authorize, consent and token."""

from collections.abc import Callable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, Depends, Form, Query, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.routing import APIRoute

from app.api.deps import DbDep, VerifiedPersonDep, client_ip
from app.core.config import get_settings
from app.core.ratelimit import limit
from app.schemas.oauth import (
    ApproveIn,
    ApproveOut,
    AuthRequestIn,
    PreviewOut,
    RegisterIn,
    RegisterOut,
)
from app.services import oauth

NO_STORE = {"Cache-Control": "no-store", "Pragma": "no-cache"}


def oauth_error(code: str, description: str, status: int = 400) -> JSONResponse:
    return JSONResponse(
        {"error": code, "error_description": description}, status_code=status, headers=NO_STORE
    )


class OAuthRoute(APIRoute):
    """Turns an OAuthError raised by a route into the standard OAuth JSON error."""

    def get_route_handler(self) -> Callable:
        handler = super().get_route_handler()

        async def wrapped(request: Request) -> Response:
            try:
                return await handler(request)
            except oauth.OAuthError as err:
                return oauth_error(err.code, err.description)

        return wrapped


router = APIRouter(route_class=OAuthRoute, tags=["oauth"])


def with_query(uri: str, **params: str | None) -> str:
    """Append parameters to a redirect address, keeping whatever query it already has."""
    parts = urlsplit(uri)
    query = parse_qsl(parts.query, keep_blank_values=True)
    query += [(k, v) for k, v in params.items() if v is not None]
    return urlunsplit(parts._replace(query=urlencode(query)))


async def known_client(db, client_id: str | None, redirect_uri: str | None):
    """The client, or a 400 error when the client or its redirect address cannot be trusted."""
    client = await oauth.get_client(db, client_id) if client_id else None
    if client is None:
        raise oauth.OAuthError("invalid_request", "Unknown client_id.")
    if not redirect_uri or not oauth.redirect_registered(client, redirect_uri):
        raise oauth.OAuthError("invalid_request", "The redirect address is not registered.")
    return client


# ------------------------------------------------------------------ discovery


def _issuer() -> str:
    return get_settings().api_public_url.rstrip("/")


def _protected_resource(resource: str) -> dict:
    return {
        "resource": resource,
        "authorization_servers": [_issuer()],
        "scopes_supported": list(oauth.OFFERED_SCOPES),
        "bearer_methods_supported": ["header"],
    }


@router.get("/.well-known/oauth-protected-resource")
async def protected_resource():
    return _protected_resource(_issuer())


@router.get("/.well-known/oauth-protected-resource/mcp")
async def protected_resource_mcp():
    return _protected_resource(_issuer() + "/mcp")


@router.get("/.well-known/oauth-authorization-server")
async def authorization_server():
    issuer = _issuer()
    return {
        "issuer": issuer,
        "authorization_endpoint": f"{issuer}/oauth/authorize",
        "token_endpoint": f"{issuer}/oauth/token",
        "registration_endpoint": f"{issuer}/oauth/register",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none"],
        "scopes_supported": list(oauth.OFFERED_SCOPES),
    }


# --------------------------------------------------------------- registration


@router.post(
    "/oauth/register",
    status_code=201,
    response_model=RegisterOut,
    dependencies=[Depends(limit("register"))],
)
async def register(body: RegisterIn, db: DbDep):
    client = await oauth.register_client(
        db, client_name=body.client_name, redirect_uris=body.redirect_uris
    )
    return RegisterOut(
        client_id=client.client_id,
        client_name=client.client_name,
        redirect_uris=list(client.redirect_uris),
    )


# ------------------------------------------------------------------ authorize


@router.get("/oauth/authorize")
async def authorize(
    request: Request,
    db: DbDep,
    client_id: str | None = Query(default=None, max_length=200),
    redirect_uri: str | None = Query(default=None, max_length=1000),
    response_type: str = Query(default="", max_length=20),
    code_challenge: str = Query(default="", max_length=200),
    code_challenge_method: str = Query(default="", max_length=20),
    scope: str | None = Query(default=None, max_length=500),
    state: str | None = Query(default=None, max_length=2000),
):
    client = await known_client(db, client_id, redirect_uri)
    try:
        oauth.check_request(
            client,
            redirect_uri=redirect_uri,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            scope=scope,
            response_type=response_type,
        )
    except oauth.OAuthError as err:
        target = with_query(
            redirect_uri, error=err.code, error_description=err.description, state=state
        )
        return RedirectResponse(target, status_code=302, headers=NO_STORE)
    consent = f"{get_settings().app_origin.rstrip('/')}/oauth/consent"
    return RedirectResponse(f"{consent}?{request.url.query}", status_code=302, headers=NO_STORE)


# ------------------------------------------------------- consent (person only)


async def checked(db, body: AuthRequestIn):
    """Validate the request before anything else happens. Returns the client and its scopes."""
    client = await known_client(db, body.client_id, body.redirect_uri)
    scopes = oauth.check_request(
        client,
        redirect_uri=body.redirect_uri,
        code_challenge=body.code_challenge,
        code_challenge_method=body.code_challenge_method,
        scope=body.scope,
        response_type=body.response_type,
    )
    return client, scopes


@router.post("/v1/oauth/preview", response_model=PreviewOut)
async def preview(body: AuthRequestIn, db: DbDep, actor: VerifiedPersonDep):
    client, scopes = await checked(db, body)
    host = urlsplit(body.redirect_uri).netloc or urlsplit(body.redirect_uri).scheme
    return PreviewOut(client_name=client.client_name, redirect_host=host, scopes=scopes)


@router.post(
    "/v1/oauth/approve", response_model=ApproveOut, dependencies=[Depends(limit("manage"))]
)
async def approve(body: ApproveIn, request: Request, db: DbDep, actor: VerifiedPersonDep):
    client, scopes = await checked(db, body)
    if body.decision == "deny":
        denied = with_query(
            body.redirect_uri,
            error="access_denied",
            error_description="The person declined.",
            state=body.state,
        )
        return ApproveOut(redirect_to=denied)
    code = await oauth.approve(
        db,
        actor.user,
        client,
        redirect_uri=body.redirect_uri,
        code_challenge=body.code_challenge,
        scopes=scopes,
        ip=client_ip(request),
    )
    return ApproveOut(redirect_to=with_query(body.redirect_uri, code=code, state=body.state))


# ---------------------------------------------------------------------- token


@router.post("/oauth/token")
async def token(
    request: Request,
    db: DbDep,
    grant_type: str = Form(default=""),
    code: str = Form(default=""),
    code_verifier: str = Form(default=""),
    redirect_uri: str = Form(default=""),
    client_id: str = Form(default=""),
):
    if grant_type != "authorization_code":
        raise oauth.OAuthError(
            "unsupported_grant_type", "Only grant_type=authorization_code is supported."
        )
    raw, scopes = await oauth.exchange(
        db,
        client_id=client_id,
        code=code,
        code_verifier=code_verifier,
        redirect_uri=redirect_uri,
        ip=client_ip(request),
    )
    return JSONResponse(
        {"access_token": raw, "token_type": "Bearer", "scope": " ".join(scopes)},
        headers=NO_STORE,
    )
