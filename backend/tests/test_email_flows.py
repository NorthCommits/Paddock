from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_engine

from .helpers import PASSWORD, auth, link_token, mails_to, make_token, page_body, signup

NEW = "a brand new phrase 77"


async def age_tokens(minutes: int):
    """Pretend the emails were sent some minutes ago (also resets the resend cooldown)."""
    async with AsyncSession(get_engine()) as db:
        await db.execute(
            text(
                "update email_tokens set created_at = created_at - make_interval(mins => :m),"
                " expires_at = expires_at - make_interval(mins => :m)"
            ),
            {"m": minutes},
        )
        await db.commit()


async def test_signup_sends_a_verification_email(client):
    data = await signup(client, verify=False)
    assert data["user"]["email_verified_at"] is None
    mails = mails_to("ana@example.com")
    assert len(mails) == 1
    assert "Confirm" in mails[0].subject
    assert "/verify-email?token=" in mails[0].text
    assert mails[0].html and "Confirm email" in mails[0].html
    for ch in ("—", "–"):
        assert ch not in mails[0].text


async def test_verifying_the_email(client):
    await signup(client, verify=False)
    token = link_token(mails_to("ana@example.com")[0])
    assert (await client.get("/v1/me")).json()["user"]["email_verified_at"] is None
    done = await client.post("/v1/auth/verify-email", json={"token": token})
    assert done.status_code == 204
    assert (await client.get("/v1/me")).json()["user"]["email_verified_at"] is not None


async def test_a_link_works_once_only(client):
    await signup(client, verify=False)
    token = link_token(mails_to("ana@example.com")[0])
    assert (await client.post("/v1/auth/verify-email", json={"token": token})).status_code == 204
    again = await client.post("/v1/auth/verify-email", json={"token": token})
    assert again.status_code == 400
    assert again.json()["error"]["code"] == "invalid_token"


async def test_bad_and_expired_links(client):
    await signup(client, verify=False)
    token = link_token(mails_to("ana@example.com")[0])
    assert (await client.post("/v1/auth/verify-email", json={"token": "x" * 40})).status_code == 400
    await age_tokens(60 * 25)
    assert (await client.post("/v1/auth/verify-email", json={"token": token})).status_code == 400
    assert (await client.post("/v1/auth/verify-email", json={"token": "short"})).status_code == 422


async def test_unverified_users_cannot_publish_or_make_tokens(client):
    data = await signup(client, verify=False)
    page = await client.post("/v1/pages", json=page_body(), headers=auth(data))
    assert page.status_code == 403
    assert page.json()["error"]["code"] == "email_not_verified"
    token = await client.post(
        "/v1/tokens", json={"name": "a", "scopes": ["pages:read"]}, headers=auth(data)
    )
    assert token.status_code == 403
    assert (await client.get("/v1/pages")).status_code == 200  # reading is fine
    assert (await client.get("/v1/me")).status_code == 200

    await client.post(
        "/v1/auth/verify-email", json={"token": link_token(mails_to("ana@example.com")[0])}
    )
    assert (await client.post("/v1/pages", json=page_body(), headers=auth(data))).status_code == 201
    assert (await make_token(client, data))["token"].startswith("pdk_")


async def test_resend_and_cooldown(client):
    data = await signup(client, verify=False)
    early = await client.post("/v1/me/verification/resend", headers=auth(data))
    assert early.status_code == 429
    await age_tokens(5)
    again = await client.post("/v1/me/verification/resend", headers=auth(data))
    assert again.status_code == 204
    mails = mails_to("ana@example.com")
    assert len(mails) == 2
    old, new = link_token(mails[0]), link_token(mails[1])
    assert (await client.post("/v1/auth/verify-email", json={"token": old})).status_code == 400
    assert (await client.post("/v1/auth/verify-email", json={"token": new})).status_code == 204
    # nothing more to send once verified
    await age_tokens(5)
    assert (await client.post("/v1/me/verification/resend", headers=auth(data))).status_code == 204
    assert len(mails_to("ana@example.com")) == 2


