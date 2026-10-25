from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from app.db.models import AuditLog, User, UserSession
from app.db.session import get_sessionmaker
from tests.helpers import PASSWORD, csrf, signup


async def test_signup_creates_a_session_and_returns_the_user(client):
    data = await signup(client)
    assert data["user"]["email"] == "ana@example.com"
    assert data["user"]["handle"] == "ana"
    assert data["user"]["display_name"] == "ana"
    assert data["csrf_token"]
    assert "paddock_session" in client.cookies

    me = await client.get("/v1/me")
    assert me.status_code == 200
    assert me.json()["user"]["handle"] == "ana"
    assert me.json()["csrf_token"] == data["csrf_token"]


async def test_session_cookie_is_http_only_and_lax(client):
    response = await client.post(
        "/v1/auth/signup",
        json={"email": "a@example.com", "password": PASSWORD, "handle": "abe"},
    )
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=lax" in cookie


async def test_password_is_stored_as_an_argon2_hash(client):
    await signup(client)
    async with get_sessionmaker()() as db:
        user = await db.scalar(select(User))
    assert PASSWORD not in user.password_hash
    assert user.password_hash.startswith("$argon2id$")


async def test_session_cookie_value_is_stored_only_as_a_hash(client):
    await signup(client)
    raw = client.cookies["paddock_session"]
    async with get_sessionmaker()() as db:
        stored = await db.scalar(select(UserSession.token_hash))
    assert stored != raw
    assert len(stored) == 64


async def test_duplicate_email_is_rejected(client):
    await signup(client)
    response = await client.post(
        "/v1/auth/signup",
        json={"email": "ANA@example.com", "password": PASSWORD, "handle": "other"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


async def test_duplicate_handle_is_rejected(client):
    await signup(client)
    response = await client.post(
        "/v1/auth/signup",
        json={"email": "b@example.com", "password": PASSWORD, "handle": "ana"},
    )
    assert response.status_code == 409


async def test_bad_signup_input_is_rejected(client):
    base = {"email": "a@example.com", "password": PASSWORD, "handle": "abe"}
    for change in (
        {"password": "short"},
        {"handle": "admin"},
        {"handle": "a"},
        {"handle": "-bad-"},
        {"handle": "has space"},
        {"email": "not-an-email"},
    ):
        response = await client.post("/v1/auth/signup", json={**base, **change})
        assert response.status_code == 422, change
        assert response.json()["error"]["code"] == "validation_failed"


async def test_login_works_with_any_email_case(client):
    await signup(client)
    client.cookies.clear()
    response = await client.post(
        "/v1/auth/login", json={"email": "Ana@Example.com", "password": PASSWORD}
    )
    assert response.status_code == 200
    assert (await client.get("/v1/me")).status_code == 200


async def test_wrong_password_and_unknown_email_look_the_same(client):
    await signup(client)
    client.cookies.clear()
    wrong = await client.post(
        "/v1/auth/login", json={"email": "ana@example.com", "password": "not the password"}
    )
    unknown = await client.post(
        "/v1/auth/login", json={"email": "nobody@example.com", "password": PASSWORD}
    )
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["error"]["message"] == unknown.json()["error"]["message"]


async def test_failed_login_is_recorded_in_the_audit_log(client):
    await signup(client)
    await client.post(
        "/v1/auth/login", json={"email": "ana@example.com", "password": "not the password"}
    )
    async with get_sessionmaker()() as db:
        actions = list(await db.scalars(select(AuditLog.action)))
    assert "user.login_failed" in actions
    assert "user.signup" in actions


async def test_disabled_user_cannot_log_in_or_use_an_existing_session(client):
    await signup(client)
    async with get_sessionmaker()() as db:
        await db.execute(update(User).values(disabled_at=datetime.now(UTC)))
        await db.commit()
    assert (await client.get("/v1/me")).status_code == 401
    client.cookies.clear()
    response = await client.post(
        "/v1/auth/login", json={"email": "ana@example.com", "password": PASSWORD}
    )
    assert response.status_code == 401


async def test_expired_session_is_rejected(client):
    await signup(client)
    async with get_sessionmaker()() as db:
        await db.execute(
            update(UserSession).values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
        )
        await db.commit()
    assert (await client.get("/v1/me")).status_code == 401


async def test_me_requires_sign_in(client):
    response = await client.get("/v1/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


async def test_state_changing_request_needs_the_csrf_token(client):
    await signup(client)
    assert (await client.post("/v1/auth/logout")).status_code == 403
    assert (
        await client.post("/v1/auth/logout", headers={"X-CSRF-Token": "wrong"})
    ).status_code == 403
    assert (await client.get("/v1/me")).status_code == 200  # still signed in


async def test_csrf_token_from_another_session_does_not_work(client):
    first = await signup(client)
    client.cookies.clear()
    await signup(client, email="b@example.com", handle="ben")
    response = await client.post("/v1/auth/logout", headers=csrf(first))
    assert response.status_code == 403


async def test_logout_ends_the_session(client):
    data = await signup(client)
    response = await client.post("/v1/auth/logout", headers=csrf(data))
    assert response.status_code == 204
    assert (await client.get("/v1/me")).status_code == 401
    async with get_sessionmaker()() as db:
        assert await db.scalar(select(UserSession.id)) is None
