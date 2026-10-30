"""The MCP endpoint at /mcp, driven by the mcp library's own client over an in-process app."""

import asyncio
import base64
import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from sqlalchemy import select, update

from app.core import config
from app.db.models import ApiToken, AuditLog, User
from app.db.session import get_sessionmaker
from app.main import app
from app.mcp import server as mcp_server

from .helpers import auth, make_token, signup
from .test_requests import AGENT_SCOPES, ask

URL = "http://test/mcp"
TOOLS = {
    "list_pages",
    "get_page",
    "publish_page",
    "list_comments",
    "reply_to_comment",
    "list_requests",
    "claim_request",
    "complete_request",
    "ask_requester",
    "set_request_brief",
    "update_page_context",
}
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "1"},
    },
}
MCP_HEADERS = {"Accept": "application/json, text/event-stream"}


def http(token: str | None) -> httpx2.AsyncClient:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), headers=headers)


@asynccontextmanager
async def session(token: str, *, url: str = URL, mode: str = "legacy"):
    """A fresh MCP client. The caller keeps the MCP server running around it."""
    async with http(token) as hc:
        async with Client(streamable_http_client(url, http_client=hc), mode=mode) as c:
            yield c


@asynccontextmanager
async def connected(token: str, **kwargs):
    async with mcp_server.running():
        async with session(token, **kwargs) as c:
            yield c


def ok(result) -> dict:
    assert not result.is_error, result.content
    return json.loads(result.content[0].text)


def failed(result) -> str:
    assert result.is_error, result.content
    return result.content[0].text


async def agent_token(client, scopes=AGENT_SCOPES) -> tuple[dict, str]:
    data = await signup(client)
    return data, (await make_token(client, data, scopes=scopes))["token"]


def metadata_path() -> str:
    return "/.well-known/oauth-protected-resource/mcp"


# ------------------------------------------------------------ authentication


async def test_mcp_without_token_returns_401_with_metadata_hint(client):
    api = config.get_settings().api_public_url.rstrip("/")
    async with mcp_server.running():
        for headers in ({}, {"Authorization": "Bearer pdk_not_a_real_token"}):
            r = await client.post("/mcp", json=INITIALIZE, headers={**MCP_HEADERS, **headers})
            assert r.status_code == 401
            hint = r.headers["www-authenticate"]
            assert f'resource_metadata="{api}{metadata_path()}"' in hint
    meta = await client.get(metadata_path())
    assert meta.status_code == 200
    assert meta.json()["resource"] == f"{api}/mcp"


async def test_mcp_with_revoked_token_returns_401_not_500(client):
    data = await signup(client)
    revoked = await make_token(client, data, scopes=AGENT_SCOPES)
    expired = await make_token(client, data, scopes=AGENT_SCOPES)
    assert (await client.delete(f"/v1/tokens/{revoked['id']}", headers=auth(data))).status_code
    async with get_sessionmaker()() as db:
        await db.execute(
            update(ApiToken)
            .where(ApiToken.id == expired["id"])
            .values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
        )
        await db.commit()
    async with mcp_server.running():
        for raw in (revoked["token"], expired["token"]):
            r = await client.post(
                "/mcp", json=INITIALIZE, headers={**MCP_HEADERS, **auth(token=raw)}
            )
            assert r.status_code == 401
            assert "resource_metadata=" in r.headers["www-authenticate"]


# ------------------------------------------------------------ tools


async def test_initialize_and_list_tools_shows_the_eight_tools(client):
    _, token = await agent_token(client)
    async with connected(token) as c:
        tools = (await c.list_tools()).tools
    assert {t.name for t in tools} == TOOLS
    for tool in tools:
        assert tool.description and len(tool.description) > 40, tool.name


