"""Sign in with Neon Auth: token checks, picking a handle, and the profile."""

import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.core import neon
from app.core.errors import AppError

from .helpers import mint_token, signup


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ----- the token check -----


async def test_a_good_token_is_accepted():
    who = await neon.verify(mint_token("ana@example.com", name="Ana Lopez"))
    assert who.email == "ana@example.com"
    assert who.name == "Ana Lopez"
    assert who.email_verified is True


async def test_an_expired_token_is_rejected():
    token = mint_token("ana@example.com", minutes=-5)
    with pytest.raises(AppError) as err:
        await neon.verify(token)
    assert err.value.status == 401


async def test_a_token_signed_with_another_key_is_rejected():
    token = mint_token("ana@example.com", key=Ed25519PrivateKey.generate())
    # The test fixture hands back the real test public key, so a stranger's signature fails.
    with pytest.raises(AppError):
        await neon.verify(token)


async def test_a_token_without_an_email_is_rejected():
    from tests.conftest import TEST_PRIVATE_KEY

    now = int(time.time())
    token = jwt.encode(
        {"sub": "x", "exp": now + 60}, TEST_PRIVATE_KEY, algorithm="EdDSA", headers={"kid": "t"}
    )
    with pytest.raises(AppError):
        await neon.verify(token)


async def test_the_none_algorithm_is_rejected():
    token = jwt.encode({"sub": "x", "email": "a@b.co", "exp": int(time.time()) + 60}, None, "none")
    with pytest.raises(AppError):
        await neon.verify(token)


async def test_email_verified_can_come_from_the_server_setting(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "neon_auth_email_verified", True)
    who = await neon.verify(mint_token("ana@example.com", verified=False))
    assert who.email_verified is True


# ----- onboarding -----


async def test_requests_without_a_token_are_401(client):
    assert (await client.get("/v1/me")).status_code == 401
    assert (await client.get("/v1/onboarding")).status_code == 401


async def test_signed_in_but_no_handle_yet_must_onboard(client):
    token = mint_token("ana@example.com", name="Ana Lopez")
    me = await client.get("/v1/me", headers=bearer(token))
    assert me.status_code == 403
    assert me.json()["error"]["code"] == "onboarding_required"

    state = (await client.get("/v1/onboarding", headers=bearer(token))).json()
    assert state["needs_onboarding"] is True
    assert state["email"] == "ana@example.com"
    assert len(state["suggestions"]) == 5


async def test_suggestions_are_valid_and_free(client):
    await signup(client, email="first@example.com", handle="ana-lopez")
    token = mint_token("ana@example.com", name="Ana Lopez")
    state = (await client.get("/v1/onboarding", headers=bearer(token))).json()
    assert "ana-lopez" not in state["suggestions"]
    for handle in state["suggestions"]:
        check = (
            await client.get("/v1/handles/check", params={"handle": handle}, headers=bearer(token))
        ).json()
        assert check["available"] is True, handle


async def test_choosing_a_handle_creates_the_account(client):
    token = mint_token("ana@example.com", name="Ana Lopez")
    done = await client.post("/v1/onboarding", json={"handle": "Ana-L"}, headers=bearer(token))
    assert done.status_code == 201
    assert done.json()["handle"] == "ana-l"
    assert done.json()["display_name"] == "Ana Lopez"
    assert done.json()["email_verified_at"] is not None

    me = (await client.get("/v1/me", headers=bearer(token))).json()
    assert me["user"]["handle"] == "ana-l"
    state = (await client.get("/v1/onboarding", headers=bearer(token))).json()
    assert state["needs_onboarding"] is False
    assert state["suggestions"] == []


async def test_handle_rules_and_conflicts(client):
    await signup(client, email="ana@example.com", handle="ana")
    token = mint_token("bo@example.com")
    for bad in ("a", "-ana-", "has space", "admin"):
        r = await client.post("/v1/onboarding", json={"handle": bad}, headers=bearer(token))
        assert r.status_code == 422, bad
    taken = await client.post("/v1/onboarding", json={"handle": "ana"}, headers=bearer(token))
    assert taken.status_code == 409
    check = (
        await client.get("/v1/handles/check", params={"handle": "ana"}, headers=bearer(token))
    ).json()
    assert check["available"] is False


async def test_onboarding_twice_is_refused(client):
    token = mint_token("ana@example.com")
    assert (
        await client.post("/v1/onboarding", json={"handle": "ana"}, headers=bearer(token))
    ).status_code == 201
    again = await client.post("/v1/onboarding", json={"handle": "ana2"}, headers=bearer(token))
    assert again.status_code == 409


async def test_unverified_email_blocks_publishing_until_verified(client):
    data = await signup(client, verify=False)
    page = await client.post(
        "/v1/pages",
        json={"title": "T", "files": [{"path": "index.html", "content": "x"}]},
        headers=bearer(data["token"]),
    )
    assert page.status_code == 403
    assert page.json()["error"]["code"] == "email_not_verified"

    # Once Neon reports the address as verified, the next request catches up.
    verified = mint_token("ana@example.com", verified=True)
    page = await client.post(
        "/v1/pages",
        json={"title": "T", "files": [{"path": "index.html", "content": "x"}]},
        headers=bearer(verified),
    )
    assert page.status_code == 201


async def test_profile_name_can_change(client):
    data = await signup(client)
    done = await client.patch(
        "/v1/me", json={"display_name": " Ana L. "}, headers=bearer(data["token"])
    )
    assert done.status_code == 200
    assert done.json()["display_name"] == "Ana L."


async def test_theme_defaults_to_system_and_can_be_saved(client):
    data = await signup(client)
    assert (await client.get("/v1/me", headers=bearer(data["token"]))).json()["user"][
        "theme"
    ] == "system"
    done = await client.patch("/v1/me", json={"theme": "dark"}, headers=bearer(data["token"]))
    assert done.status_code == 200 and done.json()["theme"] == "dark"
    assert (await client.get("/v1/me", headers=bearer(data["token"]))).json()["user"][
        "theme"
    ] == "dark"
    # Changing only the name leaves the theme alone, and back to system works.
    renamed = await client.patch(
        "/v1/me", json={"display_name": "Ana"}, headers=bearer(data["token"])
    )
    assert renamed.json()["theme"] == "dark" and renamed.json()["display_name"] == "Ana"
    back = await client.patch("/v1/me", json={"theme": "system"}, headers=bearer(data["token"]))
    assert back.json()["theme"] == "system"


async def test_theme_must_be_a_known_value_and_something_must_change(client):
    data = await signup(client)
    for body in ({"theme": "purple"}, {}, {"theme": None}):
        r = await client.patch("/v1/me", json=body, headers=bearer(data["token"]))
        assert r.status_code == 422, body


async def test_api_tokens_cannot_change_the_theme(client):
    from .helpers import make_token

    data = await signup(client)
    token = await make_token(client, data)
    r = await client.patch("/v1/me", json={"theme": "dark"}, headers=bearer(token["token"]))
    assert r.status_code == 403


async def test_api_tokens_cannot_edit_the_profile(client):
    from .helpers import make_token

    data = await signup(client)
    token = await make_token(client, data)
    r = await client.patch("/v1/me", json={"display_name": "X"}, headers=bearer(token["token"]))
    assert r.status_code == 403
