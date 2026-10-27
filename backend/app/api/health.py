import asyncio
import json
import time
import urllib.error
import urllib.request
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.db.session import get_session

router = APIRouter(tags=["operations"])

# Free hosting puts idle servers to sleep. /warmz wakes the ones a visit needs ahead of time.
_background: set[asyncio.Task] = set()
_last_poke = 0.0
_waiting = asyncio.Semaphore(5)
WAIT_SECONDS = 40


@router.get("/healthz")
async def healthz() -> dict:
    """The process is alive. Does not touch the database."""
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(session: Annotated[AsyncSession, Depends(get_session)]) -> dict:
    """The database is reachable. The wait is generous because Neon may be waking up."""
    try:
        await asyncio.wait_for(session.execute(text("select 1")), timeout=15)
    except Exception as exc:
        raise AppError(503, "database_unavailable", "Database is not reachable") from exc
    return {"status": "ready"}


def _content_answers() -> str:
    """One try at the content server: "ready", "waking" (no proper answer yet) or "down"."""
    url = get_settings().content_origin.rstrip("/") + "/healthz"
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            body = json.load(response)
        return "ready" if body.get("status") == "ok" else "waking"
    except urllib.error.URLError as exc:
        # Nothing listens there at all (for example on a laptop without the content server).
        return "down" if isinstance(exc.reason, ConnectionRefusedError) else "waking"
    except Exception:
        # A sleeping server may answer with its own wake-up page instead of ours.
        return "waking"


async def _pause() -> None:
    await asyncio.sleep(2)


async def _wait_for_content(seconds: float) -> str:
    deadline = time.monotonic() + seconds
    while True:
        state = await asyncio.to_thread(_content_answers)
        if state != "waking" or time.monotonic() >= deadline:
            return state
        await _pause()


def _poke_content() -> None:
    """Start waking the content server in the background, at most once a minute."""
    global _last_poke
    now = time.monotonic()
    if now - _last_poke < 60:
        return
    _last_poke = now
    task = asyncio.create_task(_wait_for_content(60))
    _background.add(task)
    task.add_done_callback(_background.discard)


@router.get("/warmz")
async def warmz(
    session: Annotated[AsyncSession, Depends(get_session)], wait: str | None = None
) -> dict:
    """Wake the database and the content server. With ?wait=content, answer once the content
    server is really awake, so a page is never opened onto the host's "waking up" screen."""
    await readyz(session)
    if wait == "content":
        if _waiting.locked():
            return {"status": "ok", "content": "busy"}
        async with _waiting:
            return {"status": "ok", "content": await _wait_for_content(WAIT_SECONDS)}
    _poke_content()
    return {"status": "ok", "content": "checking"}