async def test_publish_page_creates_page_then_new_version(client):
    _, token = await agent_token(client)
    async with connected(token) as c:
        first = ok(
            await c.call_tool(
                "publish_page",
                {
                    "title": "Launch notes",
                    "files": [{"path": "index.html", "content": "<h1>One</h1>"}],
                    "message": "First draft",
                },
            )
        )
        assert first["created"] is True
        assert first["version"] == 1
        page_id = first["page_id"]
        assert first["url"].endswith(f"/pages/{page_id}")

        second = ok(
            await c.call_tool(
                "publish_page",
                {
                    "title": "ignored when updating",
                    "page_id": page_id,
                    "files": [
                        {"path": "index.html", "content": "<h1>Two</h1>"},
                        {
                            "path": "logo.png",
                            "content": base64.b64encode(PNG).decode(),
                            "encoding": "base64",
                        },
                    ],
                },
            )
        )
        assert second["version"] == 2
        assert second["created"] is True

        same = ok(
            await c.call_tool(
                "publish_page",
                {
                    "title": "x",
                    "page_id": page_id,
                    "files": [
                        {"path": "index.html", "content": "<h1>Two</h1>"},
                        {
                            "path": "logo.png",
                            "content": base64.b64encode(PNG).decode(),
                            "encoding": "base64",
                        },
                    ],
                },
            )
        )
        assert same["created"] is False
        assert same["version"] == 2

        page = ok(await c.call_tool("get_page", {"page_id": page_id}))
        files = {f["path"]: f for f in page["files"]}
        assert page["title"] == "Launch notes"
        assert page["version"] == 2
        assert files["index.html"] == {
            "path": "index.html",
            "content_type": "text/html; charset=utf-8",
            "encoding": "utf-8",
            "content": "<h1>Two</h1>",
        }
        assert files["logo.png"]["encoding"] == "base64"
        assert base64.b64decode(files["logo.png"]["content"]) == PNG

        listed = ok(await c.call_tool("list_pages", {}))
        assert [p["id"] for p in listed["pages"]] == [page_id]

    async with get_sessionmaker()() as db:
        actions = list(await db.scalars(select(AuditLog.action).order_by(AuditLog.id)))
    assert "page.create" in actions
    assert "version.publish" in actions


async def test_publish_page_rejects_bad_base64_with_clear_message(client):
    _, token = await agent_token(client)
    async with connected(token) as c:
        message = failed(
            await c.call_tool(
                "publish_page",
                {
                    "title": "T",
                    "files": [
                        {"path": "index.html", "content": "<p>x</p>"},
                        {"path": "logo.png", "content": "not base64!!", "encoding": "base64"},
                    ],
                },
            )
        )
        assert "logo.png" in message
        assert "base64" in message
        message = failed(
            await c.call_tool(
                "publish_page",
                {
                    "title": "T",
                    "files": [{"path": "index.html", "content": "x", "encoding": "latin-1"}],
                },
            )
        )
        assert "encoding" in message
        assert ok(await c.call_tool("list_pages", {}))["pages"] == []


async def test_publish_page_rejects_oversize_file_and_bad_path(client, monkeypatch):
    _, token = await agent_token(client)
    monkeypatch.setattr(config.get_settings(), "max_file_bytes", 10, raising=False)
    async with connected(token) as c:
        message = failed(
            await c.call_tool(
                "publish_page",
                {"title": "T", "files": [{"path": "index.html", "content": "<p>" + "x" * 50}]},
            )
        )
        assert "larger than 10 bytes" in message
        message = failed(
            await c.call_tool(
                "publish_page",
                {"title": "T", "files": [{"path": "../secret.html", "content": "<p>x</p>"}]},
            )
        )
        assert "Invalid file path" in message
        assert ok(await c.call_tool("list_pages", {}))["pages"] == []


async def test_write_tool_without_pages_write_scope_is_refused(client):
    _, token = await agent_token(client, scopes=("pages:read", "comments:read"))
    async with connected(token) as c:
        message = failed(
            await c.call_tool(
                "publish_page",
                {"title": "T", "files": [{"path": "index.html", "content": "<p>x</p>"}]},
            )
        )
        assert "pages:write" in message
        message = failed(
            await c.call_tool(
                "claim_request",
                {"request_id": "00000000-0000-0000-0000-000000000000"},
            )
        )
        assert "requests:act" in message


