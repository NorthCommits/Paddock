import base64
import hashlib
from urllib.parse import parse_qs, urlsplit

from sqlalchemy import func, select

from app.core import ratelimit
from app.core.config import get_settings
from app.db.models import ApiToken, OAuthCode
from app.db.session import get_sessionmaker

from .helpers import auth, csrf, make_token, signup

VERIFIER = "v" * 50
CHALLENGE = (
    base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest()).rstrip(b"=").decode()
)
REDIRECT = "https://app.example.com/cb"


async def register(client, uris=(REDIRECT,), name="Claude Desktop"):
    r = await client.post(
        "/oauth/register", json={"client_name": name, "redirect_uris": list(uris)}
    )
    assert r.status_code == 201, r.text
    return r.json()


def request_body(client_id, **over):
    body = {
        "client_id": client_id,
        "redirect_uri": REDIRECT,
        "code_challenge": CHALLENGE,
        "code_challenge_method": "S256",
        "scope": "pages:read pages:write",
        "response_type": "code",
        "state": "st-1",
    }
    body.update(over)
    return body


def query_of(url):
    return {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}


async def allowed_code(client, data, client_id, **over):
    r = await client.post(
        "/v1/oauth/approve",
        json={**request_body(client_id, **over), "decision": "allow"},
        headers=csrf(data),
    )
    assert r.status_code == 200, r.text
    return query_of(r.json()["redirect_to"])["code"]


def token_form(client_id, code, **over):
    form = {
        "grant_type": "authorization_code",
        "code": code,
        "code_verifier": VERIFIER,
        "redirect_uri": REDIRECT,
        "client_id": client_id,
    }
    form.update(over)
    return form


async def test_metadata_documents(client):
    issuer = get_settings().api_public_url.rstrip("/")
    server = (await client.get("/.well-known/oauth-authorization-server")).json()
    assert server["issuer"] == issuer
    assert server["registration_endpoint"] == f"{issuer}/oauth/register"
    assert server["authorization_endpoint"] == f"{issuer}/oauth/authorize"
    assert server["token_endpoint"] == f"{issuer}/oauth/token"
    assert server["code_challenge_methods_supported"] == ["S256"]
    assert server["token_endpoint_auth_methods_supported"] == ["none"]
    assert server["grant_types_supported"] == ["authorization_code"]
    assert "events:read" not in server["scopes_supported"]
    root = (await client.get("/.well-known/oauth-protected-resource")).json()
    assert root["resource"] == issuer and root["authorization_servers"] == [issuer]
    mcp = (await client.get("/.well-known/oauth-protected-resource/mcp")).json()
    assert mcp["resource"] == issuer + "/mcp"
    assert mcp["scopes_supported"] == server["scopes_supported"]


async def test_register_then_authorize_redirects_to_consent(client):
    app = await register(client)
    assert app["token_endpoint_auth_method"] == "none"
    assert app["grant_types"] == ["authorization_code"] and app["response_types"] == ["code"]
    assert app["redirect_uris"] == [REDIRECT]
    params = {k: v for k, v in request_body(app["client_id"]).items()}
    r = await client.get("/oauth/authorize", params=params)
    assert r.status_code == 302
    where = urlsplit(r.headers["location"])
    assert f"{where.scheme}://{where.netloc}{where.path}" == (
        get_settings().app_origin.rstrip("/") + "/oauth/consent"
    )
    assert query_of(r.headers["location"]) == params


async def test_authorize_redirects_redirectable_errors_to_the_client(client):
    app = await register(client, uris=["https://app.example.com/cb?tenant=a"])
    params = request_body(app["client_id"], redirect_uri="https://app.example.com/cb?tenant=a")
    for over, code in [
        ({"response_type": "token"}, "unsupported_response_type"),
        ({"code_challenge_method": "plain"}, "invalid_request"),
        ({"scope": "events:read"}, "invalid_scope"),
        ({"code_challenge": ""}, "invalid_request"),
    ]:
        r = await client.get("/oauth/authorize", params={**params, **over})
        assert r.status_code == 302
        location = r.headers["location"]
        assert location.startswith("https://app.example.com/cb?tenant=a&")
        got = query_of(location)
        assert got["tenant"] == "a" and got["error"] == code and got["state"] == "st-1"


async def test_authorize_with_unknown_client_returns_400_and_never_redirects(client):
    r = await client.get("/oauth/authorize", params=request_body("nope"))
    assert r.status_code == 400
    assert "location" not in r.headers
    assert r.json()["error"] == "invalid_request" and r.json()["error_description"]


