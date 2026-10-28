import asyncio
import hashlib
import hmac
import json

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import Webhook, WebhookDelivery
from app.db.session import get_engine
from app.services import webhooks

from .helpers import auth, make_token
from .test_comments import comment, setup
from .test_sharing import age_rows, other
from .test_versions import publish

URL = "https://hooks.example.com/paddock"
REAL_ADDRESSES = webhooks.addresses


@pytest.fixture(autouse=True)
def public_dns(monkeypatch):
    async def fake(host):
        return ["93.184.216.34"]

    monkeypatch.setattr(webhooks, "addresses", fake)


class Receiver:
    """Stands in for the customer's server. Records calls and answers as told."""

    def __init__(self, monkeypatch):
        self.calls: list[httpx.Request] = []
        self.answer = 200
        self.fail: Exception | None = None

        def handler(request: httpx.Request) -> httpx.Response:
            self.calls.append(request)
            if self.fail:
                raise self.fail
            return httpx.Response(self.answer)

        monkeypatch.setattr(
            webhooks,
            "make_client",
            lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        )


@pytest.fixture
def receiver(monkeypatch):
    return Receiver(monkeypatch)


async def register(client, data, types=(), url=URL, scopes=None):
    headers = auth(data) if scopes is None else auth(token=scopes)
    return await client.post(
        "/v1/webhooks", json={"url": url, "event_types": list(types)}, headers=headers
    )


async def deliveries() -> list[WebhookDelivery]:
    async with AsyncSession(get_engine()) as db:
        return list(await db.scalars(select(WebhookDelivery).order_by(WebhookDelivery.created_at)))


# ------------------------------------------------------------ managing webhooks


async def test_create_shows_the_secret_once_and_stores_it_encrypted(client):
    data, _ = await setup(client)
    r = await register(client, data, ["comment.created"])
    assert r.status_code == 201
    body = r.json()
    assert body["secret"].startswith("whsec_")
    assert body["event_types"] == ["comment.created"]
    assert body["active"] is True

    listing = (await client.get("/v1/webhooks", headers=auth(data))).json()
    assert [h["id"] for h in listing] == [body["id"]]
    assert "secret" not in listing[0]

    async with AsyncSession(get_engine()) as db:
        row = await db.scalar(select(Webhook))
    assert body["secret"] not in row.secret_enc
    assert webhooks.open_secret(row.secret_enc) == body["secret"]


@pytest.mark.parametrize(
    "url",
    [
        "ftp://hooks.example.com/x",
        "not a url",
        "https://user:pw@hooks.example.com/x",
        "http://127.0.0.1:8000/hook",
        "http://localhost/hook",
        "http://10.0.0.5/hook",
        "http://192.168.1.10/hook",
        "http://169.254.169.254/latest/meta-data",
        "http://[::1]/hook",
    ],
)
async def test_unsafe_addresses_are_refused(client, url, monkeypatch):
    monkeypatch.setattr(webhooks, "addresses", REAL_ADDRESSES)  # check against real lookups
    data, _ = await setup(client)
    assert (await register(client, data, url=url)).status_code == 422


async def test_a_host_that_points_inside_is_refused(client, monkeypatch):
    async def inside(host):
        return ["93.184.216.34", "10.0.0.7"]  # one private answer is enough to refuse

    monkeypatch.setattr(webhooks, "addresses", inside)
    data, _ = await setup(client)
    assert (await register(client, data)).status_code == 422


async def test_an_unknown_host_is_refused(client, monkeypatch):
    async def nothing(host):
        return []

    monkeypatch.setattr(webhooks, "addresses", nothing)
    data, _ = await setup(client)
    assert (await register(client, data)).status_code == 422


async def test_production_needs_https(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "environment", "production")
    data, _ = await setup(client)
    assert (await register(client, data, url="http://hooks.example.com/x")).status_code == 422
    assert (await register(client, data)).status_code == 201


async def test_unknown_event_types_are_refused(client):
    data, _ = await setup(client)
    assert (await register(client, data, ["comment.exploded"])).status_code == 422


async def test_a_person_can_have_ten_webhooks(client):
    data, _ = await setup(client)
    for _n in range(webhooks.MAX_WEBHOOKS):
        assert (await register(client, data)).status_code == 201
    assert (await register(client, data)).status_code == 409


async def test_tokens_need_the_events_scope(client):
    data, _ = await setup(client)
    bad = (await make_token(client, data, scopes=("pages:read",)))["token"]
    good = (await make_token(client, data, scopes=("events:read",)))["token"]
    assert (await register(client, data, scopes=bad)).status_code == 403
    assert (await client.get("/v1/webhooks", headers=auth(token=bad))).status_code == 403
    assert (await register(client, data, scopes=good)).status_code == 201


