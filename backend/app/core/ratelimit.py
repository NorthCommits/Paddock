"""Abuse controls: limits on how often one caller can use the API (SDD section 6 and 9).

Counts live in this process, which matches the single-instance design used for events. Each caller
is a token (agents) or a signed-in person, told apart by a hash of the Authorization header, or an
IP address when there is no credential. A window is one minute. When Paddock runs on several
instances, swap `Limiter` for one backed by Redis.
"""

import hashlib
import math
import time

from fastapi import Request

from app.core.config import get_settings
from app.core.errors import AppError

WINDOW = 60  # seconds

# name: calls allowed per window
RULES = {
    "general": 600,  # every request from one credential
    "anonymous": 120,  # every request with no credential, per IP address
    "publish": 30,  # create a page, publish a version, restore a version
    "comment": 60,  # create, edit, delete or resolve comments
    "request": 120,  # claim, complete or dismiss a request
    "manage": 20,  # create tokens, webhooks, invitations and share links
    "stream": 30,  # open a live event stream
    "view": 120,  # ask for a link to view a page
}

QUIET_PATHS = ("/healthz", "/readyz", "/warmz")


def now() -> float:
    return time.monotonic()


class Limiter:
    def __init__(self) -> None:
        self.windows: dict[tuple[str, str], list[float]] = {}  # (rule, caller) -> [start, count]
        self.calls = 0

    def hit(self, rule: str, caller: str) -> int | None:
        """Count a call. Returns None when allowed, else the seconds until the window resets."""
        current = now()
        self.calls += 1
        if self.calls % 1000 == 0:
            self._prune(current)
        entry = self.windows.get((rule, caller))
        if entry is None or current - entry[0] >= WINDOW:
            entry = self.windows[(rule, caller)] = [current, 0]
        entry[1] += 1
        if entry[1] > RULES[rule]:
            return max(1, math.ceil(WINDOW - (current - entry[0])))
        return None

    def _prune(self, current: float) -> None:
        stale = [k for k, v in self.windows.items() if current - v[0] >= WINDOW]
        for key in stale:
            del self.windows[key]


limiter = Limiter()


def caller_ip(request: Request) -> str | None:
    """The address of the caller. Behind proxies, set PROXY_HOPS to how many of them add to
    X-Forwarded-For, so a header the caller wrote themselves is not trusted."""
    hops = get_settings().proxy_hops
    forwarded = request.headers.get("x-forwarded-for", "")
    if hops > 0 and forwarded:
        parts = [p.strip() for p in forwarded.split(",") if p.strip()]
        if len(parts) >= hops:
            return parts[-hops]
    return request.client.host if request.client else None


def caller(request: Request) -> str:
    raw = request.headers.get("authorization", "")
    if raw:
        return "c:" + hashlib.sha256(raw.encode()).hexdigest()[:20]
    return "ip:" + (caller_ip(request) or "unknown")


def general_wait(request: Request) -> int | None:
    """Used for every request by the middleware. Returns seconds to wait, or None."""
    if not get_settings().rate_limit_enabled or request.url.path in QUIET_PATHS:
        return None
    who = caller(request)
    return limiter.hit("anonymous" if who.startswith("ip:") else "general", who)


def limit(rule: str):
    """A route dependency that applies one of the stricter named limits."""

    def check(request: Request) -> None:
        if not get_settings().rate_limit_enabled:
            return
        wait = limiter.hit(rule, caller(request))
        if wait is not None:
            raise AppError(
                429,
                "rate_limited",
                f"Too many requests. Try again in {wait} seconds.",
                retry_after=wait,
            )

    return check