async def test_list_requests_claim_and_complete_round_trip(client):
    data, token = await agent_token(client)
    page = (
        await client.post(
            "/v1/pages",
            json={"title": "Report", "files": [{"path": "index.html", "content": "<p>long</p>"}]},
            headers=auth(data),
        )
    ).json()["page"]
    request_id = await ask(client, data, page["id"])

    async with connected(token) as c:
        items = ok(await c.call_tool("list_requests", {}))["requests"]
        assert [i["id"] for i in items] == [request_id]
        assert items[0]["comment"]["body"] == "@agent make it shorter"

        claimed = ok(await c.call_tool("claim_request", {"request_id": request_id}))
        assert claimed["status"] == "claimed"

        published = ok(
            await c.call_tool(
                "publish_page",
                {
                    "title": "Report",
                    "page_id": page["id"],
                    "files": [{"path": "index.html", "content": "<p>short</p>"}],
                },
            )
        )
        done = ok(
            await c.call_tool(
                "complete_request",
                {
                    "request_id": request_id,
                    "result_version": published["version"],
                    "reply": "Shortened it.",
                },
            )
        )
        assert done["status"] == "done"
        assert done["result_version"] == 2
        assert ok(await c.call_tool("list_requests", {}))["requests"] == []

        threads = ok(await c.call_tool("list_comments", {"page_id": page["id"]}))["comments"]
        assert [r["body"] for r in threads[0]["replies"]] == ["Shortened it."]

        reply = ok(
            await c.call_tool(
                "reply_to_comment",
                {"page_id": page["id"], "comment_id": threads[0]["id"], "body": "Anything else?"},
            )
        )
        assert reply["parent_id"] == threads[0]["id"]

        message = failed(await c.call_tool("claim_request", {"request_id": "not-an-id"}))
        assert "request_id" in message


async def test_unverified_email_cannot_publish(client):
    data, token = await agent_token(client)
    async with get_sessionmaker()() as db:
        await db.execute(
            update(User).where(User.id == data["user"]["id"]).values(email_verified_at=None)
        )
        await db.commit()
    async with connected(token) as c:
        message = failed(
            await c.call_tool(
                "publish_page",
                {"title": "T", "files": [{"path": "index.html", "content": "<p>x</p>"}]},
            )
        )
        assert "Verify your email" in message
        assert ok(await c.call_tool("list_pages", {}))["pages"] == []


async def test_mcp_works_without_trailing_slash_and_with_stateless_calls(client):
    _, token = await agent_token(client)
    async with mcp_server.running():
        # Two fresh clients at the same time, one on each spelling of the address, one on the
        # handshake protocol and one on the newer discover protocol.
        async def use(url, mode):
            async with session(token, url=url, mode=mode) as c:
                names = {t.name for t in (await c.list_tools()).tools}
                pages = ok(await c.call_tool("list_pages", {}))["pages"]
                return names, pages

        results = await asyncio.gather(use(URL, "legacy"), use(URL + "/", "auto"))
        assert all(names == TOOLS and pages == [] for names, pages in results)

        # A later client starts from nothing and still works: no session is kept.
        names, _ = await use(URL, "legacy")
        assert names == TOOLS

        async with http(token) as hc:
            r = await hc.post(URL, json=INITIALIZE, headers=MCP_HEADERS)
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("application/json")
        assert "mcp-session-id" not in r.headers

    # A restart (a new run of the server) does not break a client either.
    async with connected(token) as c:
        assert {t.name for t in (await c.list_tools()).tools} == TOOLS


async def test_app_lifespan_starts_the_mcp_server(client):
    _, token = await agent_token(client)
    async with app.router.lifespan_context(app):
        async with session(token) as c:
            assert {t.name for t in (await c.list_tools()).tools} == TOOLS
    async with http(token) as hc:
        r = await hc.post(URL, json=INITIALIZE, headers=MCP_HEADERS)
    assert r.status_code == 503


async def test_publish_page_shares_the_rest_publish_rate_limit(client, monkeypatch):
    from app.core import ratelimit

    _, token = await agent_token(client)
    monkeypatch.setattr(config.get_settings(), "rate_limit_enabled", True)
    monkeypatch.setattr(ratelimit, "RULES", {**ratelimit.RULES, "publish": 1})
    ratelimit.limiter.windows.clear()
    try:
        files = [{"path": "index.html", "content": "<p>x</p>"}]
        async with connected(token) as c:
            ok(await c.call_tool("publish_page", {"title": "One", "files": files}))
            message = failed(await c.call_tool("publish_page", {"title": "Two", "files": files}))
        assert "Too many requests" in message
    finally:
        ratelimit.limiter.windows.clear()


