import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_engine
from app.services import mailer, triggers

from .helpers import auth, mails_to, make_token, signup
from .test_comments import comment, setup
from .test_sharing import invite, other, raw_token

SCOPES = ("comments:read", "comments:write", "requests:act", "pages:read", "pages:write")


async def member(owner, owner_data, page_id, email, handle, role):
    """Someone joins the page. Returns their client and login data."""
    await owner.patch(
        f"/v1/pages/{page_id}", json={"visibility": "members"}, headers=auth(owner_data)
    )
    client = other()
    inv = await invite(owner, owner_data, page_id, email=email, role=role)
    data = await signup(client, email=email, handle=handle)
    r = await client.post(f"/v1/invites/{raw_token(inv['accept_url'])}/accept", headers=auth(data))
    assert r.status_code == 200, r.text
    return client, data


async def agent(client, data):
    return (await make_token(client, data, scopes=SCOPES))["token"]


async def ask(client, data, page_id, body="@agent make it shorter"):
    r = await comment(client, data, page_id, body)
    assert r.status_code == 201, r.text
    return r.json()["request"]


async def listed(client, token, status="open"):
    r = await client.get(f"/v1/requests?status={status}", headers=auth(token=token))
    assert r.status_code == 200, r.text
    return [i["id"] for i in r.json()["items"]]


async def bell(client, data):
    r = await client.get("/v1/notifications", headers=auth(data))
    assert r.status_code == 200, r.text
    return r.json()


async def approve(client, data, rid):
    return await client.post(f"/v1/requests/{rid}/approve", headers=auth(data))


# ------------------------------------------------------------ who is asked


async def test_the_owner_asking_uses_their_own_agent_without_a_yes(client):
    data, page_id = await setup(client)
    request = await ask(client, data, page_id)
    assert request["status"] == "open"
    assert request["approved_by"] is not None
    token = await agent(client, data)
    assert await listed(client, token) == [request["id"]]


async def test_an_editor_with_an_agent_uses_their_own_and_nobody_else_is_asked(client):
    data, page_id = await setup(client)
    await agent(client, data)
    bo, bo_data = await member(client, data, page_id, "bo@example.com", "bobby", "editor")
    bo_token = await agent(bo, bo_data)
    request = await ask(bo, bo_data, page_id)
    assert request["status"] == "open"
    assert await listed(bo, bo_token) == [request["id"]]
    assert (await bell(client, data))["items"] == []
    await bo.aclose()


async def test_a_commenter_request_waits_for_the_owner_and_no_agent_may_touch_it(client):
    data, page_id = await setup(client)
    ana_token = await agent(client, data)
    bo, bo_data = await member(client, data, page_id, "bo@example.com", "bobby", "commenter")
    request = await ask(bo, bo_data, page_id)
    assert request["status"] == "awaiting"
    assert request["asked"] == 1
    # Ana's own agent sees nothing and cannot claim it.
    assert await listed(client, ana_token) == []
    claim = await client.post(
        f"/v1/requests/{request['id']}/claim", json={}, headers=auth(token=ana_token)
    )
    assert claim.status_code == 409
    assert claim.json()["error"]["code"] == "awaiting_approval"
    # Ana is asked in the app and by email.
    news = await bell(client, data)
    assert news["unread"] == 1
    item = news["items"][0]
    assert item["kind"] == "agent_offer"
    assert item["request"]["my_offer"] == "offered"
    assert item["actor"] is not None
    await mailer.finish_sending()
    assert len([m for m in mails_to("ana@example.com") if "needs a yes" in m.subject]) == 1
    await bo.aclose()


async def test_saying_yes_hands_the_request_to_that_persons_agent_only(client):
    data, page_id = await setup(client)
    ana_token = await agent(client, data)
    bo, bo_data = await member(client, data, page_id, "bo@example.com", "bobby", "commenter")
    request = await ask(bo, bo_data, page_id)
    done = await approve(client, data, request["id"])
    assert done.status_code == 200
    assert done.json()["status"] == "open"
    assert await listed(client, ana_token) == [request["id"]]
    claimed = await client.post(
        f"/v1/requests/{request['id']}/claim", json={}, headers=auth(token=ana_token)
    )
    assert claimed.status_code == 200
    # Bo hears that Ana's agent is on it.
    kinds = [i["kind"] for i in (await bell(bo, bo_data))["items"]]
    assert "agent_approved" in kinds
    await bo.aclose()


