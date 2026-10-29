"""A stand-in for Claude Desktop or ChatGPT. It connects to a running Paddock the way they do.

    PADDOCK_SIGN_IN_TOKEN=<your sign-in token> python scripts/mcp_standin.py --url http://localhost:8000

The sign-in token plays the part of the person clicking Allow on the consent page. It is the
token your browser holds after signing in. It is read from the environment variable
PADDOCK_SIGN_IN_TOKEN (not a command line flag, so it stays out of the process list). Use it
only on a machine you trust, and never paste it into chat. The script prints each step,
publishes one small test page, and at the end revokes the token it created.
"""

import argparse
import asyncio
import base64
import hashlib
import json
import os
import secrets
from urllib.parse import parse_qs, urlsplit

import httpx
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

REDIRECT = "http://127.0.0.1:53682/callback"


def step(n: int, text: str) -> None:
    print(f"{n}. {text}")


def query_of(url: str) -> dict[str, str]:
    return {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True, help="the API address, like http://localhost:8000")
    args = ap.parse_args()
    sign_in = os.environ.get("PADDOCK_SIGN_IN_TOKEN", "")
    if not sign_in:
        raise SystemExit("Set PADDOCK_SIGN_IN_TOKEN to your sign-in token.")
    base = args.url.rstrip("/")

    async with httpx.AsyncClient(base_url=base, follow_redirects=False, timeout=30) as http:
        refused = await http.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
        step(1, f"/mcp without a token answered {refused.status_code}")
        hint = refused.headers.get("www-authenticate", "")
        assert "resource_metadata=" in hint, "the 401 does not point at the metadata"
        resource_url = hint.split('resource_metadata="')[1].split('"')[0]

        resource = (await http.get(resource_url)).json()
        server = (
            await http.get(
                f"{resource['authorization_servers'][0]}/.well-known/oauth-authorization-server"
            )
        ).json()
        step(2, f"found the sign-in server at {server['issuer']}")

        registered = await http.post(
            server["registration_endpoint"],
            json={"client_name": "Paddock stand-in", "redirect_uris": [REDIRECT]},
        )
        registered.raise_for_status()
        client_id = registered.json()["client_id"]
        step(3, f"registered as {client_id}")

        verifier = secrets.token_urlsafe(48)
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .rstrip(b"=")
            .decode()
        )
        params = {
            "client_id": client_id,
            "redirect_uri": REDIRECT,
            "response_type": "code",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "scope": "pages:read pages:write",
            "state": secrets.token_urlsafe(8),
        }
        authorize = await http.get(server["authorization_endpoint"], params=params)
        assert authorize.status_code == 302, authorize.text
        consent_url = authorize.headers["location"]
        step(4, f"the person would be sent to {urlsplit(consent_url).path}")

        approved = await http.post(
            f"{base}/v1/oauth/approve",
            json={**query_of(consent_url), "decision": "allow"},
            headers={"Authorization": f"Bearer {sign_in}"},
        )
        approved.raise_for_status()
        back = query_of(approved.json()["redirect_to"])
        assert back["state"] == params["state"], "state did not come back"
        step(5, "the person clicked Allow and the app received a one time code")

        token = await http.post(
            server["token_endpoint"],
            data={
                "grant_type": "authorization_code",
                "code": back["code"],
                "code_verifier": verifier,
                "redirect_uri": REDIRECT,
                "client_id": client_id,
            },
        )
        token.raise_for_status()
        access = token.json()["access_token"]
        step(6, f"exchanged the code for a token ({access[:8]}...)")

    headers = {"Authorization": f"Bearer {access}"}
    async with httpx.AsyncClient(headers=headers, timeout=30) as http:
        async with Client(streamable_http_client(f"{base}/mcp", http_client=http)) as mcp:
            tools = await mcp.list_tools()
            step(7, "tools: " + ", ".join(sorted(t.name for t in tools.tools)))
            pages = await mcp.call_tool("list_pages", {})
            step(8, f"list_pages returned: {pages.content[0].text[:200]}")
            made = await mcp.call_tool(
                "publish_page",
                {
                    "title": "Hello from the stand-in",
                    "files": [{"path": "index.html", "content": "<h1>Connected</h1>"}],
                },
            )
            step(9, f"publish_page returned: {json.loads(made.content[0].text)}")

    # Clean up: take back the access token this script made, using the person's sign-in.
    person = {"Authorization": f"Bearer {sign_in}"}
    async with httpx.AsyncClient(base_url=base, headers=person, timeout=30) as http:
        rows = (await http.get("/v1/tokens")).json()
        mine = [t for t in rows if t["source"] == "oauth" and access.startswith(t["prefix"])]
        mine.sort(key=lambda t: t["created_at"], reverse=True)
        gone = await http.delete(f"/v1/tokens/{mine[0]['id']}")
        gone.raise_for_status()
        after = await http.get("/mcp", headers={"Authorization": f"Bearer {access}"})
        step(10, f"revoked the stand-in token (it now gets {after.status_code} from /mcp)")


if __name__ == "__main__":
    asyncio.run(main())
