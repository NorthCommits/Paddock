import asyncio
import json

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Event
from app.db.session import get_engine
from app.main import app
from app.services import events

from .helpers import auth, make_token, new_page, signup
from .test_comments import comment, setup, share
from .test_requests import act, agent, ask
from .test_sharing import BO, other
from .test_versions import publish


async def stored(type_: str | None = None) -> list[Event]:
    async with AsyncSession(get_engine()) as db:
        rows = list(await db.scalars(select(Event).order_by(Event.id)))
    return [r for r in rows if type_ is None or r.type == type_]


async def types() -> list[str]:
    return [e.type for e in await stored()]


# ------------------------------------------------------------ events are saved with the change


async def test_publishing_and_restoring_are_recorded(client):
    data, page_id = await setup(client)
    await publish(client, data, page_id, "<p>two</p>", message="second")
    await client.post(f"/v1/pages/{page_id}/versions/1/rollback", headers=auth(data))
    rows = await stored()
    assert [r.type for r in rows] == [
        "version.published",
        "version.published",
        "version.rolled_back",
    ]
    assert rows[1].payload == {"version": 2, "message": "second", "by_agent": False}
    assert rows[2].payload["restored"] == 1
    assert all(str(r.page_id) == page_id for r in rows)


async def test_page_changes_are_recorded(client):
    data, page_id = await setup(client)
    await client.patch(f"/v1/pages/{page_id}", json={"title": "Renamed"}, headers=auth(data))
    await client.delete(f"/v1/pages/{page_id}", headers=auth(data))
    rows = await stored()
    assert [r.type for r in rows[1:]] == ["page.updated", "page.deleted"]
    assert rows[1].payload == {"title": "Renamed"}


async def test_a_change_that_does_nothing_records_nothing(client):
    data, page_id = await setup(client)
    await client.patch(
        f"/v1/pages/{page_id}", json={"title": "Quarterly report"}, headers=auth(data)
    )
    assert await types() == ["version.published"]


async def test_comment_and_request_life_is_recorded(client):
    data, page_id = await setup(client)
    token = await agent(client, data)
    first = (await comment(client, data, page_id, "@agent shorten")).json()
    rid = first["request"]["id"]
    await act(client, rid, "claim", token)
    await publish(client, data, page_id, "<p>short</p>")
    await act(client, rid, "complete", token, result_version=2)
    await client.post(f"/v1/comments/{first['id']}/resolve", headers=auth(data))
    await client.patch(
        f"/v1/comments/{first['id']}", json={"body": "@agent shorter"}, headers=auth(data)
    )
    await client.delete(f"/v1/comments/{first['id']}", headers=auth(data))
    assert await types() == [
        "version.published",
        "comment.created",
        "request.created",
        "request.claimed",
        "version.published",
        "comment.created",  # the agent's reply
        "request.completed",
        "comment.resolved",
        "comment.updated",
        "comment.deleted",
    ]
    created = (await stored("request.created"))[0].payload
    assert created["request_id"] == rid
    assert created["body"] == "@agent shorten"
    assert created["base_version"] == 1
    assert (await stored("comment.created"))[0].payload["request_id"] == rid


async def test_dismiss_and_mention_removed_are_recorded(client):
    data, page_id = await setup(client)
    one = await ask(client, data, page_id)
    await client.post(f"/v1/requests/{one}/dismiss", json={"reason": "no"}, headers=auth(data))
    two = (await comment(client, data, page_id, "@agent again")).json()
    await client.patch(f"/v1/comments/{two['id']}", json={"body": "never mind"}, headers=auth(data))
    dismissed = await stored("request.dismissed")
    assert [d.payload["reason"] for d in dismissed] == ["no", "The mention was removed"]


async def test_an_expired_claim_is_recorded_as_reopened(client):
    from .test_sharing import age_rows

    data, page_id = await setup(client)
    rid = await ask(client, data, page_id)
    token = await agent(client, data)
    await act(client, rid, "claim", token, minutes=1)
    await age_rows("revision_requests", "claim_expires_at", 1)
    await client.get("/v1/requests", headers=auth(token=token))
    reopened = await stored("request.reopened")
    assert [r.payload["request_id"] for r in reopened] == [rid]


async def test_membership_is_recorded(client):
    data, page_id = await setup(client)
    async with other() as bo:
        bo_data, _ = await share(client, data, page_id, bo, "viewer")
        await bo.delete(
            f"/v1/pages/{page_id}/members/{bo_data['user']['id']}", headers=auth(bo_data)
        )
    added, removed = await stored("member.added"), await stored("member.removed")
    assert added[0].payload["role"] == "viewer"
    assert removed[0].payload["left"] is True


async def test_a_refused_action_leaves_no_event(client):
    data, page_id = await setup(client)
    async with other() as bo:
        bo_data, _ = await share(client, data, page_id, bo, "viewer")
        before = len(await stored())
        assert (await comment(bo, bo_data, page_id)).status_code == 403
    assert len(await stored()) == before


