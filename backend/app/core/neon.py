"""Checks the sign-in tokens that Neon Auth issues.

The browser signs in with Neon and sends us a short-lived token (a JWT signed with a
private key that only Neon holds). We check the signature against Neon's public keys.
"""

import asyncio
import logging
import ssl
from dataclasses import dataclass

import certifi
import jwt
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError

from app.core.config import get_settings
from app.core.errors import AppError

log = logging.getLogger("paddock.neon")
_client: PyJWKClient | None = None


@dataclass(frozen=True)
class Identity:
    """Who Neon says is calling."""

    sub: str
    email: str
    name: str | None
    email_verified: bool


def _jwks_client() -> PyJWKClient:
    """One shared client. It caches Neon's public keys and refetches when a new key appears."""
    global _client
    url = get_settings().neon_auth_url
    if not url:
        raise AppError(503, "auth_unavailable", "Sign in is not configured on this server")
    if _client is None:
        # certifi gives Python a trusted list of certificate authorities, even on a Mac
        # where Python was installed without one.
        _client = PyJWKClient(
            f"{url.rstrip('/')}/.well-known/jwks.json",
            lifespan=3600,
            ssl_context=ssl.create_default_context(cafile=certifi.where()),
        )
    return _client


def _signing_key(token: str):
    return _jwks_client().get_signing_key_from_jwt(token).key


def looks_like_jwt(value: str) -> bool:
    return value.count(".") == 2


async def verify(token: str) -> Identity:
    """Return who the token belongs to, or raise a 401."""
    try:
        key = await asyncio.to_thread(_signing_key, token)
        claims = jwt.decode(
            token,
            key,
            algorithms=["EdDSA"],
            options={"require": ["exp", "sub"], "verify_aud": False},
        )
    except PyJWKClientConnectionError as exc:
        log.warning("Could not fetch Neon's public keys: %s", exc)
        raise AppError(503, "auth_unavailable", "Cannot reach the sign in service") from exc
    except jwt.PyJWTError as exc:
        raise AppError(401, "unauthenticated", "Sign in again") from exc

    email = str(claims.get("email") or "").lower()
    if not email:
        raise AppError(401, "unauthenticated", "Sign in again")
    verified = bool(
        claims.get("email_verified")
        or claims.get("emailVerified")
        or get_settings().neon_auth_email_verified
    )
    return Identity(
        sub=str(claims["sub"]),
        email=email,
        name=(str(claims["name"]).strip() or None) if claims.get("name") else None,
        email_verified=verified,
    )
