from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Depends
from sqlalchemy import select, update

from app.api.deps import Actor, require_scope
from app.db.models import ApiToken
from app.db.session import get_sessionmaker
from app.main import app
from tests.helpers import csrf, make_token, signup


# A small route that needs one scope, used to test scope checks before real routes exist.
@app.get("/_test/needs-pages-read")
async def _needs_pages_read(actor: Annotated[Actor, Depends(require_scope("pages:read"))]):
    return {"ok": True}


def bearer(token: dict) -> dict:
    return {"Authorization": f"Bearer {token['token']}"}


async def test_token_is_shown_once_and_stored_only_as_a_hash(client):
    data = await signup(client)
    token = await make_token(client, data, scopes=("pages:read", "pages:write"))
    assert token["token"].startswith("pdk_")
    assert token["prefix"] == token["token"][:8]
    assert token["scopes"] == ["pages:read", "pages:write"]

    listed = (await client.get("/v1/tokens")).json()
    assert len(listed) == 1
    assert "token" not in listed[0]

    async with get_sessionmaker()() as db:
        stored = await db.scalar(select(ApiToken.token_hash))
    assert stored != token["token"]
    assert len(stored) == 64


async def test_token_authenticates_on_its_own(client):
    data = await signup(client)
    token = await make_token(client, data)
    client.cookies.clear()
    response = await client.get("/v1/me", headers=bearer(token))
    assert response.status_code == 200
    assert response.json()["scopes"] == ["pages:read"]


async def test_token_records_when_it_was_last_used(client):
    data = await signup(client)
    token = await make_token(client, data)
    await client.get("/v1/me", headers=bearer(token))
    listed = (await client.get("/v1/tokens")).json()
    assert listed[0]["last_used_at"] is not None


async def test_scope_is_enforced(client):
    data = await signup(client)
    reader = await make_token(client, data, scopes=("pages:read",))
    writer = await make_token(client, data, scopes=("pages:write",))
    client.cookies.clear()
    assert (await client.get("/_test/needs-pages-read", headers=bearer(reader))).status_code == 200
    denied = await client.get("/_test/needs-pages-read", headers=bearer(writer))
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "forbidden"


async def test_browser_session_has_every_scope(client):
    await signup(client)
    assert (await client.get("/_test/needs-pages-read")).status_code == 200


async def test_a_token_cannot_manage_tokens(client):
    data = await signup(client)
    token = await make_token(client, data, scopes=("pages:read",))
    client.cookies.clear()
    assert (await client.get("/v1/tokens", headers=bearer(token))).status_code == 403
    response = await client.post(
        "/v1/tokens",
        json={"name": "more", "scopes": ["pages:read"]},
        headers=bearer(token),
    )
    assert response.status_code == 403


async def test_unknown_or_malformed_tokens_are_rejected(client):
    assert (
        await client.get("/v1/me", headers={"Authorization": "Bearer pdk_nonsense"})
    ).status_code == 401
    assert (await client.get("/v1/me", headers={"Authorization": "Basic abc"})).status_code == 401


async def test_a_bad_token_does_not_fall_back_to_the_cookie(client):
    await signup(client)  # the cookie is valid
    response = await client.get("/v1/me", headers={"Authorization": "Bearer pdk_nonsense"})
    assert response.status_code == 401


async def test_revoked_token_stops_working(client):
    data = await signup(client)
    token = await make_token(client, data)
    response = await client.delete(f"/v1/tokens/{token['id']}", headers=csrf(data))
    assert response.status_code == 204
    assert (await client.get("/v1/me", headers=bearer(token))).status_code == 401
    assert (await client.get("/v1/tokens")).json()[0]["revoked_at"] is not None


async def test_expired_token_stops_working(client):
    data = await signup(client)
    token = await make_token(client, data, expires_in_days=1)
    async with get_sessionmaker()() as db:
        await db.execute(update(ApiToken).values(expires_at=datetime.now(UTC) - timedelta(hours=1)))
        await db.commit()
    client.cookies.clear()
    assert (await client.get("/v1/me", headers=bearer(token))).status_code == 401


async def test_unknown_scope_and_empty_scopes_are_rejected(client):
    data = await signup(client)
    for scopes in (["admin:everything"], []):
        response = await client.post(
            "/v1/tokens", json={"name": "x", "scopes": scopes}, headers=csrf(data)
        )
        assert response.status_code == 422


async def test_users_cannot_see_or_revoke_each_others_tokens(client):
    ana = await signup(client)
    token = await make_token(client, ana)
    client.cookies.clear()
    ben = await signup(client, email="b@example.com", handle="ben")
    assert (await client.get("/v1/tokens")).json() == []
    response = await client.delete(f"/v1/tokens/{token['id']}", headers=csrf(ben))
    assert response.status_code == 404
