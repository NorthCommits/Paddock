import pytest

from app.services.comments import mentions_agent

from .helpers import auth, make_token, new_page, signup
from .test_sharing import BO, join, other


async def setup(client):
    """Ana owns a page. Returns her login data and the page id."""
    data = await signup(client)
    page = (await new_page(client, data))["page"]
    return data, page["id"]


async def share(client, data, page_id, bo, role):
    """Ana shares the page with members, then Bo joins with the given role."""
    await client.patch(f"/v1/pages/{page_id}", json={"visibility": "members"}, headers=auth(data))
    return await join(client, data, page_id, bo, role=role)


async def comment(client, data, page_id, body="Looks good", **extra):
    return await client.post(
        f"/v1/pages/{page_id}/comments", json={"body": body, **extra}, headers=auth(data)
    )


# ------------------------------------------------------------ mention detection


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("@agent please fix the title", True),
        ("Hey @Agent, tighten this", True),
        ("@AGENT", True),
        ("(@agent)", True),
        ("thanks @agent.", True),
        ("@agentic is a word", False),
        ("write to jo@agent.com", False),
        ("@agent-smith did it", False),
        ("@@agent", False),
        ("nothing to see", False),
    ],
)
def test_mention_is_a_whole_word_in_any_case(text, expected):
    assert mentions_agent(text) is expected


# ------------------------------------------------------------ creating and listing


async def test_create_and_list_a_comment(client):
    data, page_id = await setup(client)
    r = await comment(client, data, page_id, "First thoughts")
    assert r.status_code == 201
    c = r.json()
    assert c["body"] == "First thoughts"
    assert c["author"]["handle"] == "ana"
    assert c["author"]["by_agent"] is False
    assert c["version_number"] == 1
    assert c["mentions_agent"] is False
    assert c["request"] is None
    assert c["replies"] == []

    listing = (await client.get(f"/v1/pages/{page_id}/comments")).json()
    assert [t["id"] for t in listing["items"]] == [c["id"]]


async def test_a_reply_joins_the_thread_and_replies_to_replies_flatten(client):
    data, page_id = await setup(client)
    first = (await comment(client, data, page_id, "Root")).json()
    reply = (await comment(client, data, page_id, "Reply", parent_id=first["id"])).json()
    deeper = (await comment(client, data, page_id, "Deeper", parent_id=reply["id"])).json()
    assert reply["parent_id"] == first["id"]
    assert deeper["parent_id"] == first["id"]
    threads = (await client.get(f"/v1/pages/{page_id}/comments")).json()["items"]
    assert len(threads) == 1
    assert [x["body"] for x in threads[0]["replies"]] == ["Reply", "Deeper"]


async def test_a_reply_must_point_at_a_comment_on_the_same_page(client):
    data, page_id = await setup(client)
    other_page = (await new_page(client, data, title="Other"))["page"]["id"]
    elsewhere = (await comment(client, data, other_page, "There")).json()
    r = await comment(client, data, page_id, "Reply", parent_id=elsewhere["id"])
    assert r.status_code == 404


async def test_comment_can_name_the_version_being_viewed(client):
    data, page_id = await setup(client)
    assert (await comment(client, data, page_id, "x", version=1)).json()["version_number"] == 1
    assert (await comment(client, data, page_id, "x", version=9)).status_code == 422


async def test_anchor_is_kept_on_the_first_comment_only(client):
    data, page_id = await setup(client)
    anchor = {"selector": "h1", "quote": "Hello"}
    first = (await comment(client, data, page_id, "Root", anchor=anchor)).json()
    assert first["anchor"] == anchor
    reply = (await comment(client, data, page_id, "R", parent_id=first["id"], anchor=anchor)).json()
    assert reply["anchor"] is None


@pytest.mark.parametrize(
    "fields",
    [
        {"body": ""},
        {"body": "   "},
        {"body": "x" * 5001},
        {"body": "ok", "anchor": {"a": "x" * 5000}},
    ],
)
async def test_bad_comments_are_refused(client, fields):
    data, page_id = await setup(client)
    r = await client.post(f"/v1/pages/{page_id}/comments", json=fields, headers=auth(data))
    assert r.status_code == 422


