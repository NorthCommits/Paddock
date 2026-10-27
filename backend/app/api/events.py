import uuid

from fastapi import APIRouter, Header
from fastapi.responses import StreamingResponse

from app.api.deps import ActorDep, DbDep
from app.core.errors import AppError
from app.services import events
from app.services.pages import get_for_actor

router = APIRouter(tags=["events"])

HEADERS = {"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"}


def _last_id(value: str | None) -> int | None:
    if value is None or not value.strip():
        return None
    try:
        return max(int(value), 0)
    except ValueError:
        raise AppError(422, "validation_failed", "Last-Event-ID must be a number") from None


def _sse(user_id: uuid.UUID, page_id: uuid.UUID | None, last: int | None) -> StreamingResponse:
    return StreamingResponse(
        events.stream(user_id, page_id, last), media_type="text/event-stream", headers=HEADERS
    )


@router.get("/v1/events")
async def all_events(db: DbDep, actor: ActorDep, last_event_id: str | None = Header(None)):
    """Everything on the pages this person owns or has been given access to."""
    if "events:read" not in actor.scopes:
        raise AppError(403, "forbidden", "This token lacks the events:read scope")
    last = _last_id(last_event_id)
    user_id = actor.user.id
    await db.close()  # a stream can stay open for hours, so do not hold a connection
    return _sse(user_id, None, last)


@router.get("/v1/pages/{page_id}/events")
async def page_events(
    page_id: uuid.UUID, db: DbDep, actor: ActorDep, last_event_id: str | None = Header(None)
):
    await get_for_actor(db, actor, page_id, "events.read")
    last = _last_id(last_event_id)
    user_id = actor.user.id
    await db.close()
    return _sse(user_id, page_id, last)
