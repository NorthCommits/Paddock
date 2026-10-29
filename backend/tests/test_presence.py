import asyncio

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PagePresence
from app.db.session import get_engine
from app.services import events

from .helpers import auth, make_token
from .test_approvals import member
from .test_comments import setup


def capture(monkeypatch):
    pushed = []
    monkeypatch.setattr(events, "push", lambda *a, **k: pushed.append((a, k)))
    return pushed


async def beat(client, data, page_id):
    return await client.post(f"/v1/pages/{page_id}/presence", headers=auth(data))


async def people(client, data, page_id):
    r = await client.get(f"/v1/pages/{page_id}/people", headers=auth(data))
    assert r.status_code == 200, r.text
    return {p["handle"]: p for p in r.json()["items"]}


async def age(seconds: int):
    async with AsyncSession(get_engine()) as db:
        await db.execute(
            text(f"update page_presence set last_seen_at = now() - interval '{seconds} seconds'")
        )
        await db.commit()


async def test_a_heartbeat_marks_the_person_here_and_tells_others_once(client, monkeypatch):
    pushed = capture(monkeypatch)
    data, page_id = await setup(client)
    assert (await beat(client, data, page_id)).status_code == 204
    assert (await people(client, data, page_id))["ana"]["here"] is True
    assert len(pushed) == 1
    (args, _) = pushed[0]
    assert args[1] == "presence.changed" and args[2]["here"] is True
    await beat(client, data, page_id)
    assert len(pushed) == 1  # still here, nothing new to say


async def test_a_person_disappears_after_45_seconds(client):
    data, page_id = await setup(client)
    await beat(client, data, page_id)
    await age(40)
    assert (await people(client, data, page_id))["ana"]["here"] is True
    await age(46)
    assert (await people(client, data, page_id))["ana"]["here"] is False


async def test_coming_back_after_expiry_is_announced_again(client, monkeypatch):
    pushed = capture(monkeypatch)
    data, page_id = await setup(client)
    await beat(client, data, page_id)
    await age(60)
    await beat(client, data, page_id)
    assert len(pushed) == 2


async def test_leaving_removes_the_person_and_tells_others(client, monkeypatch):
    pushed = capture(monkeypatch)
    data, page_id = await setup(client)
    await beat(client, data, page_id)
    r = await client.delete(f"/v1/pages/{page_id}/presence", headers=auth(data))
    assert r.status_code == 204
    assert (await people(client, data, page_id))["ana"]["here"] is False
    assert pushed[-1][0][2]["here"] is False
    again = await client.delete(f"/v1/pages/{page_id}/presence", headers=auth(data))
    assert again.status_code == 204
    assert len(pushed) == 2  # leaving twice says nothing new


async def test_people_lists_only_those_with_access(client):
    data, page_id = await setup(client)
    assert set(await people(client, data, page_id)) == {"ana"}  # private page
    bo, bo_data = await member(client, data, page_id, "bo@example.com", "bobby", "viewer")
    assert set(await people(client, data, page_id)) == {"ana", "bobby"}
    assert set(await people(bo, bo_data, page_id)) == {"ana", "bobby"}
    await bo.aclose()


async def test_a_member_is_shown_here_to_everyone(client):
    data, page_id = await setup(client)
    bo, bo_data = await member(client, data, page_id, "bo@example.com", "bobby", "viewer")
    await beat(bo, bo_data, page_id)
    assert (await people(client, data, page_id))["bobby"]["here"] is True
    await bo.aclose()


async def test_strangers_get_404_and_agents_get_403(client):
    data, page_id = await setup(client)
    stranger = await member_free_stranger()
    assert (await beat(stranger[0], stranger[1], page_id)).status_code == 404
    assert (
        await stranger[0].get(f"/v1/pages/{page_id}/people", headers=auth(stranger[1]))
    ).status_code == 404
    token = (await make_token(client, data, scopes=("pages:read", "comments:write")))["token"]
    for call in (
        client.post(f"/v1/pages/{page_id}/presence", headers=auth(token=token)),
        client.delete(f"/v1/pages/{page_id}/presence", headers=auth(token=token)),
        client.get(f"/v1/pages/{page_id}/people", headers=auth(token=token)),
    ):
        assert (await call).status_code == 403
    await stranger[0].aclose()


async def member_free_stranger():
    from .helpers import signup
    from .test_sharing import other

    client = other()
    return client, await signup(client, email="zed@example.com", handle="zed")


async def test_a_removed_member_gets_404(client):
    data, page_id = await setup(client)
    bo, bo_data = await member(client, data, page_id, "bo@example.com", "bobby", "viewer")
    assert (await beat(bo, bo_data, page_id)).status_code == 204
    await client.patch(f"/v1/pages/{page_id}", json={"visibility": "private"}, headers=auth(data))
    assert (await beat(bo, bo_data, page_id)).status_code == 404
    await bo.aclose()


async def test_two_heartbeats_at_once_keep_one_row(client):
    data, page_id = await setup(client)
    a, b = await asyncio.gather(beat(client, data, page_id), beat(client, data, page_id))
    assert a.status_code == 204 and b.status_code == 204
    async with AsyncSession(get_engine()) as db:
        assert await db.scalar(select(func.count()).select_from(PagePresence)) == 1