async def test_events_are_pushed_only_after_the_commit(client):
    data, page_id = await setup(client)
    other_page = (await new_page(client, data, title="Two"))["page"]
    sub = events.hub.subscribe()
    try:
        # Taking a slug that is in use fails at commit, so the event must not go out.
        clash = await client.patch(
            f"/v1/pages/{page_id}", json={"slug": other_page["slug"]}, headers=auth(data)
        )
        assert clash.status_code == 409
        assert sub.queue.empty()
        await comment(client, data, page_id, "hello")
        assert sub.queue.get_nowait()["type"] == "comment.created"
    finally:
        events.hub.unsubscribe(sub)
    assert not events.hub.subscriptions


def test_a_slow_listener_is_marked_lost():
    sub = events.hub.subscribe()
    try:
        for n in range(events.QUEUE_SIZE + 1):
            events.hub.publish({"id": n})
        assert sub.lost is True
    finally:
        events.hub.unsubscribe(sub)


# ------------------------------------------------------------ streams


class Stream:
    """Runs the app directly, so a stream can stay open while the test reads from it."""

    def __init__(self, path: str, headers: dict):
        self.status = None
        self.body = asyncio.Queue()
        self.started = asyncio.Event()
        self.stop = asyncio.Event()
        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
            "client": ("127.0.0.1", 5000),
            "server": ("test", 80),
            "scheme": "http",
        }

        async def receive():
            await self.stop.wait()
            return {"type": "http.disconnect"}

        async def send(message):
            if message["type"] == "http.response.start":
                self.status = message["status"]
                self.started.set()
            elif message.get("body"):
                await self.body.put(message["body"].decode())

        self.task = asyncio.create_task(app(scope, receive, send))

    async def chunk(self, timeout: float = 3) -> str:
        return await asyncio.wait_for(self.body.get(), timeout)

    async def frame(self) -> tuple[str, dict]:
        """The next event, skipping comments such as pings."""
        while True:
            text = await self.chunk()
            if text.startswith(":"):
                continue
            lines = dict(line.split(": ", 1) for line in text.strip().split("\n"))
            return lines["event"], json.loads(lines["data"])

    async def nothing_more(self, wait: float = 0.3) -> bool:
        try:
            while True:
                if not (await asyncio.wait_for(self.body.get(), wait)).startswith(":"):
                    return False
        except TimeoutError:
            return True

    async def close(self) -> None:
        self.stop.set()
        await asyncio.wait_for(self.task, 3)


async def open_stream(path: str, headers: dict) -> Stream:
    s = Stream(path, headers)
    await asyncio.wait_for(s.started.wait(), 3)
    if s.status == 200:
        assert (await s.chunk()).startswith(": connected")
    return s


async def test_a_page_stream_delivers_new_events(client):
    data, page_id = await setup(client)
    stream = await open_stream(f"/v1/pages/{page_id}/events", auth(data))
    try:
        assert stream.status == 200
        await comment(client, data, page_id, "@agent hi")
        names = [(await stream.frame())[0] for _ in range(2)]
        assert names == ["comment.created", "request.created"]
    finally:
        await stream.close()
    assert not events.hub.subscriptions


async def test_the_page_stream_ignores_other_pages(client):
    data, page_id = await setup(client)
    other_page = (await new_page(client, data, title="Two"))["page"]["id"]
    stream = await open_stream(f"/v1/pages/{page_id}/events", auth(data))
    try:
        await comment(client, data, other_page, "elsewhere")
        assert await stream.nothing_more()
        await comment(client, data, page_id, "here")
        name, body = await stream.frame()
        assert name == "comment.created"
        assert body["page_id"] == page_id
        assert body["data"]["body"] == "here"
    finally:
        await stream.close()


async def test_the_all_pages_stream_and_event_shape(client):
    data, page_id = await setup(client)
    two = (await new_page(client, data, title="Two"))["page"]["id"]
    token = await agent(client, data, scopes=("events:read",))
    stream = await open_stream("/v1/events", auth(token=token))
    try:
        await comment(client, data, page_id, "one")
        await comment(client, data, two, "two")
        a, b = await stream.frame(), await stream.frame()
        assert a[1]["page_id"] == page_id and b[1]["page_id"] == two
        assert set(a[1]) == {"id", "type", "page_id", "created_at", "data"}
        assert b[1]["id"] > a[1]["id"]
    finally:
        await stream.close()


async def test_stream_frames_carry_the_event_id(client):
    data, page_id = await setup(client)
    stream = await open_stream(f"/v1/pages/{page_id}/events", auth(data))
    try:
        await comment(client, data, page_id, "x")
        text = await stream.chunk()
        row = (await stored("comment.created"))[0]
        assert text.startswith(f"id: {row.id}\nevent: comment.created\ndata: ")
        assert text.endswith("\n\n")
    finally:
        await stream.close()


