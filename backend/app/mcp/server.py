"""The MCP endpoint at /mcp: wiring, sign-in and the per-run session manager.

Agents (Claude Desktop, Claude Code, ChatGPT, Codex) send an ordinary Paddock `pdk_` token as a
Bearer token. The server is stateless: every HTTP request stands alone, so a restart never breaks
a connected client and nothing is kept in memory between calls.
"""

from contextlib import asynccontextmanager

from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import get_settings
from app.db.session import get_sessionmaker
from app.mcp import tools
from app.services import tokens

PATH = "/mcp"

INSTRUCTIONS = """Paddock hosts web pages that you publish for a person, keeps every version, and
collects their comments. Publish with publish_page, then share the returned url. Before changing
a page, read it with get_page. People ask you for changes by writing @agent in a comment: find
those with list_requests, claim one, publish the fix, then complete it with the new version."""


class PaddockTokenVerifier:
    """Checks the Bearer token with the same lookup the REST API uses. A revoked, expired or
    unknown token gives None, which the library turns into a 401 with the metadata hint."""

    async def verify_token(self, token: str) -> AccessToken | None:
        async with get_sessionmaker()() as db:
            found = await tokens.find(db, token.strip())
        if found is None:
            return None
        user, row = found
        return AccessToken(
            token=token.strip(),
            client_id=row.client_id or str(row.id),
            scopes=list(row.scopes),
            subject=str(user.id),
        )


def _server() -> MCPServer:
    api = get_settings().api_public_url.rstrip("/")
    server = MCPServer(
        name="Paddock",
        instructions=INSTRUCTIONS,
        website_url=get_settings().app_origin,
        token_verifier=PaddockTokenVerifier(),
        auth=AuthSettings(
            issuer_url=api,
            resource_server_url=f"{api}{PATH}",
            # Paddock tokens are not bound to a resource; the verifier checks them itself.
            validate_token_resource=False,
        ),
    )
    for fn, annotations in tools.TOOLS:
        server.add_tool(fn, annotations=annotations)
    return server


server = _server()
_inner: ASGIApp | None = None


@asynccontextmanager
async def running():
    """Start the library's session manager. Called from the FastAPI lifespan.

    The library allows one run per session manager, so each run builds a fresh inner app.
    """
    global _inner
    settings = get_settings()
    inner = server.streamable_http_app(
        streamable_http_path=PATH,
        stateless_http=True,
        json_response=True,
        # Same ceiling the API applies to every request body, so large bundles fit.
        max_request_body_size=settings.max_bundle_bytes * 2 + 2 * 1024 * 1024,
        # Callers prove who they are with a Bearer token, not by where they connect from, so the
        # localhost-only Host check the library turns on by default does not apply here.
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )
    async with server.session_manager.run():
        _inner = inner
        try:
            yield
        finally:
            _inner = None


class _McpApp:
    """The ASGI app behind /mcp and /mcp/. Both spellings reach the same endpoint. (A class, so
    Starlette routes hand it the raw ASGI call instead of wrapping it as a GET handler.)"""

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if _inner is None:
            response = JSONResponse({"error": "The MCP server is starting. Try again."}, 503)
            await response(scope, receive, send)
            return
        if scope["path"] != PATH:
            scope = {**scope, "path": PATH, "raw_path": PATH.encode()}
        await _inner(scope, receive, send)


mcp_app = _McpApp()
