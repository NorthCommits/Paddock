from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Event, PageMessage
from app.db.session import get_engine
from app.services import events, mailer, retention

from .helpers import auth, mails_to, make_token
from .test_approvals import member
from .test_comments import setup
from .test_hardening import limits_on, small  # noqa: F401  (fixture used by name)


def capture(monkeypatch):
    pushed = []
    monkeypatch.setattr(events, "push", lambda *a, **k: pushed.append((a, k)))
    return pushed


async def say(client, data, page_id, body="hello", to=None):
    payload = {"body": body, **({"to": to} if to else {})}
    return await client.post(f"/v1/pages/{page_id}/messages", json=payload, headers=auth(data))


async def thread(client, data, page_id, with_id=None, **extra):
    params = {**({"with": with_id} if with_id else {}), **extra}
    r = await client.get(f"/v1/pages/{page_id}/messages", params=params, headers=auth(data))
    assert r.status_code == 200, r.text
    return r.json()


async def count(model) -> int:
    async with AsyncSession(get_engine()) as db:
        return await db.scalar(select(func.count()).select_from(model))


async def test_a_viewer_can_read_and_write_the_page_chat(client):
    data, page_id = await setup(client)
    bo, bo_data = await member(client, data, page_id, "bo@example.com", "bobby", "viewer")
    sent = await say(bo, bo_data, page_id, "hi all")
    assert sent.status_code == 201
    assert sent.json()["body"] == "hi all" and sent.json()["to"] is None
    seen = await thread(client, data, page_id)
    assert [m["body"] for m in seen["items"]] == ["hi all"]
    assert seen["items"][0]["sender"]["handle"] == "bobby" and seen["more"] is False
    await bo.aclose()


async def test_a_private_message_is_seen_only_by_the_two_people(client):
    data, page_id = await setup(client)
    bo, bo_data = await member(client, data, page_id, "bo@example.com", "bobby", "viewer")
    cy, cy_data = await member(client, data, page_id, "cy@example.com", "cyrus", "commenter")
    ana, bobby = data["user"]["id"], bo_data["user"]["id"]
    assert (await say(bo, bo_data, page_id, "just you", to=ana)).status_code == 201
    assert (await say(client, data, page_id, "and you", to=bobby)).status_code == 201
    mine = await thread(client, data, page_id, bobby)
    assert [m["body"] for m in mine["items"]] == ["just you", "and you"]
    theirs = await thread(bo, bo_data, page_id, ana)
    assert [m["body"] for m in theirs["items"]] == ["just you", "and you"]
    # A third person, including no one with more rights, sees nothing of it.
    assert (await thread(cy, cy_data, page_id, ana))["items"] == []
    assert (await thread(cy, cy_data, page_id, bobby))["items"] == []
    assert (await thread(client, data, page_id))["items"] == []  # the page chat has none of it
    await bo.aclose()
    await cy.aclose()


async def test_a_private_message_to_someone_without_access_is_refused(client):
    from .helpers import signup
    from .test_sharing import other

    data, page_id = await setup(client)
    zed = other()
    zed_data = await signup(zed, email="zed@example.com", handle="zed")
    r = await say(client, data, page_id, "psst", to=zed_data["user"]["id"])
    assert r.status_code == 422
    assert await count(PageMessage) == 0
    own = await say(client, data, page_id, "me", to=data["user"]["id"])
    assert own.status_code == 422
    await zed.aclose()


async def test_a_removed_member_loses_the_chat(client):
    data, page_id = await setup(client)
    bo, bo_data = await member(client, data, page_id, "bo@example.com", "bobby", "viewer")
    assert (await say(bo, bo_data, page_id)).status_code == 201
    await client.patch(f"/v1/pages/{page_id}", json={"visibility": "private"}, headers=auth(data))
    assert (await say(bo, bo_data, page_id)).status_code == 404
    r = await bo.get(f"/v1/pages/{page_id}/messages", headers=auth(bo_data))
    assert r.status_code == 404
    await bo.aclose()


async def test_empty_and_overlong_messages_are_refused_and_text_is_trimmed(client):
    data, page_id = await setup(client)
    assert (await say(client, data, page_id, "   ")).status_code == 422
    assert (await say(client, data, page_id, "x" * 1001)).status_code == 422
    ok = await say(client, data, page_id, "  padded  ")
    assert ok.status_code == 201 and ok.json()["body"] == "padded"
    assert (await say(client, data, page_id, "y" * 1000)).status_code == 201


