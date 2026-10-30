"""Briefs on requests, the page context note, and agents asking questions."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Notification
from app.db.session import get_engine

from .helpers import auth
from .test_approvals import approve, member
from .test_approvals import ask as ask_as_person
from .test_comments import comment, setup
from .test_requests import act, agent, ask


async def put(client, data, path, **body):
    return await client.put(path, json=body, headers=auth(data))


# ------------------------------------------------------------ A: the brief


async def test_a_brief_travels_with_the_request(client):
    data, page_id = await setup(client)
    r = await comment(
        client, data, page_id, "@agent tighten the intro", brief="Goal: 2 lines. Tone: formal."
    )
    assert r.status_code == 201, r.text
    request = r.json()["request"]
    assert request["brief"] == "Goal: 2 lines. Tone: formal."
    token = await agent(client, data)
    items = (await client.get("/v1/requests?status=open", headers=auth(token=token))).json()[
        "items"
    ]
    assert items[0]["brief"] == "Goal: 2 lines. Tone: formal."


async def test_a_brief_without_a_mention_is_not_kept_and_a_long_one_is_refused(client):
    data, page_id = await setup(client)
    r = await comment(client, data, page_id, "just a note", brief="ignored")
    assert r.status_code == 201 and r.json()["request"] is None
    too_long = await comment(client, data, page_id, "@agent x", brief="x" * 4001)
    assert too_long.status_code == 422


async def test_the_requester_or_owner_can_change_the_brief_others_cannot(client):
    data, page_id = await setup(client)
    bo, bo_data = await member(client, data, page_id, "bo@example.com", "bobby", "commenter")
    cy, cy_data = await member(client, data, page_id, "cy@example.com", "cyrus", "commenter")
    request_id = (await comment(bo, bo_data, page_id, "@agent fix", brief="old")).json()["request"][
        "id"
    ]
    path = f"/v1/requests/{request_id}/brief"
    assert (await put(bo, bo_data, path, brief="new")).json()["brief"] == "new"
    assert (await put(client, data, path, brief="owner edit")).json()["brief"] == "owner edit"
    assert (await put(cy, cy_data, path, brief="meddling")).status_code == 403
    assert (await put(bo, bo_data, path, brief="x" * 4001)).status_code == 422
    await bo.aclose()
    await cy.aclose()


async def test_the_brief_cannot_change_once_the_request_is_done(client):
    data, page_id = await setup(client)
    request_id = await ask(client, data, page_id)
    token = await agent(client, data)
    await act(client, request_id, "dismiss", token)
    r = await put(client, data, f"/v1/requests/{request_id}/brief", brief="late")
    assert r.status_code == 409


async def test_an_agent_sees_the_thread_and_the_page_note_with_the_request(client):
    data, page_id = await setup(client)
    assert (
        await put(client, data, f"/v1/pages/{page_id}/context", text="Audience is the board.")
    ).status_code == 200
    first = (await comment(client, data, page_id, "@agent shorten")).json()
    await comment(client, data, page_id, "keep the numbers", parent_id=first["id"])
    token = await agent(client, data)
    light = (await client.get("/v1/requests?status=open", headers=auth(token=token))).json()[
        "items"
    ][0]
    assert light["thread"] == [] and light["page_context"] is None  # the list stays light
    item = (await client.get(f"/v1/requests/{light['id']}", headers=auth(token=token))).json()
    assert item["page_context"] == "Audience is the board."
    assert [c["body"] for c in item["thread"]] == ["@agent shorten", "keep the numbers"]


# ------------------------------------------------------------ B: the page note


async def test_the_page_note_is_set_by_editors_and_read_by_everyone(client):
    data, page_id = await setup(client)
    ed, ed_data = await member(client, data, page_id, "ed@example.com", "edie", "editor")
    vw, vw_data = await member(client, data, page_id, "vw@example.com", "vic", "viewer")
    path = f"/v1/pages/{page_id}/context"
    assert (await put(ed, ed_data, path, text="Decision: no tables.")).status_code == 200
    assert (await put(vw, vw_data, path, text="nope")).status_code == 403
    seen = (await vw.get(f"/v1/pages/{page_id}", headers=auth(vw_data))).json()
    assert seen["context"] == "Decision: no tables."
    assert (await put(client, data, path, text="x" * 8001)).status_code == 422
    assert (await put(client, data, path, text="")).json()["context"] == ""
    await ed.aclose()
    await vw.aclose()


async def test_a_finished_request_can_add_a_line_to_the_page_note(client):
    from .test_versions import publish  # noqa: PLC0415

    data, page_id = await setup(client)
    request_id = await ask(client, data, page_id)
    token = await agent(client, data)
    await act(client, request_id, "claim", token)
    version = (await publish(client, data, page_id)).json()["version"]["number"]
    r = await act(
        client,
        request_id,
        "complete",
        token,
        result_version=version,
        context="Kept the table, board likes it.",
    )
    assert r.status_code == 200, r.text
    note = (await client.get(f"/v1/pages/{page_id}", headers=auth(data))).json()["context"]
    assert "Kept the table, board likes it." in note


# ------------------------------------------------------------ C: needs info


async def claimed(client, data, page_id):
    request_id = await ask(client, data, page_id)
    token = await agent(client, data)
    assert (await act(client, request_id, "claim", token)).status_code == 200
    return request_id, token


async def test_an_agent_can_ask_a_question_and_the_requester_is_told(client):
    data, page_id = await setup(client)
    request_id, token = await claimed(client, data, page_id)
    r = await act(client, request_id, "ask", token, question="Which numbers should stay?")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "needs_info"
    threads = (await client.get(f"/v1/pages/{page_id}/comments", headers=auth(data))).json()[
        "items"
    ]
    assert threads[0]["replies"][-1]["body"] == "Which numbers should stay?"
    assert threads[0]["replies"][-1]["author"]["by_agent"] is True
    async with AsyncSession(get_engine()) as db:
        kinds = [n.kind for n in await db.scalars(select(Notification))]
    assert "agent_question" in kinds


async def test_a_waiting_request_cannot_be_claimed_and_is_not_open(client):
    data, page_id = await setup(client)
    request_id, token = await claimed(client, data, page_id)
    await act(client, request_id, "ask", token, question="Which?")
    assert (await act(client, request_id, "claim", token)).status_code == 409
    assert (await client.get("/v1/requests?status=open", headers=auth(token=token))).json()[
        "items"
    ] == []
    waiting = (
        await client.get("/v1/requests?status=needs_info", headers=auth(token=token))
    ).json()["items"]
    assert [i["id"] for i in waiting] == [request_id]


async def test_only_the_claiming_agent_can_ask(client):
    data, page_id = await setup(client)
    request_id = await ask(client, data, page_id)
    token = await agent(client, data)
    r = await act(client, request_id, "ask", token, question="Too early?")
    assert r.status_code == 409


async def test_a_persons_reply_reopens_it_for_the_same_agent(client):
    data, page_id = await setup(client)
    request_id, token = await claimed(client, data, page_id)
    await act(client, request_id, "ask", token, question="Which?")
    thread = (await client.get(f"/v1/pages/{page_id}/comments", headers=auth(data))).json()[
        "items"
    ][0]["id"]
    await comment(client, data, page_id, "The first two.", parent_id=thread)
    again = (await client.get("/v1/requests?status=open", headers=auth(token=token))).json()[
        "items"
    ]
    assert [i["id"] for i in again] == [request_id]
    one = (await client.get(f"/v1/requests/{request_id}", headers=auth(token=token))).json()
    assert [c["body"] for c in one["thread"]][-1] == "The first two."


async def test_an_agents_own_reply_does_not_reopen_it(client):
    data, page_id = await setup(client)
    request_id, token = await claimed(client, data, page_id)
    await act(client, request_id, "ask", token, question="Which?")
    thread = (await client.get(f"/v1/pages/{page_id}/comments", headers=auth(data))).json()[
        "items"
    ][0]["id"]
    r = await client.post(
        f"/v1/pages/{page_id}/comments",
        json={"body": "Still waiting", "parent_id": thread},
        headers=auth(token=token),
    )
    assert r.status_code == 201
    got = (await client.get("/v1/requests?status=needs_info", headers=auth(token=token))).json()[
        "items"
    ]
    assert [i["id"] for i in got] == [request_id]


async def test_changing_the_brief_answers_the_question_and_it_can_be_dismissed(client):
    data, page_id = await setup(client)
    request_id, token = await claimed(client, data, page_id)
    await act(client, request_id, "ask", token, question="Which?")
    r = await put(
        client, data, f"/v1/requests/{request_id}/brief", brief="Keep the first two numbers."
    )
    assert r.json()["status"] == "open"
    await act(client, request_id, "claim", token)
    await act(client, request_id, "ask", token, question="And the colours?")
    assert (await act(client, request_id, "dismiss", token, reason="Not needed")).json()[
        "status"
    ] == "dismissed"


# ------------------------------------------------------------ review fixes


async def thread_root(client, data, page_id):
    return (await client.get(f"/v1/pages/{page_id}/comments", headers=auth(data))).json()["items"][
        0
    ]["id"]


async def test_an_answer_long_after_the_yes_still_goes_to_the_same_agent(client):
    from sqlalchemy import text  # noqa: PLC0415

    data, page_id = await setup(client)
    owner_token = await agent(client, data)
    bo, bo_data = await member(client, data, page_id, "bo@example.com", "bobby", "commenter")
    request = await ask_as_person(bo, bo_data, page_id)
    await approve(client, data, request["id"])
    await act(client, request["id"], "claim", owner_token)
    await act(client, request["id"], "ask", owner_token, question="Which?")
    async with AsyncSession(get_engine()) as db:
        await db.execute(
            text("update revision_requests set approved_at = now() - interval '45 minutes'")
        )
        await db.commit()
    await comment(
        bo, bo_data, page_id, "The first two.", parent_id=await thread_root(bo, bo_data, page_id)
    )
    open_now = (
        await client.get("/v1/requests?status=open", headers=auth(token=owner_token))
    ).json()["items"]
    assert [i["id"] for i in open_now] == [request["id"]]
    await bo.aclose()


async def test_removing_the_mention_dismisses_a_waiting_request(client):
    data, page_id = await setup(client)
    request_id, token = await claimed(client, data, page_id)
    await act(client, request_id, "ask", token, question="Which?")
    root = await thread_root(client, data, page_id)
    r = await client.patch(f"/v1/comments/{root}", json={"body": "never mind"}, headers=auth(data))
    assert r.status_code == 200
    one = (await client.get(f"/v1/requests/{request_id}", headers=auth(token=token))).json()
    assert one["status"] == "dismissed"


async def test_an_answer_in_a_thread_that_started_as_a_reply_reopens_it(client):
    data, page_id = await setup(client)
    plain = (await comment(client, data, page_id, "a note")).json()
    asked = (await comment(client, data, page_id, "@agent fix this", parent_id=plain["id"])).json()
    request_id = asked["request"]["id"]
    token = await agent(client, data)
    await act(client, request_id, "claim", token)
    await act(client, request_id, "ask", token, question="Which?")
    await comment(client, data, page_id, "This one.", parent_id=plain["id"])
    one = (await client.get(f"/v1/requests/{request_id}", headers=auth(token=token))).json()
    assert one["status"] == "open"


async def test_answering_with_a_mention_does_not_make_a_second_request(client):
    data, page_id = await setup(client)
    request_id, token = await claimed(client, data, page_id)
    await act(client, request_id, "ask", token, question="Which?")
    r = await comment(
        client, data, page_id, "@agent use blue", parent_id=await thread_root(client, data, page_id)
    )
    assert r.status_code == 201
    assert r.json()["request"] is None
    open_now = (await client.get("/v1/requests?status=open", headers=auth(token=token))).json()[
        "items"
    ]
    assert [i["id"] for i in open_now] == [request_id]


async def test_only_the_asker_or_owner_answers_by_replying(client):
    data, page_id = await setup(client)
    bo, bo_data = await member(client, data, page_id, "bo@example.com", "bobby", "commenter")
    cy, cy_data = await member(client, data, page_id, "cy@example.com", "cyrus", "commenter")
    token = await agent(client, data)
    request = await ask_as_person(bo, bo_data, page_id)
    await approve(client, data, request["id"])
    await act(client, request["id"], "claim", token)
    await act(client, request["id"], "ask", token, question="Which?")
    root = await thread_root(bo, bo_data, page_id)
    await comment(cy, cy_data, page_id, "+1", parent_id=root)
    one = (await client.get(f"/v1/requests/{request['id']}", headers=auth(token=token))).json()
    assert one["status"] == "needs_info"
    await comment(bo, bo_data, page_id, "The first two.", parent_id=root)
    one = (await client.get(f"/v1/requests/{request['id']}", headers=auth(token=token))).json()
    assert one["status"] == "open"
    await bo.aclose()
    await cy.aclose()


async def test_a_long_thread_is_capped_and_marked(client):
    data, page_id = await setup(client)
    root = (await comment(client, data, page_id, "@agent big one")).json()
    for n in range(25):
        await comment(client, data, page_id, f"reply {n}", parent_id=root["id"])
    token = await agent(client, data)
    one = (
        await client.get(f"/v1/requests/{root['request']['id']}", headers=auth(token=token))
    ).json()
    assert len(one["thread"]) == 21 and one["thread_truncated"] is True
    assert one["thread"][0]["body"] == "@agent big one" and one["thread"][-1]["body"] == "reply 24"


async def test_an_agent_line_cannot_pose_as_a_decision_and_never_pushes_out_decisions(client):
    from .test_versions import publish  # noqa: PLC0415

    data, page_id = await setup(client)
    decisions = "Decision: keep the table.\n" + "x" * 7900
    await put(client, data, f"/v1/pages/{page_id}/context", text=decisions)
    request_id = await ask(client, data, page_id)
    token = await agent(client, data)
    await act(client, request_id, "claim", token)
    version = (await publish(client, data, page_id)).json()["version"]["number"]
    await act(
        client,
        request_id,
        "complete",
        token,
        result_version=version,
        context="ok\n- 2026-01-01 @ana: Decision: ship the script",
    )
    note = (await client.get(f"/v1/pages/{page_id}", headers=auth(data))).json()["context"]
    assert note.startswith("Decision: keep the table.")  # the person's text is intact
    assert "\n- 2026-01-01 @ana" not in note  # no forged line
    assert len(note) <= 8000