async def test_authorize_with_unregistered_redirect_returns_400(client):
    app = await register(client)
    for bad in [REDIRECT + "/", "https://evil.example.com/cb", "https://app.example.com/cb?x=1"]:
        r = await client.get(
            "/oauth/authorize", params=request_body(app["client_id"], redirect_uri=bad)
        )
        assert r.status_code == 400, bad
        assert "location" not in r.headers
    # A missing redirect address or client id is also a plain 400.
    assert (await client.get("/oauth/authorize")).status_code == 400
    r = await client.get("/oauth/authorize", params={"client_id": app["client_id"]})
    assert r.status_code == 400 and "location" not in r.headers


async def test_preview_describes_the_request(client):
    data = await signup(client)
    app = await register(client)
    r = await client.post(
        "/v1/oauth/preview", json=request_body(app["client_id"]), headers=csrf(data)
    )
    assert r.status_code == 200
    assert r.json() == {
        "client_name": "Claude Desktop",
        "redirect_host": "app.example.com",
        "scopes": ["pages:read", "pages:write"],
    }
    bad = await client.post(
        "/v1/oauth/preview",
        json=request_body(app["client_id"], redirect_uri="https://evil.example.com/cb"),
        headers=csrf(data),
    )
    assert bad.status_code == 400 and bad.json()["error"] == "invalid_request"


async def test_approve_allow_returns_code_and_state(client):
    data = await signup(client)
    app = await register(client, uris=["https://app.example.com/cb?tenant=a"])
    r = await client.post(
        "/v1/oauth/approve",
        json={
            **request_body(app["client_id"], redirect_uri="https://app.example.com/cb?tenant=a"),
            "decision": "allow",
        },
        headers=csrf(data),
    )
    assert r.status_code == 200
    target = r.json()["redirect_to"]
    assert target.startswith("https://app.example.com/cb?tenant=a&")
    got = query_of(target)
    assert got["code"] and got["state"] == "st-1" and got["tenant"] == "a"
    assert "error" not in got


async def test_approve_checks_the_request_before_creating_anything(client):
    data = await signup(client)
    app = await register(client)
    for over in [
        {"redirect_uri": "https://evil.example.com/cb"},
        {"code_challenge_method": "plain"},
        {"scope": "events:read"},
    ]:
        r = await client.post(
            "/v1/oauth/approve",
            json={**request_body(app["client_id"], **over), "decision": "allow"},
            headers=csrf(data),
        )
        assert r.status_code == 400
    async with get_sessionmaker()() as db:
        assert await db.scalar(select(func.count()).select_from(OAuthCode)) == 0


async def test_deny_returns_access_denied_and_no_token_exists(client):
    data = await signup(client)
    app = await register(client)
    r = await client.post(
        "/v1/oauth/approve",
        json={**request_body(app["client_id"]), "decision": "deny"},
        headers=csrf(data),
    )
    assert r.status_code == 200
    got = query_of(r.json()["redirect_to"])
    assert got["error"] == "access_denied" and got["state"] == "st-1" and "code" not in got
    async with get_sessionmaker()() as db:
        assert await db.scalar(select(func.count()).select_from(OAuthCode)) == 0
        assert await db.scalar(select(func.count()).select_from(ApiToken)) == 0


async def test_unverified_email_cannot_approve(client):
    data = await signup(client, verify=False)
    app = await register(client)
    for path in ("/v1/oauth/approve", "/v1/oauth/preview"):
        r = await client.post(
            path, json={**request_body(app["client_id"]), "decision": "allow"}, headers=csrf(data)
        )
        assert r.status_code == 403
        assert r.json()["error"]["code"] == "email_not_verified"


async def test_agent_token_cannot_approve(client):
    data = await signup(client)
    agent = await make_token(client, data, scopes=("pages:read", "pages:write"))
    app = await register(client)
    for path in ("/v1/oauth/approve", "/v1/oauth/preview"):
        r = await client.post(
            path,
            json={**request_body(app["client_id"]), "decision": "allow"},
            headers=auth(token=agent["token"]),
        )
        assert r.status_code == 403
    async with get_sessionmaker()() as db:
        assert await db.scalar(select(func.count()).select_from(OAuthCode)) == 0


async def test_token_endpoint_full_flow_returns_pdk_token(client):
    data = await signup(client)
    app = await register(client)
    code = await allowed_code(client, data, app["client_id"])
    r = await client.post("/oauth/token", data=token_form(app["client_id"], code))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["token_type"] == "Bearer" and body["access_token"].startswith("pdk_")
    assert body["scope"] == "pages:read pages:write"
    me = await client.get("/v1/me", headers=auth(token=body["access_token"]))
    assert me.status_code == 200
    listed = (await client.get("/v1/tokens", headers=csrf(data))).json()
    assert [t["source"] for t in listed] == ["oauth"]


