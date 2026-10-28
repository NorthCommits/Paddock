import pytest

from app.core import ratelimit
from app.core.config import get_settings

from .helpers import auth, make_token, new_page, signup
from .test_comments import comment, setup
from .test_sharing import BO, other


@pytest.fixture
def limits_on(monkeypatch):
    """Switch limits on with small numbers, and start every test with empty counters."""
    monkeypatch.setattr(get_settings(), "rate_limit_enabled", True)
    ratelimit.limiter.windows.clear()
    clock = {"t": 1000.0}
    monkeypatch.setattr(ratelimit, "now", lambda: clock["t"])
    yield clock
    ratelimit.limiter.windows.clear()


def small(monkeypatch, **rules):
    monkeypatch.setattr(ratelimit, "RULES", {**ratelimit.RULES, **rules})


# ------------------------------------------------------------ general limit


async def test_a_caller_over_the_limit_gets_429_with_retry_after(client, limits_on, monkeypatch):
    small(monkeypatch, general=3)
    data = await signup(client)  # one request used
    for _ in range(2):
        assert (await client.get("/v1/me", headers=auth(data))).status_code == 200
    r = await client.get("/v1/me", headers=auth(data))
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "rate_limited"
    assert int(r.headers["retry-after"]) >= 1
    assert r.headers["x-request-id"]


async def test_the_window_resets(client, limits_on, monkeypatch):
    small(monkeypatch, general=2)
    data = await signup(client)
    assert (await client.get("/v1/me", headers=auth(data))).status_code == 200
    assert (await client.get("/v1/me", headers=auth(data))).status_code == 429
    limits_on["t"] += ratelimit.WINDOW + 1
    assert (await client.get("/v1/me", headers=auth(data))).status_code == 200


async def test_callers_are_counted_separately(client, limits_on, monkeypatch):
    small(monkeypatch, general=3)
    data = await signup(client)
    async with other() as bo:
        bo_data = await signup(bo, **BO)
        for _ in range(2):
            await client.get("/v1/me", headers=auth(data))
        assert (await client.get("/v1/me", headers=auth(data))).status_code == 429
        assert (await bo.get("/v1/me", headers=auth(bo_data))).status_code == 200


async def test_health_checks_are_never_counted(client, limits_on, monkeypatch):
    small(monkeypatch, anonymous=1)
    for _ in range(5):
        assert (await client.get("/healthz")).status_code == 200


async def test_anonymous_callers_are_counted_by_address(client, limits_on, monkeypatch):
    small(monkeypatch, anonymous=2)
    for _ in range(2):
        assert (await client.get("/v1/handles/check?handle=zed")).status_code in (200, 401)
    assert (await client.get("/v1/handles/check?handle=zed")).status_code == 429


async def test_forwarded_for_is_ignored_unless_proxies_are_configured(
    client, limits_on, monkeypatch
):
    small(monkeypatch, anonymous=1)
    path = "/v1/handles/check?handle=zed"
    await client.get(path, headers={"x-forwarded-for": "1.1.1.1"})
    # Same caller, new header value: still counted together, so a spoofed header buys nothing.
    assert (await client.get(path, headers={"x-forwarded-for": "2.2.2.2"})).status_code == 429


async def test_forwarded_for_is_used_when_configured(client, limits_on, monkeypatch):
    monkeypatch.setattr(get_settings(), "proxy_hops", 1)
    small(monkeypatch, anonymous=1)
    path = "/v1/handles/check?handle=zed"
    first = {"x-forwarded-for": "spoofed, 1.1.1.1"}  # only the entry the proxy added counts
    assert (await client.get(path, headers=first)).status_code != 429
    assert (
        await client.get(path, headers={"x-forwarded-for": "other, 1.1.1.1"})
    ).status_code == 429
    assert (await client.get(path, headers={"x-forwarded-for": "2.2.2.2"})).status_code != 429


def test_caller_ip_picks_the_entry_the_last_proxy_added():
    class Req:
        def __init__(self, header):
            self.headers = {"x-forwarded-for": header} if header else {}
            self.client = type("C", (), {"host": "10.0.0.1"})()

    settings = get_settings()
    original = settings.proxy_hops
    try:
        settings.proxy_hops = 2
        assert ratelimit.caller_ip(Req("evil, client, vercel")) == "client"
        assert ratelimit.caller_ip(Req("only-one")) == "10.0.0.1"  # fewer than expected: ignore
        assert ratelimit.caller_ip(Req(None)) == "10.0.0.1"
        settings.proxy_hops = 0
        assert ratelimit.caller_ip(Req("a, b")) == "10.0.0.1"
    finally:
        settings.proxy_hops = original


# ------------------------------------------------------------ named limits


async def test_comments_have_their_own_limit(client, limits_on, monkeypatch):
    data, page_id = await setup(client)
    small(monkeypatch, comment=2)
    assert (await comment(client, data, page_id, "one")).status_code == 201
    assert (await comment(client, data, page_id, "two")).status_code == 201
    r = await comment(client, data, page_id, "three")
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "rate_limited"
    assert (
        await client.get(f"/v1/pages/{page_id}/comments", headers=auth(data))
    ).status_code == 200


async def test_publishing_has_its_own_limit(client, limits_on, monkeypatch):
    small(monkeypatch, publish=2)
    data, _ = await setup(client)  # the first publish
    assert (await new_page(client, data, title="Second"))["page"]["id"]
    r = await client.post(
        "/v1/pages",
        json={"title": "Third", "files": [{"path": "index.html", "content": "<p>x</p>"}]},
        headers=auth(data),
    )
    assert r.status_code == 429


async def test_agents_are_limited_per_token(client, limits_on, monkeypatch):
    data, page_id = await setup(client)
    one = (await make_token(client, data, scopes=("comments:write",)))["token"]
    two = (await make_token(client, data, scopes=("comments:write",)))["token"]
    small(monkeypatch, comment=1)
    post = lambda t: client.post(  # noqa: E731
        f"/v1/pages/{page_id}/comments", json={"body": "x"}, headers=auth(token=t)
    )
    assert (await post(one)).status_code == 201
    assert (await post(one)).status_code == 429
    assert (await post(two)).status_code == 201


async def test_token_creation_is_limited(client, limits_on, monkeypatch):
    data = await signup(client)
    small(monkeypatch, manage=1)
    await make_token(client, data)
    r = await client.post(
        "/v1/tokens", json={"name": "x", "scopes": ["pages:read"]}, headers=auth(data)
    )
    assert r.status_code == 429


async def test_limits_are_off_in_tests_by_default(client):
    data, page_id = await setup(client)
    for n in range(80):
        assert (await comment(client, data, page_id, f"c{n}")).status_code == 201


# ------------------------------------------------------------ headers and size


async def test_responses_carry_security_headers(client):
    r = await client.get("/healthz")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["referrer-policy"] == "no-referrer"
    assert r.headers["cache-control"] == "no-store"
    assert "strict-transport-security" not in r.headers


async def test_error_responses_carry_them_too(client):
    r = await client.get("/v1/me")
    assert r.status_code == 401
    assert r.headers["x-content-type-options"] == "nosniff"


async def test_hsts_in_production(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "environment", "production")
    r = await client.get("/healthz")
    assert "max-age" in r.headers["strict-transport-security"]


async def test_an_oversized_body_is_refused_up_front(client):
    data, _ = await setup(client)
    r = await client.post(
        "/v1/pages",
        content=b"{}",
        headers={**auth(data), "content-type": "application/json", "content-length": str(10**10)},
    )
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "payload_too_large"
