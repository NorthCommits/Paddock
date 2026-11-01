import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BlockReaction, Event
from app.db.session import get_engine
from app.services import events

from .helpers import auth, make_token
from .test_approvals import member
from .test_comments import setup
from .test_hardening import limits_on, small  # noqa: F401  (limits_on is a fixture)


def capture(monkeypatch):
    pushed = []
    monkeypatch.setattr(events, "push", lambda *a, **k: pushed.append((a, k)))
    return pushed


async def look(client, data, page_id, block="b-1a2b", kind="look"):
    return await client.post(
        f"/v1/pages/{page_id}/focus", json={"block": block, "kind": kind}, headers=auth(data)
    )


async def react(client, data, page_id, block="b-1a2b", key="like", on=True):
    return await client.put(
        f"/v1/pages/{page_id}/reactions",
        json={"block": block, "key": key, "on": on},
        headers=auth(data),
    )


async def reactions(client, data, page_id):
    r = await client.get(f"/v1/pages/{page_id}/reactions", headers=auth(data))
    assert r.status_code == 200, r.text
    return r.json()["items"]


async def count(model) -> int:
    async with AsyncSession(get_engine()) as db:
        return await db.scalar(select(func.count()).select_from(model))


# ------------------------------------------------------------ who is where


async def test_focus_is_relayed_live_and_never_stored(client, monkeypatch):
    pushed = capture(monkeypatch)
    data, page_id = await setup(client)
    before = await count(Event)
    r = await look(client, data, page_id, "b-9z", "select")
    assert r.status_code == 204
    assert await count(Event) == before
    (args, kwargs) = pushed[-1]
    assert args[1] == "focus.changed"
    assert args[2] == {
        "user_id": data["user"]["id"],
        "name": data["user"]["display_name"],
        "block": "b-9z",
        "kind": "select",
    }
    assert kwargs.get("audience") is None


async def test_focus_can_be_cleared_and_is_checked(client, monkeypatch):
    pushed = capture(monkeypatch)
    data, page_id = await setup(client)
    r = await client.post(
        f"/v1/pages/{page_id}/focus", json={"block": None, "kind": "look"}, headers=auth(data)
    )
    assert r.status_code == 204
    assert pushed[-1][0][2]["block"] is None
    for bad in ("", "x" * 65, "has space", "a/b", "<b>"):
        assert (await look(client, data, page_id, bad)).status_code == 422, bad
    assert (await look(client, data, page_id, "ok", "stare")).status_code == 422


async def test_focus_needs_access_and_a_person(client):
    data, page_id = await setup(client)
    other, other_data = await member(client, data, page_id, "bo@example.com", "bobby", "viewer")
    assert (await look(other, other_data, page_id)).status_code == 204  # a viewer may look
    await other.aclose()
    stranger = (await make_token(client, data, scopes=("pages:read", "comments:write")))["token"]
    r = await client.post(
        f"/v1/pages/{page_id}/focus",
        json={"block": "b", "kind": "look"},
        headers=auth(token=stranger),
    )
    assert r.status_code == 403  # agents have no use for it
    missing = await look(client, data, str(uuid.uuid4()))
    assert missing.status_code == 404


async def test_focus_has_its_own_rate_limit(client, limits_on, monkeypatch):  # noqa: F811
    small(monkeypatch, focus=5)
    data, page_id = await setup(client)
    codes = [(await look(client, data, page_id)).status_code for _ in range(8)]
    assert 429 in codes
    assert codes[0] == 204


# ------------------------------------------------------------ reactions


async def test_a_reaction_is_added_once_counted_and_removed(client, monkeypatch):
    pushed = capture(monkeypatch)
    data, page_id = await setup(client)
    assert (await react(client, data, page_id)).status_code == 204
    assert (await react(client, data, page_id)).status_code == 204  # again: still one
    items = await reactions(client, data, page_id)
    assert items == [
        {
            "block": "b-1a2b",
            "key": "like",
            "count": 1,
            "mine": True,
            "who": [data["user"]["display_name"]],
        }
    ]
    assert pushed[-1][0][1] == "reaction.changed"
    assert pushed[-1][0][2]["block"] == "b-1a2b"
    assert (await react(client, data, page_id, on=False)).status_code == 204
    assert (
        await react(client, data, page_id, on=False)
    ).status_code == 204  # removing nothing is fine
    assert await reactions(client, data, page_id) == []


