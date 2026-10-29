"""OAuth endpoints for agents: discovery, registration, authorize, consent and token."""

from collections.abc import Callable
from urllib.parse import urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, Depends, Form, Request, Response
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
    """Append parameters to a redirect address. The address's own query is kept byte for byte."""
    parts = urlsplit(uri)
    added = urlencode([(k, v) for k, v in params.items() if v is not None])
    query = f"{parts.query}&{added}" if parts.query else added
    return urlunsplit(parts._replace(query=query))


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
    dependencies=[Depends(limit("register", by_ip=True))],
)
async def register(request: Request, db: DbDep):
    try:
        body = await request.json()
    except ValueError:
        body = None
    if not isinstance(body, dict):
        raise oauth.OAuthError("invalid_client_metadata", "The body must be a JSON object.")
    uris = body.get("redirect_uris")
    if not isinstance(uris, list) or not uris or not all(isinstance(u, str) for u in uris):
        raise oauth.OAuthError("invalid_redirect_uri", "redirect_uris must be a list of strings.")
    name = body.get("client_name")
    if name is None:
        parts = urlsplit(uris[0])
        name = (parts.netloc or parts.scheme or "App")[: oauth.MAX_NAME_LENGTH]
    elif not isinstance(name, str):
        raise oauth.OAuthError("invalid_client_metadata", "client_name must be a string.")
    client = await oauth.register_client(db, client_name=name, redirect_uris=uris)
    return JSONResponse(
        RegisterOut(
            client_id=client.client_id,
            client_name=client.client_name,
            redirect_uris=list(client.redirect_uris),
        ).model_dump(),
        status_code=201,
        headers=NO_STORE,
    )


# ------------------------------------------------------------------ authorize


AUTHORIZE_LIMITS = {
    "client_id": 200,
    "redirect_uri": 1000,
    "response_type": 20,
    "code_challenge": 200,
    "code_challenge_method": 20,
    "scope": 500,
    "state": 2000,
}


@router.get("/oauth/authorize")
async def authorize(
    db: DbDep,
    client_id: str | None = None,
    redirect_uri: str | None = None,
    response_type: str = "",
    code_challenge: str = "",
    code_challenge_method: str = "",
    scope: str | None = None,
    state: str | None = None,
):
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": response_type,
        "code_challenge": code_challenge,
        "code_challenge_method": code_challenge_method,
        "scope": scope,
        "state": state,
    }
    too_long = [k for k, v in params.items() if v is not None and len(v) > AUTHORIZE_LIMITS[k]]
    if "client_id" in too_long or "redirect_uri" in too_long or "state" in too_long:
        raise oauth.OAuthError("invalid_request", "A request parameter is too long.")
    client = await known_client(db, client_id, redirect_uri)
    try:
        if too_long:
            raise oauth.OAuthError("invalid_request", "A request parameter is too long.")
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
    # Only the named, validated parameters are passed on.
    query = urlencode([(k, v) for k, v in params.items() if v])
    return RedirectResponse(f"{consent}?{query}", status_code=302, headers=NO_STORE)


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


def display_host(uri: str) -> str:
    """The host the browser will really go to, with its port. Custom schemes show the scheme."""
    parts = urlsplit(uri)
    if not parts.hostname:
        return parts.scheme
    host = f"[{parts.hostname}]" if ":" in parts.hostname else parts.hostname
    try:
        port = parts.port
    except ValueError:
        port = None
    return f"{host}:{port}" if port else host


@router.post("/v1/oauth/preview", response_model=PreviewOut)
async def preview(body: AuthRequestIn, db: DbDep, actor: VerifiedPersonDep):
    client, scopes = await checked(db, body)
    host = display_host(body.redirect_uri)
    return PreviewOut(client_name=client.client_name, redirect_host=host, scopes=scopes)


@router.post(
    "/v1/oauth/approve", response_model=ApproveOut, dependencies=[Depends(limit("manage"))]
)
async def approve(body: ApproveIn, request: Request, db: DbDep, actor: VerifiedPersonDep):
    client, scopes = await checked(db, body)
    if body.decision == "deny":
        await oauth.deny(db, actor.user, client, ip=client_ip(request))
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