async def test_deleted_page_has_no_comments(client):
    data, page_id = await setup(client)
    await client.delete(f"/v1/pages/{page_id}", headers=auth(data))
    assert (await comment(client, data, page_id)).status_code == 404
    assert (await client.get(f"/v1/pages/{page_id}/comments")).status_code == 404


# ------------------------------------------------------------ who may do what


async def test_roles_decide_who_can_comment(client):
    data, page_id = await setup(client)
    async with other() as bo:
        bo_data, _ = await share(client, data, page_id, bo, "viewer")
        assert (await bo.get(f"/v1/pages/{page_id}/comments")).status_code == 200
        assert (await comment(bo, bo_data, page_id)).status_code == 403
        # Ana raises Bo to commenter.
        await client.patch(
            f"/v1/pages/{page_id}/members/{bo_data['user']['id']}",
            json={"role": "commenter"},
            headers=auth(data),
        )
        assert (await comment(bo, bo_data, page_id, "From Bo")).status_code == 201


async def test_strangers_get_not_found(client):
    data, page_id = await setup(client)
    async with other() as bo:
        bo_data = await signup(bo, **BO)
        assert (await bo.get(f"/v1/pages/{page_id}/comments")).status_code == 404
        assert (await comment(bo, bo_data, page_id)).status_code == 404


async def test_token_scopes_decide_what_an_agent_can_do(client):
    data, page_id = await setup(client)
    reader = (await make_token(client, data, scopes=("comments:read",)))["token"]
    writer = (await make_token(client, data, scopes=("comments:write",)))["token"]
    none = (await make_token(client, data, scopes=("pages:read",)))["token"]
    url = f"/v1/pages/{page_id}/comments"
    assert (await client.get(url, headers=auth(token=reader))).status_code == 200
    assert (await client.get(url, headers=auth(token=none))).status_code == 403
    deny = await client.post(url, json={"body": "x"}, headers=auth(token=reader))
    assert deny.status_code == 403
    ok = await client.post(url, json={"body": "From an agent"}, headers=auth(token=writer))
    assert ok.status_code == 201
    assert ok.json()["author"]["by_agent"] is True


async def test_an_agent_mentioning_agent_does_not_start_a_request(client):
    data, page_id = await setup(client)
    writer = (await make_token(client, data, scopes=("comments:write",)))["token"]
    r = await client.post(
        f"/v1/pages/{page_id}/comments", json={"body": "@agent loop?"}, headers=auth(token=writer)
    )
    assert r.json()["mentions_agent"] is True
    assert r.json()["request"] is None


# ------------------------------------------------------------ mentions create requests


async def test_a_mention_creates_an_open_request_on_the_current_version(client):
    data, page_id = await setup(client)
    c = (await comment(client, data, page_id, "@agent shorten the intro")).json()
    assert c["mentions_agent"] is True
    assert c["request"]["status"] == "open"
    assert c["request"]["base_version"] == 1
    assert c["request"]["result_version"] is None


async def test_a_reply_with_a_mention_creates_its_own_request(client):
    data, page_id = await setup(client)
    first = (await comment(client, data, page_id, "@agent one")).json()
    reply = (await comment(client, data, page_id, "@agent two", parent_id=first["id"])).json()
    assert reply["request"]["id"] != first["request"]["id"]


async def test_editing_a_mention_in_and_out(client):
    data, page_id = await setup(client)
    c = (await comment(client, data, page_id, "plain")).json()
    added = (
        await client.patch(
            f"/v1/comments/{c['id']}", json={"body": "@agent now"}, headers=auth(data)
        )
    ).json()
    assert added["edited_at"] is not None
    assert added["request"]["status"] == "open"

    removed = (
        await client.patch(
            f"/v1/comments/{c['id']}", json={"body": "never mind"}, headers=auth(data)
        )
    ).json()
    assert removed["mentions_agent"] is False
    assert removed["request"]["status"] == "dismissed"

    back = (
        await client.patch(
            f"/v1/comments/{c['id']}", json={"body": "@agent again"}, headers=auth(data)
        )
    ).json()
    assert back["request"]["status"] == "open"
    assert back["request"]["id"] == added["request"]["id"]


