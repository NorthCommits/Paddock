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