async def test_an_agent_token_cannot_say_yes(client):
    data, page_id = await setup(client)
    token = await agent(client, data)
    bo, bo_data = await member(client, data, page_id, "bo@example.com", "bobby", "commenter")
    request = await ask(bo, bo_data, page_id)
    r = await client.post(f"/v1/requests/{request['id']}/approve", headers=auth(token=token))
    assert r.status_code == 403
    await bo.aclose()


async def test_saying_yes_needs_a_connected_agent(client):
    data, page_id = await setup(client)  # Ana has no agent
    bo, bo_data = await member(client, data, page_id, "bo@example.com", "bobby", "commenter")
    request = await ask(bo, bo_data, page_id)
    assert request["status"] == "awaiting"
    assert request["asked"] == 0  # nobody has an agent, so nobody was asked
    r = await approve(client, data, request["id"])
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "no_agent"
    await bo.aclose()


# ------------------------------------------------------------ two people say yes


async def test_two_people_saying_yes_at_once_gives_the_request_to_exactly_one(client):
    data, page_id = await setup(client)
    ana_token = await agent(client, data)
    cy, cy_data = await member(client, data, page_id, "cy@example.com", "cyrus", "editor")
    cy_token = await agent(cy, cy_data)
    bo, bo_data = await member(client, data, page_id, "bo@example.com", "bobby", "commenter")
    request = await ask(bo, bo_data, page_id)
    assert request["asked"] == 2

    first, second = await asyncio.gather(
        approve(client, data, request["id"]), approve(cy, cy_data, request["id"])
    )
    codes = sorted([first.status_code, second.status_code])
    assert codes == [200, 409]
    loser = first if first.status_code == 409 else second
    assert loser.json()["error"]["code"] == "taken"
    assert "got there first" in loser.json()["error"]["message"]

    ana_has = await listed(client, ana_token)
    cy_has = await listed(cy, cy_token)
    assert sorted([len(ana_has), len(cy_has)]) == [0, 1]  # never both, never neither
    winner_is_ana = len(ana_has) == 1
    # The loser cannot claim it either.
    loser_client, loser_token = (cy, cy_token) if winner_is_ana else (client, ana_token)
    r = await loser_client.post(
        f"/v1/requests/{request['id']}/claim", json={}, headers=auth(token=loser_token)
    )
    assert r.status_code == 403
    # Their bell shows who took it.
    loser_data = cy_data if winner_is_ana else data
    item = (await bell(loser_client, loser_data))["items"][0]
    assert item["request"]["my_offer"] == "lost"
    assert item["request"]["approved_by"] is not None
    await cy.aclose()
    await bo.aclose()


async def test_a_second_yes_from_the_same_person_is_fine_and_a_late_one_is_told_who_won(client):
    data, page_id = await setup(client)
    await agent(client, data)
    cy, cy_data = await member(client, data, page_id, "cy@example.com", "cyrus", "editor")
    await agent(cy, cy_data)
    bo, bo_data = await member(client, data, page_id, "bo@example.com", "bobby", "commenter")
    request = await ask(bo, bo_data, page_id)
    assert (await approve(client, data, request["id"])).status_code == 200
    assert (await approve(client, data, request["id"])).status_code == 200  # same person
    late = await approve(cy, cy_data, request["id"])
    assert late.status_code == 409
    assert late.json()["error"]["code"] == "taken"
    await cy.aclose()
    await bo.aclose()


