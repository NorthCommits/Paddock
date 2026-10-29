from .helpers import auth, make_token
from .test_comments import comment, setup, share
from .test_sharing import age_rows, other
from .test_versions import publish

AGENT_SCOPES = ("comments:read", "comments:write", "requests:act", "pages:read", "pages:write")


async def agent(client, data, scopes=AGENT_SCOPES):
    return (await make_token(client, data, scopes=scopes))["token"]


async def ask(client, data, page_id, body="@agent make it shorter"):
    return (await comment(client, data, page_id, body)).json()["request"]["id"]


async def act(client, request_id, action, token, **body):
    return await client.post(
        f"/v1/requests/{request_id}/{action}", json=body, headers=auth(token=token)
    )


# ------------------------------------------------------------ listing


async def test_agent_lists_open_requests_oldest_first(client):
    data, page_id = await setup(client)
    first = await ask(client, data, page_id, "@agent one")
    second = await ask(client, data, page_id, "@agent two")
    await comment(client, data, page_id, "no mention")
    token = await agent(client, data)
    items = (await client.get("/v1/requests?status=open", headers=auth(token=token))).json()[
        "items"
    ]
    assert [i["id"] for i in items] == [first, second]
    assert items[0]["page_title"] == "Quarterly report"
    assert items[0]["owner_handle"] == "ana"
    assert items[0]["comment"]["body"] == "@agent one"
    assert items[0]["base_version"] == 1


async def test_listing_needs_a_scope_and_can_filter(client):
    data, page_id = await setup(client)
    other_page = (
        await client.post(
            "/v1/pages",
            json={"title": "Two", "files": [{"path": "index.html", "content": "<p>x</p>"}]},
            headers=auth(data),
        )
    ).json()["page"]["id"]
    await ask(client, data, page_id)
    await ask(client, data, other_page)
    none = await agent(client, data, scopes=("pages:read",))
    assert (await client.get("/v1/requests", headers=auth(token=none))).status_code == 403
    token = await agent(client, data)
    only = (await client.get(f"/v1/requests?page_id={page_id}", headers=auth(token=token))).json()
    assert len(only["items"]) == 1
    limited = (await client.get("/v1/requests?limit=1", headers=auth(token=token))).json()
    assert len(limited["items"]) == 1


async def test_requests_on_other_peoples_private_pages_are_hidden(client):
    data, page_id = await setup(client)
    await ask(client, data, page_id)
    async with other() as bo:
        bo_data, _ = await share(client, data, page_id, bo, "editor")
        bo_token = await agent(bo, bo_data)
        # Page is shared with members, so Bo's agent sees it.
        assert (
            len((await bo.get("/v1/requests", headers=auth(token=bo_token))).json()["items"]) == 1
        )
        # Ana makes it private again, and it disappears.
        await client.patch(
            f"/v1/pages/{page_id}", json={"visibility": "private"}, headers=auth(data)
        )
        assert (await bo.get("/v1/requests", headers=auth(token=bo_token))).json()["items"] == []
        hidden = await ask(client, data, page_id)
        claimed = await act(bo, hidden, "claim", bo_token)
        assert claimed.status_code == 404
        # The same answer as an id that does not exist, so the request stays secret.
        assert claimed.json()["error"]["message"] == "Request not found"
        read = await bo.get(f"/v1/requests/{hidden}", headers=auth(token=bo_token))
        assert read.status_code == 404
        assert read.json()["error"]["message"] == "Request not found"


# ------------------------------------------------------------ claim


async def test_claim_is_for_agents_only(client):
    data, page_id = await setup(client)
    rid = await ask(client, data, page_id)
    r = await client.post(f"/v1/requests/{rid}/claim", json={}, headers=auth(data))
    assert r.status_code == 403