async def test_resend_needs_a_browser_session(client):
    data = await signup(client)
    token = (await make_token(client, data))["token"]
    response = await client.post(
        "/v1/me/verification/resend", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403


async def test_forgot_password_answers_the_same_for_everyone(client):
    await signup(client)
    known = await client.post("/v1/auth/forgot-password", json={"email": "ana@example.com"})
    unknown = await client.post("/v1/auth/forgot-password", json={"email": "nobody@example.com"})
    assert known.status_code == unknown.status_code == 204
    assert known.content == unknown.content
    assert len(mails_to("ana@example.com")) == 2  # verification + reset
    assert mails_to("nobody@example.com") == []
    bad = await client.post("/v1/auth/forgot-password", json={"email": "not-an-email"})
    assert bad.status_code == 422


async def test_reset_password_flow(client):
    await signup(client)
    await client.post("/v1/auth/forgot-password", json={"email": "ana@example.com"})
    mail = mails_to("ana@example.com")[-1]
    assert "Reset" in mail.subject and "/reset-password?token=" in mail.text
    token = link_token(mail)

    weak = await client.post(
        "/v1/auth/reset-password", json={"token": token, "new_password": "short"}
    )
    assert weak.status_code == 422
    done = await client.post("/v1/auth/reset-password", json={"token": token, "new_password": NEW})
    assert done.status_code == 204
    again = await client.post("/v1/auth/reset-password", json={"token": token, "new_password": NEW})
    assert again.status_code == 400

    old = await client.post(
        "/v1/auth/login", json={"email": "ana@example.com", "password": PASSWORD}
    )
    assert old.status_code == 401
    new = await client.post("/v1/auth/login", json={"email": "ana@example.com", "password": NEW})
    assert new.status_code == 200


async def test_reset_signs_out_every_browser_and_verifies_the_email(client):
    await signup(client, verify=False)
    assert (await client.get("/v1/me")).status_code == 200
    await client.post("/v1/auth/forgot-password", json={"email": "ana@example.com"})
    token = link_token(mails_to("ana@example.com")[-1])
    await client.post("/v1/auth/reset-password", json={"token": token, "new_password": NEW})
    assert (await client.get("/v1/me")).status_code == 401
    login = await client.post("/v1/auth/login", json={"email": "ana@example.com", "password": NEW})
    assert login.json()["user"]["email_verified_at"] is not None


async def test_reset_links_expire_and_a_new_request_replaces_the_old(client):
    await signup(client)
    await client.post("/v1/auth/forgot-password", json={"email": "ana@example.com"})
    first = link_token(mails_to("ana@example.com")[-1])
    await client.post("/v1/auth/forgot-password", json={"email": "ana@example.com"})
    assert len(mails_to("ana@example.com")) == 2  # second request hit the cooldown, no new mail
    await age_tokens(61)
    stale = await client.post("/v1/auth/reset-password", json={"token": first, "new_password": NEW})
    assert stale.status_code == 400
    await client.post("/v1/auth/forgot-password", json={"email": "ana@example.com"})
    second = link_token(mails_to("ana@example.com")[-1])
    assert second != first
    ok = await client.post("/v1/auth/reset-password", json={"token": second, "new_password": NEW})
    assert ok.status_code == 204


async def test_a_verify_link_cannot_reset_a_password(client):
    await signup(client, verify=False)
    token = link_token(mails_to("ana@example.com")[0])
    response = await client.post(
        "/v1/auth/reset-password", json={"token": token, "new_password": NEW}
    )
    assert response.status_code == 400


async def test_mail_failures_do_not_break_signup(client, outbox):
    class Broken:
        async def send(self, message):
            raise RuntimeError("smtp down")

    from app.services import mailer

    mailer.set_mailer(Broken())
    response = await client.post(
        "/v1/auth/signup",
        json={"email": "z@example.com", "password": PASSWORD, "handle": "zed"},
    )
    assert response.status_code == 201
    await age_tokens(5)
    resend = await client.post(
        "/v1/me/verification/resend", headers={"X-CSRF-Token": response.json()["csrf_token"]}
    )
    assert resend.status_code == 503