async def test_declining_leaves_the_request_for_the_others(client):
    data, page_id = await setup(client)
    await agent(client, data)
    cy, cy_data = await member(client, data, page_id, "cy@example.com", "cyrus", "editor")
    await agent(cy, cy_data)
    bo, bo_data = await member(client, data, page_id, "bo@example.com", "bobby", "commenter")
    request = await ask(bo, bo_data, page_id)
    r = await client.post(f"/v1/requests/{request['id']}/decline", headers=auth(data))
    assert r.status_code == 200
    assert r.json()["status"] == "awaiting"
    assert (await bell(client, data))["items"][0]["request"]["my_offer"] == "declined"
    assert (await approve(cy, cy_data, request["id"])).status_code == 200
    await cy.aclose()
    await bo.aclose()


# ------------------------------------------------------------ preferences and timing


async def test_auto_says_yes_in_advance_and_never_opts_out(client):
    data, page_id = await setup(client)
    ana_token = await agent(client, data)
    bo, bo_data = await member(client, data, page_id, "bo@example.com", "bobby", "commenter")
    auto = await client.patch("/v1/me", json={"agent_approval": "auto"}, headers=auth(data))
    assert auto.status_code == 200 and auto.json()["agent_approval"] == "auto"
    request = await ask(bo, bo_data, page_id)
    assert request["status"] == "open"
    assert await listed(client, ana_token) == [request["id"]]
    assert "agent_approved" in [i["kind"] for i in (await bell(bo, bo_data))["items"]]

    await client.patch("/v1/me", json={"agent_approval": "never"}, headers=auth(data))
    again = await ask(bo, bo_data, page_id, "@agent one more")
    assert again["status"] == "awaiting" and again["asked"] == 0
    assert (await bell(client, data))["items"] == []

    bad = await client.patch("/v1/me", json={"agent_approval": "sometimes"}, headers=auth(data))
    assert bad.status_code == 422
    await bo.aclose()


async def test_a_yes_that_no_agent_acts_on_is_asked_for_again(client):
    data, page_id = await setup(client)
    await agent(client, data)
    cy, cy_data = await member(client, data, page_id, "cy@example.com", "cyrus", "editor")
    cy_token = await agent(cy, cy_data)
    bo, bo_data = await member(client, data, page_id, "bo@example.com", "bobby", "commenter")
    request = await ask(bo, bo_data, page_id)
    await approve(client, data, request["id"])
    async with AsyncSession(get_engine()) as db:
        await db.execute(
            text("update revision_requests set approved_at = now() - interval '31 minutes'")
        )
        await db.commit()
    assert await listed(cy, cy_token) == []  # reading puts it back, still unapproved
    assert (await approve(cy, cy_data, request["id"])).status_code == 200  # Cy may now take it
    await cy.aclose()
    await bo.aclose()


async def test_a_persons_own_request_is_never_asked_for_again(client):
    data, page_id = await setup(client)
    token = await agent(client, data)
    request = await ask(client, data, page_id)
    async with AsyncSession(get_engine()) as db:
        await db.execute(
            text("update revision_requests set approved_at = now() - interval '5 hours'")
        )
        await db.commit()
    assert await listed(client, token) == [request["id"]]


async def test_a_mention_that_comes_back_is_routed_again(client):
    data, page_id = await setup(client)
    await agent(client, data)
    bo, bo_data = await member(client, data, page_id, "bo@example.com", "bobby", "commenter")
    request = await ask(bo, bo_data, page_id)
    await approve(client, data, request["id"])
    cid = (await bo.get(f"/v1/pages/{page_id}/comments", headers=auth(bo_data))).json()["items"][0][
        "id"
    ]
    await bo.patch(f"/v1/comments/{cid}", json={"body": "no mention now"}, headers=auth(bo_data))
    again = await bo.patch(
        f"/v1/comments/{cid}", json={"body": "@agent back again"}, headers=auth(bo_data)
    )
    assert again.status_code == 200
    await bo.aclose()


# ------------------------------------------------------------ the bell


