import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChatRead
from app.db.session import get_engine
from app.services import events

from .helpers import auth, make_token
from .test_approvals import member
from .test_chat import say, thread
from .test_comments import setup
from .test_hardening import limits_on, small  # noqa: F401  (limits_on is a fixture)


def capture(monkeypatch):
    pushed = []
    monkeypatch.setattr(events, "push", lambda *a, **k: pushed.append((a, k)))
    return pushed


async def read(client, data, page_id, up_to, with_id=None):
    return await client.put(
        f"/v1/pages/{page_id}/chat-read",
        json={"up_to": up_to, **({"with": with_id} if with_id else {})},
        headers=auth(data),
    )


async def mine(client, data, page_id, with_id=None):
    return (await thread(client, data, page_id, with_id))["items"]


async def count() -> int:
    async with AsyncSession(get_engine()) as db:
        return await db.scalar(select(func.count()).select_from(ChatRead))


async def test_a_private_message_is_seen_once_the_other_person_reads_it(client):
    data, page_id = await setup(client)
    bo, bo_data = await member(client, data, page_id, "bo@example.com", "bobby", "viewer")
    ana, bobby = data["user"]["id"], bo_data["user"]["id"]
    sent = (await say(client, data, page_id, "psst", to=bobby)).json()
    first = (await mine(client, data, page_id, bobby))[0]
    assert first["seen_by"] == [] and first["audience"] == 1
    assert (await read(bo, bo_data, page_id, sent["id"], ana)).status_code == 204
    seen = (await mine(client, data, page_id, bobby))[0]
    assert [s["id"] for s in seen["seen_by"]] == [bobby] and seen["audience"] == 1
    # The reader's own view of that message carries no receipt.
    theirs = (await mine(bo, bo_data, page_id, ana))[0]
    assert theirs["seen_by"] == [] and theirs["audience"] == 0
    await bo.aclose()


async def test_a_page_wide_message_is_seen_by_each_member_who_reads_it(client):
    data, page_id = await setup(client)
    bo, bo_data = await member(client, data, page_id, "bo@example.com", "bobby", "viewer")
    cy, cy_data = await member(client, data, page_id, "cy@example.com", "cyrus", "commenter")
    sent = (await say(client, data, page_id, "hello all")).json()
    await read(bo, bo_data, page_id, sent["id"])
    one = (await mine(client, data, page_id))[0]
    assert len(one["seen_by"]) == 1 and one["audience"] == 2
    assert one["seen_by"][0]["name"] == bo_data["user"]["display_name"]
    await read(cy, cy_data, page_id, sent["id"])
    two = (await mine(client, data, page_id))[0]
    assert len(two["seen_by"]) == 2 and two["audience"] == 2
    await bo.aclose()
    await cy.aclose()


async def test_reading_a_later_message_covers_the_earlier_ones_and_never_goes_back(client):
    data, page_id = await setup(client)
    bo, bo_data = await member(client, data, page_id, "bo@example.com", "bobby", "viewer")
    a = (await say(client, data, page_id, "one")).json()
    b = (await say(client, data, page_id, "two")).json()
    await read(bo, bo_data, page_id, b["id"])
    assert [len(m["seen_by"]) for m in await mine(client, data, page_id)] == [1, 1]
    await read(bo, bo_data, page_id, a["id"])  # an older message does not undo it
    assert [len(m["seen_by"]) for m in await mine(client, data, page_id)] == [1, 1]
    assert await count() == 1
    await bo.aclose()


async def test_only_messages_in_that_conversation_can_be_marked(client):
    data, page_id = await setup(client)
    bo, bo_data = await member(client, data, page_id, "bo@example.com", "bobby", "viewer")
    cy, cy_data = await member(client, data, page_id, "cy@example.com", "cyrus", "commenter")
    ana, bobby = data["user"]["id"], bo_data["user"]["id"]
    private = (await say(client, data, page_id, "just bobby", to=bobby)).json()
    wide = (await say(client, data, page_id, "everyone")).json()
    # Cyrus is not in that private thread: it does not exist for him.
    assert (await read(cy, cy_data, page_id, private["id"], ana)).status_code == 404
    assert (await read(cy, cy_data, page_id, private["id"])).status_code == 404
    # A page-wide message cannot be marked as a private thread, nor the other way round.
    assert (await read(bo, bo_data, page_id, wide["id"], ana)).status_code == 404
    assert (await read(bo, bo_data, page_id, private["id"])).status_code == 404
    assert (await read(bo, bo_data, page_id, str(uuid.uuid4()))).status_code == 404
    assert await count() == 0
    await bo.aclose()
    await cy.aclose()


async def test_only_the_senders_hear_who_read(client, monkeypatch):
    data, page_id = await setup(client)
    bo, bo_data = await member(client, data, page_id, "bo@example.com", "bobby", "viewer")
    ana, bobby = data["user"]["id"], bo_data["user"]["id"]
    private = (await say(client, data, page_id, "psst", to=bobby)).json()
    pushed = capture(monkeypatch)
    await read(bo, bo_data, page_id, private["id"], ana)
    (args, kwargs) = pushed[-1]
    assert args[1] == "chat.read"
    assert args[2] == {"reader_id": bobby, "scope": "private"}
    assert kwargs["audience"] == [uuid.UUID(ana)]
    wide = (await say(client, data, page_id, "hi")).json()
    await read(bo, bo_data, page_id, wide["id"])
    (args, kwargs) = pushed[-1]
    assert args[2] == {"reader_id": bobby, "scope": "all"}
    assert kwargs["audience"] == [uuid.UUID(ana)]  # not everyone on the page
    before = len(pushed)
    await read(bo, bo_data, page_id, wide["id"])  # nothing new was read, so nothing is announced
    assert len(pushed) == before
    await bo.aclose()


async def test_reading_your_own_message_changes_nothing(client):
    data, page_id = await setup(client)
    wide = (await say(client, data, page_id, "me")).json()
    assert (await read(client, data, page_id, wide["id"])).status_code == 204
    assert (await mine(client, data, page_id))[0]["seen_by"] == []


async def test_agents_and_strangers_cannot_mark_anything(client):
    data, page_id = await setup(client)
    sent = (await say(client, data, page_id, "hi")).json()
    token = (await make_token(client, data, scopes=("pages:read", "comments:write")))["token"]
    r = await client.put(
        f"/v1/pages/{page_id}/chat-read", json={"up_to": sent["id"]}, headers=auth(token=token)
    )
    assert r.status_code == 403
    from .helpers import signup
    from .test_sharing import other

    async with other() as eve:
        eve_data = await signup(eve, email="eve@example.com", handle="eve")
        assert (await read(eve, eve_data, page_id, sent["id"])).status_code == 404


async def test_nothing_can_be_marked_once_the_page_is_gone(client):
    data, page_id = await setup(client)
    bo, bo_data = await member(client, data, page_id, "bo@example.com", "bobby", "viewer")
    sent = (await say(client, data, page_id, "hi")).json()
    await read(bo, bo_data, page_id, sent["id"])
    assert (await client.delete(f"/v1/pages/{page_id}", headers=auth(data))).status_code == 204
    assert (await read(bo, bo_data, page_id, sent["id"])).status_code == 404
    await bo.aclose()


async def test_marking_has_its_own_rate_limit(client, limits_on, monkeypatch):  # noqa: F811
    small(monkeypatch, chatread=3)
    data, page_id = await setup(client)
    sent = (await say(client, data, page_id, "hi")).json()
    codes = [(await read(client, data, page_id, sent["id"])).status_code for _ in range(6)]
    assert 429 in codes and codes[0] == 204
