"""Wake a person's own agent when a request is approved for it.

A person can save the address and token of a Claude Code scheduled task (an API trigger). When they
approve a request, Paddock knocks on that address so their agent starts at once, even with their
laptop closed. The token is stored encrypted and is used for nothing else.
"""

import asyncio
import logging
import re
import uuid
from datetime import UTC, datetime
from urllib.parse import urlparse

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.db.models import AgentTrigger
from app.db.session import get_sessionmaker
from app.services import audit
from app.services.webhooks import lock_secret, open_secret

log = logging.getLogger("paddock.triggers")

HOST = "api.anthropic.com"
PATH = re.compile(r"^/v1/claude_code/routines/trig_[A-Za-z0-9]+/fire$")
BETA = "experimental-cc-routine-2026-04-01"
TIMEOUT = 15

_running: set[asyncio.Task] = set()


def check_url(url: str) -> str:
    """Only a Claude Code task address is accepted, so this cannot be pointed elsewhere."""
    parts = urlparse(url.strip())
    if (
        parts.scheme != "https"
        or parts.hostname != HOST
        or parts.port
        or not PATH.match(parts.path)
    ):
        raise AppError(
            422,
            "validation_failed",
            "That does not look like a Claude Code task address. It starts with "
            "https://api.anthropic.com/v1/claude_code/routines/ and ends with /fire",
        )
    return f"https://{HOST}{parts.path}"


async def post_fire(url: str, token: str, text: str) -> str:
    """Knock once. Returns "started" or a short reason. Replaced in tests."""
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "anthropic-beta": BETA,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={"text": text},
            )
    except httpx.HTTPError:
        return "could not reach Claude"
    return "started" if r.status_code < 300 else f"refused ({r.status_code})"


async def get(db: AsyncSession, user_id: uuid.UUID) -> AgentTrigger | None:
    return await db.get(AgentTrigger, user_id)


async def save(db: AsyncSession, user_id: uuid.UUID, url: str, token: str, ip: str | None):
    url = check_url(url)
    token = token.strip()
    if not token:
        raise AppError(422, "validation_failed", "Paste the task token as well")
    row = await db.get(AgentTrigger, user_id)
    if row is None:
        row = AgentTrigger(user_id=user_id, url=url, token_enc=lock_secret(token))
        db.add(row)
    else:
        row.url, row.token_enc = url, lock_secret(token)
        row.last_fired_at = row.last_result = None
    audit.record(db, action="agent_trigger.save", user_id=user_id, ip=ip)
    await db.commit()
    return row


async def remove(db: AsyncSession, user_id: uuid.UUID, ip: str | None) -> None:
    row = await db.get(AgentTrigger, user_id)
    if row is not None:
        await db.delete(row)
        audit.record(db, action="agent_trigger.remove", user_id=user_id, ip=ip)
        await db.commit()


async def _fire(user_id: uuid.UUID, text: str) -> str | None:
    async with get_sessionmaker()() as db:
        row = await db.get(AgentTrigger, user_id)
        if row is None:
            return None
        result = await post_fire(row.url, open_secret(row.token_enc), text)
        row.last_fired_at = datetime.now(UTC)
        row.last_result = result
        await db.commit()
        return result


def wake_later(user_id: uuid.UUID, text: str) -> None:
    """Knock in the background, so an approval does not wait for Claude. Failures are logged."""

    async def run() -> None:
        try:
            await _fire(user_id, text)
        except Exception:
            log.exception("Could not wake the agent for %s", user_id)

    task = asyncio.create_task(run())
    _running.add(task)
    task.add_done_callback(_running.discard)


async def finish_waking() -> None:
    """Wait for knocks started with wake_later. Tests use this."""
    if _running:
        await asyncio.gather(*list(_running))


async def test_fire(db: AsyncSession, user_id: uuid.UUID) -> str:
    row = await db.get(AgentTrigger, user_id)
    if row is None:
        raise AppError(404, "not_found", "No task is saved yet")
    text = "This is a test from Paddock. Check Paddock for approved requests and handle them."
    result = await post_fire(row.url, open_secret(row.token_enc), text)
    row.last_fired_at = datetime.now(UTC)
    row.last_result = result
    await db.commit()
    return result


def request_text(page_title: str, who: str, body: str, request_id: uuid.UUID) -> str:
    return (
        f"Paddock request {request_id} is approved for you. {who} wrote on the page "
        f'"{page_title}": {body[:500]}\n'
        "Use the Paddock connector: list requests that are open, claim this one, make the change, "
        "publish a new version, and complete the request with the new version number."
    )