async def test_get_page_shares_the_rest_view_rate_limit(client, monkeypatch):
    from app.core import ratelimit

    data, token = await agent_token(client)
    page_id = (
        await client.post(
            "/v1/pages",
            json={"title": "T", "files": [{"path": "index.html", "content": "<p>x</p>"}]},
            headers=auth(data),
        )
    ).json()["page"]["id"]
    monkeypatch.setattr(config.get_settings(), "rate_limit_enabled", True)
    monkeypatch.setattr(ratelimit, "RULES", {**ratelimit.RULES, "view": 2})
    ratelimit.limiter.windows.clear()
    try:
        # One REST view-url call and one get_page use up the shared allowance of two.
        r = await client.post(f"/v1/pages/{page_id}/view-url", headers=auth(token=token))
        assert r.status_code == 200, r.text
        async with connected(token) as c:
            ok(await c.call_tool("get_page", {"page_id": page_id}))
            message = failed(await c.call_tool("get_page", {"page_id": page_id}))
        assert "Too many requests" in message
    finally:
        ratelimit.limiter.windows.clear()


async def test_other_users_pages_and_requests_stay_hidden(client):
    ana, _ = await agent_token(client)
    page = (
        await client.post(
            "/v1/pages",
            json={"title": "Ana", "files": [{"path": "index.html", "content": "<p>a</p>"}]},
            headers=auth(ana),
        )
    ).json()["page"]
    request_id = await ask(client, ana, page["id"])
    threads = (await client.get(f"/v1/pages/{page['id']}/comments", headers=auth(ana))).json()
    comment_id = threads["items"][0]["id"]

    bo = await signup(client, email="bo@example.com", handle="bobo")
    bo_token = (await make_token(client, bo, scopes=AGENT_SCOPES))["token"]
    files = [{"path": "index.html", "content": "<p>b</p>"}]
    async with connected(bo_token) as c:
        calls = [
            ("get_page", {"page_id": page["id"]}),
            ("list_comments", {"page_id": page["id"]}),
            ("reply_to_comment", {"page_id": page["id"], "comment_id": comment_id, "body": "hi"}),
            ("publish_page", {"title": "x", "page_id": page["id"], "files": files}),
        ]
        for name, args in calls:
            assert "Page not found" in failed(await c.call_tool(name, args)), name
        for name, args in [
            ("claim_request", {"request_id": request_id}),
            ("complete_request", {"request_id": request_id, "result_version": 1}),
        ]:
            assert "Request not found" in failed(await c.call_tool(name, args)), name
        for status in ("open", None):
            assert ok(await c.call_tool("list_requests", {"status": status}))["requests"] == []


async def test_disabled_user_and_person_jwt_get_401(client):
    from .helpers import mint_token

    data, token = await agent_token(client)
    async with get_sessionmaker()() as db:
        await db.execute(
            update(User).where(User.id == data["user"]["id"]).values(disabled_at=datetime.now(UTC))
        )
        await db.commit()
    async with mcp_server.running():
        for raw in (token, mint_token("ana@example.com"), "just-some-string"):
            r = await client.post(
                "/mcp", json=INITIALIZE, headers={**MCP_HEADERS, **auth(token=raw)}
            )
            assert r.status_code == 401, raw
            assert "resource_metadata=" in r.headers["www-authenticate"]


async def test_publish_page_accepts_utf8_alias_and_wrapped_base64(client):
    _, token = await agent_token(client)
    wrapped = base64.encodebytes(PNG + b"\x00" * 100).decode()  # lines of 76 with newlines
    assert "\n" in wrapped.strip()
    async with connected(token) as c:
        published = ok(
            await c.call_tool(
                "publish_page",
                {
                    "title": "T",
                    "files": [
                        {"path": "index.html", "content": "<p>x</p>", "encoding": "utf8"},
                        {"path": "logo.png", "content": wrapped, "encoding": "base64"},
                    ],
                },
            )
        )
        page = ok(await c.call_tool("get_page", {"page_id": published["page_id"]}))
    logo = next(f for f in page["files"] if f["path"] == "logo.png")
    assert base64.b64decode(logo["content"]) == PNG + b"\x00" * 100