async def test_claim_then_extend_by_the_same_token(client):
    data, page_id = await setup(client)
    rid = await ask(client, data, page_id)
    token = await agent(client, data)
    claimed = (await act(client, rid, "claim", token)).json()
    assert claimed["status"] == "claimed"
    assert claimed["claim_expires_at"] is not None
    longer = (await act(client, rid, "claim", token, minutes=30)).json()
    assert longer["claim_expires_at"] > claimed["claim_expires_at"]
    assert (await act(client, rid, "claim", token, minutes=61)).status_code == 422


async def test_a_second_agent_cannot_take_a_live_claim(client):
    data, page_id = await setup(client)
    rid = await ask(client, data, page_id)
    one, two = await agent(client, data), await agent(client, data)
    await act(client, rid, "claim", one)
    assert (await act(client, rid, "claim", two)).status_code == 409


async def test_claim_needs_the_requests_scope(client):
    data, page_id = await setup(client)
    rid = await ask(client, data, page_id)
    token = await agent(client, data, scopes=("comments:read", "comments:write"))
    assert (await act(client, rid, "claim", token)).status_code == 403


async def test_an_expired_claim_goes_back_to_open(client):
    data, page_id = await setup(client)
    rid = await ask(client, data, page_id)
    one, two = await agent(client, data), await agent(client, data)
    await act(client, rid, "claim", one, minutes=1)
    await age_rows("revision_requests", "claim_expires_at", 1)
    listed = (await client.get("/v1/requests?status=open", headers=auth(token=two))).json()
    assert [i["id"] for i in listed["items"]] == [rid]
    again = await act(client, rid, "claim", two)
    assert again.status_code == 200
    assert again.json()["status"] == "claimed"


# ------------------------------------------------------------ complete


async def test_complete_with_a_new_version_posts_a_reply(client):
    data, page_id = await setup(client)
    rid = await ask(client, data, page_id)
    token = await agent(client, data)
    await act(client, rid, "claim", token)
    assert (await publish(client, data, page_id, "<p>shorter</p>")).status_code == 201
    done = await act(client, rid, "complete", token, result_version=2)
    assert done.status_code == 200
    body = done.json()
    assert body["status"] == "done"
    assert body["result_version"] == 2
    thread = (await client.get(f"/v1/pages/{page_id}/comments")).json()["items"][0]
    assert thread["request"]["status"] == "done"
    assert thread["replies"][0]["body"] == "Published version 2."
    assert thread["replies"][0]["author"]["by_agent"] is True
    assert thread["replies"][0]["request"] is None


async def test_complete_uses_a_custom_reply(client):
    data, page_id = await setup(client)
    rid = await ask(client, data, page_id)
    token = await agent(client, data)
    await act(client, rid, "claim", token)
    await publish(client, data, page_id, "<p>b</p>")
    await act(client, rid, "complete", token, result_version=2, reply="Trimmed the intro.")
    thread = (await client.get(f"/v1/pages/{page_id}/comments")).json()["items"][0]
    assert thread["replies"][0]["body"] == "Trimmed the intro."


async def test_complete_rules(client):
    data, page_id = await setup(client)
    rid = await ask(client, data, page_id)
    one, two = await agent(client, data), await agent(client, data)
    # Not claimed yet.
    assert (await act(client, rid, "complete", one, result_version=1)).status_code == 409
    await act(client, rid, "claim", one)
    # A people login cannot complete.
    r = await client.post(
        f"/v1/requests/{rid}/complete", json={"result_version": 1}, headers=auth(data)
    )
    assert r.status_code == 403
    # Another agent cannot complete it.
    assert (await act(client, rid, "complete", two, result_version=1)).status_code == 409
    # The old version was not made after the request.
    assert (await act(client, rid, "complete", one, result_version=1)).status_code == 422
    # A version that does not exist.
    assert (await act(client, rid, "complete", one, result_version=9)).status_code == 422
    # A version of another page does not count.
    other_page = (
        await client.post(
            "/v1/pages",
            json={"title": "Two", "files": [{"path": "index.html", "content": "<p>x</p>"}]},
            headers=auth(data),
        )
    ).json()["page"]["id"]
    await publish(client, data, other_page, "<p>y</p>")
    assert (await act(client, rid, "complete", one, result_version=2)).status_code == 422
    # Finished requests stay finished.
    await publish(client, data, page_id, "<p>z</p>")
    assert (await act(client, rid, "complete", one, result_version=2)).status_code == 200
    assert (await act(client, rid, "complete", one, result_version=2)).status_code == 409
    assert (await act(client, rid, "claim", one)).status_code == 409


