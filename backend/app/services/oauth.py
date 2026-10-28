"""Sign-in flow for agents (OAuth 2.1 for public clients, PKCE S256).

The access token is an ordinary agent token. There are no refresh tokens.
"""

import base64
import hashlib
import re
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import new_secret, same_value, sha256_hex
from app.db.models import ApiToken, OAuthClient, OAuthCode, User
from app.services import audit, tokens

OFFERED_SCOPES = (
    "pages:read",
    "pages:write",
    "comments:read",
    "comments:write",
    "requests:act",
)
CODE_LIFETIME = timedelta(minutes=10)
MAX_REDIRECT_URIS = 10
MAX_URI_LENGTH = 500
MAX_NAME_LENGTH = 100
LOOPBACK_HOSTS = ("localhost", "127.0.0.1", "::1")
BLOCKED_SCHEMES = ("javascript", "data", "file", "vbscript", "blob", "about", "http")
CHALLENGE_PATTERN = re.compile(r"[A-Za-z0-9_-]{43,128}")
VERIFIER_PATTERN = re.compile(r"[A-Za-z0-9._~-]{43,128}")
GRANT_ERROR = "The code is invalid, expired, or already used."


class OAuthError(Exception):
    """An OAuth failure. The API layer turns it into the standard OAuth JSON error."""

    def __init__(self, code: str, description: str):
        super().__init__(f"{code}: {description}")
        self.code = code
        self.description = description


def _now() -> datetime:
    return datetime.now(UTC)


def _split(uri: str):
    try:
        return urlsplit(uri)
    except ValueError:
        return None


def _is_loopback(parts) -> bool:
    return parts.scheme == "http" and parts.hostname in LOOPBACK_HOSTS


def redirect_ok(uri: str) -> bool:
    """Is this a redirect address we are willing to send a person back to?"""
    # urlsplit silently drops tab, CR and LF, so refuse control and space characters first.
    if any(ord(c) < 0x21 or ord(c) == 0x7F for c in uri):
        return False
    parts = _split(uri)
    if parts is None or parts.fragment or "@" in parts.netloc:
        return False
    if parts.scheme == "https":
        return bool(parts.hostname)
    if parts.scheme == "http":
        return _is_loopback(parts)
    if len(parts.scheme) < 3 or parts.scheme in BLOCKED_SCHEMES:
        return False
    return bool(parts.netloc or parts.path)


def _same_redirect(registered: str, given: str) -> bool:
    if same_value(registered, given):
        return True
    a, b = _split(registered), _split(given)
    if a is None or b is None or not (_is_loopback(a) and _is_loopback(b)):
        return False
    # RFC 8252 section 7.3: only the port of a loopback address may differ.
    if a.fragment or b.fragment:
        return False
    return (a.hostname, a.path, a.query) == (b.hostname, b.path, b.query)


async def register_client(
    db: AsyncSession, *, client_name: str, redirect_uris: list[str]
) -> OAuthClient:
    if not redirect_uris or len(redirect_uris) > MAX_REDIRECT_URIS:
        raise OAuthError("invalid_redirect_uri", "Give between 1 and 10 redirect addresses.")
    for uri in redirect_uris:
        if len(uri) > MAX_URI_LENGTH or not redirect_ok(uri):
            raise OAuthError("invalid_redirect_uri", "A redirect address is not allowed.")
    name = client_name.strip()
    if not name or len(name) > MAX_NAME_LENGTH:
        raise OAuthError("invalid_client_metadata", "The client name must be 1 to 100 characters.")
    client = OAuthClient(client_id=new_secret()[:43], client_name=name, redirect_uris=redirect_uris)
    db.add(client)
    await db.flush()
    audit.record(
        db,
        action="oauth.register",
        target_type="oauth_client",
        target_id=client.client_id,
        meta={"name": name},
    )
    await db.commit()
    return client


async def get_client(db: AsyncSession, client_id: str) -> OAuthClient | None:
    return await db.scalar(select(OAuthClient).where(OAuthClient.client_id == client_id))