async def test_who_may_delete_a_message(client):
    data, page_id = await setup(client)
    bo, bo_data = await member(client, data, page_id, "bo@example.com", "bobby", "viewer")
    cy, cy_data = await member(client, data, page_id, "cy@example.com", "cyrus", "viewer")
    mid = (await say(bo, bo_data, page_id, "oops")).json()["id"]
    assert (await cy.delete(f"/v1/messages/{mid}", headers=auth(cy_data))).status_code == 403
    assert (
        await client.delete(f"/v1/messages/{mid}", headers=auth(data))
    ).status_code == 204  # owner
    gone = (await thread(client, data, page_id))["items"][0]
    assert gone["deleted"] is True and gone["body"] == ""
    mine = (await say(bo, bo_data, page_id, "mine")).json()["id"]
    assert (await bo.delete(f"/v1/messages/{mine}", headers=auth(bo_data))).status_code == 204
    private = (await say(bo, bo_data, page_id, "secret", to=data["user"]["id"])).json()["id"]
    assert (await client.delete(f"/v1/messages/{private}", headers=auth(data))).status_code == 403
    assert (await cy.delete(f"/v1/messages/{private}", headers=auth(cy_data))).status_code == 404
    assert (await bo.delete(f"/v1/messages/{private}", headers=auth(bo_data))).status_code == 204
    await bo.aclose()
    await cy.aclose()


async def test_a_private_message_notifies_only_someone_who_is_away(client):
    data, page_id = await setup(client)
    bo, bo_data = await member(client, data, page_id, "bo@example.com", "bobby", "viewer")
    ana = data["user"]["id"]
    await say(bo, bo_data, page_id, "are you there?", to=ana)
    items = (await client.get("/v1/notifications", headers=auth(data))).json()["items"]
    assert [i["kind"] for i in items] == ["chat_message"]
    assert items[0]["body"].startswith("bobby") or "are you there?" in items[0]["body"]
    await client.post(f"/v1/pages/{page_id}/presence", headers=auth(data))  # Ana arrives
    await say(bo, bo_data, page_id, "welcome", to=ana)
    items = (await client.get("/v1/notifications", headers=auth(data))).json()["items"]
    assert len(items) == 1  # no second bell while she is on the page
    await say(bo, bo_data, page_id, "page wide")  # a page message never rings the bell
    assert len((await client.get("/v1/notifications", headers=auth(data))).json()["items"]) == 1
    await mailer.finish_sending()
    assert mails_to("ana@example.com") == []
    await bo.aclose()


async def test_messages_are_not_stored_as_events(client, monkeypatch):
    pushed = capture(monkeypatch)
    data, page_id = await setup(client)
    before = await count(Event)
    await say(client, data, page_id, "quiet")
    assert await count(Event) == before
    assert pushed and pushed[-1][0][1] == "message.created"


async def test_push_audience_is_the_two_people_for_private_and_open_for_the_page(
    client, monkeypatch
):
    pushed = capture(monkeypatch)
    data, page_id = await setup(client)
    bo, bo_data = await member(client, data, page_id, "bo@example.com", "bobby", "viewer")
    await say(client, data, page_id, "to all")
    assert pushed[-1][1].get("audience") is None
    await say(client, data, page_id, "to bo", to=bo_data["user"]["id"])
    audience = {str(a) for a in pushed[-1][1]["audience"]}
    assert audience == {data["user"]["id"], bo_data["user"]["id"]}
    data_out = pushed[-1][0][2]
    assert data_out["sender_id"] == data["user"]["id"]
    await bo.aclose()


async def test_agent_tokens_cannot_use_the_chat(client):
    data, page_id = await setup(client)
    token = (await make_token(client, data, scopes=("pages:read", "comments:write")))["token"]
    r = await client.post(
        f"/v1/pages/{page_id}/messages", json={"body": "hi"}, headers=auth(token=token)
    )
    assert r.status_code == 403
    r = await client.get(f"/v1/pages/{page_id}/messages", headers=auth(token=token))
    assert r.status_code == 403


async def test_the_21st_message_in_a_minute_is_refused(client, limits_on, monkeypatch):  # noqa: F811
    small(monkeypatch, general=1000)
    data, page_id = await setup(client)
    for _ in range(20):
        assert (await say(client, data, page_id)).status_code == 201
    assert (await say(client, data, page_id)).status_code == 429


async def test_pages_of_50_newest_come_oldest_first(client):
    data, page_id = await setup(client)
    for n in range(55):
        await say(client, data, page_id, f"m{n}")
    first = await thread(client, data, page_id)
    assert len(first["items"]) == 50 and first["more"] is True
    assert first["items"][0]["body"] == "m5" and first["items"][-1]["body"] == "m54"
    older = await thread(client, data, page_id, before=first["items"][0]["created_at"])
    assert [m["body"] for m in older["items"]] == ["m0", "m1", "m2", "m3", "m4"]
    assert older["more"] is False


async def test_retention_removes_messages_older_than_30_days(client):
    data, page_id = await setup(client)
    await say(client, data, page_id, "old")
    await say(client, data, page_id, "new")
    async with AsyncSession(get_engine()) as db:
        await db.execute(
            text(
                "update page_messages set created_at = now() - interval '31 days' "
                "where body = 'old'"
            )
        )
        await db.commit()
        assert await retention.purge_old_messages(db) == 1
    assert [m["body"] for m in (await thread(client, data, page_id))["items"]] == ["new"]