async def test_webhooks_belong_to_one_person(client):
    data, _ = await setup(client)
    hook = (await register(client, data)).json()
    async with other() as bo:
        from .helpers import signup
        from .test_sharing import BO

        bo_data = await signup(bo, **BO)
        assert (await bo.get("/v1/webhooks", headers=auth(bo_data))).json() == []
        assert (
            await bo.delete(f"/v1/webhooks/{hook['id']}", headers=auth(bo_data))
        ).status_code == 404
        assert (
            await bo.post(f"/v1/webhooks/{hook['id']}/test", headers=auth(bo_data))
        ).status_code == 404
        assert (
            await bo.get(f"/v1/webhooks/{hook['id']}/deliveries", headers=auth(bo_data))
        ).status_code == 404


async def test_edit_and_delete(client):
    data, _ = await setup(client)
    hook = (await register(client, data)).json()
    r = await client.patch(
        f"/v1/webhooks/{hook['id']}",
        json={"active": False, "event_types": ["page.deleted"]},
        headers=auth(data),
    )
    assert r.json()["active"] is False
    assert r.json()["event_types"] == ["page.deleted"]
    bad = await client.patch(
        f"/v1/webhooks/{hook['id']}", json={"event_types": ["x"]}, headers=auth(data)
    )
    assert bad.status_code == 422
    assert (
        await client.delete(f"/v1/webhooks/{hook['id']}", headers=auth(data))
    ).status_code == 204
    assert (await client.get("/v1/webhooks", headers=auth(data))).json() == []


# ------------------------------------------------------------ what gets queued


async def test_matching_events_queue_deliveries(client):
    data, page_id = await setup(client)
    await register(client, data, ["comment.created"])
    await register(client, data)  # no filter means every event
    await comment(client, data, page_id, "hello")
    await publish(client, data, page_id, "<p>x</p>")
    rows = await deliveries()
    # comment.created goes to both webhooks, version.published only to the second
    assert len(rows) == 3
    assert {r.status for r in rows} == {"pending"}


async def test_an_off_webhook_gets_nothing(client):
    data, page_id = await setup(client)
    hook = (await register(client, data)).json()
    await client.patch(f"/v1/webhooks/{hook['id']}", json={"active": False}, headers=auth(data))
    await comment(client, data, page_id, "hello")
    assert await deliveries() == []


async def test_a_webhook_only_hears_about_its_owners_pages(client):
    data, page_id = await setup(client)
    async with other() as bo:
        from .helpers import signup
        from .test_sharing import BO

        bo_data = await signup(bo, **BO)
        await register(bo, bo_data)
    await comment(client, data, page_id, "mine")
    assert await deliveries() == []


# ------------------------------------------------------------ sending


async def test_a_delivery_is_signed_and_marked_delivered(client, receiver):
    data, page_id = await setup(client)
    secret = (await register(client, data, ["comment.created"])).json()["secret"]
    await comment(client, data, page_id, "@agent hi")
    assert await webhooks.process_due() == 1

    (call,) = receiver.calls
    assert str(call.url) == URL
    body = call.content
    stamp = call.headers["x-paddock-timestamp"]
    expected = hmac.new(secret.encode(), stamp.encode() + b"." + body, hashlib.sha256).hexdigest()
    assert call.headers["x-paddock-signature"] == "v1=" + expected
    assert call.headers["x-paddock-event"] == "comment.created"
    payload = json.loads(body)
    assert payload["type"] == "comment.created"
    assert payload["page_id"] == page_id
    assert payload["data"]["body"] == "@agent hi"

    (row,) = await deliveries()
    assert row.status == "delivered"
    assert row.attempts == 1
    assert row.last_status_code == 200
    assert call.headers["x-paddock-delivery"] == str(row.id)
    assert await webhooks.process_due() == 0  # nothing left to send


async def test_failures_retry_with_growing_waits_and_then_give_up(client, receiver):
    data, page_id = await setup(client)
    await register(client, data, ["comment.created"])
    await comment(client, data, page_id, "hi")
    receiver.answer = 500

    for attempt in range(1, len(webhooks.RETRY_WAITS) + 2):
        assert await webhooks.process_due() == 1
        (row,) = await deliveries()
        assert row.attempts == attempt
        assert row.last_status_code == 500
        assert row.last_error == "The server answered 500"
        if attempt <= len(webhooks.RETRY_WAITS):
            assert row.status == "pending"
            assert row.next_attempt_at is not None
            assert await webhooks.process_due() == 0  # not due yet
            await age_rows("webhook_deliveries", "next_attempt_at", 1)
    assert row.status == "failed"
    assert row.next_attempt_at is None
    await age_rows("webhook_deliveries", "next_attempt_at", 1)
    assert await webhooks.process_due() == 0
    assert len(receiver.calls) == len(webhooks.RETRY_WAITS) + 1


async def test_a_retry_can_succeed(client, receiver):
    data, page_id = await setup(client)
    await register(client, data)
    await comment(client, data, page_id, "hi")
    receiver.fail = httpx.ConnectError("refused")
    await webhooks.process_due()
    (row,) = await deliveries()
    assert row.status == "pending"
    assert "ConnectError" in row.last_error
    receiver.fail = None
    await age_rows("webhook_deliveries", "next_attempt_at", 1)
    await webhooks.process_due()
    (row,) = await deliveries()
    assert (row.status, row.attempts) == ("delivered", 2)


