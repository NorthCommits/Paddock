"""Passwords, tokens and CSRF values. Nothing in here touches the database."""

import hashlib
import hmac
import secrets
import uuid

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.core.config import get_settings

_hasher = PasswordHasher()
_DUMMY_HASH = _hasher.hash("not-a-real-password")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def burn_password_time(password: str) -> None:
    """Spend the same time as a real check, so an unknown email is not detectable by timing."""
    verify_password(_DUMMY_HASH, password)


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def new_secret() -> str:
    """A random value with 256 bits of randomness, safe for URLs and headers."""
    return secrets.token_urlsafe(32)


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def csrf_for_session(session_id: uuid.UUID) -> str:
    """The CSRF value for a browser session. Derived, so nothing extra is stored."""
    key = get_settings().secret_key.encode()
    return hmac.new(key, f"csrf:{session_id}".encode(), hashlib.sha256).hexdigest()


def same_value(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())