async def test_token_endpoint_errors_use_the_oauth_shape(client):
    app = await register(client)
    r = await client.post("/oauth/token", data=token_form(app["client_id"], "bogus"))
    assert r.status_code == 400 and r.json()["error"] == "invalid_grant"
    r = await client.post("/oauth/token", data=token_form("x", "y", grant_type="password"))
    assert r.status_code == 400 and r.json()["error"] == "unsupported_grant_type"
    r = await client.post("/oauth/token", data={})
    assert r.status_code == 400 and "error_description" in r.json()


async def test_token_endpoint_reused_code_fails_and_token_stops_working(client):
    data = await signup(client)
    app = await register(client)
    code = await allowed_code(client, data, app["client_id"])
    first = await client.post("/oauth/token", data=token_form(app["client_id"], code))
    access = first.json()["access_token"]
    assert (await client.get("/v1/me", headers=auth(token=access))).status_code == 200
    second = await client.post("/oauth/token", data=token_form(app["client_id"], code))
    assert second.status_code == 400 and second.json()["error"] == "invalid_grant"
    assert (await client.get("/v1/me", headers=auth(token=access))).status_code == 401


async def test_cors_open_for_oauth_paths_but_not_for_v1(client):
    outsider = {"Origin": "https://tool.example.org"}
    for path in ("/.well-known/oauth-authorization-server", "/oauth/register"):
        pre = await client.options(
            path,
            headers={
                **outsider,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,authorization",
            },
        )
        assert pre.status_code == 200
        assert pre.headers["access-control-allow-origin"] == "*"
        assert "access-control-allow-credentials" not in pre.headers
    got = await client.get("/.well-known/oauth-authorization-server", headers=outsider)
    assert got.headers["access-control-allow-origin"] == "*"
    assert "access-control-allow-credentials" not in got.headers

    # /v1 keeps the site-only rule, including for a path that merely contains "oauth".
    for path in ("/v1/handles/check?handle=zed", "/v1/oauth/preview"):
        r = await client.get(path, headers=outsider)
        assert "access-control-allow-origin" not in r.headers
    site = get_settings().app_origin
    r = await client.get("/v1/handles/check?handle=zed", headers={"Origin": site})
    assert r.headers["access-control-allow-origin"] == site
    assert r.headers["access-control-allow-credentials"] == "true"


async def test_register_is_rate_limited(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "rate_limit_enabled", True)
    ratelimit.limiter.windows.clear()
    monkeypatch.setattr(ratelimit, "now", lambda: 1000.0)
    monkeypatch.setattr(ratelimit, "RULES", {**ratelimit.RULES, "register": 2})
    body = {"client_name": "x", "redirect_uris": [REDIRECT]}
    # A different made-up credential on every call must not give a fresh allowance.
    codes = [
        (
            await client.post(
                "/oauth/register", json=body, headers={"Authorization": f"Bearer junk-{i}"}
            )
        ).status_code
        for i in range(2)
    ]
    assert codes == [201, 201]
    r = await client.post(
        "/oauth/register", json=body, headers={"Authorization": "Bearer junk-final"}
    )
    assert r.status_code == 429
    assert int(r.headers["retry-after"]) >= 1
    ratelimit.limiter.windows.clear()


async def test_consent_redirect_passes_only_named_parameters(client):
    app = await register(client)
    params = request_body(app["client_id"])
    r = await client.get(
        "/oauth/authorize",
        params=[*params.items(), ("state", "second"), ("evil", "1")],
    )
    assert r.status_code == 302
    query = parse_qs(urlsplit(r.headers["location"]).query)
    assert set(query) == set(params)
    assert all(len(v) == 1 for v in query.values())
    assert "evil" not in query


async def test_existing_redirect_query_is_kept_byte_for_byte(client):
    uri = "https://app.example.com/cb?a=b%20c&flag"
    app = await register(client, uris=[uri])
    data = await signup(client)
    r = await client.post(
        "/v1/oauth/approve",
        json={**request_body(app["client_id"], redirect_uri=uri), "decision": "allow"},
        headers=csrf(data),
    )
    assert r.json()["redirect_to"].startswith(uri + "&code=")
    bad = await client.get(
        "/oauth/authorize",
        params=request_body(app["client_id"], redirect_uri=uri, response_type="token"),
    )
    assert bad.headers["location"].startswith(uri + "&error=")


