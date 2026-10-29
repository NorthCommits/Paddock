"""The whole connection the way a real app does it, from discovery to a published page."""

from urllib.parse import urlsplit

import httpx2

from app.core import config
from app.main import app as asgi_app
from app.mcp import server as mcp_server

from .helpers import auth, csrf, signup
from .test_mcp import INITIALIZE, MCP_HEADERS, connected, ok
from .test_oauth_api import CHALLENGE, REDIRECT, VERIFIER, query_of


async def test_full_flow_discovery_to_publish(client):
    person = await signup(client)
    api = config.get_settings().api_public_url.rstrip("/")

    plain = httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=asgi_app), base_url="http://test", follow_redirects=False
    )
    async with plain as app:  # the connecting app has no account and no headers
        # 1. The first call is refused and points at the metadata.
        async with mcp_server.running():
            refused = await app.post("/mcp", json=INITIALIZE, headers=MCP_HEADERS)
        assert refused.status_code == 401
        hint = refused.headers["www-authenticate"]
        resource_url = hint.split('resource_metadata="')[1].split('"')[0]
        assert resource_url.startswith(api)

        # 2. Discovery: resource document, then the authorization server document.
        resource = (await app.get(urlsplit(resource_url).path)).json()
        issuer = resource["authorization_servers"][0]
        server = (await app.get("/.well-known/oauth-authorization-server")).json()
        assert server["issuer"] == issuer
        assert urlsplit(server["registration_endpoint"]).path == "/oauth/register"

        # 3. Register itself.
        registered = await app.post(
            urlsplit(server["registration_endpoint"]).path,
            json={"client_name": "Stand-in agent", "redirect_uris": [REDIRECT]},
        )
        assert registered.status_code == 201
        client_id = registered.json()["client_id"]

        # 4. Send the person to the consent page.
        params = {
            "client_id": client_id,
            "redirect_uri": REDIRECT,
            "response_type": "code",
            "code_challenge": CHALLENGE,
            "code_challenge_method": "S256",
            "scope": "pages:read pages:write",
            "state": "xyz",
        }
        authorize = await app.get(urlsplit(server["authorization_endpoint"]).path, params=params)
        assert authorize.status_code == 302
        assert urlsplit(authorize.headers["location"]).path == "/oauth/consent"
        shown = query_of(authorize.headers["location"])

        # 5. The person clicks Allow on the consent page.
        approved = await client.post(
            "/v1/oauth/approve", json={**shown, "decision": "allow"}, headers=csrf(person)
        )
        assert approved.status_code == 200, approved.text
        back = query_of(approved.json()["redirect_to"])
        assert back["state"] == "xyz"

        # 6. The app trades the code for a token.
        token = await app.post(
            urlsplit(server["token_endpoint"]).path,
            data={
                "grant_type": "authorization_code",
                "code": back["code"],
                "code_verifier": VERIFIER,
                "redirect_uri": REDIRECT,
                "client_id": client_id,
            },
        )
        assert token.status_code == 200, token.text
        access = token.json()["access_token"]
        assert access.startswith("pdk_")

    # 7. The app publishes a page over MCP.
    async with connected(access) as mcp:
        made = ok(
            await mcp.call_tool(
                "publish_page",
                {
                    "title": "From a stand-in",
                    "files": [{"path": "index.html", "content": "<p>Hi</p>"}],
                },
            )
        )
    assert made["created"] is True

    # 8. The page exists for the person, and the token is listed as an app connection.
    page = await client.get(f"/v1/pages/{made['page_id']}", headers=auth(person))
    assert page.status_code == 200
    assert page.json()["title"] == "From a stand-in"
    tokens = (await client.get("/v1/tokens", headers=auth(person))).json()
    items = tokens["items"] if isinstance(tokens, dict) else tokens
    assert [t["source"] for t in items if t["name"] != "test agent"] == ["oauth"]
