"""Short-lived signed values, used for links to published content.

A token says: this link may read this version of this page until this time.
Nothing is stored. The signature uses the server secret.
"""

import base64
import hashlib
import hmac
import json
import time
import uuid

from app.core.config import get_settings

AUDIENCE = "content"


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(payload: str) -> str:
    key = get_settings().secret_key.encode()
    return _b64(hmac.new(key, payload.encode(), hashlib.sha256).digest())


def make_content_token(page_id: uuid.UUID, version: int, lifetime_seconds: int) -> tuple[str, int]:
    """Return (token, expiry as a unix time)."""
    expires = int(time.time()) + lifetime_seconds
    body = json.dumps(
        {"p": str(page_id), "v": version, "e": expires, "a": AUDIENCE}, separators=(",", ":")
    )
    payload = _b64(body.encode())
    return f"{payload}.{_sign(payload)}", expires


def read_content_token(token: str) -> tuple[uuid.UUID, int] | None:
    """Return (page_id, version) when the token is genuine and not expired, else None."""
    try:
        payload, signature = token.split(".", 1)
        if not hmac.compare_digest(signature, _sign(payload)):
            return None
        data = json.loads(_unb64(payload))
        if data.get("a") != AUDIENCE or int(data["e"]) < time.time():
            return None
        return uuid.UUID(data["p"]), int(data["v"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None