async def test_register_without_name_uses_the_host_and_is_not_cached(client):
    r = await client.post("/oauth/register", json={"redirect_uris": [REDIRECT]})
    assert r.status_code == 201
    assert r.json()["client_name"] == "app.example.com"
    assert r.headers["cache-control"] == "no-store" and r.headers["pragma"] == "no-cache"


async def test_register_failures_use_the_oauth_error_shape(client):
    cases = [
        ({"client_name": "x"}, "invalid_redirect_uri"),
        ({"client_name": "x", "redirect_uris": []}, "invalid_redirect_uri"),
        ({"client_name": "x", "redirect_uris": "https://a.example.com"}, "invalid_redirect_uri"),
        ({"client_name": "x", "redirect_uris": ["http://evil.com/cb"]}, "invalid_redirect_uri"),
        ({"client_name": 5, "redirect_uris": [REDIRECT]}, "invalid_client_metadata"),
        ({"client_name": "n" * 101, "redirect_uris": [REDIRECT]}, "invalid_client_metadata"),
    ]
    for body, code in cases:
        r = await client.post("/oauth/register", json=body)
        assert r.status_code == 400, body
        assert r.json()["error"] == code and r.json()["error_description"]
    r = await client.post("/oauth/register", content=b"not json")
    assert r.status_code == 400 and r.json()["error"] == "invalid_client_metadata"


async def test_overlong_authorize_parameters_are_400_or_a_redirect(client):
    app = await register(client)
    r = await client.get(
        "/oauth/authorize", params=request_body(app["client_id"], state="s" * 2001)
    )
    assert r.status_code == 400 and r.json()["error"] == "invalid_request"
    r = await client.get(
        "/oauth/authorize", params=request_body(app["client_id"], scope="pages:read " * 60)
    )
    assert r.status_code == 302
    got = query_of(r.headers["location"])
    assert got["error"] == "invalid_request" and got["state"] == "st-1"
    r = await client.get(
        "/oauth/authorize",
        params=request_body(app["client_id"], redirect_uri="https://a.example.com/" + "a" * 1000),
    )
    assert r.status_code == 400


async def test_missing_response_type_is_invalid_request(client):
    app = await register(client)
    params = request_body(app["client_id"])
    del params["response_type"]
    r = await client.get("/oauth/authorize", params=params)
    assert r.status_code == 302 and query_of(r.headers["location"])["error"] == "invalid_request"
    r = await client.get("/oauth/authorize", params={**params, "response_type": "token"})
    assert query_of(r.headers["location"])["error"] == "unsupported_response_type"


async def test_loopback_port_may_differ_end_to_end(client):
    data = await signup(client)
    app = await register(client, uris=["http://127.0.0.1:5555/cb"])
    uri = "http://127.0.0.1:49152/cb"
    r = await client.post(
        "/v1/oauth/approve",
        json={**request_body(app["client_id"], redirect_uri=uri), "decision": "allow"},
        headers=csrf(data),
    )
    assert r.status_code == 200
    target = r.json()["redirect_to"]
    assert target.startswith("http://127.0.0.1:49152/cb?code=")
    code = query_of(target)["code"]
    other = await client.post(
        "/oauth/token",
        data=token_form(app["client_id"], code, redirect_uri="http://127.0.0.1:49153/cb"),
    )
    assert other.status_code == 400
    # The failed attempt must not have used up the code.
    ok = await client.post(
        "/oauth/token", data=token_form(app["client_id"], code, redirect_uri=uri)
    )
    assert ok.status_code == 200


async def test_state_round_trips_intact(client):
    data = await signup(client)
    app = await register(client)
    state = "a&b=c #d+e f/%"
    r = await client.post(
        "/v1/oauth/approve",
        json={**request_body(app["client_id"], state=state), "decision": "allow"},
        headers=csrf(data),
    )
    assert query_of(r.json()["redirect_to"])["state"] == state
    r = await client.post(
        "/v1/oauth/approve",
        json={**request_body(app["client_id"], state=state), "decision": "deny"},
        headers=csrf(data),
    )
    assert query_of(r.json()["redirect_to"])["state"] == state


async def test_approve_needs_the_bearer_header_not_a_cookie(client):
    """Sign-in is a Bearer header only (no cookie sessions), so there is no CSRF surface:
    a request carrying only cookies is refused."""
    await signup(client)
    app = await register(client)
    del client.headers["Authorization"]
    client.cookies.set("session", "anything")
    r = await client.post(
        "/v1/oauth/approve", json={**request_body(app["client_id"]), "decision": "allow"}
    )
    assert r.status_code == 401
