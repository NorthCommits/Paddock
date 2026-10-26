"""Random secrets and hashing for tokens. Nothing in here touches the database."""

import hashlib
import hmac
import secrets


def new_secret() -> str:
    """A random value with 256 bits of randomness, safe for URLs and headers."""
    return secrets.token_urlsafe(32)


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def same_value(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())