async def test_bad_base64_message_truncates_long_paths(client):
    _, token = await agent_token(client)
    long_path = "a" * 150 + ".png"
    async with connected(token) as c:
        message = failed(
            await c.call_tool(
                "publish_page",
                {
                    "title": "T",
                    "files": [
                        {"path": "index.html", "content": "<p>x</p>"},
                        {"path": long_path, "content": "%%%", "encoding": "base64"},
                    ],
                },
            )
        )
    assert "invalid base64" in message
    assert long_path not in message


async def test_list_requests_says_when_there_are_more(client, monkeypatch):
    from app.mcp import tools

    data, token = await agent_token(client)
    page = (
        await client.post(
            "/v1/pages",
            json={"title": "R", "files": [{"path": "index.html", "content": "<p>r</p>"}]},
            headers=auth(data),
        )
    ).json()["page"]
    first = await ask(client, data, page["id"], "@agent one")
    await ask(client, data, page["id"], "@agent two")
    monkeypatch.setattr(tools, "REQUEST_LIMIT", 1)
    async with connected(token) as c:
        result = ok(await c.call_tool("list_requests", {}))
        assert [r["id"] for r in result["requests"]] == [first]
        assert result["more"] is True
        monkeypatch.setattr(tools, "REQUEST_LIMIT", 50)
        assert ok(await c.call_tool("list_requests", {}))["more"] is False


async def test_rate_limited_tool_fails_closed_without_a_request(client, monkeypatch):
    from app.mcp import tools

    _, token = await agent_token(client)
    monkeypatch.setattr(tools, "_request", lambda ctx: None)
    async with connected(token) as c:
        message = failed(
            await c.call_tool(
                "publish_page",
                {"title": "T", "files": [{"path": "index.html", "content": "<p>x</p>"}]},
            )
        )
        assert "rate limit" in message
        assert ok(await c.call_tool("list_pages", {}))["pages"] == []


async def test_lifespan_cleans_up_even_if_mcp_shutdown_fails(monkeypatch):
    import pytest

    from app import main
    from app.services import webhooks as webhooks_service

    @asynccontextmanager
    async def broken():
        yield
        raise RuntimeError("mcp shutdown failed")

    stopped = []

    async def stop():
        stopped.append(True)

    # Nothing real is started, so the patched stop leaves nothing running behind.
    monkeypatch.setattr(config.get_settings(), "webhook_worker", False)
    monkeypatch.setattr(config.get_settings(), "retention_enabled", False)
    monkeypatch.setattr(mcp_server, "running", broken)
    monkeypatch.setattr(webhooks_service.worker, "stop", stop)
    with pytest.raises(RuntimeError):
        async with main.lifespan(app):
            pass
    assert stopped == [True]


async def test_brief_question_and_page_note_through_the_tools(client):
    data, token = await agent_token(client)
    page = (
        await client.post(
            "/v1/pages",
            json={"title": "Report", "files": [{"path": "index.html", "content": "<p>x</p>"}]},
            headers=auth(data),
        )
    ).json()["page"]
    request_id = await ask(client, data, page["id"])
    async with connected(token) as c:
        noted = ok(
            await c.call_tool(
                "update_page_context", {"page_id": page["id"], "text": "Board audience."}
            )
        )
        assert noted["context"] == "Board audience."
        assert (
            ok(await c.call_tool("get_page", {"page_id": page["id"]}))["context"]
            == "Board audience."
        )
        ok(
            await c.call_tool(
                "set_request_brief", {"request_id": request_id, "brief": "Keep it to two lines."}
            )
        )
        item = ok(await c.call_tool("list_requests", {}))["requests"][0]
        assert item["brief"] == "Keep it to two lines."
        claimed = ok(await c.call_tool("claim_request", {"request_id": request_id}))
        assert claimed["page_context"] == "Board audience."
        asked = ok(
            await c.call_tool(
                "ask_requester", {"request_id": request_id, "question": "Which two lines?"}
            )
        )
        assert asked["status"] == "needs_info"
        waiting = ok(await c.call_tool("list_requests", {"status": "needs_info"}))["requests"]
        assert [r["id"] for r in waiting] == [request_id]