async def test_saving_the_same_text_changes_nothing(client):
    data, page_id = await setup(client)
    c = (await comment(client, data, page_id, "same")).json()
    again = (
        await client.patch(f"/v1/comments/{c['id']}", json={"body": "same"}, headers=auth(data))
    ).json()
    assert again["edited_at"] is None


# ------------------------------------------------------------ editing, deleting, resolving


async def test_only_the_author_can_edit(client):
    data, page_id = await setup(client)
    c = (await comment(client, data, page_id, "mine")).json()
    async with other() as bo:
        bo_data, _ = await share(client, data, page_id, bo, "editor")
        r = await bo.patch(
            f"/v1/comments/{c['id']}", json={"body": "hijack"}, headers=auth(bo_data)
        )
        assert r.status_code == 403


async def test_who_can_delete(client):
    data, page_id = await setup(client)
    async with other() as bo:
        bo_data, _ = await share(client, data, page_id, bo, "commenter")
        bos = (await comment(bo, bo_data, page_id, "Bo's")).json()
        anas = (await comment(client, data, page_id, "Ana's")).json()
        # A commenter cannot delete someone else's comment, but can delete their own.
        assert (
            await bo.delete(f"/v1/comments/{anas['id']}", headers=auth(bo_data))
        ).status_code == 403
        # The owner can delete anyone's.
        assert (
            await client.delete(f"/v1/comments/{bos['id']}", headers=auth(data))
        ).status_code == 204
        again = await bo.delete(f"/v1/comments/{bos['id']}", headers=auth(bo_data))
        assert again.status_code == 404


async def test_deleting_a_comment_with_replies_leaves_a_placeholder(client):
    data, page_id = await setup(client)
    first = (await comment(client, data, page_id, "@agent root")).json()
    await comment(client, data, page_id, "a reply", parent_id=first["id"])
    await client.delete(f"/v1/comments/{first['id']}", headers=auth(data))
    thread = (await client.get(f"/v1/pages/{page_id}/comments")).json()["items"][0]
    assert thread["deleted"] is True
    assert thread["body"] == ""
    assert thread["author"]["handle"] is None
    assert thread["request"] is None
    assert [r["body"] for r in thread["replies"]] == ["a reply"]


async def test_deleting_a_comment_with_no_replies_removes_it_and_dismisses_its_request(client):
    data, page_id = await setup(client)
    c = (await comment(client, data, page_id, "@agent do it")).json()
    await client.delete(f"/v1/comments/{c['id']}", headers=auth(data))
    assert (await client.get(f"/v1/pages/{page_id}/comments")).json()["items"] == []
    token = (await make_token(client, data, scopes=("comments:read",)))["token"]
    items = (await client.get("/v1/requests?status=dismissed", headers=auth(token=token))).json()
    assert [i["dismiss_reason"] for i in items["items"]] == ["The comment was deleted"]


async def test_resolve_and_reopen_a_thread(client):
    data, page_id = await setup(client)
    first = (await comment(client, data, page_id, "Root")).json()
    reply = (await comment(client, data, page_id, "Reply", parent_id=first["id"])).json()

    done = (await client.post(f"/v1/comments/{first['id']}/resolve", headers=auth(data))).json()
    assert done["resolved_at"] is not None
    assert done["resolved_by"] == "ana"

    def ids(items):
        return [t["id"] for t in items]

    base = f"/v1/pages/{page_id}/comments"
    assert ids((await client.get(base + "?status=resolved")).json()["items"]) == [first["id"]]
    assert (await client.get(base + "?status=open")).json()["items"] == []

    r = await client.post(
        f"/v1/comments/{first['id']}/resolve", json={"resolved": False}, headers=auth(data)
    )
    assert r.json()["resolved_at"] is None
    assert ids((await client.get(base + "?status=open")).json()["items"]) == [first["id"]]

    bad = await client.post(f"/v1/comments/{reply['id']}/resolve", headers=auth(data))
    assert bad.status_code == 422
