import asyncio
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Event
from app.db.session import get_engine
from app.services import events

from .helpers import auth
from .test_approvals import member
from .test_comments import setup


async def event_count() -> int:
    async with AsyncSession(get_engine()) as db:
        return await db.scalar(select(func.count()).select_from(Event))


async def opened(user_id: str, page_id: str, person: bool = True):
    gen = events.stream(uuid.UUID(user_id), uuid.UUID(page_id), None, person=person)
    assert (await asyncio.wait_for(anext(gen), 2)).startswith(": connected")
    return gen


async def nothing_within(gen, seconds: float = 0.3) -> bool:
    try:
        await asyncio.wait_for(anext(gen), seconds)
    except TimeoutError:
        return True
    return False


async def test_push_is_not_stored_in_the_events_table(client):
    data, page_id = await setup(client)
    before = await event_count()
    events.push(uuid.UUID(page_id), "message.created", {"id": "x"})
    assert await event_count() == before


async def test_frame_without_an_id_has_no_id_line_and_hides_internal_fields():
    item = {
        "id": None,
        "type": "message.created",
        "page_id": "p",
        "created_at": "now",
        "data": {"a": 1},
        "owner": "",
        "people_only": True,
        "audience": ["u"],
    }
    text = events.frame(item)
    assert not any(line.startswith("id:") for line in text.splitlines())
    assert "audience" not in text and "people_only" not in text and "owner" not in text
    assert "event: message.created" in text


async def test_a_person_with_access_receives_a_pushed_event(client):
    data, page_id = await setup(client)
    gen = await opened(data["user"]["id"], page_id)
    events.push(uuid.UUID(page_id), "presence.changed", {"here": True})
    frame = await asyncio.wait_for(anext(gen), 2)
    assert "event: presence.changed" in frame
    await gen.aclose()


async def test_agent_streams_never_receive_people_only_events(client):
    data, page_id = await setup(client)
    gen = await opened(data["user"]["id"], page_id, person=False)
    events.push(uuid.UUID(page_id), "message.created", {"id": "x"})
    assert await nothing_within(gen)
    await gen.aclose()


async def test_audience_limits_who_receives_an_event(client):
    data, page_id = await setup(client)
    bo, bo_data = await member(client, data, page_id, "bo@example.com", "bobby", "viewer")
    ana = uuid.UUID(data["user"]["id"])
    mine = await opened(data["user"]["id"], page_id)
    his = await opened(bo_data["user"]["id"], page_id)
    events.push(uuid.UUID(page_id), "message.created", {"id": "x"}, audience=[ana])
    assert "message.created" in await asyncio.wait_for(anext(mine), 2)
    assert await nothing_within(his)
    await mine.aclose()
    await his.aclose()
    await bo.aclose()


async def test_losing_access_stops_pushed_events(client):
    data, page_id = await setup(client)
    bo, bo_data = await member(client, data, page_id, "bo@example.com", "bobby", "viewer")
    gen = await opened(bo_data["user"]["id"], page_id)
    await client.patch(f"/v1/pages/{page_id}", json={"visibility": "private"}, headers=auth(data))
    events.push(uuid.UUID(page_id), "presence.changed", {"here": True})
    assert await nothing_within(gen)
    await gen.aclose()
    await bo.aclose()