async def test_the_bell_counts_marks_read_and_shows_whether_an_agent_is_connected(client):
    data, page_id = await setup(client)
    quiet = await bell(client, data)
    assert quiet["unread"] == 0 and quiet["agent"]["connected"] is False
    await agent(client, data)
    bo, bo_data = await member(client, data, page_id, "bo@example.com", "bobby", "commenter")
    await ask(bo, bo_data, page_id)
    await ask(bo, bo_data, page_id, "@agent and this")
    news = await bell(client, data)
    assert news["unread"] == 2 and news["agent"]["connected"] is True
    assert (await client.post("/v1/notifications/read", headers=auth(data))).status_code == 204
    assert (await bell(client, data))["unread"] == 0
    # An agent token has no bell.
    token = await agent(client, data)
    assert (await client.get("/v1/notifications", headers=auth(token=token))).status_code == 403
    await bo.aclose()


async def test_the_bell_is_private_to_each_person(client):
    data, page_id = await setup(client)
    await agent(client, data)
    bo, bo_data = await member(client, data, page_id, "bo@example.com", "bobby", "commenter")
    await ask(bo, bo_data, page_id)
    assert (await bell(bo, bo_data))["items"] == []
    await bo.aclose()


# ------------------------------------------------------------ waking an agent


async def test_the_task_address_must_be_a_claude_code_task(client):
    data = await signup(client)
    good = "https://api.anthropic.com/v1/claude_code/routines/trig_01ABC/fire"
    for bad in (
        "http://api.anthropic.com/v1/claude_code/routines/trig_01ABC/fire",
        "https://evil.example.com/v1/claude_code/routines/trig_01ABC/fire",
        "https://api.anthropic.com:8443/v1/claude_code/routines/trig_01ABC/fire",
        "https://api.anthropic.com/v1/messages",
    ):
        r = await client.put(
            "/v1/me/agent-trigger", json={"url": bad, "token": "t"}, headers=auth(data)
        )
        assert r.status_code == 422, bad
    ok = await client.put(
        "/v1/me/agent-trigger", json={"url": good, "token": "sk-secret"}, headers=auth(data)
    )
    assert ok.status_code == 200 and ok.json()["saved"] is True
    assert "sk-secret" not in ok.text  # the token is never sent back
    assert (await client.delete("/v1/me/agent-trigger", headers=auth(data))).status_code == 204
    assert (await client.get("/v1/me/agent-trigger", headers=auth(data))).json()["saved"] is False


async def test_saying_yes_wakes_the_approvers_saved_task(client, monkeypatch):
    knocks = []

    async def fake(url, token, text):
        knocks.append((url, token, text))
        return "started"

    monkeypatch.setattr(triggers, "post_fire", fake)
    data, page_id = await setup(client)
    await agent(client, data)
    url = "https://api.anthropic.com/v1/claude_code/routines/trig_01ABC/fire"
    await client.put(
        "/v1/me/agent-trigger", json={"url": url, "token": "sk-secret"}, headers=auth(data)
    )
    bo, bo_data = await member(client, data, page_id, "bo@example.com", "bobby", "commenter")
    request = await ask(bo, bo_data, page_id, "@agent shorten the intro")
    await triggers.finish_waking()
    assert knocks == []  # nothing is sent until a person says yes
    await approve(client, data, request["id"])
    await triggers.finish_waking()
    assert len(knocks) == 1
    assert knocks[0][0] == url and knocks[0][1] == "sk-secret"
    assert "shorten the intro" in knocks[0][2] and request["id"] in knocks[0][2]
    status = (await client.get("/v1/me/agent-trigger", headers=auth(data))).json()
    assert status["last_result"] == "started" and status["last_fired_at"] is not None
    await bo.aclose()


async def test_the_owners_own_mention_also_wakes_their_task(client, monkeypatch):
    knocks = []

    async def fake(url, token, text):
        knocks.append(text)
        return "started"

    monkeypatch.setattr(triggers, "post_fire", fake)
    data, page_id = await setup(client)
    await agent(client, data)
    url = "https://api.anthropic.com/v1/claude_code/routines/trig_01ABC/fire"
    await client.put("/v1/me/agent-trigger", json={"url": url, "token": "sk"}, headers=auth(data))
    await ask(client, data, page_id)
    await triggers.finish_waking()
    assert len(knocks) == 1