async def test_connecting_needs_the_right_scope_and_access(client):
    data, page_id = await setup(client)
    no_scope = await agent(client, data, scopes=("pages:read",))
    for path in ("/v1/events", f"/v1/pages/{page_id}/events"):
        s = await open_stream(path, auth(token=no_scope))
        assert s.status == 403
        await s.close()
    s = await open_stream("/v1/events", {})
    assert s.status == 401
    await s.close()
    async with other() as bo:
        bo_data = await signup(bo, **BO)
        s = await open_stream(f"/v1/pages/{page_id}/events", auth(bo_data))
        assert s.status == 404
        await s.close()
    s = await open_stream("/v1/events", {**auth(data), "Last-Event-ID": "abc"})
    assert s.status == 422
    await s.close()


async def test_reconnecting_replays_what_was_missed(client):
    data, page_id = await setup(client)
    await comment(client, data, page_id, "one")
    await comment(client, data, page_id, "two")
    first = (await stored("comment.created"))[0].id
    stream = await open_stream(
        f"/v1/pages/{page_id}/events", {**auth(data), "Last-Event-ID": str(first)}
    )
    try:
        name, body = await stream.frame()
        assert (name, body["data"]["body"]) == ("comment.created", "two")
        assert await stream.nothing_more()
        await comment(client, data, page_id, "three")  # then live events carry on
        assert (await stream.frame())[1]["data"]["body"] == "three"
    finally:
        await stream.close()


async def test_replay_only_covers_pages_the_person_can_see(client):
    data, page_id = await setup(client)
    await new_page(client, data, title="Private two")
    await comment(client, data, page_id, "private note")
    async with other() as bo:
        bo_data = await signup(bo, **BO)
        s = await open_stream("/v1/events", {**auth(bo_data), "Last-Event-ID": "0"})
        try:
            assert await s.nothing_more()
        finally:
            await s.close()


async def test_too_many_missed_events_ask_for_a_refetch(client, monkeypatch):
    monkeypatch.setattr(events, "MAX_REPLAY", 2)
    data, page_id = await setup(client)
    for n in range(3):
        await comment(client, data, page_id, f"c{n}")
    s = await open_stream("/v1/events", {**auth(data), "Last-Event-ID": "0"})
    try:
        assert (await s.chunk()).startswith("event: resync")
    finally:
        await s.close()


async def test_a_quiet_stream_sends_pings(client, monkeypatch):
    monkeypatch.setattr(events, "PING_SECONDS", 0.05)
    data, _ = await setup(client)
    s = await open_stream("/v1/events", auth(data))
    try:
        assert (await s.chunk()).startswith(": ping")
    finally:
        await s.close()


async def test_members_hear_page_events_until_they_lose_access(client):
    data, page_id = await setup(client)
    async with other() as bo:
        bo_data, _ = await share(client, data, page_id, bo, "viewer")
        stream = await open_stream(f"/v1/pages/{page_id}/events", auth(bo_data))
        try:
            await comment(client, data, page_id, "for everyone")
            assert (await stream.frame())[0] == "comment.created"
            # Who joined or left is for the owner only.
            await client.delete(
                f"/v1/pages/{page_id}/members/{bo_data['user']['id']}", headers=auth(data)
            )
            assert await stream.nothing_more()
            await comment(client, data, page_id, "after removal")
            assert await stream.nothing_more()
        finally:
            await stream.close()


async def test_a_private_page_goes_quiet_for_members(client):
    data, page_id = await setup(client)
    async with other() as bo:
        bo_data, _ = await share(client, data, page_id, bo, "viewer")
        stream = await open_stream("/v1/events", auth(bo_data))
        try:
            await client.patch(
                f"/v1/pages/{page_id}", json={"visibility": "private"}, headers=auth(data)
            )
            await comment(client, data, page_id, "hidden")
            assert await stream.nothing_more()
        finally:
            await stream.close()


async def test_the_owner_hears_about_a_deleted_page(client):
    data, page_id = await setup(client)
    stream = await open_stream("/v1/events", auth(data))
    try:
        await client.delete(f"/v1/pages/{page_id}", headers=auth(data))
        assert (await stream.frame())[0] == "page.deleted"
    finally:
        await stream.close()


async def test_a_stream_does_not_hold_a_database_connection(client):
    data, _ = await setup(client)
    streams = [await open_stream("/v1/events", auth(data)) for _ in range(8)]
    try:
        # More streams than the pool allows connections. Normal requests must still work.
        assert (await client.get("/v1/me", headers=auth(data))).status_code == 200
    finally:
        for s in streams:
            await s.close()


@pytest.fixture(autouse=True)
def _clean_hub():
    yield
    events.hub.subscriptions.clear()


_ = (make_token,)