async def test_a_claim_that_ran_out_cannot_complete(client):
    data, page_id = await setup(client)
    rid = await ask(client, data, page_id)
    token = await agent(client, data)
    await act(client, rid, "claim", token, minutes=1)
    await publish(client, data, page_id, "<p>late</p>")
    await age_rows("revision_requests", "claim_expires_at", 1)
    assert (await act(client, rid, "complete", token, result_version=2)).status_code == 409


# ------------------------------------------------------------ dismiss


async def test_a_person_can_dismiss_and_the_reason_becomes_a_reply(client):
    data, page_id = await setup(client)
    rid = await ask(client, data, page_id)
    r = await client.post(
        f"/v1/requests/{rid}/dismiss", json={"reason": "Not needed now"}, headers=auth(data)
    )
    assert r.status_code == 200
    assert r.json()["status"] == "dismissed"
    assert r.json()["dismiss_reason"] == "Not needed now"
    thread = (await client.get(f"/v1/pages/{page_id}/comments")).json()["items"][0]
    assert thread["replies"][0]["body"] == "Not needed now"
    again = await client.post(f"/v1/requests/{rid}/dismiss", json={}, headers=auth(data))
    assert again.status_code == 409


async def test_dismiss_without_a_reason_adds_no_reply(client):
    data, page_id = await setup(client)
    rid = await ask(client, data, page_id)
    token = await agent(client, data)
    await act(client, rid, "claim", token)
    r = await act(client, rid, "dismiss", token)
    assert r.json()["status"] == "dismissed"
    thread = (await client.get(f"/v1/pages/{page_id}/comments")).json()["items"][0]
    assert thread["replies"] == []


async def test_only_editors_can_dismiss(client):
    data, page_id = await setup(client)
    rid = await ask(client, data, page_id)
    async with other() as bo:
        bo_data, _ = await share(client, data, page_id, bo, "commenter")
        r = await bo.post(f"/v1/requests/{rid}/dismiss", json={}, headers=auth(bo_data))
        assert r.status_code == 403
        await client.patch(
            f"/v1/pages/{page_id}/members/{bo_data['user']['id']}",
            json={"role": "editor"},
            headers=auth(data),
        )
        r = await bo.post(f"/v1/requests/{rid}/dismiss", json={}, headers=auth(bo_data))
        assert r.status_code == 200


async def test_unknown_request_is_not_found(client):
    data, _ = await setup(client)
    token = await agent(client, data)
    missing = "00000000-0000-0000-0000-000000000000"
    assert (await act(client, missing, "claim", token)).status_code == 404


async def test_get_one_request(client):
    data, page_id = await setup(client)
    rid = await ask(client, data, page_id, "@agent tighten")
    token = await agent(client, data)
    r = await client.get(f"/v1/requests/{rid}", headers=auth(token=token))
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == rid
    assert body["page_id"] == page_id
    assert body["comment"]["body"] == "@agent tighten"
    assert body["comment"]["thread_id"] == body["comment"]["id"]

    none = await agent(client, data, scopes=("pages:read",))
    assert (await client.get(f"/v1/requests/{rid}", headers=auth(token=none))).status_code == 403
    missing = "00000000-0000-0000-0000-000000000000"
    assert (
        await client.get(f"/v1/requests/{missing}", headers=auth(token=token))
    ).status_code == 404
    async with other() as bo:
        from .helpers import signup
        from .test_sharing import BO

        bo_data = await signup(bo, **BO)
        bo_token = await agent(bo, bo_data)
        assert (
            await bo.get(f"/v1/requests/{rid}", headers=auth(token=bo_token))
        ).status_code == 404