def check_request(
    client: OAuthClient,
    *,
    redirect_uri: str,
    code_challenge: str,
    code_challenge_method: str,
    scope: str | None,
    response_type: str,
) -> list[str]:
    """Validate an authorization request. Returns the scopes that would be granted."""
    if response_type != "code":
        raise OAuthError("unsupported_response_type", "Only response_type=code is supported.")
    if not redirect_ok(redirect_uri) or not any(
        _same_redirect(registered, redirect_uri) for registered in client.redirect_uris
    ):
        raise OAuthError("invalid_request", "The redirect address is not registered.")
    if code_challenge_method != "S256":
        raise OAuthError("invalid_request", "code_challenge_method must be S256.")
    if not CHALLENGE_PATTERN.fullmatch(code_challenge or ""):
        raise OAuthError("invalid_request", "The code_challenge is missing or malformed.")
    if scope is None or not scope.split():
        return list(OFFERED_SCOPES)
    asked = list(dict.fromkeys(scope.split()))
    if any(s not in OFFERED_SCOPES for s in asked):
        raise OAuthError("invalid_scope", "A requested scope is not offered.")
    return asked


async def approve(
    db: AsyncSession,
    user: User,
    client: OAuthClient,
    *,
    redirect_uri: str,
    code_challenge: str,
    scopes: list[str],
    ip: str | None,
) -> str:
    """Record that a signed-in person clicked Allow. Returns the raw single-use code."""
    raw = new_secret()
    db.add(
        OAuthCode(
            code_hash=sha256_hex(raw),
            client_id=client.client_id,
            user_id=user.id,
            redirect_uri=redirect_uri,
            code_challenge=code_challenge,
            scopes=scopes,
            expires_at=_now() + CODE_LIFETIME,
        )
    )
    audit.record(
        db,
        action="oauth.approve",
        user_id=user.id,
        target_type="oauth_client",
        target_id=client.client_id,
        ip=ip,
        meta={"scopes": scopes},
    )
    await db.commit()
    return raw


def _pkce_matches(verifier: str, challenge: str) -> bool:
    digest = hashlib.sha256(verifier.encode()).digest()
    return same_value(base64.urlsafe_b64encode(digest).rstrip(b"=").decode(), challenge)


async def _revoke_for_reuse(db: AsyncSession, row: OAuthCode) -> None:
    """A used code came back: take away what it produced."""
    stmt = update(ApiToken).where(ApiToken.revoked_at.is_(None))
    if row.token_id is not None:
        stmt = stmt.where(ApiToken.id == row.token_id)
    else:
        # The first exchange has not stored its token id yet; fall back to the client's tokens.
        stmt = stmt.where(
            ApiToken.user_id == row.user_id,
            ApiToken.client_id == row.client_id,
            ApiToken.source == "oauth",
        )
    await db.execute(stmt.values(revoked_at=_now()))
    await db.commit()


async def exchange(
    db: AsyncSession,
    *,
    client_id: str,
    code: str,
    code_verifier: str,
    redirect_uri: str,
    ip: str | None,
) -> tuple[str, list[str]]:
    """Trade a code and its PKCE verifier for an access token. Every failure looks the same."""
    fail = OAuthError("invalid_grant", GRANT_ERROR)
    # The row lock makes two simultaneous exchanges of one code take turns.
    row = await db.scalar(
        select(OAuthCode).where(OAuthCode.code_hash == sha256_hex(code)).with_for_update()
    )
    if row is None:
        await db.rollback()
        raise fail
    if row.used_at is not None:
        await _revoke_for_reuse(db, row)
        raise fail
    client = await get_client(db, client_id)
    valid = (
        client is not None
        and same_value(row.client_id, client_id)
        and row.expires_at > _now()
        and same_value(row.redirect_uri, redirect_uri)
        and VERIFIER_PATTERN.fullmatch(code_verifier or "") is not None
        and _pkce_matches(code_verifier, row.code_challenge)
    )
    if not valid:
        await db.rollback()
        raise fail

    user = await db.get(User, row.user_id)
    if user is None or user.disabled_at is not None:
        await db.rollback()
        raise fail

    now = _now()
    row.used_at = now
    client.last_used_at = now
    await db.execute(
        update(ApiToken)
        .where(
            ApiToken.user_id == user.id,
            ApiToken.client_id == client.client_id,
            ApiToken.source == "oauth",
            ApiToken.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    audit.record(
        db,
        action="oauth.token",
        user_id=user.id,
        target_type="oauth_client",
        target_id=client.client_id,
        ip=ip,
    )
    # commit=False: the token, used_at, token_id and revocations are saved in one commit.
    token, raw = await tokens.create(
        db,
        user,
        name=f"{client.client_name} (connected with sign-in)"[:MAX_NAME_LENGTH],
        scopes=list(row.scopes),
        expires_in_days=None,
        ip=ip,
        client_id=client.client_id,
        source="oauth",
        commit=False,
    )
    row.token_id = token.id
    await db.commit()
    return raw, list(row.scopes)