async def test_reactions_add_up_across_people_and_keep_mine_apart(client):
    data, page_id = await setup(client)
    bo, bo_data = await member(client, data, page_id, "bo@example.com", "bobby", "commenter")
    await react(client, data, page_id, key="love")
    await react(bo, bo_data, page_id, key="love")
    await react(bo, bo_data, page_id, key="eyes")
    mine = {(i["key"], i["count"], i["mine"]) for i in await reactions(client, data, page_id)}
    assert mine == {("love", 2, True), ("eyes", 1, False)}
    theirs = {(i["key"], i["count"], i["mine"]) for i in await reactions(bo, bo_data, page_id)}
    assert theirs == {("love", 2, True), ("eyes", 1, True)}
    await bo.aclose()


async def test_only_known_reactions_and_block_names(client):
    data, page_id = await setup(client)
    for key in ("thumbs", "", "LIKE", "👍"):
        assert (await react(client, data, page_id, key=key)).status_code == 422, key
    for block in ("", "x" * 65, "two words", "<img>"):
        assert (await react(client, data, page_id, block=block)).status_code == 422, block


async def test_a_viewer_cannot_react_and_agents_cannot_either(client):
    data, page_id = await setup(client)
    bo, bo_data = await member(client, data, page_id, "bo@example.com", "bobby", "viewer")
    assert (await react(bo, bo_data, page_id)).status_code == 403
    assert (await reactions(bo, bo_data, page_id)) == []  # but they can see them
    await bo.aclose()
    token = (await make_token(client, data, scopes=("pages:read", "comments:write")))["token"]
    r = await client.put(
        f"/v1/pages/{page_id}/reactions",
        json={"block": "b", "key": "like", "on": True},
        headers=auth(token=token),
    )
    assert r.status_code == 403
    r = await client.get(f"/v1/pages/{page_id}/reactions", headers=auth(token=token))
    assert r.status_code == 403


async def test_strangers_see_nothing_of_reactions(client):
    data, page_id = await setup(client)
    await react(client, data, page_id)
    from .helpers import signup
    from .test_sharing import other

    async with other() as eve:
        eve_data = await signup(eve, email="eve@example.com", handle="eve")
        assert (await react(eve, eve_data, page_id)).status_code == 404
        r = await eve.get(f"/v1/pages/{page_id}/reactions", headers=auth(eve_data))
        assert r.status_code == 404


async def test_one_person_cannot_pile_up_reactions(client):
    data, page_id = await setup(client)
    codes = []
    for i in range(205):
        codes.append((await react(client, data, page_id, block=f"b-{i}")).status_code)
    assert codes[:200] == [204] * 200
    assert set(codes[200:]) == {409}
    assert await count(BlockReaction) == 200


async def test_reactions_go_when_the_page_goes(client):
    data, page_id = await setup(client)
    await react(client, data, page_id)
    assert await count(BlockReaction) == 1
    r = await client.delete(f"/v1/pages/{page_id}", headers=auth(data))
    assert r.status_code == 204
    r = await client.get(f"/v1/pages/{page_id}/reactions", headers=auth(data))
    assert r.status_code == 404


async def test_two_identical_reactions_at_once_are_not_an_error(client, monkeypatch):
    data, page_id = await setup(client)
    assert (await react(client, data, page_id)).status_code == 204
    real = AsyncSession.scalar

    async def blind_first(self, stmt, *a, **k):
        if str(stmt).startswith("SELECT block_reactions.id"):
            return None  # the "is it there?" check misses
        return await real(self, stmt, *a, **k)

    monkeypatch.setattr(AsyncSession, "scalar", blind_first)
    assert (await react(client, data, page_id)).status_code == 204
    monkeypatch.undo()
    assert await count(BlockReaction) == 1