async def test_redirects_are_not_followed(client, monkeypatch):
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(302, headers={"Location": "http://169.254.169.254/"})

    monkeypatch.setattr(
        webhooks, "make_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )
    data, page_id = await setup(client)
    await register(client, data, ["comment.created"])
    await comment(client, data, page_id, "hi")
    await webhooks.process_due()
    assert calls == [URL]
    (row,) = await deliveries()
    assert row.status == "pending"
    assert row.last_status_code == 302


async def test_the_address_is_checked_again_at_delivery(client, receiver, monkeypatch):
    data, page_id = await setup(client)
    await register(client, data, ["comment.created"])
    await comment(client, data, page_id, "hi")

    async def now_private(host):
        return ["10.0.0.9"]  # the name was changed to point inside after sign up

    monkeypatch.setattr(webhooks, "addresses", now_private)
    await webhooks.process_due()
    assert receiver.calls == []
    (row,) = await deliveries()
    assert "private" in row.last_error


async def test_turning_a_webhook_off_stops_pending_deliveries(client, receiver):
    data, page_id = await setup(client)
    hook = (await register(client, data, ["comment.created"])).json()
    await comment(client, data, page_id, "hi")
    await client.patch(f"/v1/webhooks/{hook['id']}", json={"active": False}, headers=auth(data))
    await webhooks.process_due()
    assert receiver.calls == []
    assert (await deliveries())[0].status == "failed"


async def test_deleting_a_webhook_removes_its_deliveries(client):
    data, page_id = await setup(client)
    hook = (await register(client, data)).json()
    await comment(client, data, page_id, "hi")
    await client.delete(f"/v1/webhooks/{hook['id']}", headers=auth(data))
    assert await deliveries() == []


# ------------------------------------------------------------ test button and history


async def test_the_test_call_reports_what_the_receiver_said(client, receiver):
    data, _ = await setup(client)
    hook = (await register(client, data, ["page.deleted"])).json()
    ok = await client.post(f"/v1/webhooks/{hook['id']}/test", headers=auth(data))
    assert ok.status_code == 200
    assert ok.json()["status"] == "delivered"
    assert ok.json()["event_type"] == "webhook.test"  # sent even though the filter excludes it
    assert receiver.calls[0].headers["x-paddock-event"] == "webhook.test"

    receiver.answer = 503
    bad = (await client.post(f"/v1/webhooks/{hook['id']}/test", headers=auth(data))).json()
    assert bad["status"] == "failed"  # a test is tried once
    assert bad["last_status_code"] == 503
    assert await webhooks.process_due() == 0


async def test_delivery_history(client, receiver):
    data, page_id = await setup(client)
    hook = (await register(client, data, ["comment.created"])).json()
    await comment(client, data, page_id, "one")
    await comment(client, data, page_id, "two")
    await webhooks.process_due()
    r = await client.get(f"/v1/webhooks/{hook['id']}/deliveries?limit=1", headers=auth(data))
    assert len(r.json()["items"]) == 1
    full = (await client.get(f"/v1/webhooks/{hook['id']}/deliveries", headers=auth(data))).json()
    assert [i["event_type"] for i in full["items"]] == ["comment.created"] * 2
    assert {i["status"] for i in full["items"]} == {"delivered"}


# ------------------------------------------------------------ the worker


async def wait_for(check, timeout=3.0):
    end = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < end:
        if await check():
            return True
        await asyncio.sleep(0.05)
    return False


async def all_delivered():
    rows = await deliveries()
    return bool(rows) and all(r.status == "delivered" for r in rows)


async def test_the_worker_sends_when_kicked_and_at_start(client, receiver):
    data, page_id = await setup(client)
    await register(client, data, ["comment.created"])
    worker = webhooks.Worker()
    worker.start()
    try:
        await asyncio.sleep(0.1)  # idle: nothing pending
        await comment(client, data, page_id, "wake up")
        worker.kick()  # in the app, the commit kicks the shared worker
        assert await wait_for(all_delivered)
    finally:
        await worker.stop()

    # Deliveries left over from before a restart are sent when the worker starts.
    await comment(client, data, page_id, "while down")
    again = webhooks.Worker()
    again.start()
    try:
        assert await wait_for(all_delivered)
    finally:
        await again.stop()


async def test_seconds_until_next(client, receiver):
    data, page_id = await setup(client)
    assert await webhooks.seconds_until_next() is None
    await register(client, data, ["comment.created"])
    await comment(client, data, page_id, "hi")
    receiver.answer = 500
    await webhooks.process_due()
    wait = await webhooks.seconds_until_next()
    assert 50 < wait <= webhooks.RETRY_WAITS[0]
